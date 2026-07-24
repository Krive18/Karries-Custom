import type {
  AccountCreateRequest,
  AccountView,
  AdminSummary,
  ApiResponse,
  ImageCopyRequest,
  ImageCopyResult,
  InspirationMessageCreate,
  InspirationMessageResponse,
  InspirationSession,
  InspirationSessionCreate,
  InspirationSessionDetail,
  AuthUser,
  PaginatedResult,
  TaskCreateRequest,
  TaskView,
  VideoEditJobCreate,
  VideoEditJobView,
  ViralAnalysisJob,
  ViralAnalysisJobCreate,
  ViralAnalysisMaterial,
  XHSAccountCreate,
  XHSAccountView
} from "../types";


const API_BASE = "http://127.0.0.1:8765";

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = window.localStorage.getItem("karries_access_token");
  const isFormData = init?.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init?.headers || {})
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers
  });
  const body = (await response.json()) as ApiResponse<T>;
  if (!response.ok || !body.success) {
    throw new ApiRequestError(
      body.error?.message || `请求失败: ${path}`,
      body.error?.code || "REQUEST_FAILED",
      response.status
    );
  }
  return body.data;
}


export const api = {
  getCurrentUser: () => request<AuthUser>("/api/auth/me"),
  checkRuntime: () => request<Record<string, unknown>>("/api/runtime/check"),
  listAccounts: () => request<AccountView[]>("/api/accounts"),
  createAccount: (payload: AccountCreateRequest) =>
    request<AccountView>("/api/accounts", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listTasks: () => request<TaskView[]>("/api/tasks"),
  createTask: (payload: TaskCreateRequest) =>
    request<TaskView>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  submitTask: (taskId: number) =>
    request<TaskView>(`/api/tasks/${taskId}/submit`, {
      method: "POST"
    }),
  listXHSAccounts: () => request<XHSAccountView[]>("/api/xhs-accounts"),
  createXHSAccount: (payload: XHSAccountCreate) =>
    request<XHSAccountView>("/api/xhs-accounts", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  generateImageCopy: (payload: ImageCopyRequest) =>
    request<ImageCopyResult>("/api/ai/image-copy", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listVideoEditJobs: () => request<VideoEditJobView[]>("/api/video-edit/jobs"),
  createVideoEditJob: (payload: VideoEditJobCreate) =>
    request<VideoEditJobView>("/api/video-edit/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getAdminSummary: () => request<AdminSummary>("/api/admin/summary"),
  listInspirationSessions: (params?: URLSearchParams) =>
    request<PaginatedResult<InspirationSession>>(
      `/api/inspiration/sessions${params?.size ? `?${params.toString()}` : ""}`
    ),
  createInspirationSession: (payload: InspirationSessionCreate) =>
    request<InspirationSession>("/api/inspiration/sessions", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getInspirationSession: (sessionId: number) =>
    request<InspirationSessionDetail>(`/api/inspiration/sessions/${sessionId}`),
  sendInspirationMessage: (sessionId: number, payload: InspirationMessageCreate) =>
    request<InspirationMessageResponse>(`/api/inspiration/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  saveInspirationMessageDraft: (messageId: number) =>
    request<{ draft_id: number }>(`/api/inspiration/messages/${messageId}/save-draft`, {
      method: "POST"
    }),
  archiveInspirationSession: (sessionId: number) =>
    request<InspirationSession>(`/api/inspiration/sessions/${sessionId}/archive`, {
      method: "POST"
    }),
  listAdminInspirationSessions: (params?: URLSearchParams) =>
    request<PaginatedResult<InspirationSession>>(
      `/api/admin/inspiration/sessions${params?.size ? `?${params.toString()}` : ""}`
    ),
  getAdminInspirationSession: (sessionId: number) =>
    request<InspirationSessionDetail>(`/api/admin/inspiration/sessions/${sessionId}`),
  createViralAnalysisJob: (payload: ViralAnalysisJobCreate) =>
    request<ViralAnalysisJob>("/api/viral-analysis/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listViralAnalysisJobs: (params?: URLSearchParams) =>
    request<PaginatedResult<ViralAnalysisJob>>(
      `/api/viral-analysis/jobs${params?.size ? `?${params.toString()}` : ""}`
    ),
  getViralAnalysisJob: (jobId: number) => request<ViralAnalysisJob>(`/api/viral-analysis/jobs/${jobId}`),
  uploadViralAnalysisMaterial: (jobId: number, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<ViralAnalysisMaterial>(
      `/api/viral-analysis/jobs/${jobId}/upload`,
      { method: "POST", body }
    );
  },
  runViralAnalysisJob: (jobId: number) =>
    request<ViralAnalysisJob>(`/api/viral-analysis/jobs/${jobId}/run`, { method: "POST" }),
  cancelViralAnalysisJob: (jobId: number) =>
    request<ViralAnalysisJob>(`/api/viral-analysis/jobs/${jobId}/cancel`, { method: "POST" }),
  saveViralAnalysisDraft: (jobId: number) =>
    request<{ draft_id: number }>(`/api/viral-analysis/jobs/${jobId}/save-draft`, { method: "POST" }),
  listAdminViralAnalysisJobs: (params?: URLSearchParams) =>
    request<PaginatedResult<ViralAnalysisJob>>(
      `/api/admin/viral-analysis/jobs${params?.size ? `?${params.toString()}` : ""}`
    ),
  getAdminViralAnalysisJob: (jobId: number) =>
    request<ViralAnalysisJob>(`/api/admin/viral-analysis/jobs/${jobId}`)
};
