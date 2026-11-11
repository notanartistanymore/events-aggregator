from unittest.mock import patch

import httpx
import pytest

from events_aggregator.events_provider import EventsProviderClient


def test_get_events():
    with patch("events_aggregator.events_provider.httpx.get") as mock_get:
        client = EventsProviderClient(api_url="https://example.com", api_token="example token")
        mock_get.return_value.json.return_value = {
            "results": [{"name": "Event name 1"}],
            "next": None,
        }
        data = client.get_events(changed_at="2000-01-01")

        mock_get.assert_called_once_with(
            "https://example.com/api/events/",
            headers={"x-api-key": "example token"},
            params={"changed_at": "2000-01-01"},
        )

        mock_get.return_value.raise_for_status.assert_called_once()

        assert data == {"results": [{"name": "Event name 1"}], "next": None}


def test_get_events_unauthorized():
    client = EventsProviderClient(
        api_url="https://example.com",
        api_token="example token",
    )

    with patch("events_aggregator.events_provider.httpx.get") as mock_get:
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=httpx.Request(
                "GET",
                "https://example.com/api/events/",
            ),
            response=httpx.Response(401),
        )

        with pytest.raises(httpx.HTTPStatusError):
            client.get_events(changed_at="2000-01-01")

        mock_get.assert_called_once()
        mock_get.return_value.raise_for_status.assert_called_once()
