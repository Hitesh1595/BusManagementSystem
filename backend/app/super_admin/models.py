"""
Platform billing model — the PLATFORM (super_admin) charges each SCHOOL a
monthly platform fee. Distinct from parent transport fees (app/payments), which
are a school↔parent concern.

One invoice per school per month (UNIQUE school_id, period). Reuses the
invoice_status enum from migration 0001. Manual payment recording is inlined
(paid_at / paid_amount / receipt_no) — no gateway in MVP.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, CreatedAtMixin

PLATFORM_INVOICE_STATUS = ("draft", "sent", "paid", "overdue", "cancelled")


class PlatformInvoice(Base, CreatedAtMixin):
    __tablename__ = "platform_invoices"
    __table_args__ = (
        UniqueConstraint("school_id", "period", name="uq_platform_invoice_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # 'YYYY-MM'
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    status: Mapped[str] = mapped_column(
        PGEnum(*PLATFORM_INVOICE_STATUS, name="invoice_status", create_type=False),
        nullable=False,
        server_default="sent",
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    receipt_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
