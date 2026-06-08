import { useTranslation } from "react-i18next";
import { MapPin, Radio, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import type { GeoBroadcastState } from "../useGeoBroadcast";

/**
 * Sticky status banner shown while a trip is running: confirms GPS is
 * broadcasting and the screen will stay awake, or surfaces a permission error.
 */
export function KeepScreenOnBanner({ geo }: { geo: GeoBroadcastState }) {
  const { t } = useTranslation("driver");

  if (geo.geoError) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-destructive">
        <ShieldAlert className="mt-0.5 size-5 shrink-0" />
        <div className="text-sm">
          <p className="font-semibold">
            {t("run.gpsError", "Location sharing is off")}
          </p>
          <p className="mt-0.5 text-destructive/80">
            {t(
              "run.gpsErrorHint",
              "Allow location access so parents can track the bus, then keep this screen open.",
            )}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4">
      <span
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-full",
          geo.tracking
            ? "bg-success/15 text-success"
            : "bg-muted text-muted-foreground",
        )}
      >
        <Radio className={cn("size-5", geo.tracking && "animate-pulse")} />
      </span>
      <div className="min-w-0 text-sm">
        <p className="font-semibold">
          {geo.tracking
            ? t("run.sharingLive", "Sharing live location")
            : t("run.sharingStarting", "Starting location sharing…")}
        </p>
        <p className="mt-0.5 flex items-center gap-1 text-muted-foreground">
          <MapPin className="size-3.5" />
          {geo.wakeLock
            ? t("run.screenStaysOn", "Keep this screen on during the trip")
            : t("run.keepOpen", "Keep this app open during the trip")}
        </p>
      </div>
    </div>
  );
}
