"""
Scheduled vehicle compliance job — spec §11.

check_vehicle_compliance:
  Daily at 07:00 IST.
  For each vehicle, check insurance_expiry and fitness_expiry:
    - 30/7/1 days out → create Alert(type=insurance_expiry, severity varies).
    - On or after expiry → set vehicle.is_active=False + alert.
  Idempotent per vehicle+threshold: skip if an unresolved insurance_expiry
  alert already exists for that vehicle (matched via metadata vehicle_id +
  days_until_expiry bucket).
"""

from __future__ import annotations

import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, select

from app.alerts.models import Alert
from app.auth.models import User
from app.config import get_settings
from app.database import SessionLocal
from app.notifications.services import notify
from app.vehicles.models import Vehicle

log = structlog.get_logger(__name__)
settings = get_settings()

IST = ZoneInfo("Asia/Kolkata")

# Thresholds (days) at which to alert
EXPIRY_WARN_DAYS = [30, 7, 1]


def _severity_for_days(days: int) -> str:
    if days <= 1:
        return "critical"
    if days <= 7:
        return "high"
    return "medium"


async def check_vehicle_compliance() -> None:
    """
    Check all vehicles for upcoming or past insurance/fitness expiry.
    Creates alerts and deactivates vehicles past expiry.
    Idempotent: skip if matching unresolved alert already exists.
    """
    t0 = time.monotonic()
    today_ist = datetime.now(IST).date()
    alerts_created = 0

    try:
        async with SessionLocal() as db:
            vehicles = (
                await db.execute(select(Vehicle))
            ).scalars().all()

            for vehicle in vehicles:
                for field_name in ("insurance_expiry", "fitness_expiry"):
                    expiry_date: date | None = getattr(vehicle, field_name)
                    if expiry_date is None:
                        continue

                    days_until = (expiry_date - today_ist).days

                    # Already expired
                    if days_until < 0:
                        severity = "critical"
                        threshold_key = "expired"
                        title = f"Vehicle {field_name.replace('_', ' ').title()} Expired"
                        desc = (
                            f"Vehicle {vehicle.plate_number}: {field_name} expired on "
                            f"{expiry_date} ({abs(days_until)} days ago). "
                            f"Vehicle deactivated."
                        )
                        # Deactivate vehicle if still active
                        if vehicle.is_active:
                            vehicle.is_active = False
                            log.info(
                                "check_vehicle_compliance.deactivated",
                                vehicle_id=str(vehicle.id),
                                field=field_name,
                                expiry=str(expiry_date),
                            )
                    elif days_until in EXPIRY_WARN_DAYS:
                        severity = _severity_for_days(days_until)
                        threshold_key = str(days_until)
                        title = f"Vehicle {field_name.replace('_', ' ').title()} Expiring Soon"
                        desc = (
                            f"Vehicle {vehicle.plate_number}: {field_name} expires on "
                            f"{expiry_date} ({days_until} day(s) remaining)."
                        )
                    else:
                        continue

                    # Idempotency: check for existing unresolved alert for same
                    # vehicle + field + threshold bucket
                    existing = (
                        await db.execute(
                            select(Alert).where(
                                and_(
                                    Alert.type == "insurance_expiry",
                                    Alert.resolved_at.is_(None),
                                    # Use school_id + vehicle metadata to scope
                                    Alert.school_id == vehicle.school_id,
                                    Alert.metadata_["vehicle_id"].astext == str(vehicle.id),
                                    Alert.metadata_["field"].astext == field_name,
                                    Alert.metadata_["threshold"].astext == threshold_key,
                                )
                            )
                        )
                    ).scalar_one_or_none()

                    if existing is not None:
                        continue  # Already alerted

                    alert = Alert(
                        school_id=vehicle.school_id,
                        trip_id=None,
                        type="insurance_expiry",
                        severity=severity,
                        title=title,
                        description=desc,
                        metadata_={
                            "vehicle_id": str(vehicle.id),
                            "plate_number": vehicle.plate_number,
                            "field": field_name,
                            "expiry_date": str(expiry_date),
                            "threshold": threshold_key,
                        },
                    )
                    db.add(alert)
                    await db.flush()

                    # Notify school admins
                    admins = (
                        await db.execute(
                            select(User).where(
                                and_(
                                    User.school_id == vehicle.school_id,
                                    User.role == "school_admin",
                                    User.is_active.is_(True),
                                )
                            )
                        )
                    ).scalars().all()

                    for admin in admins:
                        await notify(
                            db,
                            user_id=admin.id,
                            school_id=vehicle.school_id,
                            type="alert",
                            title=title,
                            body=desc,
                            data={
                                "vehicle_id": str(vehicle.id),
                                "alert_id": str(alert.id),
                            },
                        )

                    alerts_created += 1
                    log.info(
                        "check_vehicle_compliance.alert_created",
                        task_name="check_vehicle_compliance",
                        school_id=str(vehicle.school_id),
                        vehicle_id=str(vehicle.id),
                        field=field_name,
                        days_until=days_until,
                    )

            await db.commit()

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error(
            "check_vehicle_compliance.failed",
            task_name="check_vehicle_compliance",
            duration_ms=duration_ms,
            status="error",
            exc=str(exc),
        )
        return

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "check_vehicle_compliance.done",
        task_name="check_vehicle_compliance",
        alerts_created=alerts_created,
        duration_ms=duration_ms,
        status="ok",
    )
