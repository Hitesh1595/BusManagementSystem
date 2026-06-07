"""
AuditLog model — spec §6.6.

High-volume table: BIGSERIAL PK (not UUID).
school_id / user_id are nullable (super_admin / system actions produce NULL).

write_audit() is a fire-and-forget helper; the caller is responsible for
committing the session (or the helper flushes immediately, no commit).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, CreatedAtMixin


class AuditLog(Base, CreatedAtMixin):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("idx_audit_school_time", "school_id", "created_at"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Stored as text; Postgres accepts text→inet implicit cast in queries.
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Helper — insert an audit row; caller must commit the session.
# ---------------------------------------------------------------------------

async def write_audit(
    db,
    *,
    school_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    """
    Add an AuditLog row to *db* and flush (does NOT commit).
    The calling request handler is responsible for committing.

    Usage::

        await write_audit(
            db,
            school_id=school.id,
            user_id=claims_user_id,
            action="school.update",
            entity_type="school",
            entity_id=school.id,
            old={"name": old_name},
            new={"name": new_name},
            ip=request.client.host,
        )
        await db.commit()
    """
    row = AuditLog(
        school_id=school_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old,
        new_values=new,
        ip_address=ip,
    )
    db.add(row)
    await db.flush()
    return row
