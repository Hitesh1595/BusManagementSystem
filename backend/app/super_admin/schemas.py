"""
Super-admin console schemas — platform analytics + per-school overview.

Read-only aggregations across all schools. super_admin only (router gate).
"""

from __future__ import annotations

from pydantic import BaseModel

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
