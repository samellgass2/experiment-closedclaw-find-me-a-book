"""Smoke checks for importability in a clean test environment."""

from __future__ import annotations

import importlib


CORE_MODULES: tuple[str, ...] = (
    "config",
    "backend.app",
    "backend.repositories.books",
    "db.setup_database",
    "crawler.goodreads_crawler",
)


def test_core_modules_importable() -> None:
    """Ensure key project modules import without runtime ImportError."""
    for module_name in CORE_MODULES:
        imported = importlib.import_module(module_name)
        assert imported is not None
