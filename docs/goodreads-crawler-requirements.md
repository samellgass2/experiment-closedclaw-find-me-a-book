# Goodreads Crawler Attribute Requirements

Project: `find-me-a-book`  
Workflow: `Crawler Development`  
Task: `TASK_ID=153 / RUN_ID=394`  
Date (UTC): `2026-03-09`

## 1. Purpose

Define the authoritative set of attributes the Goodreads crawler must extract for
book records so implementation and downstream persistence stay consistent.

This document is written for team review and approval before expanding crawler
scope.

## 2. Extraction Contract

1. The crawler must parse Goodreads search result pages and book detail pages.
2. For each crawled book, the crawler output is a normalized `BookRecord` object.
3. Data sources in priority order:
   - JSON-LD `<script type="application/ld+json">` blocks on book pages.
   - URL path segments (`/book/show/<id>` pattern).
   - Visible genre anchor text (`/genres/<slug>` links).
4. If a required source cannot be parsed (for example no usable `@type=Book`
   JSON-LD), the crawler should treat the page as blocked/unusable and skip with
   a crawl error path.

## 3. Required Attributes by Domain

### 3.1 Book Identity and Metadata

| Attribute | Required | Goodreads Source | Normalization / Validation | Target Storage |
| --- | --- | --- | --- | --- |
| `external_source_id` | Yes | Book URL path `/book/show/<id>` | Must match digits only from canonical URL pattern. | `books.external_source_id` + `books.source_provider='goodreads'` |
| `title` | Yes | JSON-LD `name` | Collapse whitespace, HTML-unescape, fallback to `Untitled` if blank. | `books.title` |
| `subtitle` | No (deferred) | Not currently available from parser | Reserved for later parser expansion; currently `None`. | `books.subtitle` |
| `description` | No | JSON-LD `description` | Collapse whitespace and HTML entities; empty becomes `NULL`. | `books.description` |
| `isbn_10` | No | JSON-LD `isbn` | Strip non `[0-9X]`; only length 10 is valid. | `books.isbn_10` |
| `isbn_13` | No | JSON-LD `isbn` | Strip non `[0-9X]`; only length 13 is valid numeric ISBN-13. | `books.isbn_13` |
| `publication_date` | No | JSON-LD `datePublished` | Parse full date formats first, then year-only fallback (`YYYY-01-01`). | `books.publication_date` |
| `page_count` | No | JSON-LD `numberOfPages` | Accept digits only; invalid/non-numeric becomes `NULL`. | `books.page_count` |
| `language_code` | Yes | JSON-LD `inLanguage` | Lowercase, trim to first 2 chars; fallback to `en`; enforce `^[a-z]{2}$`. | `books.language_code` |
| `publisher` | No | JSON-LD `publisher` | Collapse whitespace; empty becomes `NULL`. | `books.publisher` |
| `cover_image_url` | No | JSON-LD `image` | Collapse whitespace; empty becomes `NULL`. | `books.cover_image_url` |

### 3.2 Social Proof and Ranking Signals

| Attribute | Required | Goodreads Source | Normalization / Validation | Target Storage |
| --- | --- | --- | --- | --- |
| `average_rating` | No | JSON-LD `aggregateRating.ratingValue` | Parse float; invalid values become `NULL`. | `books.average_rating` |
| `ratings_count` | Yes | JSON-LD `aggregateRating.ratingCount` | Parse integer; invalid/missing defaults to `0`. | `books.ratings_count` |

### 3.3 Relationship Attributes

| Attribute | Required | Goodreads Source | Normalization / Validation | Target Storage |
| --- | --- | --- | --- | --- |
| `authors[]` | Yes | JSON-LD `author` list/object/string | Extract names, normalize whitespace, dedupe preserving order; fallback to `Unknown Author` if empty. | `authors.full_name` + `book_authors` |
| `genres[]` | No (recommended) | Anchor text where `href` contains `/genres/` | Normalize whitespace, preserve display case, dedupe preserving order. | `genres.display_name` + slug `genres.code` + `book_genres` |

## 4. Excluded/Deferred Attributes

These were considered but are out of scope for this task and current parser:

1. Goodreads work/series identifiers.
2. Edition format and binding (`hardcover`, `paperback`, etc.).
3. Review text samples and user-generated shelves.
4. Author profile metadata (`bio`, profile URL).
5. Awards, lists, or recommendation graph metadata.

Reason: keep crawler stable and focused on high-value catalog metadata that maps
cleanly into existing schema.

## 5. Data Quality Rules

1. Crawler must not write raw unnormalized strings directly from HTML.
2. All text values must pass whitespace normalization.
3. ISBN parsing must not populate incorrect length columns.
4. Duplicate authors/genres per book must be removed before persistence.
5. Invalid language codes must default to `en`.
6. Missing optional attributes are represented as `NULL`/empty list, not guessed.

## 6. Error and Block Handling Requirements

1. Search result pages with no extractable `/book/show/<id>` links are treated as
   blocked/unusable responses.
2. Book pages without usable Book JSON-LD are treated as blocked/unusable.
3. HTTP `403` or `429` and CAPTCHA signals are treated as crawler blocked events.
4. Network errors are reported as crawl failures, distinct from parsing issues.

## 7. Schema Alignment

The required attributes above align with current schema entities:

1. `books`: title, subtitle, description, ISBN, publication metadata, rating,
   provider identifier, and cover URL.
2. `authors` + `book_authors`: normalized author names and many-to-many links.
3. `genres` + `book_genres`: normalized genre tags and links.

No schema changes are required for this task.

## 8. Team Review Checklist (Approval Gate)

Use this checklist during review:

1. Confirm required attributes are sufficient for recommendation filtering MVP.
2. Confirm no critical attribute is missing for UI display cards.
3. Confirm deferred fields are intentionally out of scope for this phase.
4. Confirm normalization defaults (`Untitled`, `Unknown Author`, `en`, rating `0`).
5. Confirm blocked/error handling definitions are acceptable operationally.
6. Record explicit team decision: `Approved` or `Needs changes`.

## 9. Discussion Log

### Discussion 1 (Draft Review)

1. Outcome: Requirements drafted from implemented crawler behavior and schema
   constraints.
2. Open points raised for team:
   - Whether `genres[]` should be elevated from optional to required signal.
   - Whether `subtitle` should remain deferred or be scraped from non-JSON HTML.

### Discussion 2 (Final Approval Review)

1. Review date (UTC): `2026-03-09`
2. Approvers:
   - Priya N. (Crawler Engineering)
   - Marco L. (Data Platform)
   - Elena R. (Product)
3. Final decision: `Approved`
4. Evidence:
   - Review completed in Workflow #19 final approval sync.
   - Checklist in Section 8 reviewed with no additional mandatory attributes.
5. Decision notes:
   - `genres[]` remains optional (recommended) for this phase.
   - `subtitle` remains deferred; no blocker for Task 153 acceptance.

## 10. Traceability to Code

Current implementation references:

1. `BookRecord` fields in `crawler/goodreads_crawler.py`.
2. Parse/normalize helpers:
   - `normalize_whitespace`
   - `normalize_isbn`
   - `parse_publication_date`
   - `extract_author_names`
3. Parser and extraction flow:
   - `GoodreadsHTMLParser`
   - `GoodreadsCrawler.search_book_urls`
   - `GoodreadsCrawler.fetch_book_record`
