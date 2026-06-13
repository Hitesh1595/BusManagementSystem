"""
Feedback + complaints models (spec §6.7, V2).

  TripFeedback — a parent rates a completed trip (1-5 + comment). Auto-flagged
                 when rating <= 2. Driver sees aggregate only (OQ-15); admin
                 sees full text and can review.
  Complaint    — a parent or driver raises an issue against a driver/route/
                 vehicle/general; school_admin triages and resolves.

Enums (complaint_against, complaint_status, priority) were created in migration
0001 (V2 enums). Both tables carry school_id and are enrolled in RLS (0011).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, CreatedAtMixin, TimestampMixin

COMPLAINT_AGAINST = ("driver", "route", "vehicle", "general")
COMPLAINT_STATUS = ("open", "in_review", "resolved", "closed")
PRIORITY = ("low", "medium", "high", "urgent")


class TripFeedback(Base, CreatedAtMixin):
    __tablename__ = "trip_feedback"
    __table_args__ = (
        UniqueConstraint("trip_id", "parent_id", name="uq_feedback_trip_parent"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        Index("idx_feedback_driver", "driver_id", "created_at"),
        Index("idx_feedback_flag", "school_id", "is_flagged", "admin_reviewed"),
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
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    admin_reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"
    __table_args__ = (
        Index("idx_complaint_school", "school_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    against_type: Mapped[str] = mapped_column(
        PGEnum(*COMPLAINT_AGAINST, name="complaint_against", create_type=False),
        nullable=False,
    )
    against_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=True
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        PGEnum(*COMPLAINT_STATUS, name="complaint_status", create_type=False),
        nullable=False,
        server_default="open",
    )
    priority: Mapped[str] = mapped_column(
        PGEnum(*PRIORITY, name="priority", create_type=False),
        nullable=False,
        server_default="medium",
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
