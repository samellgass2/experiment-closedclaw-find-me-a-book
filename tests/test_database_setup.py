import argparse
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db.setup_database import (
    DbConnectionParams,
    REQUIRED_TABLES,
    apply_migrations,
    build_client_args,
    collect_migration_files,
    create_database,
    run_scalar_query,
    resolve_connection_params,
    setup_database,
    validate_setup,
    validate_database_name,
)


class ConnectionParamResolutionTests(unittest.TestCase):
    def test_resolve_params_from_environment(self):
        args = argparse.Namespace(
            database_name=None,
            host=None,
            user=None,
            password=None,
            port=None,
        )
        with patch.dict(
            "os.environ",
            {
                "DB_NAME": "find_me_a_book",
                "DB_HOST": "db.example",
                "DB_USER": "book_user",
                "DB_PASSWORD": "topsecret",
                "DB_PORT": "3306",
            },
            clear=True,
        ):
            params = resolve_connection_params(args)

        self.assertEqual(
            params,
            DbConnectionParams(
                database="find_me_a_book",
                host="db.example",
                user="book_user",
                password="topsecret",
                port=3306,
            ),
        )

    def test_resolve_params_prefers_explicit_arguments(self):
        args = argparse.Namespace(
            database_name="explicit_db",
            host="explicit_host",
            user="explicit_user",
            password="explicit_pass",
            port="3307",
        )
        with patch.dict(
            "os.environ",
            {
                "DB_NAME": "env_db",
                "DB_HOST": "env_host",
                "DB_USER": "env_user",
                "DB_PASSWORD": "env_pass",
                "DB_PORT": "3306",
            },
            clear=True,
        ):
            params = resolve_connection_params(args)

        self.assertEqual(
            params,
            DbConnectionParams(
                database="explicit_db",
                host="explicit_host",
                user="explicit_user",
                password="explicit_pass",
                port=3307,
            ),
        )

    def test_resolve_params_uses_defaults_when_env_missing(self):
        args = argparse.Namespace(
            database_name=None,
            host=None,
            user=None,
            password=None,
            port=None,
        )
        with patch.dict("os.environ", {}, clear=True):
            params = resolve_connection_params(args)

        self.assertEqual(
            params,
            DbConnectionParams(
                database="dev_find_me_a_book",
                host="dev-mysql",
                user="devagent",
                password="",
                port=3306,
            ),
        )


class CommandConstructionTests(unittest.TestCase):
    def test_build_client_args(self):
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        self.assertEqual(
            build_client_args(params),
            [
                "--host",
                "db.example",
                "--port",
                "3306",
                "--user",
                "book_user",
                "--password=secret",
                "--protocol=TCP",
                "--default-character-set=utf8mb4",
            ],
        )

    @patch("db.setup_database.run_command")
    def test_create_database_invokes_mysql(self, run_command_mock):
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        create_database(params)
        run_command_mock.assert_called_once_with(
            [
                "mysql",
                "--host",
                "db.example",
                "--port",
                "3306",
                "--user",
                "book_user",
                "--password=secret",
                "--protocol=TCP",
                "--default-character-set=utf8mb4",
                "--execute",
                "CREATE DATABASE IF NOT EXISTS `find_me_a_book` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            ]
        )

    def test_validate_database_name_rejects_invalid_characters(self):
        with self.assertRaises(ValueError):
            validate_database_name("find-me-a-book")


class MigrationTests(unittest.TestCase):
    def test_collect_migration_files_returns_sorted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            (path / "002_second.sql").write_text("SELECT 2;", encoding="utf-8")
            (path / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            files = collect_migration_files(path)

        self.assertEqual([f.name for f in files], ["001_first.sql", "002_second.sql"])

    @patch("db.setup_database.apply_sql_file")
    def test_apply_migrations_applies_all_files(self, apply_sql_file_mock):
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            first = path / "001_first.sql"
            second = path / "002_second.sql"
            first.write_text("SELECT 1;", encoding="utf-8")
            second.write_text("SELECT 2;", encoding="utf-8")

            apply_migrations(params, path)

        apply_sql_file_mock.assert_any_call(params, first)
        apply_sql_file_mock.assert_any_call(params, second)
        self.assertEqual(apply_sql_file_mock.call_count, 2)


class SetupDatabaseTests(unittest.TestCase):
    @patch("db.setup_database.validate_setup")
    @patch("db.setup_database.apply_schema")
    @patch("db.setup_database.apply_migrations")
    @patch("db.setup_database.collect_migration_files")
    @patch("db.setup_database.create_database")
    @patch("db.setup_database.check_server_reachable")
    @patch("db.setup_database.ensure_mysql_tools_available")
    def test_setup_database_success_with_migrations(
        self,
        tools_mock,
        reachable_mock,
        create_db_mock,
        collect_migrations_mock,
        apply_migrations_mock,
        apply_schema_mock,
        validate_setup_mock,
    ):
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        schema_path = Path("/workspace/db/schema.sql")
        migrations_dir = Path("/workspace/db/migrations")
        collect_migrations_mock.return_value = [Path("/workspace/db/migrations/001_init.sql")]

        result = setup_database(params, schema_path, migrations_dir)

        self.assertTrue(result.success)
        self.assertIn("created successfully", result.message.lower())
        tools_mock.assert_called_once()
        reachable_mock.assert_called_once_with(params)
        create_db_mock.assert_called_once_with(params)
        apply_migrations_mock.assert_called_once_with(params, migrations_dir)
        apply_schema_mock.assert_not_called()
        validate_setup_mock.assert_called_once_with(params)

    def test_setup_database_fails_for_missing_schema(self):
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        result = setup_database(
            params,
            Path("/workspace/db/missing.sql"),
            Path("/workspace/db/migrations"),
        )
        self.assertFalse(result.success)
        self.assertIn("does not exist", result.message)

    @patch("db.setup_database.ensure_mysql_tools_available")
    def test_setup_database_surfaces_tool_error(self, tools_mock):
        tools_mock.side_effect = FileNotFoundError("mysql missing")
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        result = setup_database(
            params,
            Path("/workspace/db/schema.sql"),
            Path("/workspace/db/migrations"),
        )
        self.assertFalse(result.success)
        self.assertIn("mysql missing", result.message)

    @patch("db.setup_database.check_server_reachable")
    @patch("db.setup_database.ensure_mysql_tools_available")
    def test_setup_database_surfaces_subprocess_error(
        self,
        _tools_mock,
        reachable_mock,
    ):
        reachable_mock.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["mysqladmin", "ping"],
            stderr="connection refused",
        )
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        result = setup_database(
            params,
            Path("/workspace/db/schema.sql"),
            Path("/workspace/db/migrations"),
        )
        self.assertFalse(result.success)
        self.assertIn("connection refused", result.message)

    @patch("db.setup_database.validate_setup")
    @patch("db.setup_database.apply_schema")
    @patch("db.setup_database.collect_migration_files")
    @patch("db.setup_database.create_database")
    @patch("db.setup_database.check_server_reachable")
    @patch("db.setup_database.ensure_mysql_tools_available")
    def test_setup_database_surfaces_validation_error(
        self,
        _tools_mock,
        _reachable_mock,
        _create_db_mock,
        _apply_schema_mock,
        collect_migrations_mock,
        validate_setup_mock,
    ):
        collect_migrations_mock.return_value = []
        validate_setup_mock.side_effect = ValueError("validation failed")
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )
        result = setup_database(
            params,
            Path("/workspace/db/schema.sql"),
            Path("/workspace/db/migrations"),
        )
        self.assertFalse(result.success)
        self.assertIn("validation failed", result.message)


class ValidationTests(unittest.TestCase):
    @patch("db.setup_database.run_command")
    def test_run_scalar_query_returns_first_line(self, run_command_mock):
        run_command_mock.return_value = subprocess.CompletedProcess(
            args=["mysql"],
            returncode=0,
            stdout="1\nignored\n",
            stderr="",
        )
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )

        value = run_scalar_query(params, "SELECT 1;")

        self.assertEqual(value, "1")

    @patch("db.setup_database.run_command")
    def test_validate_setup_runs_expected_checks(self, run_command_mock):
        run_command_mock.side_effect = [
            subprocess.CompletedProcess(
                args=["mysql"],
                returncode=0,
                stdout="1\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["mysql"],
                returncode=0,
                stdout="find_me_a_book\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["mysql"],
                returncode=0,
                stdout=f"{len(REQUIRED_TABLES)}\n",
                stderr="",
            ),
        ]
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )

        validate_setup(params)

        self.assertEqual(run_command_mock.call_count, 3)

    @patch("db.setup_database.run_command")
    def test_validate_setup_fails_when_select_one_wrong(self, run_command_mock):
        run_command_mock.return_value = subprocess.CompletedProcess(
            args=["mysql"],
            returncode=0,
            stdout="2\n",
            stderr="",
        )
        params = DbConnectionParams(
            database="find_me_a_book",
            host="db.example",
            user="book_user",
            password="secret",
            port=3306,
        )

        with self.assertRaises(ValueError):
            validate_setup(params)


if __name__ == "__main__":
    unittest.main()
