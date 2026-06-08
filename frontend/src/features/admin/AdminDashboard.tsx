import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Bus,
  Inbox,
  Map as MapIcon,
  Rocket,
  Route as RouteIcon,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { TripStatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";
import { alertsApi, transportRequestsApi, tripsApi, vehiclesApi } from "@/lib/api";
import { routesApi } from "@/lib/api/routes";
import { qk } from "@/lib/query";

function StatCard({
  to,
  icon: Icon,
  label,
  value,
  loading,
  accent,
}: {
  to: string;
  icon: LucideIcon;
  label: string;
  value: number | undefined;
  loading: boolean;
  accent?: "destructive" | "warning" | "default";
}) {
  return (
    <Link to={to} className="group">
      <Card className="transition-colors hover:border-primary/40 hover:bg-accent/40">
        <CardContent className="flex items-center gap-4 p-5">
          <span
            className={cn(
              "inline-flex size-11 shrink-0 items-center justify-center rounded-xl",
              accent === "destructive" && value
                ? "bg-destructive/15 text-destructive"
                : accent === "warning" && value
                  ? "bg-warning/15 text-warning-foreground"
                  : "bg-secondary text-secondary-foreground",
            )}
          >
            <Icon className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">{label}</p>
            {loading ? (
              <Skeleton className="mt-1 h-7 w-10" />
            ) : (
              <p className="text-2xl font-bold tabular-nums">{value ?? 0}</p>
            )}
          </div>
          <ArrowRight className="ml-auto size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        </CardContent>
      </Card>
    </Link>
  );
}

export function AdminDashboard() {
  const { t } = useTranslation("admin");

  const activeTrips = useQuery({
    queryKey: qk.activeTrips,
    queryFn: () => tripsApi.listActive(),
  });

  const openAlerts = useQuery({
    queryKey: qk.alerts({ resolved: false }),
    queryFn: () => alertsApi.list({ resolved: false }),
  });

  const pendingRequests = useQuery({
    queryKey: qk.transportRequests({ status: "pending" }),
    queryFn: () => transportRequestsApi.list({ status: "pending" }),
  });

  const routes = useQuery({
    queryKey: qk.routes({ limit: 1 }),
    queryFn: () => routesApi.list({ limit: 1 }),
  });

  const vehicles = useQuery({
    queryKey: qk.vehicles({ limit: 1 }),
    queryFn: () => vehiclesApi.list({ limit: 1 }),
  });

  const setupIncomplete =
    routes.isSuccess &&
    vehicles.isSuccess &&
    (routes.data.total === 0 || vehicles.data.total === 0);

  const trips = activeTrips.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("dashboard.title", "Dashboard")}
        description={t("dashboard.subtitle", "Your fleet at a glance")}
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/fleet">
              <MapIcon className="size-4" />
              {t("dashboard.liveMap", "Live map")}
            </Link>
          </Button>
        }
      />

      {setupIncomplete ? (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
                <Rocket className="size-5" />
              </span>
              <div>
                <p className="font-semibold">
                  {t("dashboard.finishSetupTitle", "Finish setting up your school")}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t(
                    "dashboard.finishSetupBody",
                    "Add a vehicle and create your first route so buses can start running.",
                  )}
                </p>
              </div>
            </div>
            <Button asChild className="shrink-0">
              <Link to="/admin/setup">
                {t("dashboard.finishSetupCta", "Finish setup")}
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          to="/admin/fleet"
          icon={Bus}
          label={t("dashboard.activeTrips", "Active trips")}
          value={activeTrips.data?.length}
          loading={activeTrips.isLoading}
          accent="default"
        />
        <StatCard
          to="/admin/alerts"
          icon={AlertTriangle}
          label={t("dashboard.openAlerts", "Open alerts")}
          value={openAlerts.data?.total}
          loading={openAlerts.isLoading}
          accent="destructive"
        />
        <StatCard
          to="/admin/requests"
          icon={Inbox}
          label={t("dashboard.pendingRequests", "Pending requests")}
          value={pendingRequests.data?.total}
          loading={pendingRequests.isLoading}
          accent="warning"
        />
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>{t("dashboard.todayTitle", "Today's trips")}</CardTitle>
            <CardDescription>
              {t("dashboard.todaySubtitle", "Trips currently running")}
            </CardDescription>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link to="/admin/routes">
              <RouteIcon className="size-4" />
              {t("dashboard.manageRoutes", "Routes")}
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {activeTrips.isLoading ? (
            <CardListSkeleton rows={2} />
          ) : activeTrips.isError ? (
            <ErrorState onRetry={() => activeTrips.refetch()} />
          ) : trips.length === 0 ? (
            <EmptyState
              icon={Bus}
              title={t("dashboard.noActive", "No active trips right now")}
              description={t(
                "dashboard.noActiveBody",
                "Trips will appear here once drivers start their routes.",
              )}
            />
          ) : (
            <ul className="divide-y divide-border">
              {trips.map((trip) => (
                <li key={trip.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex size-9 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                      <Bus className="size-4" />
                    </span>
                    <div>
                      <p className="text-sm font-medium">
                        {t("dashboard.tripSlot", "{{slot}} trip", { slot: trip.slot })}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {trip.started_at
                          ? t("dashboard.startedAt", "Started {{time}}", {
                              time: formatTime(trip.started_at),
                            })
                          : t("dashboard.notStarted", "Not started yet")}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <TripStatusBadge status={trip.status} />
                    <Button asChild variant="ghost" size="icon">
                      <Link to="/admin/fleet" aria-label={t("dashboard.track", "Track")}>
                        <ArrowRight className="size-4" />
                      </Link>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
