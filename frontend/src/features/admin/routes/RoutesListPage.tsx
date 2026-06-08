import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { MapPin, Plus, Route as RouteIcon, Trash2, User, Bus } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState, CardListSkeleton } from "@/components/common/States";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Field } from "@/components/common/Field";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getErrorMessage } from "@/lib/api/client";
import { qk, queryClient } from "@/lib/query";
import { routesApi } from "@/lib/api/routes";
import { vehiclesApi } from "@/lib/api/vehicles";
import { driversApi } from "@/lib/api/drivers";
import type { Route, ScheduleType } from "@/lib/api/types";

const SCHEDULE_TYPES: ScheduleType[] = ["morning", "evening", "both"];

const scheduleVariant: Record<ScheduleType, "secondary" | "warning" | "default"> = {
  morning: "warning",
  evening: "secondary",
  both: "default",
};

export function RoutesListPage() {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleting, setDeleting] = useState<Route | null>(null);

  const query = useQuery({
    queryKey: qk.routes({ limit: 100 }),
    queryFn: () => routesApi.list({ limit: 100 }),
  });

  const vehicleMap = useVehicleMap();
  const driverMap = useDriverMap();

  const handleDelete = async () => {
    if (!deleting) return;
    try {
      await routesApi.remove(deleting.id);
      toast.success(t("routes.deleted", "Route deleted"));
      void queryClient.invalidateQueries({ queryKey: ["routes"] });
    } catch (e) {
      toast.error(await getErrorMessage(e));
      throw e;
    }
  };

  const items = query.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("routes.title", "Routes")}
        description={t("routes.subtitle", "Define routes, then add stops on the map editor.")}
        actions={
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="size-4" />
                {t("routes.create", "Create route")}
              </Button>
            </DialogTrigger>
            <CreateRouteDialog
              onCreated={(route) => {
                setCreateOpen(false);
                navigate(`/admin/routes/${route.id}`);
              }}
            />
          </Dialog>
        }
      />

      {query.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={RouteIcon}
          title={t("routes.empty.title", "No routes yet")}
          description={t("routes.empty.desc", "Create your first route to start placing bus stops.")}
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" />
              {t("routes.create", "Create route")}
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((route) => (
            <Card
              key={route.id}
              className="cursor-pointer transition-colors hover:border-primary"
              onClick={() => navigate(`/admin/routes/${route.id}`)}
            >
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate font-semibold">{route.name}</p>
                  <Badge variant={scheduleVariant[route.schedule_type]} className="capitalize">
                    {t(`routes.schedule.${route.schedule_type}`, route.schedule_type)}
                  </Badge>
                </div>

                {route.description ? (
                  <p className="line-clamp-2 text-sm text-muted-foreground">{route.description}</p>
                ) : null}

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <MapPin className="size-3.5" />
                    {t("routes.stopCount", "{{count}} stops", { count: route.stops.length })}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Bus className="size-3.5" />
                    {route.vehicle_id ? vehicleMap.get(route.vehicle_id) ?? t("routes.assigned", "Assigned") : t("routes.noVehicle", "No vehicle")}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <User className="size-3.5" />
                    {route.driver_id ? driverMap.get(route.driver_id) ?? t("routes.assigned", "Assigned") : t("routes.noDriver", "No driver")}
                  </span>
                </div>

                <div className="flex justify-end border-t border-border pt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleting(route);
                    }}
                  >
                    <Trash2 className="size-4" />
                    {t("routes.delete", "Delete")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t("routes.deleteTitle", "Delete route?")}
        description={t("routes.deleteDesc", "This removes the route and its stops. This can't be undone.")}
        confirmLabel={t("routes.delete", "Delete")}
        destructive
        onConfirm={handleDelete}
      />
    </div>
  );
}

function useVehicleMap() {
  const q = useQuery({
    queryKey: qk.vehicles({ limit: 100 }),
    queryFn: () => vehiclesApi.list({ limit: 100 }),
    staleTime: 60_000,
  });
  return useMemo(() => {
    const m = new Map<string, string>();
    for (const v of q.data?.items ?? []) m.set(v.id, v.plate_number);
    return m;
  }, [q.data]);
}

function useDriverMap() {
  const q = useQuery({
    queryKey: qk.drivers({ limit: 100 }),
    queryFn: () => driversApi.list({ limit: 100 }),
    staleTime: 60_000,
  });
  return useMemo(() => {
    const m = new Map<string, string>();
    for (const d of q.data?.items ?? []) m.set(d.id, d.full_name);
    return m;
  }, [q.data]);
}

function CreateRouteDialog({ onCreated }: { onCreated: (route: Route) => void }) {
  const { t } = useTranslation("admin");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scheduleType, setScheduleType] = useState<ScheduleType>("morning");
  const [vehicleId, setVehicleId] = useState<string>("");
  const [driverId, setDriverId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  const vehiclesQuery = useQuery({
    queryKey: qk.vehicles({ limit: 100 }),
    queryFn: () => vehiclesApi.list({ limit: 100 }),
  });
  const driversQuery = useQuery({
    queryKey: qk.drivers({ limit: 100 }),
    queryFn: () => driversApi.list({ limit: 100 }),
  });

  const submit = async () => {
    if (!name.trim()) {
      toast.error(t("routes.nameRequired", "Route name is required."));
      return;
    }
    setSubmitting(true);
    try {
      const route = await routesApi.create({
        name: name.trim(),
        description: description.trim() || undefined,
        schedule_type: scheduleType,
        vehicle_id: vehicleId || undefined,
        driver_id: driverId || undefined,
      });
      toast.success(t("routes.created", "Route created"));
      void queryClient.invalidateQueries({ queryKey: ["routes"] });
      onCreated(route);
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{t("routes.create", "Create route")}</DialogTitle>
        <DialogDescription>
          {t("routes.createDesc", "Name the route and optionally assign a vehicle and driver.")}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        <Field label={t("routes.name", "Route name")} htmlFor="route-name" required>
          <Input
            id="route-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("routes.namePlaceholder", "e.g. Sector 14 — Morning")}
          />
        </Field>

        <Field label={t("routes.description", "Description")} htmlFor="route-desc">
          <Textarea
            id="route-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </Field>

        <Field label={t("routes.scheduleType", "Schedule")}>
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

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("routes.vehicle", "Vehicle")}>
            <Select value={vehicleId} onValueChange={setVehicleId}>
              <SelectTrigger>
                <SelectValue placeholder={t("routes.optional", "Optional")} />
              </SelectTrigger>
              <SelectContent>
                {(vehiclesQuery.data?.items ?? []).map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    {v.plate_number}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label={t("routes.driver", "Driver")}>
            <Select value={driverId} onValueChange={setDriverId}>
              <SelectTrigger>
                <SelectValue placeholder={t("routes.optional", "Optional")} />
              </SelectTrigger>
              <SelectContent>
                {(driversQuery.data?.items ?? []).map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
      </div>

      <DialogFooter>
        <Button onClick={submit} disabled={submitting || !name.trim()}>
          {submitting ? <Spinner /> : null}
          {t("routes.create", "Create route")}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
