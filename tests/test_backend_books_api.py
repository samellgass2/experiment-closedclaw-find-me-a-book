import unittest
from importlib.util import find_spec
from unittest.mock import patch

FLASK_AVAILABLE = find_spec("flask") is not None

if FLASK_AVAILABLE:
    from backend.app import create_app
    from backend.config import AppConfig, DatabaseConfig
    from backend.repositories.books import BookRepositoryError


@unittest.skipUnless(FLASK_AVAILABLE, "Flask is not installed in this environment")
class BooksApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig(
            debug=False,
            log_level="INFO",
            database=DatabaseConfig(
                host="localhost",
                port=3306,
                user="dev",
                password="dev",
                database="dev_find_me_a_book",
            ),
        )
        self.app = create_app(config)
        self.client = self.app.test_client()

    @patch("backend.app.fetch_books")
    def test_get_books_without_q_returns_default_results(
        self,
        fetch_books_mock,
    ) -> None:
        fetch_books_mock.return_value = []

        response = self.client.get("/api/books")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])
        fetch_books_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            query=None,
            filters={},
        )

    @patch("backend.app.fetch_books")
    def test_get_books_with_q_returns_matching_books(
        self,
        fetch_books_mock,
    ) -> None:
        fetch_books_mock.return_value = [
            {
                "id": 1,
                "title": "Test Driven Development",
                "author": "Kent Beck",
                "genre": "Software",
                "age_rating": "general",
                "description": "A practical testing book.",
            }
        ]

        response = self.client.get("/api/books?q=test")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 1)
        self.assertEqual(
            sorted(body[0].keys()),
            ["age_rating", "author", "description", "genre", "id", "title"],
        )
        fetch_books_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            query="test",
            filters={},
        )

    @patch("backend.app.fetch_books")
    def test_get_books_with_empty_q_treated_as_no_query(
        self,
        fetch_books_mock,
    ) -> None:
        fetch_books_mock.return_value = []

        response = self.client.get("/api/books?q=   ")

        self.assertEqual(response.status_code, 200)
        fetch_books_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            query=None,
            filters={},
        )

    def test_get_books_rejects_multiple_q_values(self) -> None:
        response = self.client.get("/api/books?q=first&q=second")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")

    @patch("backend.app.fetch_books")
    def test_get_books_passes_genre_filter(
        self,
        fetch_books_mock,
    ) -> None:
        fetch_books_mock.return_value = []

        response = self.client.get("/api/books?genre=fantasy")

        self.assertEqual(response.status_code, 200)
        fetch_books_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            query=None,
            filters={"genre": "fantasy"},
        )

    @patch("backend.app.fetch_books")
    def test_get_books_passes_combined_filters(
        self,
        fetch_books_mock,
    ) -> None:
        fetch_books_mock.return_value = []

        response = self.client.get(
            (
                "/api/books?genre=fantasy&subject=friendship"
                "&spice_level=low&age_min=10&age_max=20"
            )
        )

        self.assertEqual(response.status_code, 200)
        fetch_books_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            query=None,
            filters={
                "genre": "fantasy",
                "subject": "friendship",
                "spice_level": "low",
                "age_min": 10,
                "age_max": 20,
            },
        )

    @patch("backend.app.fetch_books")
    def test_get_books_rejects_non_numeric_age_filter(
        self,
        fetch_books_mock,
    ) -> None:
        response = self.client.get("/api/books?age_min=abc")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")
        self.assertIn("age_min must be an integer", payload["message"])
        fetch_books_mock.assert_not_called()

    @patch("backend.app.fetch_books")
    def test_get_books_rejects_unsupported_spice_level(
        self,
        fetch_books_mock,
    ) -> None:
        response = self.client.get("/api/books?spice_level=extreme")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")
        self.assertIn("spice_level must be one of", payload["message"])
        fetch_books_mock.assert_not_called()

    @patch("backend.app.fetch_books")
    def test_get_books_rejects_invalid_age_range(
        self,
        fetch_books_mock,
    ) -> None:
        response = self.client.get("/api/books?age_min=18&age_max=12")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")
        self.assertIn("age_min cannot be greater than age_max", payload["message"])
        fetch_books_mock.assert_not_called()

    @patch("backend.app.fetch_books")
    def test_get_books_returns_500_when_database_fails(
        self,
        fetch_books_mock,
    ) -> None:
        fetch_books_mock.side_effect = BookRepositoryError("connect failed")

        response = self.client.get("/api/books?q=test")

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"], "database_unavailable")
        self.assertIn("Unable to fetch books", payload["message"])


if __name__ == "__main__":
    unittest.main()
