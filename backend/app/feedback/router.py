"""
Feedback + complaints routers (spec §8.13).

Visibility (OQ-15): a driver sees only an aggregate of their own feedback;
school_admin sees full feedback text and reviews flagged items. Parents/drivers
file complaints; school_admin triages and resolves them.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import DbDep, SchoolScopeDep, require_role
from app.feedback import schemas, services

# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

feedback_router = APIRouter(prefix="/api/v1", tags=["feedback"])


@feedback_router.post("/trips/{trip_id}/feedback", status_code=201)
async def submit_feedback(
    trip_id: UUID,
    body: schemas.FeedbackCreateIn,
    db: DbDep,
    claims: Annotated[dict, Depends(require_role("parent"))],
    school_id: SchoolScopeDep,
) -> schemas.FeedbackOut:
    return await services.submit_feedback(
        db,
        trip_id=trip_id,
        parent_id=UUID(claims["sub"]),
        school_scope=school_id,
        payload=body,
    )


@feedback_router.get("/feedback/my-rating")
async def my_driver_rating(
    db: DbDep,
    claims: Annotated[dict, Depends(require_role("driver"))],
) -> schemas.DriverRatingOut:
    return await services.driver_rating(db, UUID(claims["sub"]))


@feedback_router.get("/feedback")
async def list_feedback(
    db: DbDep,
    claims: Annotated[dict, Depends(require_role("school_admin", "super_admin"))],
    school_id: SchoolScopeDep,
    flagged: Annotated[bool | None, Query()] = None,
    driver_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.FeedbackPage:
    return await services.list_feedback(
        db,
        school_scope=school_id,
        flagged=flagged,
        driver_id=driver_id,
        limit=limit,
        offset=offset,
    )


@feedback_router.put("/feedback/{feedback_id}/review")
async def review_feedback(
    feedback_id: UUID,
    body: schemas.FeedbackReviewIn,
    db: DbDep,
    claims: Annotated[dict, Depends(require_role("school_admin", "super_admin"))],
    school_id: SchoolScopeDep,
) -> schemas.FeedbackOut:
    return await services.review_feedback(
        db, feedback_id=feedback_id, school_scope=school_id, payload=body
    )


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------

complaints_router = APIRouter(prefix="/api/v1/complaints", tags=["complaints"])

_AnyMember = Annotated[
    dict, Depends(require_role("parent", "driver", "school_admin"))
]
_AdminOnly = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]


@complaints_router.post("/", status_code=201)
async def create_complaint(
    body: schemas.ComplaintCreateIn,
    db: DbDep,
    claims: _AnyMember,
    school_id: SchoolScopeDep,
) -> schemas.ComplaintOut:
    return await services.create_complaint(
        db, submitter_id=UUID(claims["sub"]), school_scope=school_id, payload=body
    )


@complaints_router.get("/")
async def list_complaints(
    db: DbDep,
    claims: _AnyMember,
    school_id: SchoolScopeDep,
    status: Annotated[str | None, Query()] = None,
    priority: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.ComplaintPage:
    return await services.list_complaints(
        db,
        requester_id=UUID(claims["sub"]),
        requester_role=claims["role"],
        school_scope=school_id,
        status=status,
        priority=priority,
        limit=limit,
        offset=offset,
    )


@complaints_router.get("/{complaint_id}")
async def get_complaint(
    complaint_id: UUID,
    db: DbDep,
    claims: _AnyMember,
    school_id: SchoolScopeDep,
) -> schemas.ComplaintOut:
    return await services.get_complaint(
        db,
        complaint_id=complaint_id,
        requester_id=UUID(claims["sub"]),
        requester_role=claims["role"],
        school_scope=school_id,
    )


@complaints_router.put("/{complaint_id}/assign")
async def assign_complaint(
    complaint_id: UUID,
    body: schemas.ComplaintAssignIn,
    db: DbDep,
    claims: _AdminOnly,
    school_id: SchoolScopeDep,
) -> schemas.ComplaintOut:
    return await services.assign_complaint(
        db, complaint_id=complaint_id, school_scope=school_id, payload=body
    )


@complaints_router.put("/{complaint_id}/resolve")
async def resolve_complaint(
    complaint_id: UUID,
    body: schemas.ComplaintResolveIn,
    db: DbDep,
    claims: _AdminOnly,
    school_id: SchoolScopeDep,
) -> schemas.ComplaintOut:
    return await services.resolve_complaint(
        db, complaint_id=complaint_id, school_scope=school_id, payload=body
    )


@complaints_router.put("/{complaint_id}/status")
async def set_complaint_status(
    complaint_id: UUID,
    body: schemas.ComplaintStatusIn,
    db: DbDep,
    claims: _AdminOnly,
    school_id: SchoolScopeDep,
) -> schemas.ComplaintOut:
    return await services.set_complaint_status(
        db, complaint_id=complaint_id, school_scope=school_id, status=body.status
    )
