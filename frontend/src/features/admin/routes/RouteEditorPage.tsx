import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Clock,
  MapPin,
  Pencil,
  Trash2,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CenteredSpinner, ErrorState } from "@/components/common/States";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Field } from "@/components/common/Field";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { formatClock } from "@/lib/format";
import { reverseGeocode } from "@/lib/geocode";
import { getErrorMessage, parseApiError } from "@/lib/api/client";
import { qk, queryClient } from "@/lib/query";
import { routesApi } from "@/lib/api/routes";
import { vehiclesApi } from "@/lib/api/vehicles";
import { driversApi } from "@/lib/api/drivers";
import type { LatLng, Route, ScheduleType, Stop } from "@/lib/api/types";
import {
  MapView,
  MapClick,
  RouteLine,
  StopMarkers,
  Recenter,
  GeocodeSearch,
} from "@/components/maps";

const SCHEDULE_TYPES: ScheduleType[] = ["morning", "evening", "both"];

export function RouteEditorPage() {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const { routeId = "" } = useParams();

  const query = useQuery({
    queryKey: qk.route(routeId),
    queryFn: () => routesApi.get(routeId),
    enabled: !!routeId,
  });

  const [pendingPick, setPendingPick] = useState<LatLng | null>(null);
  const [editingStop, setEditingStop] = useState<Stop | null>(null);
  const [deletingStop, setDeletingStop] = useState<Stop | null>(null);
  const [center, setCenter] = useState<LatLng | null>(null);
  const [reordering, setReordering] = useState(false);

  const route = query.data;
  const stops = useMemo(
    () => [...(route?.stops ?? [])].sort((a, b) => a.stop_order - b.stop_order),
    [route?.stops],
  );

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: qk.route(routeId) });
    void queryClient.invalidateQueries({ queryKey: ["routes"] });
  };

  const reorder = async (orderedIds: string[]) => {
    setReordering(true);
    try {
      await routesApi.reorderStops(routeId, orderedIds);
      invalidate();
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setReordering(false);
    }
  };

  const move = (index: number, dir: -1 | 1) => {
    const next = [...stops];
    const target = index + dir;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    void reorder(next.map((s) => s.id));
  };

  const handleDeleteStop = async () => {
    if (!deletingStop) return;
    try {
      await routesApi.deleteStop(routeId, deletingStop.id);
      toast.success(t("editor.stopDeleted", "Stop removed"));
      invalidate();
    } catch (e) {
      toast.error(await getErrorMessage(e));
      throw e;
    }
  };

  if (query.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("editor.title", "Route editor")} />
        <CenteredSpinner />
      </div>
    );
  }
  if (query.isError || !route) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("editor.title", "Route editor")} />
        <ErrorState onRetry={() => query.refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={route.name}
        description={t("editor.subtitle", "Click the map to add stops; drag the order with the arrows.")}
        actions={
          <Button variant="outline" size="sm" onClick={() => navigate("/admin/routes")}>
            <ArrowLeft className="size-4" />
            {t("editor.back", "All routes")}
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_24rem]">
        <div className="space-y-3">
          <GeocodeSearch
            placeholder={t("editor.searchPlaceholder", "Jump to an address…")}
            onSelect={(r) => setCenter({ lat: r.lat, lng: r.lng })}
          />
          <div className="h-[60vh] w-full overflow-hidden rounded-xl border border-border">
            <MapView center={center ?? stops[0]?.location ?? null} zoom={14}>
              <MapClick onPick={(p) => setPendingPick(p)} />
              <RouteLine stops={stops} />
              <StopMarkers stops={stops} />
              {center ? <Recenter point={center} /> : null}
            </MapView>
          </div>
          {stops.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground">
              {t("editor.clickHint", "Click anywhere on the map to add your first stop.")}
            </p>
          ) : null}
        </div>

        <div className="space-y-4">
          <AssignmentCard route={route} onSaved={invalidate} />

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle className="text-base">
                {t("editor.stops", "Stops")} ({stops.length})
              </CardTitle>
              {reordering ? <Spinner /> : null}
            </CardHeader>
            <CardContent className="space-y-2">
              {stops.length === 0 ? (
                <EmptyState
                  icon={MapPin}
                  title={t("editor.noStops", "No stops yet")}
                  description={t("editor.noStopsDesc", "Click the map to add your first stop.")}
                  className="py-8"
                />
              ) : (
                stops.map((stop, i) => (
                  <div
                    key={stop.id}
                    className="flex items-center gap-2 rounded-lg border border-border p-2.5"
                  >
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{stop.name}</p>
                      <p className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="size-3" />
                        {stop.arrival_time ? formatClock(stop.arrival_time) : t("editor.noTime", "No time set")}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        disabled={i === 0 || reordering}
                        onClick={() => move(i, -1)}
                        aria-label={t("editor.moveUp", "Move up")}
                      >
                        <ArrowUp className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        disabled={i === stops.length - 1 || reordering}
                        onClick={() => move(i, 1)}
                        aria-label={t("editor.moveDown", "Move down")}
                      >
                        <ArrowDown className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        onClick={() => setEditingStop(stop)}
                        aria-label={t("editor.editStop", "Edit stop")}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 text-destructive hover:text-destructive"
                        onClick={() => setDeletingStop(stop)}
                        aria-label={t("editor.deleteStop", "Delete stop")}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {pendingPick ? (
        <AddStopDialog
          routeId={routeId}
          point={pendingPick}
          nextOrder={stops.length}
          onClose={() => setPendingPick(null)}
          onSaved={invalidate}
        />
      ) : null}

      {editingStop ? (
        <EditStopDialog
          routeId={routeId}
          stop={editingStop}
          onClose={() => setEditingStop(null)}
          onSaved={invalidate}
        />
      ) : null}

      <ConfirmDialog
        open={!!deletingStop}
        onOpenChange={(o) => !o && setDeletingStop(null)}
        title={t("editor.deleteStopTitle", "Remove this stop?")}
        description={deletingStop?.name}
        confirmLabel={t("editor.deleteStop", "Delete stop")}
        destructive
        onConfirm={handleDeleteStop}
      />
    </div>
  );
}

function AddStopDialog({
  routeId,
  point,
  nextOrder,
  onClose,
  onSaved,
}: {
  routeId: string;
  point: LatLng;
  nextOrder: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation("admin");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [arrivalTime, setArrivalTime] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [geocoding, setGeocoding] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const label = await reverseGeocode(point.lat, point.lng);
      if (cancelled) return;
      if (label) {
        setAddress(label);
        if (!name) setName(label.split(",").slice(0, 1).join(""));
      }
      setGeocoding(false);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [point.lat, point.lng]);

  const submit = async () => {
    if (!name.trim()) {
      toast.error(t("editor.stopNameRequired", "Give the stop a name."));
      return;
    }
    setSubmitting(true);
    try {
      await routesApi.addStop(routeId, {
        name: name.trim(),
        location: point,
        address: address.trim() || undefined,
        stop_order: nextOrder,
        arrival_time: arrivalTime ? `${arrivalTime}:00` : undefined,
      });
      toast.success(t("editor.stopAdded", "Stop added"));
      onSaved();
      onClose();
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !submitting && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("editor.addStop", "Add stop")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Field label={t("editor.stopName", "Stop name")} htmlFor="stop-name" required>
            <Input
              id="stop-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("editor.stopNamePlaceholder", "e.g. Green Park Gate")}
            />
          </Field>
          <Field
            label={t("editor.address", "Address")}
            htmlFor="stop-address"
            hint={geocoding ? t("editor.geocoding", "Looking up address…") : undefined}
          >
            <Input
              id="stop-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />
          </Field>
          <Field label={t("editor.arrivalTime", "Arrival time")} htmlFor="stop-time">
            <Input
              id="stop-time"
              type="time"
              value={arrivalTime}
              onChange={(e) => setArrivalTime(e.target.value)}
            />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            {t("editor.cancel", "Cancel")}
          </Button>
          <Button onClick={submit} disabled={submitting || !name.trim()}>
            {submitting ? <Spinner /> : null}
            {t("editor.addStop", "Add stop")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditStopDialog({
  routeId,
  stop,
  onClose,
  onSaved,
}: {
  routeId: string;
  stop: Stop;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation("admin");
  const [name, setName] = useState(stop.name);
  const [address, setAddress] = useState(stop.address ?? "");
  const [arrivalTime, setArrivalTime] = useState(stop.arrival_time?.slice(0, 5) ?? "");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!name.trim()) {
      toast.error(t("editor.stopNameRequired", "Give the stop a name."));
      return;
    }
    setSubmitting(true);
    try {
      await routesApi.updateStop(routeId, stop.id, {
        name: name.trim(),
        address: address.trim() || undefined,
        arrival_time: arrivalTime ? `${arrivalTime}:00` : undefined,
      });
      toast.success(t("editor.stopUpdated", "Stop updated"));
      onSaved();
      onClose();
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !submitting && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("editor.editStop", "Edit stop")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Field label={t("editor.stopName", "Stop name")} htmlFor="edit-stop-name" required>
            <Input id="edit-stop-name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t("editor.address", "Address")} htmlFor="edit-stop-address">
            <Input id="edit-stop-address" value={address} onChange={(e) => setAddress(e.target.value)} />
          </Field>
          <Field label={t("editor.arrivalTime", "Arrival time")} htmlFor="edit-stop-time">
            <Input
              id="edit-stop-time"
              type="time"
              value={arrivalTime}
              onChange={(e) => setArrivalTime(e.target.value)}
            />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            {t("editor.cancel", "Cancel")}
          </Button>
          <Button onClick={submit} disabled={submitting || !name.trim()}>
            {submitting ? <Spinner /> : null}
            {t("editor.save", "Save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AssignmentCard({ route, onSaved }: { route: Route; onSaved: () => void }) {
  const { t } = useTranslation("admin");
  const [vehicleId, setVehicleId] = useState(route.vehicle_id ?? "");
  const [driverId, setDriverId] = useState(route.driver_id ?? "");
  const [scheduleType, setScheduleType] = useState<ScheduleType>(route.schedule_type);
  const [saving, setSaving] = useState(false);

  // Keep local form in sync if the route is refetched (e.g. after a 409 retry).
  useEffect(() => {
    setVehicleId(route.vehicle_id ?? "");
    setDriverId(route.driver_id ?? "");
    setScheduleType(route.schedule_type);
  }, [route.vehicle_id, route.driver_id, route.schedule_type]);

  const vehiclesQuery = useQuery({
    queryKey: qk.vehicles({ limit: 200 }),
    queryFn: () => vehiclesApi.list({ limit: 200 }),
  });
  const driversQuery = useQuery({
    queryKey: qk.drivers({ limit: 200 }),
    queryFn: () => driversApi.list({ limit: 200 }),
  });

  const dirty =
    (route.vehicle_id ?? "") !== vehicleId ||
    (route.driver_id ?? "") !== driverId ||
    route.schedule_type !== scheduleType;

  const save = async () => {
    setSaving(true);
    try {
      await routesApi.update(route.id, {
        vehicle_id: vehicleId || null,
        driver_id: driverId || null,
        schedule_type: scheduleType,
        version: route.version,
      });
      toast.success(t("editor.assignmentSaved", "Route updated"));
      onSaved();
    } catch (e) {
      const parsed = await parseApiError(e);
      if (parsed.status === 409) {
        // Stale version: refetch the route, then ask the admin to re-save.
        await queryClient.invalidateQueries({ queryKey: qk.route(route.id) });
        toast.error(t("editor.versionConflict", "This route changed elsewhere. We've refreshed it — please re-apply your changes."));
      } else {
        toast.error(parsed.message);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("editor.assignment", "Assignment")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Field label={t("editor.scheduleType", "Schedule")}>
          <Select value={scheduleType} onValueChange={(v) => setScheduleType(v as ScheduleType)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SCHEDULE_TYPES.map((s) => (
                <SelectItem key={s} value={s} className="capitalize">
                  {t(`routes.schedule.${s}`, s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label={t("editor.vehicle", "Vehicle")}>
          <Select value={vehicleId || "none"} onValueChange={(v) => setVehicleId(v === "none" ? "" : v)}>
            <SelectTrigger>
              <SelectValue placeholder={t("editor.noVehicle", "No vehicle")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">{t("editor.noVehicle", "No vehicle")}</SelectItem>
              {(vehiclesQuery.data?.items ?? []).map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  {v.plate_number}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label={t("editor.driver", "Driver")}>
          <Select value={driverId || "none"} onValueChange={(v) => setDriverId(v === "none" ? "" : v)}>
            <SelectTrigger>
              <SelectValue placeholder={t("editor.noDriver", "No driver")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">{t("editor.noDriver", "No driver")}</SelectItem>
              {(driversQuery.data?.items ?? []).map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {d.full_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Button
          className={cn("w-full")}
          onClick={save}
          disabled={saving || !dirty}
        >
          {saving ? <Spinner /> : null}
          {t("editor.saveAssignment", "Save changes")}
        </Button>
      </CardContent>
    </Card>
  );
}
