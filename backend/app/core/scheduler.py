import asyncio
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

settings = get_settings()
log = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.APP_TIMEZONE)


def start_scheduler() -> None:
    """Start the APScheduler. Jobs are registered per chunk."""
    scheduler.start()
    log.info("scheduler.started", timezone=settings.APP_TIMEZONE)


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    scheduler.shutdown(wait=False)
    log.info("scheduler.stopped")


async def _gps_flush_loop() -> None:
    """
    Placeholder GPS flush loop.
    Logs a tick every GPS_FLUSH_INTERVAL_SEC seconds.
    Real flush logic (Redis → gps_logs) is implemented in Chunk 4.
    """
    while True:
        await asyncio.sleep(settings.GPS_FLUSH_INTERVAL_SEC)
        log.debug("gps_flusher.tick", interval_sec=settings.GPS_FLUSH_INTERVAL_SEC)


async def start_gps_flusher() -> asyncio.Task:
    """
    Spawn the GPS flush asyncio task and return it so lifespan can cancel it on shutdown.
    """
    task = asyncio.create_task(_gps_flush_loop(), name="gps_flusher")
    log.info("gps_flusher.started", interval_sec=settings.GPS_FLUSH_INTERVAL_SEC)
    return task
