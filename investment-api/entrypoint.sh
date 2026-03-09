#!/bin/sh
set -e

echo "Waiting for database..."
for i in $(seq 1 10); do
    if alembic upgrade head 2>&1; then
        echo "Migrations applied successfully."
        break
    fi
    if [ "$i" = "10" ]; then
        echo "Failed to apply migrations after 10 attempts, exiting."
        exit 1
    fi
    echo "Database not ready, retrying in 2s... (attempt $i/10)"
    sleep 2
done

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000