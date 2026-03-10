import importlib
import unittest
from unittest.mock import patch


class RootConfigTests(unittest.TestCase):
    def test_import_config_exposes_required_attributes(self):
        import config

        self.assertTrue(hasattr(config, "DB_HOST"))
        self.assertTrue(hasattr(config, "DB_PORT"))
        self.assertTrue(hasattr(config, "DB_NAME"))
        self.assertTrue(hasattr(config, "DB_USER"))
        self.assertTrue(hasattr(config, "DB_PASSWORD"))
        self.assertTrue(hasattr(config, "BOOK_SOURCE_BASE_URL"))
        self.assertTrue(hasattr(config, "BOOK_SOURCE_API_KEY"))
        self.assertTrue(hasattr(config, "CRAWLER_RATE_LIMIT_PER_MIN"))

    def test_load_database_settings_supports_db_prefixed_env(self):
        with patch.dict(
            "os.environ",
            {
                "DB_HOST": "mysql.internal",
                "DB_PORT": "3310",
                "DB_NAME": "books_db",
                "DB_USER": "books_user",
                "DB_PASSWORD": "books_pass",
            },
            clear=True,
        ):
            import config

            importlib.reload(config)
            settings = config.load_database_settings()

        self.assertEqual(settings.host, "mysql.internal")
        self.assertEqual(settings.port, 3310)
        self.assertEqual(settings.name, "books_db")
        self.assertEqual(settings.user, "books_user")
        self.assertEqual(settings.password, "books_pass")

    def test_load_database_settings_falls_back_to_dev_mysql_env(self):
        with patch.dict(
            "os.environ",
            {
                "DEV_MYSQL_HOST": "legacy-host",
                "DEV_MYSQL_PORT": "3309",
                "DEV_MYSQL_DATABASE": "legacy_db",
                "DEV_MYSQL_USER": "legacy_user",
                "DEV_MYSQL_PASSWORD": "legacy_pass",
            },
            clear=True,
        ):
            import config

            importlib.reload(config)
            settings = config.load_database_settings()

        self.assertEqual(settings.host, "legacy-host")
        self.assertEqual(settings.port, 3309)
        self.assertEqual(settings.name, "legacy_db")
        self.assertEqual(settings.user, "legacy_user")
        self.assertEqual(settings.password, "legacy_pass")

    def test_load_book_source_settings_api_key_defaults_to_none(self):
        with patch.dict("os.environ", {}, clear=True):
            import config

            importlib.reload(config)
            settings = config.load_book_source_settings()

        self.assertEqual(settings.base_url, "https://www.goodreads.com")
        self.assertIsNone(settings.api_key)


if __name__ == "__main__":
    unittest.main()
