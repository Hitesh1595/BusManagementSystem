import { Bell, CheckCheck } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { notificationsApi } from "@/lib/api/notifications";
import { qk } from "@/lib/query";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/format";

export function NotificationBell() {
  const { t } = useTranslation("common");
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: qk.notifications({ recent: 15 }),
    queryFn: () => notificationsApi.list({ page: 1, page_size: 15 }),
    refetchInterval: 60_000,
  });

  const items = data?.notifications ?? [];
  const unread = items.filter((n) => !n.is_read).length;

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={t("nav.notifications")}
        >
          <Bell className="size-5" />
          {unread > 0 ? (
            <span className="absolute right-1 top-1 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-4 text-destructive-foreground">
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <span className="text-sm font-semibold">{t("nav.notifications")}</span>
          {unread > 0 ? (
            <button
              type="button"
              onClick={() => markAll.mutate()}
              className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              <CheckCheck className="size-3.5" /> Mark all read
            </button>
          ) : null}
        </div>
        <div className="max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="py-10">
              <Spinner className="mx-auto" />
            </div>
          ) : items.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-muted-foreground">
              {t("empty.default")}
            </p>
          ) : (
            items.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => !n.is_read && markRead.mutate(n.id)}
                className={cn(
                  "flex w-full flex-col items-start gap-0.5 border-b border-border px-4 py-3 text-left transition-colors last:border-0 hover:bg-muted/60",
                  !n.is_read && "bg-secondary/40",
                )}
              >
                <div className="flex w-full items-center gap-2">
                  {!n.is_read ? (
                    <span className="size-2 shrink-0 rounded-full bg-primary" />
                  ) : null}
                  <span className="flex-1 text-sm font-medium leading-snug">
                    {n.title}
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {timeAgo(n.created_at)}
                  </span>
                </div>
                {n.body ? (
                  <span className="text-xs text-muted-foreground">{n.body}</span>
                ) : null}
              </button>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
