"""
Feedback + complaints service layer.

All tenant reads/writes are scoped explicitly by school_id (RLS is defense-in-
depth only while the app connects as the bootstrap superuser — see migration
0010). Drivers may read an aggregate of their own feedback only (OQ-15).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate
from app.errors import AppError
from app.feedback.models import Complaint, TripFeedback
from app.feedback.schemas import (
    ComplaintAssignIn,
    ComplaintCreateIn,
    ComplaintOut,
    ComplaintPage,
    ComplaintResolveIn,
    DriverRatingOut,
    FeedbackCreateIn,
    FeedbackOut,
    FeedbackPage,
    FeedbackReviewIn,
)
from app.students.models import Student, StudentRouteAssignment
from app.tracking.models import Trip

# ---------------------------------------------------------------------------
# Trip feedback
# ---------------------------------------------------------------------------


async def _parent_has_child_on_route(
    db: AsyncSession, parent_id: uuid.UUID, route_id: uuid.UUID
) -> bool:
    stmt = (
        select(Student.id)
        .join(StudentRouteAssignment, StudentRouteAssignment.student_id == Student.id)
        .where(Student.parent_id == parent_id, StudentRouteAssignment.route_id == route_id)
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def submit_feedback(
    db: AsyncSession,
    *,
    trip_id: uuid.UUID,
    parent_id: uuid.UUID,
    school_scope: uuid.UUID | None,
    payload: FeedbackCreateIn,
) -> FeedbackOut:
    trip = (
        await db.execute(select(Trip).where(Trip.id == trip_id))
    ).scalar_one_or_none()
    if trip is None or (school_scope is not None and trip.school_id != school_scope):
        raise AppError("not_found", "Trip not found", 404)
    if trip.status != "completed":
        raise AppError("conflict", "You can only rate a completed trip", 409)
    if not await _parent_has_child_on_route(db, parent_id, trip.route_id):
        raise AppError("forbidden", "No child of yours was on this trip", 403)

    existing = (
        await db.execute(
            select(TripFeedback.id).where(
                TripFeedback.trip_id == trip_id, TripFeedback.parent_id == parent_id
            )
        )
    ).first()
    if existing is not None:
        raise AppError("conflict", "You have already rated this trip", 409)

    feedback = TripFeedback(
        school_id=trip.school_id,
        trip_id=trip_id,
        parent_id=parent_id,
        driver_id=trip.driver_id,
        rating=payload.rating,
        comment=payload.comment,
        is_flagged=payload.rating <= 2,  # auto-flag low ratings (spec §6.7)
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return FeedbackOut.model_validate(feedback)


async def list_feedback(
    db: AsyncSession,
    *,
    school_scope: uuid.UUID | None,
    flagged: bool | None = None,
    driver_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> FeedbackPage:
    stmt = select(TripFeedback)
    if school_scope is not None:
        stmt = stmt.where(TripFeedback.school_id == school_scope)
    if flagged is not None:
        stmt = stmt.where(TripFeedback.is_flagged.is_(flagged))
    if driver_id is not None:
        stmt = stmt.where(TripFeedback.driver_id == driver_id)
    stmt = stmt.order_by(TripFeedback.created_at.desc())

    result = await paginate(stmt, db, limit=limit, offset=offset)
    return FeedbackPage(
        items=[FeedbackOut.model_validate(f) for f in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def review_feedback(
    db: AsyncSession,
    *,
    feedback_id: uuid.UUID,
    school_scope: uuid.UUID | None,
    payload: FeedbackReviewIn,
) -> FeedbackOut:
    stmt = select(TripFeedback).where(TripFeedback.id == feedback_id)
    if school_scope is not None:
        stmt = stmt.where(TripFeedback.school_id == school_scope)
    feedback = (await db.execute(stmt)).scalar_one_or_none()
    if feedback is None:
        raise AppError("not_found", "Feedback not found", 404)

    feedback.admin_reviewed = True
    if payload.admin_notes is not None:
        feedback.admin_notes = payload.admin_notes
    if payload.is_flagged is not None:
        feedback.is_flagged = payload.is_flagged
    await db.commit()
    await db.refresh(feedback)
    return FeedbackOut.model_validate(feedback)


async def driver_rating(db: AsyncSession, driver_id: uuid.UUID) -> DriverRatingOut:
    avg, count = (
        await db.execute(
            select(func.avg(TripFeedback.rating), func.count()).where(
                TripFeedback.driver_id == driver_id
            )
        )
    ).one()
    return DriverRatingOut(
        average=round(float(avg), 2) if avg is not None else None,
        count=count,
    )


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------


async def create_complaint(
    db: AsyncSession,
    *,
    submitter_id: uuid.UUID,
    school_scope: uuid.UUID | None,
    payload: ComplaintCreateIn,
) -> ComplaintOut:
    if school_scope is None:
        raise AppError("validation_error", "A school context is required", 422)
    complaint = Complaint(
        school_id=school_scope,
        submitted_by=submitter_id,
        against_type=payload.against_type,
        against_id=payload.against_id,
        trip_id=payload.trip_id,
        subject=payload.subject,
        description=payload.description,
    )
    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)
    return ComplaintOut.model_validate(complaint)


async def list_complaints(
    db: AsyncSession,
    *,
    requester_id: uuid.UUID,
    requester_role: str,
    school_scope: uuid.UUID | None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ComplaintPage:
    stmt = select(Complaint)
    if school_scope is not None:
        stmt = stmt.where(Complaint.school_id == school_scope)
    # Non-admins only see complaints they submitted.
    if requester_role not in ("school_admin", "super_admin"):
        stmt = stmt.where(Complaint.submitted_by == requester_id)
    if status is not None:
        stmt = stmt.where(Complaint.status == status)
    if priority is not None:
        stmt = stmt.where(Complaint.priority == priority)
    stmt = stmt.order_by(Complaint.created_at.desc())

    result = await paginate(stmt, db, limit=limit, offset=offset)
    return ComplaintPage(
        items=[ComplaintOut.model_validate(c) for c in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def _load_complaint(
    db: AsyncSession,
    *,
    complaint_id: uuid.UUID,
    requester_id: uuid.UUID,
    requester_role: str,
    school_scope: uuid.UUID | None,
) -> Complaint:
    stmt = select(Complaint).where(Complaint.id == complaint_id)
    if school_scope is not None:
        stmt = stmt.where(Complaint.school_id == school_scope)
    complaint = (await db.execute(stmt)).scalar_one_or_none()
    if complaint is None:
        raise AppError("not_found", "Complaint not found", 404)
    if (
        requester_role not in ("school_admin", "super_admin")
        and complaint.submitted_by != requester_id
    ):
        raise AppError("not_found", "Complaint not found", 404)
    return complaint


async def get_complaint(
    db: AsyncSession,
    *,
    complaint_id: uuid.UUID,
    requester_id: uuid.UUID,
    requester_role: str,
    school_scope: uuid.UUID | None,
) -> ComplaintOut:
    complaint = await _load_complaint(
        db,
        complaint_id=complaint_id,
        requester_id=requester_id,
        requester_role=requester_role,
        school_scope=school_scope,
    )
    return ComplaintOut.model_validate(complaint)


async def assign_complaint(
    db: AsyncSession,
    *,
    complaint_id: uuid.UUID,
    school_scope: uuid.UUID | None,
    payload: ComplaintAssignIn,
) -> ComplaintOut:
    complaint = await _load_complaint(
        db,
        complaint_id=complaint_id,
        requester_id=payload.assigned_to,  # unused for admins; kept uniform
        requester_role="school_admin",
        school_scope=school_scope,
    )
    complaint.assigned_to = payload.assigned_to
    if complaint.status == "open":
        complaint.status = "in_review"
    await db.commit()
    await db.refresh(complaint)
    return ComplaintOut.model_validate(complaint)


async def resolve_complaint(
    db: AsyncSession,
    *,
    complaint_id: uuid.UUID,
    school_scope: uuid.UUID | None,
    payload: ComplaintResolveIn,
) -> ComplaintOut:
    complaint = await _load_complaint(
        db,
        complaint_id=complaint_id,
        requester_id=uuid.uuid4(),
        requester_role="school_admin",
        school_scope=school_scope,
    )
    complaint.status = "resolved"
    complaint.resolution_notes = payload.notes
    complaint.resolved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(complaint)
    return ComplaintOut.model_validate(complaint)


async def set_complaint_status(
    db: AsyncSession,
    *,
    complaint_id: uuid.UUID,
    school_scope: uuid.UUID | None,
    status: str,
) -> ComplaintOut:
    complaint = await _load_complaint(
        db,
        complaint_id=complaint_id,
        requester_id=uuid.uuid4(),
        requester_role="school_admin",
        school_scope=school_scope,
    )
    complaint.status = status
    if status in ("resolved", "closed") and complaint.resolved_at is None:
        complaint.resolved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(complaint)
    return ComplaintOut.model_validate(complaint)
