/**
 * Formatting helpers. The backend stores UTC TIMESTAMPTZ; the product renders
 * in IST (Asia/Kolkata) per spec.
 */

const IST = "Asia/Kolkata";

export function formatTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone: IST,
  }).format(d);
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: IST,
  }).format(d);
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  return `${formatDate(value)}, ${formatTime(value)}`;
}

/** "HH:MM:SS" (a stop arrival_time) -> "7:05 AM". */
export function formatClock(hms: string | null | undefined): string {
  if (!hms) return "—";
  const [h, m] = hms.split(":");
  const hour = Number(h);
  const ampm = hour >= 12 ? "PM" : "AM";
  const h12 = hour % 12 === 0 ? 12 : hour % 12;
  return `${h12}:${m} ${ampm}`;
}

/** Relative "x ago" / "in x" using seconds granularity, capped at days. */
export function timeAgo(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  const diffSec = Math.round((Date.now() - d.getTime()) / 1000);
  const abs = Math.abs(diffSec);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (abs < 60) return rtf.format(-Math.sign(diffSec) * abs, "second");
  if (abs < 3600) return rtf.format(-Math.sign(diffSec) * Math.round(abs / 60), "minute");
  if (abs < 86400) return rtf.format(-Math.sign(diffSec) * Math.round(abs / 3600), "hour");
  return rtf.format(-Math.sign(diffSec) * Math.round(abs / 86400), "day");
}

/** Seconds -> compact ETA string ("4 min", "45 sec", "1 hr 5 min"). */
export function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} min`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem ? `${hrs} hr ${rem} min` : `${hrs} hr`;
}

export function formatDistance(meters: number | null | undefined): string {
  if (meters == null || !Number.isFinite(meters)) return "—";
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

/**
 * Mask a phone number for display: only the last 4 digits are visible
 * (e.g. "9876543210" -> "98765***10"). The full number is used only inside a
 * tel: href, never rendered. Spec §9.5 / §13 privacy rule.
 */
export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return "—";
  const digits = phone.replace(/\D/g, "");
  if (digits.length <= 4) return phone;
  const last2 = digits.slice(-2);
  const first5 = digits.slice(0, Math.max(0, digits.length - 4));
  return `${first5}***${last2}`;
}
