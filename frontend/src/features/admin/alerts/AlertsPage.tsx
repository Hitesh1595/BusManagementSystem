import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { AlertTriangle, Bell, BellOff, Check, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState, CardListSkeleton } from "@/components/common/States";
import { AlertSeverityBadge } from "@/components/common/StatusBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { formatDateTime, timeAgo } from "@/lib/format";
import { getErrorMessage } from "@/lib/api/client";
import { qk, queryClient } from "@/lib/query";
import { alertsApi } from "@/lib/api/alerts";
import type { Alert, AlertSeverity, AlertType } from "@/lib/api/types";

const ALERT_TYPES: AlertType[] = [
  "child_not_boarded",
  "child_not_dropped",
  "driver_no_show",
  "sos",
  "route_deviation",
  "incident",
  "insurance_expiry",
  "driver_behavior_pattern",
];

const SEVERITIES: AlertSeverity[] = ["critical", "high", "medium", "low"];

type ResolvedFilter = "unresolved" | "resolved";

/** Tiny WebAudio beep for new critical alerts; only fires after user interaction. */
function useCriticalBeep() {
  const ctxRef = useRef<AudioContext | null>(null);
  const armedRef = useRef(false);

  useEffect(() => {
    const arm = () => {
      armedRef.current = true;
    };
    window.addEventListener("pointerdown", arm, { once: true });
    window.addEventListener("keydown", arm, { once: true });
    return () => {
      window.removeEventListener("pointerdown", arm);
      window.removeEventListener("keydown", arm);
    };
  }, []);

  return useCallback(() => {
    if (!armedRef.current) return;
    try {
      type WindowWithWebkit = Window & { webkitAudioContext?: typeof AudioContext };
      const Ctor = window.AudioContext ?? (window as WindowWithWebkit).webkitAudioContext;
      if (!Ctor) return;
      if (!ctxRef.current) ctxRef.current = new Ctor();
      const ctx = ctxRef.current;
      void ctx.resume();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.36);
    } catch {
      /* audio not available */
    }
  }, []);
}

export function AlertsPage() {
  const { t } = useTranslation("admin");
  const [resolved, setResolved] = useState<ResolvedFilter>("unresolved");
  const [type, setType] = useState<AlertType | "all">("all");
  const [severity, setSeverity] = useState<AlertSeverity | "all">("all");
  const [soundOn, setSoundOn] = useState(true);

  const beep = useCriticalBeep();

  const params = useMemo(
    () => ({
      resolved: resolved === "resolved",
      type: type === "all" ? undefined : type,
      severity: severity === "all" ? undefined : severity,
      limit: 100,
    }),
    [resolved, type, severity],
  );

  const query = useQuery({
    queryKey: qk.alerts(params),
    queryFn: () => alertsApi.list(params),
    refetchInterval: 20_000,
  });

  // Detect newly-arrived critical alerts and beep.
  const seenCriticalRef = useRef<Set<string>>(new Set());
  const primedRef = useRef(false);
  useEffect(() => {
    const items = query.data?.items ?? [];
    const criticalIds = items.filter((a) => a.severity === "critical" && !a.resolved_at).map((a) => a.id);
    if (!primedRef.current) {
      // First load: don't beep for the backlog, just record it.
      seenCriticalRef.current = new Set(criticalIds);
      primedRef.current = true;
      return;
    }
    const fresh = criticalIds.filter((id) => !seenCriticalRef.current.has(id));
    if (fresh.length > 0 && soundOn) beep();
    for (const id of criticalIds) seenCriticalRef.current.add(id);
  }, [query.data, soundOn, beep]);

  const [busyId, setBusyId] = useState<string | null>(null);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    void queryClient.invalidateQueries({ queryKey: qk.activeTrips });
  };

  const acknowledge = async (alert: Alert) => {
    setBusyId(alert.id);
    try {
      await alertsApi.acknowledge(alert.id);
      toast.success(t("alerts.acked", "Alert acknowledged"));
      invalidate();
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  };

  const resolve = async (alert: Alert) => {
    setBusyId(alert.id);
    try {
      const res = await alertsApi.resolve(alert.id);
      if (res.trip_completed) toast.success(t("alerts.tripCompleted", "Trip completed"));
      else toast.success(t("alerts.resolved", "Alert resolved"));
      invalidate();
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  };

  const items = query.data?.items ?? [];
  // Critical pinned first, then by recency.
  const sorted = useMemo(
    () =>
      [...items].sort((a, b) => {
        if (a.severity === "critical" && b.severity !== "critical") return -1;
        if (b.severity === "critical" && a.severity !== "critical") return 1;
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }),
    [items],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("alerts.title", "Safety alerts")}
        description={t("alerts.subtitle", "Acknowledge and resolve incidents across your fleet.")}
        actions={
          <Button
            variant={soundOn ? "outline" : "ghost"}
            size="sm"
            onClick={() => setSoundOn((s) => !s)}
            title={t("alerts.soundToggle", "Toggle critical-alert sound")}
          >
            {soundOn ? <Bell className="size-4" /> : <BellOff className="size-4" />}
            {soundOn ? t("alerts.soundOn", "Sound on") : t("alerts.soundOff", "Sound off")}
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={resolved} onValueChange={(v) => setResolved(v as ResolvedFilter)}>
          <TabsList>
            <TabsTrigger value="unresolved">{t("alerts.tab.open", "Open")}</TabsTrigger>
            <TabsTrigger value="resolved">{t("alerts.tab.resolved", "Resolved")}</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex flex-wrap gap-2">
          <Select value={severity} onValueChange={(v) => setSeverity(v as AlertSeverity | "all")}>
            <SelectTrigger className="w-[10rem]">
              <SelectValue placeholder={t("alerts.severity", "Severity")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("alerts.allSeverities", "All severities")}</SelectItem>
              {SEVERITIES.map((s) => (
                <SelectItem key={s} value={s} className="capitalize">
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={type} onValueChange={(v) => setType(v as AlertType | "all")}>
            <SelectTrigger className="w-[12rem]">
              <SelectValue placeholder={t("alerts.type", "Type")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("alerts.allTypes", "All types")}</SelectItem>
              {ALERT_TYPES.map((tp) => (
                <SelectItem key={tp} value={tp}>
                  {t(`alerts.type.${tp}`, tp.replace(/_/g, " "))}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {query.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : query.isError ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : sorted.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title={
            resolved === "unresolved"
              ? t("alerts.empty.open", "All clear")
              : t("alerts.empty.resolved", "No resolved alerts")
          }
          description={
            resolved === "unresolved"
              ? t("alerts.empty.openDesc", "No open alerts right now. We'll surface new ones here instantly.")
              : t("alerts.empty.resolvedDesc", "Resolved alerts will be listed here.")
          }
        />
      ) : (
        <div className="space-y-3">
          {sorted.map((alert) => (
            <AlertRow
              key={alert.id}
              alert={alert}
              busy={busyId === alert.id}
              onAcknowledge={() => acknowledge(alert)}
              onResolve={() => resolve(alert)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AlertRow({
  alert,
  busy,
  onAcknowledge,
  onResolve,
}: {
  alert: Alert;
  busy: boolean;
  onAcknowledge: () => void;
  onResolve: () => void;
}) {
  const { t } = useTranslation("admin");
  const isCritical = alert.severity === "critical";
  const isResolved = !!alert.resolved_at;
  const isAcked = !!alert.acknowledged_at;

  return (
    <Card
      className={cn(
        isCritical && !isResolved && "border-destructive bg-destructive/5 shadow-sm",
      )}
    >
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3">
          <span
            className={cn(
              "mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-full",
              isCritical ? "bg-destructive/15 text-destructive" : "bg-secondary text-secondary-foreground",
            )}
          >
            <AlertTriangle className="size-4" />
          </span>
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <AlertSeverityBadge severity={alert.severity} />
              <span className="truncate font-semibold">{alert.title}</span>
              {isAcked && !isResolved ? (
                <span className="text-xs font-medium text-muted-foreground">
                  {t("alerts.ackedTag", "Acknowledged")}
                </span>
              ) : null}
            </div>
            {alert.description ? (
              <p className="text-sm text-muted-foreground">{alert.description}</p>
            ) : null}
            <p className="text-xs text-muted-foreground" title={formatDateTime(alert.created_at)}>
              {formatDateTime(alert.created_at)} · {timeAgo(alert.created_at)}
            </p>
          </div>
        </div>

        {!isResolved ? (
          <div className="flex shrink-0 gap-2">
            {!isAcked ? (
              <Button variant="outline" size="sm" onClick={onAcknowledge} disabled={busy}>
                <Check className="size-4" />
                {t("alerts.acknowledge", "Acknowledge")}
              </Button>
            ) : null}
            <Button
              variant={isCritical ? "destructive" : "default"}
              size="sm"
              onClick={onResolve}
              disabled={busy}
            >
              <ShieldCheck className="size-4" />
              {t("alerts.resolve", "Resolve")}
            </Button>
          </div>
        ) : (
          <span className="shrink-0 text-xs font-medium text-success">
            {t("alerts.resolvedAt", "Resolved {{when}}", { when: timeAgo(alert.resolved_at) })}
          </span>
        )}
      </CardContent>
    </Card>
  );
}
