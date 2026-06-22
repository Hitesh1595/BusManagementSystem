"""
Super-admin console schemas — platform analytics + per-school overview.

Read-only aggregations across all schools. super_admin only (router gate).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import Page
from app.schools.schemas import SchoolOut


class AlertSeverityBreakdown(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class UsersByRole(BaseModel):
    school_admin: int = 0
    driver: int = 0
    parent: int = 0


class SchoolOverviewOut(BaseModel):
    """Per-school drill-down: the school plus live resource counts."""

    school: SchoolOut
    vehicle_count: int
    driver_count: int
    route_count: int
    student_count: int
    active_trip_count: int
    open_alert_count: int
    alert_severity: AlertSeverityBreakdown


class PlatformAnalyticsOut(BaseModel):
    """Platform-wide totals for the super-admin dashboard."""

    total_schools: int
    active_schools: int
    users_by_role: UsersByRole
    active_vehicles: int
    active_routes: int
    active_students: int
    active_trips: int
    open_alerts: int
    alerts_last_24h: int
    alert_severity: AlertSeverityBreakdown


# ---------------------------------------------------------------------------
# Platform billing (platform → school monthly fee)
# ---------------------------------------------------------------------------


class PlatformInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    period: str
    amount: float
    currency: str
    status: str
    due_date: date | None
    paid_at: datetime | None
    paid_amount: float | None
    receipt_no: str | None
    created_at: datetime


PlatformInvoicePage = Page[PlatformInvoiceOut]


class PlatformFeeOverride(BaseModel):
    school_id: uuid.UUID
    amount: float = Field(gt=0)


class GenerateInvoicesIn(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")  # 'YYYY-MM'
    default_amount: float = Field(gt=0)
    due_date: date | None = None
    overrides: list[PlatformFeeOverride] = Field(default_factory=list)


class GenerateInvoicesOut(BaseModel):
    period: str
    count: int


class RecordPlatformPaymentIn(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    receipt_no: str | None = Field(default=None, max_length=40)


class PlatformBillingSummaryOut(BaseModel):
    billed: float
    collected: float
    outstanding: float
    invoice_count: int
    paid_count: int
