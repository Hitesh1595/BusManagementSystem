import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  Bus,
  Check,
  Copy,
  GraduationCap,
  Navigation,
  Plus,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { schoolsApi, superAdminApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";
import type { School } from "@/lib/api/types";
import { qk } from "@/lib/query";

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

export function SuperDashboard() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const params = { limit: 100 };
  const list = useQuery({
    queryKey: qk.schools(params),
    queryFn: () => schoolsApi.list(params),
  });

  const analytics = useQuery({
    queryKey: ["superPlatform"],
    queryFn: () => superAdminApi.platformAnalytics(),
  });

  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ name: "", address: "", phone: "", email: "" });
  const [nameError, setNameError] = useState<string | null>(null);
  const [created, setCreated] = useState<School | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      schoolsApi.create({
        name: form.name.trim(),
        address: form.address.trim() || undefined,
        phone: form.phone.trim() || undefined,
        email: form.email.trim() || undefined,
      }),
    onSuccess: (school) => {
      qc.invalidateQueries({ queryKey: ["schools"] });
      setAddOpen(false);
      setCreated(school);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setNameError("School name is required");
      return;
    }
    setNameError(null);
    createMutation.mutate();
  };

  const openAdd = () => {
    setForm({ name: "", address: "", phone: "", email: "" });
    setNameError(null);
    setAddOpen(true);
  };

  const items = list.data?.items ?? [];
  const a = analytics.data;
  const aLoading = analytics.isLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform admin"
        description="Create and manage schools across the platform."
        actions={
          <Button onClick={openAdd}>
            <Plus className="size-4" />
            Add school
          </Button>
        }
      />

      {list.isLoading ? (
        <CardListSkeleton rows={5} />
      ) : list.isError ? (
        <ErrorState onRetry={() => list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No schools yet"
          description="Create the first school to get started."
          action={
            <Button onClick={openAdd}>
              <Plus className="size-4" />
              Add school
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard icon={Building2} label="Schools" value={a?.total_schools} loading={aLoading} />
            <StatCard icon={Navigation} label="Active trips" value={a?.active_trips} loading={aLoading} />
            <StatCard
              icon={AlertTriangle}
              label="Open alerts"
              value={a?.open_alerts}
              loading={aLoading}
              accent="destructive"
            />
            <StatCard icon={Users} label="Admins" value={a?.users_by_role.school_admin} loading={aLoading} />
            <StatCard icon={Bus} label="Drivers" value={a?.users_by_role.driver} loading={aLoading} />
            <StatCard icon={GraduationCap} label="Parents" value={a?.users_by_role.parent} loading={aLoading} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Schools</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Join code</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Timezone</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((s) => (
                    <TableRow
                      key={s.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/super/schools/${s.id}`)}
                    >
                      <TableCell className="font-medium">{s.name}</TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <span className="flex items-center gap-1">
                          <code className="font-mono text-sm tracking-wider">
                            {s.join_code}
                          </code>
                          <CopyButton value={s.join_code} />
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={s.is_active ? "success" : "muted"}>
                          {s.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {s.timezone}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      {/* Create school */}
      <Dialog open={addOpen} onOpenChange={(o) => !createMutation.isPending && setAddOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add school</DialogTitle>
            <DialogDescription>
              A join code is generated automatically — share it with the school's
              admins so parents can self-register.
            </DialogDescription>
          </DialogHeader>
          <form id="add-school-form" onSubmit={submit} className="space-y-4">
            <Field label="School name" htmlFor="sc-name" required error={nameError ?? undefined}>
              <Input
                id="sc-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                autoFocus
              />
            </Field>
            <Field label="Address" htmlFor="sc-address">
              <Input
                id="sc-address"
                value={form.address}
                onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Phone" htmlFor="sc-phone">
                <Input
                  id="sc-phone"
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                />
              </Field>
              <Field label="Email" htmlFor="sc-email">
                <Input
                  id="sc-email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                />
              </Field>
            </div>
          </form>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setAddOpen(false)}
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" form="add-school-form" disabled={createMutation.isPending}>
              {createMutation.isPending ? <Spinner /> : null}
              Add school
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Created — reveal join code */}
      <Dialog open={created !== null} onOpenChange={(o) => !o && setCreated(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{created?.name} created</DialogTitle>
            <DialogDescription>
              Share this join code with the school's admins and parents.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted px-4 py-3">
            <code className="select-all font-mono text-2xl font-bold tracking-[0.3em]">
              {created?.join_code}
            </code>
            {created ? <CopyButton value={created.join_code} /> : null}
          </div>
          <DialogFooter>
            <Button onClick={() => setCreated(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
