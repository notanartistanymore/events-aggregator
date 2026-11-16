from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from events_aggregator.models import Event, Place, SyncState, Ticket
from events_aggregator.statuses import SyncStatus


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, event_id: UUID) -> Event | None:
        return await self.session.get(Event, event_id)

    async def list(self, date_from: date | None, page: int, page_size: int):
        query = select(Event)
        if date_from is not None:
            query = query.where(
                Event.event_time
                >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
            )
        count = await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        result = await self.session.scalars(
            query.order_by(Event.event_time, Event.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return count, result.all()

    async def upsert(self, raw: dict) -> None:
        place = raw["place"]
        place_values = {
            key: place.get(key)
            for key in (
                "id",
                "name",
                "city",
                "address",
                "seats_pattern",
                "changed_at",
                "created_at",
            )
        }
        for key in ("changed_at", "created_at"):
            if isinstance(place_values[key], str):
                place_values[key] = datetime.fromisoformat(place_values[key])
        stmt = insert(Place).values(**place_values)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Place.id],
                set_={key: getattr(stmt.excluded, key) for key in place_values if key != "id"},
            )
        )
        event_values = {
            key: raw.get(key)
            for key in (
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
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Event.id],
                set_={key: getattr(stmt.excluded, key) for key in event_values if key != "id"},
                where=Event.changed_at <= stmt.excluded.changed_at,
            )
        )


class TicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, ticket_id: UUID) -> Ticket | None:
        return await self.session.get(Ticket, ticket_id)

    async def save(self, ticket_id: UUID, req) -> None:
        ticket = await self.get(ticket_id)
        if ticket is None:
            ticket = Ticket(ticket_id=ticket_id)
            self.session.add(ticket)
        ticket.event_id = req.event_id
        ticket.first_name = req.first_name
        ticket.last_name = req.last_name
        ticket.email = str(req.email)
        ticket.seat = req.seat
        ticket.created_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def delete(self, ticket: Ticket) -> None:
        await self.session.delete(ticket)
        await self.session.commit()


class SyncRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self) -> SyncState:
        state = await self.session.get(SyncState, 1)
        if state is None:
            state = SyncState(id=1, sync_status=SyncStatus.NEVER)
            self.session.add(state)
            await self.session.commit()
        return state
