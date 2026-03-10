from __future__ import annotations

import os
import time
import unittest
from importlib.util import find_spec
from pathlib import Path
from typing import Any

FLASK_AVAILABLE = find_spec("flask") is not None
PYMYSQL_AVAILABLE = find_spec("pymysql") is not None
if FLASK_AVAILABLE and PYMYSQL_AVAILABLE:
    import pymysql

    from backend.app import create_app
    from backend.config import AppConfig, DatabaseConfig

REQUIRED_ENV_VARS = (
    "DEV_MYSQL_HOST",
    "DEV_MYSQL_PORT",
    "DEV_MYSQL_USER",
    "DEV_MYSQL_PASSWORD",
)
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


@unittest.skipUnless(
    FLASK_AVAILABLE and PYMYSQL_AVAILABLE,
    "Flask and PyMySQL are required for API integration tests",
)
class BooksApiIntegrationTests(unittest.TestCase):
    schema_name: str
    db_config: DatabaseConfig
    app_config: AppConfig
    seeded_titles: dict[str, str]

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

        suffix = f"task244_{int(time.time() * 1000)}"
        cls.schema_name = f"dev_find_me_a_book_{suffix}"[:64]

        host = os.environ["DEV_MYSQL_HOST"]
        port = int(os.environ["DEV_MYSQL_PORT"])
        user = os.environ["DEV_MYSQL_USER"]
        password = os.environ["DEV_MYSQL_PASSWORD"]

        admin_connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with admin_connection.cursor() as cursor:
                cursor.execute(
                    (
                        "CREATE DATABASE IF NOT EXISTS `"
                        f"{cls.schema_name}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
        finally:
            admin_connection.close()

        cls.db_config = DatabaseConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            database=cls.schema_name,
            charset="utf8mb4",
        )

        setup_connection = cls._open_connection()
        try:
            cls._apply_migration_scripts(setup_connection)
            cls.seeded_titles = cls._seed_fixture_data(setup_connection)
        finally:
            setup_connection.close()

        cls.app_config = AppConfig(debug=False, log_level="INFO", database=cls.db_config)
        cls.app = create_app(config=cls.app_config)
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        if not hasattr(cls, "schema_name"):
            return

        host = os.environ.get("DEV_MYSQL_HOST")
        port = os.environ.get("DEV_MYSQL_PORT")
        user = os.environ.get("DEV_MYSQL_USER")
        password = os.environ.get("DEV_MYSQL_PASSWORD")
        if not host or not port or not user or password is None:
            return

        admin_connection = pymysql.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with admin_connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{cls.schema_name}`")
        finally:
            admin_connection.close()

    @classmethod
    def _open_connection(cls) -> Any:
        return pymysql.connect(
            host=cls.db_config.host,
            port=cls.db_config.port,
            user=cls.db_config.user,
            password=cls.db_config.password,
            database=cls.db_config.database,
            charset=cls.db_config.charset,
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @classmethod
    def _apply_migration_scripts(cls, connection: Any) -> None:
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
    def _seed_fixture_data(cls, connection: Any) -> dict[str, str]:
        seed_tag = cls.schema_name.replace("dev_find_me_a_book_", "")
        genre_code_tag = "".join(
            ch if ch.isalnum() else "-" for ch in seed_tag.lower()
        ).strip("-")

        def make_title(base: str) -> str:
            return f"{base} [{seed_tag}]"

        titles = {
            "fantasy_general": make_title("Starlight Friends"),
            "fantasy_supporting": make_title("Moonlit Bonds"),
            "scifi_teen": make_title("Galactic Academy"),
            "romance_mature": make_title("Midnight Oath"),
            "nonfiction_general": make_title("Quiet Gardens"),
        }

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO authors (full_name) VALUES (%s)",
                (f"Alex Lantern {seed_tag}",),
            )
            fantasy_author_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO authors (full_name) VALUES (%s)",
                (f"Nova Rivers {seed_tag}",),
            )
            scifi_author_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO authors (full_name) VALUES (%s)",
                (f"Riley Ember {seed_tag}",),
            )
            romance_author_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO authors (full_name) VALUES (%s)",
                (f"Casey Bloom {seed_tag}",),
            )
            nonfiction_author_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
                (f"{genre_code_tag[:24]}-fantasy", "Fantasy"),
            )
            fantasy_genre_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
                (f"{genre_code_tag[:24]}-scifi", "Science Fiction"),
            )
            scifi_genre_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
                (f"{genre_code_tag[:24]}-romance", "Romance"),
            )
            romance_genre_id = int(cursor.lastrowid)

            cursor.execute(
                "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
                (f"{genre_code_tag[:24]}-nonfiction", "Nonfiction"),
            )
            nonfiction_genre_id = int(cursor.lastrowid)

            book_ids: dict[str, int] = {}
            books_to_create = [
                (
                    "fantasy_general",
                    titles["fantasy_general"],
                    "A friendship quest beneath a comet.",
                    "general",
                    fantasy_author_id,
                    fantasy_genre_id,
                ),
                (
                    "fantasy_supporting",
                    titles["fantasy_supporting"],
                    "A friendship tale in starlight valley.",
                    "general",
                    fantasy_author_id,
                    fantasy_genre_id,
                ),
                (
                    "scifi_teen",
                    titles["scifi_teen"],
                    "Academy cadets face rivalry and loyalty tests.",
                    "teen",
                    scifi_author_id,
                    scifi_genre_id,
                ),
                (
                    "romance_mature",
                    titles["romance_mature"],
                    "A forbidden romance with betrayal and desire.",
                    "mature",
                    romance_author_id,
                    romance_genre_id,
                ),
                (
                    "nonfiction_general",
                    titles["nonfiction_general"],
                    "Practical botanical essays for patient gardeners.",
                    "general",
                    nonfiction_author_id,
                    nonfiction_genre_id,
                ),
            ]

            for key, title, description, maturity_rating, author_id, genre_id in books_to_create:
                cursor.execute(
                    """
                    INSERT INTO books (
                        title,
                        description,
                        maturity_rating,
                        source_provider,
                        external_source_id
                    ) VALUES (%s, %s, %s, 'api-test-suite', %s)
                    """,
                    (title, description, maturity_rating, key),
                )
                book_id = int(cursor.lastrowid)
                book_ids[key] = book_id

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

        return titles

    def _response_titles(self, response_json: list[dict[str, Any]]) -> set[str]:
        return {entry["title"] for entry in response_json}

    def test_search_q_returns_matching_books(self) -> None:
        response = self.client.get("/api/books?q=starlight")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload, list)
        assert isinstance(payload, list)
        self.assertGreaterEqual(len(payload), 2)
        self.assertEqual(payload[0]["title"], self.seeded_titles["fantasy_general"])
        titles = self._response_titles(payload)
        self.assertEqual(
            titles,
            {
                self.seeded_titles["fantasy_general"],
                self.seeded_titles["fantasy_supporting"],
            },
        )

    def test_search_q_returns_empty_list_for_no_match(self) -> None:
        response = self.client.get("/api/books?q=zzzz-no-matching-book")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload, [])

    def test_filter_by_genre(self) -> None:
        response = self.client.get("/api/books?genre=Fantasy")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert isinstance(payload, list)
        self.assertEqual(
            self._response_titles(payload),
            {self.seeded_titles["fantasy_general"]},
        )

    def test_filter_by_subject(self) -> None:
        response = self.client.get("/api/books?subject=botanical")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert isinstance(payload, list)
        self.assertEqual(
            self._response_titles(payload),
            {self.seeded_titles["nonfiction_general"]},
        )

    def test_filter_by_spice_level(self) -> None:
        response = self.client.get("/api/books?spice_level=high")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert isinstance(payload, list)
        self.assertEqual(
            self._response_titles(payload),
            {self.seeded_titles["romance_mature"]},
        )

    def test_filter_by_age_range(self) -> None:
        response = self.client.get("/api/books?age_min=13&age_max=17")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert isinstance(payload, list)
        self.assertEqual(
            self._response_titles(payload),
            {self.seeded_titles["scifi_teen"]},
        )

    def test_combined_filters_return_intersection(self) -> None:
        response = self.client.get(
            (
                "/api/books?genre=fantasy"
                "&subject_matter=friendship"
                "&spice_level=low"
                "&age_min=8"
                "&age_max=12"
            )
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        assert isinstance(payload, list)
        self.assertEqual(
            self._response_titles(payload),
            {self.seeded_titles["fantasy_general"]},
        )

    def test_advanced_filter_combination_and_monotonic_subset(self) -> None:
        broad = self.client.get("/api/books/search?genre=fantasy&spice_level=low")
        self.assertEqual(broad.status_code, 200)
        broad_payload = broad.get_json()
        assert isinstance(broad_payload, list)
        broad_titles = self._response_titles(broad_payload)
        self.assertEqual(
            broad_titles,
            {
                self.seeded_titles["fantasy_general"],
                self.seeded_titles["fantasy_supporting"],
            },
        )

        narrow = self.client.get(
            (
                "/api/books/search?genre=fantasy&spice_level=low"
                "&subject_matter=friendship"
                "&plot_points=quest"
                "&character_dynamics=friendship"
            )
        )
        self.assertEqual(narrow.status_code, 200)
        narrow_payload = narrow.get_json()
        assert isinstance(narrow_payload, list)
        narrow_titles = self._response_titles(narrow_payload)
        self.assertEqual(narrow_titles, {self.seeded_titles["fantasy_general"]})
        self.assertLessEqual(len(narrow_payload), len(broad_payload))

    def test_invalid_age_min_returns_400_json_error(self) -> None:
        response = self.client.get("/api/books?age_min=abc")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        assert isinstance(payload, dict)
        self.assertEqual(payload.get("error"), "invalid_parameter")
        self.assertIn("age_min must be an integer", payload.get("message", ""))

    def test_invalid_age_rating_returns_400_json_error(self) -> None:
        response = self.client.get("/api/books?age_rating=unknown-level")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        assert isinstance(payload, dict)
        self.assertEqual(payload.get("error"), "invalid_parameter")
        self.assertIn("age_rating must be one of", payload.get("message", ""))


if __name__ == "__main__":
    unittest.main()
