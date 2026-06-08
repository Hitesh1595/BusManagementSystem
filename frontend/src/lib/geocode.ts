/**
 * Forward + reverse geocoding via OpenStreetMap Nominatim (dev default; no API
 * key). Results constrained to India. Callers must debounce — Nominatim usage
 * policy allows ~1 req/sec.
 */
const NOMINATIM = "https://nominatim.openstreetmap.org";

export interface GeocodeResult {
  label: string;
  lat: number;
  lng: number;
}

export async function geocodeAddress(query: string): Promise<GeocodeResult[]> {
  const q = query.trim();
  if (q.length < 3) return [];
  const url = `${NOMINATIM}/search?format=jsonv2&limit=5&countrycodes=in&q=${encodeURIComponent(
    q,
  )}`;
  try {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) return [];
    const data = (await res.json()) as Array<{
      display_name: string;
      lat: string;
      lon: string;
    }>;
    return data.map((d) => ({
      label: d.display_name,
      lat: Number.parseFloat(d.lat),
      lng: Number.parseFloat(d.lon),
    }));
  } catch {
    return [];
  }
}

export async function reverseGeocode(
  lat: number,
  lng: number,
): Promise<string | null> {
  const url = `${NOMINATIM}/reverse?format=jsonv2&lat=${lat}&lon=${lng}`;
  try {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) return null;
    const data = (await res.json()) as { display_name?: string };
    return data.display_name ?? null;
  } catch {
    return null;
  }
}
