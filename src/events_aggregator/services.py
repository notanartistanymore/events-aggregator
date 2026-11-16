import asyncio
import logging
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

import httpx

from events_aggregator.errors import (
    EventAlreadyStarted,
    EventNotFound,
    EventNotPublished,
    ProviderAuthenticationFailed,
    ProviderRateLimited,
    ProviderRejected,
    ProviderResourceNotFound,
    ProviderUnavailable,
    RegistrationClosed,
    SeatUnavailable,
    TicketNotFound,
)
from events_aggregator.events_provider import EventsPaginator, EventsProviderClient
from events_aggregator.repositories import EventRepository, SyncRepository
from events_aggregator.schemas import TicketCreate
from events_aggregator.statuses import EventStatus, SyncStatus

logger = logging.getLogger(__name__)


class EventLookup(Protocol):
    async def get(self, event_id: UUID): ...


class TicketStore(Protocol):
    async def get(self, ticket_id: UUID): ...
    async def save(self, ticket_id: UUID, req: TicketCreate): ...
    async def delete(self, ticket): ...


def provider_error(exc: httpx.HTTPError) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 404:
            return ProviderResourceNotFound("Provider resource not found")
        if code == 400:
            return ProviderRejected("Provider rejected operation")
        if code == 401:
            logger.error("Provider API key rejected")
            return ProviderAuthenticationFailed("Provider authentication failed")
        if code == 429:
            return ProviderRateLimited("Provider rate limit exceeded")
    logger.warning("Provider request error: %s", exc)
    return ProviderUnavailable("External provider unavailable")


class TicketService:
    def __init__(
        self, client: EventsProviderClient, events: EventLookup, tickets: TicketStore, cache
    ):
        self.client = client
        self.events = events
        self.tickets = tickets
        self.cache = cache

    async def create(self, data: TicketCreate) -> UUID:
        event = await self.events.get(data.event_id)
        if event is None:
            raise EventNotFound("Event not found")
        now = datetime.now(timezone.utc)
        if event.status != EventStatus.PUBLISHED:
            raise EventNotPublished("Event is not published")
        if event.registration_deadline <= now or event.event_time <= now:
            raise RegistrationClosed("Registration closed")
        try:
            available = (await self.client.get_seats(data.event_id))["seats"]
            if data.seat not in available:
                raise SeatUnavailable("Seat unavailable")
            result = await self.client.register(
                data.event_id, data.first_name, data.last_name, str(data.email), data.seat
            )
        except httpx.HTTPError as exc:
            raise provider_error(exc) from exc
        ticket_id = UUID(result["ticket_id"])
        await self.tickets.save(ticket_id, data)
        self.cache.invalidate(data.event_id)
        return ticket_id

    async def cancel(self, ticket_id: UUID) -> None:
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise TicketNotFound("Ticket not found")
        event = await self.events.get(ticket.event_id)
        if event is None:
            raise EventNotFound("Event not found")
        if event.event_time <= datetime.now(timezone.utc):
            raise EventAlreadyStarted("Event already started")
        try:
            await self.client.unregister(ticket.event_id, ticket_id)
        except httpx.HTTPError as exc:
            raise provider_error(exc) from exc
        await self.tickets.delete(ticket)
        self.cache.invalidate(ticket.event_id)


class SeatsService:
    def __init__(self, client: EventsProviderClient, events: EventLookup, cache):
        self.client = client
        self.events = events
        self.cache = cache

    async def get(self, event_id: UUID) -> list[str]:
        event = await self.events.get(event_id)
        if event is None:
            raise EventNotFound("Event not found")
        if event.status != EventStatus.PUBLISHED:
            raise EventNotPublished("Event is not published")
        seats = self.cache.get(event_id)
        if seats is None:
            try:
                seats = (await self.client.get_seats(event_id))["seats"]
            except httpx.HTTPError as exc:
                raise provider_error(exc) from exc
            self.cache.set(event_id, seats)
        return seats


class Synchronizer:
    def __init__(self, client: EventsProviderClient, session_factory):
        self.client = client
        self.session_factory = session_factory
        self.lock = asyncio.Lock()

    async def run(self) -> bool:
        if self.lock.locked():
            logger.info("Sync already running")
            return False
        # No await between locked() and acquire(): single event-loop / worker.
        await self.lock.acquire()
        try:
            async with self.session_factory() as db:
                state = await SyncRepository(db).get()
                changed_at = (
                    state.last_changed_at.date().isoformat()
                    if state.last_changed_at
                    else "2000-01-01"
                )
                state.sync_status = SyncStatus.RUNNING
                await db.commit()
                latest = state.last_changed_at
                count = 0
                try:
                    async for event in EventsPaginator(self.client, changed_at=changed_at):
                        await EventRepository(db).upsert(event)
                        event_change = datetime.fromisoformat(event["changed_at"])
                        if latest is None or event_change > latest:
                            latest = event_change
                        count += 1
                    state.last_changed_at = latest
                    state.last_sync_time = datetime.now(timezone.utc)
                    state.sync_status = SyncStatus.SUCCESS
                    state.last_error = None
                    await db.commit()
                    logger.info("Sync finished: %s records", count)
                    return True
                except Exception as exc:
                    await db.rollback()
                    state = await SyncRepository(db).get()
                    state.sync_status = SyncStatus.FAILED
                    state.last_error = str(exc)[:2000]
                    await db.commit()
                    logger.exception("Sync failed")
                    raise
        finally:
            self.lock.release()
