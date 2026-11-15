from unittest.mock import Mock, call

import pytest

from events_aggregator.events_provider import EventsPaginator


def test_two_pages():
    client = Mock()
    client.get_events.side_effect = [
        {
            "results": [{"name": "A"}, {"name": "B"}],
            "next": "http://provider/api/events/?changed_at=2000-01-01&cursor=xyz",
        },
        {"results": [{"name": "C"}], "next": None},
    ]
    assert [e["name"] for e in EventsPaginator(client)] == ["A", "B", "C"]
    assert client.get_events.call_args_list == [
        call("2000-01-01", cursor=None),
        call("2000-01-01", cursor="xyz"),
    ]


def test_empty_pages():
    client = Mock()
    client.get_events.return_value = {"results": [], "next": None}
    assert list(EventsPaginator(client)) == []
    client.get_events.assert_called_once()


def test_repeated_cursor_fails():
    client = Mock()
    client.get_events.return_value = {
        "results": [],
        "next": "http://provider/api/events/?cursor=repeat",
    }
    with pytest.raises(ValueError, match="repeated cursor"):
        list(EventsPaginator(client))
