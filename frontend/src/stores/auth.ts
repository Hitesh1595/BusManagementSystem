import { create } from "zustand";
import { authApi } from "@/lib/api/auth";
import {
  refreshSession,
  setAccessToken,
  setUnauthorizedHandler,
} from "@/lib/api/client";
import type { LoginPayload, RegisterPayload, User } from "@/lib/api/types";
import { connectSocket, disconnectSocket } from "@/lib/socket";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  user: User | null;
  status: AuthStatus;
  /** Called once on app load: silently restore a session from the refresh cookie. */
  bootstrap: () => Promise<void>;
  login: (payload: LoginPayload) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: "loading",

  bootstrap: async () => {
    const token = await refreshSession();
    if (!token) {
      set({ user: null, status: "unauthenticated" });
      return;
    }
    try {
      const user = await authApi.me();
      set({ user, status: "authenticated" });
      connectSocket();
    } catch {
      setAccessToken(null);
      set({ user: null, status: "unauthenticated" });
    }
  },

  login: async (payload) => {
    const { access_token, user } = await authApi.login(payload);
    setAccessToken(access_token);
    set({ user, status: "authenticated" });
    connectSocket();
    return user;
  },

  register: async (payload) => {
    const { access_token, user } = await authApi.register(payload);
    setAccessToken(access_token);
    set({ user, status: "authenticated" });
    connectSocket();
    return user;
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch {
      /* best-effort; clear locally regardless */
    }
    setAccessToken(null);
    disconnectSocket();
    set({ user: null, status: "unauthenticated" });
  },

  setUser: (user) => set({ user }),
}));

// A hard 401 (silent refresh failed) forces the app back to signed-out state.
setUnauthorizedHandler(() => {
  setAccessToken(null);
  disconnectSocket();
  useAuthStore.setState({ user: null, status: "unauthenticated" });
});
