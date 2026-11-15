from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import pytest

from events_aggregator.events_provider import EventsProviderClient


def test_get_events_request():
    client = EventsProviderClient("https://example.com", "token")
    response = Mock()
    response.json.return_value = {"results": [], "next": None}
    with patch("events_aggregator.events_provider.httpx.Client") as cls:
        cls.return_value.__enter__.return_value.request.return_value = response
        assert client.get_events("2000-01-01", "abc") == {"results": [], "next": None}
        cls.return_value.__enter__.return_value.request.assert_called_once_with(
            "GET",
            "https://example.com/api/events/",
            headers={"x-api-key": "token"},
            params={"changed_at": "2000-01-01", "cursor": "abc"},
            json=None,
        )
        response.raise_for_status.assert_called_once()


def test_registration_request():
    client = EventsProviderClient("https://example.com", "token")
    with patch.object(client, "_request", return_value={"ticket_id": "id"}) as request:
        event_id = uuid4()
        client.register(event_id, "A", "B", "a@b.com", "A1")
        request.assert_called_once_with(
            "POST",
            f"/api/events/{event_id}/register/",
            json={"first_name": "A", "last_name": "B", "email": "a@b.com", "seat": "A1"},
        )


def test_provider_failure_propagates():
    client = EventsProviderClient("https://example.com", "token")
    request = httpx.Request("GET", "https://example.com/api/events/")
    response = httpx.Response(401, request=request)
    with patch("events_aggregator.events_provider.httpx.Client") as cls:
        cls.return_value.__enter__.return_value.request.return_value = response
        with pytest.raises(httpx.HTTPStatusError):
            client.get_events("2000-01-01")
