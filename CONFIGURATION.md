# Configuration

This project uses environment variables for backend runtime configuration.

The Flask backend loads configuration from `backend/config.py` and selects a
profile with `FLASK_ENV`.

## Environment Profiles

- `development` (default)
- `test`
- `production`

`FLASK_ENV` accepts aliases:

- `dev` -> `development`
- `testing` -> `test`
- `prod` -> `production`

## Supported Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `FLASK_ENV` | `development` | Backend environment profile (`development`, `test`, `production`). |
| `BACKEND_DEBUG` | profile default (`false` for all profiles) | Enables/disables Flask debug mode. Accepted true values: `1`, `true`, `yes`, `on`. Accepted false values: `0`, `false`, `no`, `off`. |
| `BACKEND_LOG_LEVEL` | `INFO` (`WARNING` in `test`) | Python logging level for backend startup and request handling. |
| `DB_HOST` | `dev-mysql` | Primary MySQL host used by backend queries. |
| `DB_PORT` | `3306` | Primary MySQL port used by backend queries. |
| `DB_NAME` | `dev_find_me_a_book` | Primary MySQL database/schema name. |
| `DB_USER` | `devagent` | Primary MySQL user. |
| `DB_PASSWORD` | empty string | Primary MySQL user password. |
| `DB_CHARSET` | `utf8mb4` | MySQL connection charset. |
| `BOOK_SOURCE_BASE_URL` | `https://www.goodreads.com` | Base URL for external book-source integrations. |
| `BOOK_SOURCE_API_KEY` | unset | Optional API key for external book-source integrations. |

### Legacy fallback variables

For database settings, if a `DB_*` variable is not set, backend config falls
back to matching `DEV_MYSQL_*` values:

- `DEV_MYSQL_HOST`
- `DEV_MYSQL_PORT`
- `DEV_MYSQL_DATABASE`
- `DEV_MYSQL_USER`
- `DEV_MYSQL_PASSWORD`

This preserves existing development behavior in environments that already use
`DEV_MYSQL_*` variables.

## Usage Examples

### Development (defaults only)

```bash
python -m backend.app
```

With no additional variables, backend config resolves to:

- `FLASK_ENV=development`
- `DB_HOST=dev-mysql`
- `DB_PORT=3306`
- `DB_NAME=dev_find_me_a_book`
- `DB_USER=devagent`

### Development (explicit)

```bash
FLASK_ENV=development \
DB_HOST=dev-mysql \
DB_PORT=3306 \
DB_NAME=dev_find_me_a_book \
DB_USER=devagent \
DB_PASSWORD=devpassword \
BACKEND_DEBUG=true \
python -m backend.app
```

### Production

```bash
FLASK_ENV=production \
DB_HOST=mysql.prod.internal \
DB_PORT=3306 \
DB_NAME=find_me_a_book \
DB_USER=findmebook \
DB_PASSWORD='<secure-password>' \
BACKEND_DEBUG=false \
BACKEND_LOG_LEVEL=INFO \
BOOK_SOURCE_API_KEY='<api-key>' \
python -m backend.app
```
