import { Marker, useMapEvents } from "react-leaflet";
import type { LatLng } from "@/lib/api/types";
import { pickupDivIcon } from "./markers";

/** Capture map clicks and report the lat/lng (route editor, pickup picker). */
export function MapClick({ onPick }: { onPick: (point: LatLng) => void }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

/** A single draggable pin used for selecting a pickup location. */
export function DraggablePin({
  point,
  onMove,
}: {
  point: LatLng;
  onMove: (point: LatLng) => void;
}) {
  return (
    <Marker
      position={[point.lat, point.lng]}
      icon={pickupDivIcon()}
      draggable
      eventHandlers={{
        dragend(e) {
          const p = e.target.getLatLng();
          onMove({ lat: p.lat, lng: p.lng });
        },
      }}
    />
  );
}
