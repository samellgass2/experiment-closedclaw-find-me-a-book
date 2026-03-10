from __future__ import annotations

import os
import time
import unittest
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from crawler.goodreads_crawler import BookRecord, GoodreadsCrawler, MySQLBookRepository, run_cli

PYMYSQL_AVAILABLE = find_spec("pymysql") is not None

if PYMYSQL_AVAILABLE:
    import pymysql

    from backend.repositories.books import BookFilterCriteria, BookRepository
    from db.setup_database import DbConnectionParams, setup_database


REQUIRED_ENV_VARS = (
    "DEV_MYSQL_HOST",
    "DEV_MYSQL_PORT",
    "DEV_MYSQL_USER",
    "DEV_MYSQL_PASSWORD",
)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "goodreads"
SEARCH_FIXTURE_PATH = FIXTURES_DIR / "search_result_sample.html"
BOOK_FIXTURE_PATH = FIXTURES_DIR / "book_detail_sample.html"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


@dataclass(frozen=True)
class CrawlFixtureValues:
    external_id: str
    slug: str
    title: str
    description: str
    isbn_13: str
    primary_author: str
    secondary_author: str


@unittest.skipUnless(PYMYSQL_AVAILABLE, "PyMySQL is required")
class CrawlerValidationSmokeTests(unittest.TestCase):
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
        cls.schema_name = f"dev_find_me_a_book_task303_crawler_{timestamp_ms}"[:64]
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
                "Unable to initialize integration schema for crawler smoke tests: "
                f"{setup_result.message}"
            )

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
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @staticmethod
    def _render_fixture(template: str, values: CrawlFixtureValues) -> str:
        rendered = template
        replacements = {
            "__BOOK_ID__": values.external_id,
            "__BOOK_SLUG__": values.slug,
            "__BOOK_TITLE__": values.title,
            "__BOOK_DESCRIPTION__": values.description,
            "__BOOK_ISBN13__": values.isbn_13,
            "__PRIMARY_AUTHOR__": values.primary_author,
            "__SECONDARY_AUTHOR__": values.secondary_author,
        }
        for marker, replacement in replacements.items():
            rendered = rendered.replace(marker, replacement)
        return rendered

    @staticmethod
    def _fixture_values(prefix: str) -> CrawlFixtureValues:
        suffix = str(int(time.time() * 1000))[-8:]
        return CrawlFixtureValues(
            external_id=f"{prefix}{suffix}",
            slug="crawler-validation-smoke",
            title=f"Crawler Validation {prefix} {suffix}",
            description=(
                "A found family survives academy rivalries and learns to trust."
            ),
            isbn_13=f"97812{suffix}",
            primary_author=f"Primary Author {suffix}",
            secondary_author=f"Secondary Author {suffix}",
        )

    def _crawl_fixture_record(self, values: CrawlFixtureValues) -> BookRecord:
        search_template = SEARCH_FIXTURE_PATH.read_text(encoding="utf-8")
        book_template = BOOK_FIXTURE_PATH.read_text(encoding="utf-8")
        search_html = self._render_fixture(search_template, values)
        book_html = self._render_fixture(book_template, values)

        crawler = GoodreadsCrawler(base_url="https://www.goodreads.com")

        def fake_fetch(url: str) -> str:
            if "/search?" in url:
                return search_html
            if f"/book/show/{values.external_id}" in url:
                return book_html
            raise AssertionError(f"Unexpected crawler URL: {url}")

        crawler._fetch_html = fake_fetch  # type: ignore[method-assign]
        records = crawler.crawl(query="found family", limit=1)
        self.assertEqual(len(records), 1)
        return records[0]

    def test_crawler_fixture_persistence_populates_required_fields(self) -> None:
        values = self._fixture_values(prefix="900303")
        record = self._crawl_fixture_record(values)

        connection = self._open_connection()
        self.addCleanup(connection.close)
        repository = MySQLBookRepository(connection)

        book_id = repository.upsert_book(record)
        self.assertGreater(book_id, 0)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  title,
                  description,
                  maturity_rating,
                  source_provider,
                  external_source_id
                FROM books
                WHERE id = %s
                """,
                (book_id,),
            )
            book_row = cursor.fetchone()

            cursor.execute(
                """
                SELECT a.full_name
                FROM book_authors ba
                INNER JOIN authors a ON a.id = ba.author_id
                WHERE ba.book_id = %s
                ORDER BY ba.author_order
                """,
                (book_id,),
            )
            author_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT g.display_name
                FROM book_genres bg
                INNER JOIN genres g ON g.id = bg.genre_id
                WHERE bg.book_id = %s
                ORDER BY g.display_name
                """,
                (book_id,),
            )
            genre_rows = cursor.fetchall()

        assert isinstance(book_row, dict)
        self.assertEqual(book_row["title"], values.title)
        self.assertIn("found family", str(book_row["description"]).lower())
        self.assertEqual(book_row["maturity_rating"], "general")
        self.assertEqual(book_row["source_provider"], "goodreads")
        self.assertEqual(book_row["external_source_id"], values.external_id)
        self.assertEqual(
            [row["full_name"] for row in author_rows],
            [values.primary_author, values.secondary_author],
        )
        self.assertEqual(
            [row["display_name"] for row in genre_rows],
            ["Fantasy", "Young Adult"],
        )

    def test_crawled_book_is_searchable_through_filtering_query_layer(self) -> None:
        values = self._fixture_values(prefix="901303")
        record = self._crawl_fixture_record(values)

        connection = self._open_connection()
        self.addCleanup(connection.close)
        persistence_repo = MySQLBookRepository(connection)
        persistence_repo.upsert_book(record)

        query_repo = BookRepository(connection)
        results = query_repo.search(
            BookFilterCriteria(
                query="found family",
                genre="fantasy",
                age_rating="general",
                subject_matter=("found family",),
                limit=5,
            )
        )

        titles = [entry["title"] for entry in results]
        self.assertIn(values.title, titles)


class CrawlerCliMockedTests(unittest.TestCase):
    def test_run_cli_executes_with_mocked_crawler_and_repository(self) -> None:
        fake_record = BookRecord(
            external_source_id="cli303",
            title="CLI Crawler Book",
            description="CLI smoke fixture",
            authors=["CLI Author"],
            genres=["Fantasy"],
        )
        fake_crawler = Mock()
        fake_crawler.crawl.return_value = [fake_record]

        fake_repo = Mock()

        with patch(
            "crawler.goodreads_crawler.GoodreadsCrawler",
            return_value=fake_crawler,
        ) as crawler_cls, patch(
            "crawler.goodreads_crawler.MySQLBookRepository.connect",
            return_value=fake_repo,
        ) as repo_connect:
            exit_code = run_cli(
                [
                    "--query",
                    "cli fixture",
                    "--limit",
                    "1",
                    "--db-host",
                    "db.example",
                    "--db-port",
                    "3306",
                    "--db-user",
                    "crawler",
                    "--db-password",
                    "secret",
                    "--db-name",
                    "books",
                ]
            )

        self.assertEqual(exit_code, 0)
        crawler_cls.assert_called_once()
        fake_crawler.crawl.assert_called_once_with(query="cli fixture", limit=1)
        repo_connect.assert_called_once()
        fake_repo.upsert_book.assert_called_once_with(fake_record)
        fake_repo.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
