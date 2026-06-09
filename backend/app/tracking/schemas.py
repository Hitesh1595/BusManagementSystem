"""
Trip + GPS Pydantic schemas — spec §8.7.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.core.pagination import Page

TripStatusEnum = Literal[
    "scheduled",
    "in_progress",
    "pending_safeguard_check",
    "completed",
    "cancelled",
    "incident",
]
SlotEnum = Literal["morning", "evening"]


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class TripCreateIn(BaseModel):
    """Manual trip creation — admin."""

    route_id: uuid.UUID
    scheduled_date: date
    slot: SlotEnum


class TripGenerateIn(BaseModel):
    """Bulk generation — admin."""

    scheduled_date: date


# ---------------------------------------------------------------------------
# Nested sub-objects in TripOut
# ---------------------------------------------------------------------------


class DriverBrief(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str | None  # populated only via conditional disclosure in get_trip_detail()

    model_config = {"from_attributes": True}


class VehicleBrief(BaseModel):
    id: uuid.UUID
    plate_number: str

    model_config = {"from_attributes": True}


class RouteBrief(BaseModel):
    id: uuid.UUID
    name: str
    schedule_type: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Trip output
# ---------------------------------------------------------------------------


class TripOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    route_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    status: str
    scheduled_date: date
    scheduled_departure_at: datetime
    slot: str
    current_stop_order: int | None
    started_at: datetime | None
    ended_at: datetime | None
    safeguarding_checked: bool
    original_driver_id: uuid.UUID | None
    reassigned_at: datetime | None
    reassignment_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TripDetail(TripOut):
    """Enriched detail view — includes nested route, vehicle, driver."""

    route: RouteBrief | None = None
    vehicle: VehicleBrief | None = None
    driver: DriverBrief | None = None


TripPage = Page[TripOut]


# ---------------------------------------------------------------------------
# GPS log output (GeoJSON LineString)
# ---------------------------------------------------------------------------


class GpsLogGeoJSON(BaseModel):
    """
    Minimal GeoJSON Feature wrapping a LineString of the trip's GPS trace.
    """

    type: str = "Feature"
    geometry: dict[str, Any]
    properties: dict[str, Any]


# ---------------------------------------------------------------------------
# Generation result
# ---------------------------------------------------------------------------


class GenerateResult(BaseModel):
    created: int


# ---------------------------------------------------------------------------
# Attendance — request + response schemas (spec §8.8)
# ---------------------------------------------------------------------------

AttendanceStatusEnum = Literal["boarded", "absent", "absent_parent_marked"]


class AttendanceEntry(BaseModel):
    """One student's attendance status submitted by the driver."""

    student_id: uuid.UUID
    status: AttendanceStatusEnum


class AttendanceSubmitIn(BaseModel):
    """Body for POST /trips/{trip_id}/stops/{stop_id}/attendance."""

    attendance: list[AttendanceEntry]


class AttendanceResult(BaseModel):
    """Response from attendance submission."""

    processed: int
    alerts_triggered: int


class AttendanceRecordOut(BaseModel):
    """Single attendance record in the roster view."""

    student_id: uuid.UUID
    student_name: str
    stop_id: uuid.UUID | None
    status: str | None  # None if student has no record yet (unscanned)
    marked_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# End-trip result (safeguarding gate) — spec §10.2
# ---------------------------------------------------------------------------


class EndTripResult(BaseModel):
    status: str  # 'completed' | 'pending_safeguard_check'
    unresolved_students: list[str]  # list of student UUIDs as strings


# ---------------------------------------------------------------------------
# Drop-off schemas — spec §8.8
# ---------------------------------------------------------------------------

DropTypeEnum = Literal["stop", "school"]


class DropIn(BaseModel):
    """Body for POST /trips/{id}/drop."""

    student_ids: list[uuid.UUID]
    drop_type: DropTypeEnum
    stop_id: uuid.UUID | None = None  # required when drop_type='stop'


class DropResult(BaseModel):
    dropped: int


# ---------------------------------------------------------------------------
# Parent absent-marking schemas — spec §8.9
# ---------------------------------------------------------------------------


class AbsentMarkResult(BaseModel):
    student_id: uuid.UUID
    status: str  # 'absent_parent_marked' | 'cancelled'


class AbsenceListOut(BaseModel):
    student_id: uuid.UUID
    student_name: str
    stop_id: uuid.UUID | None
    marked_at: datetime | None

    model_config = {"from_attributes": True}
