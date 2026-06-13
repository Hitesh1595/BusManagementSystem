import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  Complaint,
  ComplaintCreatePayload,
  ComplaintStatus,
  Page,
} from "./types";

export interface ComplaintListParams extends PageParams {
  status?: ComplaintStatus;
  priority?: string;
}

export const complaintsApi = {
  /** Parent/driver/admin file a complaint. */
  create: (payload: ComplaintCreatePayload) =>
    api.post("complaints/", { json: payload }).json<Complaint>(),

  /** Admin sees all in-school; others see only their own. */
  list: (params: ComplaintListParams = {}) =>
    api
      .get("complaints/", { searchParams: cleanParams({ ...params }) })
      .json<Page<Complaint>>(),

  get: (id: string) => api.get(`complaints/${id}`).json<Complaint>(),

  assign: (id: string, assignedTo: string) =>
    api
      .put(`complaints/${id}/assign`, { json: { assigned_to: assignedTo } })
      .json<Complaint>(),

  resolve: (id: string, notes?: string) =>
    api.put(`complaints/${id}/resolve`, { json: { notes } }).json<Complaint>(),

  setStatus: (id: string, status: ComplaintStatus) =>
    api.put(`complaints/${id}/status`, { json: { status } }).json<Complaint>(),
};
