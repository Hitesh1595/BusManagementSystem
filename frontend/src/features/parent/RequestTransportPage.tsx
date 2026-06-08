import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { MapPin, Navigation, Send } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState, CenteredSpinner } from "@/components/common/States";
import { Field } from "@/components/common/Field";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import {
  MapView,
  DraggablePin,
  MapClick,
  GeocodeSearch,
  Recenter,
} from "@/components/maps";
import { studentsApi } from "@/lib/api/students";
import { transportRequestsApi } from "@/lib/api/transportRequests";
import { getErrorMessage } from "@/lib/api/client";
import { qk } from "@/lib/query";
import { reverseGeocode } from "@/lib/geocode";
import { formatDistance, formatClock } from "@/lib/format";
import type { LatLng, StopSuggestion } from "@/lib/api/types";

export function RequestTransportPage() {
  const { t } = useTranslation("parent");
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [studentId, setStudentId] = useState<string>("");
  const [pickup, setPickup] = useState<LatLng | null>(null);
  const [address, setAddress] = useState<string>("");
  const [suggestions, setSuggestions] = useState<StopSuggestion[] | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const studentsQuery = useQuery({
    queryKey: qk.students({ scope: "mine" }),
    queryFn: () => studentsApi.list({ limit: 100 }),
  });
  const students = studentsQuery.data?.items ?? [];

  // Pre-select the only child, and seed its saved pickup if present.
  useEffect(() => {
    if (!studentId && students.length === 1) {
      setStudentId(students[0].id);
    }
  }, [students, studentId]);

  // When a child is chosen, seed the map from their saved pickup (once per child).
  const seededFor = useRef<string | null>(null);
  useEffect(() => {
    const s = students.find((st) => st.id === studentId);
    if (!s || seededFor.current === studentId) return;
    seededFor.current = studentId;
    if (s.pickup_location) {
      setPickup(s.pickup_location);
      setAddress(s.pickup_address ?? "");
    }
  }, [studentId, students]);

  const setPin = async (point: LatLng) => {
    setPickup(point);
    setSuggestions(null);
    const r = await reverseGeocode(point.lat, point.lng);
    if (r) setAddress(r);
  };

  const fetchSuggestions = async () => {
    if (!pickup) return;
    setSuggesting(true);
    try {
      const res = await transportRequestsApi.suggestStop({
        lat: pickup.lat,
        lng: pickup.lng,
      });
      setSuggestions(res.suggestions.slice(0, 3));
    } catch (e) {
      toast.error(await getErrorMessage(e));
    } finally {
      setSuggesting(false);
    }
  };

  const createMutation = useMutation({
    mutationFn: () =>
      transportRequestsApi.create({
        student_id: studentId,
        pickup_address: address.trim() || null,
        pickup_location: pickup,
      }),
    onSuccess: () => {
      toast.success(t("request.success", "Transport request submitted"));
      void queryClient.invalidateQueries({ queryKey: ["transport-requests"] });
      navigate("/parent/requests");
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const onSubmit = () => {
    setSubmitted(true);
    if (!studentId || !pickup) return;
    createMutation.mutate();
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("request.title", "Request transport")}
        description={t(
          "request.subtitle",
          "Pick your child and pickup point. The school will assign the nearest stop.",
        )}
      />

      {studentsQuery.isLoading ? (
        <CenteredSpinner label={t("request.loadingChildren", "Loading your children…")} />
      ) : studentsQuery.isError ? (
        <ErrorState
          message={t("request.childrenError", "Couldn't load your children.")}
          onRetry={() => void studentsQuery.refetch()}
        />
      ) : students.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title={t("request.noChildrenTitle", "Add a child first")}
          description={t(
            "request.noChildrenDescription",
            "You need to add a child before requesting transport.",
          )}
          action={
            <Button onClick={() => navigate("/parent")}>
              {t("request.goAddChild", "Go to my children")}
            </Button>
          }
        />
      ) : (
        <div className="space-y-5">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                {t("request.childSection", "1. Choose child")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Field
                label={t("request.child", "Child")}
                required
                error={
                  submitted && !studentId
                    ? t("request.childRequired", "Select a child")
                    : undefined
                }
              >
                <Select value={studentId} onValueChange={setStudentId}>
                  <SelectTrigger>
                    <SelectValue
                      placeholder={t("request.childPlaceholder", "Select a child")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {students.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.full_name}
                        {s.grade ? ` · ${t("request.gradeShort", "Gr")} ${s.grade}` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                {t("request.pickupSection", "2. Set pickup location")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <GeocodeSearch
                placeholder={t("request.searchPlaceholder", "Search an address")}
                onSelect={(r) => {
                  setPickup({ lat: r.lat, lng: r.lng });
                  setAddress(r.label);
                  setSuggestions(null);
                }}
              />
              <p className="text-xs text-muted-foreground">
                {t("request.mapHint", "Tap the map or drag the pin to fine-tune.")}
              </p>
              <div className="h-[45vh] w-full overflow-hidden rounded-xl border border-border">
                <MapView center={pickup ?? undefined} zoom={15}>
                  <MapClick onPick={setPin} />
                  {pickup ? (
                    <>
                      <DraggablePin point={pickup} onMove={setPin} />
                      <Recenter point={pickup} />
                    </>
                  ) : null}
                </MapView>
              </div>
              {address ? (
                <p className="flex items-start gap-2 text-sm">
                  <MapPin className="mt-0.5 size-4 shrink-0 text-primary" />
                  <span className="text-muted-foreground">{address}</span>
                </p>
              ) : null}
              {submitted && !pickup ? (
                <p className="text-xs font-medium text-destructive">
                  {t("request.pickupRequired", "Set a pickup location")}
                </p>
              ) : null}

              <Button
                type="button"
                variant="outline"
                onClick={() => void fetchSuggestions()}
                disabled={!pickup || suggesting}
                className="w-full"
              >
                {suggesting ? <Spinner className="size-4" /> : <Navigation className="size-4" />}
                {t("request.findStops", "Find nearest stops")}
              </Button>
            </CardContent>
          </Card>

          {suggestions ? (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  {t("request.nearestStops", "Nearest existing stops")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {suggestions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t(
                      "request.noStops",
                      "No nearby stops yet — the school will create one for you.",
                    )}
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {suggestions.map((s) => (
                      <li
                        key={s.stop_id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-border p-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{s.name}</p>
                          {s.arrival_time ? (
                            <p className="text-xs text-muted-foreground">
                              {t("request.arrives", "Arrives")} {formatClock(s.arrival_time)}
                            </p>
                          ) : null}
                        </div>
                        <Badge variant="secondary">{formatDistance(s.distance_m)}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-3 text-xs text-muted-foreground">
                  {t(
                    "request.suggestionsNote",
                    "These are suggestions only. The school confirms the final stop after you submit.",
                  )}
                </p>
              </CardContent>
            </Card>
          ) : null}

          <Button
            type="button"
            size="lg"
            className="w-full"
            onClick={onSubmit}
            disabled={createMutation.isPending || !studentId || !pickup}
          >
            {createMutation.isPending ? <Spinner className="size-4" /> : <Send className="size-4" />}
            {t("request.submit", "Submit request")}
          </Button>
        </div>
      )}
    </div>
  );
}
