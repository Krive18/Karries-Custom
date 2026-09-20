import type {
  AccountCreateRequest,
  AccountView,
  AiTranslationLanguage,
  AiTranslationTask,
  ContentDraftManualCreate,
  ContentDraftUpdate,
  ContentDraftView,
  ContentCollection,
  ContentCollectionUpdate,
  DailyCheckinStatus,
  ImageCopyRequest,
  ImageCopyResult,
  InspirationAttachment,
  InspirationMessageCreate,
  InspirationMessageRevisionCreate,
  InspirationMessageResponse,
  InspirationPersonalization,
  InspirationPersonalizationPreference,
  InspirationPersonalizationPreferenceUpdate,
  InspirationPersonalizationTemplate,
  InspirationPersonalizationTemplateUpdate,
  InspirationPersonalizationUpdate,
  InspirationSession,
  InspirationSessionCreate,
  InspirationSessionDetail,
  AuthResponse,
  AuthUser,
  LoginRequest,
  MaterialAsset,
  MaterialFolder,
  MaterialLibraryListing,
  MaterialProjectGroup,
  MaterialStorageUsage,
  MembershipPlan,
  MatrixPlanActionResult,
  MatrixPlanCreateResult,
  MatrixPlanFromDraftsCreate,
  MatrixPlanItemView,
  MatrixPlanView,
  PaginatedResult,
  RechargeOrder,
  RechargeOrderCreate,
  RechargePackage,
  TaskCreateRequest,
  TaskView,
  VideoEditJobCreate,
  VideoEditJobHistory,
  VideoEditJobView,
  VideoEditRequestSnapshot,
  VideoEditPublishContentUpdate,
  VideoEditRevisionRequestCreate,
  VideoScriptOptimizeRequest,
  VideoScriptOptimizeResult,
  ViralAnalysisJob,
  ViralAnalysisJobCreate,
  ViralAnalysisMaterial,
  UserMembership,
  UserNotification,
  UserFeedback,
  UserFeedbackCreate,
  WalletView,
  CreditLedgerView,
  XHSAccountLoginCheck,
  XHSAccountLoginSession,
  XHSAccountCreate,
  XHSAccountView
} from "../types";
import { setPortalToken } from "../auth/portalSession";
import {
  ApiRequestError,
  createPortalBlobRequest,
  createPortalRequest
} from "./httpClient";


export { ApiRequestError };

const request = createPortalRequest("customer");
const requestBlob = createPortalBlobRequest("customer");


export const customerApi = {
  login: async (payload: LoginRequest) => {
    const result = await request<AuthResponse>("/api/auth/customer/login", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    setPortalToken("customer", result.access_token);
    return result;
  },
  getCurrentUser: () => request<AuthUser>("/api/auth/me"),
  getWallet: () => request<WalletView>("/api/wallet"),
  listCreditLedger: () => request<CreditLedgerView[]>("/api/wallet/ledger"),
  listMembershipPlans: () =>
    request<MembershipPlan[]>("/api/wallet/membership-plans"),
  getCurrentMembership: () =>
    request<UserMembership>("/api/wallet/membership"),
  getDailyCheckinStatus: () =>
    request<DailyCheckinStatus>("/api/wallet/check-in"),
  dailyCheckIn: () =>
    request<DailyCheckinStatus>("/api/wallet/check-in", {
      method: "POST"
    }),
  listNotifications: (params?: URLSearchParams) =>
    request<PaginatedResult<UserNotification>>(
      `/api/notifications${params?.size ? `?${params.toString()}` : ""}`
    ),
  getUnreadNotificationCount: () =>
    request<{ count: number }>("/api/notifications/unread-count"),
  markNotificationRead: (notificationId: number) =>
    request<{ id: number; is_read: boolean }>(`/api/notifications/${notificationId}/read`, {
      method: "POST"
    }),
  markAllNotificationsRead: () =>
    request<{ updated_count: number }>("/api/notifications/read-all", {
      method: "POST"
    }),
  listUserFeedback: (params?: URLSearchParams) =>
    request<PaginatedResult<UserFeedback>>(
      `/api/user-feedback${params?.size ? `?${params.toString()}` : ""}`
    ),
  createUserFeedback: (payload: UserFeedbackCreate) =>
    request<UserFeedback>("/api/user-feedback", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listRechargePackages: () =>
    request<RechargePackage[]>("/api/wallet/recharge-packages"),
  listRechargeOrders: () =>
    request<RechargeOrder[]>("/api/wallet/recharge-orders"),
  createRechargeOrder: (payload: RechargeOrderCreate) =>
    request<RechargeOrder>("/api/wallet/recharge-orders", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  submitRechargePaymentProof: (
    orderId: number,
    payerNote: string,
    proof: File
  ) => {
    const body = new FormData();
    body.append("payer_note", payerNote);
    body.append("proof", proof);
    return request<RechargeOrder>(
      `/api/wallet/recharge-orders/${orderId}/payment-proof`,
      { method: "POST", body }
    );
  },
  getRechargePaymentProofBlob: (orderId: number) =>
    requestBlob(`/api/wallet/recharge-orders/${orderId}/payment-proof`),
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
  updateXHSAccount: (accountId: number, payload: XHSAccountCreate) =>
    request<XHSAccountView>(`/api/xhs-accounts/${accountId}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  deleteXHSAccount: (accountId: number) =>
    request<{ deleted: boolean }>(`/api/xhs-accounts/${accountId}`, {
      method: "DELETE"
    }),
  startXHSAccountLogin: (accountId: number) =>
    request<XHSAccountLoginSession>(`/api/xhs-accounts/${accountId}/login/start`, {
      method: "POST"
    }),
  getLatestXHSAccountLoginSession: (accountId: number) =>
    request<XHSAccountLoginSession | null>(`/api/xhs-accounts/${accountId}/login/session`),
  checkXHSAccountLogin: (accountId: number) =>
    request<XHSAccountLoginCheck>(`/api/xhs-accounts/${accountId}/login/check`, {
      method: "POST"
    }),
  listContentDrafts: (status?: string) =>
    request<ContentDraftView[]>(
      `/api/content-drafts${status ? `?status=${encodeURIComponent(status)}` : ""}`
    ),
  listSmartCreationHistory: () =>
    request<ContentDraftView[]>("/api/content-drafts?source_type=smart_create"),
  createManualContentDraft: (payload: ContentDraftManualCreate) =>
    request<ContentDraftView>("/api/content-drafts/manual", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateContentDraft: (draftId: number, payload: ContentDraftUpdate) =>
    request<ContentDraftView>(`/api/content-drafts/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  listMatrixPlans: () => request<MatrixPlanView[]>("/api/matrix-plans"),
  getMatrixPlan: (planId: number) =>
    request<MatrixPlanView>(`/api/matrix-plans/${planId}`),
  listMatrixPlanItems: (planId: number) =>
    request<MatrixPlanItemView[]>(`/api/matrix-plans/${planId}/items`),
  createMatrixPlanFromDrafts: (payload: MatrixPlanFromDraftsCreate) =>
    request<MatrixPlanCreateResult>("/api/matrix-plans/from-drafts", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  confirmMatrixPlan: (planId: number) =>
    request<MatrixPlanActionResult>(`/api/matrix-plans/${planId}/confirm`, {
      method: "POST"
    }),
  cancelMatrixPlan: (planId: number) =>
    request<MatrixPlanActionResult>(`/api/matrix-plans/${planId}/cancel`, {
      method: "POST"
    }),
  retryFailedMatrixPlanItems: (planId: number) =>
    request<MatrixPlanActionResult>(`/api/matrix-plans/${planId}/retry-failed`, {
      method: "POST"
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
  updateVideoEditPublishContent: (
    jobId: number,
    payload: VideoEditPublishContentUpdate
  ) =>
    request<VideoEditJobView>(`/api/video-edit/jobs/${jobId}/publish-content`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  requestVideoEditRevision: (
    jobId: number,
    payload: VideoEditRevisionRequestCreate
  ) =>
    request<VideoEditJobView>(`/api/video-edit/jobs/${jobId}/revisions`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  optimizeVideoScript: (payload: VideoScriptOptimizeRequest) =>
    request<VideoScriptOptimizeResult>("/api/video-edit/jobs/script-optimize", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getVideoEditDeliveryBlob: (jobId: number) =>
    requestBlob(`/api/video-edit/jobs/${jobId}/delivery/content`),
  getVideoEditDeliveryArchiveBlob: (jobId: number) =>
    requestBlob(`/api/video-edit/jobs/${jobId}/delivery/archive`),
  getVideoEditDeliveryVersionBlob: (jobId: number, version: number) =>
    requestBlob(`/api/video-edit/jobs/${jobId}/delivery/versions/${version}/content`),
  getVideoEditDeliveryResourceBlob: (
    jobId: number,
    resourceType: "voiceover" | "subtitle",
    version: number
  ) => requestBlob(
    `/api/video-edit/jobs/${jobId}/delivery/resources/${resourceType}/${version}/content`
  ),
  getVideoEditJobHistory: async (jobId: number) => {
    try {
      return await request<VideoEditJobHistory>(
        `/api/video-edit/jobs/${jobId}/history`
      );
    } catch (error) {
      // Older deployed backends do not expose the dedicated history route yet.
      // Keep the creation record usable during rolling upgrades by rebuilding
      // the immutable request view from the existing job representation.
      if (
        !(error instanceof ApiRequestError)
        || ![404, 405, 501].includes(error.status)
      ) {
        throw error;
      }
      const job = await request<VideoEditJobView>(
        `/api/video-edit/jobs/${jobId}`
      );
      const snapshot: VideoEditRequestSnapshot = Object.assign({}, {
        creation_mode: job.creation_mode,
        creation_mode_label: job.creation_mode_label,
        credit_cost: job.credit_cost,
        job_title: job.job_title,
        post_title: job.post_title,
        post_body: job.post_body,
        post_tags: job.post_tags,
        script_text: job.script_text,
        requirement_text: job.requirement_text,
        materials: job.materials,
        xhs_account_id: job.xhs_account_id,
        xhs_account_name: job.xhs_account_name,
        planned_publish_time: job.planned_publish_time,
        submitted_at: job.create_time
      }, job.request_snapshot ?? {});
      if ((!Array.isArray(snapshot.materials) || snapshot.materials.length === 0) && job.materials.length > 0) {
        snapshot.materials = job.materials;
      }
      return {
        id: job.id,
        request_snapshot: snapshot,
        creation_mode: job.creation_mode,
        creation_mode_label: job.creation_mode_label,
        credit_cost: job.credit_cost,
        status: job.status,
        status_name: job.status_name,
        status_text: job.status_text,
        delivery_versions: job.delivery_versions ?? [],
        delivery_assets: job.delivery_assets ?? [],
        revision_count: job.revision_count ?? 0,
        create_time: job.create_time,
        update_time: job.update_time,
        delivered_time: job.delivered_time
      };
    }
  },
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
  reviseInspirationMessage: (
    sessionId: number,
    messageId: number,
    payload: InspirationMessageRevisionCreate
  ) =>
    request<InspirationMessageResponse>(
      `/api/inspiration/sessions/${sessionId}/messages/${messageId}/revisions`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  activateInspirationMessageRevision: (sessionId: number, messageId: number) =>
    request<InspirationSessionDetail>(
      `/api/inspiration/sessions/${sessionId}/messages/${messageId}/activate`,
      { method: "POST" }
    ),
  uploadInspirationAttachment: (sessionId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<InspirationAttachment>(
      `/api/inspiration/sessions/${sessionId}/attachments`,
      { method: "POST", body: form }
    );
  },
  getInspirationAttachmentBlob: (attachmentId: number) =>
    requestBlob(`/api/inspiration/attachments/${attachmentId}/content`),
  saveInspirationMessageDraft: (messageId: number) =>
    request<{ collection_id: number }>(`/api/inspiration/messages/${messageId}/save-collection`, {
      method: "POST"
    }),
  archiveInspirationSession: (sessionId: number) =>
    request<InspirationSession>(`/api/inspiration/sessions/${sessionId}/archive`, {
      method: "POST"
    }),
  setInspirationSessionPinned: (sessionId: number, isPinned: boolean) =>
    request<InspirationSession>(`/api/inspiration/sessions/${sessionId}/pin`, {
      method: "PATCH",
      body: JSON.stringify({ is_pinned: isPinned })
    }),
  renameInspirationSession: (sessionId: number, title: string) =>
    request<InspirationSession>(`/api/inspiration/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ title })
    }),
  deleteInspirationSession: (sessionId: number) =>
    request<{ deleted: boolean }>(`/api/inspiration/sessions/${sessionId}`, {
      method: "DELETE"
    }),
  getInspirationPersonalization: () =>
    request<InspirationPersonalization>("/api/inspiration/personalization"),
  updateInspirationPersonalization: (payload: InspirationPersonalizationUpdate) =>
    request<InspirationPersonalization>("/api/inspiration/personalization", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  listInspirationPersonalizationTemplates: (includeArchived = false) =>
    request<InspirationPersonalizationTemplate[]>(
      `/api/inspiration/personalization/templates${includeArchived ? "?include_archived=true" : ""}`
    ),
  createInspirationPersonalizationTemplate: (
    payload: InspirationPersonalizationTemplateUpdate
  ) => request<InspirationPersonalizationTemplate>(
    "/api/inspiration/personalization/templates",
    { method: "POST", body: JSON.stringify(payload) }
  ),
  updateInspirationPersonalizationTemplate: (
    templateId: number,
    payload: InspirationPersonalizationTemplateUpdate
  ) => request<InspirationPersonalizationTemplate>(
    `/api/inspiration/personalization/templates/${templateId}`,
    { method: "PUT", body: JSON.stringify(payload) }
  ),
  duplicateInspirationPersonalizationTemplate: (templateId: number) =>
    request<InspirationPersonalizationTemplate>(
      `/api/inspiration/personalization/templates/${templateId}/duplicate`,
      { method: "POST" }
    ),
  archiveInspirationPersonalizationTemplate: (templateId: number) =>
    request<InspirationPersonalizationTemplate>(
      `/api/inspiration/personalization/templates/${templateId}`,
      { method: "DELETE" }
    ),
  getInspirationPersonalizationPreference: () =>
    request<InspirationPersonalizationPreference>(
      "/api/inspiration/personalization/preference"
    ),
  updateInspirationPersonalizationPreference: (
    payload: InspirationPersonalizationPreferenceUpdate
  ) => request<InspirationPersonalizationPreference>(
    "/api/inspiration/personalization/preference",
    { method: "PUT", body: JSON.stringify(payload) }
  ),
  listMaterialLibraryItems: (
    folderId = 0,
    keyword = "",
    fileType = "",
    recursive = false,
    projectGroupId = 0
  ) => {
    const params = new URLSearchParams({ folder_id: String(folderId) });
    if (projectGroupId > 0) params.set("project_group_id", String(projectGroupId));
    if (keyword.trim()) params.set("keyword", keyword.trim());
    if (fileType) params.set("file_type", fileType);
    if (recursive) params.set("recursive", "true");
    return request<MaterialLibraryListing>(`/api/material-library/items?${params.toString()}`);
  },
  listMaterialProjectGroups: () =>
    request<MaterialProjectGroup[]>("/api/material-library/project-groups"),
  createMaterialProjectGroup: (groupName: string) =>
    request<MaterialProjectGroup>("/api/material-library/project-groups", {
      method: "POST",
      body: JSON.stringify({ group_name: groupName })
    }),
  renameMaterialProjectGroup: (projectGroupId: number, groupName: string) =>
    request<MaterialProjectGroup>(
      `/api/material-library/project-groups/${projectGroupId}`,
      {
        method: "PATCH",
        body: JSON.stringify({ group_name: groupName })
      }
    ),
  deleteMaterialProjectGroup: (projectGroupId: number) =>
    request<{ deleted: boolean }>(
      `/api/material-library/project-groups/${projectGroupId}`,
      { method: "DELETE" }
    ),
  getMaterialStorageUsage: () =>
    request<MaterialStorageUsage>("/api/material-library/storage-usage"),
  createMaterialFolder: (
    parentId: number,
    folderName: string,
    projectGroupId = 0
  ) =>
    request<MaterialFolder>("/api/material-library/folders", {
      method: "POST",
      body: JSON.stringify({
        project_group_id: projectGroupId,
        parent_id: parentId,
        folder_name: folderName
      })
    }),
  renameMaterialFolder: (folderId: number, folderName: string) =>
    request<MaterialFolder>(`/api/material-library/folders/${folderId}`, {
      method: "PATCH",
      body: JSON.stringify({ folder_name: folderName })
    }),
  deleteMaterialFolder: (folderId: number) =>
    request<{ deleted: boolean }>(`/api/material-library/folders/${folderId}`, {
      method: "DELETE"
    }),
  uploadMaterialAsset: (folderId: number, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<MaterialAsset>(
      `/api/material-library/assets/upload?folder_id=${folderId}`,
      { method: "POST", body }
    );
  },
  updateMaterialAsset: (
    assetId: number,
    payload: { folder_id?: number; file_name?: string }
  ) =>
    request<MaterialAsset>(`/api/material-library/assets/${assetId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteMaterialAsset: (assetId: number) =>
    request<{ deleted: boolean }>(`/api/material-library/assets/${assetId}`, {
      method: "DELETE"
    }),
  getMaterialAssetBlob: (assetId: number) =>
    requestBlob(`/api/material-library/assets/${assetId}/content`),
  getMaterialAssetThumbnailBlob: (assetId: number) =>
    requestBlob(`/api/material-library/assets/${assetId}/thumbnail`),
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
  getViralAnalysisMaterialBlob: (jobId: number, materialId: number) =>
    requestBlob(`/api/viral-analysis/jobs/${jobId}/materials/${materialId}/content`),
  uploadViralAnalysisMaterial: (jobId: number, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<ViralAnalysisMaterial>(
      `/api/viral-analysis/jobs/${jobId}/upload`,
      { method: "POST", body }
    );
  },
  selectViralAnalysisLibraryMaterial: (jobId: number, materialFileId: number) =>
    request<ViralAnalysisMaterial>(
      `/api/viral-analysis/jobs/${jobId}/library-material`,
      {
        method: "POST",
        body: JSON.stringify({ material_file_id: materialFileId })
      }
    ),
  runViralAnalysisJob: (jobId: number) =>
    request<ViralAnalysisJob>(`/api/viral-analysis/jobs/${jobId}/run`, { method: "POST" }),
  cancelViralAnalysisJob: (jobId: number) =>
    request<ViralAnalysisJob>(`/api/viral-analysis/jobs/${jobId}/cancel`, { method: "POST" }),
  createContentCollection: (payload: { source_type: "viral_analysis"; source_id: number }) =>
    request<{ item: ContentCollection; created: boolean }>("/api/content-collections", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listContentCollections: (params?: URLSearchParams) =>
    request<PaginatedResult<ContentCollection>>(
      `/api/content-collections${params?.size ? `?${params.toString()}` : ""}`
    ),
  getContentCollection: (collectionId: number) =>
    request<ContentCollection>(`/api/content-collections/${collectionId}`),
  updateContentCollection: (collectionId: number, payload: ContentCollectionUpdate) =>
    request<ContentCollection>(`/api/content-collections/${collectionId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteContentCollection: (collectionId: number) =>
    request<{ deleted: boolean }>(`/api/content-collections/${collectionId}`, {
      method: "DELETE"
    }),
  listAiTranslationTasks: (status = "") =>
    request<AiTranslationTask[]>(
      `/api/ai-translations/tasks${status ? `?status=${encodeURIComponent(status)}` : ""}`
    ),
  getAiTranslationTask: (taskId: number) =>
    request<AiTranslationTask>(`/api/ai-translations/tasks/${taskId}`),
  uploadAiTranslationTask: (
    file: File,
    sourceLanguage: AiTranslationLanguage,
    targetLanguage: Exclude<AiTranslationLanguage, "auto">,
    clientRequestId: string
  ) => {
    const body = new FormData();
    body.append("file", file);
    body.append("source_language", sourceLanguage);
    body.append("target_language", targetLanguage);
    body.append("client_request_id", clientRequestId);
    return request<AiTranslationTask>("/api/ai-translations/tasks/upload", {
      method: "POST",
      body
    });
  },
  createAiTranslationTaskFromMaterial: (payload: {
    material_file_id: number;
    source_language: AiTranslationLanguage;
    target_language: Exclude<AiTranslationLanguage, "auto">;
    client_request_id: string;
  }) => request<AiTranslationTask>("/api/ai-translations/tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  }),
  cancelAiTranslationTask: (taskId: number) =>
    request<AiTranslationTask>(`/api/ai-translations/tasks/${taskId}/cancel`, { method: "POST" }),
  acceptAiTranslationTask: (taskId: number) =>
    request<AiTranslationTask>(`/api/ai-translations/tasks/${taskId}/accept`, { method: "POST" }),
  requestAiTranslationRevision: (taskId: number, feedback: string) =>
    request<AiTranslationTask>(`/api/ai-translations/tasks/${taskId}/revision`, {
      method: "POST",
      body: JSON.stringify({ feedback })
    }),
  getAiTranslationSourceBlob: (taskId: number) =>
    requestBlob(`/api/ai-translations/tasks/${taskId}/source/content`),
  getAiTranslationDeliveryBlob: (taskId: number, deliveryId: number) =>
    requestBlob(`/api/ai-translations/tasks/${taskId}/deliveries/${deliveryId}/content`)
};

export const api = customerApi;
