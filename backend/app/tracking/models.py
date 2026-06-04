"""
Trip + GpsLog + AttendanceRecord models — spec §6.4 / §6.5.

Trip:   school_id, route_id, driver_id, vehicle_id (all FK NOT NULL),
        status trip_status default 'scheduled', scheduled_date DATE,
        scheduled_departure_at TIMESTAMPTZ, slot VARCHAR(10) CHECK morning|evening,
        current_stop_order, started_at, ended_at, safeguarding_checked,
        original_driver_id (nullable FK), reassigned_at, reassignment_reason,
        timestamps.

GpsLog: partitioned table (PARTITION BY RANGE recorded_at).
        composite PK (id BIGSERIAL, recorded_at).
        The actual partitioned DDL is in migration 0007; this ORM model
        maps to the parent table for query purposes.
        SQLAlchemy NOTE: partitioned tables cannot have FK constraints on the
        parent table itself in PG < 12, but PG 16 supports them on parent.
        We reference trips(id) but DEFERRABLE is not needed for our read path.

AttendanceRecord: per-student boarding/absence record for a trip stop.
        UNIQUE(trip_id, student_id).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

TRIP_STATUS = (
    "scheduled",
    "in_progress",
    "pending_safeguard_check",
    "completed",
    "cancelled",
    "incident",
)


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        PGEnum(*TRIP_STATUS, name="trip_status", create_type=False),
        nullable=False,
        server_default="scheduled",
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_departure_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    slot: Mapped[str] = mapped_column(String(10), nullable=False)
    current_stop_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safeguarding_checked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    original_driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reassignment_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )


class GpsLog(Base):
    """
    ORM mapping for gps_logs — the actual table is PARTITIONED BY RANGE(recorded_at).
    Composite PK (id, recorded_at) matches what the migration creates.
    SQLAlchemy treats this as a regular table for INSERT/SELECT; partitioning
    is fully transparent to the ORM once the DDL is in place.
    """

    __tablename__ = "gps_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)


ATTENDANCE_STATUS = ("boarded", "absent", "absent_parent_marked")
DROP_TYPE = ("stop", "school")


class AttendanceRecord(Base):
    """
    Per-student boarding / absence record for one trip — spec §6.5.

    UNIQUE(trip_id, student_id) enforced at DB level.
    Upserted by the driver app when completing each stop.
    """

    __tablename__ = "attendance_records"

    __table_args__ = (
        UniqueConstraint("trip_id", "student_id", name="uq_att_trip_student"),
        Index("idx_att_trip_stop", "trip_id", "stop_id"),
        Index("idx_att_school_trip", "school_id", "trip_id"),
        Index("idx_att_student", "student_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    # stop_id: the pickup stop for this boarding record
    stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_stops.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        PGEnum(*ATTENDANCE_STATUS, name="attendance_status", create_type=False),
        nullable=False,
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    marked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # marked_location: GPS position at time of marking (optional)
    marked_location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    # Drop-off fields (Chunk 5B)
    drop_type: Mapped[str | None] = mapped_column(
        PGEnum(*DROP_TYPE, name="drop_type", create_type=False), nullable=True
    )
    drop_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_stops.id"), nullable=True
    )
    dropped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
