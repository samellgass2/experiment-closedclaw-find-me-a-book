import unittest
from importlib.util import find_spec
import logging
from unittest.mock import patch

FLASK_AVAILABLE = find_spec("flask") is not None

if FLASK_AVAILABLE:
    from backend.app import HealthProbeResult, create_app
    from backend.config import AppConfig, DatabaseConfig, ExternalServiceConfig
    from backend.repositories.books import (
        BookFilterCriteria,
        BookQueryTimeoutError,
        BookRepositoryError,
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask is not installed in this environment")
class BooksApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig(
            environment="test",
            debug=False,
            log_level="INFO",
            database=DatabaseConfig(
                host="localhost",
                port=3306,
                user="dev",
                password="dev",
                database="dev_find_me_a_book",
            ),
            external_services=ExternalServiceConfig(
                book_source_base_url="https://www.goodreads.com",
                book_source_api_key=None,
            ),
        )
        self.app = create_app(config)
        self.client = self.app.test_client()

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_without_q_returns_default_results(
        self,
        search_mock,
    ) -> None:
        search_mock.return_value = []

        response = self.client.get("/api/books")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])
        search_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            criteria=BookFilterCriteria(),
        )

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_with_q_returns_matching_books(
        self,
        search_mock,
    ) -> None:
        search_mock.return_value = [
            {
                "id": 1,
                "title": "Test Driven Development",
                "author": "Kent Beck",
                "genre": "Software",
                "age_rating": "general",
                "spice_level": "low",
                "summary": "A practical testing book.",
                "description": "A practical testing book.",
                "subject_matter": [],
                "plot_points": [],
                "character_dynamics": [],
            }
        ]

        response = self.client.get("/api/books?q=test")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 1)
        self.assertEqual(
            sorted(body[0].keys()),
            [
                "age_rating",
                "author",
                "character_dynamics",
                "description",
                "genre",
                "id",
                "plot_points",
                "spice_level",
                "subject_matter",
                "summary",
                "title",
            ],
        )
        search_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            criteria=BookFilterCriteria(query="test"),
        )

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_with_empty_q_treated_as_no_query(
        self,
        search_mock,
    ) -> None:
        search_mock.return_value = []

        response = self.client.get("/api/books?q=   ")

        self.assertEqual(response.status_code, 200)
        search_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            criteria=BookFilterCriteria(),
        )

    def test_get_books_rejects_multiple_q_values(self) -> None:
        response = self.client.get("/api/books?q=first&q=second")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_passes_genre_filter(
        self,
        search_mock,
    ) -> None:
        search_mock.return_value = []

        response = self.client.get("/api/books?genre=fantasy")

        self.assertEqual(response.status_code, 200)
        search_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            criteria=BookFilterCriteria(genre="fantasy"),
        )

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_passes_combined_advanced_filters(
        self,
        search_mock,
    ) -> None:
        search_mock.return_value = []

        response = self.client.get(
            (
                "/api/books?genre=fantasy&age_rating=ya&subject_matter=friendship,magic"
                "&plot_points=quest&character_dynamics=found-family"
                "&spice_level=low"
            )
        )

        self.assertEqual(response.status_code, 200)
        search_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            criteria=BookFilterCriteria(
                genre="fantasy",
                age_rating="teen",
                subject_matter=("friendship", "magic"),
                plot_points=("quest",),
                character_dynamics=("found-family",),
                spice_level="low",
            ),
        )

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_rejects_non_numeric_age_filter(
        self,
        search_mock,
    ) -> None:
        response = self.client.get("/api/books?age_min=abc")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")
        self.assertIn("age_min must be an integer", payload["message"])
        search_mock.assert_not_called()

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_rejects_unsupported_spice_level(
        self,
        search_mock,
    ) -> None:
        response = self.client.get("/api/books?spice_level=extreme")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")
        self.assertIn("spice_level must be one of", payload["message"])
        search_mock.assert_not_called()

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_rejects_unsupported_age_rating(
        self,
        search_mock,
    ) -> None:
        response = self.client.get("/api/books?age_rating=unknown-level")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")
        self.assertIn("age_rating must be one of", payload["message"])
        search_mock.assert_not_called()

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_rejects_invalid_age_range(
        self,
        search_mock,
    ) -> None:
        response = self.client.get("/api/books?age_min=18&age_max=12")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_parameter")
        self.assertIn("age_min cannot be greater than age_max", payload["message"])
        search_mock.assert_not_called()

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_returns_500_when_database_fails(
        self,
        search_mock,
    ) -> None:
        search_mock.side_effect = BookRepositoryError("connect failed")

        response = self.client.get("/api/books?q=test")

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"], "database_unavailable")
        self.assertIn("Unable to fetch books", payload["message"])

    @patch("backend.app.search_books_by_criteria")
    def test_get_books_returns_504_when_search_times_out(
        self,
        search_mock,
    ) -> None:
        search_mock.side_effect = BookQueryTimeoutError("timed out")

        response = self.client.get("/api/books?q=test")

        self.assertEqual(response.status_code, 504)
        payload = response.get_json()
        self.assertEqual(payload["error"], "search_timeout")

    @patch("backend.app.search_books_by_criteria")
    def test_search_alias_route_is_available(
        self,
        search_mock,
    ) -> None:
        search_mock.return_value = []

        response = self.client.get("/api/books/search?q=test")

        self.assertEqual(response.status_code, 200)
        search_mock.assert_called_once_with(
            self.app.config["DATABASE_CONFIG"],
            criteria=BookFilterCriteria(query="test"),
        )

    @patch("backend.app._run_health_probe")
    def test_health_reports_db_and_migration_fields(self, probe_mock) -> None:
        probe_mock.return_value = HealthProbeResult(
            db_connected=True,
            migration_version="003_book_taxonomy_fields",
        )

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"]["status"], "up")
        self.assertEqual(payload["migration_version"], "003_book_taxonomy_fields")
        self.assertEqual(payload["migration_status"], "available")

    @patch("backend.app._run_health_probe")
    def test_ready_returns_200_when_db_is_available(self, probe_mock) -> None:
        probe_mock.return_value = HealthProbeResult(
            db_connected=True,
            migration_version=None,
        )

        response = self.client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ready")

    @patch("backend.app._run_health_probe")
    def test_ready_returns_503_when_db_is_unavailable(self, probe_mock) -> None:
        probe_mock.return_value = HealthProbeResult(
            db_connected=False,
            migration_version=None,
        )

        response = self.client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "not_ready")

    @patch("backend.app._run_health_probe")
    def test_request_log_contains_method_path_and_status(self, probe_mock) -> None:
        probe_mock.return_value = HealthProbeResult(
            db_connected=True,
            migration_version=None,
        )

        captured_records: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured_records.append(record)

        backend_logger = logging.getLogger("backend.app")
        handler = _CaptureHandler()
        backend_logger.addHandler(handler)
        try:
            self.client.get("/health")
        finally:
            backend_logger.removeHandler(handler)

        request_logs = [
            record
            for record in captured_records
            if getattr(record, "event", "") == "http_request"
        ]
        self.assertTrue(request_logs)
        request_record = request_logs[-1]
        self.assertEqual(getattr(request_record, "method", None), "GET")
        self.assertEqual(getattr(request_record, "path", None), "/health")
        self.assertEqual(getattr(request_record, "status_code", None), 200)


if __name__ == "__main__":
    unittest.main()
