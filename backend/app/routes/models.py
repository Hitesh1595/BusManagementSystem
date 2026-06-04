"""
Route + RouteStop models — spec §6.3.

Route:   school_id FK, name, description, vehicle_id FK nullable,
         driver_id FK nullable (→users), route_path geography(LineString,4326),
         schedule_type enum, version INT (optimistic lock), is_active, timestamps.

RouteStop: route_id FK ON DELETE CASCADE, name,
           location geography(Point,4326) NOT NULL, address,
           stop_order INT, arrival_time TIME, created_at,
           UNIQUE(route_id, stop_order).
           GIST index on location created in migration 0005.

NOTE: student_route_assignments and transport_requests are Part D (Task 3.4).
"""

from __future__ import annotations

import uuid
from datetime import datetime, time

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SCHEDULE_TYPE = ("morning", "evening", "both")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    route_path = mapped_column(
        Geography(geometry_type="LINESTRING", srid=4326), nullable=True
    )
    schedule_type: Mapped[str] = mapped_column(
        PGEnum(*SCHEDULE_TYPE, name="schedule_type", create_type=False),
        nullable=False,
        server_default="both",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )


class RouteStop(Base):
    __tablename__ = "route_stops"

    __table_args__ = (
        UniqueConstraint("route_id", "stop_order", name="uq_route_stop_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
