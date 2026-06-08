import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState, CardListSkeleton } from "@/components/common/States";
import { studentsApi } from "@/lib/api/students";
import { transportRequestsApi } from "@/lib/api/transportRequests";
import { qk } from "@/lib/query";
import { AddChildDialog } from "./components/AddChildDialog";
import { ChildTripCard } from "./components/ChildTripCard";

/** Parent home: children list, today's trip per child, add-child. */
export function DashboardPage() {
  const { t } = useTranslation("parent");

  const studentsQuery = useQuery({
    queryKey: qk.students({ scope: "mine" }),
    queryFn: () => studentsApi.list({ limit: 100 }),
  });

  // Assigned transport requests resolve each child's bus route.
  const assignedQuery = useQuery({
    queryKey: qk.transportRequests({ status: "assigned" }),
    queryFn: () => transportRequestsApi.list({ status: "assigned", limit: 100 }),
  });

  const students = studentsQuery.data?.items ?? [];
  const assignedRequests = assignedQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("dashboard.title", "My children")}
        description={t(
          "dashboard.subtitle",
          "Track today's bus and manage your children's transport.",
        )}
        actions={<AddChildDialog />}
      />

      {studentsQuery.isLoading ? (
        <CardListSkeleton rows={2} />
      ) : studentsQuery.isError ? (
        <ErrorState
          message={t("dashboard.loadError", "Couldn't load your children.")}
          onRetry={() => void studentsQuery.refetch()}
        />
      ) : students.length === 0 ? (
        <EmptyState
          icon={Users}
          title={t("dashboard.emptyTitle", "No children yet")}
          description={t(
            "dashboard.emptyDescription",
            "Add your child to request school transport and track their bus live.",
          )}
          action={<AddChildDialog />}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {students.map((student) => (
            <ChildTripCard
              key={student.id}
              student={student}
              assignedRequests={assignedRequests}
            />
          ))}
        </div>
      )}
    </div>
  );
}
