import { api } from "./client";
import { cleanParams } from "./_params";
import type { Notification, NotificationListResponse } from "./types";

export interface NotificationListParams {
  page?: number;
  page_size?: number;
  unread?: boolean;
}

export const notificationsApi = {
  list: (params: NotificationListParams = {}) =>
    api
      .get("notifications", { searchParams: cleanParams({ ...params }) })
      .json<NotificationListResponse>(),

  markRead: (id: string) =>
    api
      .put(`notifications/${id}/read`)
      .json<Pick<Notification, "id" | "is_read" | "read_at">>(),

  markAllRead: () =>
    api.put("notifications/read-all").json<{ marked_count: number }>(),

  updatePreferences: (prefs: Record<string, unknown>) =>
    api
      .put("notifications/preferences", { json: { notification_prefs: prefs } })
      .json<{ notification_prefs: Record<string, unknown> }>(),
};
