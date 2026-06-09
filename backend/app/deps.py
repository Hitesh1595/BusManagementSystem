"""
FastAPI dependencies — used throughout all routers.

  DbDep           — async SQLAlchemy session
  get_current_claims / ClaimsDep — parse + validate Bearer JWT
  require_role    — role-gate factory
  get_school_scope / SchoolScopeDep — tenant scoping from JWT claim
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import current_school_id, get_db
from app.errors import AppError

# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# JWT claims dependency — parses Authorization: Bearer <token>
# ---------------------------------------------------------------------------


async def get_current_claims(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """
    Extract and validate the JWT access token from the Authorization header.
    Raises AppError 401 on missing/invalid/expired tokens.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("unauthorized", "Missing bearer token", 401)
    try:
        claims = decode_access_token(authorization.split(" ", 1)[1])
    except Exception as exc:
        raise AppError("unauthorized", "Invalid or expired token", 401) from exc

    # Set the RLS tenant scope for this request: the caller's school, or "" for
    # super_admin (school_id=None) → RLS bypass. System paths never reach here.
    current_school_id.set(claims.get("school_id") or "")
    return claims


ClaimsDep = Annotated[dict, Depends(get_current_claims)]


# ---------------------------------------------------------------------------
# Role gate — returns a dependency that checks the role claim
# ---------------------------------------------------------------------------


def require_role(*roles: str):
    """
    Usage::

        @router.get("/admin-only",
                    dependencies=[Depends(require_role("school_admin", "super_admin"))])
        async def admin_endpoint(
            claims: Annotated[dict, Depends(require_role("school_admin"))],
        ) -> ...: ...
    """

    async def _dep(claims: ClaimsDep) -> dict:
        if claims.get("role") not in roles:
            raise AppError("forbidden", "Insufficient role", 403)
        return claims

    return _dep


# ---------------------------------------------------------------------------
# School scope — derives the tenant UUID from the JWT claim
# super_admin has school_id = None in the token → bypasses scoping (§6.8).
# ---------------------------------------------------------------------------


async def get_school_scope(claims: ClaimsDep) -> UUID | None:
    """
    Returns the school_id UUID from the JWT claim, or None for super_admin.
    Every tenant-scoped query MUST filter by this value (enforced in services).
    """
    sid = claims.get("school_id")
    if sid is None:
        return None
    return UUID(sid)


SchoolScopeDep = Annotated[UUID | None, Depends(get_school_scope)]
