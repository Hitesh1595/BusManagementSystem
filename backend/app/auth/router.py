"""
Auth router — /api/v1/auth

Implements all endpoints from spec §8.1:
  POST /register   POST /login   POST /refresh   POST /logout
  POST /forgot-password  POST /reset-password
  GET  /me         PUT  /me
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, Response
from sqlalchemy import func, select, update

from app.auth import schemas, services
from app.auth.models import RefreshToken, User
from app.auth.services import TokenReuseError
from app.config import get_settings
from app.core.security import encode_access_token, hash_password, hash_token, verify_password
from app.deps import ClaimsDep, DbDep
from app.errors import AppError
from app.schools.models import School

log = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Refresh cookie settings (spec §7.1)
_COOKIE_NAME = "refresh_token"
_COOKIE_ATTRS: dict = dict(
    httponly=True,
    secure=True,
    samesite="strict",
    path="/api/v1/auth",
    max_age=settings.REFRESH_TOKEN_TTL_DAYS * 86_400,
)


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(_COOKIE_NAME, raw_token, **_COOKIE_ATTRS)


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(_COOKIE_NAME, path="/api/v1/auth")


def _user_out(user: User) -> schemas.UserOut:
    return schemas.UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        school_id=user.school_id,
    )


def _token_out(access_token: str, user: User) -> schemas.TokenOut:
    return schemas.TokenOut(access_token=access_token, user=_user_out(user))


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------


@router.post("/register", status_code=200)
async def register(
    body: schemas.RegisterIn,
    response: Response,
    db: DbDep,
) -> schemas.TokenOut:
    """
    Parent self-registration with school join_code.
    422 if join_code invalid, 409 if email already exists.
    """
    # Validate join_code
    school_result = await db.execute(
        select(School).where(School.join_code == body.join_code, School.is_active.is_(True))
    )
    school = school_result.scalar_one_or_none()
    if school is None:
        raise AppError(
            "validation_error",
            "Invalid or expired join code",
            422,
            {"field": "join_code"},
        )

    # Case-insensitive email uniqueness check
    dup = await db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    )
    if dup.scalar_one_or_none() is not None:
        raise AppError("conflict", "Email address is already registered", 409)

    user = User(
        school_id=school.id,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        phone=body.phone,
        role="parent",
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = encode_access_token(
        sub=str(user.id),
        school_id=str(school.id),
        role=user.role,
    )
    raw_refresh, _ = await services.issue_refresh_token(db, user.id)
    _set_refresh_cookie(response, raw_refresh)

    structlog.contextvars.bind_contextvars(user_id=str(user.id), school_id=str(school.id))
    log.info("auth.registered", user_id=str(user.id), school_id=str(school.id))
    return _token_out(access_token, user)


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@router.post("/login", status_code=200)
async def login(
    body: schemas.LoginIn,
    response: Response,
    db: DbDep,
) -> schemas.TokenOut:
    """
    Authenticate with email + password.
    401 on bad credentials, 423 if account is locked.
    """
    # Lockout check first (before hitting the DB password verify to avoid timing oracle)
    if await services.is_locked(body.email):
        raise AppError("locked", "Account temporarily locked — too many failed attempts", 423)

    result = await db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        await services.record_failed_login(body.email)
        # Re-check lock so the 5th attempt immediately returns 423
        if await services.is_locked(body.email):
            raise AppError("locked", "Account temporarily locked — too many failed attempts", 423)
        raise AppError("unauthorized", "Invalid email or password", 401)

    if not user.is_active:
        raise AppError("unauthorized", "Account is deactivated", 401)

    await services.reset_attempts(body.email)

    # Update last_login_at
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login_at=datetime.now(UTC))
    )
    await db.commit()
    await db.refresh(user)

    access_token = encode_access_token(
        sub=str(user.id),
        school_id=str(user.school_id) if user.school_id else None,
        role=user.role,
    )
    raw_refresh, _ = await services.issue_refresh_token(db, user.id)
    _set_refresh_cookie(response, raw_refresh)

    structlog.contextvars.bind_contextvars(user_id=str(user.id), school_id=str(user.school_id))
    log.info("auth.login", user_id=str(user.id))
    return _token_out(access_token, user)


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", status_code=200)
async def refresh(
    response: Response,
    db: DbDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    """
    Rotate the refresh token.  Reuse of a revoked token → 401 + family revoke.
    """
    if not refresh_token:
        raise AppError("unauthorized", "Missing refresh token cookie", 401)

    try:
        new_raw, _ = await services.rotate_refresh_token(db, refresh_token)
    except TokenReuseError as exc:
        _clear_refresh_cookie(response)
        raise AppError("unauthorized", "Refresh token invalid or reused", 401) from exc

    # Fetch user to re-issue access token with fresh claims
    tok_result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(new_raw))
    )
    rt_row = tok_result.scalar_one_or_none()
    if rt_row is None:
        raise AppError("unauthorized", "Internal error resolving new token", 401)

    user_result = await db.execute(select(User).where(User.id == rt_row.user_id))
    user = user_result.scalar_one()

    access_token = encode_access_token(
        sub=str(user.id),
        school_id=str(user.school_id) if user.school_id else None,
        role=user.role,
    )
    _set_refresh_cookie(response, new_raw)
    return {"access_token": access_token}


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=200)
async def logout(
    response: Response,
    db: DbDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    """Revoke the current refresh-token family and clear the cookie."""
    if refresh_token:
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
        )
        rt = result.scalar_one_or_none()
        if rt and rt.revoked_at is None:
            await services.revoke_all_families_for_user(db, rt.user_id)

    _clear_refresh_cookie(response)
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /forgot-password
# ---------------------------------------------------------------------------


@router.post("/forgot-password", status_code=200)
async def forgot_password(body: schemas.ForgotIn, db: DbDep) -> dict:
    """Always returns 200 — no user enumeration."""
    await services.request_password_reset(db, body.email)
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /reset-password
# ---------------------------------------------------------------------------


@router.post("/reset-password", status_code=200)
async def reset_password(body: schemas.ResetIn, db: DbDep) -> dict:
    """Validate reset token, set new password, revoke all refresh families."""
    await services.reset_password(db, body.token, body.new_password)
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@router.get("/me", status_code=200)
async def get_me(claims: ClaimsDep, db: DbDep) -> schemas.UserOut:
    """Return the current user's profile."""
    user_id = claims["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError("not_found", "User not found", 404)
    structlog.contextvars.bind_contextvars(user_id=user_id, school_id=claims.get("school_id"))
    return _user_out(user)


# ---------------------------------------------------------------------------
# PUT /me
# ---------------------------------------------------------------------------


@router.put("/me", status_code=200)
async def update_me(
    body: schemas.MeUpdateIn,
    claims: ClaimsDep,
    db: DbDep,
) -> schemas.UserOut:
    """Update the current user's profile (full_name, phone, notification_prefs)."""
    user_id = claims["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError("not_found", "User not found", 404)

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.phone is not None:
        user.phone = body.phone
    if body.notification_prefs is not None:
        user.notification_prefs = body.notification_prefs
    user.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(user)
    return _user_out(user)
