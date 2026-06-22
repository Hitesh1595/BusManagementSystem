"""Payments schemas (spec §8.13). Amounts are output as float for the JSON UI."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import Page

BillingCycle = Literal["one_time", "monthly", "quarterly", "term", "annual"]
InvoiceStatus = Literal["draft", "sent", "paid", "overdue", "cancelled"]
ManualGateway = Literal["manual", "offline"]

# ---------------------------------------------------------------------------
# Fee schedules
# ---------------------------------------------------------------------------


class FeeScheduleCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    billing_cycle: BillingCycle
    effective_from: date
    effective_to: date | None = None
    route_id: uuid.UUID | None = None  # None = school-wide


class FeeScheduleUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    amount: float | None = Field(default=None, gt=0)
    effective_to: date | None = None
    is_active: bool | None = None


class FeeScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    route_id: uuid.UUID | None
    name: str
    amount: float
    currency: str
    billing_cycle: str
    effective_from: date
    effective_to: date | None
    is_active: bool
    created_at: datetime


FeeSchedulePage = Page[FeeScheduleOut]


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


class BulkGenerateIn(BaseModel):
    fee_schedule_id: uuid.UUID
    due_date: date | None = None  # default: effective_from + 30 days


class BulkGenerateOut(BaseModel):
    count: int
    invoice_ids: list[uuid.UUID]


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID
    student_id: uuid.UUID
    fee_schedule_id: uuid.UUID | None
    amount: float
    status: str
    due_date: date | None
    paid_at: datetime | None
    created_at: datetime


InvoicePage = Page[InvoiceOut]


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


class RecordPaymentIn(BaseModel):
    amount: float | None = Field(default=None, gt=0)  # default: full invoice amount
    receipt_no: str | None = Field(default=None, max_length=40)
    gateway: ManualGateway = "manual"


class RecordPaymentOut(BaseModel):
    invoice_id: uuid.UUID
    payment_id: uuid.UUID
    status: str
    receipt_no: str | None
    paid_at: datetime | None
