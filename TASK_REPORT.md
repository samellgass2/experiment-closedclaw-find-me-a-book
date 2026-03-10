# TASK REPORT

## Task
- TASK_ID: 347
- RUN_ID: 630
- Title: Introduce centralized configuration module

## Summary of Work
- Added root-level `config.py` as the centralized runtime configuration module.
- Implemented typed settings dataclasses and loaders for:
  - Database: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - Book source: `BOOK_SOURCE_BASE_URL`, `BOOK_SOURCE_API_KEY`
  - Crawler: `CRAWLER_RATE_LIMIT_PER_MIN`
- Added sensible local defaults aligned to this dev environment:
  - `DB_HOST=dev-mysql`, `DB_PORT=3306`, `DB_NAME=dev_find_me_a_book`, `DB_USER=devagent`, `DB_PASSWORD=''`
  - `BOOK_SOURCE_BASE_URL=https://www.goodreads.com`, `BOOK_SOURCE_API_KEY=None`, `CRAWLER_RATE_LIMIT_PER_MIN=60`
- Preserved compatibility by allowing `DEV_MYSQL_*` as fallback inputs behind `DB_*`.
- Refactored modules to consume centralized config instead of direct env access/hardcoded runtime values:
  - `backend/config.py`
  - `crawler/goodreads_crawler.py`
  - `db/setup_database.py`
  - `scripts/benchmark_search_performance.py`
- Added `tests/test_root_config.py` to verify root config importability and env/default behavior.
- Updated `STATUS.md` with Task 347 documentation, env variable matrix/defaults, and dev-mysql/dev DB relationship guidance.

## Acceptance Coverage
1. `config.py` exists at repo root and is importable (`import config`).
2. `config.py` defines required DB/book-source/crawler settings via env variables with documented defaults.
3. No production credentials or production-only hostnames were introduced; defaults are local/dev-safe.
4. Existing runtime code previously hardcoding/reading DB or source config directly now imports centralized config.
5. `STATUS.md` documents the configuration module, supported variables/defaults, and how they map to `dev-mysql` + `dev_find_me_a_book`.

## Validation / Test Execution
Commands run:
1. `python -m pytest tests/ -q`
2. `python -m unittest discover -s tests -p 'test*.py'`

Observed results:
- `python -m pytest tests/ -q`: FAIL in environment (`No module named pytest`)
- `python -m unittest discover -s tests -p 'test*.py'`: PASS (`Ran 84 tests`, `OK`, `skipped=23`)

## Files Changed
- `config.py`
- `backend/config.py`
- `crawler/goodreads_crawler.py`
- `db/setup_database.py`
- `scripts/benchmark_search_performance.py`
- `tests/test_database_setup.py`
- `tests/test_goodreads_crawler.py`
- `tests/test_root_config.py`
- `STATUS.md`
- `TASK_REPORT.md`

## Workflow 35 Follow-up (Bug: frontend entrypoint on :8000)
- Updated backend routing so `/` serves `frontend/index.html`.
- Added `/health` for backend health JSON previously returned by `/`.
- Added static asset route support from `frontend/` so app files load at root origin.
- Added focused tests in `tests/test_frontend_serving.py` for:
  - `/` returning HTML with `#search-input`
  - `/api/books.js` frontend module availability
- Ran browser acceptance with Playwright Chromium against `http://localhost:8000`:
  - Verified `#search-input`, `#filters-form`, and Search button render.

### Workflow 35 Validation
Commands run:
1. `python -m pytest tests/ -q`
2. `python -m pytest tests/test_performance_security_smoke.py::SearchPerformanceSmokeTests::test_representative_filter_queries_stay_within_p95_budget -q`
3. `python -m unittest discover -s tests -p 'test*.py'`

Observed results:
- Full pytest run: 1 failing test unrelated to this routing bug:
  - `tests/test_performance_security_smoke.py::SearchPerformanceSmokeTests::test_representative_filter_queries_stay_within_p95_budget`
  - Failure reason: p95 latency budget exceeded for repository query scenario.
- Targeted rerun of failing performance test: still failing with the same p95 budget assertion.
- `unittest` discovery run: PASS.
