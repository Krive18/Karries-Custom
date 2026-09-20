import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { ApiRequestError, api } from "../api/client";


vi.mock("../api/client", () => {
  const client = {
    login: vi.fn(),
    generateImageCopy: vi.fn(),
    listTasks: vi.fn(),
    createTask: vi.fn(),
    submitTask: vi.fn(),
    listAccounts: vi.fn(),
    createAccount: vi.fn(),
    checkRuntime: vi.fn(),
    listXHSAccounts: vi.fn(),
    createXHSAccount: vi.fn(),
    updateXHSAccount: vi.fn(),
    deleteXHSAccount: vi.fn(),
    startXHSAccountLogin: vi.fn(),
    getLatestXHSAccountLoginSession: vi.fn(),
    checkXHSAccountLogin: vi.fn(),
    listContentDrafts: vi.fn(),
    listSmartCreationHistory: vi.fn(),
    createManualContentDraft: vi.fn(),
    updateContentDraft: vi.fn(),
    listMatrixPlans: vi.fn(),
    getMatrixPlan: vi.fn(),
    listMatrixPlanItems: vi.fn(),
    createMatrixPlanFromDrafts: vi.fn(),
    confirmMatrixPlan: vi.fn(),
    cancelMatrixPlan: vi.fn(),
    retryFailedMatrixPlanItems: vi.fn(),
    listVideoEditJobs: vi.fn(),
    createVideoEditJob: vi.fn(),
    getVideoEditJobHistory: vi.fn(),
    getVideoEditDeliveryVersionBlob: vi.fn(),
    getVideoEditDeliveryResourceBlob: vi.fn(),
    updateVideoEditPublishContent: vi.fn(),
    requestVideoEditRevision: vi.fn(),
    optimizeVideoScript: vi.fn(),
    listInspirationSessions: vi.fn(),
    createInspirationSession: vi.fn(),
    getInspirationSession: vi.fn(),
    sendInspirationMessage: vi.fn(),
    saveInspirationMessageDraft: vi.fn(),
    archiveInspirationSession: vi.fn(),
    setInspirationSessionPinned: vi.fn(),
    renameInspirationSession: vi.fn(),
    deleteInspirationSession: vi.fn(),
    getInspirationPersonalization: vi.fn(),
    updateInspirationPersonalization: vi.fn(),
    listInspirationPersonalizationTemplates: vi.fn(),
    createInspirationPersonalizationTemplate: vi.fn(),
    updateInspirationPersonalizationTemplate: vi.fn(),
    duplicateInspirationPersonalizationTemplate: vi.fn(),
    archiveInspirationPersonalizationTemplate: vi.fn(),
    getInspirationPersonalizationPreference: vi.fn(),
    updateInspirationPersonalizationPreference: vi.fn(),
    uploadMaterialAsset: vi.fn(),
    listMaterialProjectGroups: vi.fn(),
    listMaterialLibraryItems: vi.fn(),
    createMaterialFolder: vi.fn(),
    renameMaterialFolder: vi.fn(),
    deleteMaterialFolder: vi.fn(),
    updateMaterialAsset: vi.fn(),
    deleteMaterialAsset: vi.fn(),
    getMaterialAssetBlob: vi.fn(),
    getMaterialAssetThumbnailBlob: vi.fn(),
    getCurrentUser: vi.fn(),
    getWallet: vi.fn(),
    listCreditLedger: vi.fn(),
    listMembershipPlans: vi.fn(),
    getCurrentMembership: vi.fn(),
    getDailyCheckinStatus: vi.fn(),
    dailyCheckIn: vi.fn(),
    listNotifications: vi.fn(),
    getUnreadNotificationCount: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
    listUserFeedback: vi.fn(),
    createUserFeedback: vi.fn(),
    listRechargePackages: vi.fn(),
    listRechargeOrders: vi.fn(),
    createRechargeOrder: vi.fn(),
    submitRechargePaymentProof: vi.fn(),
    getRechargePaymentProofBlob: vi.fn(),
    createViralAnalysisJob: vi.fn(),
    listViralAnalysisJobs: vi.fn(),
    getViralAnalysisJob: vi.fn(),
    getViralAnalysisMaterialBlob: vi.fn(),
    uploadViralAnalysisMaterial: vi.fn(),
    selectViralAnalysisLibraryMaterial: vi.fn(),
    runViralAnalysisJob: vi.fn(),
    cancelViralAnalysisJob: vi.fn(),
    createContentCollection: vi.fn(),
    listContentCollections: vi.fn(),
    getContentCollection: vi.fn(),
    updateContentCollection: vi.fn()
  };

  return {
    ApiRequestError: class ApiRequestError extends Error {
      constructor(message: string, public readonly code: string, public readonly status: number) {
        super(message);
      }
    },
    api: client,
    customerApi: client
  };
});


const mockedApi = vi.mocked(api);


const account = {
  id: 7,
  account_name: "品牌运营号",
  platform: "xiaohongshu",
  cookie_path: "accounts/brand.json",
  status: 1,
  last_checked_time: 0,
  create_time: 0,
  update_time: 0
};


const taskView = {
  id: 11,
  account_id: 7,
  task_title: "后端返回任务",
  task_body: "后端正文",
  tags: ["禾一斯"],
  image_paths: ["D:/images/look.png"],
  schedule_time: 1782570600,
  status: 1,
  last_error: "",
  submitted_time: 0,
  create_time: 0,
  update_time: 0
};


const xhsAccount = {
  id: 27,
  user_id: 9,
  display_name: "禾一斯品牌主号",
  account_group: "品牌号",
  status: 1,
  daily_limit: 2,
  min_interval_minutes: 360,
  last_publish_time: 0,
  today_publish_count: 0,
  login_state_ready: true,
  create_time: 0,
  update_time: 0,
  profile: {
    domain_name: "女装穿搭",
    persona: "专业穿搭顾问",
    target_audience: "25-35 岁通勤女性",
    content_style: "自然真实",
    tone: "自然真诚",
    common_phrases: "",
    forbidden_phrases: "",
    tag_preferences: "[]",
    word_count_preference: 300,
    topic_preferences: ""
  }
};

const xhsLoginSession = {
  id: 301,
  xhs_account_id: 27,
  status: "awaiting_scan" as const,
  message: "请使用小红书 App 扫码",
  qrcode_image_data: "data:image/png;base64,cXJjb2Rl",
  started_time: 1782570600,
  expires_time: 1782570900,
  completed_time: 0,
  create_time: 1782570600,
  update_time: 1782570601
};

const contentDraft = {
  id: 801,
  user_id: 9,
  product_id: 0,
  xhs_account_id: 0,
  source_type: "inspiration",
  content_type: "image_text" as const,
  title: "AI 生成的小红书笔记",
  body: "这是一条已经完成人工审核的小红书正文。",
  tags: ["新品", "种草"],
  material: { image_paths: ["D:/fixtures/product.jpg"] },
  status: "confirmed" as const,
  ai_provider: "deepseek",
  model_name: "deepseek-chat",
  prompt: {},
  create_time: 1782570600,
  update_time: 1782570601
};

const matrixPlan = {
  id: 901,
  user_id: 9,
  plan_name: "本周新品发布计划",
  source_type: "content_draft",
  content_type: "image_text",
  product_id: 0,
  status: 2 as const,
  schedule_start_time: 1782574200,
  schedule_end_time: 1782660600,
  scheduling_rule: {
    draft_ids: [801],
    xhs_account_ids: [27],
    min_interval_minutes: 360
  },
  item_count: 1,
  create_time: 1782570600,
  update_time: 1782570601
};

const matrixPlanItem = {
  id: 1001,
  plan_id: 901,
  user_id: 9,
  xhs_account_id: 27,
  content_type: "image_text",
  title: "AI 生成的小红书笔记",
  body: "这是一条已经完成人工审核的小红书正文。",
  tags: ["新品", "种草"],
  material: { image_paths: ["D:/fixtures/product.jpg"] },
  scheduled_time: 1782574200,
  status: 1 as const,
  last_error: "",
  attempt_count: 0,
  max_attempts: 3,
  next_retry_time: 0,
  submitted_time: 0,
  publish_result: {},
  create_time: 1782570600,
  update_time: 1782570601
};

const videoEditJob = {
  id: 31,
  tenant_id: 1,
  tenant_name: "禾一斯",
  user_id: 9,
  user_login_name: "karries_local_test",
  user_nickname: "禾一斯员工",
  job_title: "禾一斯小红书种草视频剪辑",
  post_title: "禾一斯新品视频种草",
  post_body: "",
  post_tags: ["禾一斯", "视频种草"],
  review_status: "draft" as const,
  script_text: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
  requirement_text: "节奏自然，保留高级感。",
  materials: [
    {
      material_file_id: 0,
      file_name: "look.mp4",
      file_type: "video" as const,
      file_path: "look.mp4",
      mime_type: "video/mp4",
      file_size: 1024,
      remark: ""
    }
  ],
  creation_mode: "standard" as const,
  creation_mode_label: "标准模式",
  request_snapshot: {
    creation_mode: "standard" as const,
    creation_mode_label: "标准模式",
    credit_cost: 140,
    job_title: "禾一斯小红书种草视频剪辑",
    post_title: "禾一斯新品视频种草",
    post_body: "",
    post_tags: ["禾一斯", "视频种草"],
    script_text: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
    requirement_text: "节奏自然，保留高级感。",
    materials: [],
    xhs_account_id: 7,
    xhs_account_name: "测试",
    planned_publish_time: 1782600000,
    submitted_at: 1782570600
  },
  xhs_account_id: 7,
  planned_publish_time: 1782600000,
  credit_cost: 140,
  publish_credit_cost: 20,
  total_credit_cost: 160,
  publish_plan_id: 81,
  publish_item_id: 91,
  status: 1,
  status_name: "submitted" as const,
  status_text: "视频待生成",
  user_progress_text: "素材和脚本已提交，预计 24 小时内生成完毕",
  expected_delivery_time: 1782600000,
  sla_status: "normal" as const,
  seconds_to_delivery: 24 * 60 * 60,
  operator_user_id: 0,
  operator_name: "",
  developer_note: "",
  delivery: { version: 0 },
  delivery_version_count: 0,
  delivery_versions: [],
  revision_count: 0,
  latest_revision_request_id: 0,
  latest_revision_feedback: "",
  latest_revision_status: "" as const,
  xhs_account_name: "测试",
  delivered_time: 0,
  create_time: 0,
  update_time: 0
};

const inspirationSession = {
  id: 41,
  tenant_id: 1,
  user_id: 9,
  title: "新品种草选题",
  linked_product_id: 12,
  linked_xhs_account_id: 7,
  goal_type: "topic" as const,
  interaction_mode: "personalized" as const,
  tone: "自然真诚",
  extra_requirement: "突出产品使用场景",
  generation_token: "",
  generation_started_time: 0,
  status: "active" as const,
  message_count: 2,
  total_credit_cost: 0,
  create_time: 1782570600,
  update_time: 1782570660
};

const inspirationDetail = {
  session: inspirationSession,
  messages: [
    {
      id: 501,
      tenant_id: 1,
      session_id: 41,
      user_id: 9,
      role: "user" as const,
      content: "给我 5 个新品选题",
      context: {},
      ai_provider: "",
      ai_model: "",
      credit_cost: 0,
      latency_ms: 0,
      status: "success" as const,
      error_message: "",
      content_draft_id: 0,
      create_time: 1782570600
    },
    {
      id: 502,
      tenant_id: 1,
      session_id: 41,
      user_id: 9,
      role: "assistant" as const,
      content: "这里是 AI 返回的运营建议",
      context: {},
      ai_provider: "deepseek",
      ai_model: "deepseek-chat",
      credit_cost: 0,
      latency_ms: 80,
      status: "success" as const,
      error_message: "",
      content_draft_id: 0,
      create_time: 1782570660
    }
  ]
};

const inspirationPersonalization = {
  id: 0,
  tenant_id: 1,
  user_id: 9,
  assistant_name: "Karries AI",
  assistant_traits: "专业、耐心、务实",
  preferred_address: "",
  occupation: "",
  user_details: "",
  response_preferences: "先给结论，再给可执行建议",
  create_time: 0,
  update_time: 0
};

const inspirationTemplate = {
  ...inspirationPersonalization,
  id: 301,
  template_name: "品牌运营顾问",
  status: "active" as const
};

const inspirationPreference = {
  id: 401,
  tenant_id: 1,
  user_id: 9,
  interaction_mode: "personalized" as const,
  personalization_template_id: inspirationTemplate.id,
  create_time: 1782570700,
  update_time: 1782570700
};

const secondInspirationSession = {
  ...inspirationSession,
  id: 42,
  title: "门店活动内容策略",
  linked_product_id: 0,
  total_credit_cost: 0
};

const viralResult = {
  hook_summary: "前三秒抛出护肤痛点", structure_summary: "痛点、使用、对比、引导收藏", shot_rhythm: "每 2 秒切换一个信息点",
  script_breakdown: "开头展示肤感，中段说明成分，结尾引导收藏", selling_points: "轻薄、不黏、适合通勤",
  reuse_suggestions: "用真实通勤场景开场，再给出一条可执行的护肤建议", rewritten_script: "通勤前别再厚涂，轻薄防晒这样用。",
  setting_analysis: "", lighting_analysis: "", visual_style: "", timeline_visual_analysis: [], visual_evidence: [],
  tags: ["护肤", "通勤"], create_time: 1782570700
};

const viralJob = {
  id: 71, tenant_id: 1, user_id: 9, title: "防晒爆款视频拆解", source_type: "text" as const, source_url: "", material_file_id: 0,
  analysis_goal: ["hook", "structure", "script", "reuse"] as Array<"hook" | "structure" | "script" | "reuse">, supplement_text: "前三秒展示通勤前防晒痛点，中段说明肤感，结尾引导收藏。",
  status: "completed" as const, credit_cost: 100, create_time: 1782570600, update_time: 1782570700, materials: [], result: viralResult
};

const contentCollection = {
  id: 901,
  tenant_id: 1,
  user_id: 9,
  source_type: "viral_analysis" as const,
  source_id: viralJob.id,
  title: viralJob.title,
  ...viralResult,
  source_context: {
    analysis_goal: viralJob.analysis_goal,
    source_type: viralJob.source_type,
    source_url: viralJob.source_url
  },
  create_time: 1782570700,
  update_time: 1782570700
};

const viralMaterial = {
  id: 1,
  job_id: 71,
  file_name: "reference.mp4",
  file_type: "video" as const,
  mime_type: "video/mp4",
  file_size: 5,
  create_time: 1782570601
};

const materialAsset = {
  id: 101,
  tenant_id: 1,
  user_id: 9,
  folder_id: 0,
  product_id: 0,
  package_id: 0,
  file_name: "look.png",
  file_type: "image" as const,
  mime_type: "image/png",
  file_size: 1024,
  create_time: 1782570601,
  update_time: 1782570601
};

const materialFolder = {
  id: 12,
  tenant_id: 1,
  project_group_id: 1,
  parent_id: 0,
  folder_name: "马卡龙美甲产品资料",
  created_by_user_id: 9,
  child_folder_count: 0,
  asset_count: 1,
  create_time: 1782570600,
  update_time: 1782570601
};

const materialProjectGroup = {
  id: 1,
  tenant_id: 1,
  group_name: "品牌产品",
  created_by_user_id: 9,
  folder_count: 1,
  asset_count: 1,
  create_time: 1782570600,
  update_time: 1782570601
};

const developerViralJob = {
  ...viralJob, ai_provider: "deepseek", ai_model: "deepseek-chat", error_message: "", latest_ai_usage: {
    id: 201, status: "success" as const, provider: "deepseek", model_name: "deepseek-chat", latency_ms: 810,
    input_chars: 88, output_chars: 356, credit_cost: 100, error_message: "", create_time: 1782570700
  }
};

const membershipPlans = [
  {
    id: 1, plan_code: "free" as const, plan_name: "免费版", price_cent: 0,
    summary: "适合体验基础内容创作能力", features: ["注册即享 500 算力新人礼"],
    monthly_credits: 500, daily_checkin_credits: 20, storage_gb: 10, status: 1, sort_order: 10,
    create_time: 1, update_time: 1
  },
  {
    id: 2, plan_code: "pro" as const, plan_name: "Pro会员版", price_cent: 19900,
    summary: "平台全部核心功能均可使用，覆盖创作、解析与定时发布",
    features: ["平台全部核心功能", "爆款解析与复刻", "定时发布与矩阵账号管理"],
    monthly_credits: 1500, daily_checkin_credits: 20, storage_gb: 100, status: 1, sort_order: 20,
    create_time: 1, update_time: 1
  },
  {
    id: 3, plan_code: "max" as const, plan_name: "Max会员版", price_cent: 29900,
    summary: "包含 Pro 会员全部功能，并升级至 180GB 云空间", features: ["包含 Pro 会员全部功能", "享 180GB 云空间"],
    monthly_credits: 3000, daily_checkin_credits: 20, storage_gb: 180, status: 1, sort_order: 30,
    create_time: 1, update_time: 1
  },
  {
    id: 4, plan_code: "storage" as const, plan_name: "存储大会员版", price_cent: 59900,
    summary: "包含 Pro 会员全部功能，并升级至 1000GB 云空间", features: ["包含 Pro 会员全部功能", "享 1000GB 云空间"],
    monthly_credits: 3000, daily_checkin_credits: 20, storage_gb: 1000, status: 1, sort_order: 40,
    create_time: 1, update_time: 1
  }
];

const currentMembership = {
  id: 1, tenant_id: 1, user_id: 9, plan_id: 2, status: 1 as const,
  start_time: 1, expire_time: 0, auto_renew: 0, create_time: 1, update_time: 1,
  plan: membershipPlans[1]
};

const walletView = {
  id: 1, user_id: 9, balance: 30, total_recharged: 50, total_consumed: 20,
  create_time: 1, update_time: 1
};

const rechargePackages = [
  {
    id: 1, package_name: "1000 元算力包", base_credits: 20000, credits: 20000, price_cent: 100000,
    is_hot: 0, status: 1, sort_order: 10, create_time: 1, update_time: 1
  }
];

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason?: unknown) => void = () => undefined;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}


beforeEach(() => {
  vi.resetAllMocks();
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:viral-reference-preview")
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn()
  });
  window.localStorage.clear();
  window.localStorage.setItem("viral-analysis-history-expanded", "1");
  delete window.karriesPublisher;
  mockedApi.login.mockImplementation(async () => {
    window.localStorage.setItem("karries_customer_access_token", "local-access-token");
    return {
      access_token: "local-access-token",
      token_type: "bearer",
      expires_in: 3600,
      user: {
        id: 9,
        tenant_id: 1,
        login_name: "operator",
        nickname: "运营",
        user_role: "customer",
        wallet_balance: 30
      }
    };
  });
  mockedApi.getCurrentUser.mockResolvedValue({ id: 9, tenant_id: 1, login_name: "operator", nickname: "运营", user_role: "customer", wallet_balance: 30 });
  mockedApi.listNotifications.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 20,
    total: 0
  });
  mockedApi.getUnreadNotificationCount.mockResolvedValue({ count: 0 });
  mockedApi.markNotificationRead.mockResolvedValue({ id: 1, is_read: true });
  mockedApi.markAllNotificationsRead.mockResolvedValue({ updated_count: 0 });
  mockedApi.listUserFeedback.mockResolvedValue({
    items: [], page: 1, page_size: 20, total: 0
  });
  mockedApi.createUserFeedback.mockImplementation(async (payload) => ({
    id: 91,
    tenant_id: 1,
    tenant_name: "禾一斯",
    user_id: 9,
    user_login_name: "operator",
    user_nickname: "运营",
    category: payload.category,
    title: payload.title,
    description: payload.description,
    status: "pending",
    developer_reply: "",
    completed_by_user_id: 0,
    completed_time: 0,
    create_time: 1782570600,
    update_time: 1782570600
  }));
  mockedApi.getWallet.mockResolvedValue(walletView);
  mockedApi.listCreditLedger.mockResolvedValue([]);
  mockedApi.listMembershipPlans.mockResolvedValue(membershipPlans);
  mockedApi.getCurrentMembership.mockResolvedValue(currentMembership);
  mockedApi.getDailyCheckinStatus.mockResolvedValue({
    checked_in: false,
    checkin_date: "2026-07-28",
    credits: 20,
    balance: 30
  });
  mockedApi.dailyCheckIn.mockResolvedValue({
    checked_in: true,
    already_checked_in: false,
    checkin_date: "2026-07-28",
    credits: 20,
    balance: 50
  });
  mockedApi.listRechargePackages.mockResolvedValue(rechargePackages);
  mockedApi.listRechargeOrders.mockResolvedValue([]);
  mockedApi.createRechargeOrder.mockResolvedValue({
    id: 1,
    order_no: "RC-TEST",
    tenant_id: 1,
    user_id: 9,
    recharge_type: "online",
    package_id: 0,
    package_name: "",
    amount_cent: 5000,
    requested_credits: 1000,
    payment_channel: "alipay",
    status: 1,
    remark: "",
    paid_time: 0,
    completed_time: 0,
    create_time: 1,
    update_time: 1
  });
  mockedApi.submitRechargePaymentProof.mockResolvedValue({
    id: 1,
    order_no: "RC-TEST",
    tenant_id: 1,
    user_id: 9,
    recharge_type: "online",
    package_id: 0,
    package_name: "",
    amount_cent: 5000,
    requested_credits: 1000,
    payment_channel: "alipay",
    status: 2,
    remark: "",
    payer_note: "",
    proof_file_name: "payment.png",
    proof_mime_type: "image/png",
    proof_file_size: 128,
    proof_submit_time: 1,
    has_payment_proof: true,
    paid_time: 1,
    completed_time: 0,
    create_time: 1,
    update_time: 1
  });
  mockedApi.getRechargePaymentProofBlob.mockResolvedValue(
    new Blob(["proof"], { type: "image/png" })
  );
  mockedApi.listAccounts.mockResolvedValue([account]);
  mockedApi.listTasks.mockResolvedValue([]);
  mockedApi.generateImageCopy.mockResolvedValue({
    title: "后端生成标题",
    body: "后端生成正文",
    tags: ["禾一斯", "小红书种草"]
  });
  mockedApi.createTask.mockResolvedValue(taskView);
  mockedApi.submitTask.mockResolvedValue({ ...taskView, status: 5, submitted_time: 1782570601 });
  mockedApi.checkRuntime.mockResolvedValue({});
  mockedApi.listXHSAccounts.mockResolvedValue([xhsAccount]);
  mockedApi.createXHSAccount.mockResolvedValue(xhsAccount);
  mockedApi.updateXHSAccount.mockResolvedValue(xhsAccount);
  mockedApi.deleteXHSAccount.mockResolvedValue({ deleted: true });
  mockedApi.startXHSAccountLogin.mockResolvedValue(xhsLoginSession);
  mockedApi.getLatestXHSAccountLoginSession.mockResolvedValue(xhsLoginSession);
  mockedApi.checkXHSAccountLogin.mockResolvedValue({
    valid: true,
    account: { ...xhsAccount, status: 1, login_state_ready: true }
  });
  mockedApi.listContentDrafts.mockResolvedValue([]);
  mockedApi.listSmartCreationHistory.mockResolvedValue([]);
  mockedApi.createManualContentDraft.mockResolvedValue(contentDraft);
  mockedApi.updateContentDraft.mockImplementation(async (_draftId, payload) => ({
    ...contentDraft,
    ...payload
  }));
  mockedApi.listMatrixPlans.mockResolvedValue([]);
  mockedApi.getMatrixPlan.mockResolvedValue(matrixPlan);
  mockedApi.listMatrixPlanItems.mockResolvedValue([]);
  mockedApi.createMatrixPlanFromDrafts.mockResolvedValue({
    id: 901,
    item_count: 1,
    draft_count: 1,
    account_count: 1
  });
  mockedApi.confirmMatrixPlan.mockResolvedValue({ id: 901, status: 3, item_count: 1 });
  mockedApi.cancelMatrixPlan.mockResolvedValue({ id: 901, status: 7, cancelled_item_count: 1 });
  mockedApi.retryFailedMatrixPlanItems.mockResolvedValue({
    id: 901,
    status: 3,
    retried_item_count: 1
  });
  mockedApi.listVideoEditJobs.mockResolvedValue([]);
  mockedApi.createVideoEditJob.mockResolvedValue(videoEditJob);
  mockedApi.getVideoEditDeliveryVersionBlob.mockResolvedValue(
    new Blob(["video"], { type: "video/mp4" })
  );
  mockedApi.getVideoEditDeliveryResourceBlob.mockResolvedValue(
    new Blob(["resource"], { type: "application/octet-stream" })
  );
  mockedApi.updateVideoEditPublishContent.mockImplementation(async (_jobId, payload) => ({
    ...videoEditJob,
    post_title: payload.post_title,
    post_body: payload.post_body,
    post_tags: payload.post_tags,
    review_status: payload.review_status
  }));
  mockedApi.requestVideoEditRevision.mockImplementation(async (_jobId, payload) => ({
    ...videoEditJob,
    status: 4,
    status_name: "revision_requested",
    status_text: "待返修",
    user_progress_text: "已提交修改意见，正在等待二次剪辑",
    revision_count: 1,
    latest_revision_request_id: 1,
    latest_revision_feedback: payload.feedback,
    latest_revision_status: "submitted"
  }));
  mockedApi.optimizeVideoScript.mockResolvedValue({
    original_script: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
    optimized_script: "0-3秒用产品特写抓住注意力，中段切换真实佩戴场景，结尾自然引导收藏咨询。"
  });
  mockedApi.listInspirationSessions.mockResolvedValue({
    items: [inspirationSession],
    page: 1,
    page_size: 20,
    total: 1
  });
  mockedApi.createInspirationSession.mockResolvedValue(inspirationSession);
  mockedApi.getInspirationSession.mockResolvedValue(inspirationDetail);
  mockedApi.sendInspirationMessage.mockResolvedValue({
    user_message: inspirationDetail.messages[0],
    assistant_message: inspirationDetail.messages[1],
    credit_cost: 1
  });
  mockedApi.saveInspirationMessageDraft.mockResolvedValue({ collection_id: 801 });
  mockedApi.archiveInspirationSession.mockResolvedValue({
    ...inspirationSession,
    status: "archived"
  });
  mockedApi.setInspirationSessionPinned.mockImplementation(async (_sessionId, isPinned) => ({
    ...inspirationSession,
    is_pinned: isPinned,
    pinned_time: isPinned ? 1782570700 : 0
  }));
  mockedApi.renameInspirationSession.mockImplementation(async (_sessionId, title) => ({
    ...inspirationSession,
    title
  }));
  mockedApi.deleteInspirationSession.mockResolvedValue({ deleted: true });
  mockedApi.getInspirationPersonalization.mockResolvedValue(inspirationPersonalization);
  mockedApi.updateInspirationPersonalization.mockImplementation(async (payload) => ({
    ...inspirationPersonalization,
    ...payload,
    id: 301,
    update_time: 1782570800
  }));
  mockedApi.listInspirationPersonalizationTemplates.mockResolvedValue([inspirationTemplate]);
  mockedApi.createInspirationPersonalizationTemplate.mockImplementation(async (payload) => ({
    ...inspirationTemplate,
    ...payload,
    id: 302,
    update_time: 1782570800
  }));
  mockedApi.updateInspirationPersonalizationTemplate.mockImplementation(async (templateId, payload) => ({
    ...inspirationTemplate,
    ...payload,
    id: templateId,
    update_time: 1782570800
  }));
  mockedApi.duplicateInspirationPersonalizationTemplate.mockResolvedValue({
    ...inspirationTemplate,
    id: 303,
    template_name: "品牌运营顾问 副本"
  });
  mockedApi.archiveInspirationPersonalizationTemplate.mockResolvedValue({
    ...inspirationTemplate,
    status: "archived"
  });
  mockedApi.getInspirationPersonalizationPreference.mockResolvedValue(inspirationPreference);
  mockedApi.updateInspirationPersonalizationPreference.mockImplementation(async (payload) => ({
    ...inspirationPreference,
    ...payload,
    update_time: 1782570800
  }));
  mockedApi.uploadMaterialAsset.mockResolvedValue(materialAsset);
  mockedApi.listMaterialProjectGroups.mockResolvedValue([materialProjectGroup]);
  mockedApi.listMaterialLibraryItems.mockResolvedValue({
    project_group_id: 1,
    current_folder: null,
    breadcrumbs: [],
    folders: [materialFolder],
    assets: [materialAsset]
  });
  mockedApi.getMaterialAssetBlob.mockResolvedValue(new Blob(["image"], { type: "image/png" }));
  mockedApi.getMaterialAssetThumbnailBlob.mockResolvedValue(
    new Blob(["thumbnail"], { type: "image/jpeg" })
  );
  mockedApi.createViralAnalysisJob.mockResolvedValue(viralJob);
  mockedApi.listViralAnalysisJobs.mockResolvedValue({ items: [viralJob], page: 1, page_size: 20, total: 1 });
  mockedApi.getViralAnalysisJob.mockResolvedValue(viralJob);
  mockedApi.getViralAnalysisMaterialBlob.mockResolvedValue(
    new Blob(["video"], { type: "video/mp4" })
  );
  mockedApi.uploadViralAnalysisMaterial.mockResolvedValue(viralMaterial);
  mockedApi.selectViralAnalysisLibraryMaterial.mockResolvedValue(viralMaterial);
  mockedApi.runViralAnalysisJob.mockResolvedValue(viralJob);
  mockedApi.cancelViralAnalysisJob.mockResolvedValue({ ...viralJob, status: "cancelled" });
  mockedApi.createContentCollection.mockResolvedValue({
    item: contentCollection,
    created: true
  });
  mockedApi.listContentCollections.mockResolvedValue({
    items: [contentCollection],
    page: 1,
    page_size: 20,
    total: 1
  });
  mockedApi.getContentCollection.mockResolvedValue(contentCollection);
  mockedApi.updateContentCollection.mockResolvedValue(contentCollection);
});

async function renderAuthenticatedApp() {
  render(<App />);
  await screen.findByRole("button", { name: "智能创作" });
}

describe("KARRIES desktop workspace", () => {
  it("opens on the smart creation workspace with the expected navigation", async () => {
    await renderAuthenticatedApp();

    expect(screen.getByText("KARRIES")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "智能创作" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "智能剪辑" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Karries AI" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("button", { name: "图文创作" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "视频创作" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发布计划" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "内容收藏" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "账号管理" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Karries AI" })).toBeInTheDocument();
  });

  it("expands and collapses product navigation groups", async () => {
    await renderAuthenticatedApp();

    const createGroup = screen.getByRole("button", { name: "智能创作" });
    expect(createGroup).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(createGroup);

    expect(createGroup).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Karries AI" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "视频创作" })).not.toBeInTheDocument();

    fireEvent.click(createGroup);
    expect(createGroup).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Karries AI" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "视频创作" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "图文创作" })).not.toBeInTheDocument();
  });

  it("collapses and restores the customer sidebar while preserving navigation", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));
    expect(screen.getByRole("button", { name: "展开侧边栏" })).toBeInTheDocument();
    expect(document.querySelector(".customer-shell")).toHaveClass("sidebar-collapsed");
    expect(window.localStorage.getItem("customer-sidebar-collapsed")).toBe("1");

    fireEvent.click(screen.getByRole("button", { name: "展开侧边栏" }));
    expect(document.querySelector(".customer-shell")).not.toHaveClass("sidebar-collapsed");
  });

  it("submits customer feedback from the primary navigation", async () => {
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "需求反馈" }));

    expect(await screen.findByRole("heading", { name: "需求反馈" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "功能需求" }));
    fireEvent.change(screen.getByLabelText("反馈标题"), {
      target: { value: "增加批量素材预览" }
    });
    fireEvent.change(screen.getByLabelText("详细说明"), {
      target: { value: "希望在产品知识库中一次预览多个视频素材，方便快速筛选。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "提交反馈" }));

    await waitFor(() => expect(mockedApi.createUserFeedback).toHaveBeenCalledWith({
      category: "feature",
      title: "增加批量素材预览",
      description: "希望在产品知识库中一次预览多个视频素材，方便快速筛选。"
    }));
    expect(await screen.findByText("反馈已提交，我们会尽快处理。")).toHaveClass(
      "app-alert",
      "success",
      "feedback-success"
    );
  });

  it("clears a stale feedback request error after refresh succeeds", async () => {
    mockedApi.listUserFeedback.mockRejectedValueOnce(new Error("请求未完成"));

    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "需求反馈" }));

    expect(await screen.findByText("请求未完成")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "刷新进度" }));

    await waitFor(() => {
      expect(screen.queryByText("请求未完成")).not.toBeInTheDocument();
    });
  });

  it("makes the selected feedback status filter explicit and requests that status", async () => {
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "需求反馈" }));

    const statusTabs = await screen.findByRole("tablist", { name: "反馈状态筛选" });
    const allTab = within(statusTabs).getByRole("tab", { name: "全部" });
    const completedTab = within(statusTabs).getByRole("tab", { name: "已完成" });

    expect(allTab).toHaveAttribute("aria-selected", "true");
    expect(completedTab).toHaveAttribute("aria-selected", "false");

    fireEvent.click(completedTab);

    expect(completedTab).toHaveAttribute("aria-selected", "true");
    expect(allTab).toHaveAttribute("aria-selected", "false");
    await waitFor(() => {
      const params = mockedApi.listUserFeedback.mock.calls.at(-1)?.[0] as URLSearchParams;
      expect(params.get("status")).toBe("completed");
    });
  });

  it("submits a user video editing work order", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "视频创作" }));
    expect(await screen.findByRole("heading", { name: "视频创作" })).toBeInTheDocument();
    expect(screen.queryByLabelText("计划发布账号")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("计划发布时间")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "从产品知识库选择" }));
    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 品牌产品" }));
    fireEvent.click(await screen.findByRole("button", { name: /look.png/ }));
    fireEvent.click(screen.getByRole("button", { name: "确认使用" }));
    fireEvent.change(screen.getByLabelText("视频脚本（可选）"), {
      target: { value: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。" }
    });
    expect(screen.queryByRole("heading", { name: "视频生成进度" })).not.toBeInTheDocument();
    expect(screen.getAllByText("160 算力").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "确定" }));
    expect(
      await screen.findByRole("alertdialog", { name: "确认视频制作需求" })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认并提交" }));

    await waitFor(() => {
      expect(mockedApi.createVideoEditJob).toHaveBeenCalledWith(
        expect.objectContaining({
          job_title: "小红书视频制作需求",
          creation_mode: "standard",
          script_text: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
          xhs_account_id: 0,
          planned_publish_time: 0,
          materials: [
            expect.objectContaining({
              material_file_id: 101,
              file_name: "look.png"
            })
          ]
        })
      );
    });
    expect(await screen.findByText("视频创作需求已提交，已进入制作流程")).toBeInTheDocument();
  });

  it("renders the immutable video creation script and requirements as readable documents", async () => {
    const deliveredTime = 1782570660;
    const deliveredTimeText = new Date(deliveredTime * 1000).toLocaleString("zh-CN");
    const historyJob = {
      ...videoEditJob,
      delivered_time: deliveredTime,
      materials: [{
        ...videoEditJob.materials[0],
        material_file_id: 101
      }],
      delivery_assets: [{
        version: 1,
        resource_type: "video" as const,
        delivery_file_name: "成片-v1.mp4",
        mime_type: "video/mp4",
        delivered_time: deliveredTime
      }],
      request_snapshot: {
        ...videoEditJob.request_snapshot,
        script_text: "## 开场\n\n- 产品特写\n- 场景切换",
        requirement_text: "节奏自然，避免硬广",
        materials: [{
          ...videoEditJob.materials[0],
          material_file_id: 101
        }]
      }
    };
    mockedApi.listVideoEditJobs.mockResolvedValue([historyJob]);
    mockedApi.getVideoEditJobHistory.mockResolvedValue({
      id: historyJob.id,
      request_snapshot: historyJob.request_snapshot,
      creation_mode: historyJob.creation_mode,
      creation_mode_label: historyJob.creation_mode_label,
      credit_cost: historyJob.credit_cost,
      status: historyJob.status,
      status_name: historyJob.status_name,
      status_text: historyJob.status_text,
      delivery_versions: [],
      delivery_assets: historyJob.delivery_assets,
      revision_count: 0,
      create_time: historyJob.create_time,
      update_time: historyJob.update_time,
      delivered_time: historyJob.delivered_time
    });

    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "视频创作" }));
    expect(await screen.findByText(`生成时间：${deliveredTimeText}`)).toBeInTheDocument();
    expect(await screen.findByText("视频生成完毕")).toHaveAttribute(
      "data-history-status",
      "completed"
    );
    expect(screen.queryByText("视频待发布")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /查看脚本与素材/ }));

    const dialog = await screen.findByRole("dialog", { name: /视频创作记录/ });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "开场" })).toBeInTheDocument();
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(2);
    expect(within(dialog).getByRole("button", { name: "复制提交脚本" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "复制制作要求" })).toBeInTheDocument();
    expect(within(dialog).getByText("生成时间")).toBeInTheDocument();
    expect(within(dialog).getByText(deliveredTimeText)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "预览素材 look.mp4" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "预览交付版本 成片-v1.mp4" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "下载交付版本 成片-v1.mp4" })).toBeInTheDocument();
  });

  it("selects video editing materials from the product library", async () => {
    const videoAsset = {
      ...materialAsset,
      id: 102,
      file_name: "product.mp4",
      file_type: "video" as const,
      mime_type: "video/mp4"
    };
    mockedApi.listMaterialLibraryItems.mockResolvedValue({
      project_group_id: 1,
      current_folder: null,
      breadcrumbs: [],
      folders: [],
      assets: [videoAsset]
    });
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "视频创作" }));
    fireEvent.click(await screen.findByRole("button", { name: "从产品知识库选择" }));
    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 品牌产品" }));
    fireEvent.click(await screen.findByRole("button", { name: /product.mp4/ }));
    await waitFor(() => {
      expect(mockedApi.getMaterialAssetThumbnailBlob).toHaveBeenCalledWith(102);
    });
    fireEvent.click(screen.getByRole("button", { name: "确认使用" }));
    fireEvent.change(screen.getByLabelText("视频脚本（可选）"), {
      target: { value: "按脚本完成产品视频剪辑。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "确定" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "确认并提交" })
    );

    await waitFor(() => {
      expect(mockedApi.createVideoEditJob).toHaveBeenCalledWith(
        expect.objectContaining({
          materials: [
            expect.objectContaining({
              material_file_id: 102,
              file_name: "product.mp4",
              file_type: "video"
            })
          ]
        })
      );
    });
  });

  it("selects every compatible asset in the current material folder tree", async () => {
    const firstVideo = {
      ...materialAsset,
      id: 201,
      file_name: "front.mp4",
      file_type: "video" as const,
      mime_type: "video/mp4"
    };
    const nestedVideo = {
      ...firstVideo,
      id: 202,
      file_name: "detail.mp4",
      folder_id: materialFolder.id
    };
    mockedApi.listMaterialLibraryItems.mockImplementation(
      async (_folderId = 0, _keyword = "", _fileType = "", recursive = false) => ({
        project_group_id: 1,
        current_folder: null,
        breadcrumbs: [],
        folders: [materialFolder],
        assets: recursive ? [firstVideo, nestedVideo] : [firstVideo]
      })
    );
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "视频创作" }));
    fireEvent.click(await screen.findByRole("button", { name: "从产品知识库选择" }));
    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 品牌产品" }));
    fireEvent.click(await screen.findByRole("button", { name: "全选当前文件夹" }));
    await screen.findByText("已选择 2 个素材");
    fireEvent.click(screen.getByRole("button", { name: "确认使用" }));

    expect(await screen.findByText("front.mp4")).toBeInTheDocument();
    expect(screen.getByText("detail.mp4")).toBeInTheDocument();
    expect(mockedApi.listMaterialLibraryItems).toHaveBeenCalledWith(0, "", "", true, 1);
  });

  it("collapses a long video material selection until the user expands it", async () => {
    const manyVideos = Array.from({ length: 6 }, (_, index) => ({
      ...materialAsset,
      id: 301 + index,
      file_name: `material-${index + 1}.mp4`,
      file_type: "video" as const,
      mime_type: "video/mp4"
    }));
    mockedApi.listMaterialLibraryItems.mockImplementation(
      async (_folderId = 0, _keyword = "", _fileType = "", recursive = false) => ({
        project_group_id: 1,
        current_folder: null,
        breadcrumbs: [],
        folders: [],
        assets: recursive ? manyVideos : [manyVideos[0]]
      })
    );
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "视频创作" }));
    fireEvent.click(await screen.findByRole("button", { name: "从产品知识库选择" }));
    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 品牌产品" }));
    fireEvent.click(await screen.findByRole("button", { name: "全选当前文件夹" }));
    await screen.findByText("已选择 6 个素材");
    fireEvent.click(screen.getByRole("button", { name: "确认使用" }));

    const toggle = await screen.findByRole("button", { name: "展开素材列表（6）" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("material-6.mp4")).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: "收起素材列表" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
    expect(await screen.findByText("material-6.mp4")).toBeInTheDocument();
    expect(window.localStorage.getItem("video-edit-materials-expanded")).toBe("1");
  });

  it("uploads local files directly into the video creation materials", async () => {
    const localFolder = {
      ...materialFolder,
      id: 88,
      folder_name: "视频创作本地上传"
    };
    const localVideo = {
      ...materialAsset,
      id: 188,
      folder_id: 88,
      file_name: "local-product.mp4",
      file_type: "video" as const,
      mime_type: "video/mp4"
    };
    mockedApi.listMaterialLibraryItems.mockResolvedValueOnce({
      project_group_id: 1,
      current_folder: null,
      breadcrumbs: [],
      folders: [],
      assets: []
    });
    mockedApi.createMaterialFolder.mockResolvedValue(localFolder);
    mockedApi.uploadMaterialAsset.mockResolvedValue(localVideo);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "视频创作" }));
    expect(await screen.findByRole("button", { name: "本地上传" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("本地上传制作素材"), {
      target: {
        files: [new File(["video"], "local-product.mp4", { type: "video/mp4" })]
      }
    });

    await waitFor(() => {
      expect(mockedApi.createMaterialFolder).toHaveBeenCalledWith(0, "视频创作本地上传", 0);
      expect(mockedApi.uploadMaterialAsset).toHaveBeenCalledWith(
        88,
        expect.objectContaining({ name: "local-product.mp4" })
      );
    });
    expect(await screen.findByText("local-product.mp4")).toBeInTheDocument();
    expect(screen.getByText(/视频 · 本地上传 ·/)).toBeInTheDocument();
  });

  it("optimizes and adopts a video script before submission", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "视频创作" }));
    fireEvent.change(screen.getByLabelText("视频脚本（可选）"), {
      target: { value: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "AI 优化脚本" }));

    expect(await screen.findByText("AI 脚本优化结果")).toBeInTheDocument();
    expect(mockedApi.optimizeVideoScript).toHaveBeenCalledWith({
      script_text: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
      requirement_text: "",
      material_file_ids: [],
      adjustment: ""
    });

    fireEvent.click(screen.getByRole("button", { name: "采用优化结果" }));
    expect(screen.getByLabelText("视频脚本（可选）")).toHaveValue(
      "0-3秒用产品特写抓住注意力，中段切换真实佩戴场景，结尾自然引导收藏咨询。"
    );
    expect(screen.getByText("已采用 AI 优化脚本")).toBeInTheDocument();
  });

  it("keeps unreleased image creation hidden from the customer workspace", async () => {
    await renderAuthenticatedApp();

    expect(screen.queryByRole("button", { name: "图文创作" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "上传到产品库" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /拖入图片/ })).not.toBeInTheDocument();
  });

  it("loads existing backend tasks into the scheduled publishing page", async () => {
    mockedApi.listContentDrafts.mockResolvedValue([contentDraft]);
    mockedApi.listMatrixPlans.mockResolvedValue([matrixPlan]);
    mockedApi.listMatrixPlanItems.mockResolvedValue([matrixPlanItem]);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "发布计划" }));

    expect((await screen.findAllByText("AI 生成的小红书笔记")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("本周新品发布计划")).toHaveLength(2);
  });

  it("switches to scheduled publishing tasks", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "发布计划" }));

    expect(await screen.findByRole("heading", { name: "发布计划", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "安排发布" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "视频内容制定" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "内容审核" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "生成发布计划" })).not.toBeInTheDocument();
    expect(screen.getByText("尚未创建发布计划")).toBeInTheDocument();
  });

  it("keeps the publishing plan workspace read-only", async () => {
    mockedApi.listContentDrafts.mockResolvedValue([contentDraft]);
    mockedApi.listXHSAccounts.mockResolvedValue([
      { ...xhsAccount, status: 1, login_state_ready: true }
    ]);
    mockedApi.listMatrixPlans.mockResolvedValue([matrixPlan]);
    mockedApi.listMatrixPlanItems.mockResolvedValue([matrixPlanItem]);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "发布计划" }));
    expect((await screen.findAllByText("本周新品发布计划")).length).toBeGreaterThan(0);
    expect(screen.queryByLabelText(/AI 生成的小红书笔记/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/禾一斯品牌主号/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "生成发布计划" })).not.toBeInTheDocument();
    expect(mockedApi.createMatrixPlanFromDrafts).not.toHaveBeenCalled();
  });

  it("creates a publishing plan from an approved content draft", async () => {
    mockedApi.listContentDrafts.mockResolvedValue([contentDraft]);
    mockedApi.listXHSAccounts.mockResolvedValue([
      { ...xhsAccount, status: 1, login_state_ready: true }
    ]);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "内容审核" }));
    fireEvent.click(await screen.findByRole("button", { name: "安排发布计划" }));
    expect(screen.getByRole("heading", { name: "安排发布计划" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("计划名称"), {
      target: { value: "新品审核发布计划" }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建发布计划" }));

    await waitFor(() => {
      expect(mockedApi.createMatrixPlanFromDrafts).toHaveBeenCalledWith(
        expect.objectContaining({
          plan_name: "新品审核发布计划",
          draft_ids: [801],
          xhs_account_ids: [27]
        })
      );
    });
    expect(await screen.findByText(/发布计划已创建/)).toBeInTheDocument();
  });

  it("shows an unclaimed video job as returned immediately after it is rejected", async () => {
    mockedApi.listVideoEditJobs.mockResolvedValue([videoEditJob]);
    mockedApi.updateVideoEditPublishContent.mockResolvedValueOnce({
      ...videoEditJob,
      review_status: "rejected",
      status: 5,
      status_name: "returned",
      status_text: "已退回",
      user_progress_text: "该视频任务已退回，请重新发起视频制作"
    });
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "内容审核" }));
    await waitFor(() => expect(screen.getByLabelText("标题")).toHaveValue(videoEditJob.post_title));
    fireEvent.click(await screen.findByRole("button", { name: "取消任务" }));

    await waitFor(() => expect(mockedApi.updateVideoEditPublishContent).toHaveBeenCalledWith(
      videoEditJob.id,
      expect.objectContaining({ review_status: "rejected" })
    ));
    expect(await screen.findByText("该视频任务已退回，请重新发起视频制作")).toBeInTheDocument();
    expect(screen.getByText("已退回", { selector: ".status-pill.danger" })).toBeInTheDocument();
  });

  it("submits delivered video feedback as a charged revision task", async () => {
    const deliveredJob = {
      ...videoEditJob,
      status: 3,
      status_name: "delivered" as const,
      status_text: "视频待发布",
      user_progress_text: "视频已交付，可预览下载",
      sla_status: "completed" as const,
      delivery: { version: 1, delivery_file_name: "first.mp4" },
      delivery_version_count: 1,
      delivery_versions: [{ version: 1, delivery_file_name: "first.mp4" }]
    };
    mockedApi.listVideoEditJobs.mockResolvedValue([deliveredJob]);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "内容审核" }));
    fireEvent.click(await screen.findByRole("button", { name: "退回修改" }));
    expect(screen.getByRole("heading", { name: "提交视频修改意见" })).toBeInTheDocument();
    expect(screen.getAllByText(/180 算力/).length).toBeGreaterThan(0);

    fireEvent.change(screen.getByRole("textbox", { name: /修改意见/ }), {
      target: { value: "请缩短前三秒，并把产品特写提前。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "确认返修并扣除 180 算力" }));

    await waitFor(() => expect(mockedApi.requestVideoEditRevision).toHaveBeenCalledWith(
      deliveredJob.id,
      expect.objectContaining({
        feedback: "请缩短前三秒，并把产品特写提前。",
        client_request_id: expect.any(String)
      })
    ));
    expect(await screen.findByText(/180 算力.*二次剪辑/)).toBeInTheDocument();
  });

  it("keeps available review data visible when one workspace request fails", async () => {
    mockedApi.listContentDrafts.mockResolvedValue([contentDraft]);
    mockedApi.listMatrixPlans.mockRejectedValueOnce(new Error("temporary plan timeout"));
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "内容审核" }));

    expect(
      await screen.findByText(
        "部分数据暂时未能加载：发布计划。其余内容已正常显示，请稍后刷新。"
      )
    ).toBeInTheDocument();
    expect((await screen.findAllByText("AI 生成的小红书笔记")).length).toBeGreaterThan(0);
  });

  it("retries failed matrix publishing items", async () => {
    mockedApi.listMatrixPlans.mockResolvedValue([
      { ...matrixPlan, status: 6 }
    ]);
    mockedApi.listMatrixPlanItems.mockResolvedValue([
      { ...matrixPlanItem, status: 5, last_error: "temporary upload error" }
    ]);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "发布计划" }));
    const retryButton = await screen.findByRole("button", { name: "重试失败任务" });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(mockedApi.retryFailedMatrixPlanItems).toHaveBeenCalledWith(901);
    });
  });

  it("opens real Xiaohongshu account management", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "账号管理" }));

    expect(screen.getByRole("heading", { name: "小红书账号管理" })).toBeInTheDocument();
    expect(await screen.findByText("禾一斯品牌主号")).toBeInTheDocument();
    expect(screen.getByText("女装穿搭")).toBeInTheDocument();
    expect(screen.queryByText("DeepSeek")).not.toBeInTheDocument();
  });

  it("creates a Xiaohongshu account profile", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "账号管理" }));
    await screen.findByText("禾一斯品牌主号");
    fireEvent.click(screen.getByRole("button", { name: "新增账号" }));
    fireEvent.change(screen.getByLabelText("账号名称"), {
      target: { value: "禾一斯门店号" }
    });
    fireEvent.change(screen.getByLabelText("账号领域"), {
      target: { value: "门店穿搭" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存账号" }));

    await waitFor(() => {
      expect(mockedApi.createXHSAccount).toHaveBeenCalledWith(
        expect.objectContaining({
          display_name: "禾一斯门店号",
          profile: expect.objectContaining({ domain_name: "门店穿搭" })
        })
      );
    });
  });

  it("edits and deletes a Xiaohongshu account", async () => {
    const updatedAccount = {
      ...xhsAccount,
      display_name: "禾一斯门店号",
      account_group: "门店号"
    };
    mockedApi.updateXHSAccount.mockResolvedValue(updatedAccount);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "账号管理" }));
    await screen.findByText("禾一斯品牌主号");
    fireEvent.click(screen.getByRole("button", { name: "编辑 禾一斯品牌主号" }));
    fireEvent.change(screen.getByLabelText("账号名称"), {
      target: { value: "禾一斯门店号" }
    });
    fireEvent.change(screen.getByLabelText("账号分组"), {
      target: { value: "门店号" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() => {
      expect(mockedApi.updateXHSAccount).toHaveBeenCalledWith(
        27,
        expect.objectContaining({
          display_name: "禾一斯门店号",
          account_group: "门店号"
        })
      );
    });

    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "删除 禾一斯门店号" }));
    await waitFor(() => {
      expect(mockedApi.deleteXHSAccount).toHaveBeenCalledWith(27);
    });
    expect(screen.queryByText("禾一斯门店号")).not.toBeInTheDocument();
  });

  it("starts a real Xiaohongshu QR login session", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "账号管理" }));
    await screen.findByText("禾一斯品牌主号");
    fireEvent.click(screen.getByRole("button", { name: "重新登录" }));

    await waitFor(() => {
      expect(mockedApi.startXHSAccountLogin).toHaveBeenCalledWith(27);
    });
    expect(await screen.findByRole("dialog", { name: "扫码登录小红书" })).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "禾一斯品牌主号 小红书登录二维码" })
    ).toBeInTheDocument();
  });

  it("checks a saved Xiaohongshu login state", async () => {
    mockedApi.listXHSAccounts.mockResolvedValue([
      { ...xhsAccount, login_state_ready: true }
    ]);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "账号管理" }));
    await screen.findByText("禾一斯品牌主号");
    fireEvent.click(screen.getByRole("button", { name: "检测状态" }));

    await waitFor(() => {
      expect(mockedApi.checkXHSAccountLogin).toHaveBeenCalledWith(27);
    });
    expect(await screen.findByText(/登录状态正常/)).toBeInTheDocument();
  });

  it("creates an inspiration session, sends a message, and saves the assistant reply as a draft", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    expect(await screen.findByRole("heading", { name: "Karries AI" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新建会话" }));
    expect(await screen.findByRole("option", {
      name: "品牌产品 / 马卡龙美甲产品资料"
    })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("会话标题"), {
      target: { value: "新品种草选题" }
    });
    expect(screen.queryByLabelText("产品 ID（可选）")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("小红书账号 ID（可选）")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("关联产品资料（可选）"), {
      target: { value: "12" }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建会话" }));

    await waitFor(() => {
      expect(mockedApi.createInspirationSession).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "新品种草选题",
          goal_type: "general",
          interaction_mode: "personalized",
          linked_product_id: 12,
          linked_xhs_account_id: 0
        })
      );
    });
    fireEvent.change(await screen.findByLabelText("输入运营问题"), {
      target: { value: "给我 5 个新品选题" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("这里是 AI 返回的运营建议")).toBeInTheDocument();
    expect(screen.queryByText("Karries AI 免费")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存到内容收藏" }));
    await waitFor(() => expect(mockedApi.saveInspirationMessageDraft).toHaveBeenCalledWith(502));
    expect(await screen.findByText("已保存到内容收藏")).toBeInTheDocument();
  });

  it("keeps product folders from healthy groups when another group fails", async () => {
    const healthyGroup = {
      ...materialProjectGroup,
      id: 2,
      group_name: "常青产品"
    };
    const healthyFolder = {
      ...materialFolder,
      id: 13,
      project_group_id: healthyGroup.id,
      folder_name: "常青资料"
    };
    mockedApi.listMaterialProjectGroups.mockResolvedValue([
      materialProjectGroup,
      healthyGroup
    ]);
    mockedApi.listMaterialLibraryItems.mockImplementation(async (
      _folderId = 0,
      _keyword = "",
      _fileType = "",
      _recursive = false,
      projectGroupId = 0
    ) => {
      if (projectGroupId === materialProjectGroup.id) {
        throw new Error("group unavailable");
      }
      return {
        project_group_id: healthyGroup.id,
        current_folder: null,
        breadcrumbs: [],
        folders: [healthyFolder],
        assets: []
      };
    });
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(await screen.findByRole("button", { name: "新建会话" }));

    expect(await screen.findByRole("option", {
      name: "常青产品 / 常青资料"
    })).toBeInTheDocument();
    expect(screen.queryByRole("option", {
      name: "品牌产品 / 马卡龙美甲产品资料"
    })).not.toBeInTheDocument();
  });

  it("sends Karries AI messages through the selected Pro model mode", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(await screen.findByRole("button", { name: "新品种草选题" }));
    const modelMode = await screen.findByRole("combobox", { name: "模型模式" });
    const modeLabels = Array.from(modelMode.querySelectorAll("option"), (option) => option.textContent);
    expect(modeLabels).toEqual(["标准模式", "Pro"]);
    expect(modeLabels.join(" ")).not.toMatch(/DeepSeek|豆包/);
    fireEvent.click(screen.getByRole("button", { name: "收起历史对话" }));
    expect(screen.getByRole("button", { name: "展开历史对话" })).toBeInTheDocument();
    fireEvent.change(modelMode, {
      target: { value: "pro" }
    });
    expect(screen.getByText("Pro 每次成功生成扣除 5 算力")).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("输入运营问题"), {
      target: { value: "用 Pro 模式生成高质量脚本" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(mockedApi.sendInspirationMessage).toHaveBeenCalledWith(
        inspirationSession.id,
        expect.objectContaining({
          content: "用 Pro 模式生成高质量脚本",
          model_mode: "pro"
        })
      );
    });
    expect(window.localStorage.getItem("inspiration:model-mode")).toBe("pro");
  });

  it("renames and deletes an inspiration session from the compact session list", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    await screen.findByRole("button", { name: "新品种草选题" });

    fireEvent.click(screen.getByRole("button", { name: "重命名第 1 个会话" }));
    fireEvent.change(screen.getByLabelText("会话名称"), {
      target: { value: "夏季门店选题" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(mockedApi.renameInspirationSession).toHaveBeenCalledWith(
        inspirationSession.id,
        "夏季门店选题"
      );
    });
    expect(await screen.findByRole("button", { name: "夏季门店选题" })).toBeInTheDocument();

    mockedApi.listInspirationSessions.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0
    });
    fireEvent.click(screen.getByRole("button", { name: "删除第 1 个会话" }));
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => {
      expect(mockedApi.deleteInspirationSession).toHaveBeenCalledWith(
        inspirationSession.id
      );
    });
    expect(await screen.findByText("暂无会话，点击“新建会话”开始。")).toBeInTheDocument();
  });

  it("creates a personalized template for future conversations", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(await screen.findByRole("button", { name: "个性化" }));
    fireEvent.change(screen.getByLabelText("模板名称"), {
      target: { value: "珠宝运营顾问" }
    });
    fireEvent.change(screen.getByLabelText("AI 名称"), {
      target: { value: "小禾" }
    });
    fireEvent.change(screen.getByLabelText("职业或身份"), {
      target: { value: "珠宝品牌运营" }
    });
    fireEvent.change(screen.getByLabelText("希望 AI 记住的详情"), {
      target: { value: "负责小红书矩阵账号，偏好真实场景种草。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建模板" }));

    await waitFor(() => {
      expect(mockedApi.createInspirationPersonalizationTemplate).toHaveBeenCalledWith(
        expect.objectContaining({
          template_name: "珠宝运营顾问",
          assistant_name: "小禾",
          occupation: "珠宝品牌运营",
          user_details: "负责小红书矩阵账号，偏好真实场景种草。"
        })
      );
    });
    expect(await screen.findByText("个性化模板已创建并设为当前对话模式。")).toBeInTheDocument();
  });

  it("filters histories by the selected conversation space and persists the selection", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    const selector = await screen.findByRole("button", { name: /对话模式：/ });
    fireEvent.click(selector);
    fireEvent.click(screen.getByRole("option", { name: /普通对话/ }));

    await waitFor(() => {
      expect(mockedApi.updateInspirationPersonalizationPreference).toHaveBeenCalledWith({
        interaction_mode: "normal",
        personalization_template_id: 0
      });
    });
    let params = mockedApi.listInspirationSessions.mock.calls.at(-1)?.[0] as URLSearchParams;
    expect(params.get("interaction_mode")).toBe("normal");
    expect(params.has("personalization_template_id")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: /对话模式：普通对话/ }));
    fireEvent.click(screen.getByRole("option", { name: new RegExp(inspirationTemplate.template_name) }));
    await waitFor(() => {
      expect(mockedApi.updateInspirationPersonalizationPreference).toHaveBeenLastCalledWith({
        interaction_mode: "personalized",
        personalization_template_id: inspirationTemplate.id
      });
    });
    params = mockedApi.listInspirationSessions.mock.calls.at(-1)?.[0] as URLSearchParams;
    expect(params.get("interaction_mode")).toBe("personalized");
    expect(params.get("personalization_template_id")).toBe(String(inspirationTemplate.id));
  });

  it("restores the last opened session inside the selected template space", async () => {
    window.localStorage.setItem(
      `inspiration:last-session:template:${inspirationTemplate.id}`,
      String(inspirationSession.id)
    );

    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));

    expect(await screen.findByRole("heading", { name: inspirationSession.title })).toBeInTheDocument();
    expect(mockedApi.getInspirationSession).toHaveBeenCalledWith(inspirationSession.id);
  });

  it("pages user inspiration sessions with a real total", async () => {
    mockedApi.listInspirationSessions
      .mockResolvedValueOnce({ items: [inspirationSession], page: 1, page_size: 20, total: 21 })
      .mockResolvedValueOnce({ items: [secondInspirationSession], page: 2, page_size: 20, total: 21 });
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    expect(await screen.findByText("第 1 页 / 共 21 条")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));

    expect(await screen.findByText("第 2 页 / 共 21 条")).toBeInTheDocument();
    const params = mockedApi.listInspirationSessions.mock.calls.at(-1)?.[0] as URLSearchParams;
    expect(params.get("page")).toBe("2");
  });

  it("keeps the newest session list when an older list request resolves late", async () => {
    const first = deferred<{ items: typeof inspirationSession[]; page: number; page_size: number; total: number }>();
    const second = deferred<{ items: typeof inspirationSession[]; page: number; page_size: number; total: number }>();
    mockedApi.listInspirationSessions
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(screen.getByRole("button", { name: "刷新" }));
    second.resolve({ items: [secondInspirationSession], page: 1, page_size: 20, total: 1 });

    expect(await screen.findByRole("button", { name: /门店活动内容策略/ })).toBeInTheDocument();
    first.resolve({ items: [inspirationSession], page: 1, page_size: 20, total: 1 });
    await Promise.resolve();
    expect(screen.queryByRole("button", { name: /新品种草选题/ })).not.toBeInTheDocument();
  });

  it("keeps the newest session detail when older detail requests resolve late", async () => {
    const first = deferred<typeof inspirationDetail>();
    const second = deferred<typeof inspirationDetail>();
    mockedApi.listInspirationSessions.mockResolvedValue({
      items: [inspirationSession, secondInspirationSession], page: 1, page_size: 20, total: 2
    });
    mockedApi.getInspirationSession.mockImplementation((sessionId: number) => sessionId === 41 ? first.promise : second.promise);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    await screen.findByRole("button", { name: /新品种草选题/ });
    fireEvent.click(screen.getByRole("button", { name: /新品种草选题/ }));
    fireEvent.click(screen.getByRole("button", { name: /门店活动内容策略/ }));
    second.resolve({ ...inspirationDetail, session: secondInspirationSession, messages: [{ ...inspirationDetail.messages[1], content: "第二个会话的建议" }] });

    expect(await screen.findByText("第二个会话的建议")).toBeInTheDocument();
    first.resolve(inspirationDetail);
    await Promise.resolve();
    expect(screen.queryByText("这里是 AI 返回的运营建议")).not.toBeInTheDocument();
  });

  it("disables archiving the active session while its reply is generating", async () => {
    const reply = deferred<{ user_message: typeof inspirationDetail.messages[number]; assistant_message: typeof inspirationDetail.messages[number]; credit_cost: number }>();
    mockedApi.getInspirationSession.mockResolvedValue(inspirationDetail);
    mockedApi.sendInspirationMessage.mockReturnValue(reply.promise);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(await screen.findByRole("button", { name: /新品种草选题/ }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.change(screen.getByLabelText("输入运营问题"), { target: { value: "继续补充 3 个角度" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    fireEvent.click(screen.getByRole("button", { name: "查看创作上下文" }));
    expect(screen.getByRole("button", { name: "归档会话" })).toBeDisabled();
    expect(screen.getByText("生成中")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "关闭创作上下文" }));
    expect(screen.queryByRole("dialog", { name: "创作上下文" })).not.toBeInTheDocument();
    reply.resolve({ user_message: inspirationDetail.messages[0], assistant_message: inspirationDetail.messages[1], credit_cost: 0 });
  });

  it("reuses the inspiration request id when the same message is retried", async () => {
    mockedApi.getInspirationSession.mockResolvedValue(inspirationDetail);
    mockedApi.sendInspirationMessage
      .mockRejectedValueOnce(new Error("网络连接中断"))
      .mockResolvedValueOnce({
        user_message: inspirationDetail.messages[0],
        assistant_message: inspirationDetail.messages[1],
        credit_cost: 0
      });
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(await screen.findByRole("button", { name: /新品种草选题/ }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.change(screen.getByLabelText("输入运营问题"), {
      target: { value: "继续补充 3 个角度" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("网络连接中断")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(mockedApi.sendInspirationMessage).toHaveBeenCalledTimes(2));
    const firstRequest = mockedApi.sendInspirationMessage.mock.calls[0][1];
    const retriedRequest = mockedApi.sendInspirationMessage.mock.calls[1][1];
    expect(firstRequest.client_request_id).toBeTruthy();
    expect(retriedRequest.client_request_id).toBe(firstRequest.client_request_id);
  });

  it("does not switch back when an older session send resolves after selecting another session", async () => {
    const reply = deferred<{ user_message: typeof inspirationDetail.messages[number]; assistant_message: typeof inspirationDetail.messages[number]; credit_cost: number }>();
    const secondDetail = { ...inspirationDetail, session: secondInspirationSession, messages: [] };
    mockedApi.listInspirationSessions.mockResolvedValue({
      items: [inspirationSession, secondInspirationSession], page: 1, page_size: 20, total: 2
    });
    mockedApi.getInspirationSession.mockImplementation((sessionId: number) => Promise.resolve(sessionId === 42 ? secondDetail : inspirationDetail));
    mockedApi.sendInspirationMessage.mockReturnValue(reply.promise);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(await screen.findByRole("button", { name: /新品种草选题/ }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.change(screen.getByLabelText("输入运营问题"), { target: { value: "继续补充 3 个角度" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    fireEvent.click(screen.getByRole("button", { name: /门店活动内容策略/ }));
    await screen.findByRole("heading", { name: "门店活动内容策略" });

    reply.resolve({ user_message: inspirationDetail.messages[0], assistant_message: inspirationDetail.messages[1], credit_cost: 0 });
    await Promise.resolve();
    expect(screen.getByRole("heading", { name: "门店活动内容策略" })).toBeInTheDocument();
    expect(screen.queryByText("这里是 AI 返回的运营建议")).not.toBeInTheDocument();
  });

  it("recovers from a failed draft save and updates the real draft id after retry", async () => {
    mockedApi.getInspirationSession.mockResolvedValue(inspirationDetail);
    mockedApi.saveInspirationMessageDraft
      .mockRejectedValueOnce(new Error("草稿保存失败"))
      .mockResolvedValueOnce({ collection_id: 801 });
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "Karries AI" }));
    fireEvent.click(await screen.findByRole("button", { name: /新品种草选题/ }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.click(screen.getByRole("button", { name: "保存到内容收藏" }));
    expect(await screen.findByText("草稿保存失败")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存到内容收藏" }));

    expect(await screen.findByText("收藏稿 ID：801")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "已保存到内容收藏" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "已保存到内容收藏" }));
    expect(mockedApi.saveInspirationMessageDraft).toHaveBeenCalledTimes(2);
  });

  it("hides management and developer navigation from a customer", async () => {
    mockedApi.getCurrentUser.mockResolvedValue({ id: 9, tenant_id: 1, login_name: "customer", nickname: "员工", user_role: "customer", wallet_balance: 0 });
    render(<App />);
    await screen.findByRole("button", { name: "智能创作" });
    expect(screen.queryByRole("button", { name: /管理端/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开发者端/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "AI 任务排查" })).not.toBeInTheDocument();
  });

  it("keeps every portal and business request behind the auth loading gate", async () => {
    const login = deferred<{ id: number; tenant_id: number; login_name: string; nickname: string; user_role: "developer_admin"; wallet_balance: number }>();
    mockedApi.getCurrentUser.mockReturnValue(login.promise);
    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent("正在验证登录信息");
    expect(screen.queryByRole("button", { name: /用户端/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开发者端/ })).not.toBeInTheDocument();
    expect(mockedApi.listAccounts).not.toHaveBeenCalled();
    expect(mockedApi.listTasks).not.toHaveBeenCalled();

    await act(async () => {
      login.resolve({ id: 1, tenant_id: 0, login_name: "developer", nickname: "开发者", user_role: "developer_admin", wallet_balance: 0 });
      await login.promise;
    });

    expect(await screen.findByRole("heading", { name: "账号登录" })).toBeInTheDocument();
    expect(screen.getByText("当前账号没有用户端访问权限")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /用户端/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "素材智能解析" })).not.toBeInTheDocument();
    expect(mockedApi.listAccounts).not.toHaveBeenCalled();
    expect(mockedApi.listTasks).not.toHaveBeenCalled();
  });

  it("shows the login page for a missing token and enters the workspace after login", async () => {
    mockedApi.getCurrentUser.mockRejectedValue(
      new ApiRequestError("missing bearer token", "UNAUTHORIZED", 401)
    );
    render(<App />);

    expect(await screen.findByRole("heading", { name: "账号登录" })).toBeInTheDocument();
    expect(screen.queryByText("missing bearer token")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("登录账号"), {
      target: { value: "karries_local_test" }
    });
    fireEvent.change(screen.getByLabelText("登录密码"), {
      target: { value: "correct-password" }
    });
    fireEvent.click(screen.getByRole("button", { name: "进入工作空间" }));

    await waitFor(() => {
      expect(mockedApi.login).toHaveBeenCalledWith({
        login_name: "karries_local_test",
        password: "correct-password"
      });
    });
    expect(await screen.findByRole("button", { name: "智能创作" })).toBeInTheDocument();
    expect(window.localStorage.getItem("karries_customer_access_token")).toBe("local-access-token");
  });

  it("supports password visibility and explains how workspace access is granted", async () => {
    mockedApi.getCurrentUser.mockRejectedValue(
      new ApiRequestError("missing bearer token", "UNAUTHORIZED", 401)
    );
    render(<App />);

    const passwordInput = await screen.findByLabelText("登录密码");
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(screen.getByText("安全访问 · 账号由管理员统一开通")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "显示密码" }));
    expect(passwordInput).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "隐藏密码" }));
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("shows a readable message when login credentials are invalid", async () => {
    mockedApi.getCurrentUser.mockRejectedValue(
      new ApiRequestError("missing bearer token", "UNAUTHORIZED", 401)
    );
    mockedApi.login.mockRejectedValue(
      new ApiRequestError("invalid login credentials", "INVALID_CREDENTIALS", 401)
    );
    render(<App />);

    fireEvent.change(await screen.findByLabelText("登录账号"), {
      target: { value: "wrong-user" }
    });
    fireEvent.change(screen.getByLabelText("登录密码"), {
      target: { value: "wrong-password" }
    });
    fireEvent.click(screen.getByRole("button", { name: "进入工作空间" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("账号或密码错误，请重新输入");
    expect(screen.queryByText("invalid login credentials")).not.toBeInTheDocument();
    expect(window.localStorage.getItem("karries_customer_access_token")).toBeNull();
  });

  it("creates, uploads, and runs a viral analysis task in order", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "爆款解析" }));
    expect(screen.getByText("预计 100 算力")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("布景分析"));
    expect(screen.getByText("预计 120 算力")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("光影分析"));
    expect(screen.getByText("预计 120 算力")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("任务名称"), { target: { value: "防晒爆款视频拆解" } });
    fireEvent.change(screen.getByLabelText("素材来源"), { target: { value: "upload" } });
    const file = new File(["video"], "reference.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText("上传参考素材"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("补充口播稿或观察笔记"), { target: { value: viralJob.supplement_text } });
    fireEvent.click(screen.getByRole("button", { name: "创建并开始解析" }));
    await waitFor(() => expect(mockedApi.createViralAnalysisJob).toHaveBeenCalled());
    expect(mockedApi.createViralAnalysisJob).toHaveBeenCalledWith(expect.objectContaining({
      analysis_goal: expect.arrayContaining(["setting", "lighting"])
    }));
    expect(mockedApi.uploadViralAnalysisMaterial).toHaveBeenCalledWith(71, file);
    expect(mockedApi.runViralAnalysisJob).toHaveBeenCalledWith(71);
    expect(mockedApi.createViralAnalysisJob.mock.invocationCallOrder[0]).toBeLessThan(mockedApi.uploadViralAnalysisMaterial.mock.invocationCallOrder[0]);
    expect(mockedApi.uploadViralAnalysisMaterial.mock.invocationCallOrder[0]).toBeLessThan(mockedApi.runViralAnalysisJob.mock.invocationCallOrder[0]);
    expect(await screen.findByText("前三秒抛出护肤痛点")).toBeInTheDocument();
    expect(screen.getByText("解析任务已完成，可查看结构化结果。")).toHaveClass("success");
  });

  it("selects a product-library asset before running viral analysis", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "爆款解析" }));
    fireEvent.change(screen.getByLabelText("任务名称"), {
      target: { value: "知识库视频拆解" }
    });
    fireEvent.change(screen.getByLabelText("素材来源"), {
      target: { value: "library" }
    });
    fireEvent.click(screen.getByRole("button", { name: "从产品知识库选择" }));
    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 品牌产品" }));
    fireEvent.click(await screen.findByRole("button", { name: /look\.png/ }));
    fireEvent.click(screen.getByRole("button", { name: "确认使用" }));
    fireEvent.click(screen.getByRole("button", { name: "创建并开始解析" }));

    await waitFor(() => {
      expect(mockedApi.createViralAnalysisJob).toHaveBeenCalledWith(
        expect.objectContaining({ source_type: "upload" })
      );
    });
    expect(mockedApi.selectViralAnalysisLibraryMaterial).toHaveBeenCalledWith(71, 101);
    expect(mockedApi.uploadViralAnalysisMaterial).not.toHaveBeenCalled();
    expect(mockedApi.createViralAnalysisJob.mock.invocationCallOrder[0]).toBeLessThan(
      mockedApi.selectViralAnalysisLibraryMaterial.mock.invocationCallOrder[0]
    );
    expect(mockedApi.selectViralAnalysisLibraryMaterial.mock.invocationCallOrder[0]).toBeLessThan(
      mockedApi.runViralAnalysisJob.mock.invocationCallOrder[0]
    );
  });

  it("retains the created task and retries an upload that is rejected with 413", async () => {
    const pending = {
      ...viralJob,
      source_type: "upload" as const,
      status: "pending" as const,
      materials: [],
      result: null
    };
    mockedApi.createViralAnalysisJob.mockResolvedValue(pending);
    mockedApi.uploadViralAnalysisMaterial
      .mockRejectedValueOnce(new ApiRequestError("too large", "PAYLOAD_TOO_LARGE", 413))
      .mockResolvedValueOnce(viralMaterial);
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.change(screen.getByLabelText("任务名称"), { target: { value: "上传失败后重试" } });
    fireEvent.change(screen.getByLabelText("素材来源"), { target: { value: "upload" } });
    const file = new File(["video"], "retry.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText("上传参考素材"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("补充口播稿或观察笔记"), { target: { value: viralJob.supplement_text } });
    fireEvent.click(screen.getByRole("button", { name: "创建并开始解析" }));

    expect(await screen.findByText(/超过 200 MB/)).toBeInTheDocument();
    expect(mockedApi.runViralAnalysisJob).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "重新上传并继续解析" }));

    await waitFor(() => expect(mockedApi.uploadViralAnalysisMaterial).toHaveBeenCalledTimes(2));
    expect(mockedApi.uploadViralAnalysisMaterial).toHaveBeenLastCalledWith(71, file);
    expect(mockedApi.runViralAnalysisJob).toHaveBeenCalledWith(71);
  });

  it("does not upload the same material again after upload succeeds but analysis fails", async () => {
    const pending = {
      ...viralJob,
      source_type: "upload" as const,
      status: "pending" as const,
      materials: [],
      result: null
    };
    mockedApi.createViralAnalysisJob.mockResolvedValue(pending);
    mockedApi.uploadViralAnalysisMaterial
      .mockRejectedValueOnce(new ApiRequestError("upload interrupted", "UPLOAD_FAILED", 400))
      .mockResolvedValueOnce(viralMaterial);
    mockedApi.runViralAnalysisJob.mockRejectedValueOnce(new Error("provider failed"));
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.change(screen.getByLabelText("任务名称"), { target: { value: "上传成功后解析失败" } });
    fireEvent.change(screen.getByLabelText("素材来源"), { target: { value: "upload" } });
    const file = new File(["video"], "retry-once.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText("上传参考素材"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("补充口播稿或观察笔记"), {
      target: { value: viralJob.supplement_text }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建并开始解析" }));
    await screen.findByRole("button", { name: "重新上传并继续解析" });
    fireEvent.click(screen.getByRole("button", { name: "重新上传并继续解析" }));

    await waitFor(() => expect(mockedApi.runViralAnalysisJob).toHaveBeenCalledWith(71));
    expect(mockedApi.uploadViralAnalysisMaterial).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: "重新上传并继续解析" })).not.toBeInTheDocument();
  });

  it("recovers an unfinished upload from backend state after the page is reopened", async () => {
    const pendingUpload = {
      ...viralJob,
      source_type: "upload" as const,
      status: "pending" as const,
      materials: [],
      result: null
    };
    mockedApi.listViralAnalysisJobs.mockResolvedValue({
      items: [pendingUpload],
      page: 1,
      page_size: 20,
      total: 1
    });
    mockedApi.getViralAnalysisJob.mockResolvedValue(pendingUpload);

    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));

    expect(await screen.findByText(/还没有可解析的素材/)).toBeInTheDocument();
    expect(screen.getByLabelText("重新选择解析素材")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新上传并继续解析" })).toBeDisabled();
  });

  it("collapses viral analysis history by default and remembers expansion", async () => {
    window.localStorage.removeItem("viral-analysis-history-expanded");
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));

    const toggle = await screen.findByRole("button", { name: "展开历史解析任务" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: /防晒爆款视频拆解/ })).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(await screen.findByRole("button", { name: /防晒爆款视频拆解/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "收起历史解析任务" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
    expect(window.localStorage.getItem("viral-analysis-history-expanded")).toBe("1");
  });

  it("shows the real reference material for a selected viral analysis job", async () => {
    const uploadJob = {
      ...viralJob,
      source_type: "upload" as const,
      material_file_id: viralMaterial.id,
      materials: [viralMaterial]
    };
    mockedApi.listViralAnalysisJobs.mockResolvedValue({
      items: [uploadJob],
      page: 1,
      page_size: 20,
      total: 1
    });
    mockedApi.getViralAnalysisJob.mockResolvedValue(uploadJob);

    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));

    expect(await screen.findByRole("heading", { name: "本次参考素材" })).toBeInTheDocument();
    expect(screen.getByText("reference.mp4")).toBeInTheDocument();
    expect(screen.getByText("视频 · 5 B")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "预览参考素材 reference.mp4" })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "预览参考素材 reference.mp4" }));
    await waitFor(() => {
      expect(mockedApi.getViralAnalysisMaterialBlob).toHaveBeenCalledWith(71, 1);
    });
    expect(
      await screen.findByRole("dialog", { name: "预览参考素材 reference.mp4" })
    ).toBeInTheDocument();
  });

  it("opens the actual Xiaohongshu video page from a stored share message", async () => {
    const videoUrl = "https://www.xiaohongshu.com/discovery/item/68a5f34f000000001d02abcd?xsec_token=test";
    const linkJob = {
      ...viralJob,
      source_type: "link" as const,
      source_url: `47 【爆款视频】复制口令 😍 ${videoUrl} ，打开小红书查看`
    };
    mockedApi.listViralAnalysisJobs.mockResolvedValue({
      items: [linkJob],
      page: 1,
      page_size: 20,
      total: 1
    });
    mockedApi.getViralAnalysisJob.mockResolvedValue(linkJob);

    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));

    const link = await screen.findByRole("link", { name: /打开原视频/ });
    expect(link).toHaveAttribute("href", videoUrl);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("does not invent a reference file for an old viral analysis job", async () => {
    const legacyUploadJob = {
      ...viralJob,
      source_type: "upload" as const,
      material_file_id: 0,
      materials: []
    };
    mockedApi.listViralAnalysisJobs.mockResolvedValue({
      items: [legacyUploadJob],
      page: 1,
      page_size: 20,
      total: 1
    });
    mockedApi.getViralAnalysisJob.mockResolvedValue(legacyUploadJob);

    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));

    expect(await screen.findByRole("heading", { name: "本次参考素材" })).toBeInTheDocument();
    expect(screen.getByText("历史参考素材文件暂时无法定位")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /预览参考素材/ })).not.toBeInTheDocument();
  });

  it("only allows pending viral jobs to be cancelled", async () => {
    const pending = { ...viralJob, status: "pending" as const, result: null };
    mockedApi.listViralAnalysisJobs.mockResolvedValue({ items: [pending], page: 1, page_size: 20, total: 1 });
    mockedApi.getViralAnalysisJob.mockResolvedValue(pending);
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));
    const cancelButton = await screen.findByRole("button", { name: "取消任务" });
    expect(cancelButton).toBeEnabled();
    fireEvent.click(cancelButton);
    await waitFor(() => expect(mockedApi.cancelViralAnalysisJob).toHaveBeenCalledWith(71));
    expect(screen.getByRole("button", { name: "取消任务" })).toBeDisabled();
  });

  it("replaces viral task actions with a progress footer while analysis is running", async () => {
    const pending = { ...viralJob, status: "pending" as const, result: null };
    const runningRequest = deferred<typeof pending>();
    mockedApi.listViralAnalysisJobs.mockResolvedValue({ items: [pending], page: 1, page_size: 20, total: 1 });
    mockedApi.getViralAnalysisJob.mockResolvedValue(pending);
    mockedApi.runViralAnalysisJob.mockReturnValue(runningRequest.promise);
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));

    fireEvent.click(await screen.findByRole("button", { name: "开始解析" }));

    const resultPanel = screen.getByRole("heading", { name: "解析结果" }).closest("section");
    expect(await screen.findByRole("status", { name: "解析进度" })).toHaveTextContent("正在解析内容");
    expect(resultPanel).toHaveTextContent("解析中");
    expect(screen.queryByRole("button", { name: "开始解析" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "取消任务" })).not.toBeInTheDocument();
  });

  it("does not let a stale viral detail response replace the selected task", async () => {
    const first = { ...viralJob, id: 72, title: "旧请求任务", result: { ...viralResult, hook_summary: "旧详情结果" } };
    const second = { ...viralJob, id: 73, title: "当前任务", result: { ...viralResult, hook_summary: "当前详情结果" } };
    const firstDetail = deferred<typeof first>();
    mockedApi.listViralAnalysisJobs.mockResolvedValue({ items: [first, second], page: 1, page_size: 20, total: 2 });
    mockedApi.getViralAnalysisJob.mockImplementation((jobId: number) => jobId === first.id ? firstDetail.promise : Promise.resolve(second));
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /旧请求任务/ }));
    fireEvent.click(screen.getByRole("button", { name: /当前任务/ }));
    expect(await screen.findByText("当前详情结果")).toBeInTheDocument();

    await act(async () => {
      firstDetail.resolve(first);
      await firstDetail.promise;
    });
    expect(screen.getByText("当前详情结果")).toBeInTheDocument();
    expect(screen.queryByText("旧详情结果")).not.toBeInTheDocument();
  });

  it("clears previous viral actions while the newly selected detail is loading", async () => {
    const completed = { ...viralJob, id: 72, title: "已完成任务" };
    const pending = { ...viralJob, id: 73, title: "等待加载任务", status: "pending" as const, result: null };
    const pendingDetail = deferred<typeof pending>();
    mockedApi.listViralAnalysisJobs.mockResolvedValue({ items: [completed, pending], page: 1, page_size: 20, total: 2 });
    mockedApi.getViralAnalysisJob.mockImplementation((jobId: number) => jobId === completed.id ? Promise.resolve(completed) : pendingDetail.promise);
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /已完成任务/ }));
    expect(await screen.findByRole("button", { name: "保存视频草稿" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /等待加载任务/ }));
    expect(await screen.findByText("正在加载任务详情")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存视频草稿" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "取消任务" })).not.toBeInTheDocument();

    await act(async () => {
      pendingDetail.resolve(pending);
      await pendingDetail.promise;
    });
    expect(await screen.findByRole("button", { name: "取消任务" })).toBeEnabled();
  });

  it("refreshes the selected viral detail after a run failure", async () => {
    const pending = { ...viralJob, status: "pending" as const, result: null };
    const failed = { ...pending, status: "failed" as const };
    mockedApi.listViralAnalysisJobs
      .mockResolvedValueOnce({ items: [pending], page: 1, page_size: 20, total: 1 })
      .mockResolvedValueOnce({ items: [failed], page: 1, page_size: 20, total: 1 });
    mockedApi.getViralAnalysisJob.mockResolvedValue(pending);
    mockedApi.runViralAnalysisJob.mockRejectedValueOnce(new Error("provider failed"));
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));
    fireEvent.click(await screen.findByRole("button", { name: "开始解析" }));

    expect(await screen.findByRole("button", { name: "重试解析" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消任务" })).toBeDisabled();
  });

  it("blocks an upload analysis run without a selected material", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "爆款解析" }));
    fireEvent.change(screen.getByLabelText("任务名称"), { target: { value: "空文本任务" } });
    fireEvent.click(screen.getByRole("button", { name: "创建并开始解析" }));
    expect(await screen.findByText(/上传素材类型需要选择一个本地文件/)).toBeInTheDocument();
    expect(mockedApi.createViralAnalysisJob).not.toHaveBeenCalled();
  });

  it("retries a failed viral task and tells the user where its video draft is saved", async () => {
    const failed = { ...viralJob, status: "failed" as const, result: null };
    mockedApi.getViralAnalysisJob.mockResolvedValue(failed);
    mockedApi.listViralAnalysisJobs.mockResolvedValue({ items: [failed], page: 1, page_size: 20, total: 1 });
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));
    await screen.findByRole("button", { name: "重试解析" });
    fireEvent.click(screen.getByRole("button", { name: "重试解析" }));
    await waitFor(() => expect(mockedApi.runViralAnalysisJob).toHaveBeenCalledWith(71));
    mockedApi.getViralAnalysisJob.mockResolvedValue(viralJob);
    fireEvent.click(screen.getByRole("button", { name: /防晒爆款视频拆解/ }));
    await screen.findByRole("button", { name: "保存视频草稿" });
    fireEvent.click(screen.getByRole("button", { name: "保存视频草稿" }));
    await waitFor(() => expect(mockedApi.createContentCollection).toHaveBeenCalledWith({
      source_type: "viral_analysis",
      source_id: 71
    }));
    expect(await screen.findByText("已保存至“发布管理 → 内容收藏”（收藏稿 #901）。"))
      .toHaveClass("success");
  });

  it("opens the content collection workspace from publishing navigation", async () => {
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "内容收藏" }));

    expect(await screen.findByRole("heading", { name: "内容收藏" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /防晒爆款视频拆解/ })).toBeInTheDocument();
  });

  it("labels viral analysis video drafts as video scripts in content review", async () => {
    mockedApi.listContentDrafts.mockResolvedValue([
      {
        ...contentDraft,
        id: 902,
        source_type: "viral_analysis",
        content_type: "video" as const,
        title: "防晒爆款视频拆解",
        body: "通勤前别再厚涂，轻薄防晒这样用。"
      }
    ]);
    await renderAuthenticatedApp();

    fireEvent.click(screen.getByRole("button", { name: "内容审核" }));

    expect(await screen.findByRole("button", { name: /视频脚本/ })).toBeInTheDocument();
    expect(screen.getByText("视频脚本草稿")).toBeInTheDocument();
    expect(screen.getByText("来自爆款解析 · 草稿 #902")).toBeInTheDocument();
  });

  it("prefills a new Karries AI session from a viral result without sending it", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));
    await screen.findByRole("button", { name: "转入 Karries AI" });
    fireEvent.click(screen.getByRole("button", { name: "转入 Karries AI" }));
    expect(await screen.findByRole("heading", { name: "Karries AI" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("关联产品资料（可选）"), {
      target: { value: "12" }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建会话" }));
    await waitFor(() => expect(mockedApi.createInspirationSession).toHaveBeenCalledWith(expect.objectContaining({
      goal_type: "script",
      linked_product_id: 12,
      extra_requirement: "基于爆款结构融合关联产品，保留方法但不照搬表达，生成原创视频脚本。"
    })));
    expect(mockedApi.sendInspirationMessage).not.toHaveBeenCalled();
    expect((screen.getByLabelText("输入消息") as HTMLTextAreaElement).value)
      .toContain(viralResult.rewritten_script);
  });

  it("keeps the viral handoff dialog open when the remembered session list resolves late", async () => {
    const delayedSessionList = deferred<{
      items: typeof inspirationSession[];
      page: number;
      page_size: number;
      total: number;
    }>();
    window.localStorage.setItem(
      `inspiration:last-session:template:${inspirationTemplate.id}`,
      String(inspirationSession.id)
    );
    mockedApi.listInspirationSessions
      .mockResolvedValueOnce({
        items: [inspirationSession],
        page: 1,
        page_size: 20,
        total: 1
      })
      .mockReturnValueOnce(delayedSessionList.promise);

    render(<App />);
    await screen.findByRole("button", { name: /新品种草选题/ });
    fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
    fireEvent.click(await screen.findByRole("button", { name: /防晒爆款视频拆解/ }));
    fireEvent.click(await screen.findByRole("button", { name: "转入 Karries AI" }));

    expect(await screen.findByRole("dialog", { name: "新建会话" })).toBeInTheDocument();
    expect((screen.getByLabelText("会话标题") as HTMLInputElement).value)
      .toBe("爆款脚本融合：防晒爆款视频拆解");
    mockedApi.getInspirationSession.mockClear();

    await act(async () => {
      delayedSessionList.resolve({
        items: [inspirationSession],
        page: 1,
        page_size: 20,
        total: 1
      });
      await delayedSessionList.promise;
    });

    expect(screen.getByRole("dialog", { name: "新建会话" })).toBeInTheDocument();
    expect((screen.getByLabelText("会话标题") as HTMLInputElement).value)
      .toBe("爆款脚本融合：防晒爆款视频拆解");
    expect(mockedApi.getInspirationSession).not.toHaveBeenCalled();
  });

  it("sends upload data as FormData without a manually assigned content type", async () => {
    const realClient = await vi.importActual<typeof import("../api/client")>("../api/client");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ success: true, data: { id: 1 }, error: null }), { status: 200, headers: { "Content-Type": "application/json" } }));
    window.localStorage.setItem("karries_customer_access_token", "test-token");
    await realClient.api.uploadViralAnalysisMaterial(71, new File(["video"], "reference.mp4", { type: "video/mp4" }));
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.body).toBeInstanceOf(FormData);
    expect(new Headers(init?.headers).has("Content-Type")).toBe(false);
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer test-token");
    fetchMock.mockRestore();
    window.localStorage.removeItem("karries_customer_access_token");
  });

  it("shows the current Pro membership and submits a manual recharge request", async () => {
    await renderAuthenticatedApp();
    expect(screen.queryByRole("button", { name: "账户中心" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "账号菜单" }));
    fireEvent.click(screen.getByRole("button", { name: "充值中心" }));

    expect(await screen.findByRole("heading", { name: "充值中心" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "免费版" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro会员版" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Max会员版" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "存储大会员版" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "当前订阅" })).toBeDisabled();
    expect(screen.getByText("实时算力账户")).toBeInTheDocument();
    expect(screen.getAllByText("平台全部核心功能").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("包含 Pro 会员全部功能").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("button", { name: "立即同步算力" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "算力充值" }));
    fireEvent.click(screen.getByRole("button", { name: "自定义充值" }));
    fireEvent.click(await screen.findByRole("button", { name: /提交 ¥1,000 充值需求/ }));

    await waitFor(() => expect(mockedApi.createRechargeOrder).toHaveBeenCalledWith({
      recharge_type: "online",
      amount_cent: 100000,
      payment_channel: "manual"
    }));
    expect(await screen.findByText(/充值需求 .* 已提交/)).toBeInTheDocument();
  });

  it("opens the personal center from the navigation and shows account balances", async () => {
    await renderAuthenticatedApp();
    fireEvent.click(screen.getByRole("button", { name: "账号菜单" }));
    fireEvent.click(screen.getByRole("button", { name: "个人中心" }));

    expect(await screen.findByRole("heading", { name: "个人中心" })).toBeInTheDocument();
    expect(screen.getByText("@operator · 员工编号 9")).toBeInTheDocument();
    expect(screen.getByText("禾一斯运营团队")).toBeInTheDocument();
    expect(screen.getAllByText("Pro会员版").length).toBeGreaterThan(0);
    expect(screen.getAllByText("30").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /每日签到/ })).toBeInTheDocument();
  });

  it("shows task notifications from the manager in the customer bell", async () => {
    mockedApi.listNotifications.mockResolvedValue({
      items: [{
        id: 41,
        notification_type: "task",
        title: "完成新品发布排期",
        content: "请在今天下班前确认本周内容。",
        priority: 2,
        action_path: "schedule",
        business_type: "",
        business_id: 0,
        deadline_time: 1785261600,
        read_time: 0,
        is_read: false,
        create_time: 1785216000,
        update_time: 1785216000
      }],
      page: 1,
      page_size: 20,
      total: 1
    });
    mockedApi.getUnreadNotificationCount.mockResolvedValue({ count: 1 });

    await renderAuthenticatedApp();
    fireEvent.click(await screen.findByRole("button", { name: "通知" }));

    expect(await screen.findByText("完成新品发布排期")).toBeInTheDocument();
    expect(screen.getByText("1 条未读")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /完成新品发布排期/ }));
    await waitFor(() => expect(mockedApi.markNotificationRead).toHaveBeenCalledWith(41));
  });

  it("does not expose the developer portal in the customer application", async () => {
    mockedApi.getCurrentUser.mockResolvedValue({ id: 1, tenant_id: 0, login_name: "dev", nickname: "开发", user_role: "developer_admin", wallet_balance: 0 });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "账号登录" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开发者端/ })).not.toBeInTheDocument();
    expect(screen.queryByText("/api/developer/viral-analysis/jobs")).not.toBeInTheDocument();
  });
});
