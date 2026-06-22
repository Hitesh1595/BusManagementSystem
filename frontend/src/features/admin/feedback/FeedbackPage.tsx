import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { MessageSquare } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { RatingStars } from "@/components/common/RatingStars";
import { Field } from "@/components/common/Field";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { driversApi, feedbackApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";
import { timeAgo } from "@/lib/format";
import { qk, queryClient } from "@/lib/query";
import { usePagination } from "@/lib/hooks/usePagination";
import { useEntityMap } from "@/lib/hooks/useEntityMap";
import type { TripFeedback } from "@/lib/api/types";

type Tab = "flagged" | "all";

export function FeedbackPage() {
  const { t } = useTranslation("admin");
  const [tab, setTab] = useState<Tab>("flagged");

  const { limit, offset, setOffset } = usePagination(24, tab);
  const params = useMemo(
    () => ({ flagged: tab === "flagged" ? true : undefined, limit, offset }),
    [tab, limit, offset],
  );
  const query = useQuery({
    queryKey: qk.feedback(params),
    queryFn: () => feedbackApi.list(params),
    placeholderData: keepPreviousData,
  });

  const [reviewing, setReviewing] = useState<TripFeedback | null>(null);
  const items = query.data?.items ?? [];

  // Resolve driver names only for the rows on this page (not a capped list scan).
  const driverMap = useEntityMap(
    items.map((f) => f.driver_id),
    driversApi.get,
    "driver",
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("feedback.title", "Trip feedback")}
        description={t("feedback.subtitle", "Ratings from parents. Low ratings are flagged for review.")}
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="flagged">{t("feedback.tab.flagged", "Flagged")}</TabsTrigger>
          <TabsTrigger value="all">{t("feedback.tab.all", "All")}</TabsTrigger>
        </TabsList>
      </Tabs>

      {query.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title={t("feedback.empty.title", "No feedback here")}
          description={t("feedback.empty.desc", "Parent ratings for completed trips will show up here.")}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((f) => (
            <Card key={f.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <RatingStars value={f.rating} size="sm" />
                  <div className="flex gap-1.5">
                    {f.is_flagged ? (
                      <Badge variant="destructive">{t("feedback.flagged", "Flagged")}</Badge>
                    ) : null}
                    {f.admin_reviewed ? (
                      <Badge variant="success">{t("feedback.reviewed", "Reviewed")}</Badge>
                    ) : null}
                  </div>
                </div>
                {f.comment ? (
                  <p className="text-sm">{f.comment}</p>
                ) : (
                  <p className="text-sm italic text-muted-foreground">
                    {t("feedback.noComment", "No comment")}
                  </p>
                )}
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    {t("feedback.driver", "Driver")}:{" "}
                    {driverMap.get(f.driver_id)?.full_name ?? "—"}
                  </span>
                  <span>{timeAgo(f.created_at)}</span>
                </div>
                {f.admin_notes ? (
                  <p className="rounded-lg bg-muted/40 p-2 text-xs text-muted-foreground">
                    {f.admin_notes}
                  </p>
                ) : null}
                <Button size="sm" variant="outline" onClick={() => setReviewing(f)}>
                  {f.admin_reviewed
                    ? t("feedback.editReview", "Edit review")
                    : t("feedback.review", "Review")}
                </Button>
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

      {reviewing ? (
        <ReviewDialog feedback={reviewing} onClose={() => setReviewing(null)} />
      ) : null}
    </div>
  );
}

function ReviewDialog({
  feedback,
  onClose,
}: {
  feedback: TripFeedback;
  onClose: () => void;
}) {
  const { t } = useTranslation("admin");
  const [notes, setNotes] = useState(feedback.admin_notes ?? "");
  const [flagged, setFlagged] = useState(feedback.is_flagged);

  const mut = useMutation({
    mutationFn: () =>
      feedbackApi.review(feedback.id, {
        admin_notes: notes.trim() || undefined,
        is_flagged: flagged,
      }),
    onSuccess: () => {
      toast.success(t("feedback.reviewSaved", "Feedback reviewed"));
      void queryClient.invalidateQueries({ queryKey: ["feedback"] });
      onClose();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  return (
    <Dialog open onOpenChange={(o) => !o && !mut.isPending && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("feedback.reviewTitle", "Review feedback")}</DialogTitle>
          <DialogDescription>
            {t("feedback.reviewDesc", "Add a note and mark this feedback as reviewed.")}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <RatingStars value={feedback.rating} />
          {feedback.comment ? <p className="text-sm">{feedback.comment}</p> : null}
          <Field label={t("feedback.notes", "Admin notes")}>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder={t("feedback.notesPlaceholder", "What action did you take?")}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={flagged}
              onChange={(e) => setFlagged(e.target.checked)}
              className="size-4"
            />
            {t("feedback.keepFlagged", "Keep flagged")}
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mut.isPending}>
            {t("common.cancel", "Cancel")}
          </Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>
            {mut.isPending ? <Spinner /> : null}
            {t("feedback.markReviewed", "Mark reviewed")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
