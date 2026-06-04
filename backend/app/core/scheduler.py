"""
APScheduler setup + GPS flush asyncio task.

- `scheduler` — singleton AsyncIOScheduler (tz=Asia/Kolkata).
- `start_scheduler()` — starts scheduler + registers all APScheduler jobs.
- `shutdown_scheduler()` — graceful shutdown.
- `start_gps_flusher()` — spawns the asyncio flush loop task; returns the task
  so lifespan can cancel it on shutdown.  On CancelledError the loop does one
  final flush before exiting (flush-on-shutdown guarantee).
"""

from __future__ import annotations

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

settings = get_settings()
log = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.APP_TIMEZONE)


def start_scheduler() -> None:
    """Start the APScheduler and register all recurring jobs."""
    _register_jobs()
    scheduler.start()
    log.info("scheduler.started", timezone=settings.APP_TIMEZONE)


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    scheduler.shutdown(wait=False)
    log.info("scheduler.stopped")


# ---------------------------------------------------------------------------
# GPS flush asyncio loop (not APScheduler — pure asyncio task)
# ---------------------------------------------------------------------------


async def _gps_flush_loop() -> None:
    """
    Asyncio task: sleep → flush → repeat.
    On CancelledError: do one final flush then exit cleanly.
    """
    from app.tracking.gps_buffer import flush_gps_buffer

    try:
        while True:
            await asyncio.sleep(settings.GPS_FLUSH_INTERVAL_SEC)
            await flush_gps_buffer()
    except asyncio.CancelledError:
        log.info("gps_flusher.shutdown_flush_starting")
        try:
            await flush_gps_buffer()
        except Exception as exc:
            log.error("gps_flusher.shutdown_flush_failed", exc=str(exc))
        log.info("gps_flusher.stopped")


async def start_gps_flusher() -> asyncio.Task:
    """
    Spawn the GPS flush asyncio task and return it so lifespan can cancel it on shutdown.
    """
    task = asyncio.create_task(_gps_flush_loop(), name="gps_flusher")
    log.info("gps_flusher.started", interval_sec=settings.GPS_FLUSH_INTERVAL_SEC)
    return task


# ---------------------------------------------------------------------------
# APScheduler job registration
# ---------------------------------------------------------------------------


def _register_jobs() -> None:
    """Register all scheduled jobs with the APScheduler instance."""
    from app.tracking.gps_buffer import check_tracking_paused
    from app.tracking.jobs import (
        check_driver_no_show,
        cleanup_gps_logs,
        ensure_gps_partitions,
        generate_daily_trips,
    )
    from app.vehicles.jobs import check_vehicle_compliance

    # generate_daily_trips — daily at TRIP_AUTOGEN_HOUR (default 06:00 IST)
    scheduler.add_job(
        generate_daily_trips,
        "cron",
        hour=settings.TRIP_AUTOGEN_HOUR,
        minute=0,
        id="generate_daily_trips",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # check_driver_no_show — every 5 minutes (filter school hours inside the job)
    scheduler.add_job(
        check_driver_no_show,
        "interval",
        minutes=5,
        id="check_driver_no_show",
        replace_existing=True,
        misfire_grace_time=60,
    )

    # check_vehicle_compliance — daily at 07:00 IST
    scheduler.add_job(
        check_vehicle_compliance,
        "cron",
        hour=7,
        minute=0,
        id="check_vehicle_compliance",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # ensure_gps_partitions — daily at 00:30 IST
    scheduler.add_job(
        ensure_gps_partitions,
        "cron",
        hour=0,
        minute=30,
        id="ensure_gps_partitions",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # cleanup_gps_logs — daily at 01:00 IST
    scheduler.add_job(
        cleanup_gps_logs,
        "cron",
        hour=1,
        minute=0,
        id="cleanup_gps_logs",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # check_tracking_paused — every 30 seconds
    scheduler.add_job(
        check_tracking_paused,
        "interval",
        seconds=30,
        id="check_tracking_paused",
        replace_existing=True,
        misfire_grace_time=15,
    )

    log.info(
        "scheduler.jobs_registered",
        jobs=[job.id for job in scheduler.get_jobs()],
    )
