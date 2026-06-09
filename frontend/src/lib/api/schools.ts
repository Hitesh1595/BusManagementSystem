import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  Page,
  School,
  SchoolCreatePayload,
  SchoolSettings,
  SchoolUpdatePayload,
} from "./types";

export interface SchoolListParams extends PageParams {
  /** Filter by name (super_admin console). */
  q?: string;
}

export const schoolsApi = {
  get: (id: string) => api.get(`schools/${id}`).json<School>(),

  /** super_admin: list all schools. */
  list: (params: SchoolListParams = {}) =>
    api
      .get("schools/", { searchParams: cleanParams({ ...params }) })
      .json<Page<School>>(),

  /** super_admin: create a school (join code auto-generated). */
  create: (payload: SchoolCreatePayload) =>
    api.post("schools/", { json: payload }).json<School>(),

  update: (id: string, payload: SchoolUpdatePayload) =>
    api.put(`schools/${id}`, { json: payload }).json<School>(),

  updateSettings: (id: string, settings: SchoolSettings) =>
    api.put(`schools/${id}/settings`, { json: settings }).json<School>(),

  regenerateJoinCode: (id: string) =>
    api
      .post(`schools/${id}/regenerate-join-code`)
      .json<{ join_code: string }>(),
};
