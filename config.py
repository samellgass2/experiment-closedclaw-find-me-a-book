"""Centralized runtime configuration for find-me-a-book."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _read_string(
    primary_name: str,
    *,
    fallback_name: str | None = None,
    default: str,
    allow_blank: bool = False,
) -> str:
    raw_value = os.getenv(primary_name)
    if raw_value is None and fallback_name is not None:
        raw_value = os.getenv(fallback_name)
    value = raw_value if raw_value is not None else default
    if not allow_blank and value.strip() == "":
        raise ValueError(
            f"Environment variable {primary_name} must not be blank."
        )
    return value


def _read_optional_string(
    name: str,
    *,
    fallback_name: str | None = None,
) -> str | None:
    raw_value = os.getenv(name)
    if raw_value is None and fallback_name is not None:
        raw_value = os.getenv(fallback_name)
    if raw_value is None:
        return None
    value = raw_value.strip()
    if value == "":
        return None
    return value


def _read_int(
    primary_name: str,
    *,
    fallback_name: str | None = None,
    default: int,
) -> int:
    raw_value = os.getenv(primary_name)
    if raw_value is None and fallback_name is not None:
        raw_value = os.getenv(fallback_name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {primary_name} must be an integer."
        ) from exc


@dataclass(frozen=True)
class DatabaseSettings:
    """Database connection parameters."""

    host: str
    port: int
    name: str
    user: str
    password: str
    charset: str = "utf8mb4"

    @property
    def as_connection_dict(self) -> dict[str, str | int]:
        """Return mapping compatible with `pymysql.connect`."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.name,
            "charset": self.charset,
        }


@dataclass(frozen=True)
class BookSourceSettings:
    """External book-source provider settings."""

    base_url: str
    api_key: str | None


@dataclass(frozen=True)
class CrawlerSettings:
    """Crawler behavior settings."""

    rate_limit_per_min: int


@dataclass(frozen=True)
class AppSettings:
    """Backend app runtime settings."""

    debug: bool
    log_level: str


def load_database_settings() -> DatabaseSettings:
    """Load DB settings from `DB_*` variables with `DEV_MYSQL_*` fallback."""
    return DatabaseSettings(
        host=_read_string(
            "DB_HOST",
            fallback_name="DEV_MYSQL_HOST",
            default="dev-mysql",
        ),
        port=_read_int(
            "DB_PORT",
            fallback_name="DEV_MYSQL_PORT",
            default=3306,
        ),
        name=_read_string(
            "DB_NAME",
            fallback_name="DEV_MYSQL_DATABASE",
            default="dev_find_me_a_book",
        ),
        user=_read_string(
            "DB_USER",
            fallback_name="DEV_MYSQL_USER",
            default="devagent",
        ),
        password=_read_string(
            "DB_PASSWORD",
            fallback_name="DEV_MYSQL_PASSWORD",
            default="",
            allow_blank=True,
        ),
    )


def load_book_source_settings() -> BookSourceSettings:
    """Load crawler source settings from environment."""
    return BookSourceSettings(
        base_url=_read_string(
            "BOOK_SOURCE_BASE_URL",
            default="https://www.goodreads.com",
        ),
        api_key=_read_optional_string("BOOK_SOURCE_API_KEY"),
    )


def load_crawler_settings() -> CrawlerSettings:
    """Load crawler controls from environment."""
    rate_limit_per_min = _read_int("CRAWLER_RATE_LIMIT_PER_MIN", default=60)
    if rate_limit_per_min <= 0:
        raise ValueError(
            "Environment variable CRAWLER_RATE_LIMIT_PER_MIN must be > 0."
        )
    return CrawlerSettings(rate_limit_per_min=rate_limit_per_min)


def load_app_settings() -> AppSettings:
    """Load backend app settings from environment."""
    debug_value = os.getenv("BACKEND_DEBUG", "false").strip().lower()
    return AppSettings(
        debug=debug_value in {"1", "true", "yes", "on"},
        log_level=os.getenv("BACKEND_LOG_LEVEL", "INFO").upper(),
    )


# Snapshot values for convenient imports in modules that do not need reloads.
_DB_SETTINGS = load_database_settings()
_BOOK_SOURCE_SETTINGS = load_book_source_settings()
_CRAWLER_SETTINGS = load_crawler_settings()

DB_HOST: str = _DB_SETTINGS.host
DB_PORT: int = _DB_SETTINGS.port
DB_NAME: str = _DB_SETTINGS.name
DB_USER: str = _DB_SETTINGS.user
DB_PASSWORD: str = _DB_SETTINGS.password
BOOK_SOURCE_BASE_URL: str = _BOOK_SOURCE_SETTINGS.base_url
BOOK_SOURCE_API_KEY: str | None = _BOOK_SOURCE_SETTINGS.api_key
CRAWLER_RATE_LIMIT_PER_MIN: int = _CRAWLER_SETTINGS.rate_limit_per_min
