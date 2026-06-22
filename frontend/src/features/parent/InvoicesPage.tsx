import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Receipt } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { BadgeProps } from "@/components/ui/badge";
import { paymentsApi, studentsApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/format";
import { qk } from "@/lib/query";
import type { InvoiceStatus } from "@/lib/api/types";

const INVOICE_VARIANT: Record<InvoiceStatus, BadgeProps["variant"]> = {
  draft: "muted",
  sent: "warning",
  paid: "success",
  overdue: "destructive",
  cancelled: "muted",
};

export function InvoicesPage() {
  const { t } = useTranslation("parent");

  const query = useQuery({
    queryKey: qk.invoices({ scope: "mine" }),
    queryFn: () => paymentsApi.listInvoices({ limit: 100 }),
  });
  const studentsQuery = useQuery({
    queryKey: qk.students({ scope: "mine" }),
    queryFn: () => studentsApi.list({ limit: 100 }),
    staleTime: 60_000,
  });
  const studentName = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of studentsQuery.data?.items ?? []) m.set(s.id, s.full_name);
    return m;
  }, [studentsQuery.data]);

  const items = query.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("invoices.title", "Invoices")}
        description={t("invoices.subtitle", "Your transport fees. Pay at school; the office records your payment.")}
      />

      {query.isLoading ? (
        <CardListSkeleton rows={3} />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Receipt}
          title={t("invoices.empty.title", "No invoices")}
          description={t("invoices.empty.desc", "Transport fee invoices from your school will appear here.")}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((inv) => (
            <Card key={inv.id}>
              <CardContent className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-muted-foreground">
                      {studentName.get(inv.student_id) ?? t("invoices.student", "Student")}
                    </p>
                    <p className="text-2xl font-bold tabular-nums">{formatCurrency(inv.amount)}</p>
                  </div>
                  <Badge variant={INVOICE_VARIANT[inv.status]} className="capitalize">
                    {inv.status}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {inv.status === "paid"
                    ? `${t("invoices.paidOn", "Paid")} ${formatDate(inv.paid_at)}`
                    : `${t("invoices.due", "Due")} ${formatDate(inv.due_date)}`}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
