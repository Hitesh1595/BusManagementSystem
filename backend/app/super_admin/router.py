"""
Super-admin console router — /api/v1/super-admin  (super_admin only).

Read-only cross-tenant aggregations powering the platform dashboard and the
per-school drill-down.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import DbDep, require_role
from app.super_admin import schemas, services

router = APIRouter(
    prefix="/api/v1/super-admin",
    tags=["super-admin"],
    dependencies=[Depends(require_role("super_admin"))],
)


@router.get("/analytics/platform")
async def platform_analytics(db: DbDep) -> schemas.PlatformAnalyticsOut:
    return await services.platform_analytics(db)


@router.get("/schools/{school_id}/overview")
async def school_overview(
    school_id: UUID, db: DbDep
) -> schemas.SchoolOverviewOut:
    return await services.school_overview(db, school_id)
