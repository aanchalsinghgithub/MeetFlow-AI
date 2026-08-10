#!/bin/sh
# BUGFIX: this is the second time a deploy went out with a new Alembic
# migration that never got run against Neon (production), causing
# "UndefinedColumn"/"UndefinedTable" crashes at request time instead of
# failing loudly at deploy time. `alembic upgrade head` is safe to run on
# every startup — if there's nothing new to apply it's a no-op — so this
# just makes "deploy code" and "migrate the DB" the same step instead of
# two manual steps that are easy to forget one of.
set -e
cd "$(dirname "$0")"
echo "Running database migrations..."
uv run alembic upgrade head
echo "Starting server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
