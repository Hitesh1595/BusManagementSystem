import { useMemo, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft,
  Clock,
  MapPin,
  Phone,
  RadioTower,
  Route as RouteIcon,
  User,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState, CenteredSpinner } from "@/components/common/States";
import { TripStatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  MapView,
  BusMarker,
  FitBounds,
  Recenter,
  RouteLine,
  StopMarkers,
} from "@/components/maps";
import { tripsApi } from "@/lib/api/trips";
import { qk } from "@/lib/query";
import { formatEta, maskPhone, timeAgo } from "@/lib/format";
import type { LatLng, Stop } from "@/lib/api/types";
import { useTripRoom } from "@/lib/hooks/useTripRoom";

export function LiveTrackPage() {
  const { t } = useTranslation("parent");
  const { tripId } = useParams<{ tripId: string }>();
  const id = tripId ?? "";

  const detailQuery = useQuery({
    queryKey: qk.trip(id),
    queryFn: () => tripsApi.get(id),
    enabled: !!id,
    refetchInterval: 60_000,
  });

  const stopsQuery = useQuery({
    queryKey: ["trip", id, "stops"],
    queryFn: () => tripsApi.stops(id),
    enabled: !!id,
  });

  // Last-known GPS line (fallback before any live position arrives).
  const gpsQuery = useQuery({
    queryKey: qk.tripGpsLog(id),
    queryFn: () => tripsApi.gpsLog(id),
    enabled: !!id,
  });

  const lastAnnouncedStop = useRef<string | null>(null);
  const { connection, position, approaching, paused } = useTripRoom(
    id,
    {
      onApproaching: (e) => {
        if (lastAnnouncedStop.current === e.stop_id) return;
        lastAnnouncedStop.current = e.stop_id;
        const stop = stopsQuery.data?.find((s) => s.id === e.stop_id);
        toast(
          t("track.approachingToast", "Bus approaching {{stop}}", {
            stop: stop?.name ?? t("track.yourStop", "your stop"),
          }),
          { icon: "🚌" },
        );
      },
    },
    !!id,
  );

  const detail = detailQuery.data;
  const stops = stopsQuery.data ?? [];

  // Fallback last GPS point: last coordinate of the LineString ([lng, lat]).
  const lastGps: LatLng | null = useMemo(() => {
    const coords = gpsQuery.data?.geometry?.coordinates;
    if (!coords || coords.length === 0) return null;
    const [lng, lat] = coords[coords.length - 1];
    return { lat, lng };
  }, [gpsQuery.data]);

  const busPoint: LatLng | null = position
    ? { lat: position.lat, lng: position.lng }
    : lastGps;

  const stopPoints: LatLng[] = useMemo(
    () => stops.map((s: Stop) => s.location),
    [stops],
  );

  const etaSeconds = position?.eta_next_stop_s ?? approaching?.eta_s ?? null;
  const driverPhone = detail?.driver?.phone ?? null;
  const showCall = detail?.status === "in_progress" && !!driverPhone;

  if (!id) return <ErrorState message={t("track.noTrip", "Trip not found.")} />;

  return (
    <div className="space-y-4">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Button asChild variant="ghost" size="icon" className="-ml-2 shrink-0">
              <Link to="/parent" aria-label={t("common.back", "Back")}>
                <ArrowLeft className="size-5" />
              </Link>
            </Button>
            {t("track.title", "Live tracking")}
          </span>
        }
        description={detail?.route?.name ?? undefined}
        actions={detail ? <TripStatusBadge status={detail.status} /> : null}
      />

      {detailQuery.isLoading ? (
        <CenteredSpinner label={t("track.loading", "Loading trip…")} />
      ) : detailQuery.isError || !detail ? (
        <ErrorState
          message={t("track.loadError", "Couldn't load this trip.")}
          onRetry={() => void detailQuery.refetch()}
        />
      ) : (
        <>
          {/* Paused banner */}
          {paused ? (
            <div className="flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/15 px-4 py-3 text-warning-foreground">
              <RadioTower className="mt-0.5 size-5 shrink-0" />
              <div className="text-sm">
                <p className="font-semibold">
                  {t("track.paused", "Tracking paused")}
                </p>
                <p className="text-warning-foreground/80">
                  {t(
                    "track.pausedDetail",
                    "No signal for {{secs}}s. Showing the last known position from {{when}}.",
                    {
                      secs: Math.round(paused.stale_for_sec),
                      when: timeAgo(paused.last_updated_at),
                    },
                  )}
                </p>
              </div>
            </div>
          ) : null}

          {/* Live status strip */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Card>
              <CardContent className="flex items-center gap-3 p-4">
                <Clock className="size-5 text-primary" />
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">
                    {t("track.etaNext", "ETA next stop")}
                  </p>
                  <p className="truncate text-base font-semibold">
                    {formatEta(etaSeconds)}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="flex items-center gap-3 p-4">
                <RadioTower
                  className={
                    position
                      ? "size-5 text-success"
                      : "size-5 text-muted-foreground"
                  }
                />
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">
                    {t("track.lastUpdate", "Updated")}
                  </p>
                  <p className="truncate text-base font-semibold">
                    {position?.ts
                      ? timeAgo(new Date(position.ts * 1000))
                      : paused
                        ? timeAgo(paused.last_updated_at)
                        : connection === "connected"
                          ? t("track.waiting", "Waiting…")
                          : t("track.connecting", "Connecting…")}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="col-span-2 sm:col-span-1">
              <CardContent className="flex items-center gap-3 p-4">
                <User className="size-5 text-primary" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">
                    {t("track.driver", "Driver")}
                  </p>
                  <p className="truncate text-base font-semibold">
                    {detail.driver?.full_name ?? t("track.driverTbd", "To be assigned")}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Map */}
          <div className="h-[60vh] w-full overflow-hidden rounded-xl border border-border">
            <MapView center={busPoint ?? stopPoints[0] ?? undefined} zoom={14}>
              {stops.length > 0 ? (
                <>
                  <RouteLine stops={stops} />
                  <StopMarkers stops={stops} />
                  <FitBounds points={stopPoints} />
                </>
              ) : null}
              {busPoint ? (
                <>
                  <BusMarker
                    lat={busPoint.lat}
                    lng={busPoint.lng}
                    label={detail.vehicle?.plate_number ?? detail.route?.name ?? undefined}
                  />
                  {position ? <Recenter point={busPoint} /> : null}
                </>
              ) : null}
            </MapView>
          </div>

          {!busPoint ? (
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              {detail.status === "in_progress"
                ? t("track.awaitingGps", "Waiting for the bus to send its location…")
                : t("track.notStarted", "The trip hasn't started yet. Stops are shown above.")}
            </div>
          ) : null}

          {/* Approaching highlight */}
          {approaching ? (
            <div className="flex items-center gap-3 rounded-xl border border-success/40 bg-success/15 px-4 py-3 text-success">
              <MapPin className="size-5 shrink-0" />
              <p className="text-sm font-medium">
                {(() => {
                  const stop = stops.find((s) => s.id === approaching.stop_id);
                  return t(
                    "track.approaching",
                    "Bus approaching {{stop}} — about {{eta}} away",
                    {
                      stop: stop?.name ?? t("track.yourStop", "your stop"),
                      eta: formatEta(approaching.eta_s),
                    },
                  );
                })()}
              </p>
            </div>
          ) : null}

          {/* Call driver */}
          {showCall ? (
            <Card>
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div className="flex items-center gap-3">
                  <RouteIcon className="size-5 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">
                      {t("track.callDriverTitle", "Need to reach the driver?")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {maskPhone(driverPhone)}
                    </p>
                  </div>
                </div>
                <Button asChild size="lg">
                  <a href={"tel:" + driverPhone}>
                    <Phone className="size-4" />
                    {t("track.callDriver", "Call driver")}
                  </a>
                </Button>
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
