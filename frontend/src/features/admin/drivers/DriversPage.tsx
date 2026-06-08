import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Link2, Pencil, Plus, Users } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
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
import { maskPhone } from "@/lib/format";
import { getErrorMessage, HTTPError } from "@/lib/api/client";
import { driversApi, vehiclesApi } from "@/lib/api";
import type { Driver } from "@/lib/api/types";
import { qk } from "@/lib/query";

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard may be unavailable */
        }
      }}
    >
      {copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
      {label}
    </Button>
  );
}

export function DriversPage() {
  const { t } = useTranslation("admin");
  const qc = useQueryClient();

  const params = { limit: 100, offset: 0 };
  const list = useQuery({
    queryKey: qk.drivers(params),
    queryFn: () => driversApi.list(params),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["drivers"] });

  // ---- Add driver ----
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({ email: "", full_name: "", phone: "" });
  const [addErrors, setAddErrors] = useState<{ email?: string; full_name?: string }>({});
  const [tempPassword, setTempPassword] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      driversApi.create({
        email: addForm.email.trim(),
        full_name: addForm.full_name.trim(),
        phone: addForm.phone.trim() || undefined,
      }),
    onSuccess: (res) => {
      toast.success(t("drivers.created", "Driver account created"));
      invalidate();
      setAddOpen(false);
      setTempPassword(res.temp_password);
    },
    onError: async (e) => {
      if (e instanceof HTTPError && e.response.status === 409) {
        toast.error(t("drivers.emailExists", "A user with that email already exists"));
        return;
      }
      toast.error(await getErrorMessage(e));
    },
  });

  const submitAdd = (e: React.FormEvent) => {
    e.preventDefault();
    const next: { email?: string; full_name?: string } = {};
    if (!/^\S+@\S+\.\S+$/.test(addForm.email.trim()))
      next.email = t("drivers.emailInvalid", "Enter a valid email");
    if (!addForm.full_name.trim())
      next.full_name = t("drivers.nameRequired", "Name is required");
    setAddErrors(next);
    if (Object.keys(next).length > 0) return;
    createMutation.mutate();
  };

  const openAdd = () => {
    setAddForm({ email: "", full_name: "", phone: "" });
    setAddErrors({});
    setAddOpen(true);
  };

  // ---- Edit driver ----
  const [editing, setEditing] = useState<Driver | null>(null);
  const [editForm, setEditForm] = useState({ full_name: "", phone: "", is_active: true });

  const editMutation = useMutation({
    mutationFn: () =>
      driversApi.update(editing!.id, {
        full_name: editForm.full_name.trim(),
        phone: editForm.phone.trim() || undefined,
        is_active: editForm.is_active,
      }),
    onSuccess: () => {
      toast.success(t("drivers.updated", "Driver updated"));
      invalidate();
      setEditing(null);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const openEdit = (d: Driver) => {
    setEditForm({
      full_name: d.full_name,
      phone: d.phone ?? "",
      is_active: d.is_active,
    });
    setEditing(d);
  };

  // ---- Assign vehicle ----
  const [assigning, setAssigning] = useState<Driver | null>(null);
  const [vehicleId, setVehicleId] = useState("");

  const vehicles = useQuery({
    queryKey: qk.vehicles({ limit: 100 }),
    queryFn: () => vehiclesApi.list({ limit: 100 }),
    enabled: assigning !== null,
  });

  const assignMutation = useMutation({
    mutationFn: () => driversApi.assignVehicle(assigning!.id, vehicleId),
    onSuccess: () => {
      toast.success(t("drivers.assigned", "Vehicle assigned"));
      invalidate();
      setAssigning(null);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const openAssign = (d: Driver) => {
    setVehicleId("");
    setAssigning(d);
  };

  const items = list.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("drivers.title", "Drivers")}
        description={t("drivers.desc", "Manage driver accounts and vehicle assignments")}
        actions={
          <Button onClick={openAdd}>
            <Plus className="size-4" />
            {t("drivers.add", "Add driver")}
          </Button>
        }
      />

      {list.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : list.isError ? (
        <ErrorState onRetry={() => list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Users}
          title={t("drivers.emptyTitle", "No drivers yet")}
          description={t(
            "drivers.emptyBody",
            "Create driver accounts so they can run trips and report attendance.",
          )}
          action={
            <Button onClick={openAdd}>
              <Plus className="size-4" />
              {t("drivers.add", "Add driver")}
            </Button>
          }
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("drivers.colName", "Name")}</TableHead>
                  <TableHead>{t("drivers.colEmail", "Email")}</TableHead>
                  <TableHead>{t("drivers.colPhone", "Phone")}</TableHead>
                  <TableHead>{t("drivers.colStatus", "Status")}</TableHead>
                  <TableHead className="text-right">
                    {t("drivers.colActions", "Actions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium">{d.full_name}</TableCell>
                    <TableCell className="text-muted-foreground">{d.email}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {maskPhone(d.phone)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={d.is_active ? "success" : "muted"}>
                        {d.is_active
                          ? t("drivers.active", "Active")
                          : t("drivers.inactive", "Inactive")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openAssign(d)}
                        >
                          <Link2 className="size-4" />
                          {t("drivers.assign", "Assign")}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEdit(d)}
                          aria-label={t("drivers.edit", "Edit")}
                        >
                          <Pencil className="size-4" />
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

      {/* Add driver */}
      <Dialog open={addOpen} onOpenChange={(o) => !createMutation.isPending && setAddOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("drivers.addTitle", "Add driver")}</DialogTitle>
            <DialogDescription>
              {t(
                "drivers.addDesc",
                "We'll create an account and generate a temporary password to share with the driver.",
              )}
            </DialogDescription>
          </DialogHeader>
          <form id="add-driver-form" onSubmit={submitAdd} className="space-y-4">
            <Field
              label={t("drivers.fName", "Full name")}
              htmlFor="d-name"
              required
              error={addErrors.full_name}
            >
              <Input
                id="d-name"
                value={addForm.full_name}
                onChange={(e) => setAddForm((f) => ({ ...f, full_name: e.target.value }))}
                autoFocus
              />
            </Field>
            <Field
              label={t("drivers.fEmail", "Email")}
              htmlFor="d-email"
              required
              error={addErrors.email}
            >
              <Input
                id="d-email"
                type="email"
                value={addForm.email}
                onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
              />
            </Field>
            <Field label={t("drivers.fPhone", "Phone")} htmlFor="d-phone">
              <Input
                id="d-phone"
                type="tel"
                value={addForm.phone}
                onChange={(e) => setAddForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="+91…"
              />
            </Field>
          </form>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setAddOpen(false)}
              disabled={createMutation.isPending}
            >
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="submit" form="add-driver-form" disabled={createMutation.isPending}>
              {createMutation.isPending ? <Spinner /> : null}
              {t("drivers.add", "Add driver")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Temp password (shown once) */}
      <Dialog open={tempPassword !== null} onOpenChange={(o) => !o && setTempPassword(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("drivers.tempTitle", "Temporary password")}</DialogTitle>
            <DialogDescription>
              {t(
                "drivers.tempDesc",
                "Share this with the driver now — it is shown only once. They'll be asked to change it on first login.",
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted px-4 py-3">
            <code className="select-all font-mono text-base font-semibold tracking-wide">
              {tempPassword}
            </code>
            {tempPassword ? (
              <CopyButton value={tempPassword} label={t("common.copy", "Copy")} />
            ) : null}
          </div>
          <DialogFooter>
            <Button onClick={() => setTempPassword(null)}>
              {t("drivers.tempDone", "Done")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit driver */}
      <Dialog open={editing !== null} onOpenChange={(o) => !editMutation.isPending && !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("drivers.editTitle", "Edit driver")}</DialogTitle>
            <DialogDescription>{editing?.email}</DialogDescription>
          </DialogHeader>
          <form
            id="edit-driver-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (editForm.full_name.trim()) editMutation.mutate();
            }}
            className="space-y-4"
          >
            <Field label={t("drivers.fName", "Full name")} htmlFor="e-name" required>
              <Input
                id="e-name"
                value={editForm.full_name}
                onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
              />
            </Field>
            <Field label={t("drivers.fPhone", "Phone")} htmlFor="e-phone">
              <Input
                id="e-phone"
                type="tel"
                value={editForm.phone}
                onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
              />
            </Field>
            <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
              <div>
                <p className="text-sm font-medium">{t("drivers.activeLabel", "Active")}</p>
                <p className="text-xs text-muted-foreground">
                  {t("drivers.activeHint", "Inactive drivers can't sign in or run trips.")}
                </p>
              </div>
              <Switch
                checked={editForm.is_active}
                onCheckedChange={(c) => setEditForm((f) => ({ ...f, is_active: c }))}
              />
            </div>
          </form>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setEditing(null)}
              disabled={editMutation.isPending}
            >
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="submit" form="edit-driver-form" disabled={editMutation.isPending}>
              {editMutation.isPending ? <Spinner /> : null}
              {t("common.save", "Save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign vehicle */}
      <Dialog open={assigning !== null} onOpenChange={(o) => !assignMutation.isPending && !o && setAssigning(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("drivers.assignTitle", "Assign vehicle")}</DialogTitle>
            <DialogDescription>
              {t("drivers.assignDesc", "Assign a vehicle to {{name}}.", {
                name: assigning?.full_name ?? "",
              })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {vehicles.isLoading ? (
              <CardListSkeleton rows={1} />
            ) : vehicles.isError ? (
              <ErrorState onRetry={() => vehicles.refetch()} />
            ) : (vehicles.data?.items.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t("drivers.noVehicles", "No vehicles available. Add a vehicle first.")}
              </p>
            ) : (
              <Field label={t("drivers.fVehicle", "Vehicle")} htmlFor="assign-vehicle">
                <Select value={vehicleId} onValueChange={setVehicleId}>
                  <SelectTrigger id="assign-vehicle">
                    <SelectValue placeholder={t("drivers.pickVehicle", "Select a vehicle")} />
                  </SelectTrigger>
                  <SelectContent>
                    {vehicles.data?.items.map((v) => (
                      <SelectItem key={v.id} value={v.id}>
                        {v.plate_number} · <span className="capitalize">{v.vehicle_type}</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setAssigning(null)}
              disabled={assignMutation.isPending}
            >
              {t("common.cancel", "Cancel")}
            </Button>
            <Button
              onClick={() => assignMutation.mutate()}
              disabled={!vehicleId || assignMutation.isPending}
            >
              {assignMutation.isPending ? <Spinner /> : null}
              {t("drivers.assign", "Assign")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
