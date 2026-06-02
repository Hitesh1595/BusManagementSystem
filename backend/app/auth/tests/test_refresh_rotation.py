"""
Focused security tests for refresh-token rotation + family theft detection.

These tests verify:
  1. rotate_refresh_token revokes the old token and issues a new valid one.
  2. Replaying a revoked token raises TokenReuseError AND revokes the entire family.

Tests use the live PostgreSQL instance (docker compose db service).
DATABASE_URL is read from .env in the backend/ directory.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.schools.models  # noqa: F401 — ensure schools FK resolves in metadata
from app.auth import services
from app.auth.models import User
from app.config import get_settings
from app.core.security import hash_password

settings = get_settings()

# ---------------------------------------------------------------------------
# DB session fixture (per-test, uses real Postgres)
# Create engine+session fresh per test to avoid asyncio event-loop conflicts.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()  # keep DB clean after each test
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helper — create a minimal user row directly in the DB
# ---------------------------------------------------------------------------


async def _make_user(db: AsyncSession) -> uuid.UUID:
    """Insert a minimal user and return its UUID."""
    user = User(
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("test1234"),
        full_name="Test User",
        role="parent",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotation_revokes_previous(db: AsyncSession):
    """
    After rotating a refresh token, the old token must be revoked
    and the new one must be valid.
    """
    user_id = await _make_user(db)
    raw1, _fam = await services.issue_refresh_token(db, user_id, device_id="d1")
    raw2, _ = await services.rotate_refresh_token(db, raw1)

    # New token is valid.
    assert await services.refresh_is_valid(db, raw2), "new token should be valid"
    # Old token is revoked.
    assert not await services.refresh_is_valid(db, raw1), "old token should be revoked"


@pytest.mark.asyncio
async def test_reuse_of_revoked_token_revokes_family(db: AsyncSession):
    """
    When an attacker replays an already-rotated token, the entire family must be
    revoked (forcing re-login on all devices) and TokenReuseError must be raised.
    """
    user_id = await _make_user(db)
    raw1, _fam = await services.issue_refresh_token(db, user_id, device_id="d1")
    raw2, _ = await services.rotate_refresh_token(db, raw1)  # legitimate rotation

    # Attacker replays the already-rotated raw1.
    with pytest.raises(services.TokenReuseError):
        await services.rotate_refresh_token(db, raw1)

    # The whole family (including the legitimately issued raw2) must now be revoked.
    assert not await services.refresh_is_valid(db, raw2), (
        "family member raw2 should be revoked after theft detection"
    )
