# Events Aggregator

FastAPI/PostgreSQL aggregator for the LMS Events Provider API.

## Start locally (Docker)

1. `cp .env.example .env` and set `LMS_TOKEN` to the key from LMS. Never commit `.env`.
2. `docker compose up --build`
3. Browse `http://localhost:8000/docs` and `http://localhost:8000/api/health`.
4. First sync happens on startup; manually sync with `curl -X POST http://localhost:8000/api/sync/trigger`.

## Develop outside Docker

- Install Python 3.14 and uv, then `uv sync` (creates `uv.lock` on the first run).
- Start PostgreSQL (for example `docker compose up -d db`).
- `uv run alembic upgrade head`
- `uv run uvicorn events_aggregator.main:app --reload`
- `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format .` (optional formatting)

## Endpoints

- `GET /api/health`
- `POST /api/sync/trigger`
- `GET /api/events?date_from=YYYY-MM-DD&page=1&page_size=20`
- `GET /api/events/{event_id}`
- `GET /api/events/{event_id}/seats`
- `POST /api/tickets`
- `DELETE /api/tickets/{ticket_id}`

## Architecture

`events_provider.py`: external HTTP client + lazy cursor iterator.
`repositories.py`: persistence and PostgreSQL upserts.
`services.py`: ticket use case, error mapping, synchronized upsert.
`cache.py`: 30-second in-process seats cache.
`main.py`: FastAPI adapters and lifespan scheduled synchronization.

## Deployment

The archive does not contain `uv.lock` because dependency resolution requires network access; run `uv lock` and commit the resulting lockfile before submission. GitHub Actions lint + tests must pass before publishing to GHCR. Configure LMS `events-aggregator` deployment with the resulting image. Set `DATABASE_URL`, `LMS_TOKEN`, and `EVENTS_API_URL` as runtime environment variables / secrets. The included image applies migrations on startup. Use **one replica / one uvicorn worker** for this training configuration, since the scheduler and cache are in-process. For multi-replica production use distributed scheduling/locking and shared cache. GH Actions publishes images, but **does not deploy to LMS Kubernetes**, because LMS-specific deployment credentials/template are not provided.

## Important behavior

- `changed_at` accepts a date; the last changed day is refetched to avoid losing same-day updates; PostgreSQL upserts prevent duplicates.
- Provider registration is authoritative. A precheck of seats is informative, not atomic; provider can reject a seat during races.
- A provider may reuse a ticket UUID for a seat after cancellation, so saving a ticket overwrites data on an existing UUID after successful registration.
- Unexpected network errors return 502/503. Synchronization errors persist as `failed` state.
- Migration expects a PostgreSQL database already created.
- Background sync runs immediately at startup and every 24 hours from the previous attempt; trigger runs synchronously and yields 409 if a sync is in progress.
- This is a single-instance training implementation; thorough end-to-end testing against the LMS cluster/provider is still required before submission.
