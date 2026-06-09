"""
Users router — /api/v1/users   (school_admin | super_admin)

Admin People screen (list/search drivers + parents) and admin-initiated
password reset. Per-user authz is enforced in the service layer.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import ClaimsDep, DbDep, SchoolScopeDep, require_role
from app.users import services
from app.users.schemas import ResetPasswordIn, ResetPasswordOut, UserPage

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    dependencies=[Depends(require_role("school_admin", "super_admin"))],
)


@router.get("/")
async def list_users(
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
    role: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(description="Search name or email")] = None,
    school: Annotated[UUID | None, Query(description="super_admin cross-school filter")] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserPage:
    return await services.list_users(
        db,
        requester_role=claims["role"],
        school_scope=school_id,
        role=role,
        q=q,
        school_filter=school,
        limit=limit,
        offset=offset,
    )


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: UUID,
    body: ResetPasswordIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> ResetPasswordOut:
    await services.admin_reset_password(
        db,
        target_id=user_id,
        new_password=body.new_password,
        requester_role=claims["role"],
        school_scope=school_id,
    )
    return ResetPasswordOut(status="reset")
