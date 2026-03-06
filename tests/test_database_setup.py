import argparse
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from db.setup_database import (
    DbConnectionParams,
    apply_schema,
    build_client_args,
    create_database,
    parse_connection_string,
    resolve_connection_params,
    setup_database,
)


class ParseConnectionStringTests(unittest.TestCase):
    def test_parse_connection_string_extracts_expected_keys(self):
        parsed = parse_connection_string(
            "host=remote-db user=bookapp dbname=find_me_a_book port=5433"
        )
        self.assertEqual(parsed["host"], "remote-db")
        self.assertEqual(parsed["user"], "bookapp")
        self.assertEqual(parsed["dbname"], "find_me_a_book")
        self.assertEqual(parsed["port"], "5433")

    def test_parse_connection_string_ignores_invalid_tokens(self):
        parsed = parse_connection_string("host=db noequals user=reader")
        self.assertEqual(parsed, {"host": "db", "user": "reader"})


class ConnectionParamResolutionTests(unittest.TestCase):
    def test_resolve_params_from_connection_string(self):
        args = argparse.Namespace(
            database_name=None,
            host=None,
            user=None,
            port=None,
            connection_string="host=rh user=ru dbname=rdb port=5432",
        )
        params = resolve_connection_params(args)
        self.assertEqual(
            params,
            DbConnectionParams(
                dbname="rdb",
                host="rh",
                user="ru",
                port="5432",
            ),
        )

    def test_resolve_params_prefers_explicit_arguments(self):
        args = argparse.Namespace(
            database_name="explicit_db",
            host="explicit_host",
            user="explicit_user",
            port="5434",
            connection_string="host=rh user=ru dbname=rdb port=5432",
        )
        params = resolve_connection_params(args)
        self.assertEqual(
            params,
            DbConnectionParams(
                dbname="explicit_db",
                host="explicit_host",
                user="explicit_user",
                port="5434",
            ),
        )

    def test_resolve_params_requires_dbname(self):
        args = argparse.Namespace(
            database_name=None,
            host=None,
            user=None,
            port=None,
            connection_string="host=rh user=ru",
        )
        with self.assertRaises(ValueError):
            resolve_connection_params(args)


class CommandConstructionTests(unittest.TestCase):
    def test_build_client_args(self):
        params = DbConnectionParams(
            dbname="find_me_a_book",
            host="db.example",
            user="book_user",
            port="5432",
        )
        self.assertEqual(
            build_client_args(params),
            ["-h", "db.example", "-U", "book_user", "-p", "5432"],
        )

    @patch("db.setup_database.run_command")
    def test_create_database_invokes_createdb(self, run_command_mock):
        params = DbConnectionParams(
            dbname="find_me_a_book",
            host="db.example",
            user="book_user",
            port="5432",
        )
        create_database(params)
        run_command_mock.assert_called_once_with(
            [
                "createdb",
                "--if-not-exists",
                "-h",
                "db.example",
                "-U",
                "book_user",
                "-p",
                "5432",
                "find_me_a_book",
            ]
        )

    @patch("db.setup_database.run_command")
    def test_apply_schema_invokes_psql(self, run_command_mock):
        params = DbConnectionParams(dbname="find_me_a_book")
        apply_schema(params, Path("/tmp/schema.sql"))
        run_command_mock.assert_called_once_with(
            [
                "psql",
                "-d",
                "find_me_a_book",
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                "/tmp/schema.sql",
            ]
        )


class SetupDatabaseTests(unittest.TestCase):
    @patch("db.setup_database.apply_schema")
    @patch("db.setup_database.create_database")
    def test_setup_database_success(self, create_db_mock, apply_schema_mock):
        params = DbConnectionParams(dbname="find_me_a_book")
        schema_path = Path("/workspace/db/schema.sql")
        result = setup_database(params, schema_path)
        self.assertTrue(result.success)
        self.assertIn("created successfully", result.message.lower())
        create_db_mock.assert_called_once_with(params)
        apply_schema_mock.assert_called_once_with(params, schema_path)

    def test_setup_database_fails_for_missing_schema(self):
        params = DbConnectionParams(dbname="find_me_a_book")
        result = setup_database(params, Path("/workspace/db/missing.sql"))
        self.assertFalse(result.success)
        self.assertIn("does not exist", result.message)

    @patch("db.setup_database.create_database")
    def test_setup_database_surfaces_subprocess_error(self, create_db_mock):
        create_db_mock.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["createdb", "find_me_a_book"],
            stderr="permission denied",
        )
        params = DbConnectionParams(dbname="find_me_a_book")
        result = setup_database(params, Path("/workspace/db/schema.sql"))
        self.assertFalse(result.success)
        self.assertIn("permission denied", result.message)


if __name__ == "__main__":
    unittest.main()

