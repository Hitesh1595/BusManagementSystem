import { api } from "./client";
import type {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
  UpdateMePayload,
  User,
} from "./types";

export const authApi = {
  login: (payload: LoginPayload) =>
    api.post("auth/login", { json: payload }).json<TokenResponse>(),

  register: (payload: RegisterPayload) =>
    api.post("auth/register", { json: payload }).json<TokenResponse>(),

  logout: () => api.post("auth/logout").json<{ ok: boolean }>(),

  me: () => api.get("auth/me").json<User>(),

  updateMe: (payload: UpdateMePayload) =>
    api.put("auth/me", { json: payload }).json<User>(),

  forgotPassword: (email: string) =>
    api.post("auth/forgot-password", { json: { email } }).json<{ ok: boolean }>(),

  resetPassword: (token: string, newPassword: string) =>
    api
      .post("auth/reset-password", { json: { token, new_password: newPassword } })
      .json<{ ok: boolean }>(),
};
