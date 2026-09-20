import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { ManagerApp } from "../ManagerApp";
import { ApiRequestError } from "../api/httpClient";
import { managerApi } from "../api/managerClient";
import type { MaterialFolder, MaterialProjectGroup } from "../types";


vi.mock("../api/managerClient", () => ({
  managerApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
    getAdminSummary: vi.fn(),
    getOperationsOverview: vi.fn(),
    listManagedXHSAccounts: vi.fn(),
    listManagedPublishPlans: vi.fn(),
    getManagedPublishPlan: vi.fn(),
    cancelManagedPublishPlan: vi.fn(),
    retryManagedPublishPlan: vi.fn(),
    listEmployees: vi.fn(),
    getEmployeeSummary: vi.fn(),
    getEmployee: vi.fn(),
    createEmployee: vi.fn(),
    updateEmployee: vi.fn(),
    resetEmployeePassword: vi.fn(),
    updateEmployeeStatus: vi.fn(),
    listInspirationSessions: vi.fn(),
    getInspirationSession: vi.fn(),
    listViralAnalysisJobs: vi.fn(),
    getViralAnalysisJob: vi.fn(),
    listSentNotifications: vi.fn(),
    createNotification: vi.fn(),
    getBillingOverview: vi.fn(),
    listAdminMembershipPlans: vi.fn(),
    activateAdminMembership: vi.fn(),
    listAdminMembershipOrders: vi.fn(),
    createAdminMembershipOrder: vi.fn(),
    confirmAdminMembershipOrder: vi.fn(),
    cancelAdminMembershipOrder: vi.fn(),
    listAdminRechargePackages: vi.fn(),
    listAdminRechargeOrders: vi.fn(),
    createAdminRechargeOrder: vi.fn(),
    confirmAdminRechargeOrder: vi.fn(),
    getAdminRechargePaymentProofBlob: vi.fn(),
    rejectAdminRechargeOrder: vi.fn(),
    listAdminCreditLedger: vi.fn(),
    getAdminProductLibrarySummary: vi.fn(),
    listAdminProducts: vi.fn(),
    updateAdminProductStatus: vi.fn(),
    listAdminMaterialProjectGroups: vi.fn(),
    createAdminMaterialProjectGroup: vi.fn(),
    renameAdminMaterialProjectGroup: vi.fn(),
    deleteAdminMaterialProjectGroup: vi.fn(),
    listAdminMaterialItems: vi.fn(),
    createAdminMaterialFolder: vi.fn(),
    renameAdminMaterialFolder: vi.fn(),
    deleteAdminMaterialFolder: vi.fn(),
    uploadAdminMaterialAsset: vi.fn(),
    updateAdminMaterialAsset: vi.fn(),
    deleteAdminMaterialAsset: vi.fn(),
    getAdminMaterialAssetBlob: vi.fn(),
    getAdminMaterialAssetThumbnailBlob: vi.fn()
  }
}));

const mockedManagerApi = vi.mocked(managerApi);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, reject, resolve };
}

const managerProjectGroups: MaterialProjectGroup[] = [
  {
    id: 17,
    tenant_id: 1,
    group_name: "秋季上新",
    created_by_user_id: 1,
    folder_count: 2,
    asset_count: 7,
    create_time: 1787097600,
    update_time: 1787132160
  },
  {
    id: 18,
    tenant_id: 1,
    group_name: "常青产品",
    created_by_user_id: 2,
    folder_count: 1,
    asset_count: 3,
    create_time: 1787011200,
    update_time: 1787040000
  }
];

const managerProductFolder: MaterialFolder = {
  id: 7,
  tenant_id: 1,
  project_group_id: 17,
  parent_id: 0,
  folder_name: "产品图",
  created_by_user_id: 1,
  child_folder_count: 0,
  asset_count: 2,
  create_time: 1787097600,
  update_time: 1787132160
};

function managerMaterialListing(folderId = 0, projectGroupId = 17) {
  return {
    project_group_id: projectGroupId,
    current_folder: folderId ? managerProductFolder : null,
    breadcrumbs: folderId ? [managerProductFolder] : [],
    folders: folderId ? [] : [managerProductFolder],
    assets: []
  };
}

async function openManagerMaterials() {
  fireEvent.click(await screen.findByRole("button", { name: "产品库管理" }));
  fireEvent.click(await screen.findByRole("button", { name: "共享素材" }));
}

const employee = {
  id: 12,
  tenant_id: 1,
  login_name: "operator_01",
  nickname: "运营一号",
  user_role: "customer" as const,
  status: 1 as const,
  wallet_balance: 20,
  xhs_account_count: 2,
  publish_plan_count: 4,
  last_login_time: 0,
  create_time: 0,
  update_time: 0
};


beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.clear();
  mockedManagerApi.getCurrentUser.mockResolvedValue({
    id: 1,
    tenant_id: 1,
    login_name: "owner",
    nickname: "禾一斯负责人",
    user_role: "client_owner",
    wallet_balance: 0
  });
  mockedManagerApi.getAdminSummary.mockResolvedValue({
    total_users: 2,
    total_xhs_accounts: 20,
    total_matrix_plans: 6,
    total_video_edit_jobs: 3,
    pending_video_edit_jobs: 1
  });
  mockedManagerApi.getOperationsOverview.mockResolvedValue({
    summary: {
      total_employees: 2,
      active_employees: 2,
      total_accounts: 20,
      normal_accounts: 18,
      expired_accounts: 1,
      risk_accounts: 1,
      today_scheduled: 6,
      today_submitted: 4,
      today_failed: 1,
      pending_items: 2,
      success_rate: 80,
      team_credit_balance: 3000
    },
    publish_trend: [],
    status_distribution: [],
    employee_ranking: [],
    alerts: []
  });
  mockedManagerApi.listSentNotifications.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 10,
    total: 0
  });
  mockedManagerApi.createNotification.mockResolvedValue({
    notification_ids: [101],
    recipient_count: 1
  });
  mockedManagerApi.listEmployees.mockResolvedValue({
    items: [employee],
    page: 1,
    page_size: 100,
    total: 1
  });
  mockedManagerApi.getEmployeeSummary.mockResolvedValue({
    total: 1,
    active: 1,
    disabled: 0,
    recent_login: 0
  });
  mockedManagerApi.getEmployee.mockResolvedValue({
    ...employee,
    inspiration_session_count: 3,
    viral_analysis_count: 2
  });
  mockedManagerApi.createEmployee.mockResolvedValue(employee);
  const plan = {
    id: 2,
    plan_code: "pro" as const,
    plan_name: "Pro会员版",
    price_cent: 19900,
    summary: "平台全部功能",
    features: ["平台全部功能"],
    monthly_credits: 1500,
    daily_checkin_credits: 20,
    storage_gb: 100,
    status: 1,
    sort_order: 20,
    create_time: 0,
    update_time: 0
  };
  mockedManagerApi.getBillingOverview.mockResolvedValue({
    membership: {
      id: 1,
      tenant_id: 1,
      user_id: 1,
      plan_id: 2,
      status: 1,
      start_time: 0,
      expire_time: 0,
      auto_renew: 0,
      create_time: 0,
      update_time: 0,
      plan
    },
    wallet: {
      employee_count: 1,
      balance: 20,
      total_recharged: 20,
      total_consumed: 0
    },
    month_orders: {
      order_count: 0,
      pending_order_count: 0,
      completed_amount_cent: 0,
      completed_credits: 0
    },
    credit_trend: [],
    employee_wallets: []
  });
  mockedManagerApi.listAdminMembershipPlans.mockResolvedValue([plan]);
  mockedManagerApi.listAdminMembershipOrders.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 20,
    total: 0
  });
  mockedManagerApi.listAdminRechargePackages.mockResolvedValue([]);
  mockedManagerApi.listAdminRechargeOrders.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 20,
    total: 0
  });
  mockedManagerApi.getAdminRechargePaymentProofBlob.mockResolvedValue(
    new Blob(["proof"], { type: "image/png" })
  );
  mockedManagerApi.rejectAdminRechargeOrder.mockResolvedValue({
    id: 1,
    order_no: "RC-TEST",
    tenant_id: 1,
    user_id: 12,
    recharge_type: "online",
    package_id: 0,
    package_name: "",
    amount_cent: 5000,
    requested_credits: 1000,
    payment_channel: "alipay",
    status: 5,
    remark: "付款凭证无法核对",
    paid_time: 1,
    completed_time: 0,
    create_time: 1,
    update_time: 1,
    employee_name: "运营一号",
    employee_login: "operator_01"
  });
  mockedManagerApi.listAdminCreditLedger.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 20,
    total: 0,
    summary: { income: 0, expense: 0 }
  });
  mockedManagerApi.getAdminProductLibrarySummary.mockResolvedValue({
    product_count: 0,
    active_product_count: 0,
    folder_count: 0,
    asset_count: 0,
    image_count: 0,
    video_count: 0,
    document_count: 0,
    storage_bytes: 0
  });
  mockedManagerApi.listAdminProducts.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 100,
    total: 0
  });
  mockedManagerApi.listAdminMaterialProjectGroups.mockResolvedValue(managerProjectGroups);
  mockedManagerApi.createAdminMaterialProjectGroup.mockImplementation(async (groupName) => ({
    ...managerProjectGroups[0],
    id: 19,
    group_name: groupName,
    folder_count: 0,
    asset_count: 0
  }));
  mockedManagerApi.renameAdminMaterialProjectGroup.mockImplementation(async (groupId, groupName) => ({
    ...managerProjectGroups.find((group) => group.id === groupId)!,
    group_name: groupName
  }));
  mockedManagerApi.deleteAdminMaterialProjectGroup.mockResolvedValue({ deleted: true });
  mockedManagerApi.listAdminMaterialItems.mockResolvedValue({
    project_group_id: 0,
    current_folder: null,
    breadcrumbs: [],
    folders: [],
    assets: []
  });
  mockedManagerApi.getAdminMaterialAssetThumbnailBlob.mockResolvedValue(
    new Blob(["thumbnail"], { type: "image/jpeg" })
  );
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => {
  vi.restoreAllMocks();
});


it("opens the standalone manager workspace without customer navigation", async () => {
  render(<ManagerApp />);

  expect(await screen.findByRole("button", { name: "员工账号管理" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "账号与发布" })).toHaveAttribute(
    "aria-expanded",
    "true"
  );
  expect(screen.getByRole("button", { name: "内容记录" })).toHaveAttribute(
    "aria-expanded",
    "true"
  );
  expect(screen.getByRole("heading", { name: "运营总览" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "智能创作" })).not.toBeInTheDocument();
});


it("creates a login-ready employee from the manager workspace", async () => {
  render(<ManagerApp />);
  fireEvent.click(await screen.findByRole("button", { name: "员工账号管理" }));

  expect(await screen.findByText("运营一号")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "新增员工" }));
  fireEvent.change(screen.getByLabelText("员工姓名"), {
    target: { value: "运营二号" }
  });
  fireEvent.change(screen.getByLabelText("登录账号"), {
    target: { value: "operator_02" }
  });
  fireEvent.change(screen.getByLabelText("长期密码"), {
    target: { value: "password123" }
  });
  fireEvent.click(screen.getByRole("button", { name: "创建员工" }));

  await waitFor(() => {
    expect(mockedManagerApi.createEmployee).toHaveBeenCalledWith({
      login_name: "operator_02",
      nickname: "运营二号",
      password: "password123",
      status: 1
    });
  });
});


it("does not expose the retired manual task notification composer", async () => {
  render(<ManagerApp />);
  await screen.findByRole("heading", { name: "运营总览" });

  expect(
    screen.queryByRole("button", { name: "发布任务通知" })
  ).not.toBeInTheDocument();
  expect(mockedManagerApi.createNotification).not.toHaveBeenCalled();
});


it("collapses and restores the manager sidebar", async () => {
  render(<ManagerApp />);
  await screen.findByRole("heading", { name: "运营总览" });

  fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));
  expect(document.querySelector(".manager-shell")).toHaveClass("sidebar-collapsed");
  expect(window.localStorage.getItem("manager-sidebar-collapsed")).toBe("1");
  fireEvent.click(screen.getByRole("button", { name: "展开侧边栏" }));
  expect(document.querySelector(".manager-shell")).not.toHaveClass("sidebar-collapsed");
});


it("opens billing, credit ledger and product library management", async () => {
  render(<ManagerApp />);

  fireEvent.click(await screen.findByRole("button", { name: "会员与充值" }));
  expect(await screen.findByRole("heading", { name: "会员与充值" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "算力流水" }));
  expect(await screen.findByRole("heading", { name: "算力流水" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "产品库管理" }));
  expect(await screen.findByRole("heading", { name: "产品库管理" })).toBeInTheDocument();
});


it("shows included plans as opened and submits paid upgrades for review", async () => {
  const proPlan = (await mockedManagerApi.listAdminMembershipPlans()).at(0)!;
  const freePlan = {
    ...proPlan,
    id: 1,
    plan_code: "free" as const,
    plan_name: "免费版",
    price_cent: 0,
    monthly_credits: 500,
    storage_gb: 10,
    sort_order: 10
  };
  const maxPlan = {
    ...proPlan,
    id: 3,
    plan_code: "max" as const,
    plan_name: "Max会员版",
    price_cent: 29900,
    monthly_credits: 3000,
    storage_gb: 180,
    sort_order: 30
  };
  const storagePlan = {
    ...proPlan,
    id: 4,
    plan_code: "storage" as const,
    plan_name: "存储大会员版",
    price_cent: 59900,
    monthly_credits: 3000,
    storage_gb: 1000,
    sort_order: 40
  };
  mockedManagerApi.listAdminMembershipPlans.mockResolvedValue([
    freePlan,
    proPlan,
    maxPlan,
    storagePlan
  ]);
  const pendingOrder = {
    id: 31,
    order_no: "MU-TEST-31",
    tenant_id: 1,
    applicant_user_id: 1,
    applicant_name: "禾一斯负责人",
    applicant_login: "owner",
    tenant_name: "禾一斯",
    plan_id: maxPlan.id,
    plan: maxPlan,
    duration_months: 1,
    amount_cent: maxPlan.price_cent,
    payment_channel: "wechat" as const,
    status: 1 as const,
    paid_time: 0,
    reviewed_by_developer_id: 0,
    reviewed_time: 0,
    affected_user_count: 0,
    remark: "",
    create_time: 1,
    update_time: 1
  };
  mockedManagerApi.createAdminMembershipOrder.mockResolvedValue(pendingOrder);
  mockedManagerApi.confirmAdminMembershipOrder.mockResolvedValue({
    ...pendingOrder,
    status: 2,
    paid_time: 2,
    update_time: 2
  });

  render(<ManagerApp />);
  fireEvent.click(await screen.findByRole("button", { name: "会员与充值" }));

  const freeCard = (await screen.findByRole("heading", { name: "免费版" })).closest("article");
  expect(freeCard).not.toBeNull();
  expect(within(freeCard!).getByRole("button", { name: "已开通" })).toBeDisabled();

  const maxCard = screen.getByRole("heading", { name: "Max会员版" }).closest("article");
  expect(maxCard).not.toBeNull();
  fireEvent.click(within(maxCard!).getByRole("button", { name: "立即开通" }));

  await waitFor(() => {
    expect(mockedManagerApi.createAdminMembershipOrder).toHaveBeenCalledWith({
      plan_id: maxPlan.id,
      duration_months: 1,
      payment_channel: "wechat"
    });
  });
  expect(await screen.findByRole("heading", { name: "扫码完成付款" })).toBeInTheDocument();
  expect(screen.getByText("Max会员版会员升级")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "确认已付款，提交审核" }));
  await waitFor(() => {
    expect(mockedManagerApi.confirmAdminMembershipOrder).toHaveBeenCalledWith(31);
  });
});


it("keeps unpaid membership orders payable and lets the manager cancel them", async () => {
  const proPlan = (await mockedManagerApi.listAdminMembershipPlans()).at(0)!;
  const maxPlan = {
    ...proPlan,
    id: 3,
    plan_code: "max" as const,
    plan_name: "Max会员版",
    price_cent: 29900,
    monthly_credits: 3000,
    storage_gb: 180,
    sort_order: 30
  };
  const unpaidOrder = {
    id: 32,
    order_no: "MU-TEST-32",
    tenant_id: 1,
    applicant_user_id: 1,
    applicant_name: "禾一斯负责人",
    applicant_login: "owner",
    tenant_name: "禾一斯",
    plan_id: maxPlan.id,
    plan: maxPlan,
    duration_months: 1,
    amount_cent: maxPlan.price_cent,
    payment_channel: "wechat" as const,
    status: 1 as const,
    paid_time: 0,
    reviewed_by_developer_id: 0,
    reviewed_time: 0,
    affected_user_count: 0,
    remark: "",
    create_time: 1,
    update_time: 1
  };
  mockedManagerApi.listAdminMembershipPlans.mockResolvedValue([proPlan, maxPlan]);
  mockedManagerApi.listAdminMembershipOrders.mockResolvedValue({
    items: [unpaidOrder],
    page: 1,
    page_size: 20,
    total: 1
  });
  mockedManagerApi.cancelAdminMembershipOrder.mockResolvedValue({
    ...unpaidOrder,
    status: 5,
    update_time: 2
  });

  render(<ManagerApp />);
  fireEvent.click(await screen.findByRole("button", { name: "会员与充值" }));

  const maxCard = (await screen.findByRole("heading", { name: "Max会员版" })).closest("article");
  expect(maxCard).not.toBeNull();
  fireEvent.click(within(maxCard!).getByRole("button", { name: "继续支付" }));
  expect(await screen.findByRole("heading", { name: "扫码完成付款" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "关闭付款窗口" }));

  fireEvent.click(screen.getByRole("button", { name: "取消Max会员版申请" }));
  await waitFor(() => {
    expect(mockedManagerApi.cancelAdminMembershipOrder).toHaveBeenCalledWith(32);
  });
});


it("opens manager shared materials on project groups and waits to load items", async () => {
  render(<ManagerApp />);
  await openManagerMaterials();

  const autumnCard = (await screen.findByRole("button", { name: "打开项目组 秋季上新" }))
    .closest(".material-project-card");
  expect(autumnCard).not.toBeNull();
  expect(within(autumnCard as HTMLElement).getByText("2 个文件夹")).toBeInTheDocument();
  expect(within(autumnCard as HTMLElement).getByText("7 个素材")).toBeInTheDocument();
  expect(within(autumnCard as HTMLElement).getByText(/更新于 .*2026/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "上传素材" })).not.toBeInTheDocument();
  expect(screen.queryByText("当前文件夹还没有内容")).not.toBeInTheDocument();
  expect(mockedManagerApi.listAdminMaterialItems).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "打开项目组 秋季上新" }));
  await waitFor(() => {
    expect(mockedManagerApi.listAdminMaterialItems).toHaveBeenCalledWith(
      new URLSearchParams({ folder_id: "0", project_group_id: "17" })
    );
  });
});


it("propagates the selected manager project group when creating folders and resets from breadcrumb", async () => {
  mockedManagerApi.listAdminMaterialItems.mockImplementation(async (params) => (
    managerMaterialListing(Number(params?.get("folder_id") ?? 0), Number(params?.get("project_group_id") ?? 0))
  ));
  mockedManagerApi.createAdminMaterialFolder.mockResolvedValue({
    ...managerProductFolder,
    id: 20,
    folder_name: "视频脚本"
  });
  vi.spyOn(window, "prompt").mockReturnValueOnce("视频脚本");
  render(<ManagerApp />);
  await openManagerMaterials();

  fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));
  expect(await screen.findByText("产品图")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "新建文件夹" }));

  await waitFor(() => {
    expect(mockedManagerApi.createAdminMaterialFolder).toHaveBeenCalledWith(0, "视频脚本", 17);
  });

  fireEvent.change(screen.getByRole("textbox", { name: "搜索当前文件夹" }), {
    target: { value: "口红" }
  });
  fireEvent.click(screen.getByRole("button", { name: "打开文件夹 产品图" }));
  await waitFor(() => {
    expect(mockedManagerApi.listAdminMaterialItems).toHaveBeenCalledWith(
      new URLSearchParams({ folder_id: "7", project_group_id: "17" })
    );
  });

  fireEvent.click(screen.getByRole("button", { name: "返回共享素材项目组" }));
  expect(await screen.findByRole("button", { name: "打开项目组 秋季上新" })).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: "搜索当前文件夹" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "打开项目组 秋季上新" }));
  await waitFor(() => {
    expect(mockedManagerApi.listAdminMaterialItems).toHaveBeenLastCalledWith(
      new URLSearchParams({ folder_id: "0", project_group_id: "17" })
    );
  });
});


it("creates, renames and deletes manager project groups through manager APIs", async () => {
  render(<ManagerApp />);
  await openManagerMaterials();

  fireEvent.click(await screen.findByRole("button", { name: "新建项目组" }));
  fireEvent.change(screen.getByRole("textbox", { name: "项目组名称" }), {
    target: { value: "  双十一活动  " }
  });
  fireEvent.click(screen.getByRole("button", { name: "创建项目组" }));
  expect(await screen.findByRole("button", { name: "打开项目组 双十一活动" })).toBeInTheDocument();
  expect(mockedManagerApi.createAdminMaterialProjectGroup).toHaveBeenCalledWith("双十一活动");

  fireEvent.click(screen.getByRole("button", { name: "重命名项目组 秋季上新" }));
  fireEvent.change(screen.getByRole("textbox", { name: "项目组名称" }), {
    target: { value: "秋季焕新" }
  });
  fireEvent.click(screen.getByRole("button", { name: "保存项目组名称" }));
  expect(await screen.findByRole("button", { name: "打开项目组 秋季焕新" })).toBeInTheDocument();
  expect(mockedManagerApi.renameAdminMaterialProjectGroup).toHaveBeenCalledWith(17, "秋季焕新");

  fireEvent.click(screen.getByRole("button", { name: "删除项目组 常青产品" }));
  await waitFor(() => {
    expect(mockedManagerApi.deleteAdminMaterialProjectGroup).toHaveBeenCalledWith(18);
  });
  expect(screen.queryByRole("button", { name: "打开项目组 常青产品" })).not.toBeInTheDocument();
});


it("keeps manager group input focused after a duplicate-name response", async () => {
  mockedManagerApi.createAdminMaterialProjectGroup.mockRejectedValueOnce(
    new ApiRequestError("同一团队下已存在同名项目组", "DUPLICATE_GROUP_NAME", 400)
  );
  render(<ManagerApp />);
  await openManagerMaterials();

  fireEvent.click(await screen.findByRole("button", { name: "新建项目组" }));
  const input = screen.getByRole("textbox", { name: "项目组名称" });
  fireEvent.change(input, { target: { value: "秋季上新" } });
  fireEvent.click(screen.getByRole("button", { name: "创建项目组" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("同一团队下已存在同名项目组");
  expect(input).toHaveFocus();
});


it("keeps a non-empty manager project group after a delete conflict", async () => {
  mockedManagerApi.deleteAdminMaterialProjectGroup.mockRejectedValueOnce(
    new ApiRequestError(
      "项目组内仍有文件夹或素材，请先清空后再删除",
      "PROJECT_GROUP_NOT_EMPTY",
      409
    )
  );
  render(<ManagerApp />);
  await openManagerMaterials();

  fireEvent.click(await screen.findByRole("button", { name: "删除项目组 秋季上新" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "项目组内仍有文件夹或素材，请先清空后再删除"
  );
  expect(screen.getByRole("button", { name: "打开项目组 秋季上新" })).toBeInTheDocument();
});


it("keeps a newly created manager group when the initial group response resolves late", async () => {
  const initialGroups = deferred<MaterialProjectGroup[]>();
  mockedManagerApi.listAdminMaterialProjectGroups.mockReturnValueOnce(initialGroups.promise);
  render(<ManagerApp />);
  await openManagerMaterials();

  fireEvent.click(screen.getByRole("button", { name: "新建项目组" }));
  fireEvent.change(screen.getByRole("textbox", { name: "项目组名称" }), {
    target: { value: "双十一活动" }
  });
  fireEvent.click(screen.getByRole("button", { name: "创建项目组" }));
  await waitFor(() => {
    expect(mockedManagerApi.createAdminMaterialProjectGroup).toHaveBeenCalledWith("双十一活动");
  });

  initialGroups.resolve(managerProjectGroups);

  expect(await screen.findByRole("button", { name: "打开项目组 双十一活动" })).toBeInTheDocument();
});


it("ignores an obsolete initial group failure after creating a manager group", async () => {
  const initialGroups = deferred<MaterialProjectGroup[]>();
  mockedManagerApi.listAdminMaterialProjectGroups.mockReturnValueOnce(initialGroups.promise);
  render(<ManagerApp />);
  await openManagerMaterials();

  fireEvent.click(screen.getByRole("button", { name: "新建项目组" }));
  fireEvent.change(screen.getByRole("textbox", { name: "项目组名称" }), {
    target: { value: "双十一活动" }
  });
  fireEvent.click(screen.getByRole("button", { name: "创建项目组" }));
  expect(await screen.findByRole("button", { name: "打开项目组 双十一活动" })).toBeInTheDocument();

  await act(async () => {
    initialGroups.reject(new Error("obsolete group request failed"));
    await Promise.resolve();
  });

  expect(screen.getByRole("button", { name: "打开项目组 双十一活动" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});


it("ignores stale manager material responses after switching project groups", async () => {
  const firstGroupListing = deferred<ReturnType<typeof managerMaterialListing>>();
  const secondGroupFolder = {
    ...managerProductFolder,
    id: 8,
    project_group_id: 18,
    folder_name: "常青资料"
  };
  mockedManagerApi.listAdminMaterialItems.mockImplementation(async (params) => {
    if (params?.get("project_group_id") === "17") return firstGroupListing.promise;
    return {
      project_group_id: 18,
      current_folder: null,
      breadcrumbs: [],
      folders: [secondGroupFolder],
      assets: []
    };
  });
  render(<ManagerApp />);
  await openManagerMaterials();

  fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));
  fireEvent.click(await screen.findByRole("button", { name: "返回共享素材项目组" }));
  fireEvent.click(screen.getByRole("button", { name: "打开项目组 常青产品" }));

  expect(await screen.findByRole("button", { name: "打开文件夹 常青资料" })).toBeInTheDocument();
  firstGroupListing.resolve(managerMaterialListing());
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "打开文件夹 常青资料" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "打开文件夹 产品图" })).not.toBeInTheDocument();
  });
});


it("loads video covers in manager shared materials", async () => {
  mockedManagerApi.listAdminMaterialItems.mockResolvedValue({
    project_group_id: 0,
    current_folder: null,
    breadcrumbs: [],
    folders: [],
    assets: [{
      id: 91,
      tenant_id: 1,
      user_id: 12,
      folder_id: 0,
      product_id: 0,
      package_id: 0,
      file_name: "campaign.mp4",
      file_type: "video",
      mime_type: "video/mp4",
      file_size: 1024,
      create_time: 1,
      update_time: 1
    }]
  });
  render(<ManagerApp />);

  await openManagerMaterials();
  fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));

  await waitFor(() => {
    expect(mockedManagerApi.getAdminMaterialAssetThumbnailBlob).toHaveBeenCalledWith(91);
  });
});
