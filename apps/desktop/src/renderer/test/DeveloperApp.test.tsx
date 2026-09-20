import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { DeveloperApp } from "../DeveloperApp";
import { developerApi } from "../api/developerClient";


vi.mock("../api/developerClient", () => ({
  developerApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
    getPlatformOverview: vi.fn(),
    listPlatformTasks: vi.fn(),
    actOnPlatformTask: vi.fn(),
    listPlatformAlerts: vi.fn(),
    acknowledgePlatformAlert: vi.fn(),
    resolvePlatformAlert: vi.fn(),
    listDeveloperAccounts: vi.fn(),
    createDeveloperAccount: vi.fn(),
    resetDeveloperAccountPassword: vi.fn(),
    updateDeveloperAccountStatus: vi.fn(),
    listPlatformAuditLogs: vi.fn(),
    listCustomerAccounts: vi.fn(),
    updateCustomerAccountStatus: vi.fn(),
    listUserCreationRequests: vi.fn(),
    reviewUserCreationRequest: vi.fn(),
    listViralAnalysisJobs: vi.fn(),
    getViralAnalysisJob: vi.fn(),
    listVideoEditJobs: vi.fn(),
    claimVideoEditJob: vi.fn(),
    deliverVideoEditJob: vi.fn(),
    uploadVideoEditDelivery: vi.fn(),
    getVideoEditMaterialBlob: vi.fn(),
    getVideoEditMaterialsArchiveBlob: vi.fn(),
    getVideoEditDeliveryVersionBlob: vi.fn(),
    getVideoEditDeliveryResourceBlob: vi.fn(),
    getVideoEditHistory: vi.fn(),
    listBillingCustomers: vi.fn(),
    listRechargeOrders: vi.fn(),
    grantRechargeOrder: vi.fn(),
    adjustCredits: vi.fn(),
    listCreditLedger: vi.fn(),
    listPaymentRecords: vi.fn(),
    listMembershipOrders: vi.fn(),
    approveMembershipOrder: vi.fn(),
    rejectMembershipOrder: vi.fn(),
    getAISettings: vi.fn(),
    updateAISetting: vi.fn(),
    clearAISettingKey: vi.fn(),
    testAISetting: vi.fn(),
    listUserFeedback: vi.fn(),
    updateUserFeedback: vi.fn()
  }
}));

const mockedDeveloperApi = vi.mocked(developerApi);


beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.clear();
  mockedDeveloperApi.getCurrentUser.mockResolvedValue({
    id: 1,
    tenant_id: 0,
    login_name: "developer",
    nickname: "开发者",
    user_role: "developer_admin",
    wallet_balance: 0
  });
  mockedDeveloperApi.getPlatformOverview.mockResolvedValue({
    services: [
      { key: "database", label: "MySQL 数据库", status: "healthy", detail: "连接池正常" },
      { key: "publish_worker", label: "发布 Worker", status: "unknown", detail: "外部 Worker" },
      { key: "provider_deepseek", label: "DeepSeek", status: "healthy", detail: "失败率 0%" },
      { key: "provider_doubao", label: "豆包", status: "healthy", detail: "失败率 0%" },
      { key: "storage", label: "文件存储", status: "healthy", detail: "可用空间 80%" }
    ],
    tasks: {
      viral_analysis: { total: 2, pending: 0, running: 0, completed: 1, failed: 1, cancelled: 0 },
      video_edit: { total: 3, pending: 1, running: 1, completed: 1, failed: 0, cancelled: 0 },
      matrix_publish: { total: 4, pending: 1, running: 0, completed: 2, failed: 1, cancelled: 0 }
    },
    ai: {
      calls_24h: 12,
      failures_24h: 1,
      failure_rate: 8.3,
      p95_latency_ms: 1800,
      trend: [
        { timestamp: 1_799_996_400, calls: 5, failures: 0, success_rate: 100, p95_latency_ms: 1200 },
        { timestamp: 1_800_000_000, calls: 7, failures: 1, success_rate: 85.7, p95_latency_ms: 1800 }
      ]
    },
    pool: { size: 10, total: 3, idle: 2, in_use: 1, pre_ping: true, recycle_seconds: 1800, closed: false },
    open_alerts: 2,
    page_alerts: 1,
    active_developers: 1,
    updated_at: 1_800_000_000
  });
  mockedDeveloperApi.listPlatformTasks.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
  mockedDeveloperApi.listPlatformAlerts.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
  mockedDeveloperApi.listDeveloperAccounts.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
  mockedDeveloperApi.listPlatformAuditLogs.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
  mockedDeveloperApi.listCustomerAccounts.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
  mockedDeveloperApi.listUserCreationRequests.mockResolvedValue([]);
  mockedDeveloperApi.listViralAnalysisJobs.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 20,
    total: 0
  });
  mockedDeveloperApi.listVideoEditJobs.mockResolvedValue([]);
  mockedDeveloperApi.getVideoEditHistory.mockResolvedValue([]);
  mockedDeveloperApi.listBillingCustomers.mockResolvedValue([]);
  mockedDeveloperApi.listRechargeOrders.mockResolvedValue({
    items: [], page: 1, page_size: 50, total: 0
  });
  mockedDeveloperApi.listCreditLedger.mockResolvedValue({
    items: [], page: 1, page_size: 50, total: 0
  });
  mockedDeveloperApi.listPaymentRecords.mockResolvedValue({
    items: [], page: 1, page_size: 50, total: 0
  });
  mockedDeveloperApi.listMembershipOrders.mockResolvedValue({
    items: [], page: 1, page_size: 50, total: 0
  });
  mockedDeveloperApi.getAISettings.mockResolvedValue({
    vision: {
      provider: "doubao",
      base_url: "https://ark.cn-beijing.volces.com/api/v3/responses",
      model: "doubao-seed-2-0-lite-260428",
      enabled: true,
      has_key: false,
      masked_key: ""
    },
    copywriting: {
      provider: "deepseek",
      base_url: "https://api.deepseek.com/chat/completions",
      model: "deepseek-v4-flash",
      enabled: true,
      has_key: true,
      masked_key: "sk-t********cret"
    },
    pro_copywriting: {
      provider: "doubao",
      base_url: "https://ark.cn-beijing.volces.com/api/v3/responses",
      model: "doubao-seed-2-1-pro-260628",
      enabled: true,
      has_key: false,
      masked_key: ""
    }
  });
  mockedDeveloperApi.listUserFeedback.mockResolvedValue({
    items: [{
      id: 91,
      tenant_id: 1,
      tenant_name: "禾一斯运营团队",
      user_id: 9,
      user_login_name: "operator",
      user_nickname: "运营一号",
      category: "bug",
      title: "视频预览按钮没有响应",
      description: "进入创作记录后，点击交付视频的预览按钮没有打开播放器。",
      status: "pending",
      developer_reply: "",
      completed_by_user_id: 0,
      completed_time: 0,
      create_time: 1782570600,
      update_time: 1782570600
    }],
    page: 1,
    page_size: 20,
    total: 1
  });
  mockedDeveloperApi.updateUserFeedback.mockImplementation(async (_id, payload) => ({
    id: 91,
    tenant_id: 1,
    tenant_name: "禾一斯运营团队",
    user_id: 9,
    user_login_name: "operator",
    user_nickname: "运营一号",
    category: "bug",
    title: "视频预览按钮没有响应",
    description: "进入创作记录后，点击交付视频的预览按钮没有打开播放器。",
    status: payload.status,
    developer_reply: payload.developer_reply,
    completed_by_user_id: 1,
    completed_time: 1782570800,
    create_time: 1782570600,
    update_time: 1782570800
  }));
});


it("opens the separately built developer workspace for a developer role", async () => {
  render(<DeveloperApp />);

  expect(await screen.findByRole("button", { name: "AI 任务排查" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "平台总览" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "视频交付中心" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "智能创作" })).not.toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "平台工作台" })).toBeInTheDocument();
  expect(screen.getByPlaceholderText("搜索功能、任务、事件…")).toBeInTheDocument();
  expect(screen.getByText("运行正常")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute(
    "href",
    "#developer-main-content"
  );
});


it("opens the platform overview from the developer navigation", async () => {
  render(<DeveloperApp />);

  fireEvent.click(await screen.findByRole("button", { name: "平台总览" }));

  expect(await screen.findByRole("heading", { name: "平台工作台" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "常用应用" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "常用应用" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /统一任务中心/ }).length).toBeGreaterThan(1);
  expect(screen.getAllByRole("button", { name: /告警与事件/ }).length).toBeGreaterThan(1);
  expect(screen.getByRole("region", { name: "核心运行指标" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "待处理事项" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "24 小时运行趋势" })).toBeInTheDocument();
  expect(screen.getByText("P95")).toBeInTheDocument();
  expect(mockedDeveloperApi.getPlatformOverview).toHaveBeenCalledTimes(1);
});


it("completes customer feedback and shows the reply workflow", async () => {
  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "需求反馈" }));

  expect(await screen.findByRole("heading", { name: "用户需求反馈" })).toBeInTheDocument();
  expect(screen.getAllByText("视频预览按钮没有响应").length).toBeGreaterThan(0);
  fireEvent.change(screen.getByLabelText("处理回复"), {
    target: { value: "已完成修复，请刷新后重新预览。" }
  });
  fireEvent.click(screen.getByRole("button", { name: "完成并通知用户" }));

  await waitFor(() => expect(mockedDeveloperApi.updateUserFeedback).toHaveBeenCalledWith(91, {
    status: "completed",
    developer_reply: "已完成修复，请刷新后重新预览。"
  }));
  expect(await screen.findByText("反馈已完成，用户已收到站内通知。")).toBeInTheDocument();
});


it("renders the command-center overview from real API fields without a synthetic score", async () => {
  mockedDeveloperApi.getPlatformOverview.mockResolvedValueOnce({
    services: [
      { key: "database", label: "MySQL 数据库", status: "healthy", detail: "连接池正常" },
      { key: "publish_worker", label: "发布 Worker", status: "healthy", detail: "最近心跳正常" },
      { key: "provider_deepseek", label: "DeepSeek", status: "degraded", detail: "P95 90.9 秒" },
      { key: "provider_doubao", label: "豆包", status: "healthy", detail: "失败率 0%" },
      { key: "storage", label: "文件存储", status: "healthy", detail: "可用空间 80%" }
    ],
    tasks: {
      viral_analysis: { total: 2, pending: 0, running: 0, completed: 2, failed: 0, cancelled: 0 },
      video_edit: { total: 3, pending: 0, running: 0, completed: 3, failed: 0, cancelled: 0 },
      matrix_publish: { total: 4, pending: 0, running: 0, completed: 4, failed: 0, cancelled: 0 }
    },
    ai: {
      calls_24h: 5,
      failures_24h: 0,
      failure_rate: 0,
      p95_latency_ms: 90_946,
      trend: [
        { timestamp: 1_799_996_400, calls: 2, failures: 0, success_rate: 100, p95_latency_ms: 72_000 },
        { timestamp: 1_800_000_000, calls: 3, failures: 0, success_rate: 100, p95_latency_ms: 90_946 }
      ]
    },
    pool: { size: 10, total: 3, idle: 2, in_use: 1, pre_ping: true, recycle_seconds: 1800, closed: false },
    open_alerts: 0,
    page_alerts: 0,
    active_developers: 1,
    updated_at: 1_800_000_000
  });

  render(<DeveloperApp />);

  expect(await screen.findByText("平台存在性能异常")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "常用应用" })).toBeInTheDocument();
  expect(screen.getByText("待处理事项")).toBeInTheDocument();
  expect(screen.getByText("24 小时运行趋势")).toBeInTheDocument();
  expect(screen.getByText("DeepSeek 响应延迟过高")).toBeInTheDocument();
  expect(screen.getAllByText("90.9 秒").length).toBeGreaterThan(0);
  expect(screen.queryByText("平台健康评分")).not.toBeInTheDocument();
});


it("renders alerts as a dense operations table with summary and side insights", async () => {
  mockedDeveloperApi.listPlatformAlerts.mockResolvedValue({
    items: [{
      id: 17,
      alert_type: "video_delivery_overdue",
      severity: "page",
      status: "open",
      title: "视频交付逾期：小红书视频制作需求",
      summary: "任务已超过承诺交付时间 4 小时 22 分",
      source_type: "video_edit_job",
      source_id: 10,
      tenant_id: 1,
      assigned_user_id: 0,
      assigned_user_name: "",
      detected_at: 1_800_000_000,
      last_seen_at: 1_800_000_000,
      acknowledged_at: 0,
      resolved_at: 0,
      resolution: "",
      detail: {}
    }],
    page: 1,
    page_size: 100,
    total: 1
  });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "告警与事件" }));

  expect(await screen.findByRole("heading", { name: "告警与事件" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "告警概览" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "告警事件列表" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "事件分布" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /全部/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "确认并认领" })).toBeInTheDocument();
});


it("shows an explicit empty state when the API has no AI trend points", async () => {
  const overview = await mockedDeveloperApi.getPlatformOverview();
  mockedDeveloperApi.getPlatformOverview.mockResolvedValueOnce({
    ...overview,
    ai: { ...overview.ai, trend: [] }
  });

  render(<DeveloperApp />);

  expect(await screen.findByText("近 24 小时暂无可绘制的 AI 调用趋势")).toBeInTheDocument();
});


it("groups the developer navigation by operational responsibility", async () => {
  render(<DeveloperApp />);

  expect(await screen.findByText("运行监控")).toBeInTheDocument();
  expect(screen.getByText("内容交付")).toBeInTheDocument();
  expect(screen.getByText("资源管理")).toBeInTheDocument();
  expect(screen.getByText("平台安全")).toBeInTheDocument();
  expect(screen.queryByLabelText("界面主题")).not.toBeInTheDocument();
});


it("opens every P0 operations module from developer navigation", async () => {
  render(<DeveloperApp />);

  fireEvent.click(await screen.findByRole("button", { name: "统一任务中心" }));
  expect(await screen.findByRole("heading", { name: "统一任务中心" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "告警与事件" }));
  expect(await screen.findByRole("heading", { name: "告警与事件" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "内部账号权限" }));
  expect(await screen.findByRole("heading", { name: "内部账号权限" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "审计日志" }));
  expect(await screen.findByRole("heading", { name: "审计日志" })).toBeInTheDocument();
});


it("labels a customer-returned video task as returned in the unified queue", async () => {
  mockedDeveloperApi.listPlatformTasks.mockResolvedValueOnce({
    items: [{
      id: 45,
      kind: "video_edit",
      title: "客户临时退回的视频任务",
      tenant_id: 6,
      tenant_name: "测试客户",
      user_id: 21,
      user_name: "内容运营",
      login_name: "operator_01",
      status: "cancelled",
      raw_status: "5",
      error_summary: "",
      available_actions: [],
      created_at: 1_799_900_000,
      updated_at: 1_799_900_100
    }],
    page: 1,
    page_size: 100,
    total: 1
  });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "统一任务中心" }));

  const returnedStatus = await screen.findByText("已退回");
  expect(returnedStatus).toBeInTheDocument();
  expect(returnedStatus.closest("tr")).not.toHaveTextContent("已完成");
});


it("opens the AI Provider configuration page without exposing stored keys", async () => {
  render(<DeveloperApp />);

  fireEvent.click(await screen.findByRole("button", { name: "AI Provider 配置" }));

  expect(await screen.findByRole("heading", { name: "AI Provider 配置" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "豆包视觉解析" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "DeepSeek 文案生成" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "豆包 Pro 对话" })).toBeInTheDocument();
  expect(screen.getByText("sk-t********cret")).toBeInTheDocument();
  expect(screen.queryByDisplayValue("sk-t********cret")).not.toBeInTheDocument();
  expect(mockedDeveloperApi.getAISettings).toHaveBeenCalledTimes(1);
});


it("saves and tests an AI Provider from the developer page", async () => {
  mockedDeveloperApi.updateAISetting.mockImplementation(async (_slot, payload) => ({
    vision: {
      provider: "doubao",
      base_url: "https://ark.cn-beijing.volces.com/api/v3/responses",
      model: payload.model,
      enabled: payload.enabled,
      has_key: true,
      masked_key: "test********-key"
    },
    copywriting: {
      provider: "deepseek",
      base_url: "https://api.deepseek.com/chat/completions",
      model: "deepseek-v4-flash",
      enabled: true,
      has_key: true,
      masked_key: "sk-t********cret"
    },
    pro_copywriting: {
      provider: "doubao",
      base_url: "https://ark.cn-beijing.volces.com/api/v3/responses",
      model: "doubao-seed-2-1-pro-260628",
      enabled: true,
      has_key: false,
      masked_key: ""
    }
  }));
  mockedDeveloperApi.testAISetting.mockResolvedValue({
    success: true,
    slot: "vision",
    provider: "doubao",
    model: "doubao-seed-2-0-lite-260428",
    request_id: "req-doubao-test",
    latency_ms: 420
  });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "AI Provider 配置" }));
  fireEvent.change(await screen.findByLabelText("豆包 API Key"), {
    target: { value: "test-doubao-key" }
  });
  fireEvent.change(screen.getByLabelText("DeepSeek API Key"), {
    target: { value: "unsaved-deepseek-key" }
  });
  fireEvent.click(screen.getByRole("button", { name: "保存豆包配置" }));

  await waitFor(() => {
    expect(mockedDeveloperApi.updateAISetting).toHaveBeenCalledWith("vision", {
      api_key: "test-doubao-key",
      model: "doubao-seed-2-0-lite-260428",
      enabled: true
    });
  });
  expect(screen.getByLabelText("豆包 API Key")).toHaveValue("");
  expect(screen.getByLabelText("DeepSeek API Key")).toHaveValue(
    "unsaved-deepseek-key"
  );

  fireEvent.click(screen.getByRole("button", { name: "测试豆包连接" }));
  expect(await screen.findByText("连接正常 · 420 ms")).toBeInTheDocument();
  expect(mockedDeveloperApi.testAISetting).toHaveBeenCalledWith("vision");
});


it("approves paid membership upgrades from the developer billing page", async () => {
  const plan = {
    id: 3,
    plan_code: "max" as const,
    plan_name: "Max会员版",
    price_cent: 29900,
    summary: "升级云空间",
    features: [],
    monthly_credits: 3000,
    daily_checkin_credits: 20,
    storage_gb: 180,
    status: 1,
    sort_order: 30,
    create_time: 0,
    update_time: 0
  };
  const order = {
    id: 41,
    order_no: "MU-TEST-41",
    tenant_id: 6,
    applicant_user_id: 21,
    applicant_name: "客户管理员",
    applicant_login: "manager_01",
    tenant_name: "禾一团队",
    plan_id: 3,
    plan,
    duration_months: 1,
    amount_cent: 29900,
    payment_channel: "wechat" as const,
    status: 2 as const,
    paid_time: 1_800_000_000,
    reviewed_by_developer_id: 0,
    reviewed_time: 0,
    affected_user_count: 0,
    remark: "",
    create_time: 1_800_000_000,
    update_time: 1_800_000_000
  };
  mockedDeveloperApi.listMembershipOrders.mockResolvedValue({
    items: [order], page: 1, page_size: 50, total: 1
  });
  mockedDeveloperApi.approveMembershipOrder.mockResolvedValue({
    ...order,
    status: 3,
    affected_user_count: 2,
    reviewed_time: 1_800_000_100,
    update_time: 1_800_000_100
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "算力管理" }));

  expect(await screen.findByText("Max会员版")).toBeInTheDocument();
  expect(screen.getByText(/禾一团队/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "审核开通" }));

  await waitFor(() => {
    expect(mockedDeveloperApi.approveMembershipOrder).toHaveBeenCalledWith(41);
  });
});


it("shows unified recharge and membership payment records", async () => {
  mockedDeveloperApi.listPaymentRecords.mockResolvedValue({
    items: [
      {
        record_key: "membership_purchase:41",
        record_type: "membership_purchase",
        record_type_text: "会员购买",
        order_id: 41,
        order_no: "MU-TEST-41",
        tenant_id: 6,
        tenant_name: "禾一团队",
        user_id: 21,
        customer_name: "客户管理员",
        customer_login: "manager_01",
        description: "Max会员版 · 1 个月",
        amount_cent: 29900,
        credits: 0,
        payment_channel: "wechat",
        status: 3,
        status_text: "已开通",
        paid_time: 1_800_000_100,
        create_time: 1_800_000_000,
        update_time: 1_800_000_100
      },
      {
        record_key: "credit_recharge:52",
        record_type: "credit_recharge",
        record_type_text: "算力充值",
        order_id: 52,
        order_no: "RC-TEST-52",
        tenant_id: 6,
        tenant_name: "禾一团队",
        user_id: 22,
        customer_name: "运营一号",
        customer_login: "operator_01",
        description: "自定义算力充值",
        amount_cent: 5000,
        credits: 1000,
        payment_channel: "alipay",
        status: 6,
        status_text: "已付款待发放",
        paid_time: 1_800_000_000,
        create_time: 1_799_999_900,
        update_time: 1_800_000_000
      }
    ],
    page: 1,
    page_size: 50,
    total: 2
  });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "算力管理" }));

  expect(await screen.findByRole("heading", { name: "付款记录" })).toBeInTheDocument();
  expect(screen.getByText("Max会员版 · 1 个月")).toBeInTheDocument();
  expect(screen.getByText("自定义算力充值")).toBeInTheDocument();
  expect(screen.getByText("¥299.00")).toBeInTheDocument();
  expect(screen.getAllByText("已付款待发放").length).toBeGreaterThan(1);
  expect(mockedDeveloperApi.listPaymentRecords).toHaveBeenCalledTimes(1);
});

it("keeps the credit ledger collapsed until the operator expands it", async () => {
  mockedDeveloperApi.listCreditLedger.mockResolvedValue({
    items: [{
      id: 901,
      user_id: 21,
      business_type: "manual_adjustment",
      business_id: 0,
      before_balance: 1_000,
      change_amount: 200,
      after_balance: 1_200,
      reason: "上线前人工补发",
      create_time: 1_800_000_000,
      employee_name: "折叠测试员工",
      employee_login: "ledger_operator",
      tenant_name: "折叠测试团队"
    }],
    page: 1,
    page_size: 50,
    total: 1
  });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "算力管理" }));

  expect(await screen.findByRole("heading", { name: "算力明细" })).toBeInTheDocument();
  expect(screen.queryByText("折叠测试员工")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "展开明细" }));

  expect(await screen.findByText("折叠测试员工")).toBeInTheDocument();
  expect(window.localStorage.getItem("developer-billing-ledger-expanded")).toBe("1");
  expect(screen.getByRole("button", { name: "收起明细" })).toBeInTheDocument();
});

it("queries real audit fields and opens a structured details drawer", async () => {
  mockedDeveloperApi.listPlatformAuditLogs.mockResolvedValue({
    items: [{
      id: 78,
      tenant_id: 6,
      admin_user_id: 3,
      operator_name: "审计员",
      operator_login_name: "auditor_01",
      action: "developer.account.status_update",
      target_type: "app_user",
      target_id: 21,
      detail: {
        reason: "员工离职停用",
        api_key: "[REDACTED]"
      },
      created_at: 1_800_000_000
    }],
    page: 1,
    page_size: 20,
    total: 1
  });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "审计日志" }));

  expect(await screen.findByRole("heading", { name: "审计日志" })).toBeInTheDocument();
  expect(screen.getByText("查询结果")).toBeInTheDocument();
  expect(screen.getByText("当前页记录")).toBeInTheDocument();
  expect(screen.getByText("涉及团队")).toBeInTheDocument();
  expect(screen.getByText("操作人员")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("动作"), {
    target: { value: "developer.account.status_update" }
  });
  fireEvent.change(screen.getByLabelText("目标类型"), {
    target: { value: "app_user" }
  });
  fireEvent.change(screen.getByLabelText("操作人 ID"), {
    target: { value: "3" }
  });
  fireEvent.change(screen.getByLabelText("团队 ID"), {
    target: { value: "6" }
  });
  fireEvent.change(screen.getByLabelText("关键词"), {
    target: { value: "离职" }
  });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));

  await waitFor(() => {
    expect(mockedDeveloperApi.listPlatformAuditLogs).toHaveBeenCalledTimes(2);
  });
  const params = mockedDeveloperApi.listPlatformAuditLogs.mock.calls.at(-1)?.[0];
  expect(params?.get("action")).toBe("developer.account.status_update");
  expect(params?.get("target_type")).toBe("app_user");
  expect(params?.get("operator_id")).toBe("3");
  expect(params?.get("tenant_id")).toBe("6");
  expect(params?.get("keyword")).toBe("离职");

  fireEvent.click(await screen.findByRole("button", { name: "查看详情" }));
  expect(screen.getByRole("dialog", { name: "审计记录详情" })).toBeInTheDocument();
  expect(screen.getAllByText("员工离职停用")).toHaveLength(2);
  expect(screen.getByText("[REDACTED]")).toBeInTheDocument();
});

it("reviews manager user requests from customer account management", async () => {
  mockedDeveloperApi.listCustomerAccounts.mockResolvedValue({
    items: [{
      id: 21,
      tenant_id: 6,
      tenant_name: "禾一团队",
      login_name: "manager_01",
      nickname: "客户管理员",
      user_role: "client_owner",
      status: 1,
      balance: 2860,
      membership_plan_code: "pro",
      membership_plan_name: "Pro",
      last_login_time: 1_800_000_000,
      create_time: 1_799_000_000,
      update_time: 1_800_000_000
    }],
    page: 1,
    page_size: 100,
    total: 1
  });
  mockedDeveloperApi.listUserCreationRequests.mockResolvedValue([{
    id: 8,
    tenant_id: 6,
    tenant_name: "禾一团队",
    requested_by_admin_id: 21,
    requester_name: "客户管理员",
    login_name: "operator_03",
    nickname: "第三位用户",
    requested_status: 1,
    status: "pending",
    reviewed_by_developer_id: 0,
    review_note: "",
    reviewed_time: 0,
    approved_user_id: 0,
    create_time: 1_800_000_000,
    update_time: 1_800_000_000
  }]);
  mockedDeveloperApi.reviewUserCreationRequest.mockResolvedValue({
    id: 8,
    tenant_id: 6,
    tenant_name: "禾一团队",
    requested_by_admin_id: 21,
    requester_name: "客户管理员",
    login_name: "operator_03",
    nickname: "第三位用户",
    requested_status: 1,
    status: "approved",
    reviewed_by_developer_id: 1,
    review_note: "业务需求合理",
    reviewed_time: 1_800_000_100,
    approved_user_id: 22,
    create_time: 1_800_000_000,
    update_time: 1_800_000_100
  });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "客户账号管理" }));

  expect(await screen.findByRole("heading", { name: "管理员与用户管理" })).toBeInTheDocument();
  expect(screen.getByText("第三位用户")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "通过" }));
  fireEvent.change(screen.getByLabelText("操作原因"), {
    target: { value: "业务需求合理" }
  });
  fireEvent.click(screen.getByRole("button", { name: "确认操作" }));

  await waitFor(() => {
    expect(mockedDeveloperApi.reviewUserCreationRequest).toHaveBeenCalledWith(
      8,
      "approve",
      "业务需求合理"
    );
  });
});

it("collapses and restores the developer navigation without hiding page access", async () => {
  const { container } = render(<DeveloperApp />);

  expect(await screen.findByRole("button", { name: "收起侧边栏" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));

  expect(container.querySelector(".developer-shell")).toHaveClass("sidebar-collapsed");
  expect(screen.getByRole("button", { name: "视频交付中心" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "展开侧边栏" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "展开侧边栏" }));
  expect(container.querySelector(".developer-shell")).not.toHaveClass("sidebar-collapsed");
});


it("shows the selected video delivery job with customer, SLA and material details", async () => {
  mockedDeveloperApi.listVideoEditJobs.mockResolvedValue([{
    id: 12,
    tenant_id: 6,
    tenant_name: "测试客户",
    user_id: 21,
    user_login_name: "operator_01",
    user_nickname: "内容运营",
    job_title: "夏季新品视频制作",
    post_title: "夏季新品视频种草",
    post_body: "",
    post_tags: ["夏季新品"],
    review_status: "draft",
    script_text: "前五秒展示新品细节。",
    requirement_text: "节奏自然，保留品牌质感。",
    materials: [{
      material_file_id: 99,
      file_name: "新品素材.mp4",
      file_type: "video",
      file_path: "uploads/material.mp4",
      mime_type: "video/mp4",
      file_size: 1_024_000,
      remark: ""
    }],
    xhs_account_id: 4,
    xhs_account_name: "品牌主号",
    planned_publish_time: 1_800_000_000,
    creation_mode: "standard",
    creation_mode_label: "标准模式",
    request_snapshot: {
      creation_mode: "standard",
      creation_mode_label: "标准模式",
      credit_cost: 140,
      job_title: "夏季新品视频制作",
      post_title: "夏季新品视频种草",
      post_body: "",
      post_tags: ["夏季新品"],
      script_text: "前五秒展示新品细节。",
      requirement_text: "节奏自然，保留品牌质感。",
      materials: [],
      xhs_account_id: 4,
      planned_publish_time: 1_800_000_000,
      submitted_at: 1_799_900_000
    },
    credit_cost: 140,
    publish_credit_cost: 20,
    total_credit_cost: 180,
    publish_plan_id: 0,
    publish_item_id: 0,
    status: 1,
    status_name: "submitted",
    status_text: "待领取",
    user_progress_text: "视频待生成",
    expected_delivery_time: 1_800_000_000,
    sla_status: "due_soon",
    seconds_to_delivery: 3_600,
    operator_user_id: 0,
    operator_name: "",
    developer_note: "",
    delivery: { version: 0 },
    delivery_version_count: 0,
    delivery_versions: [],
    delivered_time: 0,
    create_time: 1_799_900_000,
    update_time: 1_799_900_000
  }]);

  render(<DeveloperApp />);

  fireEvent.click(await screen.findByRole("button", { name: "视频交付中心" }));

  expect(await screen.findByRole("heading", { name: "夏季新品视频制作" })).toBeInTheDocument();
  expect(screen.getByText("测试客户")).toBeInTheDocument();
  expect(screen.getByText("品牌主号")).toBeInTheDocument();
  expect(screen.getByText("新品素材.mp4")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "领取制作任务" })).toBeInTheDocument();
});


it("shows a returned video as terminal without revision actions", async () => {
  mockedDeveloperApi.listVideoEditJobs.mockResolvedValue([{
    id: 29,
    tenant_id: 6,
    tenant_name: "测试客户",
    user_id: 21,
    user_login_name: "operator_01",
    user_nickname: "内容运营",
    job_title: "需要返工的视频制作",
    post_title: "夏季新品视频种草",
    post_body: "",
    post_tags: ["夏季新品"],
    review_status: "rejected",
    script_text: "前五秒展示新品细节。",
    requirement_text: "客户要求调整节奏。",
    materials: [],
    xhs_account_id: 4,
    xhs_account_name: "品牌主号",
    planned_publish_time: 1_800_000_000,
    creation_mode: "standard",
    creation_mode_label: "标准模式",
    request_snapshot: {
      creation_mode: "standard",
      creation_mode_label: "标准模式",
      credit_cost: 140,
      job_title: "需要返工的视频制作",
      post_title: "夏季新品视频种草",
      post_body: "",
      post_tags: ["夏季新品"],
      script_text: "前五秒展示新品细节。",
      requirement_text: "客户要求调整节奏。",
      materials: [],
      xhs_account_id: 4,
      planned_publish_time: 1_800_000_000,
      submitted_at: 1_799_900_000
    },
    credit_cost: 140,
    publish_credit_cost: 20,
    total_credit_cost: 180,
    publish_plan_id: 9,
    publish_item_id: 9,
    status: 5,
    status_name: "returned",
    status_text: "已退回",
    user_progress_text: "该视频任务已退回，请重新发起视频制作",
    expected_delivery_time: 1_800_000_000,
    sla_status: "returned",
    seconds_to_delivery: 3_600,
    operator_user_id: 1,
    operator_name: "开发者",
    developer_note: "初版已交付",
    delivery: { version: 1 },
    delivery_version_count: 1,
    delivery_versions: [{ version: 1, delivery_file_name: "revision-v1.mp4" }],
    delivered_time: 1_799_900_100,
    create_time: 1_799_900_000,
    update_time: 1_799_900_100
  }]);

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "视频交付中心" }));

  expect((await screen.findAllByText("已退回")).length).toBeGreaterThan(0);
  expect(screen.queryByText("客户已退回，请继续修改后重新交付。")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "继续修改视频" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "领取制作任务" })).not.toBeInTheDocument();
  expect(screen.queryByText("已完成交付")).not.toBeInTheDocument();
});


it("downloads an uploaded delivery version through a connected browser link", async () => {
  mockedDeveloperApi.listVideoEditJobs.mockResolvedValue([{
    id: 12,
    tenant_id: 6,
    tenant_name: "测试客户",
    user_id: 21,
    user_login_name: "operator_01",
    user_nickname: "内容运营",
    job_title: "夏季新品视频制作",
    post_title: "夏季新品视频种草",
    post_body: "",
    post_tags: ["夏季新品"],
    review_status: "draft",
    script_text: "前五秒展示新品细节。",
    requirement_text: "节奏自然。",
    materials: [],
    xhs_account_id: 4,
    xhs_account_name: "品牌主号",
    planned_publish_time: 1_800_000_000,
    creation_mode: "standard",
    creation_mode_label: "标准模式",
    request_snapshot: {
      creation_mode: "standard",
      creation_mode_label: "标准模式",
      credit_cost: 140,
      job_title: "夏季新品视频制作",
      post_title: "夏季新品视频种草",
      post_body: "",
      post_tags: ["夏季新品"],
      script_text: "前五秒展示新品细节。",
      requirement_text: "节奏自然。",
      materials: [],
      xhs_account_id: 4,
      planned_publish_time: 1_800_000_000,
      submitted_at: 1_799_900_000
    },
    credit_cost: 140,
    publish_credit_cost: 20,
    total_credit_cost: 180,
    publish_plan_id: 1,
    publish_item_id: 1,
    status: 3,
    status_name: "delivered",
    status_text: "已交付",
    user_progress_text: "视频可预览下载",
    expected_delivery_time: 1_800_000_000,
    sla_status: "completed",
    seconds_to_delivery: 0,
    operator_user_id: 1,
    operator_name: "开发者",
    developer_note: "",
    delivery: { version: 1 },
    delivery_version_count: 1,
    delivery_versions: [{
      version: 1,
      delivery_file_name: "final-cut.mp4",
      delivered_time: 1_799_900_100
    }],
    delivered_time: 1_799_900_100,
    create_time: 1_799_900_000,
    update_time: 1_799_900_100
  }]);
  mockedDeveloperApi.getVideoEditDeliveryVersionBlob.mockResolvedValue(
    new Blob(["video"], { type: "video/mp4" })
  );
  const createObjectUrl = vi.fn(() => "blob:delivery");
  const revokeObjectUrl = vi.fn();
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: createObjectUrl,
    revokeObjectURL: revokeObjectUrl
  });
  let wasConnectedWhenClicked = false;
  const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(function click(this: HTMLAnchorElement) {
      wasConnectedWhenClicked = this.isConnected;
    });

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "视频交付中心" }));
  fireEvent.click(await screen.findByRole("button", { name: "下载" }));

  await waitFor(() => {
    expect(mockedDeveloperApi.getVideoEditDeliveryVersionBlob).toHaveBeenCalledWith(12, 1);
    expect(clickSpy).toHaveBeenCalled();
  });
  expect(wasConnectedWhenClicked).toBe(true);
  expect(createObjectUrl).toHaveBeenCalled();
});


it("offers independent video, voiceover and subtitle delivery uploads", async () => {
  mockedDeveloperApi.listVideoEditJobs.mockResolvedValue([{
    id: 18,
    tenant_id: 6,
    tenant_name: "测试客户",
    user_id: 21,
    user_login_name: "operator_01",
    user_nickname: "内容运营",
    job_title: "三类资源交付",
    post_title: "三类资源交付",
    post_body: "",
    post_tags: [],
    review_status: "draft",
    script_text: "测试脚本",
    requirement_text: "",
    materials: [],
    xhs_account_id: 4,
    xhs_account_name: "品牌主号",
    planned_publish_time: 1_800_000_000,
    creation_mode: "pro",
    creation_mode_label: "AI智能创作 Pro",
    request_snapshot: {
      creation_mode: "pro",
      creation_mode_label: "AI智能创作 Pro",
      credit_cost: 180,
      job_title: "三类资源交付",
      post_title: "三类资源交付",
      post_body: "",
      post_tags: [],
      script_text: "测试脚本",
      requirement_text: "",
      materials: [],
      xhs_account_id: 4,
      planned_publish_time: 1_800_000_000,
      submitted_at: 1_799_900_000
    },
    credit_cost: 180,
    publish_credit_cost: 20,
    total_credit_cost: 180,
    publish_plan_id: 0,
    publish_item_id: 0,
    status: 2,
    status_name: "in_production",
    status_text: "制作中",
    user_progress_text: "制作中",
    expected_delivery_time: 1_800_000_000,
    sla_status: "normal",
    seconds_to_delivery: 3600,
    operator_user_id: 1,
    operator_name: "开发者",
    developer_note: "",
    delivery: { version: 0 },
    delivery_version_count: 0,
    delivery_versions: [],
    delivery_assets: [],
    delivery_resource_counts: { video: 0, voiceover: 0, subtitle: 0 },
    delivered_time: 0,
    create_time: 1_799_900_000,
    update_time: 1_799_900_000
  }]);

  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "视频交付中心" }));

  expect(await screen.findByText("视频成片（MP4 / MOV）")).toBeInTheDocument();
  expect(screen.getByText("口播音频（MP3）")).toBeInTheDocument();
  expect(screen.getByText("字幕文件（SRT / TXT）")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "上传视频成片" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "上传口播音频" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "上传字幕文件" })).toBeDisabled();
});


it("rejects a customer role before loading internal data", async () => {
  mockedDeveloperApi.getCurrentUser.mockResolvedValue({
    id: 9,
    tenant_id: 1,
    login_name: "operator",
    nickname: "运营",
    user_role: "customer",
    wallet_balance: 0
  });

  render(<DeveloperApp />);

  expect(await screen.findByRole("heading", { name: "内部系统登录" })).toBeInTheDocument();
  expect(screen.getByText("当前账号没有开发者端访问权限")).toBeInTheDocument();
  expect(mockedDeveloperApi.listViralAnalysisJobs).not.toHaveBeenCalled();
  expect(mockedDeveloperApi.listVideoEditJobs).not.toHaveBeenCalled();
});
