"""
Notifications router — /api/v1/notifications

In-app notification bell (spec §6.6). All authenticated roles read/manage only
their OWN notifications (scoped by user_id from the JWT `sub` claim).

Endpoints:
  GET  /                 list (paginated; ?unread=true filter)
  PUT  /{id}/read         mark one read
  PUT  /read-all          mark all unread read
  PUT  /preferences       update the user's notification_prefs JSONB

Web-push subscribe/unsubscribe are intentionally deferred to V2.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.auth.models import User
from app.deps import ClaimsDep, DbDep
from app.errors import AppError
from app.notifications.models import Notification

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None
    data: dict
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListOut(BaseModel):
    notifications: list[NotificationOut]
    total: int
    page: int
    page_size: int


class MarkReadOut(BaseModel):
    id: uuid.UUID
    is_read: bool
    read_at: datetime | None


class MarkAllReadOut(BaseModel):
    marked_count: int


class PreferencesIn(BaseModel):
    notification_prefs: dict[str, Any]


class PreferencesOut(BaseModel):
    notification_prefs: dict


# ---------------------------------------------------------------------------
# GET / — list current user's notifications
# ---------------------------------------------------------------------------


@router.get("")
async def list_notifications(
    db: DbDep,
    claims: ClaimsDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    unread: Annotated[bool | None, Query()] = None,
) -> NotificationListOut:
    """List the caller's notifications, newest first."""
    user_id = uuid.UUID(claims["sub"])

    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread is True:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    rows = (
        await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    return NotificationListOut(
        notifications=[NotificationOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# PUT /{id}/read — mark one read
# ---------------------------------------------------------------------------


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID,
    db: DbDep,
    claims: ClaimsDep,
) -> MarkReadOut:
    """Mark a single notification read (must belong to the caller)."""
    user_id = uuid.UUID(claims["sub"])

    notif = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
    ).scalar_one_or_none()

    if notif is None:
        raise AppError("not_found", "Notification not found", 404)

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(UTC)
        await db.commit()

    return MarkReadOut(id=notif.id, is_read=notif.is_read, read_at=notif.read_at)


# ---------------------------------------------------------------------------
# PUT /read-all — mark all the caller's unread notifications read
# ---------------------------------------------------------------------------


@router.put("/read-all")
async def mark_all_read(db: DbDep, claims: ClaimsDep) -> MarkAllReadOut:
    user_id = uuid.UUID(claims["sub"])

    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await db.commit()
    return MarkAllReadOut(marked_count=result.rowcount or 0)


# ---------------------------------------------------------------------------
# PUT /preferences — update the caller's notification preferences
# ---------------------------------------------------------------------------


@router.put("/preferences")
async def update_preferences(
    payload: PreferencesIn,
    db: DbDep,
    claims: ClaimsDep,
) -> PreferencesOut:
    user_id = uuid.UUID(claims["sub"])

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise AppError("not_found", "User not found", 404)

    # Shallow-merge so callers can patch a subset of preference keys.
    merged = {**(user.notification_prefs or {}), **payload.notification_prefs}
    user.notification_prefs = merged
    await db.commit()

    return PreferencesOut(notification_prefs=merged)
