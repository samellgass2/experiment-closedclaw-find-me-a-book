import os
import unittest
from datetime import UTC, datetime

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
    def test_crawler_retrieves_and_stores_book_data(self):
        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        external_id = str(900000000000 + int(suffix[-6:]))
        isbn_13 = f"979{suffix[-10:]}"
        title = f"Integration Book {suffix}"
        author_name = f"Integration Author {suffix}"
        genre_name = f"Integration Genre {suffix}"

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
                "datePublished": "2021-04-01",
                "numberOfPages": "220",
                "inLanguage": "en-US",
                "publisher": "Integration Press",
                "image": "https://images.example/{suffix}.jpg",
                "author": [{{"@type": "Person", "name": "{author_name}"}}],
                "aggregateRating": {{"ratingValue": "4.30", "ratingCount": "80"}}
              }}
            </script>
          </head>
          <body>
            <a href="/genres/integration">{genre_name}</a>
          </body>
        </html>
        """

        crawler = GoodreadsCrawler(base_url="https://www.goodreads.com")

        def fake_fetch(url: str) -> str:
            if "/search?" in url:
                return search_html
            return book_html

        crawler._fetch_html = fake_fetch  # type: ignore[method-assign]

        records = crawler.crawl(query="integration", limit=1)
        self.assertEqual(len(records), 1)

        conn = pymysql.connect(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            database=os.environ["DEV_MYSQL_DATABASE"],
            charset="utf8mb4",
            autocommit=False,
        )

        repository = MySQLBookRepository(conn)
        try:
            book_id = repository.upsert_book(records[0])
            self.assertGreater(book_id, 0)

            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT title, source_provider, external_source_id
                    FROM books
                    WHERE id = %s
                    """,
                    (book_id,),
                )
                row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM book_authors
                    WHERE book_id = %s
                    """,
                    (book_id,),
                )
                author_count = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM book_genres
                    WHERE book_id = %s
                    """,
                    (book_id,),
                )
                genre_count = cursor.fetchone()[0]

            self.assertIsNotNone(row)
            self.assertEqual(row[0], title)
            self.assertEqual(row[1], "goodreads")
            self.assertEqual(row[2], external_id)
            self.assertGreaterEqual(author_count, 1)
            self.assertGreaterEqual(genre_count, 1)
        finally:
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
            repository.close()


if __name__ == "__main__":
    unittest.main()
