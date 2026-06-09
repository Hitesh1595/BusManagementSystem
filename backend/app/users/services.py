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

from app.auth.models import User
from app.auth.services import revoke_all_families_for_user
from app.core.pagination import paginate
from app.core.security import hash_password
from app.errors import AppError
from app.users.schemas import UserOut, UserPage

# Roles a school_admin is allowed to see and manage.
SCHOOL_ADMIN_MANAGEABLE = ("driver", "parent")


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
