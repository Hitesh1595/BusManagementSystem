import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Bus,
  CalendarClock,
  Megaphone,
  PlayCircle,
  Sun,
  Sunset,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { TripStatusBadge } from "@/components/common/StatusBadge";
import { RatingStars } from "@/components/common/RatingStars";
import { ComplaintDialog } from "@/components/common/ComplaintDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { tripsApi } from "@/lib/api/trips";
import { feedbackApi } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatTime } from "@/lib/format";
import { useAuthStore } from "@/stores/auth";
import type { Trip } from "@/lib/api/types";

function todayStr(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function TodayPage() {
  const { t } = useTranslation("driver");
  const me = useAuthStore((s) => s.user);
  const date = todayStr();
  const [reportOpen, setReportOpen] = useState(false);

  const params = { date, limit: 100 };
  const tripsQuery = useQuery({
    queryKey: qk.trips(params),
    queryFn: () => tripsApi.list(params),
  });

  const ratingQuery = useQuery({
    queryKey: qk.driverRating,
    queryFn: () => feedbackApi.myRating(),
    staleTime: 300_000,
  });
  const rating = ratingQuery.data;

  const myTrips = (tripsQuery.data?.items ?? [])
    .filter((tr) => tr.driver_id === me?.id)
    .sort((a, b) =>
      a.scheduled_departure_at.localeCompare(b.scheduled_departure_at),
    );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("today.title", "Today's trips")}
        description={t("today.subtitle", "Your assigned runs for today.")}
        actions={
          <Button variant="outline" onClick={() => setReportOpen(true)}>
            <Megaphone className="size-4" />
            {t("today.reportIssue", "Report an issue")}
          </Button>
        }
      />

      {rating && rating.count > 0 ? (
        <Card>
          <CardContent className="flex items-center justify-between gap-3 p-4">
            <div>
              <p className="text-sm text-muted-foreground">
                {t("today.yourRating", "Your rating")}
              </p>
              <p className="text-2xl font-bold tabular-nums">
                {rating.average?.toFixed(1)}
                <span className="ml-1 text-sm font-normal text-muted-foreground">
                  ({rating.count})
                </span>
              </p>
            </div>
            <RatingStars value={rating.average ?? 0} />
          </CardContent>
        </Card>
      ) : null}

      <ComplaintDialog open={reportOpen} onOpenChange={setReportOpen} />

      {tripsQuery.isLoading ? (
        <CardListSkeleton rows={2} />
      ) : tripsQuery.isError ? (
        <ErrorState onRetry={() => void tripsQuery.refetch()} />
      ) : myTrips.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title={t("today.emptyTitle", "No trip assigned today.")}
          description={t(
            "today.emptyHint",
            "When your school schedules a run for you, it will appear here.",
          )}
        />
      ) : (
        <div className="space-y-4">
          {myTrips.map((trip) => (
            <TripCard key={trip.id} trip={trip} />
          ))}
        </div>
      )}
    </div>
  );
}

function TripCard({ trip }: { trip: Trip }) {
  const { t } = useTranslation("driver");

  // Resolve the route name (and a richer detail) without blocking the card.
  const detailQuery = useQuery({
    queryKey: qk.trip(trip.id),
    queryFn: () => tripsApi.get(trip.id),
    staleTime: 60_000,
  });

  const routeName =
    detailQuery.data?.route?.name ??
    t("today.routeFallback", "Route {{id}}", { id: trip.route_id.slice(0, 8) });

  const isRunning = trip.status === "in_progress";
  const isScheduled = trip.status === "scheduled";
  const SlotIcon = trip.slot === "morning" ? Sun : Sunset;

  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Bus className="size-6" />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-lg font-semibold">{routeName}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="secondary" className="capitalize">
                  <SlotIcon className="size-3.5" />
                  {t(`today.slot.${trip.slot}`, trip.slot)}
                </Badge>
                <span className="inline-flex items-center gap-1">
                  <CalendarClock className="size-3.5" />
                  {formatTime(trip.scheduled_departure_at)}
                </span>
              </div>
            </div>
          </div>
          <TripStatusBadge status={trip.status} />
        </div>

        {isScheduled || isRunning ? (
          <Button asChild size="xl" className="w-full" variant={isRunning ? "success" : "default"}>
            <Link to={`/driver/trip/${trip.id}`}>
              {isRunning ? (
                <>
                  <ArrowRight className="size-5" />
                  {t("today.continue", "Continue trip")}
                </>
              ) : (
                <>
                  <PlayCircle className="size-5" />
                  {t("today.start", "Start trip")}
                </>
              )}
            </Link>
          </Button>
        ) : (
          <Button asChild size="lg" variant="outline" className="w-full">
            <Link to={`/driver/trip/${trip.id}`}>
              {t("today.view", "View trip")}
            </Link>
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
