"""Data access for listing and searching books."""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

import pymysql

from backend.filters import (
    AGE_RATING_ALIASES,
    DEFAULT_BOOK_LIMIT,
    BookFilterCriteria,
    BookPayload,
    build_book_filter_query,
    row_to_book_payload,
)

QUERY_TIMEOUT_ERROR_CODES = frozenset({3024, 1969})


class BookFilters(TypedDict, total=False):
    """Optional query filters for book listing/search."""

    genre: str
    age_min: int
    age_max: int
    subject: str
    spice_level: str


class BookRepositoryError(RuntimeError):
    """Raised when the repository cannot query the database."""


class BookQueryTimeoutError(BookRepositoryError):
    """Raised when the search query exceeds database timeout constraints."""


class BookRepository:
    """Repository wrapper for reading books from MySQL."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def list_books(
        self,
        *,
        limit: int = DEFAULT_BOOK_LIMIT,
        filters: BookFilters | None = None,
    ) -> list[BookPayload]:
        """Return a default page of books ordered by recent updates."""
        criteria = BookFilterCriteria(
            query=None,
            genre=(filters or {}).get("genre"),
            subject_matter=(
                tuple([(filters or {})["subject"]])
                if (filters or {}).get("subject") is not None
                else tuple()
            ),
            spice_level=(filters or {}).get("spice_level"),
            age_min=(filters or {}).get("age_min"),
            age_max=(filters or {}).get("age_max"),
            limit=limit,
        )
        return self.search(criteria)

    def search_books(
        self,
        query: str,
        *,
        limit: int = DEFAULT_BOOK_LIMIT,
        filters: BookFilters | None = None,
    ) -> list[BookPayload]:
        """Search books by title, author, or description text."""
        criteria = BookFilterCriteria(
            query=query,
            genre=(filters or {}).get("genre"),
            subject_matter=(
                tuple([(filters or {})["subject"]])
                if (filters or {}).get("subject") is not None
                else tuple()
            ),
            spice_level=(filters or {}).get("spice_level"),
            age_min=(filters or {}).get("age_min"),
            age_max=(filters or {}).get("age_max"),
            limit=limit,
        )
        return self.search(criteria)

    def search(
        self,
        criteria: BookFilterCriteria,
    ) -> list[BookPayload]:
        """Run a ranked book search using advanced filter criteria."""
        sql, params = self._build_books_query(criteria=criteria)
        return self._query_books(sql, params)

    def _build_books_query(
        self,
        *,
        criteria: BookFilterCriteria,
    ) -> tuple[str, tuple[Any, ...]]:
        """Build the ranked search SQL and placeholders."""
        return build_book_filter_query(criteria)

    def _query_books(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> list[BookPayload]:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        except pymysql.MySQLError as exc:
            if _is_timeout_error(exc):
                raise BookQueryTimeoutError("Database search timed out.") from exc
            raise BookRepositoryError("Database query failed.") from exc

        return [self._to_book_payload(row) for row in rows]

    @staticmethod
    def _to_book_payload(row: Mapping[str, Any]) -> BookPayload:
        return row_to_book_payload(row)


def _is_timeout_error(exc: pymysql.MySQLError) -> bool:
    """Return True when the DB exception indicates query timeout."""
    code: int | None = None
    if exc.args:
        first_arg = exc.args[0]
        if isinstance(first_arg, int):
            code = first_arg
    if code in QUERY_TIMEOUT_ERROR_CODES:
        return True
    message = str(exc).lower()
    return "timeout" in message or "timed out" in message


def _open_connection(
    database_config: Mapping[str, Any],
) -> Any:
    try:
        return pymysql.connect(
            host=str(database_config["host"]),
            port=int(database_config["port"]),
            user=str(database_config["user"]),
            password=str(database_config["password"]),
            database=str(database_config["database"]),
            charset=str(database_config.get("charset", "utf8mb4")),
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
    except pymysql.MySQLError as exc:
        raise BookRepositoryError("Database connection failed.") from exc


def fetch_books(
    database_config: Mapping[str, Any],
    *,
    query: str | None = None,
    filters: BookFilters | None = None,
) -> list[BookPayload]:
    """Fetch books for API responses using default or search query mode."""
    connection = _open_connection(database_config)
    repository = BookRepository(connection=connection)
    try:
        if query is None:
            return repository.list_books(filters=filters)
        return repository.search_books(query=query, filters=filters)
    finally:
        connection.close()


def search_books_by_criteria(
    database_config: Mapping[str, Any],
    *,
    criteria: BookFilterCriteria,
) -> list[BookPayload]:
    """Fetch books from the database using advanced filter criteria."""
    connection = _open_connection(database_config)
    repository = BookRepository(connection=connection)
    try:
        return repository.search(criteria)
    finally:
        connection.close()
