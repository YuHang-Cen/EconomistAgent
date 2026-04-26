import type { ApiEnvelope } from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  "/api";
const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined)?.trim() || "";
const TRANSIENT_HTTP_STATUS = new Set([502, 503, 504]);
const RETRY_MAX_ATTEMPTS = 5;
const RETRY_BASE_DELAY_MS = 300;

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

function getRequestMethod(init?: RequestInit): string {
  return (init?.method || "GET").toUpperCase();
}

function isRetryableRequest(init?: RequestInit): boolean {
  const method = getRequestMethod(init);
  return method === "GET" || method === "HEAD";
}

function shouldRetryResponse(response: Response, init?: RequestInit): boolean {
  return isRetryableRequest(init) && TRANSIENT_HTTP_STATUS.has(response.status);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithRetry(url: string, init?: RequestInit): Promise<Response> {
  for (let attempt = 1; attempt <= RETRY_MAX_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(url, init);
      if (shouldRetryResponse(response, init) && attempt < RETRY_MAX_ATTEMPTS) {
        await sleep(RETRY_BASE_DELAY_MS * attempt);
        continue;
      }
      return response;
    } catch (error) {
      if (!isRetryableRequest(init) || attempt >= RETRY_MAX_ATTEMPTS) {
        throw error;
      }
      await sleep(RETRY_BASE_DELAY_MS * attempt);
    }
  }
  throw new Error("unreachable");
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const requestInit: RequestInit = {
    ...init,
    headers: buildHeaders(init?.headers, init?.body),
  };
  const url = `${API_BASE_URL}${path}`;

  let response: Response;
  try {
    response = await fetchWithRetry(url, requestInit);
  } catch (error) {
    throw new ApiClientError({
      code: "NETWORK_ERROR",
      message: error instanceof Error ? error.message : "network request failed",
      status: 0,
    });
  }

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
