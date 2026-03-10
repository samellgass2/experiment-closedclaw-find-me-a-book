from __future__ import annotations

import unittest
from typing import Any

from backend.filters import BookFilterCriteria, build_book_filter_query
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


class BackendFilterQueryTests(unittest.TestCase):
    def test_genre_and_age_rating_filters_apply_parameterized_where(self) -> None:
        connection = FakeConnection(rows=[_sample_row()])
        repository = BookRepository(connection=connection)

        repository.search(
            BookFilterCriteria(
                genre="fantasy",
                age_rating="general",
            )
        )

        sql = connection._cursor.executed_sql
        params = connection._cursor.executed_params
        self.assertIn("filter_g.code = %s", sql)
        self.assertIn("b.maturity_rating = %s", sql)
        self.assertNotIn("fantasy", sql)
        self.assertEqual(params[:4], ("fantasy", "fantasy", "general", "fantasy"))

    def test_subject_matter_and_spice_level_additional_refinement(self) -> None:
        base_sql, base_params = build_book_filter_query(
            BookFilterCriteria(genre="romance")
        )
        refined_sql, refined_params = build_book_filter_query(
            BookFilterCriteria(
                genre="romance",
                subject_matter=("forbidden love",),
                spice_level="high",
            )
        )

        self.assertIn("LOWER(b.description) LIKE LOWER(%s)", refined_sql)
        self.assertIn("b.maturity_rating = %s", refined_sql)
        self.assertGreater(len(refined_params), len(base_params))
        self.assertIn("%forbidden love%", refined_params)
        self.assertIn("mature", refined_params)

    def test_relevance_ordering_used_when_criteria_present(self) -> None:
        filtered_sql, _ = build_book_filter_query(
            BookFilterCriteria(genre="fantasy", age_rating="general")
        )
        default_sql, _ = build_book_filter_query(BookFilterCriteria())

        self.assertIn("ORDER BY relevance_score DESC", filtered_sql)
        self.assertIn("COALESCE(cb.average_rating, 0) DESC", filtered_sql)
        self.assertNotIn("ORDER BY relevance_score DESC", default_sql)

    def test_relevance_formula_prioritizes_genre_age_over_plot_character(self) -> None:
        sql, _ = build_book_filter_query(
            BookFilterCriteria(
                genre="fantasy",
                age_rating="general",
                plot_points=("quest",),
                character_dynamics=("rivals",),
            )
        )

        self.assertIn("THEN 30 ELSE 0 END", sql)
        self.assertIn("THEN 22 ELSE 0 END", sql)
        self.assertIn("* 8)", sql)
        self.assertIn("* 7)", sql)


if __name__ == "__main__":
    unittest.main()
