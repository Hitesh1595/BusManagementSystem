"""
Vehicle model — spec §6.3.

school_id FK → schools.id (tenant scoping).
plate_number is UNIQUE per school (UniqueConstraint).
vehicle_type uses DB enum 'vehicle_type' created in migration 0004.
capacity CHECK (capacity > 0) enforced at DB level.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

VEHICLE_TYPE = ("bus", "van", "minibus", "car", "other")


class Vehicle(Base):
    __tablename__ = "vehicles"

    __table_args__ = (
        UniqueConstraint("school_id", "plate_number", name="uq_vehicle_school_plate"),
        CheckConstraint("capacity > 0", name="ck_vehicle_capacity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    plate_number: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(
        PGEnum(*VEHICLE_TYPE, name="vehicle_type", create_type=False),
        nullable=False,
        server_default="bus",
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    insurance_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    fitness_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
