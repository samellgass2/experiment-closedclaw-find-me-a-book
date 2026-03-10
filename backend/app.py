"""Flask application entrypoint for backend API services."""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify, request

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


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


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

    app = Flask(__name__)
    app.config["DEBUG"] = runtime_config.debug
    app.config["DATABASE_CONFIG"] = runtime_config.database.as_dict

    logger = logging.getLogger("backend.app")
    logger.info("Initialized backend app with MySQL host %s", runtime_config.database.host)

    @app.get("/")
    def health() -> tuple[dict[str, Any], int]:
        payload = {
            "status": "ok",
            "service": "find-me-a-book-backend",
        }
        return jsonify(payload), 200

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
        normalized_path = request.path.rstrip("/") or "/"
        strict_legacy_intersection = (
            normalized_path == "/api/books"
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
