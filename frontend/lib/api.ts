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
      cache: "no-store",
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "TimeoutError") {
      throw new ApiError("The server took too long to respond. Please try again.", 0);
    }
    throw new ApiError("Could not reach Niramaya-AI. Check that the API server is running and try again.", 0);
  }
  const payload = (await response.json().catch(() => ({}))) as ApiErrorBody & T;
  if (!response.ok) {
    const message = response.status === 401
      ? "Your session has expired. Please sign in again."
      : response.status === 403
        ? "You don’t have permission to access this information."
        : payload.error?.message || payload.detail || "The information could not be loaded. Please try again.";
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

async function authenticatedRequest<T>(path: string, token: string, init: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", Authorization: `Bearer ${token}`, ...init.headers },
      signal: AbortSignal.timeout(timeoutMs),
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Could not reach Niramaya-AI. Check that the API server is running and try again.", 0);
  }
  const payload = response.status === 204 ? undefined : await response.json().catch(() => ({}));
  if (!response.ok) {
    const body = payload as ApiErrorBody;
    const message = response.status === 401
      ? "Your session has expired. Please sign in again."
      : response.status === 403
        ? "You don’t have permission to complete this action."
        : response.status === 422
          ? body.error?.message || body.detail || "Check the question and selected documents, then try again."
          : response.status === 429
            ? "You’ve sent questions too quickly. Wait a moment, then retry."
        : body.error?.message || body.detail || "The request could not be completed. Please try again.";
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

export type MedicalDocument = {
  id: string; original_filename: string; document_type: string; content_type: string;
  file_size: number; upload_status: "ready" | "deleting";
  processing_state: "uploaded" | "queued" | "processing" | "review_required" | "completed" | "failed" | "deletion_pending";
  processing_version: number; created_at: string; updated_at: string;
};
export type IndexingStatus = { document_id: string; extraction_generation: number; status: string; chunk_count: number; model: string | null; dimension: number | null; attempts: number; updated_at: string | null; error_code: string | null };
export type ProcessingStageResult = { stage: string; status: string; attempts: number; reason_code: string | null; started_at: string | null; finished_at: string | null };
export type ProcessingStatus = { document_id: string; document_type: string; processing_state: string; processing_version: number; processing_generation: number; processing_updated_at: string; processing: Record<string, unknown>; stages: ProcessingStageResult[] };
export type ExtractedEntity = { id: string; category: string; name: string; original_name: string | null; value: string | null; numeric_value: number | null; unit: string | null; normalized_value: string | null; normalized_unit: string | null; reference_range: string | null; reported_abnormal: boolean | null; qualitative_value: string | null; page_number: number | null; source_excerpt: string | null; extraction_method: string; rule_id: string | null; quality_score: number | null; warnings: string[]; review_status: string };
export type ExtractedEntities = { document_id: string; generation: number; items: ExtractedEntity[] };
export type ExtractedPage = { page_number: number; extracted_text: string; extraction_method: string; character_count: number; ocr_required: boolean; ocr_status: string; warnings: string[] };
export type ExtractedPages = { document_id: string; generation: number; total: number; limit: number; offset: number; items: ExtractedPage[] };
export type ExtractedTable = { page_number: number; table_index: number; headers: string[]; rows: string[][]; extraction_method: string; warnings: string[] };
export type ExtractedTables = { document_id: string; generation: number; items: ExtractedTable[] };
export type ProcessingHistory = { document_id: string; generation: number; events: { previous_state: string; next_state: string; processing_stage: string | null; actor: string; reason_code: string; state_version: number; created_at: string }[]; stages: ProcessingStageResult[]; job_status: string | null; error_code: string | null };
export type ProcessingState = MedicalDocument["processing_state"];
export const processingStateLabels: Record<ProcessingState, string> = {
  uploaded: "Uploaded",
  queued: "Waiting to be processed",
  processing: "Processing document",
  review_required: "Needs your review",
  completed: "Processing complete",
  failed: "Processing failed",
  deletion_pending: "Deletion in progress",
};
export type DocumentPage = {
  items: MedicalDocument[]; total: number; limit: number; offset: number;
  summary: { total_reports: number; blood_tests: number; imaging_reports: number; recent_uploads: number };
};
export type PresignedDocumentUrl = { url: string; expires_in: number };
export type DocumentMetadata = { id: string; name: string; document_type: string; document_date: string | null };
export type Citation = { document_id: string; document_name: string; page_number: number | null };
export type EvidenceItem = Citation & { excerpt: string };
export type HealthAnswer = { answer: string; citations: Citation[]; evidence: EvidenceItem[]; generation_status: "generated" | "evidence_only" | "insufficient_evidence" };
export type ChatHistoryItem = { id: string; question: string; answer: string; citations: Citation[]; created_at: string; generation_status?: string };
export type DocumentFilters = { q?: string; document_type?: string; date_from?: string; date_to?: string; sort?: "newest" | "oldest"; limit?: number; offset?: number };

function queryString(filters: DocumentFilters): string {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") query.set(key, String(value)); });
  const value = query.toString();
  return value ? `?${value}` : "";
}

function uploadDocument(token: string, file: File, documentType: string, onProgress: (percent: number) => void): Promise<MedicalDocument> {
  return new Promise((resolve, reject) => {
    const data = new FormData();
    data.append("file", file);
    data.append("document_type", documentType);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/v1/documents/upload`);
    xhr.timeout = 120_000;
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100)); };
    xhr.onerror = () => reject(new ApiError("Could not reach Niramaya-AI. Check that the API server is running and try again.", 0));
    xhr.ontimeout = () => reject(new ApiError("The upload timed out. Check your connection and retry the report.", 0));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as MedicalDocument);
      else reject(new ApiError(xhr.response?.error?.message || "The report could not be uploaded. Please try again.", xhr.status));
    };
    xhr.send(data);
  });
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

export const documentsApi = {
  list: (token: string, filters: DocumentFilters = {}) => authenticatedGet<DocumentPage>(`/api/v1/documents${queryString(filters)}`, token),
  get: (token: string, id: string) => authenticatedGet<MedicalDocument>(`/api/v1/documents/${id}`, token),
  status: (token: string, id: string) => authenticatedGet<ProcessingStatus>(`/api/v1/documents/${id}/status`, token),
  extractions: (token: string, id: string) => authenticatedGet<ExtractedEntities>(`/api/v1/documents/${id}/extractions`, token),
  pages: (token: string, id: string) => authenticatedGet<ExtractedPages>(`/api/v1/documents/${id}/pages`, token),
  tables: (token: string, id: string) => authenticatedGet<ExtractedTables>(`/api/v1/documents/${id}/tables`, token),
  history: (token: string, id: string) => authenticatedGet<ProcessingHistory>(`/api/v1/documents/${id}/history`, token),
  indexingStatus: (token: string, id: string) => authenticatedGet<IndexingStatus>(`/api/v1/documents/${id}/indexing-status`, token),
  reindex: (token: string, id: string) => authenticatedRequest<IndexingStatus>(`/api/v1/documents/${id}/reindex`, token, { method: "POST" }),
  metadata: (token: string, id: string) => authenticatedGet<DocumentMetadata>(`/api/v1/health/documents/${id}`, token),
  upload: uploadDocument,
  viewUrl: (token: string, id: string) => authenticatedGet<PresignedDocumentUrl>(`/api/v1/documents/${id}/view-url`, token),
  downloadUrl: (token: string, id: string) => authenticatedGet<PresignedDocumentUrl>(`/api/v1/documents/${id}/download-url`, token),
  remove: (token: string, id: string) => authenticatedRequest<void>(`/api/v1/documents/${id}`, token, { method: "DELETE" }),
  reprocess: (token: string, id: string) => authenticatedRequest<MedicalDocument>(`/api/v1/documents/${id}/reprocess`, token, { method: "POST" }),
  completeReview: (token: string, id: string) => authenticatedRequest<MedicalDocument>(`/api/v1/documents/${id}/review/complete`, token, { method: "POST" }),
};

export const healthApi = {
  ask: (token: string, question: string, documentIds?: string[]) => authenticatedRequest<HealthAnswer>("/api/v1/health/ask", token, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, ...(documentIds ? { document_ids: documentIds } : {}) }),
  }, 110_000),
  history: (token: string) => authenticatedGet<ChatHistoryItem[]>("/api/v1/health/history", token),
};
