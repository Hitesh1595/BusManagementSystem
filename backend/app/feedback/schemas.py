"""Feedback + complaints schemas (spec §8.13)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import Page

# ---------------------------------------------------------------------------
# Trip feedback
# ---------------------------------------------------------------------------


class FeedbackCreateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackReviewIn(BaseModel):
    admin_notes: str | None = Field(default=None, max_length=2000)
    is_flagged: bool | None = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    parent_id: uuid.UUID
    driver_id: uuid.UUID
    rating: int
    comment: str | None
    is_flagged: bool
    admin_reviewed: bool
    admin_notes: str | None
    created_at: datetime


FeedbackPage = Page[FeedbackOut]


class DriverRatingOut(BaseModel):
    """Aggregate only — what a driver is allowed to see about their feedback (OQ-15)."""

    average: float | None
    count: int


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------

ComplaintAgainst = Literal["driver", "route", "vehicle", "general"]
ComplaintStatus = Literal["open", "in_review", "resolved", "closed"]


class ComplaintCreateIn(BaseModel):
    against_type: ComplaintAgainst
    against_id: uuid.UUID | None = None
    trip_id: uuid.UUID | None = None
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)


class ComplaintAssignIn(BaseModel):
    assigned_to: uuid.UUID


class ComplaintResolveIn(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class ComplaintStatusIn(BaseModel):
    status: ComplaintStatus


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submitted_by: uuid.UUID
    against_type: str
    against_id: uuid.UUID | None
    trip_id: uuid.UUID | None
    subject: str
    description: str
    status: str
    priority: str
    assigned_to: uuid.UUID | None
    resolution_notes: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


ComplaintPage = Page[ComplaintOut]
