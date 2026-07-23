import type {
  AccountCreateRequest,
  AccountView,
  AdminSummary,
  AISettingSlot,
  AISettingUpdate,
  AISettingsView,
  ApiResponse,
  ImageCopyRequest,
  ImageCopyResult,
  TaskCreateRequest,
  TaskView,
  VideoEditJobClaimRequest,
  VideoEditJobCreate,
  VideoEditJobDeliverRequest,
  VideoEditJobView
} from "../types";


const API_BASE = "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = window.localStorage.getItem("karries_access_token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init?.headers || {})
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers
  });
  const body = (await response.json()) as ApiResponse<T>;
  if (!response.ok || !body.success) {
    throw new Error(body.error?.message || `请求失败: ${path}`);
  }
  return body.data;
}


export const api = {
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
  getAISettings: () => request<AISettingsView>("/api/settings/ai"),
  saveAISetting: (slot: AISettingSlot, payload: AISettingUpdate) =>
    request<AISettingsView>(`/api/settings/ai/${slot}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  clearAISettingKey: (slot: AISettingSlot) =>
    request<AISettingsView>(`/api/settings/ai/${slot}/key`, {
      method: "DELETE"
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
  listInternalVideoEditJobs: () =>
    request<VideoEditJobView[]>("/api/internal/video-edit/jobs"),
  claimInternalVideoEditJob: (jobId: number, payload: VideoEditJobClaimRequest) =>
    request<VideoEditJobView>(`/api/internal/video-edit/jobs/${jobId}/claim`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deliverInternalVideoEditJob: (jobId: number, payload: VideoEditJobDeliverRequest) =>
    request<VideoEditJobView>(`/api/internal/video-edit/jobs/${jobId}/deliver`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getAdminSummary: () => request<AdminSummary>("/api/admin/summary")
};
