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

    Parses WKB natively (no Shapely dependency).
    Supports EWKB (with SRID flag) and plain WKB, both little-endian and big-endian.
    Falls back to WKT parsing for WKTElement.
    """
    if geom is None:
        return None
    try:
        from geoalchemy2.elements import WKBElement, WKTElement  # type: ignore[import-untyped]

        if isinstance(geom, WKTElement):
            # WKT format: "SRID=4326;POINT(lng lat)" or "POINT(lng lat)"
            wkt: str = geom.desc
            # Strip SRID prefix if present
            if ";" in wkt:
                wkt = wkt.split(";", 1)[1]
            wkt = wkt.strip()
            # Extract coords from POINT(x y)
            inner = wkt[wkt.index("(") + 1 : wkt.index(")")]
            parts = inner.split()
            if len(parts) >= 2:
                return {"lat": float(parts[1]), "lng": float(parts[0])}
            return None

        if isinstance(geom, WKBElement):
            # Decode hex string or bytes
            raw = geom.data
            if isinstance(raw, str):
                data = bytes.fromhex(raw)
            elif isinstance(raw, memoryview):
                data = bytes(raw)
            else:
                data = bytes(raw)

            return _parse_wkb_point(data)

        # Unknown type — try repr-based fallback
        log.warning("geo.from_point.unknown_type", geom_type=type(geom).__name__)
        return None
    except Exception:
        log.warning("geo.from_point.failed", geom=repr(geom))
        return None


def _parse_wkb_point(data: bytes) -> dict[str, float] | None:
    """
    Parse a WKB/EWKB Point to {lat, lng}.

    WKB layout (21 bytes plain, 25 bytes EWKB with SRID):
      [0]      byte_order: 0x00=big-endian, 0x01=little-endian
      [1..4]   geometry_type (uint32) — may have 0x20000000 SRID flag set
      [5..8]   SRID if flag set (uint32) — only in EWKB
      [5/9..12/16]  X (double)
      [13/17..20/24] Y (double)
    """
    import struct

    if len(data) < 21:
        return None

    byte_order = data[0]
    endian = "<" if byte_order == 1 else ">"

    geom_type = struct.unpack_from(f"{endian}I", data, 1)[0]
    has_srid = bool(geom_type & 0x20000000)
    coord_offset = 9 if has_srid else 5

    if len(data) < coord_offset + 16:
        return None

    x = struct.unpack_from(f"{endian}d", data, coord_offset)[0]      # longitude
    y = struct.unpack_from(f"{endian}d", data, coord_offset + 8)[0]  # latitude
    return {"lat": y, "lng": x}


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
    # WKT requires comma-separated point pairs: LINESTRING(lng1 lat1, lng2 lat2, ...)
    coords = ", ".join(f"{lng} {lat}" for lat, lng in points)
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
