"""
User-management service layer — admin People list + admin-initiated password reset.

Authz model (spec / docs/TODO.md):
  super_admin  → list any user (optional school filter); reset any user.
  school_admin → list only OWN-school `driver`/`parent`; reset only those.

To avoid cross-tenant existence disclosure, a school_admin targeting a user in a
DIFFERENT school gets 404 (not 403); 403 is reserved for an in-school target whose
role they may not manage (another admin / super_admin).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import write_audit
from app.auth.models import User
from app.auth.services import revoke_all_families_for_user
from app.core.email import send_email
from app.core.pagination import paginate
from app.core.security import hash_password, temp_password
from app.errors import AppError
from app.schools.models import School
from app.users.schemas import (
    StaffCreateIn,
    StaffCreateOut,
    UserOut,
    UserPage,
    UserUpdateIn,
)

# Roles a school_admin can see and manage (list, reset, edit, (de)activate).
# Co-admins are mutually trusted within a school; the destructive paths are
# protected by per-action guards (can't deactivate yourself / the last admin).
SCHOOL_ADMIN_MANAGEABLE = ("driver", "parent", "school_admin")
# Trip states that block deactivating a driver.
_BLOCKING_TRIP_STATUSES = ("scheduled", "in_progress", "pending_safeguard_check")


async def list_users(
    db: AsyncSession,
    *,
    requester_role: str,
    school_scope: uuid.UUID | None,
    role: str | None = None,
    q: str | None = None,
    school_filter: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> UserPage:
    """List users visible to the requester (own-school for school_admin)."""
    stmt = select(User)

    if requester_role == "school_admin":
        # Hard scope: own school, manageable roles only — regardless of filters.
        stmt = stmt.where(
            User.school_id == school_scope,
            User.role.in_(SCHOOL_ADMIN_MANAGEABLE),
        )
    elif school_filter is not None:  # super_admin optional cross-school filter
        stmt = stmt.where(User.school_id == school_filter)

    if role is not None:
        stmt = stmt.where(User.role == role)

    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
            )
        )

    stmt = stmt.order_by(User.full_name.asc())

    result = await paginate(stmt, db, limit=limit, offset=offset)
    return UserPage(
        items=[UserOut.model_validate(u) for u in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def admin_reset_password(
    db: AsyncSession,
    *,
    target_id: uuid.UUID,
    new_password: str,
    requester_role: str,
    school_scope: uuid.UUID | None,
) -> None:
    """
    Set a target user's password directly and revoke all their refresh tokens
    (forcing re-login everywhere). Authz is enforced here, not just at the route.
    """
    target = (
        await db.execute(select(User).where(User.id == target_id))
    ).scalar_one_or_none()
    if target is None:
        raise AppError("not_found", "User not found", 404)

    if requester_role == "school_admin":
        # Different school → behave as if the user doesn't exist (no disclosure).
        if target.school_id != school_scope:
            raise AppError("not_found", "User not found", 404)
        # Same school but a role we may not manage → explicit privilege boundary.
        if target.role not in SCHOOL_ADMIN_MANAGEABLE:
            raise AppError(
                "forbidden", "You can only reset drivers and parents", 403
            )
    # super_admin: any user is allowed.

    target.password_hash = hash_password(new_password)
    target.updated_at = datetime.now(UTC)
    await db.commit()

    # Force re-login on every device.
    await revoke_all_families_for_user(db, target.id)


# ---------------------------------------------------------------------------
# Staff lifecycle: create / update / (de)activate
# ---------------------------------------------------------------------------


async def _load_manageable_target(
    db: AsyncSession,
    *,
    target_id: uuid.UUID,
    requester_role: str,
    school_scope: uuid.UUID | None,
) -> User:
    """
    Fetch a user the requester is allowed to manage, or raise.

    Mirrors `admin_reset_password`: a school_admin targeting a different school
    gets 404 (no cross-tenant disclosure); an in-school target whose role they
    may not manage gets 403. super_admin may manage anyone except super_admins.
    """
    target = (
        await db.execute(select(User).where(User.id == target_id))
    ).scalar_one_or_none()
    if target is None:
        raise AppError("not_found", "User not found", 404)

    if requester_role == "school_admin":
        if target.school_id != school_scope:
            raise AppError("not_found", "User not found", 404)
        if target.role not in SCHOOL_ADMIN_MANAGEABLE:
            raise AppError("forbidden", "You cannot manage this user", 403)
    elif target.role == "super_admin":  # super_admin requester
        raise AppError(
            "forbidden", "Super-admin accounts can't be managed here", 403
        )
    return target


async def _active_admin_count(db: AsyncSession, school_id: uuid.UUID | None) -> int:
    if school_id is None:
        return 0
    stmt = (
        select(func.count())
        .select_from(User)
        .where(
            User.school_id == school_id,
            User.role == "school_admin",
            User.is_active.is_(True),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def _driver_has_active_trip(db: AsyncSession, driver_id: uuid.UUID) -> bool:
    from app.tracking.models import Trip

    stmt = (
        select(Trip.id)
        .where(
            Trip.driver_id == driver_id,
            Trip.status.in_(_BLOCKING_TRIP_STATUSES),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def create_staff_user(
    db: AsyncSession,
    *,
    requester_id: uuid.UUID,
    requester_role: str,
    school_scope: uuid.UUID | None,
    payload: StaffCreateIn,
) -> StaffCreateOut:
    """
    Create a `driver` or `school_admin` with a generated temp password.

    school_admin → always their own school. super_admin → must pass `school_id`.
    """
    if requester_role == "school_admin":
        target_school = school_scope
    else:  # super_admin
        target_school = payload.school_id
        if target_school is None:
            raise AppError("validation_error", "school_id is required", 422)
        school = (
            await db.execute(select(School).where(School.id == target_school))
        ).scalar_one_or_none()
        if school is None:
            raise AppError("not_found", "School not found", 404)

    if target_school is None:
        raise AppError("validation_error", "school_id is required", 422)

    email = payload.email.lower()
    existing = (
        await db.execute(
            select(User).where(
                User.email == email, User.school_id == target_school
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError("conflict", "Email already registered for this school", 409)

    temp_pw = temp_password()
    user = User(
        school_id=target_school,
        email=email,
        password_hash=hash_password(temp_pw),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    await write_audit(
        db,
        school_id=target_school,
        user_id=requester_id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        new={"role": payload.role, "email": email},
    )

    role_label = "Driver" if payload.role == "driver" else "Admin"
    await send_email(
        to=email,
        subject=f"Your YatraTrack {role_label} Account",
        html=(
            f"<p>Hello {payload.full_name},</p>"
            f"<p>Your YatraTrack account has been created.</p>"
            f"<p>Email: <strong>{email}</strong></p>"
            f"<p>Temporary password: <strong>{temp_pw}</strong></p>"
            f"<p>Please sign in and change it.</p>"
        ),
    )

    await db.commit()
    await db.refresh(user)
    return StaffCreateOut(user=UserOut.model_validate(user), temp_password=temp_pw)


async def update_user(
    db: AsyncSession,
    *,
    target_id: uuid.UUID,
    payload: UserUpdateIn,
    requester_role: str,
    school_scope: uuid.UUID | None,
) -> UserOut:
    """Update a manageable user's profile fields (name, phone)."""
    target = await _load_manageable_target(
        db,
        target_id=target_id,
        requester_role=requester_role,
        school_scope=school_scope,
    )
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(target, field, value)
    target.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(target)
    return UserOut.model_validate(target)


async def set_user_active(
    db: AsyncSession,
    *,
    target_id: uuid.UUID,
    active: bool,
    requester_id: uuid.UUID,
    requester_role: str,
    school_scope: uuid.UUID | None,
) -> UserOut:
    """Activate or deactivate (soft-delete) a manageable user."""
    target = await _load_manageable_target(
        db,
        target_id=target_id,
        requester_role=requester_role,
        school_scope=school_scope,
    )

    if not active and target.is_active:
        if target.id == requester_id:
            raise AppError("conflict", "You cannot deactivate your own account", 409)
        if target.role == "school_admin":
            if await _active_admin_count(db, target.school_id) <= 1:
                raise AppError(
                    "conflict", "A school must keep at least one active admin", 409
                )
        if target.role == "driver" and await _driver_has_active_trip(db, target.id):
            raise AppError(
                "conflict", "Driver has an active or scheduled trip", 409
            )

    if target.is_active != active:
        target.is_active = active
        target.updated_at = datetime.now(UTC)
        await write_audit(
            db,
            school_id=target.school_id,
            user_id=requester_id,
            action="user.activate" if active else "user.deactivate",
            entity_type="user",
            entity_id=target.id,
            new={"is_active": active},
        )
        await db.commit()
        if not active:
            # Sign the user out everywhere once disabled.
            await revoke_all_families_for_user(db, target.id)
        await db.refresh(target)

    return UserOut.model_validate(target)
