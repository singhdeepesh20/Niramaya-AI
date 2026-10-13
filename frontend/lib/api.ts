const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 15_000;

function requestTimeoutSignal(): AbortSignal {
  return AbortSignal.timeout(REQUEST_TIMEOUT_MS);
}

type ApiErrorBody = {
  error?: { message?: string; fields?: Array<{ location?: Array<string | number>; message?: string }> };
  detail?: string;
};

export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;

  constructor(message: string, status: number, fields: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

async function request<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      signal: requestTimeoutSignal(),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "TimeoutError") {
      throw new ApiError("The server took too long to respond. Check the API and database, then try again.", 0);
    }
    throw new ApiError("Could not reach Niramaya-AI. Check that the API server is running and try again.", 0);
  }

  const payload = (await response.json().catch(() => ({}))) as ApiErrorBody & T;
  if (!response.ok) {
    const fields: Record<string, string> = {};
    for (const field of payload.error?.fields || []) {
      const key = field.location?.at(-1);
      if (typeof key === "string" && field.message) fields[key] = field.message;
    }
    const message = response.status === 409
      ? "An account with that username or email already exists."
      : response.status === 401
        ? "The username or password isn’t correct."
        : payload.error?.message || payload.detail || "The request could not be completed. Please try again.";
    throw new ApiError(message, response.status, fields);
  }
  return payload as T;
}

async function authenticatedGet<T>(path: string, token: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
      signal: requestTimeoutSignal(),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "TimeoutError") {
      throw new ApiError("The server took too long to respond. Please try again.", 0);
    }
    throw new ApiError("Could not reach Niramaya-AI. Check that the API server is running and try again.", 0);
  }
  const payload = (await response.json().catch(() => ({}))) as ApiErrorBody & T;
  if (!response.ok) {
    throw new ApiError(payload.error?.message || "Your session could not be verified. Please sign in again.", response.status);
  }
  return payload as T;
}

export type RegisterInput = { username: string; email: string; password: string };
export type LoginInput = { username: string; password: string };
export type User = { id: string; username: string; email: string; is_active: boolean };
export type TokenResponse = { access_token: string; token_type: "bearer"; expires_in: number };

export const authApi = {
  register: (input: RegisterInput) => request<User>("/api/v1/users/register", input),
  login: (input: LoginInput) => request<TokenResponse>("/api/v1/users/login", input),
  me: (token: string) => authenticatedGet<User>("/api/v1/users/me", token),
};
