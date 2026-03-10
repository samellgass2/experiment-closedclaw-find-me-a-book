from __future__ import annotations

import os
import time
import unittest
from importlib.util import find_spec
from pathlib import Path
from typing import Any

PYMYSQL_AVAILABLE = find_spec("pymysql") is not None

if PYMYSQL_AVAILABLE:
    import pymysql

    from backend.repositories.books import BookFilterCriteria, BookRepository

REQUIRED_ENV_VARS = (
    "DEV_MYSQL_HOST",
    "DEV_MYSQL_PORT",
    "DEV_MYSQL_USER",
    "DEV_MYSQL_PASSWORD",
)
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


@unittest.skipUnless(PYMYSQL_AVAILABLE, "PyMySQL is required")
class RelevanceRankingIntegrationTests(unittest.TestCase):
    schema_name: str

    @classmethod
    def setUpClass(cls) -> None:
        missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise unittest.SkipTest(
                "Missing required MySQL environment variables: " + ", ".join(missing)
            )

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            raise unittest.SkipTest(f"No migration files found: {MIGRATIONS_DIR}")

        suffix = f"task273_rank_{int(time.time() * 1000)}"
        cls.schema_name = f"dev_find_me_a_book_{suffix}"[:64]

        cls._create_schema(cls.schema_name)
        connection = cls._open_connection(cls.schema_name)
        try:
            cls._apply_migrations(connection)
            cls._seed_fixture_data(connection)
        finally:
            connection.close()

    @classmethod
    def tearDownClass(cls) -> None:
        if not hasattr(cls, "schema_name"):
            return
        cls._drop_schema(cls.schema_name)

    @classmethod
    def _create_schema(cls, schema_name: str) -> None:
        connection = pymysql.connect(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    (
                        "CREATE DATABASE IF NOT EXISTS `"
                        f"{schema_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
        finally:
            connection.close()

    @classmethod
    def _drop_schema(cls, schema_name: str) -> None:
        connection = pymysql.connect(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{schema_name}`")
        finally:
            connection.close()

    @classmethod
    def _open_connection(cls, schema_name: str) -> Any:
        return pymysql.connect(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            database=schema_name,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @classmethod
    def _apply_migrations(cls, connection: Any) -> None:
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        with connection.cursor() as cursor:
            for migration_path in migration_files:
                raw_sql = migration_path.read_text(encoding="utf-8")
                lines = [
                    line
                    for line in raw_sql.splitlines()
                    if not line.strip().startswith("--")
                ]
                script_without_comments = "\n".join(lines)
                statements = [
                    statement.strip()
                    for statement in script_without_comments.split(";")
                    if statement.strip()
                ]
                for statement in statements:
                    cursor.execute(statement)

    @classmethod
    def _seed_fixture_data(cls, connection: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
                ("fantasy", "Fantasy"),
            )
            fantasy_genre_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
                ("romance", "Romance"),
            )
            romance_genre_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO authors (full_name) VALUES (%s)",
                ("Avery Sky",),
            )
            sky_author_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO authors (full_name) VALUES (%s)",
                ("Morgan Vale",),
            )
            vale_author_id = int(cursor.lastrowid)

            books = [
                (
                    "Starlight Friendship Quest",
                    (
                        "friendship friendship friendship quest quest rivals "
                        "rivals found-family"
                    ),
                    "general",
                    "rank-best",
                    sky_author_id,
                    fantasy_genre_id,
                ),
                (
                    "Valley Quest",
                    "friendship quest rivals",
                    "general",
                    "rank-mid",
                    sky_author_id,
                    fantasy_genre_id,
                ),
                (
                    "Ember Oath Gentle",
                    "romance oath and trust",
                    "general",
                    "romance-low",
                    vale_author_id,
                    romance_genre_id,
                ),
                (
                    "Ember Oath Midnight",
                    "romance oath and desire",
                    "mature",
                    "romance-high",
                    vale_author_id,
                    romance_genre_id,
                ),
            ]

            for (
                title,
                description,
                maturity_rating,
                external_source_id,
                author_id,
                genre_id,
            ) in books:
                cursor.execute(
                    """
                    INSERT INTO books (
                        title,
                        description,
                        maturity_rating,
                        source_provider,
                        external_source_id
                    ) VALUES (%s, %s, %s, 'task273-tests', %s)
                    """,
                    (
                        title,
                        description,
                        maturity_rating,
                        external_source_id,
                    ),
                )
                book_id = int(cursor.lastrowid)
                cursor.execute(
                    """
                    INSERT INTO book_authors (book_id, author_id, author_order)
                    VALUES (%s, %s, 1)
                    """,
                    (book_id, author_id),
                )
                cursor.execute(
                    "INSERT INTO book_genres (book_id, genre_id) VALUES (%s, %s)",
                    (book_id, genre_id),
                )

    def _repository(self) -> BookRepository:
        connection = self._open_connection(self.schema_name)
        self.addCleanup(connection.close)
        return BookRepository(connection=connection)

    def test_multi_criteria_matches_rank_above_weaker_matches(self) -> None:
        repository = self._repository()
        books = repository.search(
            BookFilterCriteria(
                query="friendship quest",
                genre="fantasy",
                age_rating="general",
                subject_matter=("friendship",),
                plot_points=("quest",),
                character_dynamics=("rivals",),
            )
        )

        self.assertGreaterEqual(len(books), 2)
        self.assertEqual(books[0]["title"], "Starlight Friendship Quest")
        self.assertEqual(books[1]["title"], "Valley Quest")

    def test_spice_level_preference_changes_top_result(self) -> None:
        repository = self._repository()
        low_spice = repository.search(
            BookFilterCriteria(
                query="Ember Oath",
                genre="romance",
                spice_level="low",
            )
        )
        high_spice = repository.search(
            BookFilterCriteria(
                query="Ember Oath",
                genre="romance",
                spice_level="high",
            )
        )

        self.assertTrue(low_spice)
        self.assertTrue(high_spice)
        self.assertEqual(low_spice[0]["title"], "Ember Oath Gentle")
        self.assertEqual(high_spice[0]["title"], "Ember Oath Midnight")


if __name__ == "__main__":
    unittest.main()
