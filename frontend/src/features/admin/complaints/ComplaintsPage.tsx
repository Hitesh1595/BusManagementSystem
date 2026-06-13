import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Inbox } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { Field } from "@/components/common/Field";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
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
import { complaintsApi, usersApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";
import { timeAgo } from "@/lib/format";
import { qk, queryClient } from "@/lib/query";
import type { Complaint, ComplaintStatus } from "@/lib/api/types";

type Tab = "open" | "in_review" | "resolved" | "all";
const TABS: Tab[] = ["open", "in_review", "resolved", "all"];
const STATUSES: ComplaintStatus[] = ["open", "in_review", "resolved", "closed"];

const STATUS_VARIANT: Record<ComplaintStatus, BadgeProps["variant"]> = {
  open: "warning",
  in_review: "secondary",
  resolved: "success",
  closed: "muted",
};
const PRIORITY_VARIANT: Record<string, BadgeProps["variant"]> = {
  urgent: "destructive",
  high: "warning",
  medium: "secondary",
  low: "muted",
};

export function ComplaintsPage() {
  const { t } = useTranslation("admin");
  const [tab, setTab] = useState<Tab>("open");

  const params = useMemo(
    () => ({ status: tab === "all" ? undefined : tab, limit: 100 }),
    [tab],
  );
  const query = useQuery({
    queryKey: qk.complaints(params),
    queryFn: () => complaintsApi.list(params),
  });

  const usersQuery = useQuery({
    queryKey: qk.users({ limit: 100 }),
    queryFn: () => usersApi.list({ limit: 100 }),
    staleTime: 60_000,
  });
  const userName = useMemo(() => {
    const m = new Map<string, string>();
    for (const u of usersQuery.data?.items ?? []) m.set(u.id, u.full_name);
    return m;
  }, [usersQuery.data]);

  const [managing, setManaging] = useState<Complaint | null>(null);
  const items = query.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("complaints.title", "Complaints")}
        description={t("complaints.subtitle", "Issues raised by parents and drivers. Triage and resolve them.")}
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          {TABS.map((tp) => (
            <TabsTrigger key={tp} value={tp} className="capitalize">
              {t(`complaints.tab.${tp}`, tp.replace("_", " "))}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {query.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={t("complaints.empty.title", "No complaints here")}
          description={t("complaints.empty.desc", "Complaints from parents and drivers will appear in this list.")}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((c) => (
            <Card key={c.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="min-w-0 truncate font-semibold">{c.subject}</p>
                  <Badge variant={STATUS_VARIANT[c.status]} className="capitalize">
                    {c.status.replace("_", " ")}
                  </Badge>
                </div>
                <p className="line-clamp-2 text-sm text-muted-foreground">{c.description}</p>
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <Badge variant="outline" className="capitalize">
                    {c.against_type}
                  </Badge>
                  <Badge variant={PRIORITY_VARIANT[c.priority] ?? "muted"} className="capitalize">
                    {c.priority}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{userName.get(c.submitted_by) ?? t("complaints.someone", "A user")}</span>
                  <span>{timeAgo(c.created_at)}</span>
                </div>
                <Button size="sm" variant="outline" onClick={() => setManaging(c)}>
                  {t("complaints.manage", "Manage")}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {managing ? (
        <ManageDialog complaint={managing} onClose={() => setManaging(null)} />
      ) : null}
    </div>
  );
}

function ManageDialog({
  complaint,
  onClose,
}: {
  complaint: Complaint;
  onClose: () => void;
}) {
  const { t } = useTranslation("admin");
  const [status, setStatus] = useState<ComplaintStatus>(complaint.status);
  const [notes, setNotes] = useState(complaint.resolution_notes ?? "");

  const mut = useMutation({
    mutationFn: async () => {
      if (status === "resolved") {
        return complaintsApi.resolve(complaint.id, notes.trim() || undefined);
      }
      return complaintsApi.setStatus(complaint.id, status);
    },
    onSuccess: () => {
      toast.success(t("complaints.updated", "Complaint updated"));
      void queryClient.invalidateQueries({ queryKey: ["complaints"] });
      onClose();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  return (
    <Dialog open onOpenChange={(o) => !o && !mut.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{complaint.subject}</DialogTitle>
          <DialogDescription className="capitalize">
            {complaint.against_type} · {complaint.priority} priority
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <p className="rounded-lg bg-muted/40 p-3 text-sm">{complaint.description}</p>
          <Field label={t("complaints.status", "Status")}>
            <Select value={status} onValueChange={(v) => setStatus(v as ComplaintStatus)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUSES.map((s) => (
                  <SelectItem key={s} value={s} className="capitalize">
                    {s.replace("_", " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field
            label={t("complaints.resolutionNotes", "Resolution notes")}
            hint={t("complaints.resolutionHint", "Saved when you resolve the complaint.")}
          >
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder={t("complaints.notesPlaceholder", "How was this handled?")}
            />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mut.isPending}>
            {t("common.cancel", "Cancel")}
          </Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>
            {mut.isPending ? <Spinner /> : null}
            {t("complaints.save", "Save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
