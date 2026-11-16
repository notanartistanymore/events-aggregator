import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date
from math import ceil
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.cache import SeatsCache
from events_aggregator.config import get_settings
from events_aggregator.database import get_async_engine, get_db, get_session_factory
from events_aggregator.errors import (
    DomainError,
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
from events_aggregator.services import SeatsService, Synchronizer, TicketService

logging.basicConfig(level=logging.INFO)
settings = get_settings()
cache = SeatsCache(ttl=30)

ERROR_STATUSES = {
    EventNotFound: 404,
    TicketNotFound: 404,
    ProviderResourceNotFound: 404,
    EventNotPublished: 400,
    RegistrationClosed: 400,
    SeatUnavailable: 400,
    EventAlreadyStarted: 400,
    ProviderRejected: 400,
    ProviderAuthenticationFailed: 502,
    ProviderRateLimited: 503,
    ProviderUnavailable: 502,
}


async def scheduled_sync(stop: asyncio.Event, synchronizer: Synchronizer):
    # One worker; multiple processes require a distributed synchronization lock.
    while not stop.is_set():
        try:
            await synchronizer.run()
        except Exception:
            logging.exception("Scheduled sync failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.sync_interval_seconds)
        except TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        timeout=settings.provider_timeout, follow_redirects=True
    ) as http_client:
        provider = EventsProviderClient(
            settings.events_api_url,
            settings.lms_token,
            settings.provider_timeout,
            client=http_client,
        )
        synchronizer = Synchronizer(provider, get_session_factory())
        app.state.provider = provider
        app.state.synchronizer = synchronizer
        stop = asyncio.Event()
        task = (
            asyncio.create_task(scheduled_sync(stop, synchronizer))
            if settings.enable_background_sync
            else None
        )
        try:
            yield
        finally:
            stop.set()
            if task is not None:
                await task
    await get_async_engine().dispose()


app = FastAPI(title="Events Aggregator", lifespan=lifespan)


@app.exception_handler(DomainError)
async def domain_exception_handler(_request: Request, exc: DomainError):
    return JSONResponse(
        status_code=ERROR_STATUSES.get(type(exc), 500),
        content={"detail": str(exc)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": jsonable_encoder(exc.errors())})


@app.get("/api/health", tags=["Dev"])
async def health_check():
    return {"status": "ok"}


@app.post("/api/sync/trigger", tags=["Sync"])
async def sync_trigger(request: Request):
    if not await request.app.state.synchronizer.run():
        raise HTTPException(409, "Synchronization already in progress")
    return {"status": "success"}


@app.get("/api/events", response_model=EventsPage, tags=["Events"])
@app.get("/api/events/", response_model=EventsPage, include_in_schema=False)
async def get_events(
    request: Request,
    date_from: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    count, rows = await EventRepository(db).list(date_from, page, page_size)
    pages = ceil(count / page_size)

    def link(number: int) -> str:
        return str(request.url.include_query_params(page=number, page_size=page_size))

    return EventsPage(
        count=count,
        next=link(page + 1) if page < pages else None,
        previous=link(page - 1) if page > 1 and pages else None,
        results=[EventSummary.model_validate(item) for item in rows],
    )


@app.get("/api/events/{event_id}", response_model=EventDetail, tags=["Events"])
async def event_detail(event_id: UUID, db: AsyncSession = Depends(get_db)):
    event = await EventRepository(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    return EventDetail.model_validate(event)


@app.get("/api/events/{event_id}/seats", response_model=SeatsResponse, tags=["Events"])
async def event_seats(event_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    seats = await SeatsService(request.app.state.provider, EventRepository(db), cache).get(event_id)
    return SeatsResponse(event_id=event_id, available_seats=seats)


@app.post("/api/tickets", status_code=201, response_model=TicketCreated, tags=["Tickets"])
async def create_ticket(body: TicketCreate, request: Request, db: AsyncSession = Depends(get_db)):
    service = TicketService(
        request.app.state.provider, EventRepository(db), TicketRepository(db), cache
    )
    return TicketCreated(ticket_id=await service.create(body))


@app.delete("/api/tickets/{ticket_id}", response_model=SuccessResponse, tags=["Tickets"])
async def delete_ticket(ticket_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    service = TicketService(
        request.app.state.provider, EventRepository(db), TicketRepository(db), cache
    )
    await service.cancel(ticket_id)
    return SuccessResponse(success=True)
