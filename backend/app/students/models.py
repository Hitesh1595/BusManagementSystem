"""
Student, StudentRouteAssignment, TransportRequest models — spec §6.2/§6.3.

Student:
  parent_id FK → users (owner), school_id FK,
  full_name, grade, section, pickup_address,
  pickup_location geography(Point,4326), is_active, timestamps.
  Indexes: idx_students_parent (btree), idx_students_pickup (GIST).

StudentRouteAssignment:
  school_id, student_id FK, route_id FK, stop_id FK → route_stops,
  assigned_at, is_active.
  UNIQUE(student_id, route_id).
  Partial index idx_sra_route (route_id, stop_id) WHERE is_active.

TransportRequest:
  school_id, parent_id FK, student_id FK,
  pickup_address, pickup_location geography(Point,4326),
  status enum request_status default 'pending',
  assigned_route_id FK nullable, assigned_stop_id FK nullable,
  admin_notes, timestamps.
  Index idx_treq_school_status (school_id, status).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

REQUEST_STATUS = ("pending", "approved", "rejected", "assigned")


class Student(Base):
    __tablename__ = "students"

    __table_args__ = (
        Index("idx_students_parent", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    section: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pickup_location: GIST index created in migration
    pickup_location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )


class StudentRouteAssignment(Base):
    __tablename__ = "student_route_assignments"

    __table_args__ = (
        UniqueConstraint("student_id", "route_id", name="uq_sra_student_route"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False
    )
    stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_stops.id"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class TransportRequest(Base):
    __tablename__ = "transport_requests"

    __table_args__ = (
        Index("idx_treq_school_status", "school_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pickup_location geography(Point,4326) — column added via raw DDL in migration
    pickup_location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    status: Mapped[str] = mapped_column(
        PGEnum(*REQUEST_STATUS, name="request_status", create_type=False),
        nullable=False,
        server_default="pending",
    )
    assigned_route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=True
    )
    assigned_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_stops.id"), nullable=True
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
