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
from app.routes.schemas import StopOut
from app.tracking import services
from app.tracking.schemas import (
    AbsenceListOut,
    AbsentMarkResult,
    AttendanceRecordOut,
    AttendanceResult,
    AttendanceSubmitIn,
    DropIn,
    DropResult,
    EndTripResult,
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
_ParentDep = Annotated[dict, Depends(require_role("parent"))]


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
# Get trip detail (any authenticated role) — with conditional driver phone
# ---------------------------------------------------------------------------


@router.get("/{trip_id}")
async def get_trip(
    trip_id: UUID,
    db: DbDep,
    claims: _AnyAuthDep,
    school_id: SchoolScopeDep,
) -> TripDetail:
    """
    Return trip detail including route, vehicle, driver.

    driver.phone is returned ONLY IF:
      - requester role is 'parent'
      - trip.status == 'in_progress'
      - school.settings.driver_phone_visible == true
      - the requester is the parent of at least one student assigned to the trip

    On disclosure an audit_logs row is written.
    """
    return await services.get_trip_detail(
        db,
        trip_id,
        school_id,
        requester_claims=claims,
    )


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
# Trip stops (any trip viewer) — drives driver run-trip + parent live-track maps
# ---------------------------------------------------------------------------


@router.get("/{trip_id}/stops")
async def get_trip_stops(
    trip_id: UUID,
    db: DbDep,
    claims: _AnyAuthDep,
    school_id: SchoolScopeDep,
) -> list[StopOut]:
    """Return the ordered stops of the trip's route."""
    return await services.get_trip_stops(db, trip_id, school_id)


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
# Driver: end trip — safeguarding gate (Chunk 5B)
# ---------------------------------------------------------------------------


@router.put("/{trip_id}/end")
async def end_trip(
    trip_id: UUID,
    db: DbDep,
    claims: _DriverDep,
    school_id: SchoolScopeDep,
) -> EndTripResult:
    """
    Driver ends a trip — runs the safeguarding gate (spec §10.2).

    Returns {status, unresolved_students}.
    If all students accounted for → status='completed'.
    If any boarded-not-dropped → status='pending_safeguard_check' + alert IDs.
    """
    from app.core.socketio import sio

    driver_user_id = UUID(claims["sub"])
    result = await services.end_trip(db, trip_id, school_id, driver_user_id, sio=sio)
    return EndTripResult(**result)


# ---------------------------------------------------------------------------
# Driver: drop students (POST /trips/{id}/drop)
# ---------------------------------------------------------------------------


@router.post("/{trip_id}/drop")
async def drop_students(
    trip_id: UUID,
    body: DropIn,
    db: DbDep,
    claims: _DriverDep,
    school_id: SchoolScopeDep,
) -> DropResult:
    """
    Driver marks students as dropped off — spec §8.8 / §10.2.

    Body: {student_ids:[...], drop_type:"school"} (morning, one tap)
       or {student_ids:[...], drop_type:"stop", stop_id:<uuid>}

    Auto-resolves matching child_not_dropped alerts and completes the
    trip if all students are now accounted for.
    """
    from app.core.socketio import sio
    from app.crud import get_scoped_or_404
    from app.tracking.models import Trip
    from app.tracking.safety import drop_students as _drop

    driver_user_id = UUID(claims["sub"])
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    if trip.driver_id != driver_user_id:
        raise AppError("forbidden", "You are not assigned to this trip", 403)

    if trip.status not in ("in_progress", "pending_safeguard_check"):
        raise AppError(
            "conflict",
            f"Cannot drop students for a trip with status '{trip.status}'",
            409,
        )

    if body.drop_type == "stop" and body.stop_id is None:
        raise AppError("validation_error", "stop_id is required when drop_type='stop'", 422)

    result = await _drop(
        db,
        sio,
        trip_id,
        body.student_ids,
        body.drop_type,
        drop_stop_id=body.stop_id,
    )
    return DropResult(dropped=result["dropped"])


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


# ---------------------------------------------------------------------------
# Parent: pre-mark absent (spec §8.9 / §10.3)
# ---------------------------------------------------------------------------


@router.post("/{trip_id}/absent/{student_id}", status_code=200)
async def mark_absent(
    trip_id: UUID,
    student_id: UUID,
    db: DbDep,
    claims: _ParentDep,
    school_id: SchoolScopeDep,
) -> AbsentMarkResult:
    """
    Parent pre-marks their child absent for an upcoming trip.

    Allowed ONLY if trip.status == 'scheduled' (before driver starts).
    403 if the student is not the parent's child.
    409 if trip already in_progress or later.
    """
    from app.core.socketio import sio

    parent_id = UUID(claims["sub"])
    return await services.mark_student_absent(
        db, sio, trip_id, student_id, parent_id, school_id
    )


@router.delete("/{trip_id}/absent/{student_id}", status_code=200)
async def cancel_absent(
    trip_id: UUID,
    student_id: UUID,
    db: DbDep,
    claims: _ParentDep,
    school_id: SchoolScopeDep,
) -> AbsentMarkResult:
    """
    Parent cancels a pre-marked absence.

    Allowed only if trip is still 'scheduled'.
    """
    parent_id = UUID(claims["sub"])
    return await services.cancel_student_absent(
        db, trip_id, student_id, parent_id, school_id
    )


# ---------------------------------------------------------------------------
# Driver: list pre-marked absences for a trip (spec §8.9)
# ---------------------------------------------------------------------------


@router.get("/{trip_id}/absences")
async def list_absences(
    trip_id: UUID,
    db: DbDep,
    claims: _DriverDep,
    school_id: SchoolScopeDep,
) -> list[AbsenceListOut]:
    """Driver retrieves list of parent-pre-marked absences for this trip."""
    driver_user_id = UUID(claims["sub"])
    return await services.list_trip_absences(db, trip_id, school_id, driver_user_id)
