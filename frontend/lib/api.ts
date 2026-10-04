/**
 * Thin client for the Flask API. Requests go to same-origin /api/* (proxied by Next.js),
 * carry the HttpOnly session cookie automatically, and send the CSRF token on writes.
 */

export interface PageMeta {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Field-level validation messages, keyed by field name. */
  get fieldErrors(): Record<string, string> {
    return this.code === "VALIDATION_ERROR" && this.details && typeof this.details === "object"
      ? (this.details as Record<string, string>)
      : {};
  }
}

let csrfToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function onUnauthorized(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

async function request<T>(method: Method, path: string, body?: unknown): Promise<{ data: T; meta?: PageMeta }> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Unable to reach the server. Check your connection and try again.", 0);
  }

  let payload: { success?: boolean; data?: T; meta?: PageMeta; error?: { code: string; message: string; details?: unknown } } | null = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok || !payload?.success) {
    const error = payload?.error;
    if (response.status === 401 && unauthorizedHandler && !path.startsWith("/auth/login")) {
      unauthorizedHandler();
    }
    if (!error) {
      const message = response.status >= 500 || response.status === 0
        ? "The server is unavailable right now. Please try again shortly."
        : "The request could not be completed.";
      throw new ApiError("HTTP_" + response.status, message, response.status);
    }
    throw new ApiError(error.code, error.message, response.status, error.details);
  }
  return { data: payload.data as T, meta: payload.meta };
}

function query(params?: Record<string, string | number | boolean | null | undefined>): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  get: async <T>(path: string, params?: Record<string, string | number | boolean | null | undefined>) =>
    (await request<T>("GET", path + query(params))).data,
  page: <T>(path: string, params?: Record<string, string | number | boolean | null | undefined>) =>
    request<T>("GET", path + query(params)),
  post: async <T>(path: string, body?: unknown) => (await request<T>("POST", path, body)).data,
  put: async <T>(path: string, body?: unknown) => (await request<T>("PUT", path, body)).data,
  del: async <T>(path: string) => (await request<T>("DELETE", path)).data,
};

export function errorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}
