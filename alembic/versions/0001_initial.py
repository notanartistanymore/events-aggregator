"""Initial schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "places",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("city", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("seats_pattern", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("place_id", UUID(as_uuid=True), sa.ForeignKey("places.id"), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("number_of_visitors", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("status_changed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_events_event_time", "events", ["event_time"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_changed_at", "events", ["changed_at"])
    op.create_table(
        "tickets",
        sa.Column("ticket_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("seat", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_sync_time", sa.DateTime(timezone=True)),
        sa.Column("last_changed_at", sa.DateTime(timezone=True)),
        sa.Column("sync_status", sa.String(30), nullable=False),
        sa.Column("last_error", sa.Text()),
    )


def downgrade():
    op.drop_table("sync_state")
    op.drop_table("tickets")
    op.drop_index("ix_events_changed_at", table_name="events")
    op.drop_index("ix_events_status", table_name="events")
    op.drop_index("ix_events_event_time", table_name="events")
    op.drop_table("events")
    op.drop_table("places")
