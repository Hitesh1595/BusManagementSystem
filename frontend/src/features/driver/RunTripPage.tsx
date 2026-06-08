import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Flag,
  MapPin,
  PlayCircle,
  School,
  ShieldAlert,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { CenteredSpinner, ErrorState } from "@/components/common/States";
import { TripStatusBadge } from "@/components/common/StatusBadge";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { tripsApi } from "@/lib/api/trips";
import { qk, queryClient } from "@/lib/query";
import { getErrorMessage } from "@/lib/api/client";
import { formatClock } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useTripRoom } from "@/lib/hooks/useTripRoom";
import type {
  AbsenceListItem,
  AttendanceRecord,
  AttendanceInput,
  EndTripResult,
  Stop,
  TripDetail,
} from "@/lib/api/types";
import { useGeoBroadcast } from "./useGeoBroadcast";
import { KeepScreenOnBanner } from "./components/KeepScreenOnBanner";
import { StudentAttendanceRow, type Mark } from "./components/StudentAttendanceRow";

export default function RunTripPage() {
  const { tripId = "" } = useParams();
  const { t } = useTranslation("driver");
  const navigate = useNavigate();

  const tripQuery = useQuery({
    queryKey: qk.trip(tripId),
    queryFn: () => tripsApi.get(tripId),
    enabled: !!tripId,
  });
  const stopsQuery = useQuery({
    queryKey: ["trip", tripId, "stops"],
    queryFn: () => tripsApi.stops(tripId),
    enabled: !!tripId,
  });
  const attendanceQuery = useQuery({
    queryKey: qk.tripAttendance(tripId),
    queryFn: () => tripsApi.attendance(tripId),
    enabled: !!tripId,
  });
  const absencesQuery = useQuery({
    queryKey: qk.tripAbsences(tripId),
    queryFn: () => tripsApi.absences(tripId),
    enabled: !!tripId,
  });

  const trip = tripQuery.data;
  const isRunning = trip?.status === "in_progress";

  // GPS broadcast + screen wake lock — active only while the trip runs.
  const geo = useGeoBroadcast(tripId, !!isRunning);

  // Live room: refetch parent-absences and toast on not-boarded alerts.
  useTripRoom(
    tripId,
    {
      onChildAbsentMarked: () => void absencesQuery.refetch(),
      onChildNotBoarded: (e) =>
        toast.warning(
          t("run.notBoardedAlert", "{{name}} did not board at {{stop}}", {
            name: e.student_name,
            stop: e.stop_name,
          }),
        ),
      onChildNotDropped: (e) =>
        toast.error(
          t("run.notDroppedAlert", "{{name}} has not been dropped", {
            name: e.student_name,
          }),
        ),
    },
    !!isRunning,
  );

  const isLoading =
    tripQuery.isLoading ||
    stopsQuery.isLoading ||
    attendanceQuery.isLoading ||
    absencesQuery.isLoading;
  const isError =
    tripQuery.isError ||
    stopsQuery.isError ||
    attendanceQuery.isError ||
    absencesQuery.isError;

  const routeName = trip?.route?.name ?? t("run.trip", "Trip");

  return (
    <div className="space-y-5">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/driver")}
              aria-label={t("run.back", "Back")}
            >
              <ArrowLeft className="size-5" />
            </Button>
            <span className="truncate">{routeName}</span>
          </span>
        }
        actions={trip ? <TripStatusBadge status={trip.status} /> : null}
      />

      {isLoading ? (
        <CenteredSpinner label={t("run.loading", "Loading trip…")} />
      ) : isError || !trip ? (
        <ErrorState onRetry={() => void tripQuery.refetch()} />
      ) : (
        <RunTripContent
          tripId={tripId}
          trip={trip}
          stops={stopsQuery.data ?? []}
          roster={attendanceQuery.data ?? []}
          absences={absencesQuery.data ?? []}
          geo={geo}
        />
      )}
    </div>
  );
}

interface ContentProps {
  tripId: string;
  trip: TripDetail;
  stops: Stop[];
  roster: AttendanceRecord[];
  absences: AbsenceListItem[];
  geo: ReturnType<typeof useGeoBroadcast>;
}

function RunTripContent({ tripId, trip, stops, roster, absences, geo }: ContentProps) {
  const { t } = useTranslation("driver");
  const navigate = useNavigate();
  const qc = useQueryClient();

  const isMorning = trip.slot === "morning";
  const orderedStops = useMemo(
    () => [...stops].sort((a, b) => a.stop_order - b.stop_order),
    [stops],
  );

  const absentIds = useMemo(
    () => new Set(absences.map((a) => a.student_id)),
    [absences],
  );

  // students grouped by stop_id
  const studentsByStop = useMemo(() => {
    const map = new Map<string, AttendanceRecord[]>();
    for (const r of roster) {
      if (!r.stop_id) continue;
      const list = map.get(r.stop_id) ?? [];
      list.push(r);
      map.set(r.stop_id, list);
    }
    return map;
  }, [roster]);

  // Which stop is "active": current_stop_order drives it; else first stop.
  const activeStopId = useMemo(() => {
    if (orderedStops.length === 0) return null;
    const byOrder =
      trip.current_stop_order != null
        ? orderedStops.find((s) => s.stop_order === trip.current_stop_order)
        : undefined;
    return (byOrder ?? orderedStops[0]).id;
  }, [orderedStops, trip.current_stop_order]);

  const activeIndex = orderedStops.findIndex((s) => s.id === activeStopId);

  // local per-student marks for the active stop (keyed by student_id)
  const [marks, setMarks] = useState<Record<string, Mark>>({});
  const [endResult, setEndResult] = useState<EndTripResult | null>(null);
  const [confirmEnd, setConfirmEnd] = useState(false);

  const invalidateTrip = () => {
    void qc.invalidateQueries({ queryKey: qk.trip(tripId) });
    void qc.invalidateQueries({ queryKey: qk.tripAttendance(tripId) });
    void qc.invalidateQueries({ queryKey: ["trip", tripId, "stops"] });
    void queryClient.invalidateQueries({ queryKey: qk.activeTrips });
  };

  // --- mutations ------------------------------------------------------------
  const startMutation = useMutation({
    mutationFn: () => tripsApi.start(tripId),
    onSuccess: () => {
      toast.success(t("run.started", "Trip started"));
      invalidateTrip();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const submitMutation = useMutation({
    mutationFn: (vars: { stopId: string; attendance: AttendanceInput[] }) =>
      tripsApi.submitAttendance(tripId, vars.stopId, vars.attendance),
    onSuccess: (res) => {
      if (res.alerts_triggered > 0) {
        toast.warning(
          t("run.submittedWithAlerts", "Recorded {{n}} — {{a}} not-boarded alert(s)", {
            n: res.processed,
            a: res.alerts_triggered,
          }),
        );
      } else {
        toast.success(
          t("run.submitted", "Attendance recorded ({{n}})", { n: res.processed }),
        );
      }
      setMarks({});
      invalidateTrip();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const dropMutation = useMutation({
    mutationFn: (vars: { studentIds: string[]; type: "stop" | "school"; stopId?: string }) =>
      tripsApi.drop(tripId, {
        student_ids: vars.studentIds,
        drop_type: vars.type,
        stop_id: vars.stopId,
      }),
    onSuccess: (res) => {
      toast.success(t("run.dropped", "Dropped {{n}} student(s)", { n: res.dropped }));
      invalidateTrip();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const endMutation = useMutation({
    mutationFn: () => tripsApi.end(tripId),
    onSuccess: (res) => {
      invalidateTrip();
      if (res.status === "completed") {
        toast.success(t("run.completed", "Trip completed"));
        navigate("/driver");
      } else {
        setEndResult(res);
        toast.error(
          t("run.safeguardBlocked", "Trip can't end — students still on board"),
        );
      }
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  // --- derived counts -------------------------------------------------------
  const boardedIds = useMemo(
    () => roster.filter((r) => r.status === "boarded").map((r) => r.student_id),
    [roster],
  );

  // ============================ scheduled =================================
  if (trip.status === "scheduled") {
    return (
      <div className="space-y-5">
        <Card>
          <CardContent className="space-y-2 p-5 text-center">
            <School className="mx-auto size-8 text-primary" />
            <p className="text-lg font-semibold">
              {t("run.readyTitle", "Ready to start")}
            </p>
            <p className="text-sm text-muted-foreground">
              {t(
                "run.readyHint",
                "Starting will begin live location sharing with parents. Keep this screen open for the whole trip.",
              )}
            </p>
          </CardContent>
        </Card>
        <Button
          size="xl"
          className="w-full"
          disabled={startMutation.isPending}
          onClick={() => startMutation.mutate()}
        >
          {startMutation.isPending ? <Spinner /> : <PlayCircle className="size-5" />}
          {t("run.startTrip", "Start trip")}
        </Button>
        <StopOverview stops={orderedStops} studentsByStop={studentsByStop} />
      </div>
    );
  }

  // ===================== completed / cancelled / incident =================
  if (
    trip.status === "completed" ||
    trip.status === "cancelled" ||
    trip.status === "incident"
  ) {
    return (
      <Card>
        <CardContent className="space-y-3 p-6 text-center">
          <CheckCircle2 className="mx-auto size-10 text-success" />
          <p className="text-lg font-semibold">
            {trip.status === "completed"
              ? t("run.tripDone", "This trip is complete")
              : t("run.tripClosed", "This trip is closed")}
          </p>
          <Button variant="outline" size="lg" onClick={() => navigate("/driver")}>
            {t("run.backToToday", "Back to today")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  // ============== in_progress / pending_safeguard_check ===================
  const activeStop = orderedStops.find((s) => s.id === activeStopId) ?? null;
  const activeStudents = activeStop ? studentsByStop.get(activeStop.id) ?? [] : [];
  const toggleable = activeStudents.filter((s) => !absentIds.has(s.student_id));
  // Effective mark = explicit local choice, else a status already recorded
  // by the server (so a re-visited stop isn't stuck demanding re-marks).
  const effectiveMark = (s: AttendanceRecord): Mark =>
    marks[s.student_id] ??
    (s.status === "boarded" ? "boarded" : s.status === "absent" ? "absent" : null);
  const allMarked =
    toggleable.length > 0 && toggleable.every((s) => effectiveMark(s) !== null);
  const isLastStop = activeIndex === orderedStops.length - 1;

  // boarded at the active stop (this run) — used by evening per-stop drop
  const boardedAtActive = activeStudents
    .filter((s) => s.status === "boarded")
    .map((s) => s.student_id);

  const onSubmitStop = () => {
    if (!activeStop) return;
    const attendance: AttendanceInput[] = toggleable.map((s) => ({
      student_id: s.student_id,
      status: effectiveMark(s) === "boarded" ? "boarded" : "absent",
    }));
    submitMutation.mutate({ stopId: activeStop.id, attendance });
  };

  return (
    <div className="space-y-5">
      <KeepScreenOnBanner geo={geo} />

      {/* Safeguard gate banner */}
      {trip.status === "pending_safeguard_check" || endResult ? (
        <SafeguardCard
          unresolved={endResult?.unresolved_students ?? []}
          roster={roster}
          dropping={dropMutation.isPending}
          onDropRemaining={() => {
            const ids = endResult?.unresolved_students ?? boardedIds;
            if (ids.length === 0) {
              endMutation.mutate();
              return;
            }
            dropMutation.mutate(
              { studentIds: ids, type: "school" },
              {
                onSuccess: () => {
                  setEndResult(null);
                  endMutation.mutate();
                },
              },
            );
          }}
        />
      ) : null}

      {orderedStops.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title={t("run.noStops", "This route has no stops")}
          description={t(
            "run.noStopsHint",
            "You can still end the trip once you reach the school.",
          )}
        />
      ) : (
        <>
          {/* Stop progress strip */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {orderedStops.map((s, i) => {
              const count = (studentsByStop.get(s.id) ?? []).length;
              return (
                <div
                  key={s.id}
                  className={cn(
                    "flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium",
                    i === activeIndex
                      ? "border-primary bg-primary/10 text-primary"
                      : i < activeIndex
                        ? "border-success/40 bg-success/10 text-success"
                        : "border-border text-muted-foreground",
                  )}
                >
                  {i < activeIndex ? (
                    <CheckCircle2 className="size-3.5" />
                  ) : (
                    <span>{i + 1}</span>
                  )}
                  <span className="max-w-28 truncate">{s.name}</span>
                  <Badge variant="muted" className="px-1.5">
                    {count}
                  </Badge>
                </div>
              );
            })}
          </div>

          {/* Active stop card */}
          {activeStop ? (
            <Card>
              <CardContent className="space-y-4 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wide text-primary">
                      {t("run.currentStop", "Current stop")}{" "}
                      {activeIndex + 1}/{orderedStops.length}
                    </p>
                    <h3 className="truncate text-lg font-semibold">
                      {activeStop.name}
                    </h3>
                    {activeStop.arrival_time ? (
                      <p className="text-sm text-muted-foreground">
                        {t("run.eta", "ETA")} {formatClock(activeStop.arrival_time)}
                      </p>
                    ) : null}
                  </div>
                  <span className="flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground">
                    <Users className="size-3.5" />
                    {activeStudents.length}
                  </span>
                </div>

                {activeStudents.length === 0 ? (
                  <p className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
                    {t("run.noStudentsAtStop", "No students assigned to this stop.")}
                  </p>
                ) : (
                  <div className="space-y-2">
                    {activeStudents.map((s) => {
                      const parentAbsent = absentIds.has(s.student_id);
                      return (
                        <StudentAttendanceRow
                          key={s.student_id}
                          name={s.student_name}
                          parentAbsent={parentAbsent}
                          mark={parentAbsent ? null : effectiveMark(s)}
                          locked={submitMutation.isPending}
                          onChange={(m) =>
                            setMarks((prev) => ({ ...prev, [s.student_id]: m }))
                          }
                        />
                      );
                    })}
                  </div>
                )}

                {/* Submit attendance for this stop */}
                {toggleable.length > 0 ? (
                  <Button
                    size="xl"
                    className="w-full"
                    disabled={!allMarked || submitMutation.isPending}
                    onClick={onSubmitStop}
                  >
                    {submitMutation.isPending ? (
                      <Spinner />
                    ) : (
                      <CheckCircle2 className="size-5" />
                    )}
                    {allMarked
                      ? t("run.submitStop", "Submit stop")
                      : t("run.markAll", "Mark every student to continue")}
                  </Button>
                ) : null}

                {/* EVENING: per-stop drop */}
                {!isMorning && boardedAtActive.length > 0 ? (
                  <Button
                    size="lg"
                    variant="secondary"
                    className="w-full"
                    disabled={dropMutation.isPending}
                    onClick={() =>
                      dropMutation.mutate({
                        studentIds: boardedAtActive,
                        type: "stop",
                        stopId: activeStop.id,
                      })
                    }
                  >
                    {dropMutation.isPending ? <Spinner /> : <MapPin className="size-5" />}
                    {t("run.dropHere", "Drop {{n}} here", { n: boardedAtActive.length })}
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {/* MORNING: drop everyone at school after the last stop */}
          {isMorning && isLastStop && boardedIds.length > 0 ? (
            <Button
              size="xl"
              variant="secondary"
              className="w-full"
              disabled={dropMutation.isPending}
              onClick={() =>
                dropMutation.mutate({ studentIds: boardedIds, type: "school" })
              }
            >
              {dropMutation.isPending ? <Spinner /> : <School className="size-5" />}
              {t("run.dropAllSchool", "Drop all {{n}} at school", {
                n: boardedIds.length,
              })}
            </Button>
          ) : null}
        </>
      )}

      {/* End trip */}
      <Button
        size="xl"
        variant="destructive"
        className="w-full"
        disabled={endMutation.isPending}
        onClick={() => setConfirmEnd(true)}
      >
        {endMutation.isPending ? <Spinner /> : <Flag className="size-5" />}
        {t("run.endTrip", "End trip")}
      </Button>

      <ConfirmDialog
        open={confirmEnd}
        onOpenChange={setConfirmEnd}
        title={t("run.endConfirmTitle", "End this trip?")}
        description={t(
          "run.endConfirmDesc",
          "Every boarded student must be dropped first. Live tracking will stop.",
        )}
        confirmLabel={t("run.endTrip", "End trip")}
        destructive
        onConfirm={async () => {
          await endMutation.mutateAsync();
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------

function SafeguardCard({
  unresolved,
  roster,
  dropping,
  onDropRemaining,
}: {
  unresolved: string[];
  roster: AttendanceRecord[];
  dropping: boolean;
  onDropRemaining: () => void;
}) {
  const { t } = useTranslation("driver");
  const nameOf = (id: string) =>
    roster.find((r) => r.student_id === id)?.student_name ?? id.slice(0, 8);

  return (
    <Card className="border-destructive/40 bg-destructive/5">
      <CardContent className="space-y-3 p-5">
        <div className="flex items-center gap-2 text-destructive">
          <ShieldAlert className="size-6" />
          <p className="text-base font-semibold">
            {t("run.safeguardTitle", "Students still on board")}
          </p>
        </div>
        <p className="text-sm text-muted-foreground">
          {t(
            "run.safeguardDesc",
            "The trip can't be completed until everyone is dropped. Drop the remaining students at school to finish.",
          )}
        </p>
        {unresolved.length > 0 ? (
          <ul className="space-y-1.5">
            {unresolved.map((id) => (
              <li
                key={id}
                className="flex items-center gap-2 rounded-lg bg-card px-3 py-2 text-sm font-medium"
              >
                <ChevronRight className="size-4 text-destructive" />
                {nameOf(id)}
              </li>
            ))}
          </ul>
        ) : null}
        <Button
          size="xl"
          variant="destructive"
          className="w-full"
          disabled={dropping}
          onClick={onDropRemaining}
        >
          {dropping ? <Spinner /> : <School className="size-5" />}
          {t("run.dropRemaining", "Drop remaining at school")}
        </Button>
      </CardContent>
    </Card>
  );
}

function StopOverview({
  stops,
  studentsByStop,
}: {
  stops: Stop[];
  studentsByStop: Map<string, AttendanceRecord[]>;
}) {
  const { t } = useTranslation("driver");
  if (stops.length === 0) {
    return (
      <EmptyState
        icon={MapPin}
        title={t("run.noStops", "This route has no stops")}
      />
    );
  }
  return (
    <Card>
      <CardContent className="divide-y divide-border p-0">
        {stops.map((s, i) => (
          <div key={s.id} className="flex items-center gap-3 p-4">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-secondary-foreground">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{s.name}</p>
              {s.arrival_time ? (
                <p className="text-xs text-muted-foreground">
                  {formatClock(s.arrival_time)}
                </p>
              ) : null}
            </div>
            <Badge variant="muted">
              <Users className="size-3.5" />
              {(studentsByStop.get(s.id) ?? []).length}
            </Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
