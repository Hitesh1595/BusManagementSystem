import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Bus,
  Check,
  Copy,
  GraduationCap,
  Navigation,
  Route as RouteIcon,
  Users,
} from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState, CardListSkeleton } from "@/components/common/States";
import { StatCard } from "@/components/common/StatCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { superAdminApi } from "@/lib/api";
import type { AlertSeverityBreakdown } from "@/lib/api/types";

const SEVERITY_META: { key: keyof AlertSeverityBreakdown; label: string; dot: string }[] = [
  { key: "critical", label: "Critical", dot: "bg-destructive" },
  { key: "high", label: "High", dot: "bg-warning" },
  { key: "medium", label: "Medium", dot: "bg-primary" },
  { key: "low", label: "Low", dot: "bg-muted-foreground" },
];

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

export function SchoolDetailPage() {
  const { id = "" } = useParams();

  const query = useQuery({
    queryKey: ["superSchool", id],
    queryFn: () => superAdminApi.schoolOverview(id),
    enabled: id.length > 0,
  });

  const data = query.data;

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2 w-fit">
        <Link to="/super">
          <ArrowLeft className="size-4" />
          All schools
        </Link>
      </Button>

      {query.isLoading ? (
        <CardListSkeleton rows={4} />
      ) : query.isError || !data ? (
        <ErrorState onRetry={() => query.refetch()} />
      ) : (
        <>
          <PageHeader
            title={data.school.name}
            description={data.school.address ?? "No address on file"}
            actions={
              <Badge variant={data.school.is_active ? "success" : "muted"}>
                {data.school.is_active ? "Active" : "Inactive"}
              </Badge>
            }
          />

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard icon={Bus} label="Vehicles" value={data.vehicle_count} />
            <StatCard icon={Users} label="Drivers" value={data.driver_count} />
            <StatCard icon={RouteIcon} label="Routes" value={data.route_count} />
            <StatCard icon={GraduationCap} label="Students" value={data.student_count} />
            <StatCard icon={Navigation} label="Active trips" value={data.active_trip_count} />
            <StatCard
              icon={AlertTriangle}
              label="Open alerts"
              value={data.open_alert_count}
              accent="destructive"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>School details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <Row label="Join code">
                  <span className="flex items-center gap-1">
                    <code className="font-mono tracking-wider">{data.school.join_code}</code>
                    <CopyButton value={data.school.join_code} />
                  </span>
                </Row>
                <Row label="Phone">{data.school.phone ?? "—"}</Row>
                <Row label="Email">{data.school.email ?? "—"}</Row>
                <Row label="Timezone">{data.school.timezone}</Row>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Open alerts by severity</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {data.open_alert_count === 0 ? (
                  <p className="text-muted-foreground">No open alerts.</p>
                ) : (
                  SEVERITY_META.map(({ key, label, dot }) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <span className={`size-2.5 rounded-full ${dot}`} />
                        {label}
                      </span>
                      <span className="font-semibold tabular-nums">
                        {data.alert_severity[key]}
                      </span>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{children}</span>
    </div>
  );
}
