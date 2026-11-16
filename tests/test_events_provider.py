import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from events_aggregator.events_provider import EventsProviderClient


def test_get_events():
    async def run():
        transport = AsyncMock()
        request = httpx.Request("GET", "https://example.com/api/events/")
        expected = {"results": [{"name": "Event name 1"}], "next": None}
        transport.request.return_value = httpx.Response(200, json=expected, request=request)
        client = EventsProviderClient("https://example.com", "example token", client=transport)
        result = await client.get_events("2000-01-01")
        assert result == expected
        transport.request.assert_awaited_once_with(
            "GET",
            "https://example.com/api/events/",
            headers={"x-api-key": "example token"},
            params={"changed_at": "2000-01-01"},
            json=None,
        )

    asyncio.run(run())


def test_get_events_unauthorized():
    async def run():
        transport = AsyncMock()
        request = httpx.Request("GET", "https://example.com/api/events/")
        transport.request.return_value = httpx.Response(401, request=request)
        client = EventsProviderClient("https://example.com", "example token", client=transport)
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.get_events("2000-01-01")
        assert error.value.response.status_code == 401

    asyncio.run(run())
