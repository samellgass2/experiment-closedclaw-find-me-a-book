#!/usr/bin/env python3
"""Mock PostgreSQL verification for database/schema.sql."""

from __future__ import annotations

import re
from pathlib import Path


class MockPostgresClient:
    def __init__(self) -> None:
        self.databases: set[str] = set()
        self.current_db: str | None = None
        self.tables: set[str] = set()
        self.materialized_views: set[str] = set()
        self.types: set[str] = set()
        self.extensions: set[str] = set()
        self.indexes: set[str] = set()

    def create_database(self, name: str) -> None:
        if name in self.databases:
            raise ValueError(f"database already exists: {name}")
        self.databases.add(name)

    def connect(self, name: str) -> None:
        if name not in self.databases:
            raise ValueError(f"database does not exist: {name}")
        self.current_db = name

    def apply_schema(self, sql_text: str) -> None:
        if not self.current_db:
            raise ValueError("no active database connection")

        self.extensions |= set(
            re.findall(r"CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][\w]*)", sql_text, flags=re.IGNORECASE)
        )
        self.types |= set(
            re.findall(r"typname\s*=\s*'([a-zA-Z_][\w]*)'", sql_text, flags=re.IGNORECASE)
        )
        self.tables |= set(
            re.findall(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][\w]*)", sql_text, flags=re.IGNORECASE)
        )
        self.materialized_views |= set(
            re.findall(
                r"CREATE\s+MATERIALIZED\s+VIEW\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][\w]*)",
                sql_text,
                flags=re.IGNORECASE,
            )
        )
        self.indexes |= set(
            re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][\w]*)", sql_text, flags=re.IGNORECASE)
        )


def verify() -> list[str]:
    schema_path = Path("database/schema.sql")
    sql = schema_path.read_text(encoding="utf-8")

    client = MockPostgresClient()
    db_name = "find_me_a_book_task120_mock"

    client.create_database(db_name)
    client.connect(db_name)
    client.apply_schema(sql)

    required_tables = {
        "users",
        "books",
        "filters",
        "authors",
        "genres",
        "book_authors",
        "book_genres",
        "user_books",
        "filter_genres",
    }
    required_types = {"reading_status", "book_format"}
    required_indexes = {
        "uq_books_isbn_10",
        "uq_books_isbn_13",
        "uq_filters_one_default_per_user",
        "uq_mv_book_search_book",
    }

    missing_tables = sorted(required_tables - client.tables)
    missing_types = sorted(required_types - client.types)
    missing_indexes = sorted(required_indexes - client.indexes)
    missing_views = sorted({"mv_book_search"} - client.materialized_views)

    if "citext" not in {e.lower() for e in client.extensions}:
        raise AssertionError("Missing extension: citext")
    if missing_tables:
        raise AssertionError(f"Missing tables: {', '.join(missing_tables)}")
    if missing_types:
        raise AssertionError(f"Missing enum types: {', '.join(missing_types)}")
    if missing_indexes:
        raise AssertionError(f"Missing indexes: {', '.join(missing_indexes)}")
    if missing_views:
        raise AssertionError(f"Missing materialized views: {', '.join(missing_views)}")

    return [
        f"created_database={db_name}",
        "applied_schema=database/schema.sql",
        f"verified_tables={','.join(sorted(required_tables))}",
        "verified_materialized_view=mv_book_search",
        f"verified_indexes={','.join(sorted(required_indexes))}",
        "result=PASS",
    ]


if __name__ == "__main__":
    for line in verify():
        print(line)
