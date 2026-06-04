"""
Shared school-scoped CRUD helpers.

Usage:
  obj = await get_scoped_or_404(db, Vehicle, vehicle_id, school_id)
  stmt = scoped_select(Vehicle, school_id)  # returns a Select statement

school_id=None  →  super_admin bypass (no tenant filter applied).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError


async def get_scoped_or_404(
    db: AsyncSession,
    model,
    obj_id: UUID,
    school_id: UUID | None,
):
    """
    Fetch model by PK + optional school_id filter.
    Raises AppError 404 if not found (or belongs to a different school).
    """
    stmt = select(model).where(model.id == obj_id)
    if school_id is not None:  # super_admin (None) bypasses tenant filter
        stmt = stmt.where(model.school_id == school_id)
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise AppError("not_found", f"{model.__name__} not found", 404)
    return obj


def scoped_select(model, school_id: UUID | None, active_only: bool = True):
    """
    Build a SELECT scoped to school_id (if not None) and optionally
    filtered to is_active=True.
    """
    stmt = select(model)
    if school_id is not None:
        stmt = stmt.where(model.school_id == school_id)
    if active_only and hasattr(model, "is_active"):
        stmt = stmt.where(model.is_active.is_(True))
    return stmt
