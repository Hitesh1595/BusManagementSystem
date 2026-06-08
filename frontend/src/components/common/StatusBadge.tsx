import { useTranslation } from "react-i18next";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { AlertSeverity, TransportRequestStatus, TripStatus } from "@/lib/api/types";

const tripVariant: Record<TripStatus, BadgeProps["variant"]> = {
  scheduled: "muted",
  in_progress: "default",
  pending_safeguard_check: "destructive",
  completed: "success",
  cancelled: "muted",
  incident: "destructive",
};

export function TripStatusBadge({ status }: { status: TripStatus }) {
  const { t } = useTranslation("common");
  return (
    <Badge variant={tripVariant[status]}>
      {status === "in_progress" ? (
        <span className="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-current" />
      ) : null}
      {t(`status.${status}`)}
    </Badge>
  );
}

const severityVariant: Record<AlertSeverity, BadgeProps["variant"]> = {
  critical: "destructive",
  high: "warning",
  medium: "secondary",
  low: "muted",
};

export function AlertSeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <Badge variant={severityVariant[severity]} className="uppercase">
      {severity}
    </Badge>
  );
}

const requestVariant: Record<TransportRequestStatus, BadgeProps["variant"]> = {
  pending: "warning",
  approved: "secondary",
  rejected: "destructive",
  assigned: "success",
};

export function RequestStatusBadge({ status }: { status: TransportRequestStatus }) {
  return <Badge variant={requestVariant[status]} className="capitalize">{status}</Badge>;
}
