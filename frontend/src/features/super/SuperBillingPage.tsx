import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { Plus, Receipt, TrendingUp, Wallet } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { Field } from "@/components/common/Field";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { schoolsApi, superAdminApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/format";
import { qk, queryClient } from "@/lib/query";
import { usePagination } from "@/lib/hooks/usePagination";
import type { InvoiceStatus, PlatformInvoice } from "@/lib/api/types";

const STATUS_VARIANT: Record<InvoiceStatus, BadgeProps["variant"]> = {
  draft: "muted",
  sent: "warning",
  paid: "success",
  overdue: "destructive",
  cancelled: "muted",
};

function currentPeriod(): string {
  return new Date().toISOString().slice(0, 7); // YYYY-MM
}

export function SuperBillingPage() {
  const [generating, setGenerating] = useState(false);
  const [paying, setPaying] = useState<PlatformInvoice | null>(null);

  const summary = useQuery({
    queryKey: qk.platformBillingSummary(),
    queryFn: () => superAdminApi.platformBillingSummary(),
  });
  const { limit, offset, setOffset } = usePagination(24);
  const invoices = useQuery({
    queryKey: qk.platformInvoices({ limit, offset }),
    queryFn: () => superAdminApi.listPlatformInvoices({ limit, offset }),
    placeholderData: keepPreviousData,
  });
  const schoolsQuery = useQuery({
    queryKey: qk.schools({ limit: 100 }),
    queryFn: () => schoolsApi.list({ limit: 100 }),
    staleTime: 60_000,
  });
  const schoolName = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of schoolsQuery.data?.items ?? []) m.set(s.id, s.name);
    return m;
  }, [schoolsQuery.data]);

  const s = summary.data;
  const items = invoices.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform billing"
        description="Charge each school a monthly platform fee, and track what's collected."
        actions={
          <Button onClick={() => setGenerating(true)}>
            <Plus className="size-4" />
            Generate invoices
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard icon={Wallet} label="Billed" value={formatCurrency(s?.billed)} loading={summary.isLoading} />
        <StatCard icon={TrendingUp} label="Collected" value={formatCurrency(s?.collected)} loading={summary.isLoading} />
        <StatCard
          icon={Receipt}
          label="Outstanding"
          value={formatCurrency(s?.outstanding)}
          loading={summary.isLoading}
          accent="warning"
        />
      </div>

      {invoices.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : invoices.isError ? (
        <ErrorState onRetry={() => invoices.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Receipt}
          title="No platform invoices"
          description="Generate this month's invoices to bill your schools."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((inv) => (
            <Card key={inv.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">
                      {schoolName.get(inv.school_id) ?? "School"}
                    </p>
                    <p className="text-2xl font-bold tabular-nums">{formatCurrency(inv.amount)}</p>
                  </div>
                  <Badge variant={STATUS_VARIANT[inv.status]} className="capitalize">
                    {inv.status}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{inv.period}</span>
                  <span>
                    {inv.status === "paid"
                      ? `Paid ${formatDate(inv.paid_at)}`
                      : `Due ${formatDate(inv.due_date)}`}
                  </span>
                </div>
                {inv.status === "sent" || inv.status === "overdue" ? (
                  <Button size="sm" variant="outline" onClick={() => setPaying(inv)}>
                    Record payment
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!invoices.isLoading && !invoices.isError && items.length > 0 ? (
        <Pagination
          total={invoices.data?.total ?? 0}
          limit={limit}
          offset={offset}
          onOffsetChange={setOffset}
          isFetching={invoices.isFetching}
        />
      ) : null}

      {generating ? <GenerateDialog onClose={() => setGenerating(false)} /> : null}
      {paying ? <RecordDialog invoice={paying} onClose={() => setPaying(null)} /> : null}
    </div>
  );
}

function GenerateDialog({ onClose }: { onClose: () => void }) {
  const [period, setPeriod] = useState(currentPeriod());
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      superAdminApi.generatePlatformInvoices({
        period,
        default_amount: Number(amount),
        due_date: due || undefined,
      }),
    onSuccess: (res) => {
      toast.success(`${res.count} invoice(s) generated for ${res.period}`);
      void queryClient.invalidateQueries({ queryKey: ["platform-invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["platform-billing-summary"] });
      onClose();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const canSubmit = /^\d{4}-\d{2}$/.test(period) && Number(amount) > 0 && !mut.isPending;

  return (
    <Dialog open onOpenChange={(o) => !o && !mut.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate platform invoices</DialogTitle>
          <DialogDescription>
            Bills every active school the amount below for this period (schools already
            billed for the period are skipped).
          </DialogDescription>
        </DialogHeader>
        <form
          id="gen-form"
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) mut.mutate();
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Period (YYYY-MM)" htmlFor="gen-period" required>
              <Input id="gen-period" value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="2026-06" />
            </Field>
            <Field label="Amount per school (₹)" htmlFor="gen-amount" required>
              <Input
                id="gen-amount"
                type="number"
                min="1"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                autoFocus
              />
            </Field>
          </div>
          <Field label="Due date" htmlFor="gen-due">
            <Input id="gen-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mut.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="gen-form" disabled={!canSubmit}>
            {mut.isPending ? <Spinner /> : null}
            Generate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RecordDialog({ invoice, onClose }: { invoice: PlatformInvoice; onClose: () => void }) {
  const [receipt, setReceipt] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      superAdminApi.recordPlatformPayment(invoice.id, { receipt_no: receipt.trim() || undefined }),
    onSuccess: () => {
      toast.success("Payment recorded");
      void queryClient.invalidateQueries({ queryKey: ["platform-invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["platform-billing-summary"] });
      onClose();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  return (
    <Dialog open onOpenChange={(o) => !o && !mut.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record payment</DialogTitle>
          <DialogDescription>Mark this school's platform fee as paid.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-lg bg-muted/40 p-3 text-sm">
            Amount: <span className="font-bold">{formatCurrency(invoice.amount)}</span> · {invoice.period}
          </div>
          <Field label="Receipt number" htmlFor="plt-receipt">
            <Input
              id="plt-receipt"
              value={receipt}
              onChange={(e) => setReceipt(e.target.value)}
              placeholder="Optional reference"
              maxLength={40}
            />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mut.isPending}>
            Cancel
          </Button>
          <Button variant="success" onClick={() => mut.mutate()} disabled={mut.isPending}>
            {mut.isPending ? <Spinner /> : null}
            Mark paid
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
