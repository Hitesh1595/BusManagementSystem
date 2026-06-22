"""
Payments service layer — fee schedules, invoice generation, manual payment
recording. Tenant-scoped explicitly by school_id (RLS is defense-in-depth).

Money is handled as Decimal; floats from the API are converted via str() to
avoid binary-float drift (spec §16.3).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import write_audit
from app.core.pagination import paginate
from app.errors import AppError
from app.payments.models import FeeSchedule, Invoice, Payment
from app.payments.schemas import (
    BulkGenerateIn,
    BulkGenerateOut,
    FeeScheduleCreateIn,
    FeeScheduleOut,
    FeeSchedulePage,
    FeeScheduleUpdateIn,
    InvoiceOut,
    InvoicePage,
    RecordPaymentIn,
    RecordPaymentOut,
)
from app.students.models import Student, StudentRouteAssignment

# Invoices in these states are "outstanding" — block re-issuing a duplicate.
_OUTSTANDING = ("draft", "sent", "overdue")


def _money(value: float) -> Decimal:
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# Fee schedules
# ---------------------------------------------------------------------------


async def create_fee_schedule(
    db: AsyncSession, *, school_id: uuid.UUID, payload: FeeScheduleCreateIn
) -> FeeScheduleOut:
    fee = FeeSchedule(
        school_id=school_id,
        route_id=payload.route_id,
        name=payload.name,
        amount=_money(payload.amount),
        billing_cycle=payload.billing_cycle,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    db.add(fee)
    await db.commit()
    await db.refresh(fee)
    return FeeScheduleOut.model_validate(fee)


async def list_fee_schedules(
    db: AsyncSession, *, school_id: uuid.UUID | None, limit: int = 50, offset: int = 0
) -> FeeSchedulePage:
    stmt = select(FeeSchedule)
    if school_id is not None:
        stmt = stmt.where(FeeSchedule.school_id == school_id)
    stmt = stmt.order_by(FeeSchedule.created_at.desc())
    result = await paginate(stmt, db, limit=limit, offset=offset)
    return FeeSchedulePage(
        items=[FeeScheduleOut.model_validate(f) for f in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def update_fee_schedule(
    db: AsyncSession,
    *,
    school_id: uuid.UUID | None,
    fee_id: uuid.UUID,
    payload: FeeScheduleUpdateIn,
) -> FeeScheduleOut:
    stmt = select(FeeSchedule).where(FeeSchedule.id == fee_id)
    if school_id is not None:
        stmt = stmt.where(FeeSchedule.school_id == school_id)
    fee = (await db.execute(stmt)).scalar_one_or_none()
    if fee is None:
        raise AppError("not_found", "Fee schedule not found", 404)

    data = payload.model_dump(exclude_unset=True)
    if "amount" in data and data["amount"] is not None:
        fee.amount = _money(data.pop("amount"))
    for field, value in data.items():
        setattr(fee, field, value)
    await db.commit()
    await db.refresh(fee)
    return FeeScheduleOut.model_validate(fee)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


async def bulk_generate_invoices(
    db: AsyncSession,
    *,
    school_id: uuid.UUID,
    requester_id: uuid.UUID,
    payload: BulkGenerateIn,
) -> BulkGenerateOut:
    fee = (
        await db.execute(
            select(FeeSchedule).where(
                FeeSchedule.id == payload.fee_schedule_id,
                FeeSchedule.school_id == school_id,
            )
        )
    ).scalar_one_or_none()
    if fee is None:
        raise AppError("not_found", "Fee schedule not found", 404)
    if not fee.is_active:
        raise AppError("conflict", "Fee schedule is inactive", 409)

    # Resolve the billed students (route-scoped or school-wide), one per student.
    if fee.route_id is not None:
        students_stmt = (
            select(Student.id, Student.parent_id)
            .join(StudentRouteAssignment, StudentRouteAssignment.student_id == Student.id)
            .where(
                Student.school_id == school_id,
                Student.is_active.is_(True),
                StudentRouteAssignment.route_id == fee.route_id,
                StudentRouteAssignment.is_active.is_(True),
            )
            .distinct()
        )
    else:
        students_stmt = select(Student.id, Student.parent_id).where(
            Student.school_id == school_id, Student.is_active.is_(True)
        )

    rows = (await db.execute(students_stmt)).all()
    due = payload.due_date or (fee.effective_from + timedelta(days=30))

    created: list[uuid.UUID] = []
    for student_id, parent_id in rows:
        outstanding = (
            await db.execute(
                select(Invoice.id)
                .where(
                    Invoice.fee_schedule_id == fee.id,
                    Invoice.student_id == student_id,
                    Invoice.status.in_(_OUTSTANDING),
                )
                .limit(1)
            )
        ).first()
        if outstanding is not None:
            continue  # already has an unpaid invoice for this fee
        invoice = Invoice(
            school_id=school_id,
            parent_id=parent_id,
            student_id=student_id,
            fee_schedule_id=fee.id,
            amount=fee.amount,
            status="sent",  # issued immediately (no separate send step in MVP)
            due_date=due,
        )
        db.add(invoice)
        await db.flush()
        created.append(invoice.id)

    await write_audit(
        db,
        school_id=school_id,
        user_id=requester_id,
        action="invoice.bulk_generate",
        entity_type="fee_schedule",
        entity_id=fee.id,
        new={"count": len(created)},
    )
    await db.commit()
    return BulkGenerateOut(count=len(created), invoice_ids=created)


async def list_invoices(
    db: AsyncSession,
    *,
    requester_role: str,
    requester_id: uuid.UUID,
    school_scope: uuid.UUID | None,
    status: str | None = None,
    student_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> InvoicePage:
    stmt = select(Invoice)
    if school_scope is not None:
        stmt = stmt.where(Invoice.school_id == school_scope)
    if requester_role == "parent":
        stmt = stmt.where(Invoice.parent_id == requester_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    if student_id is not None:
        stmt = stmt.where(Invoice.student_id == student_id)
    stmt = stmt.order_by(Invoice.created_at.desc())

    result = await paginate(stmt, db, limit=limit, offset=offset)
    return InvoicePage(
        items=[InvoiceOut.model_validate(i) for i in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def _load_invoice(
    db: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    requester_role: str,
    requester_id: uuid.UUID,
    school_scope: uuid.UUID | None,
) -> Invoice:
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    if school_scope is not None:
        stmt = stmt.where(Invoice.school_id == school_scope)
    invoice = (await db.execute(stmt)).scalar_one_or_none()
    if invoice is None:
        raise AppError("not_found", "Invoice not found", 404)
    if requester_role == "parent" and invoice.parent_id != requester_id:
        raise AppError("not_found", "Invoice not found", 404)
    return invoice


async def get_invoice(
    db: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    requester_role: str,
    requester_id: uuid.UUID,
    school_scope: uuid.UUID | None,
) -> InvoiceOut:
    invoice = await _load_invoice(
        db,
        invoice_id=invoice_id,
        requester_role=requester_role,
        requester_id=requester_id,
        school_scope=school_scope,
    )
    return InvoiceOut.model_validate(invoice)


# ---------------------------------------------------------------------------
# Manual payment recording
# ---------------------------------------------------------------------------


async def record_payment(
    db: AsyncSession,
    *,
    school_id: uuid.UUID,
    invoice_id: uuid.UUID,
    requester_id: uuid.UUID,
    payload: RecordPaymentIn,
) -> RecordPaymentOut:
    invoice = (
        await db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id, Invoice.school_id == school_id
            )
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise AppError("not_found", "Invoice not found", 404)
    if invoice.status == "paid":
        raise AppError("conflict", "Invoice is already paid", 409)
    if invoice.status not in ("sent", "overdue"):
        raise AppError("conflict", "Invoice is not payable", 409)

    amount = _money(payload.amount) if payload.amount is not None else invoice.amount
    payment = Payment(
        school_id=school_id,
        invoice_id=invoice.id,
        amount=amount,
        currency="INR",
        gateway=payload.gateway,
        status="completed",
        receipt_no=payload.receipt_no,
    )
    db.add(payment)
    await db.flush()

    invoice.status = "paid"
    invoice.paid_at = datetime.now(UTC)

    await write_audit(
        db,
        school_id=school_id,
        user_id=requester_id,
        action="payment.record",
        entity_type="invoice",
        entity_id=invoice.id,
        new={"payment_id": str(payment.id), "amount": str(amount)},
    )
    await db.commit()
    await db.refresh(payment)
    return RecordPaymentOut(
        invoice_id=invoice.id,
        payment_id=payment.id,
        status=invoice.status,
        receipt_no=payment.receipt_no,
        paid_at=invoice.paid_at,
    )
