import { useTranslation } from "react-i18next";
import { WifiOff } from "lucide-react";
import { useLiveTripStore } from "@/stores/liveTrip";

/**
 * Thin status bar shown when the realtime socket is not connected. Hidden when
 * connected. Per spec: clear offline/disconnected indication; REST still serves
 * core data underneath.
 */
export function ConnectionBanner() {
  const { t } = useTranslation("common");
  const connection = useLiveTripStore((s) => s.connection);

  if (connection === "connected") return null;

  const reconnecting = connection === "connecting";
  return (
    <div
      role="status"
      className={
        reconnecting
          ? "flex items-center justify-center gap-2 bg-warning/15 px-4 py-1.5 text-xs font-medium text-warning-foreground"
          : "flex items-center justify-center gap-2 bg-muted px-4 py-1.5 text-xs font-medium text-muted-foreground"
      }
    >
      <WifiOff className="size-3.5" />
      {reconnecting ? t("connection.reconnecting") : t("connection.offline")}
    </div>
  );
}
