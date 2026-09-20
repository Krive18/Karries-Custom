import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AiTranslationPage } from "./AiTranslationPage";
import { customerApi } from "../api/client";
import type { AiTranslationTask } from "../types";


vi.mock("../api/client", () => ({
  customerApi: {
    listAiTranslationTasks: vi.fn(),
    uploadAiTranslationTask: vi.fn(),
    createAiTranslationTaskFromMaterial: vi.fn(),
    cancelAiTranslationTask: vi.fn(),
    acceptAiTranslationTask: vi.fn(),
    requestAiTranslationRevision: vi.fn(),
    getAiTranslationSourceBlob: vi.fn(),
    getAiTranslationDeliveryBlob: vi.fn()
  }
}));

vi.mock("../components/material/MaterialLibraryPicker", () => ({
  MaterialLibraryPicker: () => null
}));


const pendingTask: AiTranslationTask = {
  id: 1,
  tenant_id: 1,
  tenant_name: "本地测试团队",
  user_id: 9,
  user_login_name: "customer",
  user_nickname: "客户",
  client_request_id: "translation-1",
  source_type: "local_upload",
  material_file_id: 0,
  source_file_name: "source.mp4",
  source_file_path: "data/translation/source.mp4",
  source_mime_type: "video/mp4",
  source_file_size: 12 * 1024 * 1024,
  source_language: "zh",
  target_language: "en",
  status: "pending",
  status_text: "待接取",
  operator_user_id: 0,
  operator_name: "",
  developer_note: "",
  revision_feedback: "",
  revision_count: 0,
  delivery_count: 0,
  charged_credit_cost: 0,
  credit_ledger_id: 0,
  delivered_time: 0,
  completed_time: 0,
  create_time: 1786766400,
  update_time: 1786766400,
  deliveries: [],
  delivery_resource_counts: { video: 0, voiceover: 0, subtitle: 0 }
};


describe("AiTranslationPage customer language", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(customerApi.listAiTranslationTasks).mockResolvedValue([pendingTask]);
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:translation-preview")
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn()
    });
  });

  it("presents translation as a customer product without internal staffing language", async () => {
    render(<AiTranslationPage />);

    expect(await screen.findByRole("heading", { name: "AI智能翻译" })).toBeInTheDocument();
    expect(await screen.findAllByText("准备中")).not.toHaveLength(0);
    expect(screen.queryByText(/预计\s*100\s*算力/)).not.toBeInTheDocument();
    expect(screen.queryByText(/成片可用后扣除/)).not.toBeInTheDocument();
    expect(screen.queryByText("处理中")).not.toBeInTheDocument();
    expect(screen.queryByText("翻译任务 #1")).not.toBeInTheDocument();
    expect(screen.queryByText("已接取")).not.toBeInTheDocument();
    expect(screen.queryByText("待接取")).not.toBeInTheDocument();
    expect(screen.queryByText(/\u5f00\u53d1\u8005/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\u63d0\u4ea4\u4e0d\u6263\u7b97\u529b/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /source\.mp4/ }));

    expect(screen.getByText("翻译任务 #1")).toBeInTheDocument();
    expect(screen.getByText("处理中")).toBeInTheDocument();
  });

  it("maps internal claimed state to customer-facing processing language", async () => {
    vi.mocked(customerApi.listAiTranslationTasks).mockResolvedValue([
      { ...pendingTask, status: "claimed", status_text: "已接取" }
    ]);

    render(<AiTranslationPage />);

    expect((await screen.findAllByText("翻译处理中")).length).toBeGreaterThan(0);
    expect(screen.queryByText("已接取")).not.toBeInTheDocument();
  });

  it("shows an explicit loading state while the source preview is opening", async () => {
    let resolvePreview!: (blob: Blob) => void;
    vi.mocked(customerApi.getAiTranslationSourceBlob).mockImplementation(
      () => new Promise((resolve) => {
        resolvePreview = resolve;
      })
    );

    render(<AiTranslationPage />);

    fireEvent.click(await screen.findByRole("button", { name: /source\.mp4/ }));
    fireEvent.click(screen.getByRole("button", { name: "预览原视频" }));

    expect(screen.getByRole("button", { name: "正在打开" })).toBeDisabled();

    resolvePreview(new Blob(["video"], { type: "video/mp4" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "预览原视频" })).toBeEnabled();
    });
  });
});
