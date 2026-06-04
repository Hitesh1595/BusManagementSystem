"""
Scheduled tracking jobs — spec §11.

generate_daily_trips:
  Daily at TRIP_AUTOGEN_HOUR (06:00 IST).
  For each active school, call generate_trips(db, school_id, today_in_school_tz).
  Idempotent: generate_trips uses INSERT ... ON CONFLICT DO NOTHING.

check_driver_no_show:
  Every 5 min, only between SCHOOL_HOURS_START and SCHOOL_HOURS_END.
  Trips with status='scheduled' AND scheduled_departure_at + 15 min < now().
  Create Alert(type=driver_no_show, severity=high) + notify school admins.
  Idempotent: check for existing unresolved driver_no_show alert for same trip.

ensure_gps_partitions:
  Daily at 00:30 IST.
  Create the next month's gps_logs_YYYY_MM partition if not already present.
  Idempotent via IF NOT EXISTS pattern.

cleanup_gps_logs:
  Daily at 01:00 IST.
  DROP gps_logs partitions whose entire date range is older than GPS_RETENTION_DAYS.
"""

from __future__ import annotations

import calendar
import time
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, select, text

from app.alerts.models import Alert
from app.auth.models import User
from app.config import get_settings
from app.database import SessionLocal
from app.notifications.services import notify
from app.schools.models import School
from app.tracking.models import Trip
from app.tracking.services import generate_trips

log = structlog.get_logger(__name__)
settings = get_settings()

IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# generate_daily_trips
# ---------------------------------------------------------------------------


async def generate_daily_trips() -> None:
    """Generate trips for all active schools for today (in school TZ)."""
    t0 = time.monotonic()
    total_created = 0
    school_count = 0

    try:
        async with SessionLocal() as db:
            schools = (
                await db.execute(select(School).where(School.is_active.is_(True)))
            ).scalars().all()

            for school in schools:
                school_count += 1
                tz = ZoneInfo(school.timezone or "Asia/Kolkata")
                today = datetime.now(tz).date()
                try:
                    result = await generate_trips(db, school.id, today)
                    total_created += result.get("created", 0)
                    log.info(
                        "generate_daily_trips.school_done",
                        task_name="generate_daily_trips",
                        school_id=str(school.id),
                        created=result.get("created", 0),
                        date=str(today),
                    )
                except Exception as exc:
                    log.error(
                        "generate_daily_trips.school_error",
                        task_name="generate_daily_trips",
                        school_id=str(school.id),
                        exc=str(exc),
                    )

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error(
            "generate_daily_trips.failed",
            task_name="generate_daily_trips",
            duration_ms=duration_ms,
            status="error",
            exc=str(exc),
        )
        return

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "generate_daily_trips.done",
        task_name="generate_daily_trips",
        schools=school_count,
        total_created=total_created,
        duration_ms=duration_ms,
        status="ok",
    )


# ---------------------------------------------------------------------------
# check_driver_no_show
# ---------------------------------------------------------------------------


async def check_driver_no_show() -> None:
    """
    Find scheduled trips whose departure was >15 min ago and create a
    driver_no_show alert if one doesn't already exist.
    Runs every 5 min but only acts during SCHOOL_HOURS_START – SCHOOL_HOURS_END.
    """
    t0 = time.monotonic()

    # School-hours gate (IST)
    now_ist = datetime.now(IST)
    if not (settings.SCHOOL_HOURS_START <= now_ist.hour < settings.SCHOOL_HOURS_END):
        log.debug(
            "check_driver_no_show.outside_school_hours",
            task_name="check_driver_no_show",
            hour_ist=now_ist.hour,
        )
        return

    now_utc = datetime.now(UTC)
    cutoff = now_utc - timedelta(minutes=15)
    alerts_created = 0

    try:
        async with SessionLocal() as db:
            # Trips that are scheduled and overdue by 15+ minutes
            stmt = select(Trip).where(
                and_(
                    Trip.status == "scheduled",
                    Trip.scheduled_departure_at < cutoff,
                )
            )
            overdue_trips = (await db.execute(stmt)).scalars().all()

            for trip in overdue_trips:
                # Idempotency: check for an existing unresolved driver_no_show alert
                existing = (
                    await db.execute(
                        select(Alert).where(
                            and_(
                                Alert.trip_id == trip.id,
                                Alert.type == "driver_no_show",
                                Alert.resolved_at.is_(None),
                            )
                        )
                    )
                ).scalar_one_or_none()

                if existing is not None:
                    continue  # Already alerted for this trip

                # Create alert
                alert = Alert(
                    school_id=trip.school_id,
                    trip_id=trip.id,
                    type="driver_no_show",
                    severity="high",
                    title="Driver No-Show",
                    description=(
                        f"Trip scheduled at "
                        f"{trip.scheduled_departure_at.strftime('%H:%M UTC')} "
                        f"has not started (driver not present)."
                    ),
                    metadata_={"trip_id": str(trip.id)},
                )
                db.add(alert)
                await db.flush()  # get alert.id before commit

                # Notify school admins
                admin_stmt = select(User).where(
                    and_(
                        User.school_id == trip.school_id,
                        User.role == "school_admin",
                        User.is_active.is_(True),
                    )
                )
                admins = (await db.execute(admin_stmt)).scalars().all()

                for admin in admins:
                    await notify(
                        db,
                        user_id=admin.id,
                        school_id=trip.school_id,
                        type="alert",
                        title="Driver No-Show",
                        body=(
                            f"Trip (id={str(trip.id)[:8]}…) scheduled at "
                            f"{trip.scheduled_departure_at.strftime('%H:%M UTC')} "
                            f"has not started."
                        ),
                        data={"trip_id": str(trip.id), "alert_id": str(alert.id)},
                    )

                alerts_created += 1
                log.info(
                    "check_driver_no_show.alert_created",
                    task_name="check_driver_no_show",
                    school_id=str(trip.school_id),
                    trip_id=str(trip.id),
                )

            await db.commit()

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error(
            "check_driver_no_show.failed",
            task_name="check_driver_no_show",
            duration_ms=duration_ms,
            status="error",
            exc=str(exc),
        )
        return

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "check_driver_no_show.done",
        task_name="check_driver_no_show",
        alerts_created=alerts_created,
        duration_ms=duration_ms,
        status="ok",
    )


# ---------------------------------------------------------------------------
# ensure_gps_partitions
# ---------------------------------------------------------------------------


def _partition_bounds(year: int, month: int) -> tuple[str, str]:
    """Return (start_inclusive, end_exclusive) date strings for a calendar month."""
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day) + timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


async def ensure_gps_partitions() -> None:
    """
    Create the next month's gps_logs partition if it doesn't already exist.
    Idempotent (IF NOT EXISTS).
    """
    t0 = time.monotonic()

    today = datetime.now(IST).date()
    last_day = calendar.monthrange(today.year, today.month)[1]
    next_month = date(today.year, today.month, last_day) + timedelta(days=1)

    table_name = f"gps_logs_{next_month.year:04d}_{next_month.month:02d}"
    start, end = _partition_bounds(next_month.year, next_month.month)

    sql = (
        f"CREATE TABLE IF NOT EXISTS {table_name} "
        f"PARTITION OF gps_logs "
        f"FOR VALUES FROM ('{start}') TO ('{end}')"
    )

    try:
        async with SessionLocal() as db:
            await db.execute(text(sql))
            await db.commit()
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error(
            "ensure_gps_partitions.failed",
            task_name="ensure_gps_partitions",
            table=table_name,
            duration_ms=duration_ms,
            status="error",
            exc=str(exc),
        )
        return

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "ensure_gps_partitions.done",
        task_name="ensure_gps_partitions",
        table=table_name,
        start=start,
        end=end,
        duration_ms=duration_ms,
        status="ok",
    )


# ---------------------------------------------------------------------------
# cleanup_gps_logs
# ---------------------------------------------------------------------------


async def cleanup_gps_logs() -> None:
    """
    DROP gps_logs child partitions whose entire date range is older than
    GPS_RETENTION_DAYS days.

    Discovery: query pg_inherits + pg_class to find child table names, then
    check the partition bound against retention horizon.
    """
    t0 = time.monotonic()
    retention_days = settings.GPS_RETENTION_DAYS
    cutoff = datetime.now(UTC).date() - timedelta(days=retention_days)
    dropped: list[str] = []

    # Query child partition names for gps_logs
    discover_sql = text("""
        SELECT c.relname AS partition_name
        FROM pg_inherits i
        JOIN pg_class p ON p.oid = i.inhparent
        JOIN pg_class c ON c.oid = i.inhrelid
        WHERE p.relname = 'gps_logs'
        ORDER BY c.relname
    """)

    try:
        async with SessionLocal() as db:
            rows = (await db.execute(discover_sql)).fetchall()
            partitions = [row[0] for row in rows]

            for table_name in partitions:
                # Name pattern: gps_logs_YYYY_MM
                parts = table_name.split("_")
                if len(parts) < 4:
                    continue
                try:
                    year = int(parts[2])
                    month = int(parts[3])
                except ValueError:
                    continue

                # Partition end = first day of month after the partition month
                last_day = calendar.monthrange(year, month)[1]
                partition_end = date(year, month, last_day)

                if partition_end < cutoff:
                    try:
                        await db.execute(
                            text(f"DROP TABLE IF EXISTS {table_name}")
                        )
                        dropped.append(table_name)
                        log.info(
                            "cleanup_gps_logs.dropped",
                            task_name="cleanup_gps_logs",
                            table=table_name,
                        )
                    except Exception as exc:
                        log.error(
                            "cleanup_gps_logs.drop_failed",
                            task_name="cleanup_gps_logs",
                            table=table_name,
                            exc=str(exc),
                        )

            await db.commit()

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error(
            "cleanup_gps_logs.failed",
            task_name="cleanup_gps_logs",
            duration_ms=duration_ms,
            status="error",
            exc=str(exc),
        )
        return

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "cleanup_gps_logs.done",
        task_name="cleanup_gps_logs",
        dropped=dropped,
        retention_days=retention_days,
        cutoff=str(cutoff),
        duration_ms=duration_ms,
        status="ok",
    )
