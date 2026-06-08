import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  AbsenceListItem,
  AbsentMarkResult,
  AttendanceInput,
  AttendanceRecord,
  AttendanceResult,
  DropPayload,
  DropResult,
  EndTripResult,
  GenerateResult,
  GpsLogGeoJSON,
  Page,
  Stop,
  Trip,
  TripCreatePayload,
  TripDetail,
  TripStatus,
} from "./types";

export interface TripListParams extends PageParams {
  date?: string;
  route_id?: string;
  status?: TripStatus;
}

export const tripsApi = {
  create: (payload: TripCreatePayload) =>
    api.post("trips/", { json: payload }).json<Trip>(),

  generate: (scheduledDate: string) =>
    api
      .post("trips/generate", { json: { scheduled_date: scheduledDate } })
      .json<GenerateResult>(),

  listActive: () => api.get("trips/active").json<Trip[]>(),

  list: (params: TripListParams = {}) =>
    api
      .get("trips/", { searchParams: cleanParams({ ...params }) })
      .json<Page<Trip>>(),

  get: (id: string) => api.get(`trips/${id}`).json<TripDetail>(),

  gpsLog: (id: string) => api.get(`trips/${id}/gps-log`).json<GpsLogGeoJSON>(),

  /** Ordered stops of the trip's route (driver run-trip + parent live-track). */
  stops: (id: string) => api.get(`trips/${id}/stops`).json<Stop[]>(),

  // Driver actions
  start: (id: string) => api.put(`trips/${id}/start`).json<Trip>(),

  end: (id: string) => api.put(`trips/${id}/end`).json<EndTripResult>(),

  drop: (id: string, payload: DropPayload) =>
    api.post(`trips/${id}/drop`, { json: payload }).json<DropResult>(),

  cancel: (id: string) => api.put(`trips/${id}/cancel`).json<Trip>(),

  submitAttendance: (id: string, stopId: string, attendance: AttendanceInput[]) =>
    api
      .post(`trips/${id}/stops/${stopId}/attendance`, { json: { attendance } })
      .json<AttendanceResult>(),

  attendance: (id: string) =>
    api.get(`trips/${id}/attendance`).json<AttendanceRecord[]>(),

  stopAttendance: (id: string, stopId: string) =>
    api.get(`trips/${id}/stops/${stopId}/attendance`).json<AttendanceRecord[]>(),

  absences: (id: string) =>
    api.get(`trips/${id}/absences`).json<AbsenceListItem[]>(),

  // Parent actions
  markAbsent: (id: string, studentId: string) =>
    api.post(`trips/${id}/absent/${studentId}`).json<AbsentMarkResult>(),

  cancelAbsent: (id: string, studentId: string) =>
    api.delete(`trips/${id}/absent/${studentId}`).json<AbsentMarkResult>(),
};
