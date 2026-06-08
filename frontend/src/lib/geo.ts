import type { LatLng } from "./api/types";

const EARTH_RADIUS_M = 6_371_000;

/** Great-circle distance in metres between two points. */
export function haversine(a: LatLng, b: LatLng): number {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

/** Centroid of a set of points; returns null for an empty list. */
export function centroid(points: LatLng[]): LatLng | null {
  if (points.length === 0) return null;
  const sum = points.reduce(
    (acc, p) => ({ lat: acc.lat + p.lat, lng: acc.lng + p.lng }),
    { lat: 0, lng: 0 },
  );
  return { lat: sum.lat / points.length, lng: sum.lng / points.length };
}

/** Bounding box [[south, west], [north, east]] for fitBounds; null if empty. */
export function boundsOf(
  points: LatLng[],
): [[number, number], [number, number]] | null {
  if (points.length === 0) return null;
  let s = 90,
    w = 180,
    n = -90,
    e = -180;
  for (const p of points) {
    s = Math.min(s, p.lat);
    n = Math.max(n, p.lat);
    w = Math.min(w, p.lng);
    e = Math.max(e, p.lng);
  }
  return [
    [s, w],
    [n, e],
  ];
}

/** Default map center when a school has no points yet — central India. */
export const INDIA_CENTER: LatLng = { lat: 22.5937, lng: 78.9629 };
