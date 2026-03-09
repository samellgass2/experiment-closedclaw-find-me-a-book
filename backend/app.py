"""Flask application entrypoint for backend API services."""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify

from .config import AppConfig, load_app_config


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


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

    return app


def main() -> None:
    """Run local development server."""
    app = create_app()
    app.run(host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
