from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from events_aggregator.statuses import EventStatus


class PlaceSummary(BaseModel):
    id: UUID
    name: str
    city: str
    address: str
    model_config = ConfigDict(from_attributes=True)


class PlaceDetail(PlaceSummary):
    seats_pattern: str


class EventSummary(BaseModel):
    id: UUID
    name: str
    place: PlaceSummary
    event_time: datetime
    registration_deadline: datetime
    status: EventStatus
    number_of_visitors: int
    model_config = ConfigDict(from_attributes=True)


class EventDetail(EventSummary):
    place: PlaceDetail


class EventsPage(BaseModel):
    count: int
    next: str | None
    previous: str | None
    results: list[EventSummary]


class SeatsResponse(BaseModel):
    event_id: UUID
    available_seats: list[str]


class TicketCreate(BaseModel):
    event_id: UUID
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    seat: str = Field(min_length=2, max_length=50)


class TicketCreated(BaseModel):
    ticket_id: UUID


class SuccessResponse(BaseModel):
    success: bool
