"""Runtime configuration for backend services."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _read_string(
    name: str,
    *,
    default: str | None = None,
    allow_blank: bool = False,
) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    if not allow_blank and value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _read_int(name: str, *, default: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        if default is None:
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer."
        ) from exc


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection parameters for MySQL-compatible services."""

    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"

    @property
    def as_dict(self) -> dict[str, str | int]:
        """Expose params in mapping form for driver initialization."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
        }


@dataclass(frozen=True)
class AppConfig:
    """Top-level app runtime configuration."""

    debug: bool
    log_level: str
    database: DatabaseConfig


def load_database_config() -> DatabaseConfig:
    """Load database config from the existing DEV_MYSQL_* environment keys."""
    return DatabaseConfig(
        host=_read_string("DEV_MYSQL_HOST", default="localhost"),
        port=_read_int("DEV_MYSQL_PORT", default=3306),
        user=_read_string("DEV_MYSQL_USER", default="root"),
        password=_read_string(
            "DEV_MYSQL_PASSWORD",
            default="",
            allow_blank=True,
        ),
        database=_read_string("DEV_MYSQL_DATABASE", default="dev_find_me_a_book"),
    )


def load_app_config() -> AppConfig:
    """Load app config and nested database config from environment."""
    debug_value = os.getenv("BACKEND_DEBUG", "false").strip().lower()
    return AppConfig(
        debug=debug_value in {"1", "true", "yes", "on"},
        log_level=os.getenv("BACKEND_LOG_LEVEL", "INFO").upper(),
        database=load_database_config(),
    )
