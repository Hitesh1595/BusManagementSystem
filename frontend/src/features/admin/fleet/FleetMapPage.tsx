import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Bus, Gauge, MapPin, Navigation, User } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CenteredSpinner, ErrorState } from "@/components/common/States";
import { TripStatusBadge } from "@/components/common/StatusBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import { qk } from "@/lib/query";
import { tripsApi } from "@/lib/api/trips";
import { getSocket, connectSocket, joinTrip, leaveTrip, type LocationUpdateEvent } from "@/lib/socket";
import type { LatLng, Trip } from "@/lib/api/types";
import { MapView, Recenter, FitBounds, busDivIcon } from "@/components/maps";
import { Marker, Popup } from "react-leaflet";
import { formatEta } from "@/lib/format";

interface LivePos extends LatLng {
  speed: number | null;
  heading: number | null;
  ts: number | null;
  eta_next_stop_s: number | null;
}

function speedLabel(speed: number | null | undefined): string {
  if (speed == null || !Number.isFinite(speed)) return "—";
  // backend reports m/s for GPS speed; render km/h
  return `${Math.round(speed * 3.6)} km/h`;
}

export function FleetMapPage() {
  const { t } = useTranslation("admin");

  const activeQuery = useQuery({
    queryKey: qk.activeTrips,
    queryFn: () => tripsApi.listActive(),
    refetchInterval: 15_000,
  });

  const activeTrips = useMemo(
    () => (activeQuery.data ?? []).filter((tr) => tr.status === "in_progress"),
    [activeQuery.data],
  );
  const tripIds = useMemo(() => activeTrips.map((tr) => tr.id), [activeTrips]);
  const tripIdsKey = tripIds.join(",");

  const [positions, setPositions] = useState<Record<string, LivePos>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Join each active trip room and listen for live location updates.
  useEffect(() => {
    if (tripIds.length === 0) return;
    const socket = connectSocket();

    const onLocation = (e: LocationUpdateEvent) => {
      setPositions((prev) => ({
        ...prev,
        [e.trip_id]: {
          lat: e.lat,
          lng: e.lng,
          speed: e.speed,
          heading: e.heading,
          ts: e.ts,
          eta_next_stop_s: e.eta_next_stop_s,
        },
      }));
    };

    socket.on("location_update", onLocation);
    for (const id of tripIds) void joinTrip(id);

    return () => {
      getSocket().off("location_update", onLocation);
      for (const id of tripIds) void leaveTrip(id);
    };
    // tripIdsKey captures membership changes without re-subscribing on identity churn
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripIdsKey]);

  // Fallback: seed last-known positions from each trip's GPS log when no live tick yet.
  useEffect(() => {
    let cancelled = false;
    const missing = tripIds.filter((id) => !positions[id]);
    if (missing.length === 0) return;
    (async () => {
      for (const id of missing) {
        try {
          const geo = await tripsApi.gpsLog(id);
          const coords = geo.geometry?.coordinates ?? [];
          const last = coords[coords.length - 1];
          if (last && !cancelled) {
            const [lng, lat] = last;
            setPositions((prev) =>
              prev[id]
                ? prev
                : {
                    ...prev,
                    [id]: { lat, lng, speed: null, heading: null, ts: null, eta_next_stop_s: null },
                  },
            );
          }
        } catch {
          /* ignore — trip may have no GPS yet */
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripIdsKey]);

  // Keep selection valid as the active set changes.
  useEffect(() => {
    if (selectedId && !tripIds.includes(selectedId)) setSelectedId(null);
    if (!selectedId && tripIds.length > 0) setSelectedId(tripIds[0]);
  }, [tripIdsKey, selectedId, tripIds]);

  const markerPoints = useMemo(
    () => Object.values(positions).map((p) => ({ lat: p.lat, lng: p.lng })),
    [positions],
  );
  const selectedPos = selectedId ? positions[selectedId] : undefined;

  if (activeQuery.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("fleet.title", "Live fleet")} />
        <CenteredSpinner label={t("fleet.loading", "Loading active trips…")} />
      </div>
    );
  }

  if (activeQuery.isError) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("fleet.title", "Live fleet")} />
        <ErrorState onRetry={() => activeQuery.refetch()} />
      </div>
    );
  }

  if (activeTrips.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("fleet.title", "Live fleet")} description={t("fleet.subtitle", "Track every bus that's on the road right now.")} />
        <EmptyState
          icon={Bus}
          title={t("fleet.empty.title", "No buses on the road")}
          description={t("fleet.empty.desc", "Live positions appear here once drivers start their trips.")}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("fleet.title", "Live fleet")}
        description={t("fleet.subtitle", "Track every bus that's on the road right now.")}
        actions={
          <Badge variant="success" className="gap-1.5">
            <span className="inline-block size-1.5 animate-pulse rounded-full bg-current" />
            {t("fleet.activeCount", "{{count}} active", { count: activeTrips.length })}
          </Badge>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="h-[65vh] w-full overflow-hidden rounded-xl border border-border">
          <MapView center={selectedPos ?? markerPoints[0] ?? null} zoom={14}>
            {markerPoints.length > 1 && !selectedPos ? <FitBounds points={markerPoints} /> : null}
            {selectedPos ? <Recenter point={selectedPos} /> : null}
            {activeTrips.map((tr) => {
              const p = positions[tr.id];
              if (!p) return null;
              return (
                <FleetBusMarker
                  key={tr.id}
                  pos={p}
                  selected={tr.id === selectedId}
                  onSelect={() => setSelectedId(tr.id)}
                  speedText={speedLabel(p.speed)}
                />
              );
            })}
          </MapView>
        </div>

        <div className="space-y-3 lg:max-h-[65vh] lg:overflow-y-auto lg:pr-1">
          {activeTrips.map((tr) => (
            <TripListCard
              key={tr.id}
              trip={tr}
              pos={positions[tr.id]}
              selected={tr.id === selectedId}
              onSelect={() => setSelectedId(tr.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function FleetBusMarker({
  pos,
  selected,
  onSelect,
  speedText,
}: {
  pos: LivePos;
  selected: boolean;
  onSelect: () => void;
  speedText: string;
}) {
  const { t } = useTranslation("admin");
  return (
    <Marker
      position={[pos.lat, pos.lng]}
      icon={busDivIcon()}
      zIndexOffset={selected ? 1500 : 1000}
      eventHandlers={{ click: onSelect }}
    >
      <Popup>
        <span className="block font-semibold">{t("fleet.bus", "Bus")}</span>
        <span className="block text-xs text-muted-foreground">
          {t("fleet.speed", "Speed")}: {speedText}
        </span>
        {pos.eta_next_stop_s != null ? (
          <span className="block text-xs text-muted-foreground">
            {t("fleet.etaNext", "Next stop")}: {formatEta(pos.eta_next_stop_s)}
          </span>
        ) : null}
      </Popup>
    </Marker>
  );
}

function TripListCard({
  trip,
  pos,
  selected,
  onSelect,
}: {
  trip: Trip;
  pos: LivePos | undefined;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation("admin");
  // Pull richer detail (route/driver names) for the selected trip only.
  const detailQuery = useQuery({
    queryKey: qk.trip(trip.id),
    queryFn: () => tripsApi.get(trip.id),
    enabled: selected,
    staleTime: 30_000,
  });

  const detail = detailQuery.data;

  return (
    <Card
      onClick={onSelect}
      className={cn(
        "cursor-pointer transition-colors",
        selected ? "border-primary ring-1 ring-primary" : "hover:border-muted-foreground/40",
      )}
    >
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2 font-semibold">
            <Bus className="size-4 shrink-0 text-primary" />
            <span className="truncate">
              {detail?.route?.name ?? t("fleet.unnamedRoute", "Route")}
            </span>
          </span>
          <TripStatusBadge status={trip.status} />
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Gauge className="size-3.5" />
            {speedLabel(pos?.speed)}
          </span>
          <span className="flex items-center gap-1.5">
            <Navigation className="size-3.5" />
            {pos?.eta_next_stop_s != null ? formatEta(pos.eta_next_stop_s) : t("fleet.noEta", "—")}
          </span>
        </div>

        {selected ? (
          <div className="space-y-1.5 border-t border-border pt-2 text-sm">
            {detailQuery.isLoading ? (
              <span className="flex items-center gap-2 text-muted-foreground">
                <Spinner /> {t("fleet.loadingDetail", "Loading details…")}
              </span>
            ) : detail ? (
              <>
                <span className="flex items-center gap-2">
                  <User className="size-3.5 text-muted-foreground" />
                  {detail.driver?.full_name ?? t("fleet.noDriver", "Unassigned")}
                </span>
                <span className="flex items-center gap-2">
                  <Bus className="size-3.5 text-muted-foreground" />
                  {detail.vehicle?.plate_number ?? t("fleet.noVehicle", "No vehicle")}
                </span>
                {!pos ? (
                  <span className="flex items-center gap-2 text-warning-foreground">
                    <MapPin className="size-3.5" />
                    {t("fleet.awaitingGps", "Awaiting GPS signal…")}
                  </span>
                ) : null}
              </>
            ) : (
              <span className="text-muted-foreground">{t("fleet.detailUnavailable", "Details unavailable.")}</span>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
