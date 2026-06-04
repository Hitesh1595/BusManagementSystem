"""0005 routes stops

Revision ID: 543969fd1196
Revises: ab53e2db7165
Create Date: 2026-06-04 18:36:52.971053

Changes:
  - CREATE TYPE schedule_type AS ENUM ('morning','evening','both')
  - CREATE TABLE routes with school_id FK, vehicle_id FK nullable,
    driver_id FK nullable (→users), route_path geography(LineString,4326),
    schedule_type enum, version INT (optimistic lock), is_active, timestamps.
  - CREATE TABLE route_stops with route_id FK ON DELETE CASCADE,
    location geography(Point,4326) NOT NULL, stop_order INT,
    UNIQUE(route_id, stop_order).
  - GIST index idx_route_stops_location on route_stops.location.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "543969fd1196"
down_revision: str | Sequence[str] | None = "ab53e2db7165"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEDULE_TYPE_ENUM = ("morning", "evening", "both")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # schedule_type enum — create only if not already present
    # ------------------------------------------------------------------
    op.execute(
        "DO $$ BEGIN "
        "  CREATE TYPE schedule_type AS ENUM ('morning','evening','both'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    # ------------------------------------------------------------------
    # routes table (spec §6.3)
    # ------------------------------------------------------------------
    op.create_table(
        "routes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "vehicle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id"),
            nullable=True,
        ),
        sa.Column(
            "driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        # route_path stored as GEOGRAPHY so we use raw DDL after table creation
        sa.Column("route_path", sa.Text(), nullable=True),  # placeholder, altered below
        sa.Column(
            "schedule_type",
            postgresql.ENUM(*SCHEDULE_TYPE_ENUM, name="schedule_type", create_type=False),
            nullable=False,
            server_default="both",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Replace the TEXT placeholder with the proper geography column
    op.execute("ALTER TABLE routes DROP COLUMN route_path;")
    op.execute(
        "ALTER TABLE routes ADD COLUMN route_path geography(LineString,4326);"
    )

    # ------------------------------------------------------------------
    # route_stops table (spec §6.3)
    # ------------------------------------------------------------------
    op.create_table(
        "route_stops",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("routes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        # location added via raw DDL below (geography type)
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("stop_order", sa.Integer(), nullable=False),
        sa.Column("arrival_time", sa.Time(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("route_id", "stop_order", name="uq_route_stop_order"),
    )

    # Add geography(Point) column for location
    op.execute(
        "ALTER TABLE route_stops ADD COLUMN location geography(Point,4326) NOT NULL "
        "DEFAULT ST_SetSRID(ST_MakePoint(0,0),4326);"
    )
    # Drop the DEFAULT so new inserts must supply a location explicitly
    op.execute(
        "ALTER TABLE route_stops ALTER COLUMN location DROP DEFAULT;"
    )

    # GIST index on location (spec §6.3)
    op.execute(
        "CREATE INDEX idx_route_stops_location ON route_stops USING GIST (location);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_route_stops_location;")
    op.drop_table("route_stops")
    op.drop_table("routes")
    op.execute("DROP TYPE IF EXISTS schedule_type;")
