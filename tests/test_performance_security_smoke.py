from __future__ import annotations

import ast
import os
import re
import statistics
import time
import unittest
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

PYMYSQL_AVAILABLE = find_spec("pymysql") is not None

if PYMYSQL_AVAILABLE:
    import pymysql

from backend.repositories.books import BookFilterCriteria, BookRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
REQUIRED_ENV_VARS = (
    "DEV_MYSQL_HOST",
    "DEV_MYSQL_PORT",
    "DEV_MYSQL_USER",
    "DEV_MYSQL_PASSWORD",
)


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class QueryScenario:
    name: str
    criteria: BookFilterCriteria
    p95_budget_ms: float


class _RecordingCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.executions: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> "_RecordingCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _RecordingConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.cursor_impl = _RecordingCursor(rows)

    def cursor(self) -> _RecordingCursor:
        return self.cursor_impl


class RepositorySecuritySmokeTests(unittest.TestCase):
    def test_query_builder_keeps_untrusted_filter_values_out_of_sql_text(self) -> None:
        injection_like_value = "fantasy' OR 1=1 --"
        subject_filter = "friendship%' OR '1'='1"
        criteria = BookFilterCriteria(
            query="dragon') OR 1=1 --",
            genre=injection_like_value,
            subject_matter=(subject_filter,),
            plot_points=("betrayal; DROP TABLE books;",),
            character_dynamics=("found-family",),
            age_rating="teen",
            age_min=12,
            age_max=17,
            limit=10,
        )

        repository = BookRepository(connection=_RecordingConnection(rows=[]))
        sql, params = repository._build_books_query(criteria=criteria)

        self.assertEqual(sql.count("%s"), len(params))
        self.assertNotIn(injection_like_value, sql)
        self.assertNotIn(subject_filter, sql)
        self.assertIn(injection_like_value, params)
        self.assertTrue(any("DROP TABLE" in str(value) for value in params))

    def test_query_execution_passes_sql_and_parameter_tuple_to_driver(self) -> None:
        row = {
            "id": 1,
            "title": "Safety Check",
            "author": "Test Author",
            "genre": "Fantasy",
            "age_rating": "general",
            "description": "A safe query execution path.",
        }
        connection = _RecordingConnection(rows=[row])
        repository = BookRepository(connection=connection)

        repository.search(
            BookFilterCriteria(
                query="friendship",
                genre="fantasy",
                subject_matter=("allies",),
                limit=5,
            )
        )

        self.assertEqual(len(connection.cursor_impl.executions), 1)
        executed_sql, executed_params = connection.cursor_impl.executions[0]
        self.assertIn("%s", executed_sql)
        self.assertIsInstance(executed_params, tuple)
        self.assertGreater(len(executed_params), 0)

    def test_build_books_query_source_disallows_interpolating_user_input_names(self) -> None:
        source_text = Path(REPO_ROOT / "backend" / "repositories" / "books.py").read_text(
            encoding="utf-8"
        )
        module = ast.parse(source_text)

        build_query_node: ast.FunctionDef | None = None
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name == "_build_books_query":
                build_query_node = node
                break

        self.assertIsNotNone(build_query_node, "Could not locate _build_books_query.")

        user_input_names = {
            "query",
            "normalized_query",
            "like_pattern",
            "prefix_pattern",
            "boolean_query",
            "genre",
            "age_rating",
            "normalized_age_rating",
            "subject_matter",
            "plot_point",
            "dynamic",
            "spice_level",
            "maturity_rating",
            "age_min",
            "age_max",
        }

        sql_clause_collections = {
            "where_clauses",
            "relevance_terms",
            "candidate_query",
            "outer_query",
        }

        class UnsafeInterpolationVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.offenders: list[str] = []
                self._parents: dict[int, ast.AST] = {}

            def visit(self, node: ast.AST) -> Any:
                for child in ast.iter_child_nodes(node):
                    self._parents[id(child)] = node
                return super().visit(node)

            def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
                if not self._is_sql_clause_append(node):
                    self.generic_visit(node)
                    return
                for value in node.values:
                    if isinstance(value, ast.FormattedValue):
                        name = self._extract_name(value.value)
                        if name in user_input_names:
                            self.offenders.append(name)
                self.generic_visit(node)

            def _extract_name(self, node: ast.AST) -> str | None:
                if isinstance(node, ast.Name):
                    return node.id
                return None

            def _is_sql_clause_append(self, node: ast.AST) -> bool:
                current = node
                while id(current) in self._parents:
                    parent = self._parents[id(current)]
                    if (
                        isinstance(parent, ast.Call)
                        and isinstance(parent.func, ast.Attribute)
                        and parent.func.attr == "append"
                        and isinstance(parent.func.value, ast.Name)
                        and parent.func.value.id in sql_clause_collections
                    ):
                        return True
                    current = parent
                return False

        assert build_query_node is not None
        visitor = UnsafeInterpolationVisitor()
        visitor.visit(build_query_node)

        self.assertEqual(
            visitor.offenders,
            [],
            (
                "Unsafe SQL interpolation detected in _build_books_query for "
                f"variables: {', '.join(visitor.offenders)}"
            ),
        )


@unittest.skipUnless(PYMYSQL_AVAILABLE, "PyMySQL is required for MySQL smoke tests")
class SearchPerformanceSmokeTests(unittest.TestCase):
    schema_name: str
    db_config: DbConfig

    @classmethod
    def setUpClass(cls) -> None:
        missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise unittest.SkipTest(
                "Missing required MySQL environment variables: " + ", ".join(missing)
            )

        cls.db_config = DbConfig(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
        )
        cls.schema_name = f"dev_find_me_a_book_task304_smoke_{int(time.time() * 1000)}"[:64]

        cls._create_schema()
        connection = cls._open_schema_connection()
        try:
            cls._apply_migrations(connection)
            cls._seed_dataset(connection, seed_size=1200)
        finally:
            connection.close()

    @classmethod
    def tearDownClass(cls) -> None:
        if not hasattr(cls, "schema_name"):
            return
        cls._drop_schema()

    @classmethod
    def _open_admin_connection(cls) -> Any:
        assert PYMYSQL_AVAILABLE
        return pymysql.connect(
            host=cls.db_config.host,
            port=cls.db_config.port,
            user=cls.db_config.user,
            password=cls.db_config.password,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @classmethod
    def _open_schema_connection(cls) -> Any:
        assert PYMYSQL_AVAILABLE
        return pymysql.connect(
            host=cls.db_config.host,
            port=cls.db_config.port,
            user=cls.db_config.user,
            password=cls.db_config.password,
            database=cls.schema_name,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @classmethod
    def _create_schema(cls) -> None:
        with cls._open_admin_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    (
                        "CREATE DATABASE IF NOT EXISTS `"
                        f"{cls.schema_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )

    @classmethod
    def _drop_schema(cls) -> None:
        with cls._open_admin_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{cls.schema_name}`")

    @classmethod
    def _apply_migrations(cls, connection: Any) -> None:
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            raise RuntimeError(f"No migration files found in {MIGRATIONS_DIR}")

        with connection.cursor() as cursor:
            for migration_path in migration_files:
                raw_sql = migration_path.read_text(encoding="utf-8")
                lines = [
                    line
                    for line in raw_sql.splitlines()
                    if not line.strip().startswith("--")
                ]
                statements = [
                    statement.strip()
                    for statement in "\n".join(lines).split(";")
                    if statement.strip()
                ]
                for statement in statements:
                    cursor.execute(statement)

    @classmethod
    def _seed_dataset(cls, connection: Any, seed_size: int) -> None:
        genre_rows = [
            ("fantasy", "Fantasy"),
            ("science-fiction", "Science Fiction"),
            ("romance", "Romance"),
            ("mystery", "Mystery"),
        ]

        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
                genre_rows,
            )
            cursor.execute("SELECT id, code FROM genres")
            genre_lookup = {str(row["code"]): int(row["id"]) for row in cursor.fetchall()}

            author_values = [(f"Perf Author {index:04d}",) for index in range(seed_size // 4)]
            cursor.executemany(
                "INSERT INTO authors (full_name) VALUES (%s)",
                author_values,
            )
            cursor.execute("SELECT id FROM authors ORDER BY id")
            author_ids = [int(row["id"]) for row in cursor.fetchall()]

            books_to_insert: list[tuple[str, str, str, str]] = []
            for index in range(seed_size):
                if index % 4 == 0:
                    genre_code = "fantasy"
                    maturity = "general"
                    description = (
                        "friendship quest academy allies rival houses and magic "
                        "friendship themes"
                    )
                elif index % 4 == 1:
                    genre_code = "science-fiction"
                    maturity = "teen"
                    description = "academy cadets rivalry planets diplomacy and loyalty"
                elif index % 4 == 2:
                    genre_code = "romance"
                    maturity = "mature"
                    description = "romance tension desire betrayal second-chance devotion"
                else:
                    genre_code = "mystery"
                    maturity = "general"
                    description = "detective clues puzzle family secrets and quiet suspense"

                books_to_insert.append(
                    (
                        f"Task304 Book {index:05d} {genre_code}",
                        description,
                        maturity,
                        f"task304-seed-{index:05d}",
                    )
                )

            cursor.executemany(
                """
                INSERT INTO books (
                    title,
                    description,
                    maturity_rating,
                    source_provider,
                    external_source_id
                ) VALUES (%s, %s, %s, 'benchmark', %s)
                """,
                books_to_insert,
            )

            cursor.execute("SELECT id FROM books ORDER BY id")
            book_ids = [int(row["id"]) for row in cursor.fetchall()]

            book_author_rows: list[tuple[int, int, int]] = []
            book_genre_rows: list[tuple[int, int]] = []
            for index, book_id in enumerate(book_ids):
                author_id = author_ids[index % len(author_ids)]
                genre_code = genre_rows[index % 4][0]
                genre_id = genre_lookup[genre_code]
                book_author_rows.append((book_id, author_id, 1))
                book_genre_rows.append((book_id, genre_id))

            cursor.executemany(
                """
                INSERT INTO book_authors (book_id, author_id, author_order)
                VALUES (%s, %s, %s)
                """,
                book_author_rows,
            )
            cursor.executemany(
                "INSERT INTO book_genres (book_id, genre_id) VALUES (%s, %s)",
                book_genre_rows,
            )

    @staticmethod
    def _percentile(values: list[float], percent: float) -> float:
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * percent
        lower = int(rank)
        upper = min(lower + 1, len(ordered) - 1)
        weight = rank - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    def test_representative_filter_queries_stay_within_p95_budget(self) -> None:
        scenarios = [
            QueryScenario(
                name="query-genre-subject-spice",
                criteria=BookFilterCriteria(
                    query="friendship quest",
                    genre="fantasy",
                    spice_level="low",
                    subject_matter=("friendship",),
                    plot_points=("quest",),
                    age_min=8,
                    age_max=17,
                    limit=20,
                ),
                p95_budget_ms=450.0,
            ),
            QueryScenario(
                name="query-age-rating-character",
                criteria=BookFilterCriteria(
                    query="academy rivalry",
                    genre="science-fiction",
                    age_rating="teen",
                    subject_matter=("academy",),
                    character_dynamics=("rivalry",),
                    age_min=13,
                    age_max=17,
                    limit=20,
                ),
                p95_budget_ms=450.0,
            ),
            QueryScenario(
                name="browse-filter-only",
                criteria=BookFilterCriteria(
                    query=None,
                    genre="mystery",
                    age_min=10,
                    age_max=30,
                    limit=20,
                ),
                p95_budget_ms=300.0,
            ),
        ]

        connection = self._open_schema_connection()
        self.addCleanup(connection.close)
        repository = BookRepository(connection=connection)

        for scenario in scenarios:
            repository.search(scenario.criteria)

            timings_ms: list[float] = []
            for _ in range(6):
                start = time.perf_counter()
                results = repository.search(scenario.criteria)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                timings_ms.append(elapsed_ms)
                self.assertGreater(
                    len(results),
                    0,
                    f"Scenario {scenario.name} unexpectedly returned no rows.",
                )

            p95_ms = self._percentile(timings_ms, 0.95)
            mean_ms = statistics.fmean(timings_ms)
            self.assertLessEqual(
                p95_ms,
                scenario.p95_budget_ms,
                (
                    f"{scenario.name} exceeded p95 budget: "
                    f"{p95_ms:.2f}ms > {scenario.p95_budget_ms:.2f}ms "
                    f"(mean={mean_ms:.2f}ms, samples={timings_ms})"
                ),
            )


class ConfigSecretSmokeTests(unittest.TestCase):
    def test_example_and_strategy_files_do_not_contain_real_db_password_values(self) -> None:
        candidate_paths: set[Path] = {
            REPO_ROOT / "TESTING_STRATEGY.md",
            REPO_ROOT / "README.md",
        }
        for path in REPO_ROOT.rglob("*.example"):
            candidate_paths.add(path)
        for path in REPO_ROOT.rglob("*.env.example"):
            candidate_paths.add(path)

        password_assignment = re.compile(r"DEV_MYSQL_PASSWORD\s*=\s*([^\s]+)")
        disallowed_exact_values = {
            "2d81badcbb5dd418bebc80fad81bb6e5",
        }
        allowed_markers = {
            "...",
            "<password>",
            "<provided",
            "${DEV_MYSQL_PASSWORD}",
            "$DEV_MYSQL_PASSWORD",
        }

        offenders: list[str] = []
        for path in sorted(candidate_paths):
            if not path.exists() or not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            for match in password_assignment.finditer(content):
                value = match.group(1).strip().strip("'\"")
                lowered = value.lower()
                if value in disallowed_exact_values:
                    offenders.append(f"{path}: leaked concrete password value")
                    continue
                if any(marker in lowered for marker in allowed_markers):
                    continue
                if lowered in {"password", "changeme", "example", "secret"}:
                    continue
                if lowered.startswith("<") and lowered.endswith(">"):
                    continue
                offenders.append(f"{path}: suspicious DEV_MYSQL_PASSWORD={value}")

        self.assertEqual(offenders, [], "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
