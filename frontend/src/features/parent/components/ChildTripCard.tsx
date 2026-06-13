import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Bus, GraduationCap, MapPin, Navigation, Star } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RateTripDialog } from "./RateTripDialog";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Spinner } from "@/components/ui/spinner";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TripStatusBadge } from "@/components/common/StatusBadge";
import { tripsApi } from "@/lib/api/trips";
import { getErrorMessage } from "@/lib/api/client";
import { qk } from "@/lib/query";
import { initials } from "@/lib/utils";
import { formatTime } from "@/lib/format";
import type { Student, TransportRequest, Trip } from "@/lib/api/types";

const TODAY = (() => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
})();

interface ChildTripCardProps {
  student: Student;
  /** Assigned transport requests for this parent (used to resolve the route). */
  assignedRequests: TransportRequest[];
}

/** Today's trip + mark-absent control for a single child. */
export function ChildTripCard({ student, assignedRequests }: ChildTripCardProps) {
  const { t } = useTranslation("parent");
  const queryClient = useQueryClient();

  const assigned = assignedRequests.find((r) => r.student_id === student.id);
  const routeId = assigned?.assigned_route_id ?? null;

  const tripsQuery = useQuery({
    queryKey: qk.trips({ route_id: routeId, date: TODAY }),
    queryFn: () => tripsApi.list({ route_id: routeId!, date: TODAY }),
    enabled: !!routeId,
  });

  const [rateOpen, setRateOpen] = useState(false);
  const [rated, setRated] = useState(false);

  // Prefer an in_progress trip, else scheduled, else a completed one (to rate).
  const trips = tripsQuery.data?.items ?? [];
  const trip: Trip | undefined =
    trips.find((tr) => tr.status === "in_progress") ??
    trips.find((tr) => tr.status === "scheduled") ??
    trips.find((tr) => tr.status === "completed");

  const markAbsent = useMutation({
    mutationFn: (absent: boolean) =>
      absent
        ? tripsApi.markAbsent(trip!.id, student.id)
        : tripsApi.cancelAbsent(trip!.id, student.id),
    onSuccess: (res) => {
      toast.success(
        res.status === "absent_parent_marked"
          ? t("trip.markedAbsent", "Marked absent for today")
          : t("trip.absenceCancelled", "Absence cancelled"),
      );
      if (trip) {
        void queryClient.invalidateQueries({ queryKey: qk.tripAbsences(trip.id) });
      }
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const absenceQuery = useQuery({
    queryKey: qk.tripAbsences(trip?.id ?? "none"),
    queryFn: () => tripsApi.absences(trip!.id),
    enabled: !!trip && trip.status === "scheduled",
  });
  const isAbsent = !!absenceQuery.data?.some((a) => a.student_id === student.id);

  const canTrack = trip && (trip.status === "in_progress" || trip.status === "scheduled");

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3">
          <Avatar>
            <AvatarFallback>{initials(student.full_name)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <CardTitle className="truncate text-base">{student.full_name}</CardTitle>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
              <GraduationCap className="size-3.5" />
              {student.grade
                ? t("child.gradeSection", "Grade {{grade}}{{section}}", {
                    grade: student.grade,
                    section: student.section ? ` · ${student.section}` : "",
                  })
                : t("child.noGrade", "Grade not set")}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {!routeId ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/40 p-4 text-center">
            <p className="text-sm text-muted-foreground">
              {t(
                "child.noRoute",
                "No bus route assigned yet. Request transport to get a pickup stop.",
              )}
            </p>
            <Button asChild size="sm" className="mt-3">
              <Link to="/parent/request/new">
                <MapPin className="size-4" />
                {t("child.requestTransport", "Request transport")}
              </Link>
            </Button>
          </div>
        ) : tripsQuery.isLoading ? (
          <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
            <Spinner className="size-4" />
            {t("trip.loading", "Checking today's trip…")}
          </div>
        ) : tripsQuery.isError ? (
          <div className="flex items-center justify-between gap-2 rounded-lg border border-border p-3">
            <p className="text-sm text-muted-foreground">
              {t("trip.loadError", "Couldn't load today's trip.")}
            </p>
            <Button size="sm" variant="outline" onClick={() => void tripsQuery.refetch()}>
              {t("common.retry", "Retry")}
            </Button>
          </div>
        ) : !trip ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/40 p-3 text-center text-sm text-muted-foreground">
            {t("trip.none", "No trip scheduled for today.")}
          </div>
        ) : (
          <div className="space-y-3 rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-medium">
                <Bus className="size-4 text-primary" />
                {t("trip.today", "Today's trip")}
              </span>
              <TripStatusBadge status={trip.status} />
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="capitalize">
                {trip.slot === "morning"
                  ? t("trip.morning", "Morning")
                  : t("trip.evening", "Evening")}
              </Badge>
              <span>
                {t("trip.departs", "Departs")} {formatTime(trip.scheduled_departure_at)}
              </span>
            </div>

            {trip.status === "completed" ? (
              rated ? (
                <p className="rounded-lg bg-muted/40 px-3 py-2 text-center text-sm text-muted-foreground">
                  {t("trip.rateThanks", "Thanks for rating this trip.")}
                </p>
              ) : (
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => setRateOpen(true)}
                >
                  <Star className="size-4" />
                  {t("trip.rate", "Rate this trip")}
                </Button>
              )
            ) : (
              <>
                <Button
                  asChild={!!canTrack}
                  size="lg"
                  className="w-full"
                  disabled={!canTrack}
                  variant={trip.status === "in_progress" ? "default" : "secondary"}
                >
                  {canTrack ? (
                    <Link to={`/parent/track/${trip.id}`}>
                      <Navigation className="size-4" />
                      {trip.status === "in_progress"
                        ? t("trip.trackLive", "Track live")
                        : t("trip.viewTracking", "View tracking")}
                    </Link>
                  ) : (
                    <span>{t("trip.trackUnavailable", "Tracking unavailable")}</span>
                  )}
                </Button>

                {trip.status === "scheduled" ? (
                  <div className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {t("trip.absentToggle", "Mark absent today")}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t("trip.absentHint", "Tell the driver your child won't board today.")}
                      </p>
                    </div>
                    {markAbsent.isPending || absenceQuery.isLoading ? (
                      <Spinner className="size-4" />
                    ) : (
                      <Switch
                        checked={isAbsent}
                        onCheckedChange={(v) => markAbsent.mutate(v)}
                        aria-label={t("trip.absentToggle", "Mark absent today")}
                      />
                    )}
                  </div>
                ) : null}
              </>
            )}
          </div>
        )}
      </CardContent>
      {trip ? (
        <RateTripDialog
          open={rateOpen}
          onOpenChange={setRateOpen}
          tripId={trip.id}
          onRated={() => setRated(true)}
        />
      ) : null}
    </Card>
  );
}
