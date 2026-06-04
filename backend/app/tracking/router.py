"""
Trips router — /api/v1/trips

RBAC:
  admin endpoints  → require school_admin | super_admin
  driver endpoints → require driver + ownership (trip.driver_id == current user)
  read endpoints   → authenticated (any role)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import DbDep, SchoolScopeDep, require_role
from app.errors import AppError
from app.tracking import services
from app.tracking.schemas import (
    AttendanceRecordOut,
    AttendanceResult,
    AttendanceSubmitIn,
    GenerateResult,
    GpsLogGeoJSON,
    TripCreateIn,
    TripDetail,
    TripGenerateIn,
    TripOut,
    TripPage,
)

router = APIRouter(prefix="/api/v1/trips", tags=["trips"])

# Role gate type aliases
_AdminDep = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]
_DriverDep = Annotated[dict, Depends(require_role("driver"))]
_AnyAuthDep = Annotated[
    dict, Depends(require_role("school_admin", "super_admin", "driver", "parent"))
]


# ---------------------------------------------------------------------------
# Admin: manual create
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_trip(
    body: TripCreateIn,
    db: DbDep,
    claims: _AdminDep,
    school_id: SchoolScopeDep,
) -> TripOut:
    """Manually create a single trip (admin)."""
    if school_id is None:
        raise AppError("forbidden", "super_admin must scope to a school", 403)
    return await services.create_trip(
        db,
        school_id=school_id,
        route_id=body.route_id,
        scheduled_date=body.scheduled_date,
        slot=body.slot,
    )


# ---------------------------------------------------------------------------
# Admin: bulk generation
# ---------------------------------------------------------------------------


@router.post("/generate")
async def generate_trips(
    body: TripGenerateIn,
    db: DbDep,
    claims: _AdminDep,
    school_id: SchoolScopeDep,
) -> GenerateResult:
    """Generate trips for all eligible routes on the given date (idempotent)."""
    if school_id is None:
        raise AppError("forbidden", "super_admin must scope to a school", 403)
    result = await services.generate_trips(db, school_id, body.scheduled_date)
    return GenerateResult(created=result["created"])


# ---------------------------------------------------------------------------
# Admin: active trips dashboard
# NOTE: must be declared BEFORE /{id} to avoid ambiguity
# ---------------------------------------------------------------------------


@router.get("/active")
async def list_active_trips(
    db: DbDep,
    claims: _AdminDep,
    school_id: SchoolScopeDep,
) -> list[TripOut]:
    """Return all active trips (scheduled/in_progress/pending) for the school."""
    return await services.list_active_trips(db, school_id)


# ---------------------------------------------------------------------------
# List trips (any authenticated role)
# ---------------------------------------------------------------------------


@router.get("/")
async def list_trips(
    db: DbDep,
    claims: _AnyAuthDep,
    school_id: SchoolScopeDep,
    date: Annotated[str | None, Query(description="Filter by date (YYYY-MM-DD)")] = None,
    route_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TripPage:
    from datetime import date as DateType

    date_filter = DateType.fromisoformat(date) if date else None
    return await services.list_trips(
        db,
        school_id=school_id,
        date_filter=date_filter,
        route_id=route_id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Get trip detail (any authenticated role)
# ---------------------------------------------------------------------------


@router.get("/{trip_id}")
async def get_trip(
    trip_id: UUID,
    db: DbDep,
    claims: _AnyAuthDep,
    school_id: SchoolScopeDep,
) -> TripDetail:
    """Return trip detail including route, vehicle.plate_number, driver (phone=null)."""
    return await services.get_trip_detail(db, trip_id, school_id)


# ---------------------------------------------------------------------------
# GPS log (any authenticated role)
# ---------------------------------------------------------------------------


@router.get("/{trip_id}/gps-log")
async def get_gps_log(
    trip_id: UUID,
    db: DbDep,
    claims: _AnyAuthDep,
    school_id: SchoolScopeDep,
) -> GpsLogGeoJSON:
    """Return historical GPS trace as GeoJSON LineString."""
    return await services.get_gps_log(db, trip_id, school_id)


# ---------------------------------------------------------------------------
# Driver: start trip
# ---------------------------------------------------------------------------


@router.put("/{trip_id}/start")
async def start_trip(
    trip_id: UUID,
    db: DbDep,
    claims: _DriverDep,
    school_id: SchoolScopeDep,
) -> TripOut:
    """Driver starts a trip: scheduled → in_progress. Must be own trip."""
    driver_user_id = UUID(claims["sub"])
    return await services.start_trip(db, trip_id, school_id, driver_user_id)


# ---------------------------------------------------------------------------
# Driver: end trip
# ---------------------------------------------------------------------------


@router.put("/{trip_id}/end")
async def end_trip(
    trip_id: UUID,
    db: DbDep,
    claims: _DriverDep,
    school_id: SchoolScopeDep,
) -> TripOut:
    """Driver ends a trip (stub — safeguarding gate is Chunk 5)."""
    driver_user_id = UUID(claims["sub"])
    return await services.end_trip(db, trip_id, school_id, driver_user_id)


# ---------------------------------------------------------------------------
# Admin: cancel trip
# ---------------------------------------------------------------------------


@router.put("/{trip_id}/cancel")
async def cancel_trip(
    trip_id: UUID,
    db: DbDep,
    claims: _AdminDep,
    school_id: SchoolScopeDep,
) -> TripOut:
    """Admin cancels a trip."""
    return await services.cancel_trip(db, trip_id, school_id)


# ---------------------------------------------------------------------------
# Driver: submit stop attendance
# ---------------------------------------------------------------------------


@router.post("/{trip_id}/stops/{stop_id}/attendance")
async def submit_stop_attendance(
    trip_id: UUID,
    stop_id: UUID,
    body: AttendanceSubmitIn,
    db: DbDep,
    claims: _DriverDep,
    school_id: SchoolScopeDep,
) -> AttendanceResult:
    """
    Driver submits boarding attendance for a stop.
    Only the assigned driver can submit (ownership check).
    Triggers not-boarded alerts for absent unexcused students.
    """
    from app.core.socketio import sio
    from app.crud import get_scoped_or_404
    from app.tracking.models import Trip
    from app.tracking.safety import process_stop_attendance

    driver_user_id = UUID(claims["sub"])
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    if trip.driver_id != driver_user_id:
        raise AppError("forbidden", "You are not assigned to this trip", 403)

    entries = [
        {"student_id": e.student_id, "status": e.status}
        for e in body.attendance
    ]
    result = await process_stop_attendance(db, sio, trip, stop_id, entries)
    return AttendanceResult(**result)


# ---------------------------------------------------------------------------
# Attendance roster — full trip
# ---------------------------------------------------------------------------


@router.get("/{trip_id}/attendance")
async def get_trip_attendance(
    trip_id: UUID,
    db: DbDep,
    claims: _AnyAuthDep,
    school_id: SchoolScopeDep,
) -> list[AttendanceRecordOut]:
    """
    Return the full attendance roster for a trip — all assigned students
    joined with their current attendance record (if any).
    """
    return await services.get_trip_attendance(db, trip_id, school_id)


# ---------------------------------------------------------------------------
# Attendance roster — per stop
# ---------------------------------------------------------------------------


@router.get("/{trip_id}/stops/{stop_id}/attendance")
async def get_stop_attendance(
    trip_id: UUID,
    stop_id: UUID,
    db: DbDep,
    claims: _AnyAuthDep,
    school_id: SchoolScopeDep,
) -> list[AttendanceRecordOut]:
    """
    Return attendance records scoped to a specific stop of a trip.
    Only students assigned to that stop are included.
    """
    return await services.get_stop_attendance(db, trip_id, stop_id, school_id)
