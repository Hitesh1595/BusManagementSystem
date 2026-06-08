import { Marker, Popup } from "react-leaflet";
import { busDivIcon } from "./markers";

interface BusMarkerProps {
  lat: number;
  lng: number;
  label?: string;
}

/** Live bus position marker (pulsing). */
export function BusMarker({ lat, lng, label }: BusMarkerProps) {
  return (
    <Marker position={[lat, lng]} icon={busDivIcon()} zIndexOffset={1000}>
      {label ? <Popup>{label}</Popup> : null}
    </Marker>
  );
}
