"""Data access for listing and searching books."""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

import pymysql

DEFAULT_BOOK_LIMIT = 20
SPICE_LEVEL_TO_MATURITY_RATING: dict[str, str] = {
    "low": "general",
    "medium": "teen",
    "high": "mature",
}
MATURITY_MIN_AGE_SQL = (
    "CASE b.maturity_rating "
    "WHEN 'general' THEN 0 "
    "WHEN 'teen' THEN 13 "
    "WHEN 'mature' THEN 18 "
    "ELSE 0 END"
)
MATURITY_MAX_AGE_SQL = (
    "CASE b.maturity_rating "
    "WHEN 'general' THEN 12 "
    "WHEN 'teen' THEN 17 "
    "WHEN 'mature' THEN 120 "
    "ELSE 120 END"
)
BOOK_SELECT_SQL = """
    SELECT
      b.id AS id,
      b.title AS title,
      COALESCE(author_data.author_names, 'Unknown Author') AS author,
      genre_data.genre_names AS genre,
      b.maturity_rating AS age_rating,
      b.description AS description
    FROM books b
    LEFT JOIN (
      SELECT
        ba.book_id AS book_id,
        GROUP_CONCAT(
          DISTINCT a.full_name
          ORDER BY ba.author_order
          SEPARATOR ', '
        ) AS author_names
      FROM book_authors ba
      INNER JOIN authors a ON a.id = ba.author_id
      GROUP BY ba.book_id
    ) AS author_data ON author_data.book_id = b.id
    LEFT JOIN (
      SELECT
        bg.book_id AS book_id,
        GROUP_CONCAT(
          DISTINCT g.display_name
          ORDER BY g.display_name
          SEPARATOR ', '
        ) AS genre_names
      FROM book_genres bg
      INNER JOIN genres g ON g.id = bg.genre_id
      GROUP BY bg.book_id
    ) AS genre_data ON genre_data.book_id = b.id
"""


class BookPayload(TypedDict):
    """JSON-serializable book data returned by API endpoints."""

    id: int
    title: str
    author: str
    genre: str | None
    age_rating: str
    description: str | None


class BookFilters(TypedDict, total=False):
    """Optional query filters for book listing/search."""

    genre: str
    age_min: int
    age_max: int
    subject: str
    spice_level: str


class BookRepositoryError(RuntimeError):
    """Raised when the repository cannot query the database."""


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
        sql, params = self._build_books_query(
            query=None,
            filters=filters,
            limit=limit,
        )
        return self._query_books(sql, params)

    def search_books(
        self,
        query: str,
        *,
        limit: int = DEFAULT_BOOK_LIMIT,
        filters: BookFilters | None = None,
    ) -> list[BookPayload]:
        """Search books by title, author, or description text."""
        sql, params = self._build_books_query(
            query=query,
            filters=filters,
            limit=limit,
        )
        return self._query_books(sql, params)

    def _build_books_query(
        self,
        *,
        query: str | None,
        filters: BookFilters | None,
        limit: int,
    ) -> tuple[str, tuple[Any, ...]]:
        where_clauses: list[str] = []
        params: list[Any] = []

        if query is not None:
            like_pattern = f"%{query}%"
            where_clauses.append(
                "("
                "b.title LIKE %s "
                "OR b.description LIKE %s "
                "OR author_data.author_names LIKE %s"
                ")"
            )
            params.extend([like_pattern, like_pattern, like_pattern])

        active_filters = filters or {}
        genre = active_filters.get("genre")
        if genre is not None:
            where_clauses.append(
                """
                EXISTS (
                  SELECT 1
                  FROM book_genres filter_bg
                  INNER JOIN genres filter_g
                    ON filter_g.id = filter_bg.genre_id
                  WHERE filter_bg.book_id = b.id
                    AND (
                      LOWER(filter_g.code) = LOWER(%s)
                      OR LOWER(filter_g.display_name) = LOWER(%s)
                    )
                )
                """
            )
            params.extend([genre, genre])

        subject = active_filters.get("subject")
        if subject is not None:
            where_clauses.append(
                "b.description IS NOT NULL AND LOWER(b.description) LIKE LOWER(%s)"
            )
            params.append(f"%{subject}%")

        spice_level = active_filters.get("spice_level")
        if spice_level is not None:
            maturity_rating = SPICE_LEVEL_TO_MATURITY_RATING[spice_level]
            where_clauses.append("b.maturity_rating = %s")
            params.append(maturity_rating)

        age_min = active_filters.get("age_min")
        if age_min is not None:
            where_clauses.append(f"{MATURITY_MAX_AGE_SQL} >= %s")
            params.append(age_min)

        age_max = active_filters.get("age_max")
        if age_max is not None:
            where_clauses.append(f"{MATURITY_MIN_AGE_SQL} <= %s")
            params.append(age_max)

        sql_parts = [BOOK_SELECT_SQL.strip()]
        if where_clauses:
            sql_parts.append("WHERE " + " AND ".join(where_clauses))
        sql_parts.append("ORDER BY b.updated_at DESC, b.id DESC")
        sql_parts.append("LIMIT %s")
        params.append(limit)

        sql = "\n".join(sql_parts)
        return sql, tuple(params)

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
            raise BookRepositoryError("Database query failed.") from exc

        return [self._to_book_payload(row) for row in rows]

    @staticmethod
    def _to_book_payload(row: Mapping[str, Any]) -> BookPayload:
        return BookPayload(
            id=int(row["id"]),
            title=str(row["title"]),
            author=str(row["author"]),
            genre=str(row["genre"]) if row.get("genre") is not None else None,
            age_rating=str(row["age_rating"]),
            description=(
                str(row["description"])
                if row.get("description") is not None
                else None
            ),
        )


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
