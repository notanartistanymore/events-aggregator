import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date
from math import ceil
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy.orm import Session

from events_aggregator.cache import SeatsCache
from events_aggregator.config import get_settings
from events_aggregator.database import get_db, get_session_factory
from events_aggregator.events_provider import EventsProviderClient
from events_aggregator.repositories import EventRepository, TicketRepository
from events_aggregator.schemas import (
    EventDetail,
    EventsPage,
    EventSummary,
    SeatsResponse,
    SuccessResponse,
    TicketCreate,
    TicketCreated,
)
from events_aggregator.services import Synchronizer, TicketService, provider_error

logging.basicConfig(level=logging.INFO)
settings = get_settings()
provider = EventsProviderClient(
    settings.events_api_url, settings.lms_token, settings.provider_timeout
)
cache = SeatsCache(ttl=30)
synchronizer = Synchronizer(provider, get_session_factory())


async def scheduled_sync(stop: asyncio.Event):
    # A single worker is assumed. Multi-replica deployments need a distributed lock.
    while not stop.is_set():
        try:
            await asyncio.to_thread(synchronizer.run)
        except Exception:
            logging.exception("Scheduled sync failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.sync_interval_seconds)
        except TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = asyncio.create_task(scheduled_sync(stop)) if settings.enable_background_sync else None
    app.state.sync_task = task
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            await task


app = FastAPI(title="Events Aggregator", lifespan=lifespan)


@app.get("/api/health", tags=["Dev"])
def health_check():
    return {"status": "ok"}


@app.post("/api/sync/trigger", tags=["Sync"])
def sync_trigger():
    # Synchronous completion ensures clients see a completed sync at HTTP 200.
    if not synchronizer.run():
        raise HTTPException(409, "Synchronization already in progress")
    return {"status": "success"}


@app.get("/api/events", response_model=EventsPage, tags=["Events"])
@app.get("/api/events/", response_model=EventsPage, include_in_schema=False)
def get_events(
    request: Request,
    date_from: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    count, rows = EventRepository(db).list(date_from, page, page_size)
    pages = ceil(count / page_size)

    def link(number: int) -> str:
        params = dict(request.query_params)
        params.update({"page": str(number), "page_size": str(page_size)})
        return str(request.url.replace(query="")) + "?" + str(httpx.QueryParams(params))

    return EventsPage(
        count=count,
        next=link(page + 1) if page < pages else None,
        previous=link(page - 1) if page > 1 and pages else None,
        results=[EventSummary.model_validate(item) for item in rows],
    )


@app.get("/api/events/{event_id}", response_model=EventDetail, tags=["Events"])
def event_detail(event_id: UUID, db: Session = Depends(get_db)):
    event = EventRepository(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    return EventDetail.model_validate(event)


@app.get("/api/events/{event_id}/seats", response_model=SeatsResponse, tags=["Events"])
def event_seats(event_id: UUID, db: Session = Depends(get_db)):
    event = EventRepository(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    if event.status != "published":
        raise HTTPException(400, "Event is not published")
    seats = cache.get(event_id)
    if seats is None:
        try:
            seats = provider.get_seats(event_id)["seats"]
        except httpx.HTTPError as exc:
            raise provider_error(exc) from exc
        cache.set(event_id, seats)
    return SeatsResponse(event_id=event_id, available_seats=seats)


@app.post("/api/tickets", status_code=201, response_model=TicketCreated, tags=["Tickets"])
def create_ticket(body: TicketCreate, db: Session = Depends(get_db)):
    service = TicketService(provider, EventRepository(db), TicketRepository(db), cache)
    return TicketCreated(ticket_id=service.create(body))


@app.delete("/api/tickets/{ticket_id}", response_model=SuccessResponse, tags=["Tickets"])
def delete_ticket(ticket_id: UUID, db: Session = Depends(get_db)):
    service = TicketService(provider, EventRepository(db), TicketRepository(db), cache)
    service.cancel(ticket_id)
    return SuccessResponse(success=True)
