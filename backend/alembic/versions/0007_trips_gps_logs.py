"""0007 trips and partitioned gps_logs

Revision ID: 0007_trips_gps_logs
Revises: 5379341db880
Create Date: 2026-06-04 00:00:00.000000

Changes:
  - CREATE TABLE trips (school_id, route_id, driver_id, vehicle_id, status, slot, ...)
    + 4 indexes incl. UNIQUE idx_trips_route_date_slot
  - CREATE TABLE gps_logs PARTITION BY RANGE (recorded_at)
    + idx_gps_trip_time + GIST idx_gps_location
    + inline partitions for current month (2026-06) and next month (2026-07)
    (APScheduler job 'ensure_gps_partitions' maintains future months — Chunk 4C)
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_trips_gps_logs"
down_revision: str | None = "5379341db880"
branch_labels = None
depends_on = None


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    """Return (start_inclusive, end_exclusive) date strings for a calendar month."""
    start = date(year, month, 1)
    # end = first day of next month
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day) + timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # trips table
    # ------------------------------------------------------------------
    op.create_table(
        "trips",
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
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("routes.id"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "vehicle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "scheduled",
                "in_progress",
                "pending_safeguard_check",
                "completed",
                "cancelled",
                "incident",
                name="trip_status",
                create_type=False,
            ),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column(
            "scheduled_departure_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "slot",
            sa.String(10),
            sa.CheckConstraint("slot IN ('morning','evening')", name="ck_trip_slot"),
            nullable=False,
        ),
        sa.Column("current_stop_order", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "safeguarding_checked",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "original_driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("reassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reassignment_reason", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes per spec §6.4
    op.create_index("idx_trips_status_date", "trips", ["status", "scheduled_date"])
    op.create_index("idx_trips_route_date", "trips", ["route_id", "scheduled_date"])
    op.create_index(
        "idx_trips_school_active",
        "trips",
        ["school_id", "status"],
        postgresql_where=sa.text(
            "status IN ('scheduled','in_progress','pending_safeguard_check')"
        ),
    )
    op.create_index(
        "idx_trips_route_date_slot",
        "trips",
        ["route_id", "scheduled_date", "slot"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # gps_logs — partitioned table (raw SQL; Alembic has no declarative
    # support for PG table partitioning)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE gps_logs (
            id          BIGSERIAL,
            trip_id     UUID NOT NULL,
            location    geography(Point,4326) NOT NULL,
            speed       REAL,
            heading     REAL,
            accuracy    REAL,
            recorded_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (id, recorded_at)
        ) PARTITION BY RANGE (recorded_at)
    """)

    # Indexes on parent table (PG propagates them to child partitions automatically)
    op.execute(
        "CREATE INDEX idx_gps_trip_time ON gps_logs (trip_id, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_gps_location ON gps_logs USING GIST (location)"
    )

    # ------------------------------------------------------------------
    # Inline monthly partitions — current month + next month
    # Computed dynamically so the migration stays correct regardless of
    # when it runs.  APScheduler job 'ensure_gps_partitions' (Chunk 4C)
    # will keep future months created at 00:30 IST daily.
    # ------------------------------------------------------------------
    today = date.today()
    _create_partition(today.year, today.month)

    # next month
    last_day = calendar.monthrange(today.year, today.month)[1]
    next_month_date = date(today.year, today.month, last_day) + timedelta(days=1)
    _create_partition(next_month_date.year, next_month_date.month)


def _create_partition(year: int, month: int) -> None:
    """Emit CREATE TABLE ... PARTITION OF for a single month (idempotent-ish via IF NOT EXISTS)."""
    start, end = _month_bounds(year, month)
    table_name = f"gps_logs_{year:04d}_{month:02d}"
    op.execute(
        f"CREATE TABLE IF NOT EXISTS {table_name} "
        f"PARTITION OF gps_logs "
        f"FOR VALUES FROM ('{start}') TO ('{end}')"
    )


def downgrade() -> None:
    # Drop partitions first (parent drop would CASCADE but be explicit)
    today = date.today()
    _drop_partition(today.year, today.month)
    last_day = calendar.monthrange(today.year, today.month)[1]
    next_month_date = date(today.year, today.month, last_day) + timedelta(days=1)
    _drop_partition(next_month_date.year, next_month_date.month)

    op.execute("DROP TABLE IF EXISTS gps_logs CASCADE")
    op.drop_table("trips")


def _drop_partition(year: int, month: int) -> None:
    table_name = f"gps_logs_{year:04d}_{month:02d}"
    op.execute(f"DROP TABLE IF EXISTS {table_name}")
