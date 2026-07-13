/**
 * The single choke-point for all backend calls. UI code never calls fetch
 * directly — it imports typed functions from src/api/endpoints.ts, which use
 * this request() helper.
 *
 * Responsibilities:
 *   - Prefix every path with the API base (relative /v1 in dev, proxied by Vite).
 *   - Attach the Bearer token from token storage.
 *   - Parse JSON and surface a typed ApiError with the backend's error_code.
 *   - Signal auth failures (401) so the app can bounce to /login.
 */
import { clearToken, getToken } from "./token";

/** Relative base — Vite dev proxy (and same-origin prod) forwards /v1 to FastAPI. */
const BASE = "";

export class ApiError extends Error {
  status: number;
  /** Stable backend error_code when present (see exceptions/common.AppException). */
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Listeners notified on any 401 so the auth layer can force a logout. */
const unauthorizedHandlers = new Set<() => void>();
export function onUnauthorized(fn: () => void): () => void {
  unauthorizedHandlers.add(fn);
  return () => unauthorizedHandlers.delete(fn);
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Skip the auth header (used by login). */
  anonymous?: boolean;
  signal?: AbortSignal;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, anonymous, signal } = opts;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (!anonymous) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (err) {
    // Network / CORS / server-down: normalize to an ApiError so callers have one shape.
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }

  if (res.status === 401 && !anonymous) {
    clearToken();
    unauthorizedHandlers.forEach((fn) => fn());
  }

  // 204 No Content and other empty bodies.
  const text = await res.text();
  const data = text ? safeJson(text) : undefined;

  if (!res.ok) {
    const detail = extractError(data);
    throw new ApiError(res.status, detail.message, detail.code);
  }

  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Pull a human message + code out of FastAPI / AppException error bodies. */
function extractError(data: unknown): { message: string; code?: string } {
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>;
    // AppException shape: { error_code, message } (possibly nested under detail)
    const detail = (d.detail ?? d) as Record<string, unknown>;
    if (typeof detail === "object" && detail) {
      const message =
        (typeof detail.message === "string" && detail.message) ||
        (typeof d.detail === "string" && d.detail) ||
        undefined;
      const code = typeof detail.error_code === "string" ? detail.error_code : undefined;
      if (message) return { message, code };
    }
    if (typeof d.detail === "string") return { message: d.detail };
  }
  return { message: "Something went wrong. Please try again." };
}
