# Testing Strategy: find-me-a-book

## Purpose
Define a stable, repo-specific testing approach for search/filter behavior,
MySQL query integration, and Goodreads crawler data quality.

## In-Scope Components (Audit-Based)
- `backend/repositories/books.py`
  - `BookRepository`
  - `BookFilterCriteria`
  - `_build_books_query`, `_query_books`, `_to_boolean_prefix_query`, `_is_timeout_error`
  - `search_books_by_criteria` / connection wrapper behavior
- `backend/app.py`
  - query parameter parsing/validation (`q`, `genre`, `age_rating`,
    `subject_matter`, `plot_points`, `character_dynamics`, `spice_level`,
    `age_min`, `age_max`)
  - `/api/books`, `/api/books/search`, `/search` routing and error mapping
- `db/setup_database.py`
  - `resolve_connection_params`, `build_client_args`, `apply_migrations`,
    `validate_setup`, `setup_database`
- `db/migrations/001_init.sql`, `db/migrations/002_search_indexes.sql`
  - schema and search/index guarantees used by query logic
- `crawler/goodreads_crawler.py`
  - `GoodreadsCrawler` parse/retry/block handling
  - `MySQLBookRepository.upsert_book`
  - parsing helpers (`parse_publication_date`, `normalize_isbn`,
    `extract_author_names`, `slugify_genre`, `resolve_mysql_config`)

## Test Tooling and Execution
- Canonical tool: `pytest`, executed via `python -m pytest`.
- DB-backed tests use MySQL via `DEV_MYSQL_*` environment variables.

Recommended local commands (repo root):
```bash
python --version
python -m pip install -r requirements.txt
python -m pytest
```

Database bootstrap before running MySQL integration modules in a clean env:
```bash
export DEV_MYSQL_HOST=dev-mysql
export DEV_MYSQL_PORT=3306
export DEV_MYSQL_USER=devagent
export DEV_MYSQL_PASSWORD=...
export DEV_MYSQL_DATABASE=dev_find_me_a_book
python db/setup_database.py
```

Focused filtering integration run:
```bash
python -m pytest tests/test_integration_filtering.py -q
```

Performance + security smoke run:
```bash
export DEV_MYSQL_HOST=dev-mysql
export DEV_MYSQL_PORT=3306
export DEV_MYSQL_USER=devagent
export DEV_MYSQL_PASSWORD=...
python -m pytest tests/test_performance_security_smoke.py -q
python scripts/benchmark_search_performance.py --seed-size 1200 --warmup 2 --iterations 8 --budget-ms 400
```

## Test Directory Conventions
- Keep all tests under `tests/`.
- Naming:
  - files: `test_<area>.py`
  - classes: `<Area>Tests`
  - methods: `test_<behavior>`
- Mark DB/network-dependent coverage as integration using environment-gated
  skip conditions (pattern already used in `tests/test_books_api.py`,
  `tests/test_relevance_ranking.py`, `tests/test_crawler_mysql_integration.py`).
- Maintain clear separation:
  - pure unit tests with fakes/mocks for SQL generation and parser logic
  - integration tests for real MySQL schema/index/query behavior

## Coverage Plan by Layer

### 1) Unit Tests
Target modules:
- `tests/test_books_repository_filters.py`
- `tests/test_backend_books_api.py`
- `tests/test_goodreads_crawler.py`
- `tests/test_database_setup.py`

Critical behaviors:
- Search/filter SQL is parameterized (no raw user-value interpolation), and
  criteria combine with logical AND where expected.
- Relevance expression includes weighted query, genre, age, subject,
  plot-point, and character-dynamics contributions.
- API validation rejects malformed/unsupported filters with `400` payloads and
  maps repository failures to `500`/`504`.
- Crawler HTML/JSON-LD parsing normalizes titles, authors, genres, dates,
  ISBNs, and language safely.
- DB setup command building and environment resolution fail safely on invalid
  input or missing values.

### 2) Integration Tests (Database + Query Layer)
Target modules:
- `tests/test_books_api.py`
- `tests/test_relevance_ranking.py`
- `tests/test_mysql_setup_validation.py`
- `tests/test_integration_filtering.py`

Critical behaviors:
- Migrations create required schema and search indexes used by repository SQL.
- `BookRepository.search` ranking order is stable for stronger vs weaker
  matches across query + filter combinations.
- API endpoint behavior reflects repository filtering contracts in real MySQL
  (including legacy `/api/books` behavior and strict intersections).
- Setup validation verifies DB connectivity, active schema, and required table
  presence.
- Filtering integration coverage seeds crawler-like rows (`source_provider`,
  `external_source_id`, `description`, `maturity_rating`, and linked genres)
  and validates that genre, age, spice-level, subject, and combined criteria
  return exact expected subsets through repository query paths.

### 3) Crawler Validation (Parser + Persistence)
Target modules:
- `tests/test_goodreads_crawler.py`
- `tests/test_crawler_mysql_integration.py`

Critical behaviors:
- Goodreads search result parsing deduplicates canonical book URLs.
- Book detail extraction requires usable JSON-LD and handles blocked/captcha
  paths as explicit crawler errors.
- `MySQLBookRepository.upsert_book` correctly inserts/updates book rows and
  preserves normalized author/genre link integrity without duplicates.
- Persisted crawler fields (`source_provider`, `external_source_id`,
  ratings/date/page count/language) are validated against DB rows.

### 4) Future API/Frontend Contract Tests
Planned scope (next phase):
- API contract tests for response shape/versioning around advanced filters.
- Frontend integration tests validating query-string generation and handling of
  timeout/database error payloads.
- Optional end-to-end smoke path: frontend search UI -> backend API -> MySQL
  seeded fixture data.

## Performance and Security Smoke Checks
Minimum recurring smoke checks (CI or scheduled local run):
- Performance:
  - Run `python -m pytest tests/test_performance_security_smoke.py -q`.
    - `SearchPerformanceSmokeTests` creates an isolated MySQL schema, seeds
      1200 books, and runs representative query/filter scenarios.
    - Each scenario asserts a p95 wall-clock budget:
      - `query-genre-subject-spice`: `<= 450ms`
      - `query-age-rating-character`: `<= 450ms`
      - `browse-filter-only`: `<= 300ms`
  - Run `python scripts/benchmark_search_performance.py --seed-size 1200 --warmup 2 --iterations 8 --budget-ms 400`.
    - Validates p95 latency with explicit budget gating.
    - Emits index usage from `EXPLAIN FORMAT=JSON` for trend tracking.
- Security:
  - `RepositorySecuritySmokeTests` (in
    `tests/test_performance_security_smoke.py`) verifies:
    - untrusted values are not interpolated into SQL text,
    - SQL placeholder count matches supplied params,
    - query execution sends a parameter tuple to the DB driver,
    - AST-based static guard fails if `_build_books_query` interpolates
      user-input variables via f-strings.
  - `ConfigSecretSmokeTests` scans strategy/example config files to fail if
    concrete `DEV_MYSQL_PASSWORD` values are committed.
  - Existing API validation and crawler-fail-closed checks remain covered by:
    `tests/test_backend_books_api.py` and
    `tests/test_crawler_validation_smoke.py`.

## Suggested Test Matrix per Change Type
- Query/filter logic changes (`backend/repositories/books.py`):
  - run `python -m pytest tests/test_books_repository_filters.py tests/test_relevance_ranking.py tests/test_books_api.py -q`.
- API parsing/routing changes (`backend/app.py`):
  - run `python -m pytest tests/test_backend_books_api.py tests/test_books_api.py -q`.
- Crawler/parser/persistence changes (`crawler/goodreads_crawler.py`):
  - run `python -m pytest tests/test_goodreads_crawler.py tests/test_crawler_mysql_integration.py -q`.
- DB setup or migration changes (`db/setup_database.py`, `db/migrations/*`):
  - run `python -m pytest tests/test_database_setup.py tests/test_mysql_setup_validation.py -q` and impacted integration tests.

## Exit Criteria for QA Stabilization
- Unit tests pass in local/dev-runner environment.
- Integration tests pass when `DEV_MYSQL_*` variables are present.
- No regressions in search relevance ordering, filter intersection behavior,
  crawler upsert integrity, and setup validation.
- Performance and security smoke checks complete without critical findings.
