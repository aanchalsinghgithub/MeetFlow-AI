#!/bin/sh
set -e

# alembic.ini + the app/ package live in /app/backend, but the uv-managed
# venv (from `uv sync` against /app/pyproject.toml) lives at /app/.venv.
# uv walks up from cwd to find the venv, so running from /app/backend works.
cd /app/backend

echo "Running database migrations..."
uv run --project /app alembic upgrade head

echo "Starting server..."
exec uv run --project /app uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
