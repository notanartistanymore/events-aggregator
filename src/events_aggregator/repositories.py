from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from events_aggregator.models import Event, Place, SyncState, Ticket


class EventRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, event_id: UUID) -> Event | None:
        return self.session.get(Event, event_id)

    def list(self, date_from: date | None, page: int, page_size: int):
        query = select(Event)
        if date_from is not None:
            query = query.where(
                Event.event_time
                >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
            )
        count = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        events = self.session.scalars(
            query.order_by(Event.event_time, Event.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return count, events

    def upsert(self, raw: dict) -> None:
        place = raw["place"]
        place_values = {
            k: place.get(k)
            for k in ("id", "name", "city", "address", "seats_pattern", "changed_at", "created_at")
        }
        for key in ("changed_at", "created_at"):
            if isinstance(place_values[key], str):
                place_values[key] = datetime.fromisoformat(place_values[key])
        stmt = insert(Place).values(**place_values)
        self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Place.id],
                set_={k: getattr(stmt.excluded, k) for k in place_values if k != "id"},
            )
        )
        event_values = {
            k: raw.get(k)
            for k in (
                "id",
                "name",
                "event_time",
                "registration_deadline",
                "status",
                "number_of_visitors",
                "changed_at",
                "created_at",
                "status_changed_at",
            )
        }
        for key in (
            "event_time",
            "registration_deadline",
            "changed_at",
            "created_at",
            "status_changed_at",
        ):
            if isinstance(event_values[key], str):
                event_values[key] = datetime.fromisoformat(event_values[key])
        event_values["place_id"] = place["id"]
        stmt = insert(Event).values(**event_values)
        self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Event.id],
                set_={k: getattr(stmt.excluded, k) for k in event_values if k != "id"},
                where=Event.changed_at <= stmt.excluded.changed_at,
            )
        )


class TicketRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, ticket_id: UUID) -> Ticket | None:
        return self.session.get(Ticket, ticket_id)

    def save(self, ticket_id: UUID, req) -> None:
        ticket = self.get(ticket_id)
        if ticket is None:
            ticket = Ticket(ticket_id=ticket_id)
            self.session.add(ticket)
        ticket.event_id = req.event_id
        ticket.first_name = req.first_name
        ticket.last_name = req.last_name
        ticket.email = str(req.email)
        ticket.seat = req.seat
        ticket.created_at = datetime.now().astimezone()
        self.session.commit()

    def delete(self, ticket: Ticket) -> None:
        self.session.delete(ticket)
        self.session.commit()


class SyncRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self) -> SyncState:
        state = self.session.get(SyncState, 1)
        if state is None:
            state = SyncState(id=1, sync_status="never")
            self.session.add(state)
            self.session.commit()
        return state
