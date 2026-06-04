"""
Alert model — spec §6.5.

school_id FK → schools.id (tenant scoping).
trip_id FK → trips.id (nullable — some alerts are not trip-specific).
type uses DB enum 'alert_type' (created in migration 0001).
severity uses DB enum 'alert_severity' (created in migration 0001).
location geography(Point,4326) nullable — GPS location of event.
metadata JSONB default '{}' — e.g. {student_id, stop_id}.

Indexes:
  idx_alerts_school_sev   (school_id, severity, created_at DESC)
  idx_alerts_trip_unresolved (trip_id) WHERE resolved_at IS NULL  ← partial
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ALERT_TYPE = (
    "child_not_boarded",
    "child_not_dropped",
    "driver_no_show",
    "sos",
    "route_deviation",
    "incident",
    "insurance_expiry",
    "driver_behavior_pattern",
)
ALERT_SEVERITY = ("critical", "high", "medium", "low")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(
        PGEnum(*ALERT_TYPE, name="alert_type", create_type=False),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        PGEnum(*ALERT_SEVERITY, name="alert_severity", create_type=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
