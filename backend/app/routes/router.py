"""
Routes + Stops router.

Base: /api/v1/routes
Auth: school_admin | super_admin (applied at router level)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.deps import ClaimsDep, DbDep, SchoolScopeDep, require_role
from app.errors import AppError
from app.routes import services
from app.routes.schemas import (
    ReorderIn,
    RouteIn,
    RouteOut,
    RoutePage,
    RouteUpdate,
    StopIn,
    StopOut,
    StopUpdate,
)

# Shared role gate applied at router level
router = APIRouter(
    prefix="/api/v1/routes",
    tags=["routes"],
    dependencies=[Depends(require_role("school_admin", "super_admin"))],
)

_AdminDep = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]


# ---------------------------------------------------------------------------
# Route endpoints
# ---------------------------------------------------------------------------


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_route(
    body: RouteIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> RouteOut:
    if school_id is None:
        raise AppError("forbidden", "super_admin must scope to a school to create routes", 403)
    return await services.create_route(db, school_id, body)


@router.get("/")
async def list_routes(
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RoutePage:
    return await services.list_routes(db, school_id, limit=limit, offset=offset)


@router.get("/{route_id}")
async def get_route(
    route_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> RouteOut:
    return await services.get_route(db, route_id, school_id)


@router.put("/{route_id}")
async def update_route(
    route_id: UUID,
    body: RouteUpdate,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> RouteOut:
    return await services.update_route(db, route_id, school_id, body)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> None:
    await services.soft_delete_route(db, route_id, school_id)


# ---------------------------------------------------------------------------
# Stop endpoints — nested under /{route_id}/stops
# ---------------------------------------------------------------------------


@router.post("/{route_id}/stops", status_code=status.HTTP_201_CREATED)
async def add_stop(
    route_id: UUID,
    body: StopIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> StopOut:
    return await services.add_stop(db, route_id, school_id, body)


@router.put("/{route_id}/stops/reorder")
async def reorder_stops(
    route_id: UUID,
    body: ReorderIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> list[StopOut]:
    """
    Reorder all stops on a route. Body must include ALL stop IDs in the desired order.
    Renumbers stop_order 0..N-1 and rebuilds route_path.
    """
    return await services.reorder_stops(db, route_id, school_id, body)


@router.put("/{route_id}/stops/{stop_id}")
async def update_stop(
    route_id: UUID,
    stop_id: UUID,
    body: StopUpdate,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> StopOut:
    return await services.update_stop(db, route_id, stop_id, school_id, body)


@router.delete("/{route_id}/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stop(
    route_id: UUID,
    stop_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> None:
    await services.delete_stop(db, route_id, stop_id, school_id)


# ---------------------------------------------------------------------------
# Students on route — Part D stub
# ---------------------------------------------------------------------------


@router.get("/{route_id}/students")
async def list_route_students(
    route_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """
    TODO(part-d): returns assigned students for this route.
    Currently returns an empty paginated list — student_route_assignments is Part D.
    """
    return await services.list_route_students(db, route_id, school_id, limit=limit, offset=offset)


# POST /{route_id}/students — TODO(part-d): assign student to route+stop (capacity-checked).
# Deferred to Part D when student_route_assignments table is created.
