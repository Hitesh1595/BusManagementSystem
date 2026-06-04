"""
Alerts router — /api/v1/alerts

RBAC: school_admin | super_admin only.

Endpoints:
  GET  /                list (filter ?type=&severity=&resolved=)
  PUT  /{id}/acknowledge  mark acknowledged_by + acknowledged_at
  PUT  /{id}/resolve      mark resolved_at; if last child_not_dropped
                          for a trip → atomic trip completion (§10.2)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, select

from app.alerts.models import Alert
from app.deps import DbDep, SchoolScopeDep, require_role
from app.errors import AppError

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

_AdminDep = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]


# ---------------------------------------------------------------------------
# Schemas (inline — simple enough)
# ---------------------------------------------------------------------------


class AlertOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    trip_id: uuid.UUID | None
    type: str
    severity: str
    title: str
    description: str | None
    triggered_by: uuid.UUID | None
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_alert(cls, alert: Alert) -> AlertOut:
        return cls(
            id=alert.id,
            school_id=alert.school_id,
            trip_id=alert.trip_id,
            type=alert.type,
            severity=alert.severity,
            title=alert.title,
            description=alert.description,
            triggered_by=alert.triggered_by,
            acknowledged_by=alert.acknowledged_by,
            acknowledged_at=alert.acknowledged_at,
            resolved_at=alert.resolved_at,
            metadata=alert.metadata_,
            created_at=alert.created_at,
        )


class AlertListOut(BaseModel):
    items: list[AlertOut]
    total: int


class AcknowledgeResult(BaseModel):
    id: uuid.UUID
    acknowledged: bool


class ResolveResult(BaseModel):
    id: uuid.UUID
    resolved: bool
    trip_completed: bool


# ---------------------------------------------------------------------------
# GET / — list alerts
# ---------------------------------------------------------------------------


@router.get("/")
async def list_alerts(
    db: DbDep,
    claims: _AdminDep,
    school_id: SchoolScopeDep,
    type: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    resolved: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AlertListOut:
    """List alerts with optional filters."""
    stmt = select(Alert)
    if school_id is not None:
        stmt = stmt.where(Alert.school_id == school_id)
    if type is not None:
        stmt = stmt.where(Alert.type == type)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if resolved is True:
        stmt = stmt.where(Alert.resolved_at.isnot(None))
    elif resolved is False:
        stmt = stmt.where(Alert.resolved_at.is_(None))

    stmt = stmt.order_by(Alert.created_at.desc())

    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return AlertListOut(
        items=[AlertOut.from_orm_alert(r) for r in rows],
        total=total,
    )


# ---------------------------------------------------------------------------
# PUT /{id}/acknowledge
# ---------------------------------------------------------------------------


@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: uuid.UUID,
    db: DbDep,
    claims: _AdminDep,
    school_id: SchoolScopeDep,
) -> AcknowledgeResult:
    """Admin acknowledges an alert."""
    alert = (
        await db.execute(
            select(Alert).where(
                and_(
                    Alert.id == alert_id,
                    *([Alert.school_id == school_id] if school_id else []),
                )
            )
        )
    ).scalar_one_or_none()

    if alert is None:
        raise AppError("not_found", "Alert not found", 404)

    now = datetime.now(UTC)
    if alert.acknowledged_at is None:
        alert.acknowledged_by = uuid.UUID(claims["sub"])
        alert.acknowledged_at = now
        await db.commit()

    return AcknowledgeResult(id=alert.id, acknowledged=True)


# ---------------------------------------------------------------------------
# PUT /{id}/resolve
# ---------------------------------------------------------------------------


@router.put("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: uuid.UUID,
    db: DbDep,
    claims: _AdminDep,
    school_id: SchoolScopeDep,
) -> ResolveResult:
    """
    Admin resolves an alert.

    If it was a child_not_dropped alert and this was the last unresolved one
    for its trip, the trip is atomically completed (spec §10.2).
    """
    from app.core.socketio import sio
    from app.tracking.safety import resolve_alert_and_maybe_complete

    alert = (
        await db.execute(
            select(Alert).where(
                and_(
                    Alert.id == alert_id,
                    *([Alert.school_id == school_id] if school_id else []),
                )
            )
        )
    ).scalar_one_or_none()

    if alert is None:
        raise AppError("not_found", "Alert not found", 404)

    if alert.resolved_at is not None:
        # Already resolved — idempotent
        return ResolveResult(id=alert.id, resolved=True, trip_completed=False)

    completion = await resolve_alert_and_maybe_complete(db, sio, alert_id)

    return ResolveResult(
        id=alert_id,
        resolved=True,
        trip_completed=completion.completed,
    )
