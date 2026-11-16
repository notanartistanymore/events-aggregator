import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from events_aggregator.errors import EventNotPublished
from events_aggregator.schemas import TicketCreate
from events_aggregator.services import TicketService
from events_aggregator.statuses import EventStatus


def test_create_ticket_uses_provider_and_saves_registration():
    async def run():
        event_id, ticket_id = uuid4(), uuid4()
        future = datetime.now(timezone.utc) + timedelta(days=3)
        events = AsyncMock()
        events.get.return_value = SimpleNamespace(
            status=EventStatus.PUBLISHED, event_time=future, registration_deadline=future
        )
        provider = AsyncMock()
        provider.get_seats.return_value = {"seats": ["A1"]}
        provider.register.return_value = {"ticket_id": str(ticket_id)}
        tickets = AsyncMock()
        cache = Mock()
        data = TicketCreate(
            event_id=event_id,
            first_name="Ivan",
            last_name="Ivanov",
            email="ivan@example.com",
            seat="A1",
        )
        result = await TicketService(provider, events, tickets, cache).create(data)
        assert result == ticket_id
        provider.register.assert_awaited_once_with(
            event_id, "Ivan", "Ivanov", "ivan@example.com", "A1"
        )
        tickets.save.assert_awaited_once_with(ticket_id, data)
        cache.invalidate.assert_called_once_with(event_id)

    asyncio.run(run())


def test_registration_rejected_before_call_to_provider():
    async def run():
        event_id = uuid4()
        events = AsyncMock()
        events.get.return_value = SimpleNamespace(status=EventStatus.NEW)
        provider, tickets, cache = AsyncMock(), AsyncMock(), Mock()
        data = TicketCreate(
            event_id=event_id,
            first_name="Ivan",
            last_name="Ivanov",
            email="ivan@example.com",
            seat="A1",
        )
        with pytest.raises(EventNotPublished):
            await TicketService(provider, events, tickets, cache).create(data)
        provider.register.assert_not_awaited()
        tickets.save.assert_not_awaited()

    asyncio.run(run())


def test_cancel_registration():
    async def run():
        event_id, ticket_id = uuid4(), uuid4()
        future = datetime.now(timezone.utc) + timedelta(days=3)
        ticket = SimpleNamespace(event_id=event_id)
        tickets = AsyncMock()
        tickets.get.return_value = ticket
        events = AsyncMock()
        events.get.return_value = SimpleNamespace(event_time=future)
        provider, cache = AsyncMock(), Mock()
        await TicketService(provider, events, tickets, cache).cancel(ticket_id)
        provider.unregister.assert_awaited_once_with(event_id, ticket_id)
        tickets.delete.assert_awaited_once_with(ticket)
        cache.invalidate.assert_called_once_with(event_id)

    asyncio.run(run())
