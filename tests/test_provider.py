import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from events_aggregator.events_provider import EventsProviderClient


def test_get_events_request():
    async def run():
        transport = AsyncMock()
        request = httpx.Request("GET", "https://example.com/api/events/")
        transport.request.return_value = httpx.Response(
            200, json={"results": [], "next": None}, request=request
        )
        client = EventsProviderClient("https://example.com", "token", client=transport)
        data = await client.get_events("2000-01-01", "abc")
        assert data == {"results": [], "next": None}
        transport.request.assert_awaited_once_with(
            "GET",
            "https://example.com/api/events/",
            headers={"x-api-key": "token"},
            params={"changed_at": "2000-01-01", "cursor": "abc"},
            json=None,
        )

    asyncio.run(run())


def test_registration_request():
    async def run():
        client = EventsProviderClient("https://example.com", "token", client=AsyncMock())
        client._request = AsyncMock(return_value={"ticket_id": "id"})
        event_id = uuid4()
        await client.register(event_id, "A", "B", "a@b.com", "A1")
        client._request.assert_awaited_once_with(
            "POST",
            f"/api/events/{event_id}/register/",
            json={"first_name": "A", "last_name": "B", "email": "a@b.com", "seat": "A1"},
        )

    asyncio.run(run())


def test_provider_failure_propagates():
    async def run():
        transport = AsyncMock()
        request = httpx.Request("GET", "https://example.com/api/events/")
        transport.request.return_value = httpx.Response(401, request=request)
        client = EventsProviderClient("https://example.com", "token", client=transport)
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_events("2000-01-01")

    asyncio.run(run())
