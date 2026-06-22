"""
Payments router — /api/v1/payments  (spec §8.13, manual/offline only).

Admin manages fee schedules, generates invoices, and records manual payments.
Parents view their own invoices. No payment gateway in the MVP.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import DbDep, SchoolScopeDep, require_role
from app.payments import schemas, services

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

# Reads allow super_admin (cross-school oversight); writes are school-scoped so
# they're school_admin-only (super_admin has no school context → would 500/404).
_AdminOnly = Annotated[dict, Depends(require_role("school_admin", "super_admin"))]
_SchoolWrite = Annotated[dict, Depends(require_role("school_admin"))]
_ParentOrAdmin = Annotated[
    dict, Depends(require_role("parent", "school_admin", "super_admin"))
]


# ---------------------------------------------------------------------------
# Fee schedules (admin)
# ---------------------------------------------------------------------------


@router.post("/fee-schedules", status_code=201)
async def create_fee_schedule(
    body: schemas.FeeScheduleCreateIn,
    db: DbDep,
    claims: _SchoolWrite,
    school_id: SchoolScopeDep,
) -> schemas.FeeScheduleOut:
    return await services.create_fee_schedule(db, school_id=school_id, payload=body)


@router.get("/fee-schedules")
async def list_fee_schedules(
    db: DbDep,
    claims: _AdminOnly,
    school_id: SchoolScopeDep,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.FeeSchedulePage:
    return await services.list_fee_schedules(
        db, school_id=school_id, limit=limit, offset=offset
    )


@router.put("/fee-schedules/{fee_id}")
async def update_fee_schedule(
    fee_id: UUID,
    body: schemas.FeeScheduleUpdateIn,
    db: DbDep,
    claims: _SchoolWrite,
    school_id: SchoolScopeDep,
) -> schemas.FeeScheduleOut:
    return await services.update_fee_schedule(
        db, school_id=school_id, fee_id=fee_id, payload=body
    )


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@router.post("/invoices/bulk-generate", status_code=201)
async def bulk_generate(
    body: schemas.BulkGenerateIn,
    db: DbDep,
    claims: _SchoolWrite,
    school_id: SchoolScopeDep,
) -> schemas.BulkGenerateOut:
    return await services.bulk_generate_invoices(
        db, school_id=school_id, requester_id=UUID(claims["sub"]), payload=body
    )


@router.get("/invoices")
async def list_invoices(
    db: DbDep,
    claims: _ParentOrAdmin,
    school_id: SchoolScopeDep,
    status: Annotated[str | None, Query()] = None,
    student_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.InvoicePage:
    return await services.list_invoices(
        db,
        requester_role=claims["role"],
        requester_id=UUID(claims["sub"]),
        school_scope=school_id,
        status=status,
        student_id=student_id,
        limit=limit,
        offset=offset,
    )


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: UUID,
    db: DbDep,
    claims: _ParentOrAdmin,
    school_id: SchoolScopeDep,
) -> schemas.InvoiceOut:
    return await services.get_invoice(
        db,
        invoice_id=invoice_id,
        requester_role=claims["role"],
        requester_id=UUID(claims["sub"]),
        school_scope=school_id,
    )


@router.post("/invoices/{invoice_id}/record-payment")
async def record_payment(
    invoice_id: UUID,
    body: schemas.RecordPaymentIn,
    db: DbDep,
    claims: _SchoolWrite,
    school_id: SchoolScopeDep,
) -> schemas.RecordPaymentOut:
    return await services.record_payment(
        db,
        school_id=school_id,
        invoice_id=invoice_id,
        requester_id=UUID(claims["sub"]),
        payload=body,
    )
