import os
import unittest
from pathlib import Path
from typing import Any

import pymysql

from db.setup_database import (
    DbConnectionParams,
    REQUIRED_TABLES,
    setup_database,
)


def mysql_env_ready() -> bool:
    required = (
        "DEV_MYSQL_HOST",
        "DEV_MYSQL_PORT",
        "DEV_MYSQL_USER",
        "DEV_MYSQL_PASSWORD",
        "DEV_MYSQL_DATABASE",
    )
    return all(os.environ.get(name) for name in required)


@unittest.skipUnless(mysql_env_ready(), "MySQL environment variables not set")
class MySQLSetupValidationIntegrationTests(unittest.TestCase):
    def _connection_params(self) -> DbConnectionParams:
        return DbConnectionParams(
            database=os.environ["DEV_MYSQL_DATABASE"],
            host=os.environ["DEV_MYSQL_HOST"],
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
        )

    def _open_connection(self) -> Any:
        return pymysql.connect(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
            database=os.environ["DEV_MYSQL_DATABASE"],
            charset="utf8mb4",
            autocommit=True,
        )

    def test_setup_database_validates_connection_and_queries(self):
        params = self._connection_params()
        schema_path = Path("/workspace/db/schema.sql")
        migrations_dir = Path("/workspace/db/migrations")

        setup_result = setup_database(params, schema_path, migrations_dir)

        self.assertTrue(setup_result.success, setup_result.message)
        with self._open_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                select_one_row = cursor.fetchone()

                cursor.execute("SELECT DATABASE()")
                database_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                      AND table_name IN (%s, %s, %s)
                    """,
                    REQUIRED_TABLES,
                )
                required_tables_row = cursor.fetchone()

        self.assertEqual(select_one_row[0], 1)
        self.assertEqual(database_row[0], params.database)
        self.assertEqual(required_tables_row[0], len(REQUIRED_TABLES))
