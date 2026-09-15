# ImportGuard

A customer CSV import application built with React, TypeScript, FastAPI,
SQLAlchemy, and PostgreSQL.

Upload a file, map its columns, preview validation errors, and import valid
customers. Completed imports retain saved reports and rejection downloads.

## Features

- Column mapping for names, emails, companies, and phone numbers.
- Row-level validation and duplicate detection.
- Atomic customer and report writes.
- Repeat requests return the original result for the same file and mapping.
- Import history and downloadable rejected rows.
- One Docker image serves the frontend and API.
- CI checks formatting, lint, migrations, tests, and the frontend build.

## Run with Docker

Requires Docker with Compose. Create a local configuration:

    cp .env.example .env

Set POSTGRES_PASSWORD in .env before starting the database.
Do not commit .env.

Build, migrate, and start:

    docker compose -f compose.yaml -f compose.app.yaml build app
    docker compose -f compose.yaml -f compose.app.yaml run --rm -T app alembic upgrade head
    docker compose -f compose.yaml -f compose.app.yaml up -d --wait

Open http://localhost:8080 for the app or http://localhost:8080/api/docs
for API documentation.

Try examples/customers.csv. Its first import into an empty database
accepts two rows and rejects three.

## Development

Requires Python 3.12, uv, Node.js 24, and PostgreSQL.

    uv sync --locked
    docker compose up -d --wait
    uv run alembic upgrade head
    uv run uvicorn importguard.api:app --reload --host 127.0.0.1 --port 8000

In another terminal:

    cd frontend
    npm ci
    npm run dev

## Verification

    uv run ruff format --check importguard tests
    uv run ruff check importguard tests
    IMPORTGUARD_TEST_DATABASE=1 uv run python -m pytest -q
    npm --prefix frontend run build

The suite contains 47 tests, including three PostgreSQL integration tests
covering retries, duplicate protection across files, and rollback.
Without IMPORTGUARD_TEST_DATABASE=1, those three tests are skipped.
Integration test records are rolled back.

## Design decisions

Fingerprints include file content, column mapping, and validation version.
Filenames do not affect import identity.

A PostgreSQL transaction advisory lock serializes imports across processes.
A unique email constraint and ON CONFLICT DO NOTHING prevent overwriting
existing customers.

Customer writes and the JSONB report share one transaction. Failed
transactions leave neither partial customer writes nor a completed report.

## Current limits

- UTF-8 CSV only; Excel uploads are not implemented.
- Maximum 5 MB, 10,000 data rows, and 50 columns.
- Email identity is case-insensitive; mailbox ownership is not verified.
- The interface shows at most 100 matching report rows.
- Data is shared. Authentication and tenant isolation are not implemented.
  The supplied Compose configuration binds to localhost.
- Imports are serialized, limiting concurrent throughput.
- Preview counts may change before commit.
- Rejection exports prefix formula-like values for spreadsheet use.
- Upload size checks occur after multipart parsing, not at network ingress.
