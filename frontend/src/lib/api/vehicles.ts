import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type { Page, Vehicle, VehiclePayload } from "./types";

export const vehiclesApi = {
  list: (params: PageParams = {}) =>
    api
      .get("vehicles/", { searchParams: cleanParams({ ...params }) })
      .json<Page<Vehicle>>(),

  get: (id: string) => api.get(`vehicles/${id}`).json<Vehicle>(),

  create: (payload: VehiclePayload) =>
    api.post("vehicles/", { json: payload }).json<Vehicle>(),

  update: (id: string, payload: Partial<VehiclePayload>) =>
    api.put(`vehicles/${id}`, { json: payload }).json<Vehicle>(),

  remove: (id: string) => api.delete(`vehicles/${id}`).then(() => undefined),
};
