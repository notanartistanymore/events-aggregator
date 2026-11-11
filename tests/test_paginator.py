from unittest.mock import Mock, call

from events_aggregator.events_provider import EventsPaginator


def test_paginator_single_page():
    client = Mock()

    client.get_events.return_value = {
        "results": [
            {"name": "Event name 1"},
            {"name": "Event name 2"},
        ],
        "next": None,
    }

    paginator = EventsPaginator(
        client=client,
        changed_at="2000-01-01",
    )

    events = list(paginator)

    client.get_events.assert_called_once()
    assert len(events) == 2


def test_paginator_multiple_pages():
    client = Mock()

    event_page_1 = {
        "next": "https://example.com/api/events/?changed_at=2026-01-01&cursor=xyz",
        "results": [
            {"name": "Event name 1"},
            {"name": "Event name 2"},
        ],
    }

    event_page_2 = {
        "next": None,
        "results": [
            {"name": "Event name 3"},
            {"name": "Event name 4"},
        ],
    }

    client.get_events.side_effect = [event_page_1, event_page_2]

    paginator = EventsPaginator(
        client=client,
        changed_at="2000-01-01",
    )

    events = list(paginator)

    client.get_events.assert_has_calls(
        [
            call(changed_at="2000-01-01", cursor=None),
            call(changed_at="2000-01-01", cursor="xyz"),
        ]
    )

    assert len(events) == 4
    assert client.get_events.call_count == 2
    assert [event["name"] for event in events] == [
        "Event name 1",
        "Event name 2",
        "Event name 3",
        "Event name 4",
    ]
