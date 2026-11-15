from uuid import uuid4

from events_aggregator.cache import SeatsCache


def test_cache_and_invalidate():
    cache = SeatsCache(30)
    event_id = uuid4()
    assert cache.get(event_id) is None
    cache.set(event_id, ["A1"])
    value = cache.get(event_id)
    assert value == ["A1"]
    value.append("A2")
    assert cache.get(event_id) == ["A1"]
    cache.invalidate(event_id)
    assert cache.get(event_id) is None
