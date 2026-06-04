"""
Notification service helpers.

notify()
  Insert a Notification row and best-effort emit a `notification` Socket.IO
  event to the user's personal room.  The DB commit is done INSIDE this function
  so callers can treat it as fire-and-forget.  If the socket emit fails the
  row is still persisted (in-app bell is always reliable).

emit_to_school()
  Emit a Socket.IO event to the `school:{school_id}` room.
  Pure best-effort — no DB write; does not raise on failure.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.notifications.models import Notification

log = structlog.get_logger(__name__)


async def notify(
    db,
    *,
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    type: str,
    title: str,
    body: str | None = None,
    data: dict[str, Any] | None = None,
) -> Notification:
    """
    Persist a notification row and emit a real-time Socket.IO event to the
    recipient if they are connected.

    DB semantics: commits inside this function.  Caller does not need to commit.

    Socket emit is best-effort: failure is logged but does NOT raise.
    """
    notif = Notification(
        user_id=user_id,
        school_id=school_id,
        type=type,
        title=title,
        body=body,
        data=data or {},
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    # Best-effort real-time push
    try:
        from app.core.socketio import sio, user_room

        payload = {
            "id": str(notif.id),
            "type": notif.type,
            "title": notif.title,
            "body": notif.body,
            "data": notif.data,
            "created_at": notif.created_at.isoformat(),
        }
        await sio.emit("notification", payload, room=user_room(str(user_id)))
    except Exception as exc:
        log.warning(
            "notify.emit_failed",
            user_id=str(user_id),
            title=title,
            exc=str(exc),
        )

    return notif


async def emit_to_school(school_id: uuid.UUID | str, event: str, payload: dict) -> None:
    """
    Emit a Socket.IO event to all sockets in the `school:{school_id}` room.
    Best-effort — failure is logged, never raised.
    """
    try:
        from app.core.socketio import sio

        await sio.emit(event, payload, room=f"school:{school_id}")
    except Exception as exc:
        log.warning(
            "emit_to_school.failed",
            school_id=str(school_id),
            event=event,
            exc=str(exc),
        )
