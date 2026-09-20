import type {
  AIProviderSettings,
  AISettingSlot,
  AISettingTestResult,
  AISettingUpdate,
  AiTranslationTask,
  AuthResponse,
  AuthUser,
  DeveloperBillingCustomer,
  DeveloperAccount,
  DeveloperAlert,
  DeveloperAuditEntry,
  DeveloperCreditGrantResult,
  DeveloperCreditLedgerResult,
  DeveloperCustomerAccount,
  DeveloperPlatformOverview,
  DeveloperPaymentRecordResult,
  DeveloperRechargeOrder,
  DeveloperTenantMembership,
  DeveloperViralAnalysisJob,
  DeveloperViralAnalysisSummary,
  DeveloperUnifiedTask,
  DeveloperFeedbackUpdate,
  LoginRequest,
  MembershipUpgradeOrder,
  PaginatedResult,
  UserFeedback,
  UserCreationRequest,
  VideoEditJobClaimRequest,
  VideoEditJobDeliverRequest,
  VideoEditHistoryEntry,
  VideoEditJobView
} from "../types";
import { setPortalToken } from "../auth/portalSession";
import {
  createPortalBlobRequest,
  createPortalRequest
} from "./httpClient";


const request = createPortalRequest("developer");
const requestBlob = createPortalBlobRequest("developer");


export const developerApi = {
  login: async (payload: LoginRequest) => {
    const result = await request<AuthResponse>("/api/auth/developer/login", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    setPortalToken("developer", result.access_token);
    return result;
  },
  getCurrentUser: () => request<AuthUser>("/api/auth/me"),
  listUserFeedback: (params?: URLSearchParams) =>
    request<PaginatedResult<UserFeedback>>(
      `/api/developer/user-feedback${params?.size ? `?${params.toString()}` : ""}`
    ),
  updateUserFeedback: (feedbackId: number, payload: DeveloperFeedbackUpdate) =>
    request<UserFeedback>(`/api/developer/user-feedback/${feedbackId}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getAISettings: () => request<AIProviderSettings>("/api/settings/ai"),
  updateAISetting: (slot: AISettingSlot, payload: AISettingUpdate) =>
    request<AIProviderSettings>(`/api/settings/ai/${slot}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  clearAISettingKey: (slot: AISettingSlot) =>
    request<AIProviderSettings>(`/api/settings/ai/${slot}/key`, {
      method: "DELETE"
    }),
  testAISetting: (slot: AISettingSlot) =>
    request<AISettingTestResult>(`/api/settings/ai/${slot}/test`, {
      method: "POST"
    }),
  getPlatformOverview: () =>
    request<DeveloperPlatformOverview>("/api/developer/platform/overview"),
  listPlatformTasks: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperUnifiedTask>>(
      `/api/developer/platform/tasks${params?.size ? `?${params.toString()}` : ""}`
    ),
  actOnPlatformTask: (
    taskId: number,
    action: "cancel" | "retry",
    reason: string
  ) => request<Record<string, unknown>>(
    `/api/developer/platform/tasks/matrix_publish/${taskId}/${action}`,
    { method: "POST", body: JSON.stringify({ reason }) }
  ),
  listPlatformAlerts: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperAlert>>(
      `/api/developer/platform/alerts${params?.size ? `?${params.toString()}` : ""}`
    ),
  acknowledgePlatformAlert: (alertId: number, reason: string) =>
    request<DeveloperAlert>(`/api/developer/platform/alerts/${alertId}/acknowledge`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  resolvePlatformAlert: (alertId: number, reason: string) =>
    request<DeveloperAlert>(`/api/developer/platform/alerts/${alertId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  listDeveloperAccounts: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperAccount>>(
      `/api/developer/platform/accounts${params?.size ? `?${params.toString()}` : ""}`
    ),
  createDeveloperAccount: (payload: {
    login_name: string;
    nickname: string;
    password: string;
    role: DeveloperAccount["role"];
  }) => request<DeveloperAccount>("/api/developer/platform/accounts", {
    method: "POST",
    body: JSON.stringify(payload)
  }),
  resetDeveloperAccountPassword: (userId: number, password: string, reason: string) =>
    request<DeveloperAccount>(`/api/developer/platform/accounts/${userId}/password`, {
      method: "PUT",
      body: JSON.stringify({ password, reason })
    }),
  updateDeveloperAccountStatus: (userId: number, status: 1 | 2, reason: string) =>
    request<DeveloperAccount>(`/api/developer/platform/accounts/${userId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, reason })
    }),
  listCustomerAccounts: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperCustomerAccount>>(
      `/api/developer/platform/customer-accounts${params?.size ? `?${params.toString()}` : ""}`
    ),
  updateCustomerAccountStatus: (userId: number, status: 1 | 2, reason: string) =>
    request<DeveloperCustomerAccount>(
      `/api/developer/platform/customer-accounts/${userId}/status`,
      { method: "PATCH", body: JSON.stringify({ status, reason }) }
    ),
  listUserCreationRequests: (status = "") =>
    request<UserCreationRequest[]>(
      `/api/developer/platform/user-creation-requests${status ? `?status=${status}` : ""}`
    ),
  reviewUserCreationRequest: (
    requestId: number,
    action: "approve" | "reject",
    reason: string
  ) => request<UserCreationRequest>(
    `/api/developer/platform/user-creation-requests/${requestId}/${action}`,
    { method: "POST", body: JSON.stringify({ reason }) }
  ),
  listPlatformAuditLogs: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperAuditEntry>>(
      `/api/developer/platform/audit-logs${params?.size ? `?${params.toString()}` : ""}`
    ),
  listVideoEditJobs: (params?: URLSearchParams) =>
    request<VideoEditJobView[]>(
      `/api/internal/video-edit/jobs${params?.size ? `?${params.toString()}` : ""}`
    ),
  claimVideoEditJob: (jobId: number, payload: VideoEditJobClaimRequest) =>
    request<VideoEditJobView>(`/api/internal/video-edit/jobs/${jobId}/claim`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deliverVideoEditJob: (jobId: number, payload: VideoEditJobDeliverRequest) =>
    request<VideoEditJobView>(`/api/internal/video-edit/jobs/${jobId}/deliver`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  uploadVideoEditDelivery: (
    jobId: number,
    files: File[],
    note: string,
    resourceType: "video" | "voiceover" | "subtitle" = "video"
  ) => {
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    body.append("note", note);
    body.append("resource_type", resourceType);
    return request<VideoEditJobView>(
      `/api/internal/video-edit/jobs/${jobId}/delivery/upload`,
      {
        method: "POST",
        body
      }
    );
  },
  getVideoEditMaterialBlob: (jobId: number, assetId: number) =>
    requestBlob(
      `/api/internal/video-edit/jobs/${jobId}/materials/${assetId}/content`
    ),
  getVideoEditMaterialsArchiveBlob: (jobId: number) =>
    requestBlob(`/api/internal/video-edit/jobs/${jobId}/materials/archive`),
  getVideoEditDeliveryVersionBlob: (jobId: number, version: number) =>
    requestBlob(
      `/api/internal/video-edit/jobs/${jobId}/delivery/versions/${version}/content`
    ),
  getVideoEditDeliveryResourceBlob: (
    jobId: number,
    resourceType: "voiceover" | "subtitle",
    version: number
  ) => requestBlob(
    `/api/internal/video-edit/jobs/${jobId}/delivery/resources/${resourceType}/${version}/content`
  ),
  getVideoEditHistory: (jobId: number) =>
    request<VideoEditHistoryEntry[]>(
      `/api/internal/video-edit/jobs/${jobId}/history`
    ),
  listAiTranslationTasks: (params?: URLSearchParams) =>
    request<AiTranslationTask[]>(
      `/api/internal/ai-translations/tasks${params?.size ? `?${params.toString()}` : ""}`
    ),
  getAiTranslationTask: (taskId: number) =>
    request<AiTranslationTask>(`/api/internal/ai-translations/tasks/${taskId}`),
  claimAiTranslationTask: (taskId: number, note = "") =>
    request<AiTranslationTask>(`/api/internal/ai-translations/tasks/${taskId}/claim`, {
      method: "POST",
      body: JSON.stringify({ note })
    }),
  startAiTranslationTask: (taskId: number, note = "") =>
    request<AiTranslationTask>(`/api/internal/ai-translations/tasks/${taskId}/start`, {
      method: "POST",
      body: JSON.stringify({ note })
    }),
  failAiTranslationTask: (taskId: number, note: string) =>
    request<AiTranslationTask>(`/api/internal/ai-translations/tasks/${taskId}/fail`, {
      method: "POST",
      body: JSON.stringify({ note })
    }),
  uploadAiTranslationDelivery: (
    taskId: number,
    files: File[],
    note: string,
    clientRequestId: string,
    resourceType: "video" | "voiceover" | "subtitle" = "video",
    completeDelivery = false
  ) => {
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    body.append("note", note);
    body.append("client_request_id", clientRequestId);
    body.append("resource_type", resourceType);
    body.append("complete_delivery", String(completeDelivery));
    return request<AiTranslationTask>(
      `/api/internal/ai-translations/tasks/${taskId}/delivery/upload`,
      { method: "POST", body }
    );
  },
  completeAiTranslationDelivery: (taskId: number, note = "") =>
    request<AiTranslationTask>(
      `/api/internal/ai-translations/tasks/${taskId}/delivery/complete`,
      { method: "POST", body: JSON.stringify({ note }) }
    ),
  getAiTranslationSourceBlob: (taskId: number) =>
    requestBlob(`/api/internal/ai-translations/tasks/${taskId}/source/content`),
  getAiTranslationDeliveryBlob: (taskId: number, deliveryId: number) =>
    requestBlob(`/api/internal/ai-translations/tasks/${taskId}/deliveries/${deliveryId}/content`),
  listViralAnalysisJobs: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperViralAnalysisSummary>>(
      `/api/developer/viral-analysis/jobs${params?.size ? `?${params.toString()}` : ""}`
    ),
  getViralAnalysisJob: (jobId: number) =>
    request<DeveloperViralAnalysisJob>(`/api/developer/viral-analysis/jobs/${jobId}`),
  listBillingCustomers: (keyword = "") => {
    const params = new URLSearchParams();
    if (keyword.trim()) params.set("keyword", keyword.trim());
    return request<DeveloperBillingCustomer[]>(
      `/api/developer/billing/customers${params.size ? `?${params.toString()}` : ""}`
    );
  },
  listMembershipOrders: (params?: URLSearchParams) =>
    request<PaginatedResult<MembershipUpgradeOrder>>(
      `/api/developer/billing/membership-orders${params?.size ? `?${params.toString()}` : ""}`
    ),
  approveMembershipOrder: (orderId: number) =>
    request<MembershipUpgradeOrder>(
      `/api/developer/billing/membership-orders/${orderId}/approve`,
      { method: "POST" }
    ),
  rejectMembershipOrder: (orderId: number, reason: string) =>
    request<MembershipUpgradeOrder>(
      `/api/developer/billing/membership-orders/${orderId}/reject`,
      { method: "POST", body: JSON.stringify({ reason }) }
    ),
  getTenantMembership: (tenantId: number) =>
    request<DeveloperTenantMembership>(
      `/api/developer/billing/tenants/${tenantId}/membership`
    ),
  adjustTenantMembership: (
    tenantId: number,
    payload: { plan_id: number; duration_months: number }
  ) =>
    request<DeveloperTenantMembership>(
      `/api/developer/billing/tenants/${tenantId}/membership`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  listRechargeOrders: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperRechargeOrder>>(
      `/api/developer/billing/recharge-orders${params?.size ? `?${params.toString()}` : ""}`
    ),
  grantRechargeOrder: (orderId: number) =>
    request<DeveloperRechargeOrder>(
      `/api/developer/billing/recharge-orders/${orderId}/grant`,
      { method: "POST" }
    ),
  grantCredits: (payload: {
    user_id: number;
    credits: number;
    reason: string;
  }) =>
    request<DeveloperCreditGrantResult>("/api/developer/billing/credits/grant", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  adjustCredits: (payload: {
    user_id: number;
    change_amount: number;
    reason: string;
  }) => request<DeveloperCreditGrantResult>(
    "/api/developer/billing/credits/adjust",
    { method: "POST", body: JSON.stringify(payload) }
  ),
  listCreditLedger: (params?: URLSearchParams) =>
    request<DeveloperCreditLedgerResult>(
      `/api/developer/billing/ledger${params?.size ? `?${params.toString()}` : ""}`
    ),
  listPaymentRecords: (params?: URLSearchParams) =>
    request<DeveloperPaymentRecordResult>(
      `/api/developer/billing/payment-records${params?.size ? `?${params.toString()}` : ""}`
    )
};
