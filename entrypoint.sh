#!/bin/sh
set -eu
uv run --no-sync alembic upgrade head
exec uv run --no-sync uvicorn events_aggregator.main:app --host 0.0.0.0 --port 8000 --workers 1
