import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { api } from "../api/client";


vi.mock("../api/client", () => ({
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
    getAdminSummary: vi.fn()
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


beforeEach(() => {
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
});
