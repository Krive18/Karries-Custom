import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { api } from "../api/client";


vi.mock("../api/client", () => ({
  ApiRequestError: class ApiRequestError extends Error {
    constructor(message: string, public readonly code: string, public readonly status: number) {
      super(message);
    }
  },
  api: {
    generateImageCopy: vi.fn(),
    listTasks: vi.fn(),
    createTask: vi.fn(),
    submitTask: vi.fn(),
    listAccounts: vi.fn(),
    createAccount: vi.fn(),
    checkRuntime: vi.fn(),
    getAISettings: vi.fn(),
    saveAISetting: vi.fn(),
    clearAISettingKey: vi.fn(),
    listVideoEditJobs: vi.fn(),
    createVideoEditJob: vi.fn(),
    listInternalVideoEditJobs: vi.fn(),
    claimInternalVideoEditJob: vi.fn(),
    deliverInternalVideoEditJob: vi.fn(),
    getAdminSummary: vi.fn(),
    listInspirationSessions: vi.fn(),
    createInspirationSession: vi.fn(),
    getInspirationSession: vi.fn(),
    sendInspirationMessage: vi.fn(),
    saveInspirationMessageDraft: vi.fn(),
    archiveInspirationSession: vi.fn(),
    listAdminInspirationSessions: vi.fn(),
    getAdminInspirationSession: vi.fn()
  }
}));


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


const aiSettings = {
  vision: {
    provider: "doubao",
    base_url: "https://vision.example/chat/completions",
    model: "doubao-vision-pro",
    enabled: true,
    has_key: false,
    masked_key: ""
  },
  copywriting: {
    provider: "deepseek",
    base_url: "https://api.deepseek.com/chat/completions",
    model: "deepseek-chat",
    enabled: true,
    has_key: true,
    masked_key: "sk-c********cret"
  }
};

const videoEditJob = {
  id: 31,
  user_id: 9,
  job_title: "禾一斯小红书种草视频剪辑",
  script_text: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
  requirement_text: "节奏自然，保留高级感。",
  materials: [
    {
      file_name: "look.mp4",
      file_type: "video" as const,
      file_path: "look.mp4",
      mime_type: "video/mp4",
      file_size: 1024,
      remark: ""
    }
  ],
  status: 1,
  status_name: "submitted" as const,
  status_text: "待生成视频",
  user_progress_text: "素材和脚本已提交，预计 24 小时内生成完毕",
  expected_delivery_time: 1782600000,
  operator_user_id: 0,
  developer_note: "",
  delivery: {},
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
  tone: "自然真诚",
  extra_requirement: "突出产品使用场景",
  generation_token: "",
  generation_started_time: 0,
  status: "active" as const,
  message_count: 2,
  total_credit_cost: 1,
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
      credit_cost: 1,
      latency_ms: 80,
      status: "success" as const,
      error_message: "",
      content_draft_id: 0,
      create_time: 1782570660
    }
  ]
};

const secondInspirationSession = {
  ...inspirationSession,
  id: 42,
  title: "门店活动内容策略",
  linked_product_id: 0,
  total_credit_cost: 0
};

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
  delete window.karriesPublisher;
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
  mockedApi.getAISettings.mockResolvedValue(aiSettings);
  mockedApi.saveAISetting.mockResolvedValue(aiSettings);
  mockedApi.clearAISettingKey.mockResolvedValue(aiSettings);
  mockedApi.listVideoEditJobs.mockResolvedValue([]);
  mockedApi.createVideoEditJob.mockResolvedValue(videoEditJob);
  mockedApi.listInternalVideoEditJobs.mockResolvedValue([videoEditJob]);
  mockedApi.claimInternalVideoEditJob.mockResolvedValue({ ...videoEditJob, status: 2, status_name: "in_production", status_text: "智能剪辑生成中" });
  mockedApi.deliverInternalVideoEditJob.mockResolvedValue({ ...videoEditJob, status: 3, status_name: "delivered", status_text: "视频已生成" });
  mockedApi.getAdminSummary.mockResolvedValue({
    total_users: 2,
    total_xhs_accounts: 20,
    total_matrix_plans: 6,
    total_video_edit_jobs: 3,
    pending_video_edit_jobs: 1
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
  mockedApi.saveInspirationMessageDraft.mockResolvedValue({ draft_id: 801 });
  mockedApi.archiveInspirationSession.mockResolvedValue({
    ...inspirationSession,
    status: "archived"
  });
  mockedApi.listAdminInspirationSessions.mockResolvedValue({
    items: [inspirationSession],
    page: 1,
    page_size: 20,
    total: 1
  });
  mockedApi.getAdminInspirationSession.mockResolvedValue(inspirationDetail);
});


describe("KARRIES desktop workspace", () => {
  it("opens on the smart creation workspace with the expected navigation", () => {
    render(<App />);

    expect(screen.getByText("KARRIES")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "智能创作" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "智能剪辑" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "定时发布" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "系统配置" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "素材智能解析" })).toBeInTheDocument();
    expect(screen.getByText("本地素材")).toBeInTheDocument();
    expect(screen.getByText("AI 解析结果")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI 智能解析" })).toBeInTheDocument();
  });

  it("submits a user video editing work order", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "智能剪辑" }));
    expect(await screen.findByRole("heading", { name: "智能剪辑" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("剪辑脚本"), {
      target: { value: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "提交智能剪辑" }));

    await waitFor(() => {
      expect(mockedApi.createVideoEditJob).toHaveBeenCalledWith(
        expect.objectContaining({
          job_title: "禾一斯小红书种草视频剪辑",
          script_text: "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。"
        })
      );
    });
    expect(await screen.findByText("待生成视频")).toBeInTheDocument();
  });

  it("switches between manager and developer portals", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /管理端/ }));
    expect(await screen.findByRole("heading", { name: "管理端 · 运营总览" })).toBeInTheDocument();
    expect(await screen.findByText("待处理剪辑")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /开发者端/ }));
    expect(await screen.findByRole("heading", { name: "开发者端 · 剪辑工单" })).toBeInTheDocument();
    expect(await screen.findByText("禾一斯小红书种草视频剪辑")).toBeInTheDocument();
  });

  it("accepts dropped local material files", () => {
    render(<App />);

    const uploadZone = screen.getByRole("button", { name: /拖入图片或视频到此处/ });
    const imageFile = new File(["image"], "look.png", { type: "image/png" });

    fireEvent.drop(uploadZone, {
      dataTransfer: {
        files: [imageFile]
      }
    });

    expect(screen.getByText("素材 1")).toBeInTheDocument();
    expect(screen.getByText("图片 1")).toBeInTheDocument();
  });

  it("loads existing backend tasks into the scheduled publishing page", async () => {
    mockedApi.listTasks.mockResolvedValue([taskView]);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "定时发布" }));

    expect(await screen.findByText("后端返回任务")).toBeInTheDocument();
  });

  it("generates copy through the backend ai api", async () => {
    render(<App />);
    const uploadZone = screen.getByRole("button", { name: /拖入图片或视频到此处/ });
    const imageFile = new File(["image"], "look.png", { type: "image/png" });

    fireEvent.drop(uploadZone, {
      dataTransfer: {
        files: [imageFile]
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "AI 智能解析" }));

    expect(await screen.findByText("后端生成标题")).toBeInTheDocument();
    expect(mockedApi.generateImageCopy).toHaveBeenCalledWith({
      image_paths: ["look.png"],
      style: "小红书种草",
      extra_prompt: ""
    });
  });

  it("uses desktop selected material paths for ai analysis", async () => {
    const selectMaterials = vi.fn().mockResolvedValue(["D:\\images\\look.png"]);
    window.karriesPublisher = {
      version: "0.1.0",
      selectMaterials
    };
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "选择图片/视频" }));

    expect(await screen.findByText("素材 1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "AI 智能解析" }));

    expect(await screen.findByText("后端生成标题")).toBeInTheDocument();
    expect(selectMaterials).toHaveBeenCalled();
    expect(mockedApi.generateImageCopy).toHaveBeenCalledWith({
      image_paths: ["D:\\images\\look.png"],
      style: "小红书种草",
      extra_prompt: ""
    });
  });

  it("saves generated copy as a backend publish task", async () => {
    render(<App />);
    const uploadZone = screen.getByRole("button", { name: /拖入图片或视频到此处/ });
    const imageFile = new File(["image"], "look.png", { type: "image/png" });

    fireEvent.drop(uploadZone, {
      dataTransfer: {
        files: [imageFile]
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "AI 智能解析" }));
    await screen.findByText("后端生成标题");
    fireEvent.click(screen.getByRole("button", { name: "生成发布任务" }));

    await waitFor(() => {
      expect(mockedApi.createTask).toHaveBeenCalledWith({
        account_id: 7,
        task_title: "后端生成标题",
        task_body: "后端生成正文",
        tags: ["禾一斯", "小红书种草"],
        image_paths: ["look.png"],
        schedule_time: expect.any(Number)
      });
    });
  });

  it("switches to scheduled publishing tasks", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "定时发布" }));

    expect(screen.getByRole("heading", { name: "定时发布任务" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建任务" })).toBeInTheDocument();
    expect(screen.getByText("暂无任务，请先新建小红书图文发布任务。")).toBeInTheDocument();
  });

  it("submits a backend task from the task list", async () => {
    mockedApi.listTasks.mockResolvedValue([taskView]);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "定时发布" }));
    await screen.findByText("后端返回任务");
    fireEvent.click(screen.getByRole("button", { name: "提交" }));

    await waitFor(() => {
      expect(mockedApi.submitTask).toHaveBeenCalledWith(11);
    });
    expect(await screen.findByText("已提交平台")).toBeInTheDocument();
  });

  it("switches to system settings", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "系统配置" }));

    expect(screen.getByRole("heading", { name: "系统配置" })).toBeInTheDocument();
    expect(await screen.findByText("视觉识图 API")).toBeInTheDocument();
    expect(screen.getByText("文案生成 API")).toBeInTheDocument();
    expect(screen.getByText("小红书账号管理")).toBeInTheDocument();
    expect(screen.getByText("运行环境检测")).toBeInTheDocument();
  });

  it("loads ai settings and saves the vision provider config", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "系统配置" }));
    expect(await screen.findByText("视觉识图 API")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("视觉 API KEY"), {
      target: { value: "sk-vision-secret" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存视觉配置" }));

    await waitFor(() => {
      expect(mockedApi.saveAISetting).toHaveBeenCalledWith(
        "vision",
        expect.objectContaining({
          provider: "doubao",
          api_key: "sk-vision-secret"
        })
      );
    });
  });

  it("creates an inspiration session, sends a message, and saves the assistant reply as a draft", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
    expect(await screen.findByRole("heading", { name: "灵感对话" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新建会话" }));
    fireEvent.change(screen.getByLabelText("会话标题"), {
      target: { value: "新品种草选题" }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建会话" }));

    await waitFor(() => {
      expect(mockedApi.createInspirationSession).toHaveBeenCalledWith(
        expect.objectContaining({ title: "新品种草选题", goal_type: "topic" })
      );
    });
    fireEvent.change(screen.getByLabelText("输入运营问题"), {
      target: { value: "给我 5 个新品选题" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("这里是 AI 返回的运营建议")).toBeInTheDocument();
    expect(screen.getByText("本次预计消耗 1 算力")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存为内容草稿" }));
    await waitFor(() => expect(mockedApi.saveInspirationMessageDraft).toHaveBeenCalledWith(502));
    expect(await screen.findByText("已保存为内容草稿")).toBeInTheDocument();
  });

  it("shows read-only inspiration records in the manager portal and filters loaded sessions", async () => {
    mockedApi.getAdminInspirationSession.mockResolvedValue({
      ...inspirationDetail,
      messages: [
        inspirationDetail.messages[0],
        { ...inspirationDetail.messages[1], content_draft_id: 801 }
      ]
    });
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /管理端/ }));
    fireEvent.click(screen.getByRole("button", { name: "灵感对话记录" }));

    expect(await screen.findByRole("heading", { name: "灵感对话记录" })).toBeInTheDocument();
    expect(await screen.findByText("这里是 AI 返回的运营建议")).toBeInTheDocument();
    expect(screen.getByText("总算力 1")).toBeInTheDocument();
    expect(screen.getByText("草稿 ID：801")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存为内容草稿" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("关键词筛选"), {
      target: { value: "不存在的关键词" }
    });
    fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));
    await waitFor(() => {
      expect(mockedApi.listAdminInspirationSessions).toHaveBeenLastCalledWith(
        expect.any(URLSearchParams)
      );
    });
  });

  it("pages user inspiration sessions with a real total", async () => {
    mockedApi.listInspirationSessions
      .mockResolvedValueOnce({ items: [inspirationSession], page: 1, page_size: 20, total: 21 })
      .mockResolvedValueOnce({ items: [secondInspirationSession], page: 2, page_size: 20, total: 21 });
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
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
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
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
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
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
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
    fireEvent.click(await screen.findByRole("button", { name: /新品种草选题/ }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.change(screen.getByLabelText("输入运营问题"), { target: { value: "继续补充 3 个角度" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("button", { name: "归档会话" })).toBeDisabled();
    reply.resolve({ user_message: inspirationDetail.messages[0], assistant_message: inspirationDetail.messages[1], credit_cost: 1 });
  });

  it("does not switch back when an older session send resolves after selecting another session", async () => {
    const reply = deferred<{ user_message: typeof inspirationDetail.messages[number]; assistant_message: typeof inspirationDetail.messages[number]; credit_cost: number }>();
    const secondDetail = { ...inspirationDetail, session: secondInspirationSession, messages: [] };
    mockedApi.listInspirationSessions.mockResolvedValue({
      items: [inspirationSession, secondInspirationSession], page: 1, page_size: 20, total: 2
    });
    mockedApi.getInspirationSession.mockImplementation((sessionId: number) => Promise.resolve(sessionId === 42 ? secondDetail : inspirationDetail));
    mockedApi.sendInspirationMessage.mockReturnValue(reply.promise);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
    fireEvent.click(await screen.findByRole("button", { name: /新品种草选题/ }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.change(screen.getByLabelText("输入运营问题"), { target: { value: "继续补充 3 个角度" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    fireEvent.click(screen.getByRole("button", { name: /门店活动内容策略/ }));
    await screen.findByRole("heading", { name: "门店活动内容策略" });

    reply.resolve({ user_message: inspirationDetail.messages[0], assistant_message: inspirationDetail.messages[1], credit_cost: 1 });
    await Promise.resolve();
    expect(screen.getByRole("heading", { name: "门店活动内容策略" })).toBeInTheDocument();
    expect(screen.queryByText("这里是 AI 返回的运营建议")).not.toBeInTheDocument();
  });

  it("recovers from a failed draft save and updates the real draft id after retry", async () => {
    mockedApi.getInspirationSession.mockResolvedValue(inspirationDetail);
    mockedApi.saveInspirationMessageDraft
      .mockRejectedValueOnce(new Error("草稿保存失败"))
      .mockResolvedValueOnce({ draft_id: 801 });
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
    fireEvent.click(await screen.findByRole("button", { name: /新品种草选题/ }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.click(screen.getByRole("button", { name: "保存为内容草稿" }));
    expect(await screen.findByText("草稿保存失败")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存为内容草稿" }));

    expect(await screen.findByText("草稿 ID：801")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "已保存为内容草稿" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "已保存为内容草稿" }));
    expect(mockedApi.saveInspirationMessageDraft).toHaveBeenCalledTimes(2);
  });

  it("clears the manager detail when server-side filters exclude the current session", async () => {
    mockedApi.listAdminInspirationSessions
      .mockResolvedValueOnce({ items: [inspirationSession], page: 1, page_size: 20, total: 1 })
      .mockResolvedValueOnce({ items: [], page: 1, page_size: 20, total: 0 });
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /管理端/ }));
    fireEvent.click(screen.getByRole("button", { name: "灵感对话记录" }));
    await screen.findByText("这里是 AI 返回的运营建议");
    fireEvent.change(screen.getByLabelText("关键词筛选"), { target: { value: "不存在的关键词" } });
    fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));

    expect(await screen.findByText(/选择一条会话记录查看完整内容/)).toBeInTheDocument();
    expect(screen.getByText("没有符合筛选条件的会话记录")).toBeInTheDocument();
  });
});
