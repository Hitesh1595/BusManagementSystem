import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bell, CheckCheck } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState, CardListSkeleton } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { notificationsApi } from "@/lib/api/notifications";
import { getErrorMessage } from "@/lib/api/client";
import { qk } from "@/lib/query";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/format";
import type { Notification } from "@/lib/api/types";

const PAGE_SIZE = 30;

export function NotificationsPage() {
  const { t } = useTranslation("parent");
  const queryClient = useQueryClient();
  const [page] = useState(1);

  const query = useQuery({
    queryKey: qk.notifications({ page, page_size: PAGE_SIZE }),
    queryFn: () => notificationsApi.list({ page, page_size: PAGE_SIZE }),
  });

  const invalidate = () =>
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: invalidate,
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: (res) => {
      toast.success(
        t("notifications.allReadDone", "{{count}} marked read", {
          count: res.marked_count,
        }),
      );
      invalidate();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const items = query.data?.notifications ?? [];
  const hasUnread = items.some((n) => !n.is_read);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("notifications.title", "Notifications")}
        description={t(
          "notifications.subtitle",
          "Trip updates, attendance and safety alerts for your children.",
        )}
        actions={
          <Button
            variant="outline"
            onClick={() => markAllRead.mutate()}
            disabled={!hasUnread || markAllRead.isPending}
          >
            {markAllRead.isPending ? (
              <Spinner className="size-4" />
            ) : (
              <CheckCheck className="size-4" />
            )}
            {t("notifications.markAll", "Mark all read")}
          </Button>
        }
      />

      {query.isLoading ? (
        <CardListSkeleton rows={5} />
      ) : query.isError ? (
        <ErrorState
          message={t("notifications.loadError", "Couldn't load notifications.")}
          onRetry={() => void query.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title={t("notifications.emptyTitle", "You're all caught up")}
          description={t(
            "notifications.emptyDescription",
            "Updates about your children's trips will show up here.",
          )}
        />
      ) : (
        <div className="space-y-2">
          {items.map((n: Notification) => (
            <button
              key={n.id}
              type="button"
              onClick={() => {
                if (!n.is_read) markRead.mutate(n.id);
              }}
              className={cn(
                "flex w-full items-start gap-3 rounded-xl border border-border p-4 text-left transition-colors",
                n.is_read
                  ? "bg-card hover:bg-muted/40"
                  : "bg-primary/5 hover:bg-primary/10",
              )}
            >
              <span
                className={cn(
                  "mt-1.5 size-2 shrink-0 rounded-full",
                  n.is_read ? "bg-transparent" : "bg-primary",
                )}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p
                    className={cn(
                      "text-sm",
                      n.is_read ? "font-medium" : "font-semibold",
                    )}
                  >
                    {n.title}
                  </p>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {timeAgo(n.created_at)}
                  </span>
                </div>
                {n.body ? (
                  <p className="mt-0.5 text-sm text-muted-foreground">{n.body}</p>
                ) : null}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
