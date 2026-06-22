import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  ManagedUser,
  Page,
  Role,
  StaffCreatePayload,
  StaffCreateResult,
  UserUpdatePayload,
} from "./types";

export interface UserListParams extends PageParams {
  /** Filter by role. school_admin only ever sees driver/parent; super_admin any. */
  role?: Role;
  /** Search by name or email. */
  q?: string;
  /** super_admin only: restrict to a single school. */
  school?: string;
}

export const usersApi = {
  list: (params: UserListParams = {}) =>
    api
      .get("users/", { searchParams: cleanParams({ ...params }) })
      .json<Page<ManagedUser>>(),

  get: (id: string) => api.get(`users/${id}`).json<ManagedUser>(),

  resetPassword: (id: string, newPassword: string) =>
    api
      .post(`users/${id}/reset-password`, { json: { new_password: newPassword } })
      .json<{ status: string }>(),

  create: (payload: StaffCreatePayload) =>
    api.post("users/", { json: payload }).json<StaffCreateResult>(),

  update: (id: string, payload: UserUpdatePayload) =>
    api.patch(`users/${id}`, { json: payload }).json<ManagedUser>(),

  deactivate: (id: string) =>
    api.post(`users/${id}/deactivate`).json<ManagedUser>(),

  activate: (id: string) => api.post(`users/${id}/activate`).json<ManagedUser>(),
};
