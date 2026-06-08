import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bus, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDate } from "@/lib/format";
import { getErrorMessage, HTTPError } from "@/lib/api/client";
import { vehiclesApi } from "@/lib/api";
import type { Vehicle, VehiclePayload, VehicleType } from "@/lib/api/types";
import { qk } from "@/lib/query";

const VEHICLE_TYPES: VehicleType[] = ["bus", "van", "minibus", "car", "other"];

interface FormState {
  plate_number: string;
  vehicle_type: VehicleType;
  capacity: string;
  make: string;
  model: string;
  year: string;
  insurance_expiry: string;
  fitness_expiry: string;
}

const emptyForm: FormState = {
  plate_number: "",
  vehicle_type: "bus",
  capacity: "",
  make: "",
  model: "",
  year: "",
  insurance_expiry: "",
  fitness_expiry: "",
};

function toForm(v: Vehicle): FormState {
  return {
    plate_number: v.plate_number,
    vehicle_type: v.vehicle_type,
    capacity: String(v.capacity),
    make: v.make ?? "",
    model: v.model ?? "",
    year: v.year != null ? String(v.year) : "",
    insurance_expiry: v.insurance_expiry ?? "",
    fitness_expiry: v.fitness_expiry ?? "",
  };
}

/** True when an expiry date is in the past or within 30 days. */
function isExpiring(date: string | null): boolean {
  if (!date) return false;
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return false;
  const ms = d.getTime() - Date.now();
  return ms < 30 * 24 * 60 * 60 * 1000;
}

function ExpiryCell({ date }: { date: string | null }) {
  const { t } = useTranslation("admin");
  if (!date) return <span className="text-muted-foreground">—</span>;
  const expiring = isExpiring(date);
  const past = new Date(date).getTime() < Date.now();
  return (
    <span className="inline-flex items-center gap-2">
      {formatDate(date)}
      {expiring ? (
        <Badge variant="warning">
          {past ? t("vehicles.expired", "Expired") : t("vehicles.expiringSoon", "Soon")}
        </Badge>
      ) : null}
    </span>
  );
}

export function VehiclesPage() {
  const { t } = useTranslation("admin");
  const qc = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Vehicle | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [toDelete, setToDelete] = useState<Vehicle | null>(null);

  const params = { limit: 100, offset: 0 };
  const list = useQuery({
    queryKey: qk.vehicles(params),
    queryFn: () => vehiclesApi.list(params),
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["vehicles"] });

  const saveMutation = useMutation({
    mutationFn: (payload: VehiclePayload) =>
      editing ? vehiclesApi.update(editing.id, payload) : vehiclesApi.create(payload),
    onSuccess: () => {
      toast.success(
        editing
          ? t("vehicles.updated", "Vehicle updated")
          : t("vehicles.added", "Vehicle added"),
      );
      invalidate();
      setDialogOpen(false);
    },
    onError: async (e) => {
      if (e instanceof HTTPError && e.response.status === 409) {
        toast.error(t("vehicles.plateExists", "Plate number already exists"));
        return;
      }
      toast.error(await getErrorMessage(e));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => vehiclesApi.remove(id),
    onSuccess: () => {
      toast.success(t("vehicles.deleted", "Vehicle removed"));
      invalidate();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setErrors({});
    setDialogOpen(true);
  };

  const openEdit = (v: Vehicle) => {
    setEditing(v);
    setForm(toForm(v));
    setErrors({});
    setDialogOpen(true);
  };

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const next: Partial<Record<keyof FormState, string>> = {};
    if (!form.plate_number.trim())
      next.plate_number = t("vehicles.plateRequired", "Plate number is required");
    const cap = Number(form.capacity);
    if (!form.capacity || !Number.isFinite(cap) || cap <= 0)
      next.capacity = t("vehicles.capacityInvalid", "Capacity must be greater than 0");
    if (form.year) {
      const y = Number(form.year);
      if (!Number.isInteger(y) || y < 1980 || y > 2100)
        next.year = t("vehicles.yearInvalid", "Enter a valid year");
    }
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const payload: VehiclePayload = {
      plate_number: form.plate_number.trim().toUpperCase(),
      vehicle_type: form.vehicle_type,
      capacity: cap,
      make: form.make.trim() || null,
      model: form.model.trim() || null,
      year: form.year ? Number(form.year) : null,
      insurance_expiry: form.insurance_expiry || null,
      fitness_expiry: form.fitness_expiry || null,
    };
    saveMutation.mutate(payload);
  };

  const items = list.data?.items ?? [];

  const expiringCount = useMemo(
    () =>
      items.filter(
        (v) => isExpiring(v.insurance_expiry) || isExpiring(v.fitness_expiry),
      ).length,
    [items],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("vehicles.title", "Vehicles")}
        description={
          expiringCount > 0
            ? t("vehicles.expiringDesc", "{{count}} need document renewal", {
                count: expiringCount,
              })
            : t("vehicles.desc", "Manage your fleet")
        }
        actions={
          <Button onClick={openCreate}>
            <Plus className="size-4" />
            {t("vehicles.add", "Add vehicle")}
          </Button>
        }
      />

      {list.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : list.isError ? (
        <ErrorState onRetry={() => list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bus}
          title={t("vehicles.emptyTitle", "No vehicles yet")}
          description={t(
            "vehicles.emptyBody",
            "Add your first bus or van to start building routes.",
          )}
          action={
            <Button onClick={openCreate}>
              <Plus className="size-4" />
              {t("vehicles.add", "Add vehicle")}
            </Button>
          }
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("vehicles.colPlate", "Plate")}</TableHead>
                  <TableHead>{t("vehicles.colType", "Type")}</TableHead>
                  <TableHead>{t("vehicles.colCapacity", "Capacity")}</TableHead>
                  <TableHead>{t("vehicles.colInsurance", "Insurance")}</TableHead>
                  <TableHead>{t("vehicles.colFitness", "Fitness")}</TableHead>
                  <TableHead>{t("vehicles.colStatus", "Status")}</TableHead>
                  <TableHead className="text-right">
                    {t("vehicles.colActions", "Actions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((v) => (
                  <TableRow key={v.id}>
                    <TableCell className="font-medium">
                      {v.plate_number}
                      {v.make || v.model ? (
                        <span className="block text-xs text-muted-foreground">
                          {[v.make, v.model, v.year].filter(Boolean).join(" ")}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="capitalize">{v.vehicle_type}</TableCell>
                    <TableCell className="tabular-nums">{v.capacity}</TableCell>
                    <TableCell>
                      <ExpiryCell date={v.insurance_expiry} />
                    </TableCell>
                    <TableCell>
                      <ExpiryCell date={v.fitness_expiry} />
                    </TableCell>
                    <TableCell>
                      <Badge variant={v.is_active ? "success" : "muted"}>
                        {v.is_active
                          ? t("vehicles.active", "Active")
                          : t("vehicles.inactive", "Inactive")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEdit(v)}
                          aria-label={t("vehicles.edit", "Edit")}
                        >
                          <Pencil className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setToDelete(v)}
                          aria-label={t("vehicles.delete", "Delete")}
                        >
                          <Trash2 className="size-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={(o) => !saveMutation.isPending && setDialogOpen(o)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editing
                ? t("vehicles.editTitle", "Edit vehicle")
                : t("vehicles.addTitle", "Add vehicle")}
            </DialogTitle>
            <DialogDescription>
              {t("vehicles.formDesc", "Vehicle details and document expiry dates.")}
            </DialogDescription>
          </DialogHeader>
          <form id="vehicle-form" onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label={t("vehicles.fPlate", "Plate number")}
                htmlFor="plate_number"
                required
                error={errors.plate_number}
              >
                <Input
                  id="plate_number"
                  value={form.plate_number}
                  onChange={(e) => set("plate_number", e.target.value)}
                  placeholder="MH12AB1234"
                  autoFocus
                />
              </Field>
              <Field label={t("vehicles.fType", "Type")} htmlFor="vehicle_type">
                <Select
                  value={form.vehicle_type}
                  onValueChange={(v) => set("vehicle_type", v as VehicleType)}
                >
                  <SelectTrigger id="vehicle_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {VEHICLE_TYPES.map((vt) => (
                      <SelectItem key={vt} value={vt} className="capitalize">
                        {vt}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <Field
                label={t("vehicles.fCapacity", "Capacity")}
                htmlFor="capacity"
                required
                error={errors.capacity}
              >
                <Input
                  id="capacity"
                  type="number"
                  min={1}
                  value={form.capacity}
                  onChange={(e) => set("capacity", e.target.value)}
                  placeholder="40"
                />
              </Field>
              <Field label={t("vehicles.fMake", "Make")} htmlFor="make">
                <Input
                  id="make"
                  value={form.make}
                  onChange={(e) => set("make", e.target.value)}
                  placeholder="Tata"
                />
              </Field>
              <Field label={t("vehicles.fModel", "Model")} htmlFor="model">
                <Input
                  id="model"
                  value={form.model}
                  onChange={(e) => set("model", e.target.value)}
                  placeholder="Starbus"
                />
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <Field
                label={t("vehicles.fYear", "Year")}
                htmlFor="year"
                error={errors.year}
              >
                <Input
                  id="year"
                  type="number"
                  value={form.year}
                  onChange={(e) => set("year", e.target.value)}
                  placeholder="2022"
                />
              </Field>
              <Field
                label={t("vehicles.fInsurance", "Insurance expiry")}
                htmlFor="insurance_expiry"
              >
                <Input
                  id="insurance_expiry"
                  type="date"
                  value={form.insurance_expiry}
                  onChange={(e) => set("insurance_expiry", e.target.value)}
                />
              </Field>
              <Field
                label={t("vehicles.fFitness", "Fitness expiry")}
                htmlFor="fitness_expiry"
              >
                <Input
                  id="fitness_expiry"
                  type="date"
                  value={form.fitness_expiry}
                  onChange={(e) => set("fitness_expiry", e.target.value)}
                />
              </Field>
            </div>
          </form>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={saveMutation.isPending}
            >
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="submit" form="vehicle-form" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? <Spinner /> : null}
              {editing ? t("common.save", "Save") : t("vehicles.add", "Add vehicle")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(o) => !o && setToDelete(null)}
        title={t("vehicles.deleteTitle", "Remove vehicle?")}
        description={t(
          "vehicles.deleteBody",
          "This removes {{plate}} from your fleet. Routes using it will need a new vehicle.",
          { plate: toDelete?.plate_number ?? "" },
        )}
        confirmLabel={t("vehicles.delete", "Delete")}
        destructive
        onConfirm={async () => {
          if (toDelete) await deleteMutation.mutateAsync(toDelete.id);
          setToDelete(null);
        }}
      />
    </div>
  );
}
