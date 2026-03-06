# Task 120 Mock PostgreSQL Verification

Run from repository root:

```bash
python3 database/verify_mock_postgres.py
```

Expected outcome:
- Mock database is created.
- `database/schema.sql` is applied by the mock client with no errors.
- Required schema objects are asserted: `users`, `books`, `filters`, supporting planned tables, `mv_book_search`, and required indexes.

Captured passing run output:
- `docs/verification/task-120-mock-postgres-output.txt`
