import type { ApiEnvelope } from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  "http://127.0.0.1:8000/api";
const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined)?.trim() || "";

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly requestId?: string;
  public readonly details?: unknown;

  constructor(params: {
    code: string;
    message: string;
    status: number;
    requestId?: string;
    details?: unknown;
  }) {
    super(params.message);
    this.code = params.code;
    this.status = params.status;
    this.requestId = params.requestId;
    this.details = params.details;
  }
}

function buildHeaders(initHeaders?: HeadersInit, body?: BodyInit | null): Headers {
  const headers = new Headers(initHeaders || {});
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (!headers.has("Content-Type") && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  if (API_KEY && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", API_KEY);
  }
  return headers;
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: buildHeaders(init?.headers, init?.body),
  });

  let payload: ApiEnvelope<T> | null = null;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    // no-op: fallback to generic error below
  }

  if (!payload) {
    throw new ApiClientError({
      code: "INTERNAL_ERROR",
      message: `invalid API response (${response.status})`,
      status: response.status,
    });
  }

  if (!payload.success) {
    throw new ApiClientError({
      code: payload.error.code,
      message: payload.error.message,
      status: response.status,
      requestId: payload.requestId,
      details: payload.error.details,
    });
  }

  return payload.data;
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
