import { useEffect } from "react";
import { Marker, Polyline, Popup, useMap } from "react-leaflet";
import type { LatLng, Stop } from "@/lib/api/types";
import { boundsOf } from "@/lib/geo";
import { formatClock } from "@/lib/format";
import { schoolDivIcon, stopDivIcon } from "./markers";

/** Imperatively fit the map to a set of points whenever they change. */
export function FitBounds({ points, padding = 48 }: { points: LatLng[]; padding?: number }) {
  const map = useMap();
  useEffect(() => {
    const b = boundsOf(points);
    if (b) {
      map.fitBounds(b, { padding: [padding, padding], maxZoom: 16 });
    }
  }, [map, padding, JSON.stringify(points)]);
  return null;
}

/** Smoothly pan the map to follow a moving point (e.g. the bus). */
export function Recenter({ point, zoom }: { point: LatLng | null | undefined; zoom?: number }) {
  const map = useMap();
  useEffect(() => {
    if (point) map.panTo([point.lat, point.lng], { animate: true });
  }, [map, point?.lat, point?.lng, zoom]);
  return null;
}

export function RouteLine({ stops }: { stops: Stop[] }) {
  if (stops.length < 2) return null;
  const positions = stops.map((s) => [s.location.lat, s.location.lng] as [number, number]);
  return (
    <Polyline positions={positions} pathOptions={{ color: "#4f46e5", weight: 4, opacity: 0.7 }} />
  );
}

export function StopMarkers({ stops }: { stops: Stop[] }) {
  return (
    <>
      {stops.map((stop) => (
        <Marker
          key={stop.id}
          position={[stop.location.lat, stop.location.lng]}
          icon={stopDivIcon(stop.stop_order)}
        >
          <Popup>
            <span className="font-medium">{stop.name}</span>
            {stop.arrival_time ? (
              <span className="block text-xs text-muted-foreground">
                {formatClock(stop.arrival_time)}
              </span>
            ) : null}
          </Popup>
        </Marker>
      ))}
    </>
  );
}

export function SchoolMarker({ location }: { location: LatLng }) {
  return <Marker position={[location.lat, location.lng]} icon={schoolDivIcon()} />;
}
