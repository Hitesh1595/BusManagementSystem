"""
Payments models (spec §6.7 / §16, V2). Manual/offline only — no gateway in MVP.

  FeeSchedule — a recurring/one-time fee, school-wide (route_id NULL) or per route.
  Invoice     — a fee billed to a parent for a student.
  Payment     — a recorded payment against an invoice (gateway='manual'|'offline').

Money is NUMERIC(10,2) / Decimal — never float (spec §16.3). The enums
(billing_cycle, invoice_status, payment_gateway, payment_status) were created in
migration 0001. All three tables carry school_id and are enrolled in RLS (0012).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, CreatedAtMixin

BILLING_CYCLE = ("one_time", "monthly", "quarterly", "term", "annual")
INVOICE_STATUS = ("draft", "sent", "paid", "overdue", "cancelled")
PAYMENT_GATEWAY = ("razorpay", "stripe", "manual", "offline")
PAYMENT_STATUS = ("pending", "completed", "failed", "refunded")


class FeeSchedule(Base, CreatedAtMixin):
    __tablename__ = "fee_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    billing_cycle: Mapped[str] = mapped_column(
        PGEnum(*BILLING_CYCLE, name="billing_cycle", create_type=False), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")


class Invoice(Base, CreatedAtMixin):
    __tablename__ = "invoices"
    __table_args__ = (Index("idx_invoice_parent", "parent_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    fee_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fee_schedules.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        PGEnum(*INVOICE_STATUS, name="invoice_status", create_type=False),
        nullable=False,
        server_default="draft",
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payment(Base, CreatedAtMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    gateway: Mapped[str] = mapped_column(
        PGEnum(*PAYMENT_GATEWAY, name="payment_gateway", create_type=False), nullable=False
    )
    gateway_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gateway_order_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(
        PGEnum(*PAYMENT_STATUS, name="payment_status", create_type=False),
        nullable=False,
        server_default="pending",
    )
    receipt_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
