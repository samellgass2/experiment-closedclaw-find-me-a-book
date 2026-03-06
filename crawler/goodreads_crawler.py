"""Goodreads crawler and persistence flow for find-me-a-book."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin
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


class GoodreadsHTMLParser(HTMLParser):
    """Extracts links, JSON-LD blocks, and genre tags from Goodreads HTML."""

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
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalize_isbn(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    compact = re.sub(r"[^0-9Xx]", "", value).upper()
    if len(compact) == 10:
        return compact, None
    if len(compact) == 13:
        return None, compact
    return None, None


def parse_publication_date(value: str | None) -> date | None:
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
    normalized = NON_ALNUM_PATTERN.sub("-", name.strip().lower()).strip("-")
    return normalized[:40] if normalized else "unknown"


class GoodreadsCrawler:
    """Crawler for Goodreads search and book detail pages."""

    def __init__(
        self,
        base_url: str = GOODREADS_BASE_URL,
        timeout_seconds: int = 20,
        user_agent: str = "find-me-a-book-bot/1.0 (+https://example.local)",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def crawl(self, query: str, limit: int = 10) -> list[BookRecord]:
        book_urls = self.search_book_urls(query=query, limit=limit)
        records: list[BookRecord] = []
        for url in book_urls:
            records.append(self.fetch_book_record(url))
        return records

    def search_book_urls(self, query: str, limit: int = 10) -> list[str]:
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        search_url = f"{self.base_url}/search?q={quote_plus(query)}"
        html = self._fetch_html(search_url)
        parser = GoodreadsHTMLParser()
        parser.feed(html)

        urls: list[str] = []
        seen: set[str] = set()
        for href in parser.links:
            match = BOOK_PATH_PATTERN.match(href)
            if not match:
                continue
            full_url = urljoin(self.base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)
            urls.append(full_url)
            if len(urls) >= limit:
                break

        if not urls:
            raise BlockedCrawlError("No Goodreads book links found in search results.")
        return urls

    def fetch_book_record(self, book_url: str) -> BookRecord:
        html = self._fetch_html(book_url)
        parser = GoodreadsHTMLParser()
        parser.feed(html)

        ld_book = self._extract_book_json_ld(parser.ld_json_blocks)
        if not ld_book:
            raise BlockedCrawlError(f"No usable JSON-LD payload found for {book_url}.")

        external_source_id = extract_book_id(book_url)
        title = normalize_whitespace(ld_book.get("name")) or "Untitled"
        description = normalize_whitespace(ld_book.get("description")) or None

        isbn_10, isbn_13 = normalize_isbn(str(ld_book.get("isbn", "")))
        date_published = parse_publication_date(str(ld_book.get("datePublished", "")))
        language_code = (normalize_whitespace(str(ld_book.get("inLanguage", "en")))[:2] or "en").lower()

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
            language_code=language_code if re.match(r"^[a-z]{2}$", language_code) else "en",
            average_rating=avg_rating,
            ratings_count=ratings_count,
            publisher=publisher,
            cover_image_url=cover_image_url,
            authors=authors,
            genres=genres,
        )

    def _fetch_html(self, url: str) -> str:
        request = Request(url=url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status in (403, 429):
                    raise BlockedCrawlError(f"Goodreads blocked crawler request with HTTP {status}.")
                payload = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code in (403, 429):
                raise BlockedCrawlError(f"Goodreads blocked crawler request with HTTP {exc.code}.") from exc
            raise GoodreadsCrawlError(f"Failed to fetch {url}: HTTP {exc.code}") from exc
        except URLError as exc:
            raise GoodreadsCrawlError(f"Failed to connect to Goodreads for {url}: {exc.reason}") from exc

        if "captcha" in payload.lower():
            raise BlockedCrawlError("Goodreads returned CAPTCHA challenge; crawling blocked.")
        return payload

    @staticmethod
    def _extract_book_json_ld(blocks: list[str]) -> dict[str, Any] | None:
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
                if isinstance(graph, list):
                    for node in graph:
                        if isinstance(node, dict) and node.get("@type") == "Book":
                            return node
        return None


class PostgresBookRepository:
    """Persists crawler output into the PostgreSQL schema."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @classmethod
    def connect(cls, dsn: str) -> "PostgresBookRepository":
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required to persist crawler results to PostgreSQL.") from exc
        connection = psycopg.connect(dsn)
        return cls(connection=connection)

    def close(self) -> None:
        self.connection.close()

    def upsert_book(self, record: BookRecord) -> int:
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO books (
                      title, subtitle, description, isbn_10, isbn_13, publication_date,
                      page_count, language_code, average_rating, ratings_count, publisher,
                      cover_image_url, source_provider, external_source_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'goodreads', %s)
                    ON CONFLICT (source_provider, external_source_id)
                    WHERE external_source_id IS NOT NULL
                    DO UPDATE SET
                      title = EXCLUDED.title,
                      subtitle = EXCLUDED.subtitle,
                      description = EXCLUDED.description,
                      isbn_10 = EXCLUDED.isbn_10,
                      isbn_13 = EXCLUDED.isbn_13,
                      publication_date = EXCLUDED.publication_date,
                      page_count = EXCLUDED.page_count,
                      language_code = EXCLUDED.language_code,
                      average_rating = EXCLUDED.average_rating,
                      ratings_count = EXCLUDED.ratings_count,
                      publisher = EXCLUDED.publisher,
                      cover_image_url = EXCLUDED.cover_image_url
                    RETURNING id
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
                book_id = cursor.fetchone()[0]

                for idx, author_name in enumerate(record.authors, start=1):
                    cursor.execute(
                        """
                        INSERT INTO authors (full_name)
                        VALUES (%s)
                        ON CONFLICT (full_name)
                        DO UPDATE SET full_name = EXCLUDED.full_name
                        RETURNING id
                        """,
                        (author_name,),
                    )
                    author_id = cursor.fetchone()[0]
                    cursor.execute(
                        """
                        INSERT INTO book_authors (book_id, author_id, author_order, role)
                        VALUES (%s, %s, %s, 'author')
                        ON CONFLICT (book_id, author_id)
                        DO UPDATE SET author_order = EXCLUDED.author_order, role = EXCLUDED.role
                        """,
                        (book_id, author_id, idx),
                    )

                for genre_name in record.genres:
                    genre_code = slugify_genre(genre_name)
                    cursor.execute(
                        """
                        INSERT INTO genres (code, display_name)
                        VALUES (%s, %s)
                        ON CONFLICT (code)
                        DO UPDATE SET display_name = EXCLUDED.display_name
                        RETURNING id
                        """,
                        (genre_code, genre_name[:80]),
                    )
                    genre_id = cursor.fetchone()[0]
                    cursor.execute(
                        """
                        INSERT INTO book_genres (book_id, genre_id)
                        VALUES (%s, %s)
                        ON CONFLICT (book_id, genre_id) DO NOTHING
                        """,
                        (book_id, genre_id),
                    )

            self.connection.commit()
            return book_id
        except Exception:
            self.connection.rollback()
            raise


def extract_book_id(book_url: str) -> str:
    path = book_url.replace(GOODREADS_BASE_URL, "")
    match = BOOK_PATH_PATTERN.match(path)
    if not match:
        raise GoodreadsCrawlError(f"Book URL does not match Goodreads pattern: {book_url}")
    return match.group(1)


def extract_author_names(raw_author: Any) -> list[str]:
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
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl Goodreads and persist books to PostgreSQL.")
    parser.add_argument("--query", required=True, help="Search phrase used on Goodreads.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum books to fetch.")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN, defaults to DATABASE_URL env var.",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print("Missing --database-url or DATABASE_URL environment variable.", file=sys.stderr)
        return 1

    crawler = GoodreadsCrawler()
    try:
        records = crawler.crawl(query=args.query, limit=args.limit)
    except BlockedCrawlError as exc:
        print(f"Crawl blocked: {exc}", file=sys.stderr)
        return 2
    except GoodreadsCrawlError as exc:
        print(f"Crawl failed: {exc}", file=sys.stderr)
        return 1

    repository = PostgresBookRepository.connect(args.database_url)
    try:
        for record in records:
            repository.upsert_book(record)
    finally:
        repository.close()

    print(f"Stored {len(records)} books from Goodreads query '{args.query}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
