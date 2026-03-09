# Database Schema Design

Project: `find-me-a-book`  
Workflow: `Database Implementation`  
Task: `TASK_ID=148 / RUN_ID=382`

## 1. Scope and Objectives

This schema supports:

1. Core book catalog storage.
2. User accounts.
3. Reusable user preference filters.

Primary requirement tables are implemented as:

1. `books`
2. `users`
3. `user_filters`

Additional relationship tables normalize authors, genres, and feedback.

## 2. Engine and Conventions

1. Engine: MySQL / MariaDB 11.
2. IDs: `BIGINT UNSIGNED AUTO_INCREMENT`.
3. Character set/collation: `utf8mb4` / `utf8mb4_unicode_ci`.
4. Every table has a primary key.
5. Entity tables include:
   - `created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)`
   - `updated_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)`
6. Integrity rules are enforced through explicit `CHECK`, FK, and unique constraints.

## 3. Schema Layout

Core entities:

1. `users`
2. `books`
3. `user_filters`

Supporting entities:

1. `authors`
2. `genres`
3. `book_authors`
4. `book_genres`
5. `user_filter_genres`
6. `user_filter_authors`
7. `user_book_feedback`

## 4. MySQL-Specific Notes

1. `db/migrations/001_init.sql` is the canonical migration entry point.
2. `db/schema.sql` is kept in sync as a schema snapshot for fallback apply.
3. Partial-unique PostgreSQL behavior was adapted for MySQL:
   - Nullable unique keys for ISBN/provider identifiers.
   - One-default-filter-per-user is enforced via generated column
     `default_user_id` + unique index.
4. FK columns are indexed for join/filter performance.

## 5. Relationships

1. `users (1) -> (N) user_filters`
2. `books (N) <-> (N) authors` via `book_authors`
3. `books (N) <-> (N) genres` via `book_genres`
4. `user_filters (1) -> (N) user_filter_genres`
5. `user_filters (1) -> (N) user_filter_authors`
6. `users (N) <-> (N) books` via `user_book_feedback`

## 6. Setup Flow

Database setup now uses MySQL client tools and environment variables:

1. `DEV_MYSQL_HOST`
2. `DEV_MYSQL_PORT`
3. `DEV_MYSQL_USER`
4. `DEV_MYSQL_PASSWORD`
5. `DEV_MYSQL_DATABASE`

Execution sequence:

1. Validate MySQL tools (`mysql`, `mysqladmin`).
2. Ping server with provided credentials.
3. Create DB with utf8mb4 charset/collation.
4. Apply ordered migrations from `db/migrations/*.sql`.
5. Fallback to `db/schema.sql` if no migration files exist.

## 7. File Map

1. Migration DDL: `db/migrations/001_init.sql`
2. Schema snapshot: `db/schema.sql`
3. Setup implementation: `db/setup_database.py`
4. CLI wrapper: `scripts/setup_database.py`
5. Tests: `tests/test_database_setup.py`
6. Progress/status: `STATUS.md`, `TASK_REPORT.md`
