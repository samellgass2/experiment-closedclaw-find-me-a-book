"""Create and initialize the PostgreSQL database schema."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DbConnectionParams:
    """Connection parameters used by PostgreSQL client tools."""

    dbname: str
    host: str | None = None
    user: str | None = None
    port: str | None = None


@dataclass(frozen=True)
class SetupResult:
    """Result payload for setup execution."""

    success: bool
    message: str


def parse_connection_string(connection: str) -> dict[str, str]:
    """Parse a PostgreSQL key=value connection string."""
    params: dict[str, str] = {}
    for token in shlex.split(connection):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            params[key] = value
    return params


def build_client_args(params: DbConnectionParams) -> list[str]:
    """Build common psql/createdb connection flags."""
    args: list[str] = []
    if params.host:
        args.extend(["-h", params.host])
    if params.user:
        args.extend(["-U", params.user])
    if params.port:
        args.extend(["-p", params.port])
    return args


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run shell command and return completed process."""
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
    )


def create_database(params: DbConnectionParams) -> None:
    """Create target database if it does not already exist."""
    create_cmd = ["createdb", "--if-not-exists", *build_client_args(params)]
    create_cmd.append(params.dbname)
    run_command(create_cmd)


def apply_schema(params: DbConnectionParams, schema_path: Path) -> None:
    """Apply SQL schema to target database."""
    psql_cmd = [
        "psql",
        *build_client_args(params),
        "-d",
        params.dbname,
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(schema_path),
    ]
    run_command(psql_cmd)


def setup_database(params: DbConnectionParams, schema_path: Path) -> SetupResult:
    """Create database and apply schema using PostgreSQL client tools."""
    if not schema_path.exists():
        return SetupResult(
            success=False,
            message=f"Schema file does not exist: {schema_path}",
        )

    try:
        create_database(params)
        apply_schema(params, schema_path)
    except FileNotFoundError as exc:
        return SetupResult(
            success=False,
            message=f"Required PostgreSQL client tool is missing: {exc}",
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        command = " ".join(exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd)
        details = stderr or stdout or "No additional output."
        return SetupResult(
            success=False,
            message=(
                "Database setup failed while running "
                f"'{command}'. Output: {details}"
            ),
        )

    return SetupResult(
        success=True,
        message=(
            "Database created successfully and schema applied without errors."
        ),
    )


def resolve_connection_params(args: argparse.Namespace) -> DbConnectionParams:
    """Resolve connection parameters from args and optional conn string."""
    conn_params: dict[str, str] = {}
    if args.connection_string:
        conn_params = parse_connection_string(args.connection_string)

    dbname = args.database_name or conn_params.get("dbname", "")
    if not dbname:
        raise ValueError(
            "Database name is required. Use --database-name or include "
            "'dbname=<name>' in --connection-string."
        )

    host = args.host or conn_params.get("host")
    user = args.user or conn_params.get("user")
    port = args.port or conn_params.get("port")
    return DbConnectionParams(dbname=dbname, host=host, user=user, port=port)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for database setup."""
    parser = argparse.ArgumentParser(
        description="Create PostgreSQL database and apply db/schema.sql.",
    )
    parser.add_argument(
        "--database-name",
        help="Target database name. Overrides dbname from connection string.",
    )
    parser.add_argument(
        "--host",
        help="PostgreSQL host. Overrides host from connection string.",
    )
    parser.add_argument(
        "--user",
        help="PostgreSQL user. Overrides user from connection string.",
    )
    parser.add_argument(
        "--port",
        help="PostgreSQL port. Overrides port from connection string.",
    )
    parser.add_argument(
        "--connection-string",
        help=(
            "PostgreSQL key=value string, for example "
            "'host=db.internal user=app dbname=find_me_a_book'."
        ),
    )
    parser.add_argument(
        "--schema-path",
        default="db/schema.sql",
        help="Path to SQL schema file.",
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
    result = setup_database(params=params, schema_path=schema_path)
    stream = sys.stdout if result.success else sys.stderr
    print(result.message, file=stream)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(run_cli())

