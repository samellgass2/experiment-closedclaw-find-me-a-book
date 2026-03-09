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
        )

    def test_get_books_rejects_multiple_q_values(self) -> None:
        response = self.client.get("/api/books?q=first&q=second")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")

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
