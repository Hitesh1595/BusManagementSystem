import type { ReactNode } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import type { LatLng } from "@/lib/api/types";
import { INDIA_CENTER } from "@/lib/geo";
import { cn } from "@/lib/utils";

interface MapViewProps {
  center?: LatLng | null;
  zoom?: number;
  className?: string;
  children?: ReactNode;
  scrollWheelZoom?: boolean;
}

/**
 * Base map. OSM tiles in dev (no API key); swap the TileLayer url for Stadia in
 * prod. Parent must give the container an explicit height.
 */
export function MapView({
  center,
  zoom = 13,
  className,
  children,
  scrollWheelZoom = true,
}: MapViewProps) {
  const c = center ?? INDIA_CENTER;
  return (
    <MapContainer
      center={[c.lat, c.lng]}
      zoom={center ? zoom : 5}
      scrollWheelZoom={scrollWheelZoom}
      className={cn("h-full w-full rounded-xl", className)}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
      />
      {children}
    </MapContainer>
  );
}
