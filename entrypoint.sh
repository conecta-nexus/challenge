#!/usr/bin/env bash
set -e

# Run database migrations
echo "[challenge-entrypoint] Applying Alembic database migrations..."
if alembic upgrade head; then
    echo "[challenge-entrypoint] Database migrations applied successfully."
else
    echo "[challenge-entrypoint] WARNING: Alembic migrations failed or database connection is pending. Continuing startup..."
fi

exec "$@"
