#!/usr/bin/env python3
"""Benchmark advanced search filters and relevance ranking.

This script creates an isolated schema, applies all SQL migrations, seeds a
representative dataset, runs timed search queries, and prints EXPLAIN plans.

Usage:
  python scripts/benchmark_search_performance.py
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymysql

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.repositories.books import BookFilterCriteria, BookRepository


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    mean_ms: float
    p95_ms: float
    sample_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark advanced book search query performance.",
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--seed-size", type=int, default=1200)
    parser.add_argument("--budget-ms", type=float, default=350.0)
    parser.add_argument(
        "--keep-schema",
        action="store_true",
        help="Do not drop the temporary benchmark schema.",
    )
    return parser.parse_args()


def read_db_config() -> DbConfig:
    try:
        return DbConfig(
            host=os.environ["DEV_MYSQL_HOST"],
            port=int(os.environ["DEV_MYSQL_PORT"]),
            user=os.environ["DEV_MYSQL_USER"],
            password=os.environ["DEV_MYSQL_PASSWORD"],
        )
    except KeyError as exc:
        raise RuntimeError(
            "Missing DEV_MYSQL_* environment variables for MySQL connection."
        ) from exc


def open_admin_connection(config: DbConfig) -> Any:
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def open_schema_connection(config: DbConfig, schema_name: str) -> Any:
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=schema_name,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def create_schema(config: DbConfig, schema_name: str) -> None:
    with open_admin_connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                (
                    "CREATE DATABASE IF NOT EXISTS `"
                    f"{schema_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )


def drop_schema(config: DbConfig, schema_name: str) -> None:
    with open_admin_connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{schema_name}`")


def apply_migrations(connection: Any) -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No migration files found in {MIGRATIONS_DIR}")

    with connection.cursor() as cursor:
        for migration_path in migration_files:
            raw_sql = migration_path.read_text(encoding="utf-8")
            lines = [
                line
                for line in raw_sql.splitlines()
                if not line.strip().startswith("--")
            ]
            script_without_comments = "\n".join(lines)
            statements = [
                statement.strip()
                for statement in script_without_comments.split(";")
                if statement.strip()
            ]
            for statement in statements:
                cursor.execute(statement)


def seed_dataset(connection: Any, seed_size: int) -> None:
    genre_rows = [
        ("fantasy", "Fantasy"),
        ("science-fiction", "Science Fiction"),
        ("romance", "Romance"),
        ("mystery", "Mystery"),
    ]
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO genres (code, display_name) VALUES (%s, %s)",
            genre_rows,
        )
        cursor.execute("SELECT id, code FROM genres")
        genre_lookup = {str(row["code"]): int(row["id"]) for row in cursor.fetchall()}

        author_values = [(f"Author {index:04d}",) for index in range(seed_size // 4)]
        cursor.executemany(
            "INSERT INTO authors (full_name) VALUES (%s)",
            author_values,
        )
        cursor.execute("SELECT id FROM authors ORDER BY id")
        author_ids = [int(row["id"]) for row in cursor.fetchall()]

        books_to_insert: list[tuple[str, str, str, str]] = []
        for index in range(seed_size):
            if index % 4 == 0:
                genre_code = "fantasy"
                maturity = "general"
                description = (
                    "friendship quest academy allies rival houses and magic "
                    "friendship themes"
                )
            elif index % 4 == 1:
                genre_code = "science-fiction"
                maturity = "teen"
                description = (
                    "academy cadets rivalry planets diplomacy and loyalty"
                )
            elif index % 4 == 2:
                genre_code = "romance"
                maturity = "mature"
                description = (
                    "romance tension desire betrayal second-chance devotion"
                )
            else:
                genre_code = "mystery"
                maturity = "general"
                description = (
                    "detective clues puzzle family secrets and quiet suspense"
                )

            books_to_insert.append(
                (
                    f"Benchmark Book {index:05d} {genre_code}",
                    description,
                    maturity,
                    f"seed-{index:05d}",
                )
            )

        cursor.executemany(
            """
            INSERT INTO books (
                title,
                description,
                maturity_rating,
                source_provider,
                external_source_id
            ) VALUES (%s, %s, %s, 'benchmark', %s)
            """,
            books_to_insert,
        )

        cursor.execute("SELECT id FROM books ORDER BY id")
        book_ids = [int(row["id"]) for row in cursor.fetchall()]

        book_author_rows: list[tuple[int, int, int]] = []
        book_genre_rows: list[tuple[int, int]] = []
        for index, book_id in enumerate(book_ids):
            author_id = author_ids[index % len(author_ids)]
            genre_code = genre_rows[index % 4][0]
            genre_id = genre_lookup[genre_code]
            book_author_rows.append((book_id, author_id, 1))
            book_genre_rows.append((book_id, genre_id))

        cursor.executemany(
            """
            INSERT INTO book_authors (book_id, author_id, author_order)
            VALUES (%s, %s, %s)
            """,
            book_author_rows,
        )
        cursor.executemany(
            "INSERT INTO book_genres (book_id, genre_id) VALUES (%s, %s)",
            book_genre_rows,
        )


def percentile(values: list[float], percent: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of empty values.")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percent
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def benchmark_query(
    repository: BookRepository,
    criteria: BookFilterCriteria,
    *,
    warmup: int,
    iterations: int,
) -> list[float]:
    for _ in range(warmup):
        repository.search(criteria)

    timings_ms: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        repository.search(criteria)
        elapsed = (time.perf_counter() - start) * 1000.0
        timings_ms.append(elapsed)
    return timings_ms


def collect_used_indexes(plan: Any) -> set[str]:
    indexes: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            key_name = node.get("key")
            if isinstance(key_name, str) and key_name:
                indexes.add(key_name)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(plan)
    return indexes


def explain_indexes(
    connection: Any,
    repository: BookRepository,
    criteria: BookFilterCriteria,
) -> set[str]:
    sql, params = repository._build_books_query(criteria=criteria)
    explain_sql = f"EXPLAIN FORMAT=JSON {sql}"
    with connection.cursor() as cursor:
        cursor.execute(explain_sql, params)
        row = cursor.fetchone()
    if not row:
        return set()

    explain_text = row.get("EXPLAIN")
    if not explain_text:
        first_value = next(iter(row.values()))
        explain_text = str(first_value)

    plan = json.loads(str(explain_text))
    return collect_used_indexes(plan)


def main() -> int:
    args = parse_args()
    config = read_db_config()
    schema_name = f"dev_find_me_a_book_task273_perf_{int(time.time() * 1000)}"[:64]

    create_schema(config, schema_name)

    query_definitions = [
        (
            "fantasy-low-spice",
            BookFilterCriteria(
                query="friendship quest",
                genre="fantasy",
                spice_level="low",
                subject_matter=("friendship",),
                plot_points=("quest",),
                age_min=8,
                age_max=17,
            ),
        ),
        (
            "scifi-teen",
            BookFilterCriteria(
                query="academy rivalry",
                genre="science-fiction",
                age_rating="teen",
                subject_matter=("academy",),
                character_dynamics=("rivalry",),
                age_min=13,
                age_max=17,
            ),
        ),
        (
            "romance-high",
            BookFilterCriteria(
                query="romance desire",
                genre="romance",
                spice_level="high",
                subject_matter=("betrayal",),
            ),
        ),
        (
            "browse-mystery",
            BookFilterCriteria(
                query=None,
                genre="mystery",
                age_min=10,
                age_max=30,
            ),
        ),
    ]

    try:
        with open_schema_connection(config, schema_name) as connection:
            apply_migrations(connection)
            seed_dataset(connection, args.seed_size)

            repository = BookRepository(connection=connection)
            results: list[BenchmarkResult] = []

            print(
                f"Benchmark schema={schema_name} seed_size={args.seed_size} "
                f"iterations={args.iterations}"
            )
            print("-" * 80)

            for name, criteria in query_definitions:
                timings = benchmark_query(
                    repository,
                    criteria,
                    warmup=args.warmup,
                    iterations=args.iterations,
                )
                mean_ms = statistics.fmean(timings)
                p95_ms = percentile(timings, 0.95)
                results.append(
                    BenchmarkResult(
                        name=name,
                        mean_ms=mean_ms,
                        p95_ms=p95_ms,
                        sample_count=len(timings),
                    )
                )
                used_indexes = sorted(explain_indexes(connection, repository, criteria))
                indexes_text = ", ".join(used_indexes) if used_indexes else "(none)"
                print(
                    f"{name:20s} mean={mean_ms:7.2f}ms "
                    f"p95={p95_ms:7.2f}ms indexes={indexes_text}"
                )

            print("-" * 80)
            failures = [
                result
                for result in results
                if result.p95_ms > args.budget_ms
            ]
            if failures:
                print(f"Budget check failed (> {args.budget_ms:.2f}ms p95):")
                for failure in failures:
                    print(
                        f"  {failure.name}: p95={failure.p95_ms:.2f}ms "
                        f"(mean={failure.mean_ms:.2f}ms)"
                    )
                return 1

            print(
                "All benchmark queries passed budget check "
                f"(p95 <= {args.budget_ms:.2f}ms)."
            )
            return 0
    finally:
        if args.keep_schema:
            print(f"Keeping benchmark schema: {schema_name}")
        else:
            drop_schema(config, schema_name)


if __name__ == "__main__":
    raise SystemExit(main())
