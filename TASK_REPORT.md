# Task Report - TASK_ID=367 RUN_ID=645

## Scope
Implement environment-specific Flask backend configuration loading and document
runtime variables/defaults.

## Changes Implemented
- Reworked backend configuration in `backend/config.py` into a clear,
  environment-aware module.
- Added explicit environment profile resolution using `FLASK_ENV` with support
  for:
  - `development` (default)
  - `test`
  - `production`
  - aliases: `dev`, `testing`, `prod`
- Consolidated backend runtime settings into typed dataclasses:
  - `DatabaseConfig`
  - `ExternalServiceConfig`
  - `AppConfig`
- Added env-driven loading for:
  - DB host/port/name/user/password/charset (`DB_*`)
  - debug and log level (`BACKEND_DEBUG`, `BACKEND_LOG_LEVEL`)
  - external API settings (`BOOK_SOURCE_BASE_URL`, `BOOK_SOURCE_API_KEY`)
- Preserved existing development defaults:
  - host `dev-mysql`
  - port `3306`
  - database `dev_find_me_a_book`
  - user `devagent`
- Kept backward-compatible DB fallback behavior to `DEV_MYSQL_*` if `DB_*` is
  unset.
- Updated Flask app factory wiring in `backend/app.py` to use only the backend
  config layer values (no inline environment-specific literals).
- Added root documentation:
  - `CONFIGURATION.md` with all supported env vars, defaults, and
    dev/production usage examples.
- Updated `STATUS.md` with a Task 367 summary and pointer to
  `CONFIGURATION.md`.

## Tests Added/Updated
- Added `tests/test_backend_config.py` covering:
  - default development profile behavior with no env vars
  - `FLASK_ENV` profile selection
  - `DB_*` overrides
  - `DEV_MYSQL_*` fallback behavior
  - invalid `FLASK_ENV` rejection
- Updated existing test fixtures that manually instantiate `AppConfig`:
  - `tests/test_backend_books_api.py`
  - `tests/test_books_api.py`
  - `tests/test_frontend_serving.py`

## Validation Performed
- Ran full test suite:
  - `source .qa-venv/bin/activate && python -m pytest tests/ -q`
  - Result: `90 passed in 8.89s`

## Acceptance Criteria Mapping
1. Single backend configuration module exists with environment-specific loading:
   PASS (`backend/config.py`).
2. Flask initialization uses this module rather than embedded env-specific
   config:
   PASS (`backend/app.py` uses `load_app_config`).
3. No-env run preserves dev defaults (`dev-mysql:3306`, etc.):
   PASS (verified by config defaults/tests).
4. Setting `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
   `FLASK_ENV` changes config without code edits:
   PASS (implemented and tested).
5. `CONFIGURATION.md` documents variables, defaults, and dev/prod examples:
   PASS.
6. `STATUS.md` updated and references configuration docs:
   PASS.

## Files Changed
- `backend/config.py`
- `backend/app.py`
- `tests/test_backend_config.py` (new)
- `tests/test_backend_books_api.py`
- `tests/test_books_api.py`
- `tests/test_frontend_serving.py`
- `CONFIGURATION.md` (new)
- `STATUS.md`
- `TASK_REPORT.md`
