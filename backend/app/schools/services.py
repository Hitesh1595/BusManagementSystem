"""
Schools business logic (spec §8.2).
"""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import from_point, to_point
from app.errors import AppError
from app.schools.models import School
from app.schools.schemas import SchoolOut, SchoolUpdateIn

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _random_join_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _ensure_unique_join_code(db: AsyncSession) -> str:
    """Generate a join code that doesn't already exist in the DB."""
    for _ in range(10):
        code = _random_join_code()
        existing = (
            await db.execute(select(School).where(School.join_code == code))
        ).scalar_one_or_none()
        if existing is None:
            return code
    raise AppError("internal", "Could not generate unique join code", 500)


def _school_to_out(school: School) -> SchoolOut:
    return SchoolOut(
        id=school.id,
        name=school.name,
        address=school.address,
        phone=school.phone,
        email=school.email,
        logo_url=school.logo_url,
        timezone=school.timezone,
        school_location=from_point(school.school_location),
        join_code=school.join_code,
        settings=school.settings or {},
        is_active=school.is_active,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def get_school(
    db: AsyncSession,
    school_id: uuid.UUID,
    requester_school_id: uuid.UUID | None,
) -> SchoolOut:
    """
    Fetch a school by id.
    school_admin may only read their own school (requester_school_id must match).
    super_admin (requester_school_id=None) may read any school.
    """
    row = (
        await db.execute(select(School).where(School.id == school_id))
    ).scalar_one_or_none()

    if row is None:
        raise AppError("not_found", "School not found", 404)

    # Tenant ownership check
    if requester_school_id is not None and row.id != requester_school_id:
        raise AppError("not_found", "School not found", 404)

    return _school_to_out(row)


async def update_school(
    db: AsyncSession,
    school_id: uuid.UUID,
    requester_school_id: uuid.UUID | None,
    payload: SchoolUpdateIn,
) -> SchoolOut:
    """Update profile fields of a school."""
    row = (
        await db.execute(select(School).where(School.id == school_id))
    ).scalar_one_or_none()

    if row is None:
        raise AppError("not_found", "School not found", 404)

    if requester_school_id is not None and row.id != requester_school_id:
        raise AppError("not_found", "School not found", 404)

    if payload.name is not None:
        row.name = payload.name
    if payload.address is not None:
        row.address = payload.address
    if payload.phone is not None:
        row.phone = payload.phone
    if payload.email is not None:
        row.email = payload.email
    if payload.logo_url is not None:
        row.logo_url = payload.logo_url
    if payload.timezone is not None:
        row.timezone = payload.timezone
    if payload.school_location is not None:
        row.school_location = to_point(
            payload.school_location.lat, payload.school_location.lng
        )

    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return _school_to_out(row)


async def merge_settings(
    db: AsyncSession,
    school_id: uuid.UUID,
    requester_school_id: uuid.UUID | None,
    new_settings: dict[str, Any],
) -> SchoolOut:
    """
    Deep-merge *new_settings* into the existing settings JSONB.
    Existing keys NOT present in the payload are preserved.
    """
    row = (
        await db.execute(select(School).where(School.id == school_id))
    ).scalar_one_or_none()

    if row is None:
        raise AppError("not_found", "School not found", 404)

    if requester_school_id is not None and row.id != requester_school_id:
        raise AppError("not_found", "School not found", 404)

    existing: dict[str, Any] = row.settings or {}
    merged = {**existing, **new_settings}  # shallow merge per spec
    row.settings = merged
    row.updated_at = datetime.now(UTC)

    # Use flag_modified so SQLAlchemy detects the JSONB mutation
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(row, "settings")

    await db.commit()
    await db.refresh(row)
    return _school_to_out(row)


async def regenerate_join_code(
    db: AsyncSession,
    school_id: uuid.UUID,
    requester_school_id: uuid.UUID | None,
) -> str:
    """Rotate the school's join code to a new unique value."""
    row = (
        await db.execute(select(School).where(School.id == school_id))
    ).scalar_one_or_none()

    if row is None:
        raise AppError("not_found", "School not found", 404)

    if requester_school_id is not None and row.id != requester_school_id:
        raise AppError("not_found", "School not found", 404)

    new_code = await _ensure_unique_join_code(db)
    row.join_code = new_code
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return new_code
