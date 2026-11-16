import asyncio

import httpx

from events_aggregator.database import get_db
from events_aggregator.main import app


def test_invalid_ticket_payload_returns_400():
    async def dummy_db():
        yield object()

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/tickets",
                json={
                    "event_id": "not-a-uuid",
                    "first_name": "Test",
                    "last_name": "User",
                    "email": "invalid",
                    "seat": "A1",
                },
            )
        assert response.status_code == 400
        locations = [error["loc"] for error in response.json()["detail"]]
        assert ["body", "event_id"] in locations
        assert ["body", "email"] in locations

    app.dependency_overrides[get_db] = dummy_db
    try:
        asyncio.run(run())
    finally:
        app.dependency_overrides.pop(get_db, None)
