import unittest
from typing import Any

from backend.repositories.books import BookRepository


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed_sql = ""
        self.executed_params: tuple[Any, ...] = ()

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executed_sql = sql
        self.executed_params = params

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._cursor = FakeCursor(rows=rows)

    def cursor(self) -> FakeCursor:
        return self._cursor


def _sample_row() -> dict[str, Any]:
    return {
        "id": 1,
        "title": "Sample Book",
        "author": "Sample Author",
        "genre": "Fantasy",
        "age_rating": "general",
        "description": "A friendship story.",
    }


class BookRepositoryFilterQueryTests(unittest.TestCase):
    def test_list_books_applies_genre_filter_with_parameters(self) -> None:
        connection = FakeConnection(rows=[_sample_row()])
        repository = BookRepository(connection=connection)

        books = repository.list_books(filters={"genre": "fantasy"})

        self.assertEqual(len(books), 1)
        self.assertIn("WITH candidate_books AS", connection._cursor.executed_sql)
        self.assertIn("EXISTS (", connection._cursor.executed_sql)
        self.assertIn(
            "filter_g.code = %s",
            connection._cursor.executed_sql,
        )
        self.assertNotIn("fantasy", connection._cursor.executed_sql)
        self.assertEqual(connection._cursor.executed_params[:4], ("fantasy",) * 4)
        self.assertEqual(connection._cursor.executed_params[-1], 20)

    def test_search_books_combines_query_and_filters_conjunctively(self) -> None:
        connection = FakeConnection(rows=[_sample_row()])
        repository = BookRepository(connection=connection)

        repository.search_books(
            query="story",
            filters={
                "genre": "fantasy",
                "subject": "friendship",
                "spice_level": "low",
            },
        )

        sql = connection._cursor.executed_sql
        params = connection._cursor.executed_params
        self.assertIn("WITH candidate_books AS", sql)
        self.assertIn("b.title LIKE %s", sql)
        self.assertIn("LOWER(b.description) LIKE LOWER(%s)", sql)
        self.assertIn("MATCH(b.title, b.description)", sql)
        self.assertIn("b.maturity_rating = %s", sql)
        self.assertEqual(params[0], "story")
        self.assertIn("%story%", params)
        self.assertIn("+story*", params)
        self.assertIn("general", params)
        self.assertEqual(params[-1], 20)

    def test_list_books_applies_age_range_filters(self) -> None:
        connection = FakeConnection(rows=[_sample_row()])
        repository = BookRepository(connection=connection)

        repository.list_books(filters={"age_min": 10, "age_max": 16})

        sql = connection._cursor.executed_sql
        params = connection._cursor.executed_params
        self.assertIn("CASE b.maturity_rating", sql)
        self.assertIn(">= %s", sql)
        self.assertIn("<= %s", sql)
        self.assertEqual(params[-3:], (10, 16, 20))


if __name__ == "__main__":
    unittest.main()
