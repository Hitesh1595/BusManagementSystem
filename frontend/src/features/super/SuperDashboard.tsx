import { Building2 } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";

/**
 * Multi-school super-admin console is a V2 surface (the backend create/list
 * endpoints are 501 stubs). This is a minimal placeholder so super_admins can
 * still sign in.
 */
export function SuperDashboard() {
  return (
    <div className="space-y-6">
      <PageHeader title="Platform admin" />
      <EmptyState
        icon={Building2}
        title="Multi-school management is coming in V2"
        description="School creation and the cross-school dashboard aren't enabled yet. For now, manage a single school from the school-admin account."
      />
    </div>
  );
}
