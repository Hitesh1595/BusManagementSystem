"""
Super-admin aggregation service layer.

These are cross-tenant reads (super_admin only). RLS is not enabled in the MVP
(app-level scoping, spec G11), so we apply explicit WHERE filters here — for the
per-school overview we filter by school_id; the platform rollup counts everything.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import ALERT_SEVERITY, Alert
from app.auth.models import User
from app.errors import AppError
from app.routes.models import Route
from app.schools.models import School
from app.schools.schemas import SchoolOut
from app.students.models import Student
from app.super_admin.schemas import (
    AlertSeverityBreakdown,
    PlatformAnalyticsOut,
    SchoolOverviewOut,
    UsersByRole,
)
from app.tracking.models import Trip
from app.vehicles.models import Vehicle

# Trip states that count as "active now" (mirrors tracking.services.ACTIVE_STATUSES).
_ACTIVE_TRIP_STATUSES = ("scheduled", "in_progress", "pending_safeguard_check")


async def _count(db: AsyncSession, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return (await db.execute(stmt)).scalar_one()


async def _open_alert_severity(
    db: AsyncSession, *conditions
) -> AlertSeverityBreakdown:
    """Breakdown of unresolved alerts by severity (optionally school-scoped)."""
    stmt = (
        select(Alert.severity, func.count())
        .where(Alert.resolved_at.is_(None), *conditions)
        .group_by(Alert.severity)
    )
    counts = {sev: 0 for sev in ALERT_SEVERITY}
    for severity, n in (await db.execute(stmt)).all():
        counts[severity] = n
    return AlertSeverityBreakdown(**counts)


async def school_overview(
    db: AsyncSession, school_id: uuid.UUID
) -> SchoolOverviewOut:
    school = (
        await db.execute(select(School).where(School.id == school_id))
    ).scalar_one_or_none()
    if school is None:
        raise AppError("not_found", "School not found", 404)

    return SchoolOverviewOut(
        school=SchoolOut.model_validate(school),
        vehicle_count=await _count(
            db, Vehicle, Vehicle.school_id == school_id, Vehicle.is_active.is_(True)
        ),
        driver_count=await _count(
            db,
            User,
            User.school_id == school_id,
            User.role == "driver",
            User.is_active.is_(True),
        ),
        route_count=await _count(
            db, Route, Route.school_id == school_id, Route.is_active.is_(True)
        ),
        student_count=await _count(
            db, Student, Student.school_id == school_id, Student.is_active.is_(True)
        ),
        active_trip_count=await _count(
            db,
            Trip,
            Trip.school_id == school_id,
            Trip.status.in_(_ACTIVE_TRIP_STATUSES),
        ),
        open_alert_count=await _count(
            db, Alert, Alert.school_id == school_id, Alert.resolved_at.is_(None)
        ),
        alert_severity=await _open_alert_severity(db, Alert.school_id == school_id),
    )


async def platform_analytics(db: AsyncSession) -> PlatformAnalyticsOut:
    role_rows = (
        await db.execute(select(User.role, func.count()).group_by(User.role))
    ).all()
    roles = {"school_admin": 0, "driver": 0, "parent": 0}
    for role, n in role_rows:
        if role in roles:
            roles[role] = n

    since_24h = datetime.now(UTC) - timedelta(hours=24)

    return PlatformAnalyticsOut(
        total_schools=await _count(db, School),
        active_schools=await _count(db, School, School.is_active.is_(True)),
        users_by_role=UsersByRole(**roles),
        active_vehicles=await _count(db, Vehicle, Vehicle.is_active.is_(True)),
        active_routes=await _count(db, Route, Route.is_active.is_(True)),
        active_students=await _count(db, Student, Student.is_active.is_(True)),
        active_trips=await _count(
            db, Trip, Trip.status.in_(_ACTIVE_TRIP_STATUSES)
        ),
        open_alerts=await _count(db, Alert, Alert.resolved_at.is_(None)),
        alerts_last_24h=await _count(db, Alert, Alert.created_at >= since_24h),
        alert_severity=await _open_alert_severity(db),
    )
