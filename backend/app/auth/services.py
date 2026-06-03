"""
Auth services:
  - Account lockout (Redis): record_failed_login, is_locked, reset_attempts
  - Refresh token rotation + family theft detection:
      issue_refresh_token, _get_by_hash, rotate_refresh_token,
      refresh_is_valid, revoke_all_families_for_user
  - Password reset: request_password_reset, reset_password
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthToken, RefreshToken, User
from app.config import get_settings
from app.core.security import hash_password, hash_token, new_refresh_token
from app.redis_client import get_redis

log = structlog.get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class TokenReuseError(Exception):
    """Raised when a revoked refresh token is presented (theft-detection)."""


# ---------------------------------------------------------------------------
# Task 2.3 — Account lockout (Redis)
# Spec §17.3: on Redis outage, skip gracefully (log warning, never raise).
# ---------------------------------------------------------------------------

_LOCKOUT_KEY = "login_attempts:{email}"


def _lockout_key(email: str) -> str:
    return f"login_attempts:{email.lower()}"


async def record_failed_login(email: str) -> None:
    """Increment failed-login counter; set TTL when threshold is reached."""
    try:
        r = get_redis()
        key = _lockout_key(email)
        count = await r.incr(key)
        if count >= settings.ACCOUNT_LOCKOUT_THRESHOLD:
            await r.expire(key, settings.ACCOUNT_LOCKOUT_TTL_MIN * 60)
    except Exception:
        log.warning("redis.lockout_unavailable", action="record_failed_login", email=email)


async def is_locked(email: str) -> bool:
    """Return True if the account is currently locked out."""
    try:
        r = get_redis()
        val = await r.get(_lockout_key(email))
        if val is None:
            return False
        return int(val) >= settings.ACCOUNT_LOCKOUT_THRESHOLD
    except Exception:
        log.warning("redis.lockout_unavailable", action="is_locked", email=email)
        return False  # degrade gracefully — don't block login on Redis outage


async def reset_attempts(email: str) -> None:
    """Clear failed-login counter on successful authentication."""
    try:
        await get_redis().delete(_lockout_key(email))
    except Exception:
        log.warning("redis.lockout_unavailable", action="reset_attempts", email=email)


# ---------------------------------------------------------------------------
# Task 2.4 — Refresh-token rotation + family theft detection
# Spec §7.1: re-use of a revoked token → revoke entire family (forces re-login).
# ---------------------------------------------------------------------------


async def issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    device_id: str | None = None,
    family_id: uuid.UUID | None = None,
) -> tuple[str, uuid.UUID]:
    """
    Mint a new refresh token, persist its hash, return (raw_token, family_id).
    Always use the returned raw_token — the hash is what is stored.
    """
    raw = new_refresh_token()
    fam = family_id or uuid.uuid4()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw),
            device_id=device_id,
            family_id=fam,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        )
    )
    await db.commit()
    return raw, fam


async def _get_by_hash(db: AsyncSession, raw: str) -> RefreshToken | None:
    """Look up a RefreshToken row by the raw (un-hashed) token value."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))
    )
    return result.scalar_one_or_none()


async def rotate_refresh_token(
    db: AsyncSession, raw: str
) -> tuple[str, uuid.UUID]:
    """
    Rotate a refresh token:
      - If the token is unknown → TokenReuseError
      - If the token is already revoked → revoke the entire family (theft!) + TokenReuseError
      - If the token is expired → TokenReuseError
      - Otherwise: revoke the presented token, issue a new one in the same family.

    Returns (new_raw_token, family_id).
    """
    row = await _get_by_hash(db, raw)
    if row is None:
        raise TokenReuseError("unknown token")

    if row.revoked_at is not None:
        # Theft detected: revoke every active member of this family.
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == row.family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await db.commit()
        log.warning(
            "auth.token_reuse_detected",
            family_id=str(row.family_id),
            user_id=str(row.user_id),
        )
        raise TokenReuseError("token reuse detected; family revoked")

    if row.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise TokenReuseError("expired")

    # Revoke the presented token and issue a fresh one in the same family.
    row.revoked_at = datetime.now(UTC)
    await db.commit()
    return await issue_refresh_token(db, row.user_id, row.device_id, row.family_id)


async def refresh_is_valid(db: AsyncSession, raw: str) -> bool:
    """Return True iff the token exists, is not revoked, and is not expired."""
    row = await _get_by_hash(db, raw)
    if row is None or row.revoked_at is not None:
        return False
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires > datetime.now(UTC)


async def revoke_all_families_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """
    Revoke ALL active refresh tokens for a user.
    Used on password reset (spec §7.3) to force re-login on all devices.
    """
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Task 2.6 — Password reset (spec §7.3)
# ---------------------------------------------------------------------------


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """
    Always returns silently (no enumeration — caller returns 200 regardless).
    If a user exists for the given email, creates an auth_token (hashed, 1-hr
    expiry) and sends a reset link via Resend (or logs it in dev).
    """
    # Import here to avoid circular deps at module load time.
    from app.core.email import send_email

    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    user = result.scalar_one_or_none()
    if user is None:
        log.info("auth.password_reset_requested_unknown_email")
        return

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    auth_tok = AuthToken(
        user_id=user.id,
        token_hash=token_hash,
        type="password_reset",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(auth_tok)
    await db.commit()

    settings = get_settings()
    reset_url = f"{settings.FRONTEND_URL}/reset?token={raw_token}"
    html = (
        f"<p>Hi {user.full_name},</p>"
        f"<p>Click the link below to reset your YatraTrack password. "
        f"This link expires in 1 hour.</p>"
        f'<p><a href="{reset_url}">{reset_url}</a></p>'
        f"<p>If you did not request this, you can safely ignore this email.</p>"
    )
    await send_email(to=user.email, subject="Reset your YatraTrack password", html=html)
    log.info("auth.password_reset_email_sent", user_id=str(user.id))


async def reset_password(db: AsyncSession, raw_token: str, new_pwd: str) -> None:
    """
    Validate the reset token (hash match + not expired + not used),
    update the user's password_hash, mark the token used, and revoke
    all refresh-token families so the user is logged out everywhere.

    Raises AppError 400 on any validation failure.
    """
    from app.errors import AppError

    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == token_hash,
            AuthToken.type == "password_reset",
        )
    )
    auth_tok = result.scalar_one_or_none()

    if auth_tok is None:
        raise AppError("invalid_token", "Invalid or expired reset token", 400)

    now = datetime.now(UTC)
    expires = auth_tok.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)

    if expires < now:
        raise AppError("invalid_token", "Reset token has expired", 400)
    if auth_tok.used_at is not None:
        raise AppError("invalid_token", "Reset token has already been used", 400)

    # Mark token as used.
    auth_tok.used_at = now
    await db.flush()

    # Update the user's password.
    user_result = await db.execute(select(User).where(User.id == auth_tok.user_id))
    user = user_result.scalar_one()
    user.password_hash = hash_password(new_pwd)
    user.updated_at = now
    await db.commit()

    # Force re-login on all devices.
    await revoke_all_families_for_user(db, user.id)
    log.info("auth.password_reset_complete", user_id=str(user.id))
