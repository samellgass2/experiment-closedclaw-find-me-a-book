from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import unittest

import pymysql

from backend.repositories.books import (
    BookFilterCriteria,
    BookRepository,
    _is_timeout_error,
    _to_boolean_prefix_query,
)


@dataclass(frozen=True)
class SampleBook:
    id: int
    title: str
    author: str
    genres: tuple[str, ...]
    age_rating: str
    description: str


class EvaluatingFakeCursor:
    def __init__(self, catalog: Iterable[SampleBook]) -> None:
        self._catalog = tuple(catalog)
        self.executed_sql = ""
        self.executed_params: tuple[Any, ...] = ()
        self._rows: list[dict[str, Any]] = []

    def __enter__(self) -> "EvaluatingFakeCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executed_sql = sql
        self.executed_params = params

        limit = int(params[-1]) if params else 20
        filtered_books = list(self._catalog)

        if "filter_g.code = %s" in sql:
            genre_filter = self._extract_genre_filter(params)
            filtered_books = [
                book
                for book in filtered_books
                if any(genre_filter == genre.lower() for genre in book.genres)
            ]

        if "b.maturity_rating = %s" in sql:
            age_filter = self._extract_age_rating_filter(params)
            filtered_books = [
                book for book in filtered_books if book.age_rating == age_filter
            ]

        self._rows = [self._to_row(book) for book in filtered_books[:limit]]

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows

    @staticmethod
    def _extract_genre_filter(params: tuple[Any, ...]) -> str:
        return str(params[0]).lower()

    @staticmethod
    def _extract_age_rating_filter(params: tuple[Any, ...]) -> str:
        for param in params[:-1]:
            if str(param) in {"general", "teen", "mature"}:
                return str(param)
        raise AssertionError("Expected an age rating parameter in query params")

    @staticmethod
    def _to_row(book: SampleBook) -> dict[str, Any]:
        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": ", ".join(book.genres),
            "age_rating": book.age_rating,
            "description": book.description,
        }


class EvaluatingFakeConnection:
    def __init__(self, catalog: Iterable[SampleBook]) -> None:
        self.cursor_instance = EvaluatingFakeCursor(catalog)

    def cursor(self) -> EvaluatingFakeCursor:
        return self.cursor_instance


def _sample_catalog() -> list[SampleBook]:
    return [
        SampleBook(
            id=101,
            title="Enchanted Grove",
            author="Mira Vale",
            genres=("fantasy",),
            age_rating="general",
            description="Two friends protect their woodland village.",
        ),
        SampleBook(
            id=102,
            title="Starship Trials",
            author="K. Orion",
            genres=("science-fiction",),
            age_rating="teen",
            description="Cadets survive dangerous academy missions.",
        ),
        SampleBook(
            id=103,
            title="Dragon Oath",
            author="Mira Vale",
            genres=("fantasy",),
            age_rating="teen",
            description="A reluctant hero joins a dragon-bound quest.",
        ),
        SampleBook(
            id=104,
            title="Midnight Vows",
            author="Elena Hart",
            genres=("romance",),
            age_rating="mature",
            description="A forbidden romance tests loyalty and desire.",
        ),
    ]


class BookRepositoryFilteringUnitTests(unittest.TestCase):
    def test_single_genre_filter_includes_and_excludes_expected_books(self) -> None:
        connection = EvaluatingFakeConnection(_sample_catalog())
        repository = BookRepository(connection=connection)

        books = repository.search(BookFilterCriteria(genre="fantasy", limit=10))

        titles = {book["title"] for book in books}
        self.assertEqual(titles, {"Enchanted Grove", "Dragon Oath"})
        self.assertNotIn("Starship Trials", titles)
        self.assertNotIn("Midnight Vows", titles)
        self.assertIn("filter_g.code = %s", connection.cursor_instance.executed_sql)

    def test_combined_genre_and_age_rating_filters_intersect_results(self) -> None:
        connection = EvaluatingFakeConnection(_sample_catalog())
        repository = BookRepository(connection=connection)

        books = repository.search(
            BookFilterCriteria(
                genre="fantasy",
                age_rating="YA",
                limit=10,
            )
        )

        titles = [book["title"] for book in books]
        self.assertEqual(titles, ["Dragon Oath"])
        self.assertNotIn("Enchanted Grove", titles)
        sql = connection.cursor_instance.executed_sql
        self.assertIn("filter_g.code = %s", sql)
        self.assertIn("b.maturity_rating = %s", sql)

    def test_empty_filters_return_unrestricted_catalog(self) -> None:
        connection = EvaluatingFakeConnection(_sample_catalog())
        repository = BookRepository(connection=connection)

        books = repository.search(BookFilterCriteria(limit=10))

        titles = {book["title"] for book in books}
        self.assertEqual(
            titles,
            {
                "Enchanted Grove",
                "Starship Trials",
                "Dragon Oath",
                "Midnight Vows",
            },
        )
        self.assertNotIn("b.maturity_rating = %s", connection.cursor_instance.executed_sql)

    def test_invalid_age_rating_filter_is_ignored(self) -> None:
        connection = EvaluatingFakeConnection(_sample_catalog())
        repository = BookRepository(connection=connection)

        books = repository.search(BookFilterCriteria(age_rating="not-a-rating", limit=10))

        titles = {book["title"] for book in books}
        self.assertEqual(
            titles,
            {
                "Enchanted Grove",
                "Starship Trials",
                "Dragon Oath",
                "Midnight Vows",
            },
        )
        self.assertNotIn(
            "b.maturity_rating = %s",
            connection.cursor_instance.executed_sql,
        )


class BookRepositoryUtilityUnitTests(unittest.TestCase):
    def test_to_boolean_prefix_query_generates_terms_for_alphanumeric_tokens(self) -> None:
        actual = _to_boolean_prefix_query("Found Family: Dragon Quest")
        self.assertEqual(actual, "+found* +family* +dragon* +quest*")

    def test_to_boolean_prefix_query_falls_back_when_no_tokens(self) -> None:
        actual = _to_boolean_prefix_query("!!!")
        self.assertEqual(actual, "!!!")

    def test_is_timeout_error_detects_known_timeout_code(self) -> None:
        error = pymysql.MySQLError(3024, "Query execution was interrupted")
        self.assertTrue(_is_timeout_error(error))

    def test_is_timeout_error_detects_timeout_wording(self) -> None:
        error = pymysql.MySQLError("operation timed out")
        self.assertTrue(_is_timeout_error(error))

    def test_is_timeout_error_ignores_non_timeout_error(self) -> None:
        error = pymysql.MySQLError(1064, "You have an error in your SQL syntax")
        self.assertFalse(_is_timeout_error(error))


if __name__ == "__main__":
    unittest.main()
