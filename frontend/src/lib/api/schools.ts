import { api } from "./client";
import type { School, SchoolSettings, SchoolUpdatePayload } from "./types";

export const schoolsApi = {
  get: (id: string) => api.get(`schools/${id}`).json<School>(),

  update: (id: string, payload: SchoolUpdatePayload) =>
    api.put(`schools/${id}`, { json: payload }).json<School>(),

  updateSettings: (id: string, settings: SchoolSettings) =>
    api.put(`schools/${id}/settings`, { json: settings }).json<School>(),

  regenerateJoinCode: (id: string) =>
    api
      .post(`schools/${id}/regenerate-join-code`)
      .json<{ join_code: string }>(),
};
