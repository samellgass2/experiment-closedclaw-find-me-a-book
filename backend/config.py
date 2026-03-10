"""Environment-aware runtime configuration for backend Flask app."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ as os_environ
from typing import Mapping

DEFAULT_DB_HOST = "dev-mysql"
DEFAULT_DB_PORT = 3306
DEFAULT_DB_NAME = "dev_find_me_a_book"
DEFAULT_DB_USER = "devagent"
DEFAULT_DB_PASSWORD = ""
DEFAULT_DB_CHARSET = "utf8mb4"
DEFAULT_BOOK_SOURCE_BASE_URL = "https://www.goodreads.com"


def _read_env_string(
    environ: Mapping[str, str],
    primary_name: str,
    *,
    fallback_name: str | None = None,
    default: str,
    allow_blank: bool = False,
) -> str:
    raw_value = environ.get(primary_name)
    if raw_value is None and fallback_name is not None:
        raw_value = environ.get(fallback_name)
    value = raw_value if raw_value is not None else default
    if not allow_blank and value.strip() == "":
        raise ValueError(f"{primary_name} must not be blank.")
    return value


def _read_env_optional_string(
    environ: Mapping[str, str],
    name: str,
) -> str | None:
    raw_value = environ.get(name)
    if raw_value is None:
        return None
    stripped = raw_value.strip()
    if stripped == "":
        return None
    return stripped


def _read_env_int(
    environ: Mapping[str, str],
    primary_name: str,
    *,
    fallback_name: str | None = None,
    default: int,
) -> int:
    raw_value = environ.get(primary_name)
    if raw_value is None and fallback_name is not None:
        raw_value = environ.get(fallback_name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{primary_name} must be an integer.") from exc


def _read_env_bool(
    environ: Mapping[str, str],
    name: str,
    *,
    default: bool,
) -> bool:
    raw_value = environ.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection parameters for backend repository access."""

    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = DEFAULT_DB_CHARSET

    @property
    def as_dict(self) -> dict[str, str | int]:
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
        }


@dataclass(frozen=True)
class ExternalServiceConfig:
    """External API and service configuration used by the backend."""

    book_source_base_url: str
    book_source_api_key: str | None


@dataclass(frozen=True)
class AppConfig:
    """Top-level backend runtime configuration."""

    environment: str
    debug: bool
    log_level: str
    database: DatabaseConfig
    external_services: ExternalServiceConfig


@dataclass(frozen=True)
class BaseEnvironmentConfig:
    """Defaults shared by all Flask environment profiles."""

    name: str
    default_debug: bool
    default_log_level: str

    def load(self, environ: Mapping[str, str]) -> AppConfig:
        database = load_database_config(environ)
        external_services = load_external_service_config(environ)
        debug = _read_env_bool(
            environ,
            "BACKEND_DEBUG",
            default=self.default_debug,
        )
        log_level = _read_env_string(
            environ,
            "BACKEND_LOG_LEVEL",
            fallback_name="LOG_LEVEL",
            default=self.default_log_level,
        ).upper()
        return AppConfig(
            environment=self.name,
            debug=debug,
            log_level=log_level,
            database=database,
            external_services=external_services,
        )


ENVIRONMENT_CONFIGS: dict[str, BaseEnvironmentConfig] = {
    "development": BaseEnvironmentConfig(
        name="development",
        default_debug=False,
        default_log_level="INFO",
    ),
    "test": BaseEnvironmentConfig(
        name="test",
        default_debug=False,
        default_log_level="WARNING",
    ),
    "production": BaseEnvironmentConfig(
        name="production",
        default_debug=False,
        default_log_level="INFO",
    ),
}

ENVIRONMENT_ALIASES: dict[str, str] = {
    "dev": "development",
    "development": "development",
    "test": "test",
    "testing": "test",
    "prod": "production",
    "production": "production",
}


def resolve_environment_name(environ: Mapping[str, str]) -> str:
    """Return canonical environment name from FLASK_ENV."""
    raw_value = environ.get("FLASK_ENV", "development")
    normalized = raw_value.strip().lower()
    if normalized == "":
        normalized = "development"
    try:
        return ENVIRONMENT_ALIASES[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(ENVIRONMENT_CONFIGS.keys()))
        raise ValueError(
            f"FLASK_ENV must be one of: {supported}."
        ) from exc


def load_database_config(environ: Mapping[str, str] | None = None) -> DatabaseConfig:
    """Load DB settings from DB_* variables with DEV_MYSQL_* fallback."""
    env = os_environ if environ is None else environ
    return DatabaseConfig(
        host=_read_env_string(
            env,
            "DB_HOST",
            fallback_name="DEV_MYSQL_HOST",
            default=DEFAULT_DB_HOST,
        ),
        port=_read_env_int(
            env,
            "DB_PORT",
            fallback_name="DEV_MYSQL_PORT",
            default=DEFAULT_DB_PORT,
        ),
        database=_read_env_string(
            env,
            "DB_NAME",
            fallback_name="DEV_MYSQL_DATABASE",
            default=DEFAULT_DB_NAME,
        ),
        user=_read_env_string(
            env,
            "DB_USER",
            fallback_name="DEV_MYSQL_USER",
            default=DEFAULT_DB_USER,
        ),
        password=_read_env_string(
            env,
            "DB_PASSWORD",
            fallback_name="DEV_MYSQL_PASSWORD",
            default=DEFAULT_DB_PASSWORD,
            allow_blank=True,
        ),
        charset=_read_env_string(
            env,
            "DB_CHARSET",
            default=DEFAULT_DB_CHARSET,
        ),
    )


def load_external_service_config(
    environ: Mapping[str, str] | None = None,
) -> ExternalServiceConfig:
    """Load external service API settings used by backend."""
    env = os_environ if environ is None else environ
    return ExternalServiceConfig(
        book_source_base_url=_read_env_string(
            env,
            "BOOK_SOURCE_BASE_URL",
            default=DEFAULT_BOOK_SOURCE_BASE_URL,
        ),
        book_source_api_key=_read_env_optional_string(env, "BOOK_SOURCE_API_KEY"),
    )


def load_app_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    """Load environment-aware Flask application configuration."""
    env = os_environ if environ is None else environ
    environment_name = resolve_environment_name(env)
    environment_config = ENVIRONMENT_CONFIGS[environment_name]
    return environment_config.load(env)
