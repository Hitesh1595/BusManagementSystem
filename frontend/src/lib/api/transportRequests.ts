import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  Page,
  StopSuggestion,
  TransportRequest,
  TransportRequestCreatePayload,
  TransportRequestStatus,
  TransportRequestUpdatePayload,
} from "./types";

export const transportRequestsApi = {
  suggestStop: (params: { lat?: number; lng?: number; address?: string }) =>
    api
      .get("transport-requests/suggest-stop", {
        searchParams: cleanParams({ ...params }),
      })
      .json<{ suggestions: StopSuggestion[] }>(),

  list: (params: { status?: TransportRequestStatus } & PageParams = {}) =>
    api
      .get("transport-requests/", { searchParams: cleanParams({ ...params }) })
      .json<Page<TransportRequest>>(),

  get: (id: string) =>
    api.get(`transport-requests/${id}`).json<TransportRequest>(),

  create: (payload: TransportRequestCreatePayload) =>
    api.post("transport-requests/", { json: payload }).json<TransportRequest>(),

  update: (id: string, payload: TransportRequestUpdatePayload) =>
    api
      .put(`transport-requests/${id}`, { json: payload })
      .json<TransportRequest>(),
};
