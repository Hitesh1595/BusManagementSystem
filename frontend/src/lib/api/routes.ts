import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  Page,
  Route,
  RouteCreatePayload,
  RouteUpdatePayload,
  Stop,
  StopCreatePayload,
  StopUpdatePayload,
  StudentRouteAssignment,
} from "./types";

export const routesApi = {
  list: (params: PageParams = {}) =>
    api
      .get("routes/", { searchParams: cleanParams({ ...params }) })
      .json<Page<Route>>(),

  get: (id: string) => api.get(`routes/${id}`).json<Route>(),

  create: (payload: RouteCreatePayload) =>
    api.post("routes/", { json: payload }).json<Route>(),

  update: (id: string, payload: RouteUpdatePayload) =>
    api.put(`routes/${id}`, { json: payload }).json<Route>(),

  remove: (id: string) => api.delete(`routes/${id}`).then(() => undefined),

  // Stops
  addStop: (routeId: string, payload: StopCreatePayload) =>
    api.post(`routes/${routeId}/stops`, { json: payload }).json<Stop>(),

  reorderStops: (routeId: string, orderedStopIds: string[]) =>
    api
      .put(`routes/${routeId}/stops/reorder`, {
        json: { ordered_stop_ids: orderedStopIds },
      })
      .json<Stop[]>(),

  updateStop: (routeId: string, stopId: string, payload: StopUpdatePayload) =>
    api
      .put(`routes/${routeId}/stops/${stopId}`, { json: payload })
      .json<Stop>(),

  deleteStop: (routeId: string, stopId: string) =>
    api.delete(`routes/${routeId}/stops/${stopId}`).then(() => undefined),

  // Student assignments
  listStudents: (routeId: string, params: PageParams = {}) =>
    api
      .get(`routes/${routeId}/students`, {
        searchParams: cleanParams({ ...params }),
      })
      .json<Page<StudentRouteAssignment>>(),

  assignStudent: (routeId: string, studentId: string, stopId: string) =>
    api
      .post(`routes/${routeId}/students`, {
        json: { student_id: studentId, stop_id: stopId },
      })
      .json<StudentRouteAssignment>(),
};
