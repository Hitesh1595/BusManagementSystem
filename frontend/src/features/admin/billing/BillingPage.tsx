import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Plus, Receipt, Wallet } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { Field } from "@/components/common/Field";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { BadgeProps } from "@/components/ui/badge";
import { paymentsApi, routesApi, studentsApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/format";
import { qk, queryClient } from "@/lib/query";
import { usePagination } from "@/lib/hooks/usePagination";
import { useEntityMap } from "@/lib/hooks/useEntityMap";
import type {
  BillingCycle,
  FeeSchedule,
  Invoice,
  InvoiceStatus,
  Route,
} from "@/lib/api/types";

type Tab = "fees" | "invoices";
const CYCLES: BillingCycle[] = ["one_time", "monthly", "quarterly", "term", "annual"];

const INVOICE_VARIANT: Record<InvoiceStatus, BadgeProps["variant"]> = {
  draft: "muted",
  sent: "secondary",
  paid: "success",
  overdue: "destructive",
  cancelled: "muted",
};

export function BillingPage() {
  const { t } = useTranslation("admin");
  const [tab, setTab] = useState<Tab>("fees");

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("billing.title", "Billing")}
        description={t("billing.subtitle", "Set transport fees, generate invoices, and record payments.")}
      />
      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="fees">{t("billing.tab.fees", "Fee schedules")}</TabsTrigger>
          <TabsTrigger value="invoices">{t("billing.tab.invoices", "Invoices")}</TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === "fees" ? <FeesTab /> : <InvoicesTab />}
    </div>
  );
}

function FeesTab() {
  const { t } = useTranslation("admin");
  const [adding, setAdding] = useState(false);

  const query = useQuery({
    queryKey: qk.feeSchedules({ limit: 100 }),
    queryFn: () => paymentsApi.listFeeSchedules({ limit: 100 }),
  });
  const routesQuery = useQuery({
    queryKey: qk.routes({ limit: 100 }),
    queryFn: () => routesApi.list({ limit: 100 }),
    staleTime: 60_000,
  });
  const routeName = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of routesQuery.data?.items ?? []) m.set(r.id, r.name);
    return m;
  }, [routesQuery.data]);

  const items = query.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setAdding(true)}>
          <Plus className="size-4" />
          {t("billing.addFee", "Add fee")}
        </Button>
      </div>

      {query.isLoading ? (
        <CardListSkeleton rows={3} />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Wallet}
          title={t("billing.feesEmpty.title", "No fee schedules")}
          description={t("billing.feesEmpty.desc", "Create a fee to start generating invoices.")}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((f) => (
            <FeeCard key={f.id} fee={f} routeLabel={f.route_id ? routeName.get(f.route_id) : undefined} />
          ))}
        </div>
      )}

      {adding ? (
        <AddFeeDialog routes={routesQuery.data?.items ?? []} onClose={() => setAdding(false)} />
      ) : null}
    </div>
  );
}

function FeeCard({ fee, routeLabel }: { fee: FeeSchedule; routeLabel?: string }) {
  const { t } = useTranslation("admin");

  const generate = useMutation({
    mutationFn: () => paymentsApi.bulkGenerate(fee.id),
    onSuccess: (res) => {
      toast.success(
        t("billing.generated", "{{count}} invoice(s) generated", { count: res.count }),
      );
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const toggle = useMutation({
    mutationFn: () => paymentsApi.updateFeeSchedule(fee.id, { is_active: !fee.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["fee-schedules"] }),
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold">{fee.name}</p>
            <p className="text-2xl font-bold tabular-nums">{formatCurrency(fee.amount)}</p>
          </div>
          <Badge variant={fee.is_active ? "success" : "muted"}>
            {fee.is_active ? t("billing.active", "Active") : t("billing.inactive", "Inactive")}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <Badge variant="outline" className="capitalize">
            {fee.billing_cycle.replace("_", " ")}
          </Badge>
          <Badge variant="muted">
            {routeLabel ?? t("billing.schoolWide", "School-wide")}
          </Badge>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => generate.mutate()}
            disabled={generate.isPending || !fee.is_active}
          >
            {generate.isPending ? <Spinner /> : null}
            {t("billing.generate", "Generate invoices")}
          </Button>
          <Button size="sm" variant="outline" onClick={() => toggle.mutate()} disabled={toggle.isPending}>
            {fee.is_active ? t("billing.deactivate", "Deactivate") : t("billing.activate", "Activate")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function AddFeeDialog({ routes, onClose }: { routes: Route[]; onClose: () => void }) {
  const { t } = useTranslation("admin");
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [cycle, setCycle] = useState<BillingCycle>("monthly");
  const [routeId, setRouteId] = useState<string>("all");
  const [from, setFrom] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      paymentsApi.createFeeSchedule({
        name: name.trim(),
        amount: Number(amount),
        billing_cycle: cycle,
        effective_from: from,
        route_id: routeId === "all" ? null : routeId,
      }),
    onSuccess: () => {
      toast.success(t("billing.feeCreated", "Fee schedule created"));
      void queryClient.invalidateQueries({ queryKey: ["fee-schedules"] });
      onClose();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const canSubmit =
    name.trim().length > 0 && Number(amount) > 0 && from.length > 0 && !mut.isPending;

  return (
    <Dialog open onOpenChange={(o) => !o && !mut.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("billing.addFee", "Add fee")}</DialogTitle>
          <DialogDescription>
            {t("billing.addFeeDesc", "Define a transport fee. School-wide unless you pick a route.")}
          </DialogDescription>
        </DialogHeader>
        <form
          id="add-fee-form"
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) mut.mutate();
          }}
        >
          <Field label={t("billing.name", "Name")} htmlFor="fee-name" required>
            <Input id="fee-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("billing.amount", "Amount (₹)")} htmlFor="fee-amount" required>
              <Input
                id="fee-amount"
                type="number"
                min="1"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </Field>
            <Field label={t("billing.cycle", "Billing cycle")} required>
              <Select value={cycle} onValueChange={(v) => setCycle(v as BillingCycle)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CYCLES.map((c) => (
                    <SelectItem key={c} value={c} className="capitalize">
                      {c.replace("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
          <Field label={t("billing.scope", "Applies to")}>
            <Select value={routeId} onValueChange={setRouteId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("billing.schoolWide", "School-wide")}</SelectItem>
                {routes.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={t("billing.effectiveFrom", "Effective from")} htmlFor="fee-from" required>
            <Input id="fee-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mut.isPending}>
            {t("common.cancel", "Cancel")}
          </Button>
          <Button type="submit" form="add-fee-form" disabled={!canSubmit}>
            {mut.isPending ? <Spinner /> : null}
            {t("billing.create", "Create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function InvoicesTab() {
  const { t } = useTranslation("admin");
  const [status, setStatus] = useState<string>("all");

  const { limit, offset, setOffset } = usePagination(24, status);
  const params = useMemo(
    () => ({
      status: status === "all" ? undefined : (status as InvoiceStatus),
      limit,
      offset,
    }),
    [status, limit, offset],
  );
  const query = useQuery({
    queryKey: qk.invoices(params),
    queryFn: () => paymentsApi.listInvoices(params),
    placeholderData: keepPreviousData,
  });

  const [paying, setPaying] = useState<Invoice | null>(null);
  const items = query.data?.items ?? [];

  // Resolve student names for the rows on this page (scales past one list page).
  const studentMap = useEntityMap(
    items.map((inv) => inv.student_id),
    studentsApi.get,
    "student",
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="sm:w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("billing.allStatuses", "All statuses")}</SelectItem>
            <SelectItem value="sent">{t("billing.statusSent", "Sent")}</SelectItem>
            <SelectItem value="paid">{t("billing.statusPaid", "Paid")}</SelectItem>
            <SelectItem value="overdue">{t("billing.statusOverdue", "Overdue")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {query.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Receipt}
          title={t("billing.invoicesEmpty.title", "No invoices")}
          description={t("billing.invoicesEmpty.desc", "Generate invoices from a fee schedule to see them here.")}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((inv) => (
            <Card key={inv.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium">
                      {studentMap.get(inv.student_id)?.full_name ??
                        t("billing.student", "Student")}
                    </p>
                    <p className="text-xl font-bold tabular-nums">{formatCurrency(inv.amount)}</p>
                  </div>
                  <Badge variant={INVOICE_VARIANT[inv.status]} className="capitalize">
                    {inv.status}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {t("billing.due", "Due")}: {formatDate(inv.due_date)}
                </p>
                {inv.status === "sent" || inv.status === "overdue" ? (
                  <Button size="sm" variant="outline" onClick={() => setPaying(inv)}>
                    {t("billing.recordPayment", "Record payment")}
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!query.isLoading && !query.isError && items.length > 0 ? (
        <Pagination
          total={query.data?.total ?? 0}
          limit={limit}
          offset={offset}
          onOffsetChange={setOffset}
          isFetching={query.isFetching}
        />
      ) : null}

      {paying ? (
        <RecordPaymentDialog invoice={paying} onClose={() => setPaying(null)} />
      ) : null}
    </div>
  );
}

function RecordPaymentDialog({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const { t } = useTranslation("admin");
  const [receipt, setReceipt] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      paymentsApi.recordPayment(invoice.id, { receipt_no: receipt.trim() || undefined }),
    onSuccess: () => {
      toast.success(t("billing.paymentRecorded", "Payment recorded"));
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      onClose();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  return (
    <Dialog open onOpenChange={(o) => !o && !mut.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("billing.recordPayment", "Record payment")}</DialogTitle>
          <DialogDescription>
            {t("billing.recordPaymentDesc", "Mark this invoice as paid (offline/manual payment).")}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-lg bg-muted/40 p-3 text-sm">
            {t("billing.amountDue", "Amount due")}:{" "}
            <span className="font-bold">{formatCurrency(invoice.amount)}</span>
          </div>
          <Field label={t("billing.receiptNo", "Receipt number")} htmlFor="receipt">
            <Input
              id="receipt"
              value={receipt}
              onChange={(e) => setReceipt(e.target.value)}
              placeholder={t("billing.receiptPlaceholder", "Optional reference")}
              maxLength={40}
            />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mut.isPending}>
            {t("common.cancel", "Cancel")}
          </Button>
          <Button variant="success" onClick={() => mut.mutate()} disabled={mut.isPending}>
            {mut.isPending ? <Spinner /> : null}
            {t("billing.markPaid", "Mark paid")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
