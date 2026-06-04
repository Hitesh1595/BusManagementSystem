"""
Vehicles + Drivers routers.

Vehicles: /api/v1/vehicles   — school_admin | super_admin
Drivers:  /api/v1/drivers    — school_admin | super_admin
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.deps import ClaimsDep, DbDep, SchoolScopeDep, require_role
from app.vehicles import services
from app.vehicles.schemas import (
    AssignVehicleIn,
    DriverCreateOut,
    DriverIn,
    DriverOut,
    DriverPage,
    DriverUpdate,
    VehicleIn,
    VehicleOut,
    VehiclePage,
    VehicleUpdate,
)

# ---------------------------------------------------------------------------
# Shared role gate alias
# ---------------------------------------------------------------------------

_AdminDep = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]

# ---------------------------------------------------------------------------
# Vehicles router
# ---------------------------------------------------------------------------

vehicles_router = APIRouter(
    prefix="/api/v1/vehicles",
    tags=["vehicles"],
    dependencies=[Depends(require_role("school_admin", "super_admin"))],
)


@vehicles_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    body: VehicleIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> VehicleOut:
    # super_admin must have a school_id in context to create vehicles;
    # for simplicity we require it — a super_admin scoped to None cannot create.
    if school_id is None:
        from app.errors import AppError
        raise AppError("forbidden", "super_admin must scope to a school to create vehicles", 403)
    return await services.create_vehicle(db, school_id, body)


@vehicles_router.get("/")
async def list_vehicles(
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VehiclePage:
    return await services.list_vehicles(db, school_id, limit=limit, offset=offset)


@vehicles_router.get("/{vehicle_id}")
async def get_vehicle(
    vehicle_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> VehicleOut:
    return await services.get_vehicle(db, vehicle_id, school_id)


@vehicles_router.put("/{vehicle_id}")
async def update_vehicle(
    vehicle_id: UUID,
    body: VehicleUpdate,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> VehicleOut:
    return await services.update_vehicle(db, vehicle_id, school_id, body)


@vehicles_router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> None:
    await services.soft_delete_vehicle(db, vehicle_id, school_id)


# ---------------------------------------------------------------------------
# Drivers router
# ---------------------------------------------------------------------------

drivers_router = APIRouter(
    prefix="/api/v1/drivers",
    tags=["drivers"],
    dependencies=[Depends(require_role("school_admin", "super_admin"))],
)


@drivers_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_driver(
    body: DriverIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> DriverCreateOut:
    if school_id is None:
        from app.errors import AppError
        raise AppError("forbidden", "super_admin must scope to a school to create drivers", 403)
    requester_id = UUID(claims["sub"])
    return await services.create_driver(db, school_id, requester_id, body)


@drivers_router.get("/")
async def list_drivers(
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DriverPage:
    return await services.list_drivers(db, school_id, limit=limit, offset=offset)


@drivers_router.get("/{driver_id}")
async def get_driver(
    driver_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> DriverOut:
    return await services.get_driver(db, driver_id, school_id)


@drivers_router.put("/{driver_id}")
async def update_driver(
    driver_id: UUID,
    body: DriverUpdate,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> DriverOut:
    return await services.update_driver(db, driver_id, school_id, body)


@drivers_router.post("/{driver_id}/assign", status_code=status.HTTP_200_OK)
async def assign_vehicle(
    driver_id: UUID,
    body: AssignVehicleIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> dict:
    requester_id = UUID(claims["sub"])
    await services.assign_vehicle(db, driver_id, school_id, body, requester_id)
    return {"status": "assigned"}


@drivers_router.get("/{driver_id}/schedule")
async def get_driver_schedule(
    driver_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> dict:
    # TODO(chunk-4): return real schedule from trips table
    return {"items": [], "total": 0, "limit": 50, "offset": 0}


@drivers_router.get("/{driver_id}/trips")
async def get_driver_trips(
    driver_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> dict:
    # TODO(chunk-4): return real trips from trips table
    return {"items": [], "total": 0, "limit": 50, "offset": 0}
