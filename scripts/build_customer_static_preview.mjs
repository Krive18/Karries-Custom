import { readFile, readdir, writeFile } from "node:fs/promises";
import { basename, extname, join, resolve } from "node:path";

const rootDir = resolve(import.meta.dirname, "..");
const distDir = join(rootDir, "apps", "desktop", "dist", "customer-renderer");
const assetsDir = join(distDir, "assets");
const outputPath = join(
  rootDir,
  "交付文件",
  "KARRIES禾一斯智能运营平台-用户端预览.html"
);

const assetFiles = await readdir(assetsDir);
const javascriptFile = assetFiles.find((name) => /^index-.*\.js$/.test(name));
const stylesheetFile = assetFiles.find((name) => /^index-.*\.css$/.test(name));

if (!javascriptFile || !stylesheetFile) {
  throw new Error("请先运行 npm run build:customer 生成用户端构建产物。");
}

let javascript = await readFile(join(assetsDir, javascriptFile), "utf8");
const stylesheet = await readFile(join(assetsDir, stylesheetFile), "utf8");

const mimeTypes = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp"
};

for (const assetFile of assetFiles) {
  const mimeType = mimeTypes[extname(assetFile).toLowerCase()];
  if (!mimeType) continue;
  const bytes = await readFile(join(assetsDir, assetFile));
  const dataUrl = `data:${mimeType};base64,${bytes.toString("base64")}`;
  javascript = javascript.replaceAll(assetFile, dataUrl);
}

const previewApi = String.raw`
<script>
(() => {
  const now = Math.floor(Date.now() / 1000);
  let nextId = 100;
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const json = (data, status = 200) => new Response(
    JSON.stringify({ success: status >= 200 && status < 300, data, error: null }),
    { status, headers: { "Content-Type": "application/json; charset=utf-8" } }
  );
  const bodyOf = async (init) => {
    if (!init || !init.body || init.body instanceof FormData) return {};
    try { return JSON.parse(init.body); } catch { return {}; }
  };

  const user = {
    id: 1,
    tenant_id: 1,
    login_name: "karries_staff",
    nickname: "禾一斯员工",
    user_role: "customer",
    wallet_balance: 11520
  };
  const profile = {
    domain_name: "女性穿搭与美业种草",
    persona: "专业、真诚、有生活感的品牌顾问",
    target_audience: "关注品质生活的 25-35 岁女性",
    content_style: "真实体验、细节丰富、自然种草",
    tone: "自然真诚",
    common_phrases: "亲测好用,细节很加分",
    forbidden_phrases: "绝对,百分百",
    tag_preferences: "美甲分享,精致生活,新品体验",
    word_count_preference: 600,
    topic_preferences: "新品上新,门店体验,使用教程"
  };
  const xhsAccounts = [
    {
      id: 1, user_id: 1, display_name: "禾一斯品牌主号", account_group: "品牌矩阵",
      status: 1, daily_limit: 3, min_interval_minutes: 360,
      last_publish_time: now - 86400, today_publish_count: 1,
      login_state_ready: true, create_time: now - 864000, update_time: now,
      profile: { ...profile, id: 1, create_time: now - 864000, update_time: now }
    },
    {
      id: 2, user_id: 1, display_name: "新品种草号", account_group: "内容矩阵",
      status: 1, daily_limit: 2, min_interval_minutes: 360,
      last_publish_time: now - 172800, today_publish_count: 0,
      login_state_ready: true, create_time: now - 604800, update_time: now,
      profile: { ...profile, id: 2, create_time: now - 604800, update_time: now }
    }
  ];
  const accounts = xhsAccounts.map((item) => ({
    id: item.id,
    account_name: item.display_name,
    platform: "xiaohongshu",
    cookie_path: "",
    status: 1,
    last_checked_time: now,
    create_time: item.create_time,
    update_time: item.update_time
  }));
  const drafts = [
    {
      id: 21, user_id: 1, product_id: 0, xhs_account_id: 1,
      source_type: "smart_create", content_type: "image_text",
      title: "马卡龙配色也太适合夏天了",
      body: "最近试了这组清透又显白的马卡龙色，细节很温柔，上手后整个人都显得更精致。日常通勤和周末约会都很好搭。",
      tags: ["美甲分享", "夏日配色", "精致生活"],
      material: { material_ids: [201, 202] }, status: "confirmed",
      ai_provider: "dianhui", model_name: "content-agent",
      prompt: {}, create_time: now - 7200, update_time: now - 7000
    },
    {
      id: 22, user_id: 1, product_id: 0, xhs_account_id: 2,
      source_type: "smart_create", content_type: "image_text",
      title: "新款红色美甲，显白又有氛围",
      body: "红色系真的很适合需要一点氛围感的日子，这一款不挑肤色，近看还有很细腻的光泽。",
      tags: ["红色美甲", "显白美甲", "新品种草"],
      material: { material_ids: [203] }, status: "draft",
      ai_provider: "dianhui", model_name: "content-agent",
      prompt: {}, create_time: now - 93600, update_time: now - 93000
    }
  ];
  const tasks = [{
    id: 31, account_id: 1, task_title: drafts[0].title, task_body: drafts[0].body,
    tags: drafts[0].tags, image_paths: [], schedule_time: now + 7200,
    status: 1, last_error: "", submitted_time: 0,
    create_time: now - 3600, update_time: now - 3600
  }];
  let plans = [{
    id: 41, user_id: 1, plan_name: "夏日新品种草发布计划",
    source_type: "content_draft", content_type: "image_text", product_id: 0,
    status: 2, schedule_start_time: now + 7200, schedule_end_time: now + 7200,
    scheduling_rule: { min_interval_minutes: 360 }, item_count: 1,
    create_time: now - 3600, update_time: now - 3000
  }];
  let planItems = [{
    id: 51, plan_id: 41, user_id: 1, xhs_account_id: 1,
    content_type: "image_text", title: drafts[0].title, body: drafts[0].body,
    tags: drafts[0].tags, material: drafts[0].material,
    scheduled_time: now + 7200, status: 1, last_error: "",
    attempt_count: 0, max_attempts: 3, next_retry_time: 0, submitted_time: 0,
    publish_result: {}, create_time: now - 3600, update_time: now - 3000
  }];
  let folders = [
    { id: 11, tenant_id: 1, parent_id: 0, folder_name: "2026 夏季新品", created_by_user_id: 1, child_folder_count: 0, asset_count: 3, create_time: now - 864000, update_time: now },
    { id: 12, tenant_id: 1, parent_id: 0, folder_name: "品牌常用素材", created_by_user_id: 1, child_folder_count: 0, asset_count: 2, create_time: now - 604800, update_time: now }
  ];
  let assets = [
    { id: 201, tenant_id: 1, user_id: 1, folder_id: 11, product_id: 0, package_id: 0, file_name: "夏季马卡龙美甲-正面.jpg", file_type: "image", mime_type: "image/jpeg", file_size: 1268000, create_time: now - 86400, update_time: now - 86400 },
    { id: 202, tenant_id: 1, user_id: 1, folder_id: 11, product_id: 0, package_id: 0, file_name: "夏季马卡龙美甲-细节.jpg", file_type: "image", mime_type: "image/jpeg", file_size: 938000, create_time: now - 86000, update_time: now - 86000 },
    { id: 203, tenant_id: 1, user_id: 1, folder_id: 11, product_id: 0, package_id: 0, file_name: "新品展示视频.mp4", file_type: "video", mime_type: "video/mp4", file_size: 18680000, create_time: now - 85200, update_time: now - 85200 },
    { id: 204, tenant_id: 1, user_id: 1, folder_id: 12, product_id: 0, package_id: 0, file_name: "品牌LOGO.png", file_type: "image", mime_type: "image/png", file_size: 238000, create_time: now - 604800, update_time: now - 604800 },
    { id: 205, tenant_id: 1, user_id: 1, folder_id: 12, product_id: 0, package_id: 0, file_name: "门店环境.mp4", file_type: "video", mime_type: "video/mp4", file_size: 24680000, create_time: now - 500000, update_time: now - 500000 }
  ];
  let videoJobs = [{
    id: 61, user_id: 1, job_title: "夏季新品种草短视频",
    script_text: "开场展示上手效果，中段切换细节与配色，结尾补充门店预约信息。",
    requirement_text: "整体节奏轻快，突出显白和高级感。",
    materials: [{ material_file_id: 203, file_name: "新品展示视频.mp4", file_type: "video", file_path: "", mime_type: "video/mp4", file_size: 18680000, remark: "主素材" }],
    status: 2, status_name: "in_production", status_text: "制作中",
    user_progress_text: "AI 智能剪辑处理中，预计 24 小时内完成",
    expected_delivery_time: now + 64800, operator_user_id: 0,
    developer_note: "", delivery: {}, delivered_time: 0,
    create_time: now - 21600, update_time: now - 18000
  }];
  const personalization = {
    id: 1, tenant_id: 1, user_id: 1,
    assistant_name: "小禾",
    assistant_traits: "专业、敏锐、耐心，擅长小红书内容策划与矩阵运营",
    preferred_address: "美甲禾一斯",
    occupation: "品牌内容运营",
    user_details: "负责美业产品种草、账号矩阵和内容排期，重视真实体验与品牌质感。",
    response_preferences: "先给结论，再给可执行步骤；文案自然、简洁、有生活感。",
    create_time: now - 604800, update_time: now
  };
  let sessions = [
    { id: 71, tenant_id: 1, user_id: 1, title: "新品小红书种草", linked_product_id: 0, linked_xhs_account_id: 1, goal_type: "topic", tone: "自然真诚", extra_requirement: "", generation_token: "", generation_started_time: 0, status: "active", is_pinned: true, pinned_time: now - 7200, message_count: 4, total_credit_cost: 2, create_time: now - 7200, update_time: now - 7000 },
    { id: 72, tenant_id: 1, user_id: 1, title: "门店活动内容规划", linked_product_id: 0, linked_xhs_account_id: 2, goal_type: "strategy", tone: "精致高级", extra_requirement: "", generation_token: "", generation_started_time: 0, status: "active", is_pinned: false, pinned_time: 0, message_count: 2, total_credit_cost: 1, create_time: now - 93600, update_time: now - 93000 }
  ];
  const sessionMessages = {
    71: [
      { id: 711, tenant_id: 1, session_id: 71, user_id: 1, role: "user", content: "根据产品卖点，帮我规划一周的小红书发布主题。", context: {}, ai_provider: "", ai_model: "", credit_cost: 0, latency_ms: 0, status: "success", error_message: "", content_draft_id: 0, create_time: now - 7100 },
      { id: 712, tenant_id: 1, session_id: 71, user_id: 1, role: "assistant", content: "可以。建议围绕“颜色显白、真实上手、场景搭配、细节质感”四条主线展开：周一做新品第一眼，周三做不同肤色对比，周五做通勤与约会搭配，周末补充门店体验和预约引导。", context: {}, ai_provider: "dianhui", ai_model: "inspiration-agent", credit_cost: 1, latency_ms: 820, status: "success", error_message: "", content_draft_id: 0, create_time: now - 7000 }
    ],
    72: []
  };
  let viralJobs = [{
    id: 81, tenant_id: 1, user_id: 1, title: "美甲新品爆款视频拆解",
    source_type: "upload", source_url: "", material_file_id: 203,
    analysis_goal: ["hook", "structure", "rhythm", "script", "reuse"],
    supplement_text: "重点关注开场钩子、镜头节奏和结尾转化。",
    status: "completed", ai_provider: "dianhui", ai_model: "video-analysis-agent",
    credit_cost: 3, error_message: "", create_time: now - 86400, update_time: now - 85000,
    materials: [{ id: 811, job_id: 81, file_name: "新品展示视频.mp4", file_type: "video", mime_type: "video/mp4", file_size: 18680000, create_time: now - 86400 }],
    result: {
      hook_summary: "前 3 秒直接展示高完成度上手效果，用近景和高饱和色彩抓住注意力。",
      structure_summary: "效果前置 → 原料与细节 → 多款上手轮播 → 套装与预约信息收尾。",
      shot_rhythm: "0-3 秒快速抓眼，3-8 秒补充细节，8-20 秒轮播款式，20 秒后集中转化。",
      script_breakdown: "timestamp: 00:00-00:03\ncontent: 新款上手效果直接亮相\nscene: 手部近景，画面干净明亮\ntimestamp: 00:03-00:08\ncontent: 展示材质与配色细节\nscene: 特写镜头切换\ntimestamp: 00:08-00:20\ncontent: 多款效果快速轮播\nscene: 不同手型和场景切换",
      selling_points: "显白配色、细腻光泽、日常百搭、门店可预约。",
      reuse_suggestions: "保留效果前置结构，替换成不同系列产品；结尾统一加入门店位置和预约引导。",
      rewritten_script: "这组颜色真的太适合夏天了。第一眼清透显白，近看还有很细腻的光泽，通勤和约会都能搭。最后一款是本周人气最高色，想看更多上手效果可以收藏。",
      tags: ["爆款拆解", "美甲种草", "视频脚本"],
      create_time: now - 85000
    }
  }];
  const membershipPlans = [
    { id: 1, plan_code: "free", plan_name: "免费版", price_cent: 0, summary: "基础体验", features: ["基础 AI 对话", "基础内容创作"], monthly_credits: 0, daily_checkin_credits: 20, storage_gb: 10, status: 1, sort_order: 1, create_time: now, update_time: now },
    { id: 2, plan_code: "pro", plan_name: "Pro 会员版", price_cent: 19900, summary: "开放全部运营功能", features: ["全部内容创作与运营功能", "爆款解析与 AI 灵感对话", "定时发布与账号矩阵管理"], monthly_credits: 1500, daily_checkin_credits: 20, storage_gb: 100, status: 1, sort_order: 2, create_time: now, update_time: now },
    { id: 3, plan_code: "max", plan_name: "Max 会员版", price_cent: 29900, summary: "Pro 全部功能与更大存储", features: ["包含 Pro 全部功能", "180 GB 云空间", "每月 3000 算力"], monthly_credits: 3000, daily_checkin_credits: 20, storage_gb: 180, status: 1, sort_order: 3, create_time: now, update_time: now },
    { id: 4, plan_code: "storage", plan_name: "存储大会员版", price_cent: 59900, summary: "Pro 全部功能与超大存储", features: ["包含 Pro 全部功能", "1000 GB 云空间", "每月 3000 算力"], monthly_credits: 3000, daily_checkin_credits: 20, storage_gb: 1000, status: 1, sort_order: 4, create_time: now, update_time: now }
  ];
  const membership = { id: 1, tenant_id: 1, user_id: 1, plan_id: 2, status: 1, start_time: now - 864000, expire_time: now + 1728000, auto_renew: 0, create_time: now - 864000, update_time: now, plan: membershipPlans[1] };
  let wallet = { id: 1, user_id: 1, balance: 11520, total_recharged: 12000, total_consumed: 480, create_time: now - 864000, update_time: now };
  let checkin = { checked_in: false, checkin_date: new Date().toISOString().slice(0, 10), credits: 20, balance: wallet.balance };
  const ledger = [
    { id: 1, user_id: 1, business_type: "membership", business_id: 1, before_balance: 10020, change_amount: 1500, after_balance: 11520, reason: "Pro 会员每月算力到账", create_time: now - 86400 },
    { id: 2, user_id: 1, business_type: "viral_analysis", business_id: 81, before_balance: 10023, change_amount: -3, after_balance: 10020, reason: "爆款解析", create_time: now - 85000 }
  ];
  const rechargePackages = [
    { id: 1, package_name: "20,000 算力包", base_credits: 20000, credits: 20000, price_cent: 100000, is_hot: 0, status: 1, sort_order: 1, create_time: now, update_time: now },
    { id: 2, package_name: "40,000 算力包", base_credits: 40000, credits: 40000, price_cent: 200000, is_hot: 0, status: 1, sort_order: 2, create_time: now, update_time: now },
    { id: 3, package_name: "100,000 算力包", base_credits: 100000, credits: 105000, price_cent: 500000, is_hot: 1, status: 1, sort_order: 3, create_time: now, update_time: now },
    { id: 4, package_name: "200,000 算力包", base_credits: 200000, credits: 220000, price_cent: 1000000, is_hot: 0, status: 1, sort_order: 4, create_time: now, update_time: now }
  ];
  let rechargeOrders = [];
  let notifications = [
    { id: 1, notification_type: "task", title: "今日发布任务提醒", content: "请在 16:00 前完成新品种草内容审核。", priority: 2, action_path: "schedule", business_type: "matrix_plan", business_id: 41, deadline_time: now + 14400, read_time: 0, is_read: false, create_time: now - 1800, update_time: now - 1800 },
    { id: 2, notification_type: "announcement", title: "本周内容方向更新", content: "本周重点突出夏季新品与门店真实体验。", priority: 1, action_path: "inspiration", business_type: "", business_id: 0, deadline_time: 0, read_time: now - 86400, is_read: true, create_time: now - 90000, update_time: now - 86400 }
  ];

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const rawUrl = input instanceof Request ? input.url : String(input);
    let url;
    try { url = new URL(rawUrl, location.href); } catch { return originalFetch(input, init); }
    if (url.hostname !== "127.0.0.1" || url.port !== "8765") {
      return originalFetch(input, init);
    }

    const path = url.pathname;
    const method = String(init.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
    const payload = await bodyOf(init);

    if (path === "/api/auth/me") return json(clone(user));
    if (path === "/api/auth/customer/login") return json({ access_token: "static-preview", token_type: "bearer", expires_in: 86400, user: clone(user) });

    if (path === "/api/notifications/unread-count") return json({ count: notifications.filter((item) => !item.is_read).length });
    if (path === "/api/notifications/read-all" && method === "POST") {
      notifications = notifications.map((item) => ({ ...item, is_read: true, read_time: now }));
      return json({ updated_count: notifications.length });
    }
    if (/^\/api\/notifications\/\d+\/read$/.test(path) && method === "POST") {
      const id = Number(path.split("/")[3]);
      notifications = notifications.map((item) => item.id === id ? { ...item, is_read: true, read_time: now } : item);
      return json({ id, is_read: true });
    }
    if (path === "/api/notifications") return json({ items: clone(notifications), page: 1, page_size: 20, total: notifications.length });

    if (path === "/api/wallet/membership-plans") return json(clone(membershipPlans));
    if (path === "/api/wallet/membership") return json(clone(membership));
    if (path === "/api/wallet/ledger") return json(clone(ledger));
    if (path === "/api/wallet/check-in" && method === "POST") {
      if (!checkin.checked_in) wallet = { ...wallet, balance: wallet.balance + 20, update_time: now };
      checkin = { ...checkin, checked_in: true, already_checked_in: false, balance: wallet.balance };
      return json(clone(checkin));
    }
    if (path === "/api/wallet/check-in") return json(clone(checkin));
    if (path === "/api/wallet/recharge-packages") return json(clone(rechargePackages));
    if (path === "/api/wallet/recharge-orders" && method === "POST") {
      const pkg = rechargePackages.find((item) => item.id === Number(payload.package_id));
      const order = { id: ++nextId, order_no: "KR" + Date.now(), tenant_id: 1, user_id: 1, recharge_type: payload.recharge_type || "online", package_id: pkg?.id || 0, package_name: pkg?.package_name || "自定义充值", amount_cent: pkg?.price_cent || Number(payload.amount_cent || 0), requested_credits: pkg?.credits || Math.floor(Number(payload.amount_cent || 0) / 5), payment_channel: payload.payment_channel || "wechat", status: 1, remark: "", paid_time: 0, completed_time: 0, create_time: now, update_time: now };
      rechargeOrders = [order, ...rechargeOrders];
      return json(clone(order));
    }
    if (path === "/api/wallet/recharge-orders") return json(clone(rechargeOrders));
    if (path === "/api/wallet") return json(clone(wallet));

    if (path === "/api/runtime/check") return json({ browser_automation: true, scheduler: true, database: true });
    if (path === "/api/accounts") return json(clone(accounts));
    if (path === "/api/tasks") return json(clone(tasks));
    if (/^\/api\/tasks\/\d+\/submit$/.test(path)) return json(clone({ ...tasks[0], status: 5, submitted_time: now, update_time: now }));

    if (path === "/api/xhs-accounts" && method === "POST") {
      const account = { id: ++nextId, user_id: 1, display_name: payload.display_name, account_group: payload.account_group || "", status: 1, daily_limit: payload.daily_limit || 1, min_interval_minutes: payload.min_interval_minutes || 360, last_publish_time: 0, today_publish_count: 0, login_state_ready: false, create_time: now, update_time: now, profile: payload.profile || profile };
      xhsAccounts.push(account);
      return json(clone(account));
    }
    if (path === "/api/xhs-accounts") return json(clone(xhsAccounts));
    if (/^\/api\/xhs-accounts\/\d+\/login\/start$/.test(path)) return json({ id: ++nextId, xhs_account_id: Number(path.split("/")[3]), status: "awaiting_scan", message: "请使用小红书扫码登录", qrcode_image_data: "", started_time: now, expires_time: now + 300, completed_time: 0, create_time: now, update_time: now });
    if (/^\/api\/xhs-accounts\/\d+\/login\/session$/.test(path)) return json(null);
    if (/^\/api\/xhs-accounts\/\d+\/login\/check$/.test(path)) {
      const id = Number(path.split("/")[3]);
      const account = xhsAccounts.find((item) => item.id === id) || xhsAccounts[0];
      return json({ valid: true, account: clone({ ...account, login_state_ready: true }) });
    }

    if (path === "/api/content-drafts/manual" && method === "POST") {
      const draft = { ...drafts[0], ...payload, id: ++nextId, source_type: "manual", status: "confirmed", create_time: now, update_time: now };
      drafts.unshift(draft);
      return json(clone(draft));
    }
    if (/^\/api\/content-drafts\/\d+$/.test(path) && method === "PATCH") {
      const id = Number(path.split("/")[3]);
      const index = drafts.findIndex((item) => item.id === id);
      if (index >= 0) drafts[index] = { ...drafts[index], ...payload, update_time: now };
      return json(clone(drafts[index] || drafts[0]));
    }
    if (path === "/api/content-drafts") return json(clone(drafts));

    if (path === "/api/ai/image-copy" && method === "POST") return json({ title: "夏日显白马卡龙美甲，温柔又高级", body: "这组配色真的很适合夏天。清透、显白，又不会过分张扬，近看还有很细腻的光泽感。无论是通勤、约会还是周末出游都很好搭，喜欢温柔氛围感的姐妹可以收藏。", tags: ["美甲分享", "夏日美甲", "显白配色", "新品种草"], history_id: 23 });

    if (path === "/api/matrix-plans/from-drafts" && method === "POST") {
      const plan = { ...plans[0], id: ++nextId, plan_name: payload.plan_name, schedule_start_time: payload.schedule_start_time, schedule_end_time: payload.schedule_end_time, status: 1, create_time: now, update_time: now };
      plans = [plan, ...plans];
      planItems = [{ ...planItems[0], id: ++nextId, plan_id: plan.id, scheduled_time: plan.schedule_start_time, status: 1, create_time: now, update_time: now }, ...planItems];
      return json({ id: plan.id, item_count: 1, draft_count: 1, account_count: 1 });
    }
    if (/^\/api\/matrix-plans\/\d+\/items$/.test(path)) {
      const id = Number(path.split("/")[3]);
      return json(clone(planItems.filter((item) => item.plan_id === id)));
    }
    if (/^\/api\/matrix-plans\/\d+\/confirm$/.test(path)) {
      const id = Number(path.split("/")[3]);
      plans = plans.map((item) => item.id === id ? { ...item, status: 2 } : item);
      return json({ id, status: 2, item_count: planItems.filter((item) => item.plan_id === id).length });
    }
    if (/^\/api\/matrix-plans\/\d+\/cancel$/.test(path)) {
      const id = Number(path.split("/")[3]);
      plans = plans.map((item) => item.id === id ? { ...item, status: 7 } : item);
      return json({ id, status: 7, cancelled_item_count: 1 });
    }
    if (/^\/api\/matrix-plans\/\d+\/retry-failed$/.test(path)) return json({ id: Number(path.split("/")[3]), status: 2, retried_item_count: 1 });
    if (/^\/api\/matrix-plans\/\d+$/.test(path)) return json(clone(plans.find((item) => item.id === Number(path.split("/")[3])) || plans[0]));
    if (path === "/api/matrix-plans") return json(clone(plans));

    if (path === "/api/video-edit/jobs" && method === "POST") {
      const job = { ...videoJobs[0], ...payload, id: ++nextId, status: 1, status_name: "submitted", status_text: "待制作", user_progress_text: "素材已提交，预计 24 小时内生成完成", expected_delivery_time: now + 86400, create_time: now, update_time: now };
      videoJobs = [job, ...videoJobs];
      return json(clone(job));
    }
    if (path === "/api/video-edit/jobs") return json(clone(videoJobs));

    if (path === "/api/inspiration/personalization" && method === "PUT") {
      Object.assign(personalization, payload, { update_time: now });
      return json(clone(personalization));
    }
    if (path === "/api/inspiration/personalization") return json(clone(personalization));
    if (path === "/api/inspiration/sessions" && method === "POST") {
      const session = { ...sessions[0], ...payload, id: ++nextId, message_count: 0, total_credit_cost: 0, is_pinned: false, pinned_time: 0, create_time: now, update_time: now };
      sessions = [session, ...sessions];
      sessionMessages[session.id] = [];
      return json(clone(session));
    }
    if (path === "/api/inspiration/sessions") return json({ items: clone(sessions), page: 1, page_size: 20, total: sessions.length });
    if (/^\/api\/inspiration\/sessions\/\d+\/messages$/.test(path) && method === "POST") {
      const id = Number(path.split("/")[4]);
      const messages = sessionMessages[id] || (sessionMessages[id] = []);
      const userMessage = { id: ++nextId, tenant_id: 1, session_id: id, user_id: 1, role: "user", content: payload.content, context: {}, ai_provider: "", ai_model: "", credit_cost: 0, latency_ms: 0, status: "success", error_message: "", content_draft_id: 0, create_time: now };
      const assistantMessage = { ...userMessage, id: ++nextId, role: "assistant", content: "我会结合你的品牌定位和账号风格来回答。建议先明确这次内容的核心产品、目标人群和希望用户采取的行动，我可以继续为你整理成选题、标题或完整脚本。", ai_provider: "dianhui", ai_model: "inspiration-agent", credit_cost: 1, latency_ms: 680 };
      messages.push(userMessage, assistantMessage);
      sessions = sessions.map((item) => item.id === id ? { ...item, message_count: item.message_count + 2, total_credit_cost: item.total_credit_cost + 1, update_time: now } : item);
      return json({ user_message: clone(userMessage), assistant_message: clone(assistantMessage), credit_cost: 1 });
    }
    if (/^\/api\/inspiration\/sessions\/\d+\/archive$/.test(path)) {
      const id = Number(path.split("/")[4]);
      sessions = sessions.map((item) => item.id === id ? { ...item, status: "archived" } : item);
      return json(clone(sessions.find((item) => item.id === id)));
    }
    if (/^\/api\/inspiration\/sessions\/\d+\/pin$/.test(path)) {
      const id = Number(path.split("/")[4]);
      sessions = sessions.map((item) => item.id === id ? { ...item, is_pinned: Boolean(payload.is_pinned), pinned_time: payload.is_pinned ? now : 0 } : item);
      return json(clone(sessions.find((item) => item.id === id)));
    }
    if (/^\/api\/inspiration\/sessions\/\d+$/.test(path) && method === "DELETE") {
      const id = Number(path.split("/")[4]);
      sessions = sessions.filter((item) => item.id !== id);
      return json({ deleted: true });
    }
    if (/^\/api\/inspiration\/sessions\/\d+$/.test(path) && method === "PATCH") {
      const id = Number(path.split("/")[4]);
      sessions = sessions.map((item) => item.id === id ? { ...item, title: payload.title || item.title, update_time: now } : item);
      return json(clone(sessions.find((item) => item.id === id)));
    }
    if (/^\/api\/inspiration\/sessions\/\d+$/.test(path)) {
      const id = Number(path.split("/")[4]);
      const session = sessions.find((item) => item.id === id) || sessions[0];
      return json({ session: clone(session), messages: clone(sessionMessages[id] || []) });
    }
    if (/^\/api\/inspiration\/messages\/\d+\/save-draft$/.test(path)) return json({ draft_id: ++nextId });

    if (path === "/api/material-library/folders" && method === "POST") {
      const folder = { id: ++nextId, tenant_id: 1, parent_id: Number(payload.parent_id || 0), folder_name: payload.folder_name, created_by_user_id: 1, child_folder_count: 0, asset_count: 0, create_time: now, update_time: now };
      folders.push(folder);
      return json(clone(folder));
    }
    if (/^\/api\/material-library\/folders\/\d+$/.test(path) && method === "PATCH") {
      const id = Number(path.split("/")[4]);
      folders = folders.map((item) => item.id === id ? { ...item, folder_name: payload.folder_name, update_time: now } : item);
      return json(clone(folders.find((item) => item.id === id)));
    }
    if (/^\/api\/material-library\/folders\/\d+$/.test(path) && method === "DELETE") {
      const id = Number(path.split("/")[4]);
      folders = folders.filter((item) => item.id !== id);
      assets = assets.filter((item) => item.folder_id !== id);
      return json({ deleted: true });
    }
    if (path === "/api/material-library/assets/upload" && method === "POST") {
      const file = init.body instanceof FormData ? init.body.get("file") : null;
      const folderId = Number(url.searchParams.get("folder_id") || 0);
      const asset = { id: ++nextId, tenant_id: 1, user_id: 1, folder_id: folderId, product_id: 0, package_id: 0, file_name: file?.name || "新素材.jpg", file_type: String(file?.type || "").startsWith("video/") ? "video" : "image", mime_type: file?.type || "image/jpeg", file_size: file?.size || 0, create_time: now, update_time: now };
      assets.push(asset);
      return json(clone(asset));
    }
    if (/^\/api\/material-library\/assets\/\d+\/content$/.test(path)) {
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240"><rect width="100%" height="100%" fill="#f8f1e8"/><path d="M80 165l48-54 34 34 25-28 53 48z" fill="#d9b985"/><circle cx="216" cy="72" r="22" fill="#efc66c"/><text x="160" y="215" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#7a5532">KARRIES PRODUCT</text></svg>';
      return new Response(svg, { status: 200, headers: { "Content-Type": "image/svg+xml" } });
    }
    if (/^\/api\/material-library\/assets\/\d+$/.test(path) && method === "DELETE") {
      const id = Number(path.split("/")[4]);
      assets = assets.filter((item) => item.id !== id);
      return json({ deleted: true });
    }
    if (/^\/api\/material-library\/assets\/\d+$/.test(path) && method === "PATCH") {
      const id = Number(path.split("/")[4]);
      assets = assets.map((item) => item.id === id ? { ...item, ...payload, update_time: now } : item);
      return json(clone(assets.find((item) => item.id === id)));
    }
    if (path === "/api/material-library/items") {
      const folderId = Number(url.searchParams.get("folder_id") || 0);
      const currentFolder = folders.find((item) => item.id === folderId) || null;
      const keyword = String(url.searchParams.get("keyword") || "").toLowerCase();
      return json({
        current_folder: clone(currentFolder),
        breadcrumbs: currentFolder ? [{ id: currentFolder.id, parent_id: currentFolder.parent_id, folder_name: currentFolder.folder_name }] : [],
        folders: clone(folders.filter((item) => item.parent_id === folderId && (!keyword || item.folder_name.toLowerCase().includes(keyword)))),
        assets: clone(assets.filter((item) => item.folder_id === folderId && (!keyword || item.file_name.toLowerCase().includes(keyword))))
      });
    }

    if (path === "/api/viral-analysis/jobs" && method === "POST") {
      const job = { ...viralJobs[0], ...payload, id: ++nextId, material_file_id: 0, status: "pending", credit_cost: 0, materials: [], result: null, create_time: now, update_time: now };
      viralJobs = [job, ...viralJobs];
      return json(clone(job));
    }
    if (path === "/api/viral-analysis/jobs") return json({ items: clone(viralJobs), page: 1, page_size: 20, total: viralJobs.length });
    if (/^\/api\/viral-analysis\/jobs\/\d+\/upload$/.test(path)) {
      const id = Number(path.split("/")[4]);
      const file = init.body instanceof FormData ? init.body.get("file") : null;
      const material = { id: ++nextId, job_id: id, file_name: file?.name || "参考视频.mp4", file_type: String(file?.type || "").startsWith("image/") ? "image" : "video", mime_type: file?.type || "video/mp4", file_size: file?.size || 0, create_time: now };
      viralJobs = viralJobs.map((item) => item.id === id ? { ...item, material_file_id: material.id, materials: [material], update_time: now } : item);
      return json(clone(material));
    }
    if (/^\/api\/viral-analysis\/jobs\/\d+\/run$/.test(path)) {
      const id = Number(path.split("/")[4]);
      const template = viralJobs[0].result || clone(viralJobs.find((item) => item.result)?.result);
      viralJobs = viralJobs.map((item) => item.id === id ? { ...item, status: "completed", credit_cost: 3, result: template, update_time: now } : item);
      return json(clone(viralJobs.find((item) => item.id === id)));
    }
    if (/^\/api\/viral-analysis\/jobs\/\d+\/cancel$/.test(path)) {
      const id = Number(path.split("/")[4]);
      viralJobs = viralJobs.map((item) => item.id === id ? { ...item, status: "cancelled", update_time: now } : item);
      return json(clone(viralJobs.find((item) => item.id === id)));
    }
    if (/^\/api\/viral-analysis\/jobs\/\d+\/save-draft$/.test(path)) return json({ draft_id: ++nextId });
    if (/^\/api\/viral-analysis\/jobs\/\d+$/.test(path)) return json(clone(viralJobs.find((item) => item.id === Number(path.split("/")[4])) || viralJobs[0]));

    return json(null);
  };
})();
</script>`;

const html = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="light" />
    <title>KARRIES 禾一斯智能运营平台</title>
    <style>${stylesheet}</style>
  </head>
  <body>
    <div id="root"></div>
    ${previewApi}
    <script type="module">${javascript}</script>
  </body>
</html>`;

await writeFile(outputPath, html, "utf8");
console.log(`${basename(outputPath)} ${Buffer.byteLength(html)} bytes`);
