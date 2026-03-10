from __future__ import annotations

import os
import time
import unittest
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

PYMYSQL_AVAILABLE = find_spec("pymysql") is not None

if PYMYSQL_AVAILABLE:
    import pymysql

    from backend.repositories.books import (
        BookFilterCriteria,
        BookRepository,
        search_books_by_criteria,
    )
    from db.setup_database import DbConnectionParams, setup_database

REQUIRED_ENV_VARS = (
    "DEV_MYSQL_HOST",
    "DEV_MYSQL_PORT",
    "DEV_MYSQL_USER",
    "DEV_MYSQL_PASSWORD",
)
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


@dataclass(frozen=True)
class FixtureBook:
    title: str
    description: str
    maturity_rating: str
    genre_code: str
    genre_name: str
    author_name: str
    external_source_id: str


@unittest.skipUnless(PYMYSQL_AVAILABLE, "PyMySQL is required")
class BookFilteringIntegrationTests(unittest.TestCase):
    schema_name: str
    params: DbConnectionParams

    @classmethod
    def setUpClass(cls) -> None:
        missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise unittest.SkipTest(
                "Missing required MySQL environment variables: " + ", ".join(missing)
            )

        timestamp_ms = int(time.time() * 1000)
        cls.schema_name = f"dev_find_me_a_book_task302_filter_{timestamp_ms}"[:64]
        cls.params = DbConnectionParams(
            database=cls.schema_name,
            host=os.environ["DEV_MYSQL_HOST"],
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
        )

        setup_result = setup_database(
            params=cls.params,
            schema_path=SCHEMA_PATH,
            migrations_dir=MIGRATIONS_DIR,
        )
        if not setup_result.success:
            raise RuntimeError(
                "Unable to initialize integration schema for filtering tests: "
                f"{setup_result.message}"
            )

        connection = cls._open_connection()
        try:
            cls._seed_fixture_data(connection)
        finally:
            connection.close()

    @classmethod
    def tearDownClass(cls) -> None:
        if not hasattr(cls, "schema_name"):
            return

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
                cursor.execute(f"DROP DATABASE IF EXISTS `{cls.schema_name}`")
        finally:
            connection.close()

    @classmethod
    def _open_connection(cls) -> Any:
        return pymysql.connect(
            host=cls.params.host,
            port=cls.params.port,
            user=cls.params.user,
            password=cls.params.password,
            database=cls.params.database,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @classmethod
    def _seed_fixture_data(cls, connection: Any) -> None:
        fixtures = [
            FixtureBook(
                title="Skybound Companions",
                description=(
                    "A friendship quest through a floating academy where "
                    "allies become chosen family."
                ),
                maturity_rating="general",
                genre_code="fantasy",
                genre_name="Fantasy",
                author_name="Avery Skye",
                external_source_id="task302-skybound",
            ),
            FixtureBook(
                title="Crown of Embers",
                description="A war of betrayal and revenge inside a fallen court.",
                maturity_rating="mature",
                genre_code="fantasy",
                genre_name="Fantasy",
                author_name="Mara Thorne",
                external_source_id="task302-crown",
            ),
            FixtureBook(
                title="Starforge Trials",
                description=(
                    "Teen cadets survive a brutal academy quest with rival "
                    "factions."
                ),
                maturity_rating="teen",
                genre_code="fantasy",
                genre_name="Fantasy",
                author_name="Rowan Pike",
                external_source_id="task302-starforge",
            ),
            FixtureBook(
                title="Orbiting Hearts",
                description="Two rivals discover first love while orbiting Mars.",
                maturity_rating="teen",
                genre_code="romance",
                genre_name="Romance",
                author_name="Jules Ardent",
                external_source_id="task302-orbiting",
            ),
            FixtureBook(
                title="Friendship Banner",
                description="A military chronicle focused on tactics and supply.",
                maturity_rating="general",
                genre_code="fantasy",
                genre_name="Fantasy",
                author_name="Tessa Vale",
                external_source_id="task302-banner",
            ),
        ]

        genre_ids: dict[str, int] = {}
        author_ids: dict[str, int] = {}

        with connection.cursor() as cursor:
            for fixture in fixtures:
                if fixture.genre_code not in genre_ids:
                    cursor.execute(
                        """
                        INSERT INTO genres (code, display_name)
                        VALUES (%s, %s)
                        """,
                        (fixture.genre_code, fixture.genre_name),
                    )
                    genre_ids[fixture.genre_code] = int(cursor.lastrowid)

                if fixture.author_name not in author_ids:
                    cursor.execute(
                        "INSERT INTO authors (full_name) VALUES (%s)",
                        (fixture.author_name,),
                    )
                    author_ids[fixture.author_name] = int(cursor.lastrowid)

                cursor.execute(
                    """
                    INSERT INTO books (
                        title,
                        description,
                        maturity_rating,
                        source_provider,
                        external_source_id
                    ) VALUES (%s, %s, %s, 'goodreads', %s)
                    """,
                    (
                        fixture.title,
                        fixture.description,
                        fixture.maturity_rating,
                        fixture.external_source_id,
                    ),
                )
                book_id = int(cursor.lastrowid)

                cursor.execute(
                    """
                    INSERT INTO book_authors (book_id, author_id, author_order)
                    VALUES (%s, %s, 1)
                    """,
                    (book_id, author_ids[fixture.author_name]),
                )
                cursor.execute(
                    "INSERT INTO book_genres (book_id, genre_id) VALUES (%s, %s)",
                    (book_id, genre_ids[fixture.genre_code]),
                )

    def _repository(self) -> BookRepository:
        connection = self._open_connection()
        self.addCleanup(connection.close)
        return BookRepository(connection)

    def test_seed_records_include_crawler_source_fields(self) -> None:
        connection = self._open_connection()
        self.addCleanup(connection.close)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS row_count
                FROM books
                WHERE source_provider = 'goodreads'
                  AND external_source_id LIKE 'task302-%'
                  AND description IS NOT NULL
                """
            )
            result = cursor.fetchone()

        assert isinstance(result, dict)
        self.assertEqual(int(result["row_count"]), 5)

    def test_genre_and_age_range_filters_return_expected_subset(self) -> None:
        books = self._repository().search(
            BookFilterCriteria(
                genre="fantasy",
                age_min=8,
                age_max=12,
            )
        )

        titles = {book["title"] for book in books}
        self.assertEqual(titles, {"Skybound Companions", "Friendship Banner"})

    def test_spice_level_filter_uses_maturity_rating_mapping(self) -> None:
        books = self._repository().search(
            BookFilterCriteria(
                genre="fantasy",
                spice_level="high",
            )
        )

        self.assertEqual({book["title"] for book in books}, {"Crown of Embers"})

    def test_subject_filter_uses_description_not_title_only(self) -> None:
        books = self._repository().search(
            BookFilterCriteria(
                genre="fantasy",
                subject_matter=("friendship",),
            )
        )

        self.assertEqual({book["title"] for book in books}, {"Skybound Companions"})

    def test_combined_filters_via_application_query_path(self) -> None:
        books = search_books_by_criteria(
            {
                "host": self.params.host,
                "port": self.params.port,
                "user": self.params.user,
                "password": self.params.password,
                "database": self.params.database,
                "charset": "utf8mb4",
            },
            criteria=BookFilterCriteria(
                query="academy quest rival",
                genre="fantasy",
                age_rating="teen",
                subject_matter=("academy",),
                plot_points=("quest",),
                character_dynamics=("rival",),
                spice_level="medium",
                age_min=13,
                age_max=17,
            ),
        )

        self.assertEqual([book["title"] for book in books], ["Starforge Trials"])


if __name__ == "__main__":
    unittest.main()
