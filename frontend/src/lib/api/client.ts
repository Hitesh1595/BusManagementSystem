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
  /** field name → message, parsed from a 422 validation envelope. */
  fieldErrors?: Record<string, string>;
}

/** One FastAPI/pydantic validation entry: { loc: [...], msg, type }. */
interface ValidationItem {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
}

function prettifyField(field: string): string {
  const spaced = field.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Pull per-field errors out of our 422 envelope
 * ({ error: { details: { errors: [{ loc, msg }] } } }). The leading
 * body/query/path segment of `loc` is dropped so the key is the field name.
 */
function parseValidationDetails(details: unknown): {
  summary?: string;
  fieldErrors: Record<string, string>;
} {
  const fieldErrors: Record<string, string> = {};
  let summary: string | undefined;
  const errors = (details as { errors?: ValidationItem[] } | null | undefined)
    ?.errors;
  if (Array.isArray(errors)) {
    for (const e of errors) {
      const loc = Array.isArray(e.loc) ? e.loc : [];
      const field = String(loc[loc.length - 1] ?? "");
      const msg = e.msg ?? "Invalid value";
      if (field && !(field in fieldErrors)) fieldErrors[field] = msg;
      if (!summary) summary = field ? `${prettifyField(field)}: ${msg}` : msg;
    }
  }
  return { summary, fieldErrors };
}

/** Extract the backend error envelope from a thrown ky HTTPError. */
export async function parseApiError(error: unknown): Promise<ParsedApiError> {
  if (error instanceof HTTPError) {
    const status = error.response.status;
    try {
      const body = (await error.response.clone().json()) as ApiErrorBody;
      if (body?.error) {
        const parsed: ParsedApiError = {
          status,
          code: body.error.code,
          message: body.error.message,
          details: body.error.details,
        };
        // 422: replace the generic "Invalid input" with the actual field
        // problem(s) so toasts and forms can show what's wrong.
        if (status === 422) {
          const { summary, fieldErrors } = parseValidationDetails(
            body.error.details,
          );
          if (Object.keys(fieldErrors).length > 0) parsed.fieldErrors = fieldErrors;
          if (summary) parsed.message = summary;
        }
        return parsed;
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

/** Per-field validation errors from a 422, for inline form display. */
export async function getFieldErrors(
  error: unknown,
): Promise<Record<string, string>> {
  return (await parseApiError(error)).fieldErrors ?? {};
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
