import os
import unittest
from datetime import UTC, datetime
from typing import Any

import pymysql

from crawler.goodreads_crawler import GoodreadsCrawler, MySQLBookRepository


def mysql_env_ready() -> bool:
    required = (
        "DEV_MYSQL_HOST",
        "DEV_MYSQL_PORT",
        "DEV_MYSQL_USER",
        "DEV_MYSQL_PASSWORD",
        "DEV_MYSQL_DATABASE",
    )
    return all(os.environ.get(name) for name in required)


@unittest.skipUnless(mysql_env_ready(), "MySQL environment variables not set")
class CrawlerMySQLIntegrationTests(unittest.TestCase):
    def _build_connection(self) -> Any:
        return pymysql.connect(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            database=os.environ["DEV_MYSQL_DATABASE"],
            charset="utf8mb4",
            autocommit=False,
        )

    def _cleanup_test_book(self, conn: Any, external_id: str) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM books
                WHERE source_provider = 'goodreads'
                  AND external_source_id = %s
                """,
                (external_id,),
            )
        conn.commit()

    def _create_fixture_payload(
        self,
        external_id: str,
        suffix: str,
        title: str,
        author_name: str,
        second_author_name: str,
        genre_name: str,
        second_genre_name: str,
        isbn_13: str,
        average_rating: str,
        rating_count: str,
        publication_date: str,
    ) -> tuple[str, str]:
        search_html = (
            "<html><body>"
            f"<a href='/book/show/{external_id}-integration'>{title}</a>"
            "</body></html>"
        )
        book_html = f"""
        <html>
          <head>
            <script type="application/ld+json">
              {{
                "@context": "https://schema.org",
                "@type": "Book",
                "name": "{title}",
                "description": "Integration crawler persistence test",
                "isbn": "{isbn_13}",
                "datePublished": "{publication_date}",
                "numberOfPages": "220",
                "inLanguage": "en-US",
                "publisher": "Integration Press",
                "image": "https://images.example/{suffix}.jpg",
                "author": [
                  {{"@type": "Person", "name": "{author_name}"}},
                  {{"@type": "Person", "name": "{second_author_name}"}}
                ],
                "aggregateRating": {{
                  "ratingValue": "{average_rating}",
                  "ratingCount": "{rating_count}"
                }}
              }}
            </script>
          </head>
          <body>
            <a href="/genres/integration">{genre_name}</a>
            <a href="/genres/integration">{genre_name}</a>
            <a href="/genres/complete">{second_genre_name}</a>
          </body>
        </html>
        """
        return search_html, book_html

    def _crawl_fixture(
        self, external_id: str, search_html: str, book_html: str
    ) -> list[Any]:
        crawler = GoodreadsCrawler(base_url="https://www.goodreads.com")

        def fake_fetch(url: str) -> str:
            if "/search?" in url:
                return search_html
            if f"/book/show/{external_id}" in url:
                return book_html
            raise AssertionError(f"Unexpected URL requested by crawler: {url}")

        crawler._fetch_html = fake_fetch  # type: ignore[method-assign]
        return crawler.crawl(query="integration", limit=1)

    def _fetch_persisted_book(self, conn: Any, book_id: int) -> tuple[Any, ...] | None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  title,
                  description,
                  isbn_13,
                  publication_date,
                  page_count,
                  language_code,
                  average_rating,
                ratings_count,
                publisher,
                taxonomy_version,
                canonical_genres,
                canonical_plot_tags,
                canonical_character_dynamics,
                age_band,
                spice_level,
                source_provider,
                external_source_id
                FROM books
                WHERE id = %s
                """,
                (book_id,),
            )
            return cursor.fetchone()

    def test_crawler_persistence_stores_complete_book_payload(self):
        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        external_id = str(900000000000 + int(suffix[-6:]))
        isbn_13 = f"979{suffix[-10:]}"
        title = f"Integration Book {suffix}"
        author_name = f"Integration Author {suffix}"
        second_author_name = f"Second Integration Author {suffix}"
        genre_name = "Fantasy"
        second_genre_name = "Young Adult"
        expected_rating = 4.30
        expected_rating_count = 80

        search_html, book_html = self._create_fixture_payload(
            external_id=external_id,
            suffix=suffix,
            title=title,
            author_name=author_name,
            second_author_name=second_author_name,
            genre_name=genre_name,
            second_genre_name=second_genre_name,
            isbn_13=isbn_13,
            average_rating=f"{expected_rating:.2f}",
            rating_count=str(expected_rating_count),
            publication_date="2021-04-01",
        )
        records = self._crawl_fixture(external_id, search_html, book_html)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].authors, [author_name, second_author_name])
        self.assertEqual(records[0].genres, [genre_name, second_genre_name])

        conn = self._build_connection()

        repository = MySQLBookRepository(conn)
        try:
            book_id = repository.upsert_book(records[0])
            self.assertGreater(book_id, 0)

            with conn.cursor() as cursor:
                row = self._fetch_persisted_book(conn, book_id)

                cursor.execute(
                    """
                    SELECT a.full_name
                    FROM book_authors ba
                    INNER JOIN authors a ON a.id = ba.author_id
                    WHERE book_id = %s
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
                    WHERE book_id = %s
                    ORDER BY g.display_name
                    """,
                    (book_id,),
                )
                genre_rows = cursor.fetchall()

            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row[0], title)
            self.assertEqual(row[1], "Integration crawler persistence test")
            self.assertEqual(row[2], isbn_13)
            self.assertEqual(str(row[3]), "2021-04-01")
            self.assertEqual(row[4], 220)
            self.assertEqual(row[5], "en")
            self.assertAlmostEqual(float(row[6]), expected_rating, places=2)
            self.assertEqual(row[7], expected_rating_count)
            self.assertEqual(row[8], "Integration Press")
            self.assertEqual(row[9], "v1")
            self.assertIn("fantasy", str(row[10]).lower())
            self.assertIn("young-adult", str(row[10]).lower())
            self.assertEqual(row[13], "young-adult")
            self.assertEqual(row[14], "spice-3-moderate")
            self.assertEqual(row[15], "goodreads")
            self.assertEqual(row[16], external_id)
            self.assertEqual(
                [entry[0] for entry in author_rows],
                [author_name, second_author_name],
            )
            self.assertEqual(
                sorted(entry[0] for entry in genre_rows),
                sorted([genre_name, second_genre_name]),
            )
        finally:
            self._cleanup_test_book(conn, external_id)
            repository.close()

    def test_repository_upsert_updates_rows_without_duplicate_links(self):
        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        external_id = str(910000000000 + int(suffix[-6:]))
        isbn_13 = f"978{suffix[-10:]}"
        first_title = f"Upsert Book {suffix}"
        second_title = f"Upsert Book Updated {suffix}"
        first_author = f"Upsert Author {suffix}"
        second_author = f"Second Upsert Author {suffix}"
        genre_name = "Fantasy"
        second_genre_name = "Young Adult"

        first_search_html, first_book_html = self._create_fixture_payload(
            external_id=external_id,
            suffix=suffix,
            title=first_title,
            author_name=first_author,
            second_author_name=second_author,
            genre_name=genre_name,
            second_genre_name=second_genre_name,
            isbn_13=isbn_13,
            average_rating="4.10",
            rating_count="21",
            publication_date="2020-01-02",
        )
        second_search_html, second_book_html = self._create_fixture_payload(
            external_id=external_id,
            suffix=suffix,
            title=second_title,
            author_name=first_author,
            second_author_name=second_author,
            genre_name=genre_name,
            second_genre_name=second_genre_name,
            isbn_13=isbn_13,
            average_rating="4.70",
            rating_count="42",
            publication_date="2023-12-03",
        )

        first_record = self._crawl_fixture(
            external_id, first_search_html, first_book_html
        )[0]
        second_record = self._crawl_fixture(
            external_id, second_search_html, second_book_html
        )[0]

        conn = self._build_connection()
        repository = MySQLBookRepository(conn)
        try:
            first_book_id = repository.upsert_book(first_record)
            second_book_id = repository.upsert_book(second_record)
            self.assertEqual(first_book_id, second_book_id)

            row = self._fetch_persisted_book(conn, second_book_id)
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row[0], second_title)
            self.assertEqual(str(row[3]), "2023-12-03")
            self.assertAlmostEqual(float(row[6]), 4.70, places=2)
            self.assertEqual(row[7], 42)
            self.assertEqual(row[9], "v1")
            self.assertIn("fantasy", str(row[10]).lower())
            self.assertIn("young-adult", str(row[10]).lower())
            self.assertEqual(row[13], "young-adult")
            self.assertEqual(row[14], "spice-3-moderate")

            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM book_authors
                    WHERE book_id = %s
                    """,
                    (second_book_id,),
                )
                author_links = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM book_genres
                    WHERE book_id = %s
                    """,
                    (second_book_id,),
                )
                genre_links = cursor.fetchone()[0]

            self.assertEqual(author_links, 2)
            self.assertEqual(genre_links, 2)
        finally:
            self._cleanup_test_book(conn, external_id)
            repository.close()


if __name__ == "__main__":
    unittest.main()
