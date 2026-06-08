import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  Page,
  Student,
  StudentCreatePayload,
  StudentUpdatePayload,
} from "./types";

export const studentsApi = {
  list: (params: PageParams = {}) =>
    api
      .get("students/", { searchParams: cleanParams({ ...params }) })
      .json<Page<Student>>(),

  get: (id: string) => api.get(`students/${id}`).json<Student>(),

  create: (payload: StudentCreatePayload) =>
    api.post("students/", { json: payload }).json<Student>(),

  update: (id: string, payload: StudentUpdatePayload) =>
    api.put(`students/${id}`, { json: payload }).json<Student>(),
};
