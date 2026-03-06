# Database Implementation Plan: find-me-a-book

## 1. Purpose and Scope

This plan describes how to implement the approved PostgreSQL schema in a runnable environment using `database/schema.sql`.

In scope:
- Create database roles and database instance for the app.
- Apply the schema in a repeatable way.
- Validate that required tables, indexes, and materialized view exist.
- Define rollout, rollback, and operational checkpoints.

Out of scope:
- Production infra provisioning (Terraform/Cloud setup).
- App-layer query implementation.
- ETL/data ingestion pipelines.

## 2. Target Database System

- Database engine: PostgreSQL 15+
- Required extension: `citext`
- Schema source of truth: `database/schema.sql`
- Required core entities: `users`, `books`, `filters`

## 3. Inputs and Owners

Inputs required before execution:
- PostgreSQL host, port, and admin credentials
- Desired database name (recommended: `find_me_a_book`)
- App DB username/password
- Network rules allowing app/service account access

Suggested ownership:
- DBA/Platform: DB creation, role grants, extension availability
- Backend team: schema apply + verification
- QA/Dev lead: acceptance sign-off

## 4. Preconditions Checklist

Complete this checklist before applying SQL:

- [ ] PostgreSQL 15+ is reachable from the execution environment.
- [ ] Admin user can create roles/databases.
- [ ] `citext` extension is available in the PostgreSQL installation.
- [ ] A secure password is generated for the application role.
- [ ] Connection SSL requirements are known (`sslmode=require` if needed).
- [ ] Backup/snapshot strategy is confirmed for non-dev environments.

If any item fails, stop and resolve access/configuration first.

## 5. Environment Variables

Use explicit environment variables in shell/CI jobs.

```bash
export PGHOST="<db-host>"
export PGPORT="5432"
export PGUSER="<admin-user>"
export PGPASSWORD="<admin-password>"
export PGDATABASE="postgres"

# Application DB identifiers
export APP_DB_NAME="find_me_a_book"
export APP_DB_USER="findmebook_app"
export APP_DB_PASSWORD="<app-password>"
```

## 6. Implementation Steps

## Step 1: Verify Server Connectivity

```bash
psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -c "SELECT version();"
```

Pass criteria:
- Command succeeds.
- Server reports PostgreSQL 15 or later.

## Step 2: Create Application Role

Run as admin user:

```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :'APP_DB_USER'
  ) THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', :'APP_DB_USER', :'APP_DB_PASSWORD');
  END IF;
END
$$;
```

Alternative (simpler one-time run):

```sql
CREATE ROLE findmebook_app LOGIN PASSWORD '<app-password>';
```

## Step 3: Create Database

```sql
SELECT 'CREATE DATABASE find_me_a_book OWNER findmebook_app ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'find_me_a_book')\gexec
```

Then enforce minimal grants:

```sql
GRANT CONNECT ON DATABASE find_me_a_book TO findmebook_app;
```

## Step 4: Confirm Extension Availability

Connect to `find_me_a_book` as admin and run:

```sql
CREATE EXTENSION IF NOT EXISTS citext;
```

Pass criteria:
- `citext` exists in `pg_extension`.

## Step 5: Apply Schema DDL

Run from repo root:

```bash
psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$APP_DB_NAME" -v ON_ERROR_STOP=1 -f database/schema.sql
```

Notes:
- `schema.sql` is transactional (`BEGIN/COMMIT`).
- `ON_ERROR_STOP=1` makes failures explicit and non-partial.

## Step 6: Transfer/Confirm Runtime Permissions

Connect as admin to target DB and grant privileges:

```sql
GRANT USAGE ON SCHEMA public TO findmebook_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO findmebook_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO findmebook_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO findmebook_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO findmebook_app;
```

## Step 7: Verification Queries

Run these checks after schema apply.

### 7.1 Required tables exist

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('users', 'books', 'filters')
ORDER BY table_name;
```

Expected: 3 rows.

### 7.2 All planned tables/views exist

```sql
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'users', 'books', 'filters', 'authors', 'genres',
    'book_authors', 'book_genres', 'user_books', 'filter_genres'
  )
UNION ALL
SELECT matviewname AS table_name, 'MATERIALIZED VIEW' AS table_type
FROM pg_matviews
WHERE schemaname = 'public'
  AND matviewname = 'mv_book_search'
ORDER BY table_name;
```

Expected: all listed objects present.

### 7.3 Core indexes and constraint behavior

```sql
SELECT indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'uq_books_isbn_10',
    'uq_books_isbn_13',
    'uq_filters_one_default_per_user',
    'uq_mv_book_search_book'
  )
ORDER BY indexname;
```

Expected: 4 rows.

### 7.4 Smoke test inserts

```sql
INSERT INTO users (email, username, display_name)
VALUES ('impl-plan-smoke@example.com', 'impl_plan_smoke', 'Implementation Smoke')
RETURNING user_id;

INSERT INTO books (title, language_code)
VALUES ('Smoke Book', 'en')
RETURNING book_id;

INSERT INTO filters (user_id, name, is_default)
VALUES (
  (SELECT user_id FROM users WHERE username = 'impl_plan_smoke'),
  'default-smoke',
  TRUE
)
RETURNING filter_id;
```

Expected:
- All inserts succeed.
- One row each returned.

Cleanup:

```sql
DELETE FROM filters WHERE name = 'default-smoke';
DELETE FROM books WHERE title = 'Smoke Book';
DELETE FROM users WHERE username = 'impl_plan_smoke';
```

## 8. Migration and Release Strategy

Recommended strategy for managed environments:

1. Baseline migration:
   - Store current `database/schema.sql` as migration `V001__baseline_schema.sql` in the chosen migration tool.
2. Forward-only migrations:
   - Any schema change after baseline uses numbered migrations (`V002`, `V003`, ...).
3. Separate deploy phases:
   - Phase A: apply DDL.
   - Phase B: deploy app version requiring new schema.
4. Compatibility window:
   - Keep additive changes backward compatible for at least one deploy cycle.

## 9. Rollback Plan

For baseline creation:
- If schema apply fails before commit, PostgreSQL transaction rolls back automatically.
- If post-apply validation fails, drop and recreate database in non-production.

For later migrations:
- Prefer forward-fix migration over destructive rollback.
- Restore from backup/snapshot for severe production issues.

## 10. Operational Runbook Notes

- Refresh materialized view after bulk catalog loads:

```sql
REFRESH MATERIALIZED VIEW mv_book_search;
```

- Optionally use concurrent refresh after adding unique index and if downtime constraints require it:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_book_search;
```

- Track key metrics:
  - DDL execution time
  - Lock wait events
  - Query performance on recommendation endpoints

## 11. Risk Register and Mitigations

- Risk: `citext` not installed in DB cluster.
  - Mitigation: preflight extension check; involve DBA before deployment window.

- Risk: Insufficient privileges for app role.
  - Mitigation: execute grants/default privileges and validate with app role connection.

- Risk: Production lock contention during schema apply.
  - Mitigation: run during low-traffic window; separate heavy operations into later migrations.

- Risk: Materialized view staleness.
  - Mitigation: schedule refresh job post-ingestion and monitor refresh age.

## 12. Blocker Conditions

Stop execution and escalate if any of the following occur:
- Cannot authenticate to PostgreSQL with provided credentials.
- Host/port unreachable from runtime environment.
- Missing permissions to create database/role/extension.
- `citext` extension unavailable and cannot be installed by platform team.
- Configuration conflicts (SSL/TLS requirements, pg_hba policy) prevent stable connections.

Escalation payload should include:
- Exact command executed
- Error message
- Environment target (dev/stage/prod)
- Requested action owner (DBA/platform/security)

## 13. Acceptance Mapping

Acceptance test: "Implementation plan is documented and includes steps for creating the database and applying the schema."

Mapping:
- Database creation steps: Section 6, Step 2 and Step 3.
- Schema application steps: Section 6, Step 5.
- Validation of successful implementation: Section 7.
- Blocked conditions for access/configuration: Section 12.

## 14. Execution Sign-off Template

Use this checklist in implementation PR or release ticket:

- [ ] Preconditions complete (Section 4)
- [ ] Database role created
- [ ] Database created and reachable
- [ ] Schema applied successfully from `database/schema.sql`
- [ ] Verification queries passed
- [ ] Smoke test inserts passed and cleaned up
- [ ] Materialized view refresh process confirmed
- [ ] Risks reviewed and owners assigned
- [ ] Sign-off by backend + platform
