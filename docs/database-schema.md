# Database Schema Design: find-me-a-book

## Overview

This document defines the relational schema for the **find-me-a-book** project.
The schema is designed for PostgreSQL 15+ and covers:

- Book catalog and metadata
- User identity and bookshelf state
- User-specific recommendation filters

Primary goals:

- Support fast recommendation filtering against large book catalogs
- Preserve normalized relationships for authors/genres
- Allow flexible user filter presets with safe constraints

---

## Entity Summary

Core required entities from task scope:

- `users`
- `books`
- `filters`

Supporting entities added for integrity and query performance:

- `authors`
- `genres`
- `book_authors`
- `book_genres`
- `user_books`
- `filter_genres`
- `mv_book_search` (materialized view)

---

## High-Level ER Diagram (Text)

```text
users (1) ----< user_books >---- (1) books
  |                                 |
  |                                 +----< book_authors >---- authors
  |
  +----< filters >----< filter_genres >---- genres
                                    ^
books ----< book_genres >-----------+
```

Relationship cardinality:

- A user has many filters.
- A filter can include/exclude many genres.
- A book can have many authors and genres.
- A user can maintain one bookshelf record per book.

---

## Table Specifications

## `users`

Purpose: Stores account and profile identity.

Key columns:

- `user_id` (PK, identity)
- `email` (CITEXT, unique)
- `username` (unique)
- `display_name`
- soft-delete and audit timestamps (`created_at`, `updated_at`, `deleted_at`)

Constraints and behavior:

- `country_code` must be ISO-like 2-letter uppercase when present.
- `birth_year` is bounded (`1900` to current year).
- Partial index on active, non-deleted users.

## `books`

Purpose: Master catalog entries.

Key columns:

- `book_id` (PK, identity)
- ISBN columns (`isbn_10`, `isbn_13`) with format checks
- title metadata
- `publication_date`, `page_count`, `language_code`
- rating metadata (`average_rating`, `ratings_count`)

Constraints and behavior:

- Partial unique indexes on nullable ISBN columns.
- Numeric checks enforce valid rating/page ranges.
- Indexes support sort/filter operations (title, publication date, rating).

## `filters`

Purpose: User-defined recommendation presets.

Key columns:

- `filter_id` (PK, identity)
- `user_id` (FK to `users`)
- Filter bounds (`min/max_publication_year`, `min/max_page_count`, `min_average_rating`)
- inclusion/exclusion arrays (`language_codes`, `allowed_formats`, `excluded_author_ids`, `blocked_maturity_ratings`)
- `sort_by` with controlled values
- `is_default` with one-default-per-user partial unique index

Constraints and behavior:

- Prevents invalid ranges (min > max).
- Supports defaults for common browsing (`language_codes = ['en']`).
- `UNIQUE (user_id, name)` ensures predictable preset naming.

## `authors`

Purpose: Deduplicated author records.

Key columns:

- `author_id` (PK)
- `full_name`
- `normalized_name` (unique)

## `genres`

Purpose: Canonical genre taxonomy.

Key columns:

- `genre_id` (PK)
- `slug` (unique)
- `label` (unique)

## `book_authors`

Purpose: Many-to-many mapping between books and authors.

Key columns:

- `book_id`, `author_id`
- `contribution_order`
- `role` (`author`, `editor`, etc.)

Composite PK includes role to support mixed contribution types.

## `book_genres`

Purpose: Many-to-many mapping between books and genres.

Key columns:

- `book_id`, `genre_id` (composite PK)
- `weight` (0,1] for strength/probability of genre association

## `user_books`

Purpose: User bookshelf and reading progress state.

Key columns:

- `user_id`, `book_id` (composite PK)
- `status` enum (`wishlist`, `reading`, `completed`, `paused`, `dropped`)
- optional rating/review/dates

Used to prevent recommending already-read books unless requested by filter.

## `filter_genres`

Purpose: Explicit include/exclude genre rules per filter.

Key columns:

- `filter_id`, `genre_id`, `match_mode`

`match_mode` is constrained to `include` or `exclude`.

## `mv_book_search`

Purpose: Materialized projection for recommendation search.

Contents:

- One row per book
- denormalized `genre_slugs`
- denormalized `author_names`

Refresh strategy (application/job):

- full refresh after ingestion batches, or
- incremental strategy via trigger + queue (future optimization)

---

## Data Integrity Decisions

- All foreign keys specify delete behavior.
- Nullable unique fields use **partial unique indexes**, not plain unique constraints.
- Domain checks enforce quality close to the data layer.
- Arrays are used only for low-cardinality preference lists (`language_codes`, formats, etc.).
- Genre and author relations remain normalized to preserve analytics flexibility.

---

## Query Patterns Supported

1. User recommendations by filter preset

- Input: `filter_id`
- Filter dimensions:
  - publication year range
  - page count range
  - minimum average rating
  - include/exclude genres
  - included formats/languages
  - excluding read books

2. Search + rank books quickly

- Source: `mv_book_search`
- Sort options mapped from `filters.sort_by`:
  - relevance
  - rating_desc
  - newest
  - oldest
  - title_asc

3. User bookshelf retrieval

- Query: `user_books` by `(user_id, status, updated_at)` index

---

## Future Extensions (Out of Current Scope)

- Multi-tenant support via `tenant_id` columns
- Audit history tables (`*_history`) for preference/version tracking
- Dedicated author and genre exclusion tables replacing ID arrays
- Generated `tsvector` columns for full-text search ranking

---

## Review Checklist

- [x] Includes required tables: `books`, `users`, `filters`
- [x] Documents relations and constraints
- [x] Covers indexing approach for core query paths
- [x] Includes explicit assumptions and extension points

This schema is ready for team review and approval.
