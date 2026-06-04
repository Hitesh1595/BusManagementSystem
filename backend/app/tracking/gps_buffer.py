"""
GPS buffer flusher — reads Redis `gps:buffer:{trip_id}` lists and bulk-inserts
points into gps_logs.  Called every GPS_FLUSH_INTERVAL_SEC seconds from the
asyncio flush loop in app/core/scheduler.py.

Design:
  1. SCAN all `gps:buffer:*` keys (cursor-based, non-blocking).
  2. For each key:
     a. LRANGE 0 -1  → read all buffered JSON points.
     b. LTRIM len -1  → atomically trim the items we just read
        (if new items arrive between LRANGE and LTRIM they stay in the list).
     c. Parse trip_id from the key suffix.
     d. Bulk INSERT into gps_logs (one executemany / core insert).
  3. Log task_name, drained count, duration_ms, status.

Resilience:
  - If Redis is unreachable, log a warning and return (no-op).
  - If DB write fails for a key, log an error and continue with remaining keys.
  - Individual bad JSON points are skipped with a warning.

tracking_paused check is also registered here as a companion to the flusher
(piggybacks on the same APScheduler cadence).
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import insert

from app.config import get_settings
from app.core.geo import to_point
from app.database import SessionLocal
from app.redis_client import get_redis
from app.tracking.models import GpsLog

log = structlog.get_logger(__name__)
settings = get_settings()


async def flush_gps_buffer() -> None:
    """
    Drain all `gps:buffer:*` Redis lists into gps_logs.
    Safe to call concurrently (LRANGE + LTRIM pattern ensures no data loss).
    """
    t0 = time.monotonic()
    total_drained = 0

    r = get_redis()
    try:
        # Collect all buffer keys via SCAN (avoids blocking the server with KEYS)
        keys: list[str] = []
        cursor = 0
        while True:
            cursor, batch = await r.scan(cursor, match="gps:buffer:*", count=200)
            keys.extend(batch)
            if cursor == 0:
                break
    except Exception as exc:
        log.warning(
            "flush_gps_buffer.redis_unavailable",
            task_name="flush_gps_buffer",
            exc=str(exc),
            status="skipped",
        )
        return

    if not keys:
        log.debug(
            "flush_gps_buffer.nothing_to_flush",
            task_name="flush_gps_buffer",
            status="ok",
        )
        return

    for key in keys:
        # key format: gps:buffer:{trip_id}
        parts = key.split(":", 2)
        if len(parts) != 3:
            continue
        trip_id_str = parts[2]

        try:
            trip_id = uuid.UUID(trip_id_str)
        except ValueError:
            log.warning("flush_gps_buffer.invalid_trip_id", key=key)
            continue

        try:
            # Read all items currently in the list
            raw_items: list[str] = await r.lrange(key, 0, -1)
            if not raw_items:
                continue

            n = len(raw_items)
            # Trim exactly the items we read; newer items pushed after our LRANGE
            # will have indexes ≥ n and survive the trim.
            await r.ltrim(key, n, -1)
        except Exception as exc:
            log.error(
                "flush_gps_buffer.redis_read_failed",
                task_name="flush_gps_buffer",
                trip_id=trip_id_str,
                exc=str(exc),
            )
            continue

        # Parse points
        rows: list[dict] = []
        for raw in raw_items:
            try:
                point = json.loads(raw)
                lat = float(point["lat"])
                lng = float(point["lng"])
                ts_raw = point.get("ts")
                if ts_raw is not None:
                    recorded_at = datetime.fromtimestamp(float(ts_raw), tz=UTC)
                else:
                    recorded_at = datetime.now(UTC)

                rows.append(
                    {
                        "trip_id": trip_id,
                        "location": to_point(lat, lng),
                        "speed": point.get("speed"),
                        "heading": point.get("heading"),
                        "accuracy": point.get("accuracy"),
                        "recorded_at": recorded_at,
                    }
                )
            except Exception as exc:
                log.warning(
                    "flush_gps_buffer.bad_point",
                    trip_id=trip_id_str,
                    raw=raw[:120],
                    exc=str(exc),
                )

        if not rows:
            continue

        # Bulk insert
        try:
            async with SessionLocal() as db:
                await db.execute(insert(GpsLog), rows)
                await db.commit()
            total_drained += len(rows)
            log.debug(
                "flush_gps_buffer.flushed_trip",
                trip_id=trip_id_str,
                points=len(rows),
            )
        except Exception as exc:
            log.error(
                "flush_gps_buffer.db_insert_failed",
                task_name="flush_gps_buffer",
                trip_id=trip_id_str,
                exc=str(exc),
            )

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "flush_gps_buffer.done",
        task_name="flush_gps_buffer",
        drained=total_drained,
        duration_ms=duration_ms,
        status="ok",
    )


# ---------------------------------------------------------------------------
# tracking_paused checker
# ---------------------------------------------------------------------------


async def check_tracking_paused() -> None:
    """
    For each in-progress trip, check whether GPS has gone stale
    (gps:last:{trip_id} timestamp older than GPS_STALE_THRESHOLD_SEC).

    On first detection of staleness, emit `tracking_paused` to the trip room
    and set `gps:paused:{trip_id}` flag so we don't spam.  When fresh GPS
    resumes (detected by the socket handler's set of gps:last), the flag is
    cleared by check_tracking_resumed() or by the next location_update.
    """
    from sqlalchemy import select

    from app.core.socketio import sio
    from app.tracking.models import Trip

    r = get_redis()
    now_ts = time.time()

    try:
        # Get all in-progress trips from the DB
        async with SessionLocal() as db:
            stmt = select(Trip).where(Trip.status == "in_progress")
            trips = (await db.execute(stmt)).scalars().all()
    except Exception as exc:
        log.warning("check_tracking_paused.db_error", exc=str(exc))
        return

    for trip in trips:
        trip_id = str(trip.id)
        try:
            last_ts_raw = await r.get(f"gps:last:{trip_id}")
            paused_flag = await r.get(f"gps:paused:{trip_id}")

            if last_ts_raw is None:
                # No GPS received yet — not yet stale (trip just started maybe)
                continue

            try:
                last_ts = float(last_ts_raw)
            except ValueError:
                # Try ISO parse fallback (older format stored by socket handlers)
                try:
                    from datetime import datetime as dt

                    parsed = dt.fromisoformat(last_ts_raw)
                    last_ts = parsed.timestamp()
                except Exception:
                    continue

            age_sec = now_ts - last_ts

            if age_sec > settings.GPS_STALE_THRESHOLD_SEC:
                if paused_flag is not None:
                    # Already emitted paused for this stale episode
                    continue

                # First detection — emit event and set flag
                payload = {
                    "trip_id": trip_id,
                    "last_updated_at": datetime.fromtimestamp(last_ts, tz=UTC).isoformat(),
                    "stale_for_sec": round(age_sec),
                }
                try:
                    await sio.emit("tracking_paused", payload, room=f"trip:{trip_id}")
                except Exception as emit_exc:
                    log.warning(
                        "check_tracking_paused.emit_failed",
                        trip_id=trip_id,
                        exc=str(emit_exc),
                    )

                # Set paused flag (TTL = 2× stale threshold so it auto-expires)
                await r.set(
                    f"gps:paused:{trip_id}",
                    "1",
                    ex=settings.GPS_STALE_THRESHOLD_SEC * 2,
                )
                log.info(
                    "check_tracking_paused.detected",
                    trip_id=trip_id,
                    stale_for_sec=round(age_sec),
                )
            else:
                # GPS is fresh — clear any lingering paused flag
                if paused_flag is not None:
                    await r.delete(f"gps:paused:{trip_id}")

        except Exception as exc:
            log.warning(
                "check_tracking_paused.trip_check_failed",
                trip_id=trip_id,
                exc=str(exc),
            )
