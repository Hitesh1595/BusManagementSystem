import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, MapPin, Plus } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState, CardListSkeleton } from "@/components/common/States";
import { RequestStatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { studentsApi } from "@/lib/api/students";
import { transportRequestsApi } from "@/lib/api/transportRequests";
import { qk } from "@/lib/query";
import { formatDate } from "@/lib/format";

export function RequestsPage() {
  const { t } = useTranslation("parent");

  const requestsQuery = useQuery({
    queryKey: qk.transportRequests({ scope: "mine" }),
    queryFn: () => transportRequestsApi.list({ limit: 100 }),
  });

  const studentsQuery = useQuery({
    queryKey: qk.students({ scope: "mine" }),
    queryFn: () => studentsApi.list({ limit: 100 }),
  });

  const studentNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of studentsQuery.data?.items ?? []) map.set(s.id, s.full_name);
    return map;
  }, [studentsQuery.data]);

  const requests = requestsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("requests.title", "Transport requests")}
        description={t(
          "requests.subtitle",
          "Track the status of your pickup requests to the school.",
        )}
        actions={
          <Button asChild>
            <Link to="/parent/request/new">
              <Plus className="size-4" />
              {t("requests.new", "New request")}
            </Link>
          </Button>
        }
      />

      {requestsQuery.isLoading ? (
        <CardListSkeleton rows={3} />
      ) : requestsQuery.isError ? (
        <ErrorState
          message={t("requests.loadError", "Couldn't load your requests.")}
          onRetry={() => void requestsQuery.refetch()}
        />
      ) : requests.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title={t("requests.emptyTitle", "No requests yet")}
          description={t(
            "requests.emptyDescription",
            "Submit a transport request and the school will assign a nearby stop.",
          )}
          action={
            <Button asChild>
              <Link to="/parent/request/new">
                <Plus className="size-4" />
                {t("requests.new", "New request")}
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {requests.map((req) => (
            <Card key={req.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-base">
                    {studentNames.get(req.student_id) ??
                      t("requests.unknownChild", "Child")}
                  </CardTitle>
                  <RequestStatusBadge status={req.status} />
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="flex items-start gap-2 text-muted-foreground">
                  <MapPin className="mt-0.5 size-4 shrink-0 text-primary" />
                  <span>
                    {req.pickup_address ??
                      t("requests.noAddress", "Pickup location pinned on map")}
                  </span>
                </p>
                {req.admin_notes ? (
                  <p className="rounded-lg bg-muted/50 px-3 py-2 text-muted-foreground">
                    <span className="font-medium text-foreground">
                      {t("requests.adminNotes", "School note: ")}
                    </span>
                    {req.admin_notes}
                  </p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  {t("requests.submittedOn", "Submitted {{date}}", {
                    date: formatDate(req.created_at),
                  })}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
