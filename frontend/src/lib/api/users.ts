import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type { ManagedUser, Page, Role } from "./types";

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

  resetPassword: (id: string, newPassword: string) =>
    api
      .post(`users/${id}/reset-password`, { json: { new_password: newPassword } })
      .json<{ status: string }>(),
};
