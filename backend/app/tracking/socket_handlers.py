"""
Socket.IO event handlers for live trip tracking.

Events handled:
  join_trip     {trip_id}                       — authorize + enter rooms
  leave_trip    {trip_id}                       — leave trip room
  location_update {trip_id,lat,lng,speed,       — GPS hot path (driver only,
                   heading,accuracy,ts}           ≤1/3s, no DB on happy path)

Import this module at startup (app/main.py) so the @sio.on(...)
registrations execute.
"""

from __future__ import annotations

import json
import uuid

import structlog
from sqlalchemy import select

from app.core.socketio import sio
from app.database import SessionLocal
from app.redis_client import get_redis
from app.students.models import Student, StudentRouteAssignment
from app.tracking.eta import eta_and_approaching
from app.tracking.models import GpsLog, Trip

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# join_trip
# ---------------------------------------------------------------------------


@sio.on("join_trip")
async def join_trip(sid: str, data: dict) -> dict:
    """
    Authorize and add the socket to the trip's room.

    Authorization rules (§9.2):
      - Trip's driver (session user_id == trip.driver_id)
      - School admin / super_admin with matching school_id
      - Parent with an active child assignment to the trip's route

    On success emits no separate event — just returns {"ok": True}.
    On failure returns {"ok": False, "error": "<reason>"} and does NOT join.
    """
    session = await sio.get_session(sid)
    trip_id_raw = (data or {}).get("trip_id")
    if not trip_id_raw:
        return {"ok": False, "error": "trip_id required"}

    try:
        trip_id = uuid.UUID(str(trip_id_raw))
    except ValueError:
        return {"ok": False, "error": "invalid trip_id"}

    user_id_str = session.get("user_id")
    school_id_str = session.get("school_id")
    role = session.get("role", "")

    async with SessionLocal() as db:
        trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
        if trip is None:
            return {"ok": False, "error": "trip not found"}

        allowed = False

        # 1. Driver of this trip
        if user_id_str and str(trip.driver_id) == user_id_str:
            allowed = True

        # 2. Admin of the same school (or super_admin)
        elif role in ("school_admin", "super_admin"):
            if role == "super_admin" or (
                school_id_str and str(trip.school_id) == school_id_str
            ):
                allowed = True

        # 3. Parent with an active child assigned to this trip's route
        elif role == "parent" and user_id_str:
            parent_id = uuid.UUID(user_id_str)
            stmt = (
                select(StudentRouteAssignment)
                .join(Student, Student.id == StudentRouteAssignment.student_id)
                .where(
                    Student.parent_id == parent_id,
                    StudentRouteAssignment.route_id == trip.route_id,
                    StudentRouteAssignment.is_active.is_(True),
                )
                .limit(1)
            )
            row = (await db.execute(stmt)).scalar_one_or_none()
            if row is not None:
                allowed = True

        if not allowed:
            log.info(
                "socket.join_trip.denied",
                sid=sid,
                trip_id=str(trip_id),
                role=role,
                user_id=user_id_str,
            )
            return {"ok": False, "error": "not authorized for this trip"}

        await sio.enter_room(sid, f"trip:{trip_id}")
        if role in ("school_admin", "super_admin"):
            await sio.enter_room(sid, f"school:{trip.school_id}")

    log.info(
        "socket.join_trip.ok",
        sid=sid,
        trip_id=str(trip_id),
        role=role,
        user_id=user_id_str,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# leave_trip
# ---------------------------------------------------------------------------


@sio.on("leave_trip")
async def leave_trip(sid: str, data: dict) -> dict:
    """Remove the socket from a trip room."""
    trip_id_raw = (data or {}).get("trip_id")
    if not trip_id_raw:
        return {"ok": False, "error": "trip_id required"}

    try:
        trip_id = uuid.UUID(str(trip_id_raw))
    except ValueError:
        return {"ok": False, "error": "invalid trip_id"}

    await sio.leave_room(sid, f"trip:{trip_id}")
    log.info("socket.leave_trip", sid=sid, trip_id=str(trip_id))
    return {"ok": True}


# ---------------------------------------------------------------------------
# location_update  (GPS hot path — no blocking DB on happy path)
# ---------------------------------------------------------------------------


@sio.on("location_update")
async def location_update(sid: str, data: dict) -> None:
    """
    Ingest a GPS point from the driver.

    §3.3 hot path:
      3a. Authorize (driver?) + rate-limit (≤1/3s/connection).
      3b. Push to Redis GPS buffer.
      3c. Broadcast to trip room.
      3d. Compute ETA + bus_approaching.
    """
    session = await sio.get_session(sid)
    trip_id_raw = (data or {}).get("trip_id")
    if not trip_id_raw:
        return

    trip_id = str(trip_id_raw)
    user_id = session.get("user_id")

    # ------------------------------------------------------------------
    # 3a-i: Authorize — driver check via Redis (no DB hit on happy path)
    # ------------------------------------------------------------------
    r = get_redis()
    redis_available = True

    try:
        expected_driver = await r.get(f"trip:driver:{trip_id}")
    except Exception:
        expected_driver = None
        redis_available = False

    if expected_driver is not None:
        # Cache hit: fast path
        if expected_driver != user_id:
            log.debug(
                "socket.location_update.not_driver",
                sid=sid,
                trip_id=trip_id,
                user_id=user_id,
            )
            return
    else:
        # Cache miss or Redis down: fall back to one DB check
        if user_id is None:
            return
        try:
            trip_uuid = uuid.UUID(trip_id)
        except ValueError:
            return

        async with SessionLocal() as db:
            trip = (
                await db.execute(select(Trip).where(Trip.id == trip_uuid))
            ).scalar_one_or_none()

        if trip is None or str(trip.driver_id) != user_id:
            log.debug(
                "socket.location_update.not_driver.db_fallback",
                sid=sid,
                trip_id=trip_id,
                user_id=user_id,
            )
            return

    # ------------------------------------------------------------------
    # 3a-ii: Rate-limit — ≤1 update per 3 seconds per connection
    # ------------------------------------------------------------------
    if redis_available:
        try:
            allowed = await r.set(f"ratelimit:loc:{sid}", "1", nx=True, ex=3)
            if not allowed:
                log.debug("socket.location_update.rate_limited", sid=sid, trip_id=trip_id)
                return
        except Exception:
            pass  # Redis down → skip rate-limit (degraded mode)

    # ------------------------------------------------------------------
    # 3b: Build point dict
    # ------------------------------------------------------------------
    point = {
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "speed": data.get("speed"),
        "heading": data.get("heading"),
        "accuracy": data.get("accuracy"),
        "ts": data.get("ts"),
    }

    # Validate required fields
    if point["lat"] is None or point["lng"] is None:
        return

    # ------------------------------------------------------------------
    # 3b: Push to Redis GPS buffer (rpush keeps ordering)
    # ------------------------------------------------------------------
    buffer_key = f"gps:buffer:{trip_id}"
    point_json = json.dumps(point)

    if redis_available:
        try:
            await r.rpush(buffer_key, point_json)
            await r.set(f"gps:last:{trip_id}", str(data.get("ts", "")))
        except Exception as exc:
            redis_available = False
            log.warning("socket.location_update.redis_rpush_failed", trip_id=trip_id, exc=str(exc))
            # Fall back to direct DB write so no data is lost
            await _fallback_db_write(trip_id, point)
    else:
        await _fallback_db_write(trip_id, point)

    # ------------------------------------------------------------------
    # 3d: ETA + approaching
    # ------------------------------------------------------------------
    eta_s, approaching = await eta_and_approaching(
        trip_id, float(point["lat"]), float(point["lng"])
    )

    # ------------------------------------------------------------------
    # 3c: Broadcast to trip room
    # ------------------------------------------------------------------
    broadcast_payload = {
        **point,
        "trip_id": trip_id,
        "eta_next_stop_s": eta_s,
    }
    await sio.emit("location_update", broadcast_payload, room=f"trip:{trip_id}")

    if approaching:
        await sio.emit("bus_approaching", approaching, room=f"trip:{trip_id}")

    log.debug(
        "socket.location_update.ok",
        sid=sid,
        trip_id=trip_id,
        lat=point["lat"],
        lng=point["lng"],
        eta_s=eta_s,
    )


# ---------------------------------------------------------------------------
# Internal helper — fallback DB write when Redis is unavailable
# ---------------------------------------------------------------------------


async def _fallback_db_write(trip_id: str, point: dict) -> None:
    """
    Write a GPS point directly to gps_logs when the Redis buffer is unavailable.
    Ensures no data loss even during Redis outages (spec §17.5).
    """
    from datetime import UTC, datetime

    from geoalchemy2.elements import WKTElement

    try:
        trip_uuid = uuid.UUID(trip_id)
        lat = float(point["lat"])
        lng = float(point["lng"])
        location = WKTElement(f"SRID=4326;POINT({lng} {lat})", srid=4326)

        # ts is a Unix timestamp (float/int seconds); fall back to now()
        ts_raw = point.get("ts")
        if ts_raw is not None:
            recorded_at = datetime.fromtimestamp(float(ts_raw), tz=UTC)
        else:
            recorded_at = datetime.now(UTC)

        gps_log = GpsLog(
            trip_id=trip_uuid,
            location=location,
            speed=point.get("speed"),
            heading=point.get("heading"),
            accuracy=point.get("accuracy"),
            recorded_at=recorded_at,
        )
        async with SessionLocal() as db:
            db.add(gps_log)
            await db.commit()

        log.info("socket.location_update.db_fallback_ok", trip_id=trip_id)
    except Exception as exc:
        log.error("socket.location_update.db_fallback_failed", trip_id=trip_id, exc=str(exc))
