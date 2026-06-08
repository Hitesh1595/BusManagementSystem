import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  AlertAckResult,
  AlertListResponse,
  AlertResolveResult,
  AlertSeverity,
  AlertType,
} from "./types";

export interface AlertListParams extends PageParams {
  type?: AlertType;
  severity?: AlertSeverity;
  resolved?: boolean;
}

export const alertsApi = {
  list: (params: AlertListParams = {}) =>
    api
      .get("alerts/", { searchParams: cleanParams({ ...params }) })
      .json<AlertListResponse>(),

  acknowledge: (id: string) =>
    api.put(`alerts/${id}/acknowledge`).json<AlertAckResult>(),

  resolve: (id: string) =>
    api.put(`alerts/${id}/resolve`).json<AlertResolveResult>(),
};
