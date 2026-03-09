"""Data access for listing and searching books."""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

import pymysql

DEFAULT_BOOK_LIMIT = 20


class BookPayload(TypedDict):
    """JSON-serializable book data returned by API endpoints."""

    id: int
    title: str
    author: str
    genre: str | None
    age_rating: str
    description: str | None


class BookRepositoryError(RuntimeError):
    """Raised when the repository cannot query the database."""


class BookRepository:
    """Repository wrapper for reading books from MySQL."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def list_books(self, limit: int = DEFAULT_BOOK_LIMIT) -> list[BookPayload]:
        """Return a default page of books ordered by recent updates."""
        sql = """
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
            ORDER BY b.updated_at DESC, b.id DESC
            LIMIT %s
        """
        return self._query_books(sql, (limit,))

    def search_books(
        self,
        query: str,
        limit: int = DEFAULT_BOOK_LIMIT,
    ) -> list[BookPayload]:
        """Search books by title, author, or description text."""
        like_pattern = f"%{query}%"
        sql = """
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
            WHERE b.title LIKE %s
              OR b.description LIKE %s
              OR author_data.author_names LIKE %s
            ORDER BY b.updated_at DESC, b.id DESC
            LIMIT %s
        """
        return self._query_books(
            sql,
            (like_pattern, like_pattern, like_pattern, limit),
        )

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
) -> list[BookPayload]:
    """Fetch books for API responses using default or search query mode."""
    connection = _open_connection(database_config)
    repository = BookRepository(connection=connection)
    try:
        if query is None:
            return repository.list_books()
        return repository.search_books(query=query)
    finally:
        connection.close()

