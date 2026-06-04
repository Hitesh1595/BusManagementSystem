"""
Route + RouteStop service layer.

Key behaviours:
  - All writes are school-scoped (school_id on Route).
  - Route update uses optimistic locking on `version` (409 on stale).
  - After ANY stop mutation, route_path (LineString) is rebuilt from ordered stops.
  - Reorder uses a 2-phase approach (negative offsets then final values) to avoid
    UNIQUE(route_id, stop_order) collisions within the same transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import from_point, linestring_from_stops, to_point
from app.core.pagination import paginate
from app.crud import get_scoped_or_404, scoped_select
from app.errors import AppError
from app.routes.models import Route, RouteStop
from app.routes.schemas import (
    LatLng,
    ReorderIn,
    RouteIn,
    RouteOut,
    RoutePage,
    RouteUpdate,
    StopIn,
    StopOut,
    StopUpdate,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _stop_out(stop: RouteStop) -> StopOut:
    loc = from_point(stop.location)
    return StopOut(
        id=stop.id,
        route_id=stop.route_id,
        name=stop.name,
        location=LatLng(lat=loc["lat"], lng=loc["lng"]) if loc else LatLng(lat=0.0, lng=0.0),
        address=stop.address,
        stop_order=stop.stop_order,
        arrival_time=stop.arrival_time,
        created_at=stop.created_at,
    )


async def _load_stops(db: AsyncSession, route_id: uuid.UUID) -> list[RouteStop]:
    """Return stops ordered by stop_order ascending."""
    stmt = (
        select(RouteStop)
        .where(RouteStop.route_id == route_id)
        .order_by(RouteStop.stop_order)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _rebuild_route_path(db: AsyncSession, route: Route) -> None:
    """
    Rebuild route.route_path as a LineString from the ordered stops.
    Clears route_path when fewer than 2 stops exist.
    """
    stops = await _load_stops(db, route.id)
    pts: list[tuple[float, float]] = []
    for s in stops:
        loc = from_point(s.location)
        if loc:
            pts.append((loc["lat"], loc["lng"]))

    route.route_path = linestring_from_stops(pts)  # None if < 2 pts


def _route_out(route: Route, stops: list[RouteStop]) -> RouteOut:
    return RouteOut(
        id=route.id,
        school_id=route.school_id,
        name=route.name,
        description=route.description,
        vehicle_id=route.vehicle_id,
        driver_id=route.driver_id,
        schedule_type=route.schedule_type,
        version=route.version,
        is_active=route.is_active,
        has_route_path=route.route_path is not None,
        stops=[_stop_out(s) for s in stops],
        created_at=route.created_at,
        updated_at=route.updated_at,
    )


# ---------------------------------------------------------------------------
# Route CRUD
# ---------------------------------------------------------------------------


async def create_route(
    db: AsyncSession,
    school_id: uuid.UUID,
    payload: RouteIn,
) -> RouteOut:
    route = Route(
        school_id=school_id,
        name=payload.name,
        description=payload.description,
        schedule_type=payload.schedule_type,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        version=1,
    )
    db.add(route)
    await db.flush()
    await db.commit()
    await db.refresh(route)
    return _route_out(route, [])


async def get_route(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> RouteOut:
    route = await get_scoped_or_404(db, Route, route_id, school_id)
    stops = await _load_stops(db, route.id)
    return _route_out(route, stops)


async def list_routes(
    db: AsyncSession,
    school_id: uuid.UUID | None,
    limit: int = 50,
    offset: int = 0,
) -> RoutePage:
    stmt = scoped_select(Route, school_id, active_only=True)
    result = await paginate(stmt, db, limit=limit, offset=offset)
    items: list[RouteOut] = []
    for route in result["items"]:
        stops = await _load_stops(db, route.id)
        items.append(_route_out(route, stops))
    return RoutePage(
        items=items,
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def update_route(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID | None,
    payload: RouteUpdate,
) -> RouteOut:
    route = await get_scoped_or_404(db, Route, route_id, school_id)

    # Optimistic lock check
    if payload.version != route.version:
        raise AppError(
            "conflict",
            "Route was modified; reload and retry",
            409,
        )

    update_data = payload.model_dump(exclude_unset=True, exclude={"version"})
    for field, value in update_data.items():
        setattr(route, field, value)

    route.version = route.version + 1
    route.updated_at = datetime.now(UTC)

    await db.flush()
    await db.commit()
    await db.refresh(route)
    stops = await _load_stops(db, route.id)
    return _route_out(route, stops)


async def soft_delete_route(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> None:
    route = await get_scoped_or_404(db, Route, route_id, school_id)
    route.is_active = False
    route.updated_at = datetime.now(UTC)
    await db.commit()


# ---------------------------------------------------------------------------
# Stop CRUD
# ---------------------------------------------------------------------------


async def _next_stop_order(db: AsyncSession, route_id: uuid.UUID) -> int:
    """Return the next available stop_order (max + 1, or 0 if no stops)."""
    stops = await _load_stops(db, route_id)
    if not stops:
        return 0
    return max(s.stop_order for s in stops) + 1


async def add_stop(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID | None,
    payload: StopIn,
) -> StopOut:
    # Verify route belongs to school
    route = await get_scoped_or_404(db, Route, route_id, school_id)

    order = payload.stop_order
    if order is None:
        order = await _next_stop_order(db, route_id)

    stop = RouteStop(
        route_id=route_id,
        name=payload.name,
        location=to_point(payload.location.lat, payload.location.lng),
        address=payload.address,
        stop_order=order,
        arrival_time=payload.arrival_time,
    )
    db.add(stop)
    await db.flush()

    # Rebuild route path
    await _rebuild_route_path(db, route)
    route.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(stop)
    return _stop_out(stop)


async def update_stop(
    db: AsyncSession,
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    school_id: uuid.UUID | None,
    payload: StopUpdate,
) -> StopOut:
    # Verify route belongs to school
    route = await get_scoped_or_404(db, Route, route_id, school_id)

    stop = (
        await db.execute(
            select(RouteStop).where(
                RouteStop.id == stop_id, RouteStop.route_id == route_id
            )
        )
    ).scalar_one_or_none()
    if stop is None:
        raise AppError("not_found", "Stop not found", 404)

    if payload.name is not None:
        stop.name = payload.name
    if payload.location is not None:
        stop.location = to_point(payload.location.lat, payload.location.lng)
    if payload.address is not None:
        stop.address = payload.address
    if payload.arrival_time is not None:
        stop.arrival_time = payload.arrival_time

    await db.flush()

    # Rebuild route path
    await _rebuild_route_path(db, route)
    route.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(stop)
    return _stop_out(stop)


async def delete_stop(
    db: AsyncSession,
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> None:
    # Verify route belongs to school
    route = await get_scoped_or_404(db, Route, route_id, school_id)

    stop = (
        await db.execute(
            select(RouteStop).where(
                RouteStop.id == stop_id, RouteStop.route_id == route_id
            )
        )
    ).scalar_one_or_none()
    if stop is None:
        raise AppError("not_found", "Stop not found", 404)

    await db.delete(stop)
    await db.flush()

    # Rebuild route path (may be None now if < 2 remaining stops)
    await _rebuild_route_path(db, route)
    route.updated_at = datetime.now(UTC)

    await db.commit()


async def reorder_stops(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID | None,
    payload: ReorderIn,
) -> list[StopOut]:
    """
    Reorder stops by renumbering stop_order to match the given ordered_stop_ids list.

    2-phase approach to avoid UNIQUE(route_id, stop_order) violations:
      Phase 1: assign large negative temporary offsets (e.g. -1, -2, ...).
      Phase 2: assign final values (0, 1, 2, ...).
    """
    route = await get_scoped_or_404(db, Route, route_id, school_id)

    # Load all stops for this route
    stops = await _load_stops(db, route_id)
    stop_map: dict[uuid.UUID, RouteStop] = {s.id: s for s in stops}

    # Validate that all provided IDs belong to this route
    for sid in payload.ordered_stop_ids:
        if sid not in stop_map:
            raise AppError("not_found", f"Stop {sid} not found on this route", 404)

    if len(payload.ordered_stop_ids) != len(stops):
        raise AppError(
            "validation_error",
            f"ordered_stop_ids must include all {len(stops)} stops",
            422,
        )

    # Phase 1: set large negative temporary stop_orders to avoid collisions
    for idx, sid in enumerate(payload.ordered_stop_ids):
        stop_map[sid].stop_order = -(idx + 1)
    await db.flush()

    # Phase 2: assign final 0-based stop_orders
    for idx, sid in enumerate(payload.ordered_stop_ids):
        stop_map[sid].stop_order = idx
    await db.flush()

    # Rebuild route path with new order
    await _rebuild_route_path(db, route)
    route.updated_at = datetime.now(UTC)

    await db.commit()

    # Reload stops in new order
    updated_stops = await _load_stops(db, route_id)
    return [_stop_out(s) for s in updated_stops]


# ---------------------------------------------------------------------------
# Students on route — Part D stubs
# ---------------------------------------------------------------------------


async def list_route_students(
    db: AsyncSession,
    route_id: uuid.UUID,
    school_id: uuid.UUID | None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    TODO(part-d): return real student_route_assignments for this route.
    student_route_assignments table is created in Task 3.4 (Part D).
    """
    # Verify route exists and belongs to school (raises 404 otherwise)
    await get_scoped_or_404(db, Route, route_id, school_id)
    return {"items": [], "total": 0, "limit": limit, "offset": offset}
