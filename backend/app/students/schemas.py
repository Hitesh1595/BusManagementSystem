"""
Student + transport-request Pydantic schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, Field

from app.core.pagination import Page

RequestStatusEnum = Literal["pending", "approved", "rejected", "assigned"]


# ---------------------------------------------------------------------------
# Location sub-schema (shared with routes)
# ---------------------------------------------------------------------------


class LatLng(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


# ---------------------------------------------------------------------------
# Student schemas
# ---------------------------------------------------------------------------


class StudentIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    grade: str | None = Field(default=None, max_length=20)
    section: str | None = Field(default=None, max_length=20)
    pickup_address: str | None = None
    pickup_location: LatLng | None = None


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    grade: str | None = Field(default=None, max_length=20)
    section: str | None = Field(default=None, max_length=20)
    pickup_address: str | None = None
    pickup_location: LatLng | None = None
    is_active: bool | None = None


class StudentOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    parent_id: uuid.UUID
    full_name: str
    grade: str | None
    section: str | None
    pickup_address: str | None
    pickup_location: LatLng | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


StudentPage = Page[StudentOut]


# ---------------------------------------------------------------------------
# StudentRouteAssignment schemas
# ---------------------------------------------------------------------------


class AssignStudentIn(BaseModel):
    """Body for POST /routes/{id}/students — assign a student to route+stop."""

    student_id: uuid.UUID
    stop_id: uuid.UUID


class AssignmentOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    route_id: uuid.UUID
    stop_id: uuid.UUID
    assigned_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


AssignmentPage = Page[AssignmentOut]


# ---------------------------------------------------------------------------
# TransportRequest schemas
# ---------------------------------------------------------------------------


class TransportRequestIn(BaseModel):
    student_id: uuid.UUID
    pickup_address: str | None = None
    pickup_location: LatLng | None = None


class TransportRequestUpdate(BaseModel):
    status: RequestStatusEnum
    assigned_route_id: uuid.UUID | None = None
    assigned_stop_id: uuid.UUID | None = None
    admin_notes: str | None = None


class TransportRequestOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    parent_id: uuid.UUID
    student_id: uuid.UUID
    pickup_address: str | None
    pickup_location: LatLng | None
    status: str
    assigned_route_id: uuid.UUID | None
    assigned_stop_id: uuid.UUID | None
    admin_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


TransportRequestPage = Page[TransportRequestOut]


# ---------------------------------------------------------------------------
# Suggest-stop response
# ---------------------------------------------------------------------------


class StopSuggestion(BaseModel):
    stop_id: uuid.UUID
    route_id: uuid.UUID
    name: str
    distance_m: int
    arrival_time: time | None


class SuggestStopOut(BaseModel):
    suggestions: list[StopSuggestion]
