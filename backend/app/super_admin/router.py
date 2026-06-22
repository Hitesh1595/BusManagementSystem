"""
Super-admin console router — /api/v1/super-admin  (super_admin only).

Read-only cross-tenant aggregations powering the platform dashboard and the
per-school drill-down.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import DbDep, require_role
from app.super_admin import schemas, services

router = APIRouter(
    prefix="/api/v1/super-admin",
    tags=["super-admin"],
    dependencies=[Depends(require_role("super_admin"))],
)


@router.get("/analytics/platform")
async def platform_analytics(db: DbDep) -> schemas.PlatformAnalyticsOut:
    return await services.platform_analytics(db)


@router.get("/schools/{school_id}/overview")
async def school_overview(
    school_id: UUID, db: DbDep
) -> schemas.SchoolOverviewOut:
    return await services.school_overview(db, school_id)


# ---------------------------------------------------------------------------
# Platform billing (platform → school monthly fee)
# ---------------------------------------------------------------------------


@router.post("/platform-invoices/generate", status_code=201)
async def generate_platform_invoices(
    body: schemas.GenerateInvoicesIn, db: DbDep
) -> schemas.GenerateInvoicesOut:
    return await services.generate_platform_invoices(db, payload=body)


@router.get("/platform-invoices")
async def list_platform_invoices(
    db: DbDep,
    period: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=100, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.PlatformInvoicePage:
    return await services.list_platform_invoices(
        db, period=period, status=status, limit=limit, offset=offset
    )


@router.post("/platform-invoices/{invoice_id}/record-payment")
async def record_platform_payment(
    invoice_id: UUID, body: schemas.RecordPlatformPaymentIn, db: DbDep
) -> schemas.PlatformInvoiceOut:
    return await services.record_platform_payment(
        db, invoice_id=invoice_id, payload=body
    )


@router.get("/platform-billing/summary")
async def platform_billing_summary(
    db: DbDep, period: Annotated[str | None, Query()] = None
) -> schemas.PlatformBillingSummaryOut:
    return await services.platform_billing_summary(db, period=period)
