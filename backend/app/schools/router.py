"""
Schools router — /api/v1/schools  (spec §8.2).

Endpoints:
  GET  /{id}                   school_admin (own) | super_admin
  PUT  /{id}                   school_admin (own) | super_admin  — profile update
  PUT  /{id}/settings          school_admin (own) | super_admin  — deep-merge settings
  POST /{id}/regenerate-join-code   school_admin (own) | super_admin

  POST /   (V2)  — super_admin only — create school
  GET  /   (V2)  — super_admin only — list schools
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import DbDep, SchoolScopeDep, require_role
from app.schools import schemas, services

router = APIRouter(prefix="/api/v1/schools", tags=["schools"])

# Role gate: school_admin OR super_admin
_AdminOrSuper = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]


# ---------------------------------------------------------------------------
# GET /{id} — get school details
# ---------------------------------------------------------------------------


@router.get("/{school_id}", status_code=200)
async def get_school(
    school_id: UUID,
    db: DbDep,
    claims: _AdminOrSuper,
    requester_school_id: SchoolScopeDep,
) -> schemas.SchoolOut:
    return await services.get_school(db, school_id, requester_school_id)


# ---------------------------------------------------------------------------
# PUT /{id} — update school profile
# ---------------------------------------------------------------------------


@router.put("/{school_id}", status_code=200)
async def update_school(
    school_id: UUID,
    body: schemas.SchoolUpdateIn,
    db: DbDep,
    claims: _AdminOrSuper,
    requester_school_id: SchoolScopeDep,
) -> schemas.SchoolOut:
    return await services.update_school(db, school_id, requester_school_id, body)


# ---------------------------------------------------------------------------
# PUT /{id}/settings — deep-merge settings JSONB
# ---------------------------------------------------------------------------


@router.put("/{school_id}/settings", status_code=200)
async def update_settings(
    school_id: UUID,
    body: schemas.SchoolSettingsPayload,
    db: DbDep,
    claims: _AdminOrSuper,
    requester_school_id: SchoolScopeDep,
) -> schemas.SchoolOut:
    new_settings = body.model_dump()
    return await services.merge_settings(db, school_id, requester_school_id, new_settings)


# ---------------------------------------------------------------------------
# POST /{id}/regenerate-join-code — rotate join_code
# ---------------------------------------------------------------------------


@router.post("/{school_id}/regenerate-join-code", status_code=200)
async def regenerate_join_code(
    school_id: UUID,
    db: DbDep,
    claims: _AdminOrSuper,
    requester_school_id: SchoolScopeDep,
) -> schemas.JoinCodeOut:
    new_code = await services.regenerate_join_code(db, school_id, requester_school_id)
    return schemas.JoinCodeOut(join_code=new_code)


# ---------------------------------------------------------------------------
# POST / and GET / — super_admin only (cross-school console)
# ---------------------------------------------------------------------------

_SuperOnly = Annotated[dict, Depends(require_role("super_admin"))]


@router.post("/", status_code=201)
async def create_school(
    body: schemas.SchoolCreateIn,
    db: DbDep,
    claims: _SuperOnly,
) -> schemas.SchoolOut:
    return await services.create_school(db, body)


@router.get("/")
async def list_schools(
    db: DbDep,
    claims: _SuperOnly,
    q: Annotated[str | None, Query(description="Filter by name")] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.SchoolPage:
    return await services.list_schools(db, q=q, limit=limit, offset=offset)
