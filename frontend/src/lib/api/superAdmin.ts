import { api } from "./client";
import type { PlatformAnalytics, SchoolOverview } from "./types";

export const superAdminApi = {
  platformAnalytics: () =>
    api.get("super-admin/analytics/platform").json<PlatformAnalytics>(),

  schoolOverview: (id: string) =>
    api.get(`super-admin/schools/${id}/overview`).json<SchoolOverview>(),
};
