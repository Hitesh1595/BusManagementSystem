"""
Vehicle + Driver service layer.

All write operations go through these functions; routers stay thin.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import write_audit
from app.core.email import send_email
from app.core.pagination import paginate
from app.core.security import hash_password
from app.crud import get_scoped_or_404, scoped_select
from app.errors import AppError
from app.vehicles.models import Vehicle
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
# Trip guards / helpers
# ---------------------------------------------------------------------------

# A vehicle with a trip in one of these states must not be deleted.
_BLOCKING_TRIP_STATUSES = ("scheduled", "in_progress", "pending_safeguard_check")


async def _has_active_trip(db: AsyncSession, vehicle_id: uuid.UUID) -> bool:
    """True if the vehicle has an upcoming or in-flight trip (blocks delete)."""
    from app.tracking.models import Trip

    stmt = (
        select(Trip.id)
        .where(
            Trip.vehicle_id == vehicle_id,
            Trip.status.in_(_BLOCKING_TRIP_STATUSES),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vehicle_out(v: Vehicle) -> VehicleOut:
    return VehicleOut.model_validate(v)


def _driver_out(u) -> DriverOut:
    return DriverOut.model_validate(u)


def _temp_password() -> str:
    """Generate a human-readable temp password: 12 random URL-safe chars."""
    return secrets.token_urlsafe(9)  # 12 base64url chars


# ---------------------------------------------------------------------------
# Vehicle services
# ---------------------------------------------------------------------------


async def create_vehicle(
    db: AsyncSession,
    school_id: uuid.UUID,
    payload: VehicleIn,
) -> VehicleOut:
    vehicle = Vehicle(
        school_id=school_id,
        plate_number=payload.plate_number,
        vehicle_type=payload.vehicle_type,
        capacity=payload.capacity,
        make=payload.make,
        model=payload.model,
        year=payload.year,
        insurance_expiry=payload.insurance_expiry,
        fitness_expiry=payload.fitness_expiry,
    )
    db.add(vehicle)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_vehicle_school_plate" in str(exc.orig):
            raise AppError("conflict", "Plate already exists", 409) from exc
        raise
    await db.refresh(vehicle)
    return _vehicle_out(vehicle)


async def get_vehicle(
    db: AsyncSession,
    vehicle_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> VehicleOut:
    # Use scoped_select (active_only=True) then filter by PK, so soft-deleted
    # vehicles are returned as 404 — consistent with list behaviour.
    stmt = scoped_select(Vehicle, school_id, active_only=True).where(Vehicle.id == vehicle_id)
    vehicle = (await db.execute(stmt)).scalar_one_or_none()
    if vehicle is None:
        raise AppError("not_found", "Vehicle not found", 404)
    return _vehicle_out(vehicle)


async def list_vehicles(
    db: AsyncSession,
    school_id: uuid.UUID | None,
    limit: int = 50,
    offset: int = 0,
) -> VehiclePage:
    stmt = scoped_select(Vehicle, school_id, active_only=True)
    result = await paginate(stmt, db, limit=limit, offset=offset)
    return VehiclePage(
        items=[_vehicle_out(v) for v in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def update_vehicle(
    db: AsyncSession,
    vehicle_id: uuid.UUID,
    school_id: uuid.UUID | None,
    payload: VehicleUpdate,
) -> VehicleOut:
    stmt = scoped_select(Vehicle, school_id, active_only=True).where(Vehicle.id == vehicle_id)
    vehicle = (await db.execute(stmt)).scalar_one_or_none()
    if vehicle is None:
        raise AppError("not_found", "Vehicle not found", 404)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vehicle, field, value)
    vehicle.updated_at = datetime.now(UTC)

    try:
        await db.flush()
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_vehicle_school_plate" in str(exc.orig):
            raise AppError("conflict", "Plate already exists", 409) from exc
        raise
    await db.refresh(vehicle)
    return _vehicle_out(vehicle)


async def soft_delete_vehicle(
    db: AsyncSession,
    vehicle_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> None:
    stmt = scoped_select(Vehicle, school_id, active_only=True).where(Vehicle.id == vehicle_id)
    vehicle = (await db.execute(stmt)).scalar_one_or_none()
    if vehicle is None:
        raise AppError("not_found", "Vehicle not found", 404)

    if await _has_active_trip(db, vehicle_id):
        raise AppError("conflict", "Vehicle has an active or scheduled trip", 409)

    vehicle.is_active = False
    vehicle.updated_at = datetime.now(UTC)
    await db.commit()


# ---------------------------------------------------------------------------
# Driver services
# ---------------------------------------------------------------------------


async def create_driver(
    db: AsyncSession,
    school_id: uuid.UUID,
    requester_id: uuid.UUID,
    payload: DriverIn,
) -> DriverCreateOut:
    from app.auth.models import User

    # Check if email already exists in this school
    existing = (
        await db.execute(
            select(User).where(
                User.email == payload.email.lower(),
                User.school_id == school_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError("conflict", "Email already registered for this school", 409)

    temp_pw = _temp_password()
    driver = User(
        school_id=school_id,
        email=payload.email.lower(),
        password_hash=hash_password(temp_pw),
        full_name=payload.full_name,
        phone=payload.phone,
        role="driver",
        is_active=True,
        email_verified=False,
    )
    db.add(driver)
    await db.flush()

    # Send welcome email (dev logs instead of sending when RESEND_API_KEY not set)
    await send_email(
        to=driver.email,
        subject="Your YatraTrack Driver Account",
        html=(
            f"<p>Hello {driver.full_name},</p>"
            f"<p>Your driver account has been created.</p>"
            f"<p>Temporary password: <strong>{temp_pw}</strong></p>"
            f"<p>Please change it after first login.</p>"
        ),
    )

    await db.commit()
    await db.refresh(driver)
    return DriverCreateOut(driver=_driver_out(driver), temp_password=temp_pw)


async def get_driver(
    db: AsyncSession,
    driver_id: uuid.UUID,
    school_id: uuid.UUID | None,
) -> DriverOut:
    from app.auth.models import User

    stmt = select(User).where(User.id == driver_id, User.role == "driver")
    if school_id is not None:
        stmt = stmt.where(User.school_id == school_id)
    driver = (await db.execute(stmt)).scalar_one_or_none()
    if driver is None:
        raise AppError("not_found", "Driver not found", 404)
    return _driver_out(driver)


async def list_drivers(
    db: AsyncSession,
    school_id: uuid.UUID | None,
    limit: int = 50,
    offset: int = 0,
) -> DriverPage:
    from app.auth.models import User
    from app.core.pagination import paginate

    stmt = select(User).where(User.role == "driver")
    if school_id is not None:
        stmt = stmt.where(User.school_id == school_id)

    result = await paginate(stmt, db, limit=limit, offset=offset)
    return DriverPage(
        items=[_driver_out(u) for u in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def update_driver(
    db: AsyncSession,
    driver_id: uuid.UUID,
    school_id: uuid.UUID | None,
    payload: DriverUpdate,
) -> DriverOut:
    from app.auth.models import User

    stmt = select(User).where(User.id == driver_id, User.role == "driver")
    if school_id is not None:
        stmt = stmt.where(User.school_id == school_id)
    driver = (await db.execute(stmt)).scalar_one_or_none()
    if driver is None:
        raise AppError("not_found", "Driver not found", 404)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(driver, field, value)
    driver.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(driver)
    return _driver_out(driver)


async def assign_vehicle(
    db: AsyncSession,
    driver_id: uuid.UUID,
    school_id: uuid.UUID | None,
    payload: AssignVehicleIn,
    requester_id: uuid.UUID,
) -> None:
    from app.auth.models import User

    # Validate driver belongs to school
    stmt = select(User).where(User.id == driver_id, User.role == "driver")
    if school_id is not None:
        stmt = stmt.where(User.school_id == school_id)
    driver = (await db.execute(stmt)).scalar_one_or_none()
    if driver is None:
        raise AppError("not_found", "Driver not found", 404)

    # Validate vehicle belongs to school
    vehicle = await get_scoped_or_404(db, Vehicle, payload.vehicle_id, school_id)

    # Write audit log for the assignment
    await write_audit(
        db,
        school_id=school_id,
        user_id=requester_id,
        action="driver.assign",
        entity_type="user",
        entity_id=driver_id,
        new={"vehicle_id": str(payload.vehicle_id), "plate_number": vehicle.plate_number},
    )
    await db.commit()


# Trips that count as a driver's upcoming/active schedule.
_SCHEDULE_TRIP_STATUSES = ("scheduled", "in_progress", "pending_safeguard_check")


async def list_driver_schedule(
    db: AsyncSession,
    driver_id: uuid.UUID,
    school_id: uuid.UUID | None,
    limit: int = 50,
    offset: int = 0,
):
    """Upcoming / in-flight trips assigned to a driver, soonest first."""
    from app.tracking.models import Trip
    from app.tracking.schemas import TripOut, TripPage

    await get_driver(db, driver_id, school_id)  # 404 if driver not in this school

    stmt = select(Trip).where(
        Trip.driver_id == driver_id,
        Trip.status.in_(_SCHEDULE_TRIP_STATUSES),
    )
    if school_id is not None:
        stmt = stmt.where(Trip.school_id == school_id)
    stmt = stmt.order_by(Trip.scheduled_departure_at.asc())

    result = await paginate(stmt, db, limit=limit, offset=offset)
    return TripPage(
        items=[TripOut.model_validate(t) for t in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def list_driver_trips(
    db: AsyncSession,
    driver_id: uuid.UUID,
    school_id: uuid.UUID | None,
    limit: int = 50,
    offset: int = 0,
):
    """Full trip history for a driver, most recent first."""
    from app.tracking.models import Trip
    from app.tracking.schemas import TripOut, TripPage

    await get_driver(db, driver_id, school_id)  # 404 if driver not in this school

    stmt = select(Trip).where(Trip.driver_id == driver_id)
    if school_id is not None:
        stmt = stmt.where(Trip.school_id == school_id)
    stmt = stmt.order_by(Trip.scheduled_departure_at.desc())

    result = await paginate(stmt, db, limit=limit, offset=offset)
    return TripPage(
        items=[TripOut.model_validate(t) for t in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )
