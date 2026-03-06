# Database Schema Design

Project: `find-me-a-book`  
Workflow: `Database Implementation`  
Task: `TASK_ID=147 / RUN_ID=234`

## 1. Scope and Objectives

This schema is designed to support:

1. Storage of core book catalog data.
2. Storage of user accounts.
3. Storage of reusable user preference filters used to narrow recommendations and searches.

Acceptance requirements call out `books`, `users`, and `filters`; these are implemented as:

1. `books` for catalog entries.
2. `users` for account and profile metadata.
3. `user_filters` for saved filter configurations.

Supporting tables normalize relationships and preserve data quality.

## 2. Database Engine and Conventions

1. Engine: PostgreSQL 15+.
2. IDs: `BIGSERIAL` primary keys.
3. Time columns: `created_at` and `updated_at` (when mutable).
4. Email handling: `CITEXT` extension for case-insensitive uniqueness.
5. Data integrity: explicit `CHECK` constraints for formats and ranges.
6. Soft business defaults live in table defaults (not app-only logic).

## 3. Entity Model Overview

### Core Entities

1. `users`
2. `books`
3. `user_filters`

### Supporting Entities

1. `authors`
2. `genres`
3. `book_authors` (many-to-many)
4. `book_genres` (many-to-many)
5. `user_filter_genres` (include/exclude genre sets)
6. `user_filter_authors` (include/exclude author sets)
7. `user_book_feedback` (saved/hidden/read/favorite interactions)

## 4. Table-by-Table Specification

### 4.1 users

Purpose: authentication and per-user defaults.

Key columns:

1. `id` PK.
2. `email` unique case-insensitive login identity.
3. `password_hash` for credential verification.
4. `display_name` for UX display.
5. `preferred_language` default language preference.
6. `marketing_opt_in`, `is_active` for account-state controls.

Constraints and indexes:

1. `UNIQUE(email)`.
2. `CHECK` for minimum display name length.
3. `CHECK` for ISO-like two-letter language pattern.
4. `updated_at` trigger maintenance.

### 4.2 books

Purpose: canonical catalog records for recommendation/search.

Key columns:

1. `id` PK.
2. `title`, `subtitle`, `description`.
3. `isbn_10`, `isbn_13` optional unique identifiers.
4. `publication_date`, `page_count`, `publisher`.
5. `language_code`, `maturity_rating`.
6. `average_rating`, `ratings_count`.
7. `source_provider`, `external_source_id` for ingestion lineage.

Constraints and indexes:

1. Partial unique index on `isbn_10` when non-null.
2. Partial unique index on `isbn_13` when non-null.
3. Partial unique index on (`source_provider`, `external_source_id`).
4. Range checks for rating and page count.
5. Indexes for sort/filter hotspots: title, publication date, average rating.
6. `updated_at` trigger maintenance.

### 4.3 user_filters

Purpose: saved user-defined filtering criteria.

Key columns:

1. `id` PK.
2. `user_id` FK to `users`.
3. `filter_name` human-readable label.
4. `is_default` marks preferred default profile.
5. Numeric/range controls: `min_rating`, `max_page_count`, `min_publication_year`, `max_publication_year`.
6. `language_code` and `include_mature` content constraints.
7. Sorting controls: `sort_by`, `sort_direction`.

Constraints and indexes:

1. `CHECK` range/format validations for each configurable field.
2. Year-bound sanity constraints and cross-field min<=max rule.
3. Partial unique index to enforce one default filter per user.
4. `updated_at` trigger maintenance.

### 4.4 authors

Purpose: normalized author records reusable across books and filters.

Key columns:

1. `id` PK.
2. `full_name` unique canonical name.
3. `sort_name` optional alternate ordering value.
4. `bio` optional metadata.

### 4.5 book_authors

Purpose: many-to-many link with ordering and contributor role.

Key columns:

1. Composite PK (`book_id`, `author_id`).
2. `author_order` for display order.
3. `role` for contributor type (`author`, `editor`, etc.).

Deletion behavior:

1. Deleting a book cascades link rows.
2. Deleting an author is restricted if still referenced.

### 4.6 genres

Purpose: controlled genre taxonomy.

Key columns:

1. `id` PK.
2. `code` unique normalized slug.
3. `display_name` unique user-facing label.

### 4.7 book_genres

Purpose: many-to-many mapping between books and genres.

Key columns:

1. Composite PK (`book_id`, `genre_id`).

Deletion behavior:

1. Book deletes cascade to mapping rows.
2. Genre deletes are restricted unless references removed.

### 4.8 user_filter_genres

Purpose: declare include/exclude genre behavior for a given filter.

Key columns:

1. Composite PK (`filter_id`, `genre_id`, `mode`).
2. `mode` in {`include`, `exclude`}.

### 4.9 user_filter_authors

Purpose: declare include/exclude author behavior for a given filter.

Key columns:

1. Composite PK (`filter_id`, `author_id`, `mode`).
2. `mode` in {`include`, `exclude`}.

### 4.10 user_book_feedback

Purpose: optional explicit preference and interaction signal storage.

Key columns:

1. Composite PK (`user_id`, `book_id`).
2. `status` in {`saved`, `hidden`, `read`, `favorite`}.
3. Optional `rating`.

## 5. Relationships

1. `users (1) -> (N) user_filters`
2. `books (N) <-> (N) authors` via `book_authors`
3. `books (N) <-> (N) genres` via `book_genres`
4. `user_filters (1) -> (N) user_filter_genres`
5. `user_filters (1) -> (N) user_filter_authors`
6. `users (N) <-> (N) books` via `user_book_feedback`

## 6. Query and Indexing Strategy

Primary query families expected:

1. Catalog browse sorted by `publication_date` or `average_rating`.
2. Exact lookup by ISBN.
3. User-specific filter retrieval ordered by newest/default.
4. Recommendation filtering with genre/author include-exclude joins.

Indexes are created to support those paths with bounded write overhead.

## 7. Data Integrity and Lifecycle Choices

1. Catalog links (`book_*`) cascade on book delete to avoid orphan rows.
2. Reference dimensions (`authors`, `genres`) are restricted when in use.
3. User-owned structures cascade on user delete for privacy/data minimization.
4. `updated_at` is trigger-managed for consistency across write paths.

## 8. Approval Checklist

The schema in `db/schema.sql` satisfies acceptance criteria:

1. Includes `books` table with book metadata and indexing.
2. Includes `users` table with user account attributes.
3. Includes `user_filters` table as the explicit filter storage model.
4. Provides documentation for all major structures and constraints.

Approval status for task scope: **Ready for review/approval**.

## 9. File Map

1. DDL: `db/schema.sql`
2. Design reference: `docs/database-schema.md`
3. Task progress/status: `STATUS.md`
