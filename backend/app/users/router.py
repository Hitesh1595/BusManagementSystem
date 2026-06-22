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
from app.users.schemas import (
    ResetPasswordIn,
    ResetPasswordOut,
    StaffCreateIn,
    StaffCreateOut,
    UserOut,
    UserPage,
    UserUpdateIn,
)

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


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> UserOut:
    return await services.get_user(
        db,
        target_id=user_id,
        requester_role=claims["role"],
        school_scope=school_id,
    )


@router.post("/", status_code=201)
async def create_user(
    body: StaffCreateIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> StaffCreateOut:
    return await services.create_staff_user(
        db,
        requester_id=UUID(claims["sub"]),
        requester_role=claims["role"],
        school_scope=school_id,
        payload=body,
    )


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    body: UserUpdateIn,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> UserOut:
    return await services.update_user(
        db,
        target_id=user_id,
        payload=body,
        requester_role=claims["role"],
        school_scope=school_id,
    )


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> UserOut:
    return await services.set_user_active(
        db,
        target_id=user_id,
        active=False,
        requester_id=UUID(claims["sub"]),
        requester_role=claims["role"],
        school_scope=school_id,
    )


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: UUID,
    db: DbDep,
    claims: ClaimsDep,
    school_id: SchoolScopeDep,
) -> UserOut:
    return await services.set_user_active(
        db,
        target_id=user_id,
        active=True,
        requester_id=UUID(claims["sub"]),
        requester_role=claims["role"],
        school_scope=school_id,
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
