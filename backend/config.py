"""Backend-facing configuration wrappers."""

from __future__ import annotations

from dataclasses import dataclass

import config as runtime_config


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection parameters for backend repository access."""

    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"

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
class AppConfig:
    """Top-level backend runtime configuration."""

    debug: bool
    log_level: str
    database: DatabaseConfig


def load_database_config() -> DatabaseConfig:
    """Load DB settings from the centralized root config module."""
    database_settings = runtime_config.load_database_settings()
    return DatabaseConfig(
        host=database_settings.host,
        port=database_settings.port,
        user=database_settings.user,
        password=database_settings.password,
        database=database_settings.name,
        charset=database_settings.charset,
    )


def load_app_config() -> AppConfig:
    """Load backend app settings from centralized root config."""
    app_settings = runtime_config.load_app_settings()
    return AppConfig(
        debug=app_settings.debug,
        log_level=app_settings.log_level,
        database=load_database_config(),
    )
