import argparse
import unittest
from datetime import date
from unittest.mock import patch

from crawler.goodreads_crawler import (
    BookRecord,
    GoodreadsCrawler,
    MySQLBookRepository,
    parse_publication_date,
    resolve_mysql_config,
)


SEARCH_HTML = """
<html>
  <body>
    <a href="/book/show/12345-the-sample-book">Book A</a>
    <a href="/book/show/12345-the-sample-book">Duplicate Book A</a>
    <a href="/book/show/67890-another-book">Book B</a>
    <a href="/author/show/99-not-a-book">Author link</a>
  </body>
</html>
"""


BOOK_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": "The Pragmatic Reader",
        "description": "A sample description",
        "isbn": "9781234567890",
        "datePublished": "2022-05-12",
        "numberOfPages": "321",
        "inLanguage": "en-US",
        "publisher": "Demo Press",
        "image": "https://images.example/book.jpg",
        "author": [{"@type": "Person", "name": "Ada Lovelace"}],
        "aggregateRating": {"ratingValue": "4.12", "ratingCount": "421"}
      }
    </script>
  </head>
  <body>
    <a href="/genres/fantasy">Fantasy</a>
    <a href="/genres/science-fiction">Science Fiction</a>
  </body>
</html>
"""


class FakeCursor:
    def __init__(self):
        self.exec_calls = []
        self.lastrowid = 0
        self._author_counter = 0
        self._genre_counter = 0

    def execute(self, sql, params=None):
        self.exec_calls.append((sql, params))
        text = " ".join(sql.lower().split())

        if "insert into books" in text:
            self.lastrowid = 101
        elif "insert into authors" in text:
            self._author_counter += 1
            self.lastrowid = 200 + self._author_counter
        elif "insert into genres" in text:
            self._genre_counter += 1
            self.lastrowid = 300 + self._genre_counter

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class GoodreadsCrawlerTests(unittest.TestCase):
    def test_search_urls_are_deduplicated_and_limited(self):
        crawler = GoodreadsCrawler(base_url="https://www.goodreads.com")
        crawler._fetch_html = lambda _: SEARCH_HTML
        urls = crawler.search_book_urls(query="sample", limit=2)
        self.assertEqual(
            urls,
            [
                "https://www.goodreads.com/book/show/12345",
                "https://www.goodreads.com/book/show/67890",
            ],
        )

    def test_book_record_is_parsed_from_json_ld_and_genres(self):
        crawler = GoodreadsCrawler(base_url="https://www.goodreads.com")
        crawler._fetch_html = lambda _: BOOK_HTML
        record = crawler.fetch_book_record(
            "https://www.goodreads.com/book/show/12345-test"
        )
        self.assertEqual(record.external_source_id, "12345")
        self.assertEqual(record.title, "The Pragmatic Reader")
        self.assertEqual(record.isbn_13, "9781234567890")
        self.assertEqual(record.publication_date, date(2022, 5, 12))
        self.assertEqual(record.page_count, 321)
        self.assertEqual(record.authors, ["Ada Lovelace"])
        self.assertIn("Fantasy", record.genres)
        self.assertIn("Science Fiction", record.genres)

    def test_parse_publication_date_supports_year_only(self):
        parsed = parse_publication_date("Published in 1998 by Demo House")
        self.assertEqual(parsed, date(1998, 1, 1))


class RepositoryTests(unittest.TestCase):
    def test_repository_upsert_commits_and_links_records(self):
        conn = FakeConnection()
        repo = MySQLBookRepository(conn)
        record = BookRecord(
            external_source_id="12345",
            title="The Pragmatic Reader",
            description="A sample description",
            isbn_13="9781234567890",
            publication_date=date(2022, 5, 12),
            page_count=321,
            language_code="en",
            average_rating=4.12,
            ratings_count=421,
            publisher="Demo Press",
            cover_image_url="https://images.example/book.jpg",
            authors=["Ada Lovelace", "Grace Hopper"],
            genres=["Fantasy", "Science Fiction"],
        )
        book_id = repo.upsert_book(record)
        self.assertEqual(book_id, 101)
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)
        self.assertGreaterEqual(len(conn.cursor_obj.exec_calls), 9)


class MySQLConfigTests(unittest.TestCase):
    def test_resolve_mysql_config_from_environment(self):
        args = argparse.Namespace(
            db_host=None,
            db_port=None,
            db_user=None,
            db_password=None,
            db_name=None,
        )
        with patch.dict(
            "os.environ",
            {
                "DEV_MYSQL_HOST": "db.example",
                "DEV_MYSQL_PORT": "3306",
                "DEV_MYSQL_USER": "crawler",
                "DEV_MYSQL_PASSWORD": "secret",
                "DEV_MYSQL_DATABASE": "find_me_a_book",
            },
            clear=False,
        ):
            config = resolve_mysql_config(args)

        self.assertEqual(config.host, "db.example")
        self.assertEqual(config.port, 3306)
        self.assertEqual(config.user, "crawler")
        self.assertEqual(config.password, "secret")
        self.assertEqual(config.database, "find_me_a_book")

    def test_resolve_mysql_config_requires_values(self):
        args = argparse.Namespace(
            db_host=None,
            db_port=None,
            db_user=None,
            db_password=None,
            db_name=None,
        )
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                resolve_mysql_config(args)


if __name__ == "__main__":
    unittest.main()
