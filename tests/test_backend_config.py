import unittest

from backend.config import load_app_config, load_database_config


class BackendConfigTests(unittest.TestCase):
    def test_load_app_config_defaults_to_development_profile(self) -> None:
        config = load_app_config(environ={})

        self.assertEqual(config.environment, "development")
        self.assertFalse(config.debug)
        self.assertEqual(config.database.host, "dev-mysql")
        self.assertEqual(config.database.port, 3306)
        self.assertEqual(config.database.database, "dev_find_me_a_book")
        self.assertEqual(config.database.user, "devagent")
        self.assertEqual(config.database.password, "")

    def test_load_app_config_uses_flask_env_and_db_overrides(self) -> None:
        config = load_app_config(
            environ={
                "FLASK_ENV": "production",
                "DB_HOST": "mysql.internal",
                "DB_PORT": "3310",
                "DB_NAME": "books_prod",
                "DB_USER": "books",
                "DB_PASSWORD": "supersecret",
                "BACKEND_DEBUG": "false",
            }
        )

        self.assertEqual(config.environment, "production")
        self.assertFalse(config.debug)
        self.assertEqual(config.database.host, "mysql.internal")
        self.assertEqual(config.database.port, 3310)
        self.assertEqual(config.database.database, "books_prod")
        self.assertEqual(config.database.user, "books")
        self.assertEqual(config.database.password, "supersecret")

    def test_load_database_config_supports_dev_mysql_fallback(self) -> None:
        database = load_database_config(
            environ={
                "DEV_MYSQL_HOST": "legacy-host",
                "DEV_MYSQL_PORT": "3309",
                "DEV_MYSQL_DATABASE": "legacy_db",
                "DEV_MYSQL_USER": "legacy_user",
                "DEV_MYSQL_PASSWORD": "legacy_pass",
            }
        )

        self.assertEqual(database.host, "legacy-host")
        self.assertEqual(database.port, 3309)
        self.assertEqual(database.database, "legacy_db")
        self.assertEqual(database.user, "legacy_user")
        self.assertEqual(database.password, "legacy_pass")

    def test_load_app_config_supports_generic_log_level_fallback(self) -> None:
        config = load_app_config(environ={"LOG_LEVEL": "debug"})

        self.assertEqual(config.log_level, "DEBUG")

    def test_backend_log_level_takes_precedence_over_log_level(self) -> None:
        config = load_app_config(
            environ={
                "BACKEND_LOG_LEVEL": "warning",
                "LOG_LEVEL": "debug",
            }
        )

        self.assertEqual(config.log_level, "WARNING")

    def test_load_app_config_raises_for_unknown_flask_env(self) -> None:
        with self.assertRaises(ValueError):
            load_app_config(environ={"FLASK_ENV": "staging"})


if __name__ == "__main__":
    unittest.main()
