"""Flask application entrypoint for backend API services."""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import pymysql
from flask import (
    Flask,
    abort,
    g,
    got_request_exception,
    jsonify,
    request,
    send_from_directory,
)
from flask.wrappers import Response

from .config import AppConfig, load_app_config
from .repositories.books import (
    AGE_RATING_ALIASES,
    BookFilterCriteria,
    BookQueryTimeoutError,
    BookRepositoryError,
    search_books_by_criteria,
)

MAX_QUERY_LENGTH = 200
MAX_FILTER_VALUE_LENGTH = 80
MIN_SUPPORTED_AGE = 0
MAX_SUPPORTED_AGE = 120
SUPPORTED_SPICE_LEVELS = frozenset({"low", "medium", "high"})
MAX_LIST_FILTER_TERMS = 10
HEALTHCHECK_CONNECT_TIMEOUT_SECONDS = 2
HEALTHCHECK_QUERY_TIMEOUT_SECONDS = 2
STANDARD_LOG_RECORD_FIELDS = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
)


@dataclass(frozen=True)
class HealthProbeResult:
    """Result payload for database and migration metadata probes."""

    db_connected: bool
    migration_version: str | None


class JsonLogFormatter(logging.Formatter):
    """Formatter that emits one-line JSON log records."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"), default=str)


def _configure_logging(log_level: str) -> None:
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(numeric_level)
    stream_handler.setFormatter(JsonLogFormatter())

    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)


def _open_healthcheck_connection(database_config: Mapping[str, Any]) -> Any:
    return pymysql.connect(
        host=str(database_config["host"]),
        port=int(database_config["port"]),
        user=str(database_config["user"]),
        password=str(database_config["password"]),
        database=str(database_config["database"]),
        charset=str(database_config.get("charset", "utf8mb4")),
        autocommit=True,
        connect_timeout=HEALTHCHECK_CONNECT_TIMEOUT_SECONDS,
        read_timeout=HEALTHCHECK_QUERY_TIMEOUT_SECONDS,
        write_timeout=HEALTHCHECK_QUERY_TIMEOUT_SECONDS,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _load_migration_version(cursor: Any) -> str | None:
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
          AND table_name IN ('alembic_version', 'schema_migrations')
        """
    )
    rows = cursor.fetchall()
    table_names = {str(row["table_name"]) for row in rows}

    if "alembic_version" in table_names:
        cursor.execute("SELECT version_num FROM alembic_version LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            return None
        version = row.get("version_num")
        return str(version) if version is not None else None

    if "schema_migrations" in table_names:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'schema_migrations'
              AND column_name IN ('version_num', 'version')
            ORDER BY FIELD(column_name, 'version_num', 'version')
            LIMIT 1
            """
        )
        column_row = cursor.fetchone()
        if column_row is None:
            return None

        column_name = str(column_row["column_name"])
        cursor.execute(
            f"SELECT `{column_name}` AS migration_version "
            "FROM schema_migrations "
            f"ORDER BY `{column_name}` DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            return None
        version = row.get("migration_version")
        return str(version) if version is not None else None

    return None


def _run_health_probe(database_config: Mapping[str, Any]) -> HealthProbeResult:
    connection: Any = None
    try:
        connection = _open_healthcheck_connection(database_config)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS db_ok")
            cursor.fetchone()
            migration_version = _load_migration_version(cursor)
        return HealthProbeResult(
            db_connected=True,
            migration_version=migration_version,
        )
    except pymysql.MySQLError:
        return HealthProbeResult(
            db_connected=False,
            migration_version=None,
        )
    finally:
        if connection is not None:
            connection.close()


def _invalid_parameter_response(message: str) -> tuple[Any, int]:
    return (
        jsonify(
            {
                "error": "invalid_parameter",
                "message": message,
            }
        ),
        400,
    )


def _parse_single_query_param(
    name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str | None, str | None]:
    values = request.args.getlist(name)
    if len(values) > 1:
        return None, f"Use a single {name} query parameter value."
    if not values:
        return None, None
    trimmed = values[0].strip()
    if not trimmed:
        if allow_empty:
            return None, None
        return None, f"{name} cannot be empty."
    return trimmed, None


def _parse_list_query_param(
    name: str,
) -> tuple[tuple[str, ...], str | None]:
    values = request.args.getlist(name)
    if not values:
        return tuple(), None

    parsed_values: list[str] = []
    for raw_value in values:
        for token in raw_value.split(","):
            trimmed = token.strip()
            if not trimmed:
                continue
            if len(trimmed) > MAX_FILTER_VALUE_LENGTH:
                return (
                    tuple(),
                    (
                        f"{name} values must be "
                        f"{MAX_FILTER_VALUE_LENGTH} characters or fewer."
                    ),
                )
            parsed_values.append(trimmed)

    if len(parsed_values) > MAX_LIST_FILTER_TERMS:
        return (
            tuple(),
            f"{name} supports at most {MAX_LIST_FILTER_TERMS} values.",
        )
    return tuple(parsed_values), None


def _parse_age_filter(name: str) -> tuple[int | None, str | None]:
    raw_value, error = _parse_single_query_param(name)
    if error is not None:
        return None, error
    if raw_value is None:
        return None, None
    try:
        numeric_value = int(raw_value)
    except ValueError:
        return None, f"{name} must be an integer."
    if numeric_value < MIN_SUPPORTED_AGE or numeric_value > MAX_SUPPORTED_AGE:
        return (
            None,
            (
                f"{name} must be between {MIN_SUPPORTED_AGE} and "
                f"{MAX_SUPPORTED_AGE}."
            ),
        )
    return numeric_value, None


def create_app(config: AppConfig | None = None) -> Flask:
    """Build and configure the Flask app instance."""
    runtime_config = config or load_app_config()
    _configure_logging(runtime_config.log_level)

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"

    app = Flask(__name__)
    app.config["DEBUG"] = runtime_config.debug
    app.config["ENV"] = runtime_config.environment
    app.config["LOG_LEVEL"] = runtime_config.log_level
    app.config["DATABASE_CONFIG"] = runtime_config.database.as_dict
    app.config["BOOK_SOURCE_BASE_URL"] = (
        runtime_config.external_services.book_source_base_url
    )
    app.config["BOOK_SOURCE_API_KEY"] = (
        runtime_config.external_services.book_source_api_key
    )

    logger = logging.getLogger("backend.app")
    logger.info(
        "Initialized backend app.",
        extra={
            "event": "startup",
            "db_host": runtime_config.database.host,
            "environment": runtime_config.environment,
            "log_level": runtime_config.log_level,
        },
    )

    @app.before_request
    def track_request_start() -> None:
        g.request_start_time = time.perf_counter()

    @app.after_request
    def log_request(response: Response) -> Response:
        request_start_time = getattr(g, "request_start_time", None)
        duration_ms: float | None = None
        if request_start_time is not None:
            duration_ms = round(
                (time.perf_counter() - request_start_time) * 1000,
                2,
            )

        logger.info(
            "HTTP request completed.",
            extra={
                "event": "http_request",
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    def _log_unhandled_exception(
        sender: Flask,
        exception: BaseException,
        **kwargs: Any,
    ) -> None:
        del sender
        del kwargs
        logger.exception(
            "Unhandled exception during request.",
            extra={
                "event": "unhandled_exception",
                "method": request.method,
                "path": request.path,
                "exception_type": exception.__class__.__name__,
            },
        )

    got_request_exception.connect(_log_unhandled_exception, app)

    @app.get("/health")
    def health() -> tuple[Response, int]:
        probe = _run_health_probe(app.config["DATABASE_CONFIG"])
        payload = {
            "status": "ok" if probe.db_connected else "degraded",
            "service": "find-me-a-book-backend",
            "database": {
                "status": "up" if probe.db_connected else "down",
            },
            "migration_version": probe.migration_version,
            "migration_status": (
                "available"
                if probe.migration_version is not None
                else "unknown"
            ),
        }
        return jsonify(payload), 200

    @app.get("/ready")
    def ready() -> tuple[Response, int]:
        probe = _run_health_probe(app.config["DATABASE_CONFIG"])
        if probe.db_connected:
            return jsonify({"status": "ready", "database": "up"}), 200
        return jsonify({"status": "not_ready", "database": "down"}), 503

    @app.get("/")
    def index() -> Any:
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/<path:asset_path>")
    def frontend_asset(asset_path: str) -> Any:
        if asset_path.startswith("api/") and asset_path != "api/books.js":
            abort(404)
        return send_from_directory(frontend_dir, asset_path)

    @app.get("/api/books")
    @app.get("/api/books/search")
    @app.get("/search")
    def get_books() -> tuple[Any, int]:
        q_raw, q_error = _parse_single_query_param("q", allow_empty=True)
        if q_error is not None:
            return _invalid_parameter_response(q_error)
        query: str | None = None
        if q_raw is not None:
            if len(q_raw) > MAX_QUERY_LENGTH:
                return _invalid_parameter_response(
                    f"q must be {MAX_QUERY_LENGTH} characters or fewer."
                )
            query = q_raw

        genre, genre_error = _parse_single_query_param("genre")
        if genre_error is not None:
            return _invalid_parameter_response(genre_error)
        if genre is not None and len(genre) > MAX_FILTER_VALUE_LENGTH:
            return _invalid_parameter_response(
                f"genre must be {MAX_FILTER_VALUE_LENGTH} characters or fewer."
            )

        age_rating, age_rating_error = _parse_single_query_param("age_rating")
        if age_rating_error is not None:
            return _invalid_parameter_response(age_rating_error)
        normalized_age_rating: str | None = None
        if age_rating is not None:
            normalized_age_rating = AGE_RATING_ALIASES.get(age_rating.lower())
            if normalized_age_rating is None:
                supported = ", ".join(sorted(AGE_RATING_ALIASES.keys()))
                return _invalid_parameter_response(
                    f"age_rating must be one of: {supported}."
                )

        spice_level, spice_error = _parse_single_query_param("spice_level")
        if spice_error is not None:
            return _invalid_parameter_response(spice_error)
        if spice_level is not None:
            normalized_spice_level = spice_level.lower()
            if normalized_spice_level not in SUPPORTED_SPICE_LEVELS:
                supported_text = ", ".join(sorted(SUPPORTED_SPICE_LEVELS))
                return _invalid_parameter_response(
                    (
                        "spice_level must be one of: "
                        f"{supported_text}."
                    )
                )
            spice_level = normalized_spice_level

        age_min, age_min_error = _parse_age_filter("age_min")
        if age_min_error is not None:
            return _invalid_parameter_response(age_min_error)

        age_max, age_max_error = _parse_age_filter("age_max")
        if age_max_error is not None:
            return _invalid_parameter_response(age_max_error)

        if age_min is not None and age_max is not None and age_min > age_max:
            return _invalid_parameter_response(
                "age_min cannot be greater than age_max."
            )

        subject, subject_error = _parse_single_query_param("subject")
        if subject_error is not None:
            return _invalid_parameter_response(subject_error)
        if subject is not None and len(subject) > MAX_FILTER_VALUE_LENGTH:
            return _invalid_parameter_response(
                f"subject must be {MAX_FILTER_VALUE_LENGTH} characters or fewer."
            )

        subject_matter, subject_matter_error = _parse_list_query_param(
            "subject_matter"
        )
        if subject_matter_error is not None:
            return _invalid_parameter_response(subject_matter_error)
        if not subject_matter and subject is not None:
            subject_matter = (subject,)

        plot_points, plot_points_error = _parse_list_query_param("plot_points")
        if plot_points_error is not None:
            return _invalid_parameter_response(plot_points_error)

        character_dynamics, character_dynamics_error = _parse_list_query_param(
            "character_dynamics"
        )
        if character_dynamics_error is not None:
            return _invalid_parameter_response(character_dynamics_error)

        legacy_route_has_filters = any(
            (
                genre is not None,
                normalized_age_rating is not None,
                bool(subject_matter),
                bool(plot_points),
                bool(character_dynamics),
                spice_level is not None,
                age_min is not None,
                age_max is not None,
            )
        )
        strict_legacy_intersection = (
            request.path == "/api/books"
            and query is None
            and legacy_route_has_filters
        )

        criteria = BookFilterCriteria(
            query=query,
            genre=genre,
            age_rating=normalized_age_rating,
            subject_matter=subject_matter,
            plot_points=plot_points,
            character_dynamics=character_dynamics,
            spice_level=spice_level,
            age_min=age_min,
            age_max=age_max,
        )

        try:
            books = search_books_by_criteria(
                app.config["DATABASE_CONFIG"],
                criteria=criteria,
            )
        except BookQueryTimeoutError:
            logger.exception("Book search timed out.")
            return (
                jsonify(
                    {
                        "error": "search_timeout",
                        "message": "Search timed out. Please narrow your query.",
                    }
                ),
                504,
            )
        except BookRepositoryError:
            logger.exception("Failed to fetch books from repository.")
            return (
                jsonify(
                    {
                        "error": "database_unavailable",
                        "message": "Unable to fetch books at this time.",
                    }
                ),
                500,
            )

        if strict_legacy_intersection and books:
            books = [min(books, key=lambda book: int(book["id"]))]

        return jsonify(books), 200

    return app


def main() -> None:
    """Run local development server."""
    app = create_app()
    app.run(host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
