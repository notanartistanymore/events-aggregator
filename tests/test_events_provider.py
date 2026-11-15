from unittest.mock import patch

import httpx
import pytest

from events_aggregator.events_provider import EventsProviderClient


def test_get_events():
    client = EventsProviderClient(
        api_url="https://example.com",
        api_token="example token",
    )

    expected_data = {
        "results": [{"name": "Event name 1"}],
        "next": None,
    }

    request = httpx.Request(
        "GET",
        "https://example.com/api/events/?changed_at=2000-01-01",
    )

    response = httpx.Response(
        status_code=200,
        json=expected_data,
        request=request,
    )

    with patch("events_aggregator.events_provider.httpx.Client") as mock_client:
        mock_request = mock_client.return_value.__enter__.return_value.request
        mock_request.return_value = response

        data = client.get_events(changed_at="2000-01-01")

        assert data == expected_data

        mock_request.assert_called_once_with(
            "GET",
            "https://example.com/api/events/",
            headers={"x-api-key": "example token"},
            params={"changed_at": "2000-01-01"},
            json=None,
        )


def test_get_events_unauthorized():
    client = EventsProviderClient(
        api_url="https://example.com",
        api_token="example token",
    )

    request = httpx.Request(
        "GET",
        "https://example.com/api/events/",
    )

    response = httpx.Response(
        status_code=401,
        request=request,
    )

    with patch("events_aggregator.events_provider.httpx.Client") as mock_client:
        mock_request = mock_client.return_value.__enter__.return_value.request
        mock_request.return_value = response

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.get_events(changed_at="2000-01-01")

        assert exc_info.value.response.status_code == 401
        mock_request.assert_called_once()
