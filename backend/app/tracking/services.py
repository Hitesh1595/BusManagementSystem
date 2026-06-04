"""
Trip services — generation, CRUD, status transitions.

Key logic:
  generate_trips(db, school_id, scheduled_date):
    For each active route in the school that has driver_id AND vehicle_id
    AND school.settings.trip_autogen_enabled is not False:
      - 'morning' schedule_type → 1 trip (slot='morning')
      - 'evening' schedule_type → 1 trip (slot='evening')
      - 'both'    schedule_type → 2 trips (morning + evening)
    scheduled_departure_at = combine(scheduled_date, first-stop.arrival_time)
    interpreted in school.timezone, converted to UTC.
    Idempotent: INSERT ... ON CONFLICT (route_id, scheduled_date, slot) DO NOTHING.
    Returns {"created": n} counting only newly-inserted rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.crud import get_scoped_or_404
from app.errors import AppError
from app.routes.models import Route, RouteStop
from app.schools.models import School
from app.students.models import Student, StudentRouteAssignment
from app.tracking.models import AttendanceRecord, GpsLog, Trip
from app.tracking.schemas import (
    AttendanceRecordOut,
    DriverBrief,
    GpsLogGeoJSON,
    RouteBrief,
    TripDetail,
    TripOut,
    TripPage,
    VehicleBrief,
)
from app.vehicles.models import Vehicle

log = structlog.get_logger(__name__)

ACTIVE_STATUSES = ("scheduled", "in_progress", "pending_safeguard_check")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _combine_date_time_tz(d: date, t: time, tz_name: str) -> datetime:
    """
    Combine a date + time in the given timezone and return UTC datetime.
    Falls back to Asia/Kolkata if tz_name is invalid.
    """
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Asia/Kolkata")
    local_dt = datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, tzinfo=tz)
    return local_dt.astimezone(UTC)


async def _get_first_stop_arrival(db: AsyncSession, route_id: uuid.UUID) -> time | None:
    """Return arrival_time of the stop with the lowest stop_order for the route."""
    stmt = (
        select(RouteStop.arrival_time)
        .where(RouteStop.route_id == route_id)
        .order_by(RouteStop.stop_order.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _scheduled_departure(
    scheduled_date: date,
    arrival_time: time | None,
    school_tz: str,
) -> datetime:
    """
    Compute scheduled_departure_at from the first stop arrival_time.
    Falls back to 06:00 local time if no arrival_time is set.
    """
    t = arrival_time if arrival_time is not None else time(6, 0)
    return _combine_date_time_tz(scheduled_date, t, school_tz)


# ---------------------------------------------------------------------------
# generate_trips — idempotent bulk creation
# ---------------------------------------------------------------------------


async def generate_trips(
    db: AsyncSession,
    school_id: uuid.UUID,
    scheduled_date: date,
) -> dict[str, int]:
    """
    Generate trips for all eligible routes in the school for the given date.
    Returns {"created": n}.
    """
    # Load school for timezone + autogen setting
    school_stmt = select(School).where(School.id == school_id)
    school = (await db.execute(school_stmt)).scalar_one_or_none()
    if school is None:
        raise AppError("not_found", "School not found", 404)

    # Respect per-school autogen toggle (missing key → treat as enabled)
    if school.settings and school.settings.get("trip_autogen_enabled") is False:
        log.info("generate_trips.disabled", school_id=str(school_id))
        return {"created": 0}

    school_tz = school.timezone or "Asia/Kolkata"

    # Fetch active routes with both driver and vehicle assigned
    route_stmt = (
        select(Route)
        .where(
            and_(
                Route.school_id == school_id,
                Route.is_active.is_(True),
                Route.driver_id.isnot(None),
                Route.vehicle_id.isnot(None),
            )
        )
    )
    routes = (await db.execute(route_stmt)).scalars().all()

    if not routes:
        return {"created": 0}

    # Determine slot(s) per schedule_type
    def slots_for(schedule_type: str) -> list[str]:
        if schedule_type == "morning":
            return ["morning"]
        if schedule_type == "evening":
            return ["evening"]
        return ["morning", "evening"]  # 'both'

    created = 0
    for route in routes:
        arrival_time = await _get_first_stop_arrival(db, route.id)
        departure_at = _scheduled_departure(scheduled_date, arrival_time, school_tz)

        for slot in slots_for(route.schedule_type):
            # INSERT ... ON CONFLICT DO NOTHING (idempotent)
            stmt = (
                pg_insert(Trip)
                .values(
                    school_id=school_id,
                    route_id=route.id,
                    driver_id=route.driver_id,
                    vehicle_id=route.vehicle_id,
                    status="scheduled",
                    scheduled_date=scheduled_date,
                    scheduled_departure_at=departure_at,
                    slot=slot,
                    safeguarding_checked=False,
                )
                .on_conflict_do_nothing(
                    index_elements=["route_id", "scheduled_date", "slot"]
                )
            )
            result = await db.execute(stmt)
            created += result.rowcount

    await db.commit()
    log.info(
        "generate_trips.done",
        school_id=str(school_id),
        date=str(scheduled_date),
        created=created,
    )
    return {"created": created}


# ---------------------------------------------------------------------------
# Manual trip creation
# ---------------------------------------------------------------------------


async def create_trip(
    db: AsyncSession,
    school_id: uuid.UUID,
    route_id: uuid.UUID,
    scheduled_date: date,
    slot: str,
) -> TripOut:
    """
    Manual single-trip creation. Raises 404 if route not found/not eligible.
    Raises 409 if trip already exists for that (route, date, slot).
    """
    route = await get_scoped_or_404(db, Route, route_id, school_id)
    if not route.is_active:
        raise AppError("validation_error", "Route is not active", 422)
    if route.driver_id is None or route.vehicle_id is None:
        raise AppError("validation_error", "Route must have driver and vehicle assigned", 422)

    # Validate slot vs schedule_type
    if route.schedule_type == "morning" and slot != "morning":
        raise AppError("validation_error", "Route is morning-only", 422)
    if route.schedule_type == "evening" and slot != "evening":
        raise AppError("validation_error", "Route is evening-only", 422)

    school_stmt = select(School).where(School.id == school_id)
    school = (await db.execute(school_stmt)).scalar_one_or_none()
    school_tz = school.timezone if school else "Asia/Kolkata"

    arrival_time = await _get_first_stop_arrival(db, route_id)
    departure_at = _scheduled_departure(scheduled_date, arrival_time, school_tz)

    stmt = (
        pg_insert(Trip)
        .values(
            school_id=school_id,
            route_id=route_id,
            driver_id=route.driver_id,
            vehicle_id=route.vehicle_id,
            status="scheduled",
            scheduled_date=scheduled_date,
            scheduled_departure_at=departure_at,
            slot=slot,
            safeguarding_checked=False,
        )
        .on_conflict_do_nothing(index_elements=["route_id", "scheduled_date", "slot"])
        .returning(Trip)
    )
    result = (await db.execute(stmt)).scalar_one_or_none()
    if result is None:
        raise AppError("conflict", "Trip already exists for this route/date/slot", 409)

    await db.commit()

    # Reload to get the full ORM object (result is already the ORM Trip)
    await db.refresh(result)
    return TripOut.model_validate(result)


# ---------------------------------------------------------------------------
# List trips (paginated + filtered)
# ---------------------------------------------------------------------------


async def list_trips(
    db: AsyncSession,
    school_id: uuid.UUID | None,
    *,
    date_filter: date | None = None,
    route_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TripPage:
    stmt = select(Trip)
    if school_id is not None:
        stmt = stmt.where(Trip.school_id == school_id)
    if date_filter is not None:
        stmt = stmt.where(Trip.scheduled_date == date_filter)
    if route_id is not None:
        stmt = stmt.where(Trip.route_id == route_id)
    if status_filter is not None:
        stmt = stmt.where(Trip.status == status_filter)

    stmt = stmt.order_by(Trip.scheduled_departure_at.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return TripPage(
        items=[TripOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Get trip detail (with nested route/vehicle/driver)
# ---------------------------------------------------------------------------


async def get_trip_detail(
    db: AsyncSession,
    trip_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> TripDetail:
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    # Load related objects
    route = (await db.execute(select(Route).where(Route.id == trip.route_id))).scalar_one_or_none()
    vehicle = (
        await db.execute(select(Vehicle).where(Vehicle.id == trip.vehicle_id))
    ).scalar_one_or_none()
    driver = (
        await db.execute(select(User).where(User.id == trip.driver_id))
    ).scalar_one_or_none()

    detail = TripDetail.model_validate(trip)
    if route:
        detail.route = RouteBrief.model_validate(route)
    if vehicle:
        detail.vehicle = VehicleBrief.model_validate(vehicle)
    if driver:
        # phone: null for now — conditional disclosure is Chunk 5
        detail.driver = DriverBrief(
            id=driver.id,
            full_name=driver.full_name,
            phone=None,
        )
    return detail


# ---------------------------------------------------------------------------
# Active trips (admin dashboard)
# ---------------------------------------------------------------------------


async def list_active_trips(
    db: AsyncSession,
    school_id: uuid.UUID | None,
) -> list[TripOut]:
    stmt = select(Trip).where(Trip.status.in_(ACTIVE_STATUSES))
    if school_id is not None:
        stmt = stmt.where(Trip.school_id == school_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [TripOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# GPS log — historical trace as GeoJSON LineString
# ---------------------------------------------------------------------------


async def get_gps_log(
    db: AsyncSession,
    trip_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> GpsLogGeoJSON:
    # Verify trip access
    await get_scoped_or_404(db, Trip, trip_id, school_id)

    # Fetch ordered GPS points
    stmt = (
        select(
            ST_AsGeoJSON(GpsLog.location).label("geojson"),
            GpsLog.recorded_at,
            GpsLog.speed,
            GpsLog.heading,
        )
        .where(GpsLog.trip_id == trip_id)
        .order_by(GpsLog.recorded_at.asc())
    )
    rows = (await db.execute(stmt)).all()

    # Build coordinates list [[lng, lat], ...]
    import json

    coords: list[list[float]] = []
    for row in rows:
        pt = json.loads(row.geojson)
        coords.append(pt["coordinates"])  # [lng, lat]

    if len(coords) < 2:
        geometry: dict[str, Any] = {"type": "LineString", "coordinates": coords}
    else:
        geometry = {"type": "LineString", "coordinates": coords}

    return GpsLogGeoJSON(
        type="Feature",
        geometry=geometry,
        properties={
            "trip_id": str(trip_id),
            "point_count": len(coords),
        },
    )


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


async def start_trip(
    db: AsyncSession,
    trip_id: uuid.UUID,
    school_id: uuid.UUID | None,
    driver_user_id: uuid.UUID,
) -> TripOut:
    """
    Driver starts a trip: scheduled → in_progress.
    Enforces ownership: trip.driver_id must equal driver_user_id.
    After commit, populates Redis caches (best-effort; trip still starts on failure).
    """
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    # Ownership check
    if trip.driver_id != driver_user_id:
        raise AppError("forbidden", "You are not assigned to this trip", 403)

    if trip.status != "scheduled":
        raise AppError(
            "conflict",
            f"Trip cannot be started from status '{trip.status}'",
            409,
        )

    trip.status = "in_progress"
    trip.started_at = datetime.now(UTC)
    trip.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(trip)

    # ------------------------------------------------------------------
    # Populate Redis caches (best-effort — failure must not block the trip)
    # ------------------------------------------------------------------
    await _populate_trip_redis_cache(db, trip)

    return TripOut.model_validate(trip)


async def _populate_trip_redis_cache(db: AsyncSession, trip: Trip) -> None:
    """
    Write two Redis keys so the Socket.IO GPS hot path avoids DB hits:

      trip:stops:{trip_id}   — JSON list of {stop_id, lat, lng, order}
      trip:driver:{trip_id}  — str(driver_id)

    Uses ST_X / ST_Y to extract coordinates from the geography column.
    Skips silently if Redis is unavailable.
    """
    import json

    from geoalchemy2.functions import ST_X, ST_Y

    from app.redis_client import get_redis

    try:
        r = get_redis()

        # Build stop list ordered by stop_order
        stmt = (
            select(
                RouteStop.id,
                RouteStop.stop_order,
                ST_X(RouteStop.location).label("lng"),
                ST_Y(RouteStop.location).label("lat"),
            )
            .where(RouteStop.route_id == trip.route_id)
            .order_by(RouteStop.stop_order.asc())
        )
        rows = (await db.execute(stmt)).all()

        stops = [
            {
                "stop_id": str(row.id),
                "order": row.stop_order,
                "lat": float(row.lat),
                "lng": float(row.lng),
            }
            for row in rows
        ]

        trip_id_str = str(trip.id)

        await r.set(f"trip:stops:{trip_id_str}", json.dumps(stops))
        await r.set(f"trip:driver:{trip_id_str}", str(trip.driver_id))

        log.info(
            "start_trip.redis_cache_populated",
            trip_id=trip_id_str,
            stops=len(stops),
        )
    except Exception as exc:
        log.warning(
            "start_trip.redis_cache_failed",
            trip_id=str(trip.id),
            exc=str(exc),
        )


async def cancel_trip(
    db: AsyncSession,
    trip_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> TripOut:
    """Admin cancels a trip."""
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    if trip.status in ("completed", "cancelled"):
        raise AppError(
            "conflict",
            f"Trip is already {trip.status}",
            409,
        )

    trip.status = "cancelled"
    trip.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(trip)
    return TripOut.model_validate(trip)


# ---------------------------------------------------------------------------
# Attendance roster queries
# ---------------------------------------------------------------------------


async def get_trip_attendance(
    db: AsyncSession,
    trip_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> list[AttendanceRecordOut]:
    """
    Return all assigned students for the trip's route, joined with their
    attendance record (None fields when no record exists yet).
    """
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    # All active assignments for this route (across all stops)
    assignment_rows = (
        await db.execute(
            select(StudentRouteAssignment).where(
                and_(
                    StudentRouteAssignment.route_id == trip.route_id,
                    StudentRouteAssignment.is_active.is_(True),
                )
            )
        )
    ).scalars().all()

    student_ids = [r.student_id for r in assignment_rows]
    stop_id_by_student = {r.student_id: r.stop_id for r in assignment_rows}

    if not student_ids:
        return []

    # Load students (single IN query)
    students = {
        s.id: s
        for s in (
            await db.execute(select(Student).where(Student.id.in_(student_ids)))
        ).scalars().all()
    }

    # Load existing attendance records (single IN query)
    att_rows = {
        r.student_id: r
        for r in (
            await db.execute(
                select(AttendanceRecord).where(
                    and_(
                        AttendanceRecord.trip_id == trip.id,
                        AttendanceRecord.student_id.in_(student_ids),
                    )
                )
            )
        ).scalars().all()
    }

    result = []
    for sid in student_ids:
        student = students.get(sid)
        att = att_rows.get(sid)
        result.append(
            AttendanceRecordOut(
                student_id=sid,
                student_name=student.full_name if student else str(sid),
                stop_id=att.stop_id if att else stop_id_by_student.get(sid),
                status=att.status if att else None,
                marked_at=att.marked_at if att else None,
            )
        )
    return result


async def get_stop_attendance(
    db: AsyncSession,
    trip_id: uuid.UUID,
    stop_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> list[AttendanceRecordOut]:
    """
    Return attendance records scoped to a specific stop.
    Only students assigned to that stop are included.
    """
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    assignment_rows = (
        await db.execute(
            select(StudentRouteAssignment).where(
                and_(
                    StudentRouteAssignment.route_id == trip.route_id,
                    StudentRouteAssignment.stop_id == stop_id,
                    StudentRouteAssignment.is_active.is_(True),
                )
            )
        )
    ).scalars().all()

    student_ids = [r.student_id for r in assignment_rows]

    if not student_ids:
        return []

    students = {
        s.id: s
        for s in (
            await db.execute(select(Student).where(Student.id.in_(student_ids)))
        ).scalars().all()
    }

    att_rows = {
        r.student_id: r
        for r in (
            await db.execute(
                select(AttendanceRecord).where(
                    and_(
                        AttendanceRecord.trip_id == trip.id,
                        AttendanceRecord.student_id.in_(student_ids),
                        AttendanceRecord.stop_id == stop_id,
                    )
                )
            )
        ).scalars().all()
    }

    result = []
    for sid in student_ids:
        student = students.get(sid)
        att = att_rows.get(sid)
        result.append(
            AttendanceRecordOut(
                student_id=sid,
                student_name=student.full_name if student else str(sid),
                stop_id=stop_id,
                status=att.status if att else None,
                marked_at=att.marked_at if att else None,
            )
        )
    return result


async def end_trip(
    db: AsyncSession,
    trip_id: uuid.UUID,
    school_id: uuid.UUID | None,
    driver_user_id: uuid.UUID,
) -> TripOut:
    """
    Driver ends a trip.
    STUB: sets status=completed directly.
    TODO(chunk-5): safeguarding gate — check all students accounted for,
    transition to pending_safeguard_check if needed.
    """
    trip = await get_scoped_or_404(db, Trip, trip_id, school_id)

    # Ownership check
    if trip.driver_id != driver_user_id:
        raise AppError("forbidden", "You are not assigned to this trip", 403)

    if trip.status != "in_progress":
        raise AppError(
            "conflict",
            f"Trip cannot be ended from status '{trip.status}'",
            409,
        )

    # TODO(chunk-5): safeguarding gate
    trip.status = "completed"
    trip.ended_at = datetime.now(UTC)
    trip.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(trip)
    return TripOut.model_validate(trip)
