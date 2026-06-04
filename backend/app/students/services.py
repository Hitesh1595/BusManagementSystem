"""
Student + transport-request service layer.

Key behaviours:
  - Students are parent-owned (parent_id = current user for parents).
  - school_id is inferred from the parent's User record on creation.
  - Admins see all students in their school; parents see only their own.
  - TransportRequest: parents create (pending); admin updates status.
  - On status='assigned': capacity-checked StudentRouteAssignment created
    in the same transaction.
  - suggest_stops: PostGIS ST_Distance ordered top-3 within active routes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from geoalchemy2.functions import ST_Distance
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import from_point, to_point
from app.core.pagination import paginate
from app.crud import get_scoped_or_404
from app.errors import AppError
from app.routes.models import Route, RouteStop
from app.students.models import Student, StudentRouteAssignment, TransportRequest
from app.students.schemas import (
    AssignmentOut,
    AssignmentPage,  # noqa: F401  (re-exported for route router)
    LatLng,
    StudentIn,
    StudentOut,
    StudentPage,
    StudentUpdate,
    TransportRequestIn,
    TransportRequestOut,
    TransportRequestPage,
    TransportRequestUpdate,
)
from app.vehicles.models import Vehicle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _loc_to_latlng(geom) -> LatLng | None:
    if geom is None:
        return None
    loc = from_point(geom)
    if loc is None:
        return None
    return LatLng(lat=loc["lat"], lng=loc["lng"])


def _student_out(s: Student) -> StudentOut:
    return StudentOut(
        id=s.id,
        school_id=s.school_id,
        parent_id=s.parent_id,
        full_name=s.full_name,
        grade=s.grade,
        section=s.section,
        pickup_address=s.pickup_address,
        pickup_location=_loc_to_latlng(s.pickup_location),
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _treq_out(r: TransportRequest) -> TransportRequestOut:
    return TransportRequestOut(
        id=r.id,
        school_id=r.school_id,
        parent_id=r.parent_id,
        student_id=r.student_id,
        pickup_address=r.pickup_address,
        pickup_location=_loc_to_latlng(r.pickup_location),
        status=r.status,
        assigned_route_id=r.assigned_route_id,
        assigned_stop_id=r.assigned_stop_id,
        admin_notes=r.admin_notes,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


# ---------------------------------------------------------------------------
# Student CRUD
# ---------------------------------------------------------------------------


async def create_student(
    db: AsyncSession,
    payload: StudentIn,
    parent_id: uuid.UUID,
    school_id: uuid.UUID,
) -> StudentOut:
    loc = (
        to_point(payload.pickup_location.lat, payload.pickup_location.lng)
        if payload.pickup_location
        else None
    )
    student = Student(
        school_id=school_id,
        parent_id=parent_id,
        full_name=payload.full_name,
        grade=payload.grade,
        section=payload.section,
        pickup_address=payload.pickup_address,
        pickup_location=loc,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return _student_out(student)


async def list_students(
    db: AsyncSession,
    school_id: uuid.UUID,
    parent_id: uuid.UUID | None,  # None means admin (see all)
    limit: int = 50,
    offset: int = 0,
) -> StudentPage:
    stmt = select(Student).where(Student.school_id == school_id, Student.is_active.is_(True))
    if parent_id is not None:
        stmt = stmt.where(Student.parent_id == parent_id)
    result = await paginate(stmt, db, limit=limit, offset=offset)
    return StudentPage(
        items=[_student_out(s) for s in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def get_student(
    db: AsyncSession,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    parent_id: uuid.UUID | None,  # None means admin
) -> StudentOut:
    stmt = select(Student).where(Student.id == student_id, Student.school_id == school_id)
    if parent_id is not None:
        stmt = stmt.where(Student.parent_id == parent_id)
    student = (await db.execute(stmt)).scalar_one_or_none()
    if student is None:
        raise AppError("not_found", "Student not found", 404)
    return _student_out(student)


async def update_student(
    db: AsyncSession,
    student_id: uuid.UUID,
    payload: StudentUpdate,
    school_id: uuid.UUID,
    parent_id: uuid.UUID | None,  # None means admin
) -> StudentOut:
    stmt = select(Student).where(Student.id == student_id, Student.school_id == school_id)
    if parent_id is not None:
        stmt = stmt.where(Student.parent_id == parent_id)
    student = (await db.execute(stmt)).scalar_one_or_none()
    if student is None:
        raise AppError("not_found", "Student not found", 404)

    update_data = payload.model_dump(exclude_unset=True)
    if "pickup_location" in update_data:
        loc_data = update_data.pop("pickup_location")
        if loc_data is not None:
            student.pickup_location = to_point(loc_data["lat"], loc_data["lng"])
        else:
            student.pickup_location = None
    for field, value in update_data.items():
        setattr(student, field, value)

    student.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(student)
    return _student_out(student)


# ---------------------------------------------------------------------------
# Route student assignment (POST /routes/{id}/students — Part D)
# ---------------------------------------------------------------------------


async def assign_student_to_route(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    stop_id: uuid.UUID,
) -> AssignmentOut:
    """
    Assign a student to a route+stop with a capacity check.
    Capacity = route.vehicle.capacity; count active assignments on the route.
    Raises 409 on conflict (capacity full or duplicate unique).
    """
    # Verify route belongs to school
    route = await get_scoped_or_404(db, Route, route_id, school_id)

    # Verify stop belongs to route
    stop = (
        await db.execute(
            select(RouteStop).where(RouteStop.id == stop_id, RouteStop.route_id == route_id)
        )
    ).scalar_one_or_none()
    if stop is None:
        raise AppError("not_found", "Stop not found on this route", 404)

    # Verify student belongs to school
    student = (
        await db.execute(
            select(Student).where(Student.id == student_id, Student.school_id == school_id)
        )
    ).scalar_one_or_none()
    if student is None:
        raise AppError("not_found", "Student not found", 404)

    # Capacity check
    await _check_route_capacity(db, route)

    assignment = StudentRouteAssignment(
        school_id=school_id,
        student_id=student_id,
        route_id=route_id,
        stop_id=stop_id,
        is_active=True,
    )
    db.add(assignment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("conflict", "Student already assigned to this route", 409) from exc
    await db.refresh(assignment)
    return AssignmentOut(
        id=assignment.id,
        school_id=assignment.school_id,
        student_id=assignment.student_id,
        route_id=assignment.route_id,
        stop_id=assignment.stop_id,
        assigned_at=assignment.assigned_at,
        is_active=assignment.is_active,
    )


async def list_route_students_real(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID | None,
    limit: int = 50,
    offset: int = 0,
) -> AssignmentPage:
    """Return active student_route_assignments for this route."""
    # Verify route exists and belongs to school
    await get_scoped_or_404(db, Route, route_id, school_id)

    stmt = select(StudentRouteAssignment).where(
        StudentRouteAssignment.route_id == route_id,
        StudentRouteAssignment.is_active.is_(True),
    )
    result = await paginate(stmt, db, limit=limit, offset=offset)
    items = [
        AssignmentOut(
            id=a.id,
            school_id=a.school_id,
            student_id=a.student_id,
            route_id=a.route_id,
            stop_id=a.stop_id,
            assigned_at=a.assigned_at,
            is_active=a.is_active,
        )
        for a in result["items"]
    ]
    return AssignmentPage(
        items=items,
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


# ---------------------------------------------------------------------------
# Transport requests
# ---------------------------------------------------------------------------


async def create_transport_request(
    db: AsyncSession,
    payload: TransportRequestIn,
    parent_id: uuid.UUID,
    school_id: uuid.UUID,
) -> TransportRequestOut:
    # Verify student belongs to this parent + school
    student = (
        await db.execute(
            select(Student).where(
                Student.id == payload.student_id,
                Student.school_id == school_id,
                Student.parent_id == parent_id,
            )
        )
    ).scalar_one_or_none()
    if student is None:
        raise AppError("not_found", "Student not found or not owned by you", 404)

    loc = None
    if payload.pickup_location is not None:
        loc = to_point(payload.pickup_location.lat, payload.pickup_location.lng)

    req = TransportRequest(
        school_id=school_id,
        parent_id=parent_id,
        student_id=payload.student_id,
        pickup_address=payload.pickup_address,
        pickup_location=loc,
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return _treq_out(req)


async def list_transport_requests(
    db: AsyncSession,
    school_id: uuid.UUID,
    parent_id: uuid.UUID | None,  # None = admin sees all
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TransportRequestPage:
    stmt = select(TransportRequest).where(TransportRequest.school_id == school_id)
    if parent_id is not None:
        stmt = stmt.where(TransportRequest.parent_id == parent_id)
    if status_filter is not None:
        stmt = stmt.where(TransportRequest.status == status_filter)
    result = await paginate(stmt, db, limit=limit, offset=offset)
    return TransportRequestPage(
        items=[_treq_out(r) for r in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def get_transport_request(
    db: AsyncSession,
    req_id: uuid.UUID,
    school_id: uuid.UUID,
    parent_id: uuid.UUID | None,
) -> TransportRequestOut:
    stmt = select(TransportRequest).where(
        TransportRequest.id == req_id,
        TransportRequest.school_id == school_id,
    )
    if parent_id is not None:
        stmt = stmt.where(TransportRequest.parent_id == parent_id)
    req = (await db.execute(stmt)).scalar_one_or_none()
    if req is None:
        raise AppError("not_found", "Transport request not found", 404)
    return _treq_out(req)


async def update_transport_request(
    db: AsyncSession,
    req_id: uuid.UUID,
    school_id: uuid.UUID,
    payload: TransportRequestUpdate,
) -> TransportRequestOut:
    """Admin-only update. On status='assigned', creates StudentRouteAssignment."""
    req = (
        await db.execute(
            select(TransportRequest).where(
                TransportRequest.id == req_id,
                TransportRequest.school_id == school_id,
            )
        )
    ).scalar_one_or_none()
    if req is None:
        raise AppError("not_found", "Transport request not found", 404)

    if payload.status == "assigned":
        if not payload.assigned_route_id or not payload.assigned_stop_id:
            raise AppError(
                "validation_error",
                "assigned_route_id and assigned_stop_id required when assigning",
                422,
            )

        # Verify route belongs to school
        route = await get_scoped_or_404(db, Route, payload.assigned_route_id, school_id)

        # Verify stop belongs to route
        stop = (
            await db.execute(
                select(RouteStop).where(
                    RouteStop.id == payload.assigned_stop_id,
                    RouteStop.route_id == payload.assigned_route_id,
                )
            )
        ).scalar_one_or_none()
        if stop is None:
            raise AppError("not_found", "Stop not found on the assigned route", 404)

        # Capacity check
        await _check_route_capacity(db, route)

        # Create assignment in same transaction
        assignment = StudentRouteAssignment(
            school_id=school_id,
            student_id=req.student_id,
            route_id=payload.assigned_route_id,
            stop_id=payload.assigned_stop_id,
            is_active=True,
        )
        db.add(assignment)
        # Flush so duplicate-key violation surfaces before final commit
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise AppError("conflict", "Student already assigned to this route", 409) from exc

        req.assigned_route_id = payload.assigned_route_id
        req.assigned_stop_id = payload.assigned_stop_id

    req.status = payload.status
    if payload.admin_notes is not None:
        req.admin_notes = payload.admin_notes
    req.updated_at = datetime.now(UTC)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("conflict", "Student already assigned to this route", 409) from exc
    await db.refresh(req)
    return _treq_out(req)


# ---------------------------------------------------------------------------
# Suggest stop (PostGIS)
# ---------------------------------------------------------------------------


async def suggest_stops(
    db: AsyncSession,
    school_id: uuid.UUID,
    lat: float,
    lng: float,
    k: int = 3,
) -> list[dict]:
    """
    Return up to k nearest active route-stops to (lat, lng) within the school.
    Uses PostGIS ST_Distance ordered ascending.
    """
    pt = to_point(lat, lng)
    stmt = (
        select(
            RouteStop.id,
            RouteStop.route_id,
            RouteStop.name,
            RouteStop.arrival_time,
            ST_Distance(RouteStop.location, pt).label("distance_m"),
        )
        .join(Route, Route.id == RouteStop.route_id)
        .where(Route.school_id == school_id, Route.is_active.is_(True))
        .order_by("distance_m")
        .limit(k)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "stop_id": row.id,
            "route_id": row.route_id,
            "name": row.name,
            "distance_m": round(row.distance_m),
            "arrival_time": row.arrival_time,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Internal: capacity check
# ---------------------------------------------------------------------------


async def _check_route_capacity(db: AsyncSession, route: Route) -> None:
    """
    Count active student_route_assignments for this route and compare to
    the vehicle's capacity. Raises 409 if full.
    """
    if route.vehicle_id is None:
        return  # No vehicle assigned — no capacity limit enforced

    vehicle = (
        await db.execute(select(Vehicle).where(Vehicle.id == route.vehicle_id))
    ).scalar_one_or_none()
    if vehicle is None:
        return  # Vehicle not found — skip check

    active_count_row = await db.execute(
        select(func.count()).select_from(StudentRouteAssignment).where(
            StudentRouteAssignment.route_id == route.id,
            StudentRouteAssignment.is_active.is_(True),
        )
    )
    active_count = active_count_row.scalar_one()

    if active_count >= vehicle.capacity:
        raise AppError("conflict", "Route at capacity", 409)
