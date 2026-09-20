import type {
  AdminBillingOverview,
  AdminCreditLedgerResult,
  AdminEmployeeCreate,
  AdminEmployeeDetail,
  AdminEmployeePasswordReset,
  AdminEmployeeStatusUpdate,
  AdminEmployeeSummary,
  AdminEmployeeUpdate,
  AdminEmployeeView,
  AdminMembershipActivation,
  AdminNotificationCreate,
  AdminProduct,
  AdminProductLibrarySummary,
  AdminPublishPlan,
  AdminPublishPlanDetail,
  AdminRechargeOrder,
  AdminRechargeOrderCreate,
  AdminSentNotification,
  AdminSummary,
  AdminXHSAccount,
  AuthResponse,
  AuthUser,
  InspirationSession,
  InspirationSessionDetail,
  LoginRequest,
  MaterialAsset,
  MaterialFolder,
  MaterialLibraryListing,
  MaterialProjectGroup,
  MatrixPlanActionResult,
  MembershipPlan,
  MembershipUpgradeOrder,
  MembershipUpgradeOrderCreate,
  OperationsOverview,
  PaginatedResult,
  RechargePackage,
  UserCreationRequest,
  ViralAnalysisJob
} from "../types";
import { setPortalToken } from "../auth/portalSession";
import {
  createPortalBlobRequest,
  createPortalRequest
} from "./httpClient";


const request = createPortalRequest("manager");
const requestBlob = createPortalBlobRequest("manager");


export const managerApi = {
  login: async (payload: LoginRequest) => {
    const result = await request<AuthResponse>("/api/auth/manager/login", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    setPortalToken("manager", result.access_token);
    return result;
  },
  getCurrentUser: () => request<AuthUser>("/api/auth/me"),
  getAdminSummary: () => request<AdminSummary>("/api/admin/summary"),
  getOperationsOverview: (days = 7) =>
    request<OperationsOverview>(`/api/admin/operations/overview?days=${days}`),
  listManagedXHSAccounts: (params?: URLSearchParams) =>
    request<PaginatedResult<AdminXHSAccount>>(
      `/api/admin/operations/xhs-accounts${params?.size ? `?${params.toString()}` : ""}`
    ),
  listManagedPublishPlans: (params?: URLSearchParams) =>
    request<PaginatedResult<AdminPublishPlan>>(
      `/api/admin/operations/publish-plans${params?.size ? `?${params.toString()}` : ""}`
    ),
  getManagedPublishPlan: (planId: number) =>
    request<AdminPublishPlanDetail>(`/api/admin/operations/publish-plans/${planId}`),
  cancelManagedPublishPlan: (planId: number) =>
    request<MatrixPlanActionResult>(`/api/admin/operations/publish-plans/${planId}/cancel`, {
      method: "POST"
    }),
  retryManagedPublishPlan: (planId: number) =>
    request<MatrixPlanActionResult>(`/api/admin/operations/publish-plans/${planId}/retry`, {
      method: "POST"
    }),
  listEmployees: (params?: URLSearchParams) =>
    request<PaginatedResult<AdminEmployeeView>>(
      `/api/admin/users${params?.size ? `?${params.toString()}` : ""}`
    ),
  getEmployeeSummary: () =>
    request<AdminEmployeeSummary>("/api/admin/users/summary"),
  getEmployee: (employeeId: number) =>
    request<AdminEmployeeDetail>(`/api/admin/users/${employeeId}`),
  createEmployee: (payload: AdminEmployeeCreate) =>
    request<AdminEmployeeView | UserCreationRequest>("/api/admin/users", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateEmployee: (
    employeeId: number,
    payload: AdminEmployeeUpdate
  ) =>
    request<AdminEmployeeDetail>(`/api/admin/users/${employeeId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  resetEmployeePassword: (
    employeeId: number,
    payload: AdminEmployeePasswordReset
  ) =>
    request<AdminEmployeeView>(
      `/api/admin/users/${employeeId}/password`,
      {
        method: "PUT",
        body: JSON.stringify(payload)
      }
    ),
  updateEmployeeStatus: (
    employeeId: number,
    status: AdminEmployeeStatusUpdate["status"]
  ) =>
    request<AdminEmployeeView>(
      `/api/admin/users/${employeeId}/status`,
      {
        method: "PATCH",
        body: JSON.stringify({ status })
      }
    ),
  listInspirationSessions: (params?: URLSearchParams) =>
    request<PaginatedResult<InspirationSession>>(
      `/api/admin/inspiration/sessions${params?.size ? `?${params.toString()}` : ""}`
    ),
  getInspirationSession: (sessionId: number) =>
    request<InspirationSessionDetail>(
      `/api/admin/inspiration/sessions/${sessionId}`
    ),
  listViralAnalysisJobs: (params?: URLSearchParams) =>
    request<PaginatedResult<ViralAnalysisJob>>(
      `/api/admin/viral-analysis/jobs${params?.size ? `?${params.toString()}` : ""}`
    ),
  getViralAnalysisJob: (jobId: number) =>
    request<ViralAnalysisJob>(`/api/admin/viral-analysis/jobs/${jobId}`),
  listSentNotifications: (params?: URLSearchParams) =>
    request<PaginatedResult<AdminSentNotification>>(
      `/api/admin/notifications${params?.size ? `?${params.toString()}` : ""}`
    ),
  createNotification: (payload: AdminNotificationCreate) =>
    request<{ notification_ids: number[]; recipient_count: number }>(
      "/api/admin/notifications",
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  getBillingOverview: (days = 30) =>
    request<AdminBillingOverview>(`/api/admin/billing/overview?days=${days}`),
  listAdminMembershipPlans: () =>
    request<MembershipPlan[]>("/api/admin/billing/membership-plans"),
  activateAdminMembership: (
    planId: number,
    durationMonths = 1
  ) =>
    request<AdminMembershipActivation>("/api/admin/billing/membership/activate", {
      method: "POST",
      body: JSON.stringify({
        plan_id: planId,
        duration_months: durationMonths,
        auto_renew: 0
      })
    }),
  listAdminMembershipOrders: (params?: URLSearchParams) =>
    request<PaginatedResult<MembershipUpgradeOrder>>(
      `/api/admin/billing/membership-orders${params?.size ? `?${params.toString()}` : ""}`
    ),
  createAdminMembershipOrder: (payload: MembershipUpgradeOrderCreate) =>
    request<MembershipUpgradeOrder>("/api/admin/billing/membership-orders", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  confirmAdminMembershipOrder: (orderId: number) =>
    request<MembershipUpgradeOrder>(
      `/api/admin/billing/membership-orders/${orderId}/confirm`,
      { method: "POST" }
    ),
  cancelAdminMembershipOrder: (orderId: number) =>
    request<MembershipUpgradeOrder>(
      `/api/admin/billing/membership-orders/${orderId}/cancel`,
      { method: "POST" }
    ),
  listAdminRechargePackages: () =>
    request<RechargePackage[]>("/api/admin/billing/recharge-packages"),
  listAdminRechargeOrders: (params?: URLSearchParams) =>
    request<PaginatedResult<AdminRechargeOrder>>(
      `/api/admin/billing/recharge-orders${params?.size ? `?${params.toString()}` : ""}`
    ),
  createAdminRechargeOrder: (payload: AdminRechargeOrderCreate) =>
    request<AdminRechargeOrder>("/api/admin/billing/recharge-orders", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  confirmAdminRechargeOrder: (orderId: number) =>
    request<AdminRechargeOrder>(
      `/api/admin/billing/recharge-orders/${orderId}/confirm`,
      { method: "POST" }
    ),
  rejectAdminRechargeOrder: (orderId: number, reason: string) =>
    request<AdminRechargeOrder>(
      `/api/admin/billing/recharge-orders/${orderId}/reject`,
      {
        method: "POST",
        body: JSON.stringify({ reason })
      }
    ),
  getAdminRechargePaymentProofBlob: (orderId: number) =>
    requestBlob(`/api/admin/billing/recharge-orders/${orderId}/payment-proof`),
  listAdminCreditLedger: (params?: URLSearchParams) =>
    request<AdminCreditLedgerResult>(
      `/api/admin/billing/ledger${params?.size ? `?${params.toString()}` : ""}`
    ),
  getAdminProductLibrarySummary: () =>
    request<AdminProductLibrarySummary>("/api/admin/product-library/summary"),
  listAdminProducts: (params?: URLSearchParams) =>
    request<PaginatedResult<AdminProduct>>(
      `/api/admin/product-library/products${params?.size ? `?${params.toString()}` : ""}`
    ),
  updateAdminProductStatus: (productId: number, status: 1 | 2) =>
    request<AdminProduct>(
      `/api/admin/product-library/products/${productId}/status`,
      {
        method: "PATCH",
        body: JSON.stringify({ status })
      }
    ),
  listAdminMaterialItems: (params?: URLSearchParams) =>
    request<MaterialLibraryListing>(
      `/api/admin/product-library/items${params?.size ? `?${params.toString()}` : ""}`
    ),
  listAdminMaterialProjectGroups: () =>
    request<MaterialProjectGroup[]>(
      "/api/admin/product-library/project-groups"
    ),
  createAdminMaterialProjectGroup: (groupName: string) =>
    request<MaterialProjectGroup>(
      "/api/admin/product-library/project-groups",
      {
        method: "POST",
        body: JSON.stringify({ group_name: groupName })
      }
    ),
  renameAdminMaterialProjectGroup: (
    projectGroupId: number,
    groupName: string
  ) => request<MaterialProjectGroup>(
    `/api/admin/product-library/project-groups/${projectGroupId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ group_name: groupName })
    }
  ),
  deleteAdminMaterialProjectGroup: (projectGroupId: number) =>
    request<{ deleted: boolean }>(
      `/api/admin/product-library/project-groups/${projectGroupId}`,
      { method: "DELETE" }
    ),
  createAdminMaterialFolder: (
    parentId: number,
    folderName: string,
    projectGroupId = 0
  ) =>
    request<MaterialFolder>("/api/admin/product-library/folders", {
      method: "POST",
      body: JSON.stringify({
        project_group_id: projectGroupId,
        parent_id: parentId,
        folder_name: folderName
      })
    }),
  renameAdminMaterialFolder: (folderId: number, folderName: string) =>
    request<MaterialFolder>(
      `/api/admin/product-library/folders/${folderId}`,
      {
        method: "PATCH",
        body: JSON.stringify({ folder_name: folderName })
      }
    ),
  deleteAdminMaterialFolder: (folderId: number) =>
    request<{ deleted: boolean }>(
      `/api/admin/product-library/folders/${folderId}`,
      { method: "DELETE" }
    ),
  uploadAdminMaterialAsset: (folderId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<MaterialAsset>(
      `/api/admin/product-library/assets/upload?folder_id=${folderId}`,
      { method: "POST", body: formData }
    );
  },
  updateAdminMaterialAsset: (
    assetId: number,
    payload: { folder_id?: number; file_name?: string }
  ) =>
    request<MaterialAsset>(
      `/api/admin/product-library/assets/${assetId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload)
      }
    ),
  deleteAdminMaterialAsset: (assetId: number) =>
    request<{ deleted: boolean }>(
      `/api/admin/product-library/assets/${assetId}`,
      { method: "DELETE" }
    ),
  getAdminMaterialAssetBlob: (assetId: number) =>
    requestBlob(`/api/admin/product-library/assets/${assetId}/content`),
  getAdminMaterialAssetThumbnailBlob: (assetId: number) =>
    requestBlob(`/api/admin/product-library/assets/${assetId}/thumbnail`)
};
