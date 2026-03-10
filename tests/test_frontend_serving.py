import unittest
from importlib.util import find_spec

FLASK_AVAILABLE = find_spec("flask") is not None

if FLASK_AVAILABLE:
    from backend.app import create_app
    from backend.config import AppConfig, DatabaseConfig


@unittest.skipUnless(FLASK_AVAILABLE, "Flask is not installed in this environment")
class FrontendServingTests(unittest.TestCase):
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
        self.client = create_app(config).test_client()

    def test_root_serves_frontend_index_html(self) -> None:
        response = self.client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertIn('id="search-input"', body)

    def test_frontend_module_asset_is_available(self) -> None:
        response = self.client.get("/api/books.js")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.content_type)
        self.assertIn("BOOKS_SEARCH_ENDPOINT", body)


if __name__ == "__main__":
    unittest.main()
