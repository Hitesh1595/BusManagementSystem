"""
ETA and bus-approaching computation — pure Python, no DB calls.

eta_and_approaching(trip_id, lat, lng) → (eta_s | None, approaching | None)

Reads stop cache and GPS buffer from Redis.
If Redis is unavailable or cache is empty, returns (None, None).
"""

from __future__ import annotations

import json
import math

import structlog

from app.config import get_settings
from app.redis_client import get_redis

settings = get_settings()
log = structlog.get_logger(__name__)

# Fallback speed when we cannot derive speed from the GPS buffer.
_DEFAULT_SPEED_KMH = 20.0
_DEFAULT_SPEED_MS = _DEFAULT_SPEED_KMH * 1000 / 3600  # ~5.56 m/s

_EARTH_R = 6_371_000.0  # metres


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * _EARTH_R * math.asin(math.sqrt(a))


async def eta_and_approaching(
    trip_id: str,
    lat: float,
    lng: float,
) -> tuple[int | None, dict | None]:
    """
    Returns (eta_next_stop_s, approaching_payload).

    eta_next_stop_s — estimated seconds to the nearest stop (int), or None.
    approaching_payload — dict {trip_id, stop_id, distance_m, eta_s} when bus
                          is within bus_approaching_radius_m of a stop, else None.

    All computation is in-memory.  Redis errors → (None, None).
    """
    try:
        r = get_redis()

        # 1. Load stop cache -------------------------------------------------
        raw_stops = await r.get(f"trip:stops:{trip_id}")
        if not raw_stops:
            return None, None

        stops: list[dict] = json.loads(raw_stops)
        if not stops:
            return None, None

        # 2. Estimate current speed from GPS buffer --------------------------
        speed_ms = _DEFAULT_SPEED_MS
        try:
            # last 2 points — buffer is a Redis list (rpush → newest at right)
            raw_pts = await r.lrange(f"gps:buffer:{trip_id}", -2, -1)
            if len(raw_pts) == 2:
                p0 = json.loads(raw_pts[0])
                p1 = json.loads(raw_pts[1])
                # Use reported speed if available, else derive from positions
                s1 = p1.get("speed")
                if s1 is not None and float(s1) > 0:
                    speed_ms = float(s1)
                else:
                    dist = _haversine_m(
                        float(p0["lat"]), float(p0["lng"]),
                        float(p1["lat"]), float(p1["lng"]),
                    )
                    dt = float(p1.get("ts", 0)) - float(p0.get("ts", 0))
                    if dt > 0:
                        speed_ms = dist / dt
        except Exception:
            speed_ms = _DEFAULT_SPEED_MS

        # Guard absurd values: clamp to [1, 30] m/s (3.6 – 108 km/h).
        speed_ms = max(1.0, min(30.0, speed_ms))

        # 3. Find the nearest stop -------------------------------------------
        nearest_stop = None
        nearest_dist_m = math.inf

        for stop in stops:
            slat = float(stop["lat"])
            slng = float(stop["lng"])
            d = _haversine_m(lat, lng, slat, slng)
            if d < nearest_dist_m:
                nearest_dist_m = d
                nearest_stop = stop

        if nearest_stop is None:
            return None, None

        # 4. ETA -------------------------------------------------------------
        eta_s = max(0, round(nearest_dist_m / speed_ms))

        # 5. Approaching check -----------------------------------------------
        # Radius is cached per-school in Redis at trip start (default 200 m),
        # so the hot path stays DB-free.
        radius_m = 200
        try:
            raw_radius = await r.get(f"trip:radius:{trip_id}")
            if raw_radius is not None:
                radius_m = int(raw_radius)
        except (TypeError, ValueError):
            radius_m = 200
        approaching = None
        if nearest_dist_m <= radius_m:
            approaching = {
                "trip_id": trip_id,
                "stop_id": nearest_stop["stop_id"],
                "distance_m": round(nearest_dist_m),
                "eta_s": eta_s,
            }

        return eta_s, approaching

    except Exception as exc:
        log.warning("eta.error", trip_id=trip_id, exc=str(exc))
        return None, None
