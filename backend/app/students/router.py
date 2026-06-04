"""
Students + transport-requests router.

Students:     prefix=/api/v1/students,          tags=["students"]
Transport Rq: prefix=/api/v1/transport-requests, tags=["transport-requests"]
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.geo import geocode
from app.deps import DbDep, SchoolScopeDep, require_role
from app.errors import AppError
from app.students import services
from app.students.schemas import (
    StudentIn,
    StudentOut,
    StudentPage,
    StudentUpdate,
    SuggestStopOut,
    TransportRequestIn,
    TransportRequestOut,
    TransportRequestPage,
    TransportRequestUpdate,
)

# ---------------------------------------------------------------------------
# Students router
# ---------------------------------------------------------------------------

students_router = APIRouter(
    prefix="/api/v1/students",
    tags=["students"],
)

_ParentDep = Annotated[dict, Depends(require_role("parent", "school_admin", "super_admin"))]
_AdminDep = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]


@students_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_student(
    body: StudentIn,
    db: DbDep,
    claims: Annotated[dict, Depends(require_role("parent"))],
    school_id: SchoolScopeDep,
) -> StudentOut:
    """Parent creates their own child. school_id from JWT claim."""
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    return await services.create_student(
        db,
        payload=body,
        parent_id=uuid.UUID(claims["sub"]),
        school_id=school_id,
    )


@students_router.get("/")
async def list_students(
    db: DbDep,
    claims: _ParentDep,
    school_id: SchoolScopeDep,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StudentPage:
    """Parent sees own children; admin sees all in school."""
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    role = claims.get("role")
    parent_id = uuid.UUID(claims["sub"]) if role == "parent" else None
    return await services.list_students(db, school_id, parent_id, limit=limit, offset=offset)


@students_router.get("/{student_id}")
async def get_student(
    student_id: uuid.UUID,
    db: DbDep,
    claims: _ParentDep,
    school_id: SchoolScopeDep,
) -> StudentOut:
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    role = claims.get("role")
    parent_id = uuid.UUID(claims["sub"]) if role == "parent" else None
    return await services.get_student(db, student_id, school_id, parent_id)


@students_router.put("/{student_id}")
async def update_student(
    student_id: uuid.UUID,
    body: StudentUpdate,
    db: DbDep,
    claims: _ParentDep,
    school_id: SchoolScopeDep,
) -> StudentOut:
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    role = claims.get("role")
    parent_id = uuid.UUID(claims["sub"]) if role == "parent" else None
    return await services.update_student(db, student_id, body, school_id, parent_id)


# ---------------------------------------------------------------------------
# Transport requests router
# ---------------------------------------------------------------------------

transport_router = APIRouter(
    prefix="/api/v1/transport-requests",
    tags=["transport-requests"],
)

_TRParentDep = Annotated[dict, Depends(require_role("parent", "school_admin", "super_admin"))]
_TRAdminDep = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]


@transport_router.get("/suggest-stop")
async def suggest_stop(
    db: DbDep,
    claims: _TRParentDep,
    school_id: SchoolScopeDep,
    lat: float | None = Query(default=None, ge=-90.0, le=90.0),
    lng: float | None = Query(default=None, ge=-180.0, le=180.0),
    address: str | None = Query(default=None),
) -> SuggestStopOut:
    """
    Return up to 3 nearest route stops to the given coordinates (or geocoded address).
    Ordered ascending by distance_m (nearest first).
    """
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)

    if address:
        coords = await geocode(address)
        if coords is None:
            raise AppError("not_found", "Could not geocode address", 404)
        lat, lng = coords["lat"], coords["lng"]

    if lat is None or lng is None:
        raise AppError("validation_error", "Provide lat+lng or address", 422)

    suggestions = await services.suggest_stops(db, school_id, lat, lng)
    return SuggestStopOut(suggestions=suggestions)  # type: ignore[arg-type]


@transport_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_transport_request(
    body: TransportRequestIn,
    db: DbDep,
    claims: Annotated[dict, Depends(require_role("parent"))],
    school_id: SchoolScopeDep,
) -> TransportRequestOut:
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    return await services.create_transport_request(
        db,
        payload=body,
        parent_id=uuid.UUID(claims["sub"]),
        school_id=school_id,
    )


@transport_router.get("/")
async def list_transport_requests(
    db: DbDep,
    claims: _TRParentDep,
    school_id: SchoolScopeDep,
    status: str | None = Query(default=None),
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransportRequestPage:
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    role = claims.get("role")
    parent_id = uuid.UUID(claims["sub"]) if role == "parent" else None
    return await services.list_transport_requests(
        db, school_id, parent_id, status_filter=status, limit=limit, offset=offset
    )


@transport_router.get("/{req_id}")
async def get_transport_request(
    req_id: uuid.UUID,
    db: DbDep,
    claims: _TRParentDep,
    school_id: SchoolScopeDep,
) -> TransportRequestOut:
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    role = claims.get("role")
    parent_id = uuid.UUID(claims["sub"]) if role == "parent" else None
    return await services.get_transport_request(db, req_id, school_id, parent_id)


@transport_router.put("/{req_id}")
async def update_transport_request(
    req_id: uuid.UUID,
    body: TransportRequestUpdate,
    db: DbDep,
    claims: _TRAdminDep,
    school_id: SchoolScopeDep,
) -> TransportRequestOut:
    """Admin updates request status; on 'assigned' creates StudentRouteAssignment."""
    if school_id is None:
        raise AppError("forbidden", "Cannot determine school scope", 403)
    return await services.update_transport_request(db, req_id, school_id, body)
