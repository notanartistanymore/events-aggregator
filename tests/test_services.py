from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from events_aggregator.schemas import TicketCreate
from events_aggregator.services import TicketService


def test_create_ticket_uses_provider_and_saves_registration():
    event_id, ticket_id = uuid4(), uuid4()
    future = datetime.now(timezone.utc) + timedelta(days=3)
    events = Mock()
    events.get.return_value = SimpleNamespace(
        status="published", event_time=future, registration_deadline=future
    )
    provider = Mock()
    provider.get_seats.return_value = {"seats": ["A1"]}
    provider.register.return_value = {"ticket_id": str(ticket_id)}
    tickets = Mock()
    cache = Mock()
    data = TicketCreate(
        event_id=event_id,
        first_name="Ivan",
        last_name="Ivanov",
        email="ivan@example.com",
        seat="A1",
    )

    result = TicketService(provider, events, tickets, cache).create(data)

    assert result == ticket_id
    provider.register.assert_called_once_with(event_id, "Ivan", "Ivanov", "ivan@example.com", "A1")
    tickets.save.assert_called_once_with(ticket_id, data)
    cache.invalidate.assert_called_once_with(event_id)


def test_registration_rejected_before_call_to_provider():
    event_id = uuid4()
    events = Mock()
    events.get.return_value = SimpleNamespace(status="new")
    provider, tickets, cache = Mock(), Mock(), Mock()
    data = TicketCreate(
        event_id=event_id,
        first_name="Ivan",
        last_name="Ivanov",
        email="ivan@example.com",
        seat="A1",
    )

    with pytest.raises(HTTPException) as error:
        TicketService(provider, events, tickets, cache).create(data)

    assert error.value.status_code == 400
    provider.register.assert_not_called()
    tickets.save.assert_not_called()


def test_cancel_registration():
    event_id, ticket_id = uuid4(), uuid4()
    future = datetime.now(timezone.utc) + timedelta(days=3)
    ticket = SimpleNamespace(event_id=event_id)
    tickets = Mock()
    tickets.get.return_value = ticket
    events = Mock()
    events.get.return_value = SimpleNamespace(event_time=future)
    provider, cache = Mock(), Mock()

    TicketService(provider, events, tickets, cache).cancel(ticket_id)

    provider.unregister.assert_called_once_with(event_id, ticket_id)
    tickets.delete.assert_called_once_with(ticket)
    cache.invalidate.assert_called_once_with(event_id)
