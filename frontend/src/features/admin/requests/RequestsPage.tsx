import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Inbox, MapPin, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState, CardListSkeleton } from "@/components/common/States";
import { RequestStatusBadge } from "@/components/common/StatusBadge";
import { Field } from "@/components/common/Field";
import { Card, CardContent } from "@/components/ui/card";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { formatDistance, timeAgo } from "@/lib/format";
import { getErrorMessage, parseApiError } from "@/lib/api/client";
import { qk, queryClient } from "@/lib/query";
import { usePagination } from "@/lib/hooks/usePagination";
import { useEntityMap } from "@/lib/hooks/useEntityMap";
import { transportRequestsApi } from "@/lib/api/transportRequests";
import { studentsApi } from "@/lib/api/students";
import { routesApi } from "@/lib/api/routes";
import type {
  Route,
  StopSuggestion,
  Student,
  TransportRequest,
} from "@/lib/api/types";
import { MapView, DraggablePin, SchoolMarker } from "@/components/maps";

type Tab = "pending" | "approved" | "assigned" | "rejected" | "all";
const TABS: Tab[] = ["pending", "approved", "assigned", "rejected", "all"];

export function RequestsPage() {
  const { t } = useTranslation("admin");
  const [tab, setTab] = useState<Tab>("pending");
  const [reviewing, setReviewing] = useState<TransportRequest | null>(null);

  const { limit, offset, setOffset } = usePagination(24, tab);
  const params = useMemo(
    () => ({ status: tab === "all" ? undefined : tab, limit, offset }),
    [tab, limit, offset],
  );

  const query = useQuery({
    queryKey: qk.transportRequests(params),
    queryFn: () => transportRequestsApi.list(params),
    placeholderData: keepPreviousData,
  });

  const items = query.data?.items ?? [];

  // Resolve student names for the rows on this page (scales past one list page).
  const studentMap = useEntityMap(
    items.map((req) => req.student_id),
    studentsApi.get,
    "student",
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("requests.title", "Transport requests")}
        description={t("requests.subtitle", "Review parent requests and assign each child to a route and stop.")}
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          {TABS.map((tp) => (
            <TabsTrigger key={tp} value={tp} className="capitalize">
              {t(`requests.tab.${tp}`, tp)}
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
          title={t("requests.empty.title", "No requests here")}
          description={t("requests.empty.desc", "New transport requests from parents will appear in this list.")}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((req) => (
            <RequestCard
              key={req.id}
              req={req}
              student={studentMap.get(req.student_id)}
              onReview={() => setReviewing(req)}
            />
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
        <ReviewDialog
          req={reviewing}
          student={studentMap.get(reviewing.student_id)}
          onClose={() => setReviewing(null)}
        />
      ) : null}
    </div>
  );
}

function RequestCard({
  req,
  student,
  onReview,
}: {
  req: TransportRequest;
  student: Student | undefined;
  onReview: () => void;
}) {
  const { t } = useTranslation("admin");
  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold">
              {student?.full_name ?? t("requests.unknownStudent", "Student")}
            </p>
            {student?.grade ? (
              <p className="text-xs text-muted-foreground">
                {t("requests.grade", "Grade {{grade}}", { grade: student.grade })}
                {student.section ? ` · ${student.section}` : ""}
              </p>
            ) : null}
          </div>
          <RequestStatusBadge status={req.status} />
        </div>

        <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
          <MapPin className="mt-0.5 size-3.5 shrink-0" />
          <span className="line-clamp-2">
            {req.pickup_address ?? t("requests.noAddress", "No pickup address provided")}
          </span>
        </p>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">{timeAgo(req.created_at)}</span>
          {req.status === "pending" ? (
            <Button size="sm" onClick={onReview}>
              {t("requests.review", "Review")}
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={onReview}>
              {t("requests.viewDetails", "Details")}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ReviewDialog({
  req,
  student,
  onClose,
}: {
  req: TransportRequest;
  student: Student | undefined;
  onClose: () => void;
}) {
  const { t } = useTranslation("admin");
  const readOnly = req.status !== "pending";

  const pickup = req.pickup_location;

  const [routeId, setRouteId] = useState<string>(req.assigned_route_id ?? "");
  const [stopId, setStopId] = useState<string>(req.assigned_stop_id ?? "");
  const [notes, setNotes] = useState<string>(req.admin_notes ?? "");
  const [submitting, setSubmitting] = useState(false);

  const suggestionsQuery = useQuery({
    queryKey: ["request-suggestions", req.id],
    queryFn: () =>
      transportRequestsApi.suggestStop(
        pickup ? { lat: pickup.lat, lng: pickup.lng } : { address: req.pickup_address ?? undefined },
      ),
    enabled: !readOnly,
  });

  const routesQuery = useQuery({
    queryKey: qk.routes({ limit: 100 }),
    queryFn: () => routesApi.list({ limit: 100 }),
    enabled: !readOnly,
  });

  const routeDetailQuery = useQuery({
    queryKey: qk.route(routeId),
    queryFn: () => routesApi.get(routeId),
    enabled: !readOnly && !!routeId,
  });
  const stops = routeDetailQuery.data?.stops ?? [];

  const applySuggestion = (s: StopSuggestion) => {
    setRouteId(s.route_id);
    setStopId(s.stop_id);
  };

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["transport-requests"] });
  };

  const assign = async () => {
    if (!routeId || !stopId) {
      toast.error(t("requests.pickRouteStop", "Pick a route and a stop first."));
      return;
    }
    setSubmitting(true);
    try {
      await transportRequestsApi.update(req.id, {
        status: "assigned",
        assigned_route_id: routeId,
        assigned_stop_id: stopId,
        admin_notes: notes.trim() || undefined,
      });
      toast.success(t("requests.assigned", "Request assigned"));
      invalidate();
      onClose();
    } catch (e) {
      const parsed = await parseApiError(e);
      if (parsed.status === 409) toast.error(t("requests.atCapacity", "Route is at capacity"));
      else toast.error(parsed.message);
    } finally {
      setSubmitting(false);
    }
  };

  const reject = async () => {
    setSubmitting(true);
    try {
      await transportRequestsApi.update(req.id, {
        status: "rejected",
        admin_notes: notes.trim() || undefined,
      });
      toast.success(t("requests.rejected", "Request rejected"));
      invalidate();
      onClose();
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && !submitting && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {student?.full_name ?? t("requests.unknownStudent", "Student")}
          </DialogTitle>
          <DialogDescription>
            {req.pickup_address ?? t("requests.noAddress", "No pickup address provided")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {pickup ? (
            <div className="h-48 w-full overflow-hidden rounded-xl border border-border">
              <MapView center={pickup} zoom={15} scrollWheelZoom={false}>
                <DraggablePin point={pickup} onMove={() => undefined} />
                <SchoolMarker location={pickup} />
              </MapView>
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
              {t("requests.noPin", "No pickup coordinates were provided for this request.")}
            </p>
          )}

          {readOnly ? (
            <ReadOnlyAssignment req={req} />
          ) : (
            <>
              {suggestionsQuery.data && suggestionsQuery.data.suggestions.length > 0 ? (
                <div className="space-y-2">
                  <p className="flex items-center gap-1.5 text-sm font-medium">
                    <Sparkles className="size-4 text-primary" />
                    {t("requests.suggested", "Suggested stops")}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {suggestionsQuery.data.suggestions.map((s) => (
                      <button
                        key={s.stop_id}
                        type="button"
                        onClick={() => applySuggestion(s)}
                        className={cn(
                          "rounded-lg border px-3 py-1.5 text-left text-sm transition-colors",
                          stopId === s.stop_id
                            ? "border-primary bg-primary/10"
                            : "border-border hover:bg-accent",
                        )}
                      >
                        <span className="block font-medium">{s.name}</span>
                        <span className="block text-xs text-muted-foreground">
                          {formatDistance(s.distance_m)}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : suggestionsQuery.isLoading ? (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner /> {t("requests.findingStops", "Finding nearby stops…")}
                </p>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t("requests.route", "Route")} required>
                  <Select
                    value={routeId}
                    onValueChange={(v) => {
                      setRouteId(v);
                      setStopId("");
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t("requests.selectRoute", "Select a route")} />
                    </SelectTrigger>
                    <SelectContent>
                      {(routesQuery.data?.items ?? []).map((r: Route) => (
                        <SelectItem key={r.id} value={r.id}>
                          {r.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>

                <Field label={t("requests.stop", "Stop")} required>
                  <Select value={stopId} onValueChange={setStopId} disabled={!routeId}>
                    <SelectTrigger>
                      <SelectValue
                        placeholder={
                          routeDetailQuery.isLoading
                            ? t("requests.loadingStops", "Loading…")
                            : t("requests.selectStop", "Select a stop")
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {stops.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.stop_order + 1}. {s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <Field label={t("requests.notes", "Admin notes")} hint={t("requests.notesHint", "Optional — shared with the parent.")}>
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  placeholder={t("requests.notesPlaceholder", "Add a note for this decision…")}
                />
              </Field>
            </>
          )}
        </div>

        <DialogFooter>
          {readOnly ? (
            <Button variant="outline" onClick={onClose}>
              {t("requests.close", "Close")}
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={reject} disabled={submitting}>
                {submitting ? <Spinner /> : null}
                {t("requests.reject", "Reject")}
              </Button>
              <Button variant="success" onClick={assign} disabled={submitting || !routeId || !stopId}>
                {submitting ? <Spinner /> : null}
                {t("requests.approveAssign", "Approve & assign")}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReadOnlyAssignment({ req }: { req: TransportRequest }) {
  const { t } = useTranslation("admin");
  const routeQuery = useQuery({
    queryKey: qk.route(req.assigned_route_id ?? "none"),
    queryFn: () => routesApi.get(req.assigned_route_id as string),
    enabled: !!req.assigned_route_id,
  });
  const route = routeQuery.data;
  const stop = route?.stops.find((s) => s.id === req.assigned_stop_id);

  return (
    <div className="space-y-2 rounded-lg border border-border p-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground">{t("requests.status", "Status")}</span>
        <RequestStatusBadge status={req.status} />
      </div>
      {req.assigned_route_id ? (
        <>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">{t("requests.route", "Route")}</span>
            <span className="font-medium">{route?.name ?? "—"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">{t("requests.stop", "Stop")}</span>
            <span className="font-medium">{stop?.name ?? "—"}</span>
          </div>
        </>
      ) : null}
      {req.admin_notes ? (
        <p className="border-t border-border pt-2 text-muted-foreground">{req.admin_notes}</p>
      ) : null}
    </div>
  );
}
