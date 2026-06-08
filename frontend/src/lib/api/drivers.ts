import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  Driver,
  DriverCreatePayload,
  DriverCreateResult,
  DriverUpdatePayload,
  Page,
} from "./types";

export const driversApi = {
  list: (params: PageParams = {}) =>
    api
      .get("drivers/", { searchParams: cleanParams({ ...params }) })
      .json<Page<Driver>>(),

  get: (id: string) => api.get(`drivers/${id}`).json<Driver>(),

  create: (payload: DriverCreatePayload) =>
    api.post("drivers/", { json: payload }).json<DriverCreateResult>(),

  update: (id: string, payload: DriverUpdatePayload) =>
    api.put(`drivers/${id}`, { json: payload }).json<Driver>(),

  assignVehicle: (id: string, vehicleId: string) =>
    api
      .post(`drivers/${id}/assign`, { json: { vehicle_id: vehicleId } })
      .json<{ status: string }>(),
};
