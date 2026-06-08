/**
 * HTTP client. ky instance pointed at /api/v1 (same-origin via Vite proxy in
 * dev). Access token is attached from an in-memory holder; on 401 we attempt a
 * single silent refresh (httpOnly cookie) and retry the original request once.
 */
import ky, { HTTPError } from "ky";
import type { ApiErrorBody } from "./types";

// ---------------------------------------------------------------------------
// In-memory access token (kept out of localStorage; refresh cookie is httpOnly)
// ---------------------------------------------------------------------------

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

let onUnauthorized: () => void = () => {};

/** Registered by the auth store so the client can force a logout on hard 401. */
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

// ---------------------------------------------------------------------------
// Silent refresh (deduplicated so concurrent 401s share one refresh round-trip)
// ---------------------------------------------------------------------------

let refreshPromise: Promise<string | null> | null = null;

async function rawRefresh(): Promise<string | null> {
  try {
    const res = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token?: string };
    if (data.access_token) {
      setAccessToken(data.access_token);
      return data.access_token;
    }
    return null;
  } catch {
    return null;
  }
}

export function refreshSession(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = rawRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

const NO_REFRESH = ["auth/login", "auth/register", "auth/refresh", "auth/forgot-password", "auth/reset-password"];

// ---------------------------------------------------------------------------
// ky instance
// ---------------------------------------------------------------------------

export const api = ky.create({
  prefixUrl: "/api/v1",
  credentials: "include",
  retry: 0,
  timeout: 20_000,
  hooks: {
    beforeRequest: [
      (request) => {
        if (accessToken) {
          request.headers.set("Authorization", `Bearer ${accessToken}`);
        }
      },
    ],
    afterResponse: [
      async (request, options, response) => {
        if (response.status !== 401) return response;

        const path = new URL(request.url).pathname;
        if (NO_REFRESH.some((p) => path.includes(p))) return response;
        if (request.headers.get("x-retried") === "1") {
          onUnauthorized();
          return response;
        }

        const newToken = await refreshSession();
        if (!newToken) {
          onUnauthorized();
          return response;
        }

        request.headers.set("Authorization", `Bearer ${newToken}`);
        request.headers.set("x-retried", "1");
        return ky(request, options);
      },
    ],
  },
});

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

export interface ParsedApiError {
  status: number;
  code: string;
  message: string;
  details?: unknown;
}

/** Extract the backend error envelope from a thrown ky HTTPError. */
export async function parseApiError(error: unknown): Promise<ParsedApiError> {
  if (error instanceof HTTPError) {
    const status = error.response.status;
    try {
      const body = (await error.response.clone().json()) as ApiErrorBody;
      if (body?.error) {
        return {
          status,
          code: body.error.code,
          message: body.error.message,
          details: body.error.details,
        };
      }
    } catch {
      /* fall through */
    }
    return { status, code: "http_error", message: defaultMessage(status) };
  }
  if (error instanceof Error) {
    return { status: 0, code: "network_error", message: error.message || "Network error" };
  }
  return { status: 0, code: "unknown", message: "Something went wrong" };
}

/** Convenience for toast/messages — best-effort synchronous-ish message. */
export async function getErrorMessage(error: unknown): Promise<string> {
  return (await parseApiError(error)).message;
}

function defaultMessage(status: number): string {
  switch (status) {
    case 401:
      return "Your session has expired. Please sign in again.";
    case 403:
      return "You don't have permission to do that.";
    case 404:
      return "Not found.";
    case 409:
      return "That conflicts with existing data.";
    case 422:
      return "Please check the form for errors.";
    case 423:
      return "Account locked due to too many attempts. Try again later.";
    case 429:
      return "Too many requests. Please slow down and try again.";
    case 503:
      return "Service temporarily unavailable.";
    default:
      return "Something went wrong. Please try again.";
  }
}

export { HTTPError };
