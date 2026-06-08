import L from "leaflet";

/**
 * Custom divIcon markers. Using divIcon avoids Leaflet's default-marker asset
 * bundling problem entirely (no broken image URLs under Vite).
 */

function dot(bg: string, inner: string, size: number, ring = false): string {
  const ringHtml = ring
    ? `<span style="position:absolute;inset:0;border-radius:9999px;background:${bg};opacity:.25;animation:yt-ping 1.6s cubic-bezier(0,0,.2,1) infinite;"></span>`
    : "";
  return `<div style="position:relative;display:flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;">
    ${ringHtml}
    <span style="position:relative;display:flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:9999px;background:${bg};color:#fff;border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.35);font-size:11px;font-weight:700;line-height:1;">${inner}</span>
  </div>`;
}

const BUS_SVG =
  '<svg width="17" height="17" viewBox="0 0 24 24" fill="#fff"><path d="M4 16V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a1 1 0 0 1-1 1v1a1 1 0 1 1-2 0v-1H7v1a1 1 0 1 1-2 0v-1a1 1 0 0 1-1-1Zm2-9v4h12V7H6Zm1.5 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm9 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"/></svg>';

export function busDivIcon(): L.DivIcon {
  return L.divIcon({
    className: "yt-marker",
    html: dot("#4f46e5", BUS_SVG, 34, true),
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

export function stopDivIcon(order: number): L.DivIcon {
  return L.divIcon({
    className: "yt-marker",
    html: dot("#4f46e5", String(order + 1), 24),
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

export function pickupDivIcon(): L.DivIcon {
  return L.divIcon({
    className: "yt-marker",
    html: dot("#16a34a", "•", 22),
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

export function schoolDivIcon(): L.DivIcon {
  const home =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="#fff"><path d="M12 3 2 11h3v9h5v-6h4v6h5v-9h3z"/></svg>';
  return L.divIcon({
    className: "yt-marker",
    html: dot("#1e1b4b", home, 26),
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}
