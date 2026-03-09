"""Goodreads crawler and persistence flow for find-me-a-book."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen


GOODREADS_BASE_URL = "https://www.goodreads.com"
BOOK_PATH_PATTERN = re.compile(r"^/book/show/(\d+)")
YEAR_PATTERN = re.compile(r"\b(1[4-9]\d{2}|20\d{2}|2100)\b")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


class GoodreadsCrawlError(RuntimeError):
    """Base exception for crawler failures."""


class BlockedCrawlError(GoodreadsCrawlError):
    """Raised when Goodreads blocks scraping or response is not usable."""


@dataclass
class BookRecord:
    """Normalized representation of Goodreads book data."""

    external_source_id: str
    title: str
    subtitle: str | None = None
    description: str | None = None
    isbn_10: str | None = None
    isbn_13: str | None = None
    publication_date: date | None = None
    page_count: int | None = None
    language_code: str = "en"
    average_rating: float | None = None
    ratings_count: int = 0
    publisher: str | None = None
    cover_image_url: str | None = None
    authors: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MySQLConnectionConfig:
    """MySQL connection parameters for crawler persistence."""

    host: str
    port: int
    user: str
    password: str
    database: str


class GoodreadsHTMLParser(HTMLParser):
    """Extract links, JSON-LD blocks, and genre labels from Goodreads HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ld_json_blocks: list[str] = []
        self.genres: list[str] = []
        self._in_script = False
        self._script_type = ""
        self._script_chunks: list[str] = []
        self._capture_genre = False
        self._genre_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "a":
            href = attrs_map.get("href") or ""
            if href:
                self.links.append(href)
            if "/genres/" in href:
                self._capture_genre = True
                self._genre_chunks = []

        if tag == "script":
            script_type = (attrs_map.get("type") or "").lower()
            self._in_script = True
            self._script_type = script_type
            self._script_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            content = "".join(self._script_chunks).strip()
            if "ld+json" in self._script_type and content:
                self.ld_json_blocks.append(content)
            self._in_script = False
            self._script_type = ""
            self._script_chunks = []

        if tag == "a" and self._capture_genre:
            genre = normalize_whitespace("".join(self._genre_chunks))
            if genre:
                self.genres.append(genre)
            self._capture_genre = False
            self._genre_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_chunks.append(data)
        if self._capture_genre:
            self._genre_chunks.append(data)


def normalize_whitespace(value: str | None) -> str:
    """Trim and collapse whitespace and unescape HTML entities."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalize_isbn(value: str | None) -> tuple[str | None, str | None]:
    """Return ISBN-10 and ISBN-13 from mixed input, one side always None."""
    if not value:
        return None, None

    compact = re.sub(r"[^0-9Xx]", "", value).upper()
    if len(compact) == 10:
        return compact, None
    if len(compact) == 13:
        return None, compact
    return None, None


def parse_publication_date(value: str | None) -> date | None:
    """Parse publication date from Goodreads text, including year fallback."""
    if not value:
        return None

    cleaned = normalize_whitespace(value)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    if cleaned.isdigit() and len(cleaned) == 4:
        return date(int(cleaned), 1, 1)

    year_match = YEAR_PATTERN.search(cleaned)
    if year_match:
        return date(int(year_match.group(1)), 1, 1)

    return None


def slugify_genre(name: str) -> str:
    """Create a deterministic short code for genre names."""
    normalized = NON_ALNUM_PATTERN.sub("-", name.strip().lower()).strip("-")
    return normalized[:40] if normalized else "unknown"


class GoodreadsCrawler:
    """Crawler for Goodreads search and book detail pages."""

    def __init__(
        self,
        base_url: str = GOODREADS_BASE_URL,
        timeout_seconds: int = 20,
        user_agent: str = "find-me-a-book-bot/1.0 (+https://example.local)",
        max_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def crawl(self, query: str, limit: int = 10) -> list[BookRecord]:
        """Search Goodreads and fetch book details for each candidate URL."""
        book_urls = self.search_book_urls(query=query, limit=limit)
        records: list[BookRecord] = []
        for url in book_urls:
            records.append(self.fetch_book_record(url))
        return records

    def search_book_urls(self, query: str, limit: int = 10) -> list[str]:
        """Return canonical Goodreads book URLs from a query page."""
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        search_url = f"{self.base_url}/search?q={quote_plus(query)}"
        html = self._fetch_html(search_url)
        parser = GoodreadsHTMLParser()
        parser.feed(html)

        urls: list[str] = []
        seen: set[str] = set()
        for href in parser.links:
            full_url = urljoin(self.base_url, href)
            try:
                book_id = extract_book_id(full_url)
            except GoodreadsCrawlError:
                continue

            canonical_url = f"{self.base_url}/book/show/{book_id}"
            if canonical_url in seen:
                continue

            seen.add(canonical_url)
            urls.append(canonical_url)
            if len(urls) >= limit:
                break

        if not urls:
            raise BlockedCrawlError(
                "No Goodreads book links found in search results."
            )
        return urls

    def fetch_book_record(self, book_url: str) -> BookRecord:
        """Fetch and parse a Goodreads book detail page."""
        html = self._fetch_html(book_url)
        parser = GoodreadsHTMLParser()
        parser.feed(html)

        ld_book = self._extract_book_json_ld(parser.ld_json_blocks)
        if not ld_book:
            raise BlockedCrawlError(
                f"No usable JSON-LD payload found for {book_url}."
            )

        external_source_id = extract_book_id(book_url)
        title = normalize_whitespace(ld_book.get("name")) or "Untitled"
        description = normalize_whitespace(ld_book.get("description")) or None

        isbn_10, isbn_13 = normalize_isbn(str(ld_book.get("isbn", "")))
        date_published = parse_publication_date(
            str(ld_book.get("datePublished", ""))
        )
        raw_language_code = normalize_whitespace(
            str(ld_book.get("inLanguage", "en"))
        )
        language_code = (raw_language_code[:2] or "en").lower()

        page_count_raw = ld_book.get("numberOfPages")
        page_count = int(page_count_raw) if str(page_count_raw).isdigit() else None

        agg = ld_book.get("aggregateRating", {}) if isinstance(ld_book, dict) else {}
        avg_rating = safe_float(agg.get("ratingValue"))
        ratings_count = safe_int(agg.get("ratingCount"), default=0)

        publisher = normalize_whitespace(ld_book.get("publisher")) or None
        cover_image_url = normalize_whitespace(ld_book.get("image")) or None

        authors = extract_author_names(ld_book.get("author"))
        if not authors:
            authors = ["Unknown Author"]

        genres = list(dict.fromkeys(parser.genres))

        return BookRecord(
            external_source_id=external_source_id,
            title=title,
            description=description,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publication_date=date_published,
            page_count=page_count,
            language_code=(
                language_code if re.match(r"^[a-z]{2}$", language_code) else "en"
            ),
            average_rating=avg_rating,
            ratings_count=ratings_count,
            publisher=publisher,
            cover_image_url=cover_image_url,
            authors=authors,
            genres=genres,
        )

    def _fetch_html(self, url: str) -> str:
        """Fetch HTML with retry logic for transient network/server errors."""
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            request = Request(url=url, headers={"User-Agent": self.user_agent})
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    if status in (403, 429):
                        raise BlockedCrawlError(
                            "Goodreads blocked crawler request with HTTP "
                            f"{status}."
                        )

                    if status >= 500:
                        raise GoodreadsCrawlError(
                            f"Failed to fetch {url}: HTTP {status}"
                        )

                    payload = response.read().decode("utf-8", errors="replace")

                if "captcha" in payload.lower():
                    raise BlockedCrawlError(
                        "Goodreads returned CAPTCHA challenge; crawling blocked."
                    )

                return payload
            except BlockedCrawlError:
                raise
            except HTTPError as exc:
                if exc.code in (403, 429):
                    raise BlockedCrawlError(
                        "Goodreads blocked crawler request with HTTP "
                        f"{exc.code}."
                    ) from exc

                last_error = GoodreadsCrawlError(
                    f"Failed to fetch {url}: HTTP {exc.code}"
                )
                if not self._should_retry(exc.code, attempt):
                    raise last_error from exc
            except URLError as exc:
                reason = getattr(exc, "reason", str(exc))
                last_error = GoodreadsCrawlError(
                    f"Failed to connect to Goodreads for {url}: {reason}"
                )
                if attempt >= self.max_attempts:
                    raise last_error from exc
            except GoodreadsCrawlError as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    raise

            if attempt < self.max_attempts:
                time.sleep(self.retry_backoff_seconds * attempt)

        if last_error is not None:
            raise last_error

        raise GoodreadsCrawlError(f"Failed to fetch {url}: unknown error")

    def _should_retry(self, http_code: int, attempt: int) -> bool:
        """Retry transient HTTP failures while respecting max attempts."""
        if attempt >= self.max_attempts:
            return False
        return http_code >= 500

    @staticmethod
    def _extract_book_json_ld(blocks: list[str]) -> dict[str, Any] | None:
        """Extract the first JSON-LD object with `@type=Book`."""
        for block in blocks:
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                continue

            candidates = parsed if isinstance(parsed, list) else [parsed]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue

                if candidate.get("@type") == "Book":
                    return candidate

                graph = candidate.get("@graph")
                if not isinstance(graph, list):
                    continue

                for node in graph:
                    if isinstance(node, dict) and node.get("@type") == "Book":
                        return node

        return None


class MySQLBookRepository:
    """Persist crawler output into the MySQL schema."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @classmethod
    def connect(cls, config: MySQLConnectionConfig) -> "MySQLBookRepository":
        """Connect to MySQL using pymysql and return repository wrapper."""
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError(
                "pymysql is required to persist crawler results to MySQL."
            ) from exc

        connection = pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
            charset="utf8mb4",
            autocommit=False,
        )
        return cls(connection=connection)

    def close(self) -> None:
        """Close DB connection."""
        self.connection.close()

    def upsert_book(self, record: BookRecord) -> int:
        """Insert or update a book and its author/genre associations."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO books (
                      title, subtitle, description, isbn_10, isbn_13,
                      publication_date, page_count, language_code,
                      average_rating, ratings_count, publisher,
                      cover_image_url, source_provider, external_source_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      'goodreads', %s)
                    ON DUPLICATE KEY UPDATE
                      id = LAST_INSERT_ID(id),
                      title = VALUES(title),
                      subtitle = VALUES(subtitle),
                      description = VALUES(description),
                      isbn_10 = VALUES(isbn_10),
                      isbn_13 = VALUES(isbn_13),
                      publication_date = VALUES(publication_date),
                      page_count = VALUES(page_count),
                      language_code = VALUES(language_code),
                      average_rating = VALUES(average_rating),
                      ratings_count = VALUES(ratings_count),
                      publisher = VALUES(publisher),
                      cover_image_url = VALUES(cover_image_url),
                      source_provider = 'goodreads',
                      external_source_id = VALUES(external_source_id)
                    """,
                    (
                        record.title,
                        record.subtitle,
                        record.description,
                        record.isbn_10,
                        record.isbn_13,
                        record.publication_date,
                        record.page_count,
                        record.language_code,
                        record.average_rating,
                        record.ratings_count,
                        record.publisher,
                        record.cover_image_url,
                        record.external_source_id,
                    ),
                )
                book_id = int(cursor.lastrowid)

                for index, author_name in enumerate(record.authors, start=1):
                    cursor.execute(
                        """
                        INSERT INTO authors (full_name)
                        VALUES (%s)
                        ON DUPLICATE KEY UPDATE
                          id = LAST_INSERT_ID(id),
                          full_name = VALUES(full_name)
                        """,
                        (author_name,),
                    )
                    author_id = int(cursor.lastrowid)
                    cursor.execute(
                        """
                        INSERT INTO book_authors (
                          book_id, author_id, author_order, role
                        )
                        VALUES (%s, %s, %s, 'author')
                        ON DUPLICATE KEY UPDATE
                          author_order = VALUES(author_order),
                          role = VALUES(role)
                        """,
                        (book_id, author_id, index),
                    )

                for genre_name in record.genres:
                    genre_code = slugify_genre(genre_name)
                    cursor.execute(
                        """
                        INSERT INTO genres (code, display_name)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE
                          id = LAST_INSERT_ID(id),
                          display_name = VALUES(display_name)
                        """,
                        (genre_code, genre_name[:80]),
                    )
                    genre_id = int(cursor.lastrowid)
                    cursor.execute(
                        """
                        INSERT INTO book_genres (book_id, genre_id)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE
                          book_id = VALUES(book_id)
                        """,
                        (book_id, genre_id),
                    )

            self.connection.commit()
            return book_id
        except Exception:
            self.connection.rollback()
            raise


# Backward compatibility alias for existing imports/tests.
PostgresBookRepository = MySQLBookRepository


def resolve_mysql_config(args: argparse.Namespace) -> MySQLConnectionConfig:
    """Resolve MySQL connection configuration from args and env vars."""
    host = args.db_host or os.environ.get("DEV_MYSQL_HOST")
    user = args.db_user or os.environ.get("DEV_MYSQL_USER")
    password = args.db_password or os.environ.get("DEV_MYSQL_PASSWORD")
    database = args.db_name or os.environ.get("DEV_MYSQL_DATABASE")
    port_raw = args.db_port or os.environ.get("DEV_MYSQL_PORT")

    missing: list[str] = []
    if not host:
        missing.append("DEV_MYSQL_HOST")
    if not user:
        missing.append("DEV_MYSQL_USER")
    if not password:
        missing.append("DEV_MYSQL_PASSWORD")
    if not database:
        missing.append("DEV_MYSQL_DATABASE")
    if not port_raw:
        missing.append("DEV_MYSQL_PORT")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(
            "Missing MySQL connection values. Provide CLI flags or set: "
            f"{joined}"
        )

    try:
        port = int(port_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("DEV_MYSQL_PORT/--db-port must be an integer.") from exc

    return MySQLConnectionConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


def extract_book_id(book_url: str) -> str:
    """Extract Goodreads book ID from URL path."""
    path = urlparse(book_url).path or book_url
    match = BOOK_PATH_PATTERN.match(path)
    if not match:
        raise GoodreadsCrawlError(
            f"Book URL does not match Goodreads pattern: {book_url}"
        )
    return match.group(1)


def extract_author_names(raw_author: Any) -> list[str]:
    """Normalize and deduplicate author names from JSON-LD values."""
    names: list[str] = []
    if isinstance(raw_author, dict):
        raw_author = [raw_author]

    if isinstance(raw_author, list):
        for entry in raw_author:
            if isinstance(entry, dict):
                name = normalize_whitespace(entry.get("name"))
                if name:
                    names.append(name)
            elif isinstance(entry, str):
                name = normalize_whitespace(entry)
                if name:
                    names.append(name)

    return list(dict.fromkeys(names))


def safe_float(value: Any) -> float | None:
    """Return float from input, or None for invalid values."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def safe_int(value: Any, default: int = 0) -> int:
    """Return int from input, or provided default for invalid values."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def run_cli(argv: list[str] | None = None) -> int:
    """CLI entrypoint for Goodreads crawling and MySQL persistence."""
    parser = argparse.ArgumentParser(
        description="Crawl Goodreads and persist books to MySQL."
    )
    parser.add_argument("--query", required=True, help="Search phrase used on Goodreads.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum books to fetch.")
    parser.add_argument(
        "--db-host",
        default=None,
        help="MySQL host. Defaults to DEV_MYSQL_HOST.",
    )
    parser.add_argument(
        "--db-port",
        default=None,
        help="MySQL port. Defaults to DEV_MYSQL_PORT.",
    )
    parser.add_argument(
        "--db-user",
        default=None,
        help="MySQL user. Defaults to DEV_MYSQL_USER.",
    )
    parser.add_argument(
        "--db-password",
        default=None,
        help="MySQL password. Defaults to DEV_MYSQL_PASSWORD.",
    )
    parser.add_argument(
        "--db-name",
        default=None,
        help="MySQL database name. Defaults to DEV_MYSQL_DATABASE.",
    )
    args = parser.parse_args(argv)

    try:
        config = resolve_mysql_config(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    crawler = GoodreadsCrawler(max_attempts=3)
    try:
        records = crawler.crawl(query=args.query, limit=args.limit)
    except BlockedCrawlError as exc:
        print(f"Crawl blocked: {exc}", file=sys.stderr)
        return 2
    except GoodreadsCrawlError as exc:
        print(f"Crawl failed: {exc}", file=sys.stderr)
        return 1

    try:
        repository = MySQLBookRepository.connect(config)
    except RuntimeError as exc:
        print(f"Database connect failed: {exc}", file=sys.stderr)
        return 1

    try:
        for record in records:
            repository.upsert_book(record)
    finally:
        repository.close()

    print(f"Stored {len(records)} books from Goodreads query '{args.query}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
