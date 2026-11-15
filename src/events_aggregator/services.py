import logging
import threading
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

import httpx
from fastapi import HTTPException

from events_aggregator.events_provider import EventsPaginator, EventsProviderClient
from events_aggregator.schemas import TicketCreate

logger = logging.getLogger(__name__)


class EventLookup(Protocol):
    def get(self, event_id: UUID): ...


class TicketStore(Protocol):
    def get(self, ticket_id: UUID): ...
    def save(self, ticket_id: UUID, req: TicketCreate): ...
    def delete(self, ticket): ...


def provider_error(exc: httpx.HTTPError) -> HTTPException:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 404:
            return HTTPException(404, "Provider resource not found")
        if code == 400:
            return HTTPException(400, "Provider rejected operation")
        if code == 401:
            logger.error("Provider API key rejected")
            return HTTPException(502, "Provider authentication failed")
        if code == 429:
            return HTTPException(503, "Provider rate limit exceeded")
    logger.warning("Provider request error: %s", exc)
    return HTTPException(502, "External provider unavailable")


class TicketService:
    def __init__(
        self, client: EventsProviderClient, events: EventLookup, tickets: TicketStore, cache
    ):
        self.client = client
        self.events = events
        self.tickets = tickets
        self.cache = cache

    def create(self, data: TicketCreate) -> UUID:
        event = self.events.get(data.event_id)
        if event is None:
            raise HTTPException(404, "Event not found")
        now = datetime.now(timezone.utc)
        if event.status != "published":
            raise HTTPException(400, "Event is not published")
        if event.registration_deadline <= now or event.event_time <= now:
            raise HTTPException(400, "Registration closed")
        try:
            available = self.client.get_seats(data.event_id)["seats"]
            if data.seat not in available:
                raise HTTPException(400, "Seat unavailable")
            result = self.client.register(
                data.event_id, data.first_name, data.last_name, str(data.email), data.seat
            )
        except httpx.HTTPError as exc:
            raise provider_error(exc) from exc
        ticket_id = UUID(result["ticket_id"])
        self.tickets.save(ticket_id, data)
        self.cache.invalidate(data.event_id)
        return ticket_id

    def cancel(self, ticket_id: UUID) -> None:
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise HTTPException(404, "Ticket not found")
        event = self.events.get(ticket.event_id)
        if event is None:
            raise HTTPException(404, "Event not found")
        if event.event_time <= datetime.now(timezone.utc):
            raise HTTPException(400, "Event already started")
        try:
            self.client.unregister(ticket.event_id, ticket_id)
        except httpx.HTTPError as exc:
            raise provider_error(exc) from exc
        self.tickets.delete(ticket)
        self.cache.invalidate(ticket.event_id)


class Synchronizer:
    def __init__(self, client, session_factory):
        self.client = client
        self.session_factory = session_factory
        self.lock = threading.Lock()

    def run(self) -> bool:
        from events_aggregator.repositories import EventRepository, SyncRepository

        if not self.lock.acquire(blocking=False):
            logger.info("Sync already running")
            return False
        try:
            with self.session_factory() as db:
                state = SyncRepository(db).get()
                # Provider accepts dates, not instants: fetch overlapping day and UPSERT.
                changed_at = (
                    state.last_changed_at.date().isoformat()
                    if state.last_changed_at
                    else "2000-01-01"
                )
                state.sync_status = "running"
                db.commit()
                latest = state.last_changed_at
                count = 0
                try:
                    for event in EventsPaginator(self.client, changed_at=changed_at):
                        EventRepository(db).upsert(event)
                        event_change = datetime.fromisoformat(event["changed_at"])
                        if latest is None or event_change > latest:
                            latest = event_change
                        count += 1
                    state.last_changed_at = latest
                    state.last_sync_time = datetime.now(timezone.utc)
                    state.sync_status = "success"
                    state.last_error = None
                    db.commit()
                    logger.info("Sync finished: %s records", count)
                    return True
                except Exception as exc:
                    db.rollback()
                    state = SyncRepository(db).get()
                    state.sync_status = "failed"
                    state.last_error = str(exc)[:2000]
                    db.commit()
                    logger.exception("Sync failed")
                    raise
        finally:
            self.lock.release()
