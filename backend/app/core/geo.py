"""
Geospatial utility helpers.

  to_point(lat, lng)           → GeoAlchemy2 WKTElement (SRID=4326)
  from_point(geom)             → {"lat": float, "lng": float} | None
  linestring_from_stops(pts)   → WKTElement LineString | None  (< 2 pts)
  geocode(address)             → {"lat", "lng"} | None  (async, httpx)

Geocoding backend chosen by APP_ENV:
  dev  → Nominatim public (https://nominatim.openstreetmap.org)
  prod → MapTiler (MAPTILER_API_KEY required)
"""

from __future__ import annotations

import structlog
from geoalchemy2 import WKTElement

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Point helpers
# ---------------------------------------------------------------------------


def to_point(lat: float, lng: float) -> WKTElement:
    """
    Convert lat/lng floats to a GeoAlchemy2 WKTElement point.
    Note: WKT POINT uses (longitude latitude) order.
    """
    return WKTElement(f"SRID=4326;POINT({lng} {lat})", srid=4326)


def from_point(geom) -> dict[str, float] | None:
    """
    Convert a GeoAlchemy2 WKBElement (returned from DB) or WKTElement
    to a plain dict {lat, lng}.  Returns None if geom is None.
    """
    if geom is None:
        return None
    try:
        from geoalchemy2.shape import to_shape  # type: ignore[import-untyped]

        shape = to_shape(geom)
        return {"lat": shape.y, "lng": shape.x}
    except Exception:
        log.warning("geo.from_point.failed", geom=repr(geom))
        return None


# ---------------------------------------------------------------------------
# LineString helper (used for route_path)
# ---------------------------------------------------------------------------


def linestring_from_stops(points: list[tuple[float, float]]) -> WKTElement | None:
    """
    Build a WKTElement LineString from an ordered list of (lat, lng) tuples.
    Returns None if fewer than 2 points are provided.
    """
    if len(points) < 2:
        return None
    coords = " ".join(f"{lng} {lat}" for lat, lng in points)
    return WKTElement(f"SRID=4326;LINESTRING({coords})", srid=4326)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------


async def geocode(address: str) -> dict[str, float] | None:
    """
    Resolve an address string to {lat, lng}.

    dev  → Nominatim public API (no API key required; must send User-Agent).
    prod → MapTiler geocoding API (requires MAPTILER_API_KEY).

    Returns None on failure (network error, timeout, no results, missing key).
    """
    from app.config import get_settings

    settings = get_settings()

    try:
        if settings.APP_ENV == "dev":
            return await _nominatim_geocode(address)
        else:
            if not settings.MAPTILER_API_KEY:
                log.warning("geo.geocode.no_maptiler_key")
                return None
            return await _maptiler_geocode(address, settings.MAPTILER_API_KEY)
    except Exception as exc:
        log.warning("geo.geocode.error", address=address, error=str(exc))
        return None


async def _nominatim_geocode(address: str) -> dict[str, float] | None:
    import httpx

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "YatraTrack/0.1 (school-bus-management; dev)"}
    params = {"format": "json", "q": address, "limit": "1"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return None
    first = data[0]
    return {"lat": float(first["lat"]), "lng": float(first["lon"])}


async def _maptiler_geocode(address: str, api_key: str) -> dict[str, float] | None:
    from urllib.parse import quote

    import httpx

    encoded = quote(address)
    url = f"https://api.maptiler.com/geocoding/{encoded}.json"
    params = {"key": api_key}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        return None
    coords = features[0]["geometry"]["coordinates"]  # [lng, lat]
    return {"lat": coords[1], "lng": coords[0]}
