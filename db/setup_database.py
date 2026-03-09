"""Create and initialize the MySQL database schema."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DbConnectionParams:
    """Connection parameters used by MySQL client tools."""

    database: str
    host: str
    user: str
    port: int
    password: str


@dataclass(frozen=True)
class SetupResult:
    """Result payload for setup execution."""

    success: bool
    message: str


def run_command(
    command: list[str],
    stdin=None,
) -> subprocess.CompletedProcess[str]:
    """Run shell command and return completed process."""
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
        stdin=stdin,
    )


def validate_database_name(name: str) -> None:
    """Validate db identifier to avoid injection in CREATE DATABASE."""
    if not name:
        raise ValueError("Database name cannot be empty.")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if any(char not in allowed for char in name):
        raise ValueError(
            "Database name must only contain letters, numbers, and underscores."
        )


def build_client_args(params: DbConnectionParams) -> list[str]:
    """Build common mysql/mysqladmin connection flags."""
    return [
        "--host",
        params.host,
        "--port",
        str(params.port),
        "--user",
        params.user,
        f"--password={params.password}",
        "--protocol=TCP",
        "--default-character-set=utf8mb4",
    ]


def ensure_mysql_tools_available() -> None:
    """Ensure required MySQL client tools are available."""
    for tool_name in ("mysql", "mysqladmin"):
        if shutil.which(tool_name) is None:
            raise FileNotFoundError(
                f"Required MySQL client tool is missing from PATH: {tool_name}"
            )


def check_server_reachable(params: DbConnectionParams) -> None:
    """Verify MySQL server is reachable with provided credentials."""
    ping_cmd = ["mysqladmin", *build_client_args(params), "ping"]
    run_command(ping_cmd)


def create_database(params: DbConnectionParams) -> None:
    """Create target database if it does not already exist."""
    validate_database_name(params.database)
    sql = (
        f"CREATE DATABASE IF NOT EXISTS `{params.database}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )
    create_cmd = ["mysql", *build_client_args(params), "--execute", sql]
    run_command(create_cmd)


def collect_migration_files(migrations_dir: Path) -> list[Path]:
    """Collect migration files in deterministic order."""
    if not migrations_dir.exists() or not migrations_dir.is_dir():
        return []
    return sorted(migrations_dir.glob("*.sql"))


def apply_sql_file(params: DbConnectionParams, sql_path: Path) -> None:
    """Apply SQL schema/migration file to target database."""
    mysql_cmd = ["mysql", *build_client_args(params), params.database]
    with sql_path.open("r", encoding="utf-8") as handle:
        run_command(mysql_cmd, stdin=handle)


def apply_schema(params: DbConnectionParams, schema_path: Path) -> None:
    """Apply SQL schema to target database."""
    apply_sql_file(params, schema_path)


def apply_migrations(params: DbConnectionParams, migrations_dir: Path) -> None:
    """Apply numbered migration files in order."""
    migration_files = collect_migration_files(migrations_dir)
    if not migration_files:
        raise FileNotFoundError(
            f"No migration files found in: {migrations_dir}"
        )

    for migration in migration_files:
        apply_sql_file(params, migration)


def setup_database(
    params: DbConnectionParams,
    schema_path: Path,
    migrations_dir: Path,
) -> SetupResult:
    """Create database and apply schema using MySQL client tools."""
    if not schema_path.exists():
        return SetupResult(
            success=False,
            message=f"Schema file does not exist: {schema_path}",
        )

    try:
        ensure_mysql_tools_available()
        check_server_reachable(params)
        create_database(params)
        migration_files = collect_migration_files(migrations_dir)
        if migration_files:
            apply_migrations(params, migrations_dir)
        else:
            apply_schema(params, schema_path)
    except (FileNotFoundError, ValueError) as exc:
        return SetupResult(success=False, message=str(exc))
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        command = " ".join(exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd)
        details = stderr or stdout or "No additional output."
        return SetupResult(
            success=False,
            message=(
                f"Database setup failed while running '{command}'. "
                f"Output: {details}"
            ),
        )

    return SetupResult(
        success=True,
        message=(
            "Database created successfully and schema applied without errors."
        ),
    )


def resolve_connection_params(args: argparse.Namespace) -> DbConnectionParams:
    """Resolve connection parameters from args and environment variables."""
    database = args.database_name or os.environ.get("DEV_MYSQL_DATABASE")
    host = args.host or os.environ.get("DEV_MYSQL_HOST")
    user = args.user or os.environ.get("DEV_MYSQL_USER")
    password = args.password or os.environ.get("DEV_MYSQL_PASSWORD")
    port_raw = args.port or os.environ.get("DEV_MYSQL_PORT")

    missing_vars: list[str] = []
    if not database:
        missing_vars.append("DEV_MYSQL_DATABASE")
    if not host:
        missing_vars.append("DEV_MYSQL_HOST")
    if not user:
        missing_vars.append("DEV_MYSQL_USER")
    if not password:
        missing_vars.append("DEV_MYSQL_PASSWORD")
    if not port_raw:
        missing_vars.append("DEV_MYSQL_PORT")

    if missing_vars:
        joined = ", ".join(missing_vars)
        raise ValueError(
            "Missing MySQL connection values. Provide CLI flags or set: "
            f"{joined}"
        )

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError("DEV_MYSQL_PORT/--port must be an integer.") from exc

    return DbConnectionParams(
        database=database,
        host=host,
        user=user,
        port=port,
        password=password,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for database setup."""
    parser = argparse.ArgumentParser(
        description="Create MySQL database and apply migrations/schema.",
    )
    parser.add_argument(
        "--database-name",
        help="Target database name. Defaults to DEV_MYSQL_DATABASE.",
    )
    parser.add_argument(
        "--host",
        help="MySQL host. Defaults to DEV_MYSQL_HOST.",
    )
    parser.add_argument(
        "--user",
        help="MySQL user. Defaults to DEV_MYSQL_USER.",
    )
    parser.add_argument(
        "--password",
        help="MySQL password. Defaults to DEV_MYSQL_PASSWORD.",
    )
    parser.add_argument(
        "--port",
        help="MySQL port. Defaults to DEV_MYSQL_PORT.",
    )
    parser.add_argument(
        "--schema-path",
        default="db/schema.sql",
        help="Path to fallback SQL schema file.",
    )
    parser.add_argument(
        "--migrations-dir",
        default="db/migrations",
        help="Path to migration SQL files.",
    )
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    """CLI entrypoint for creating DB and applying schema."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        params = resolve_connection_params(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    schema_path = Path(args.schema_path).resolve()
    migrations_dir = Path(args.migrations_dir).resolve()
    result = setup_database(
        params=params,
        schema_path=schema_path,
        migrations_dir=migrations_dir,
    )
    stream = sys.stdout if result.success else sys.stderr
    print(result.message, file=stream)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(run_cli())
