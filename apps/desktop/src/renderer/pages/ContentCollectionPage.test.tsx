import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { ContentCollection } from "../types";
import { ContentCollectionPage } from "./ContentCollectionPage";


vi.mock("../api/client", () => ({
  api: {
    listContentCollections: vi.fn(),
    getContentCollection: vi.fn(),
    updateContentCollection: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

const collection: ContentCollection = {
  id: 21,
  tenant_id: 1,
  user_id: 7,
  source_type: "viral_analysis",
  source_id: 71,
  title: "美甲教程爆款拆解",
  hook_summary: "前三秒展示成品反差",
  structure_summary: "痛点、演示、结果、行动引导",
  shot_rhythm: "开场快切，中段放慢",
  script_breakdown: "timestamp: 0-3秒\ncontent: 展示成品\nscene: 手部特写",
  selling_points: "步骤清晰，效果直观",
  reuse_suggestions: "替换产品和场景即可复用",
  rewritten_script: "先展示反差，再演示步骤，最后引导收藏。",
  setting_analysis: "室内桌面拍摄，产品位于中景。",
  lighting_analysis: "左侧暖色柔光，整体曝光明亮。",
  visual_style: "清透、暖调、生活化",
  timeline_visual_analysis: [{
    time_range: "0-3秒",
    setting: "桌面产品布景",
    lighting: "暖色侧光",
    visual_style: "清透生活化",
    evidence_type: "visible_confirmed",
    confidence: "high",
    visible_evidence: "左侧高光清晰可见"
  }],
  visual_evidence: [{
    conclusion: "可能采用浅景深",
    evidence_type: "inferred",
    confidence: "medium",
    visible_evidence: "主体清晰、背景虚化"
  }],
  tags: ["美甲教程", "爆款脚本"],
  source_context: {
    analysis_goal: ["hook", "structure", "script"],
    source_type: "text",
    source_url: ""
  },
  create_time: 1782570700,
  update_time: 1782570700
};

describe("ContentCollectionPage", () => {
  beforeEach(() => {
    mockedApi.listContentCollections.mockResolvedValue({
      items: [collection],
      page: 1,
      page_size: 20,
      total: 1
    });
    mockedApi.getContentCollection.mockResolvedValue(collection);
    mockedApi.updateContentCollection.mockImplementation(async (_id, payload) => ({
      ...collection,
      ...payload,
      update_time: collection.update_time + 1
    }));
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) }
    });
  });

  it("loads the real collection detail and copies the complete draft", async () => {
    render(<ContentCollectionPage />);

    expect(await screen.findByRole("heading", { name: "内容收藏" })).toBeInTheDocument();
    expect(await screen.findByText("前三秒展示成品反差")).toBeInTheDocument();
    expect(screen.getByText("室内桌面拍摄，产品位于中景。")).toBeInTheDocument();
    expect(screen.getByText("画面可确认")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "复制完整草稿" }));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1));
    expect(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0]).toContain("先展示反差");
    expect(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0]).toContain("布景分析");
    expect(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0]).toContain("画面可确认");
    expect(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0]).toContain("#美甲教程");
  });

  it("edits title, script, segments and tags without starting an AI task", async () => {
    render(<ContentCollectionPage />);
    await screen.findByText("前三秒展示成品反差");

    fireEvent.click(screen.getByRole("button", { name: "编辑收藏稿" }));
    fireEvent.change(screen.getByLabelText("收藏稿标题"), {
      target: { value: "编辑后的美甲脚本" }
    });
    fireEvent.change(screen.getByLabelText("改写脚本"), {
      target: { value: "编辑后的完整口播稿" }
    });
    fireEvent.change(screen.getByLabelText("脚本拆解与分镜"), {
      target: { value: "timestamp: 0-5秒\ncontent: 新分镜" }
    });
    fireEvent.change(screen.getByLabelText("标签"), {
      target: { value: "已编辑, 收藏稿" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() => expect(mockedApi.updateContentCollection).toHaveBeenCalledWith(21, {
      title: "编辑后的美甲脚本",
      rewritten_script: "编辑后的完整口播稿",
      script_breakdown: "timestamp: 0-5秒\ncontent: 新分镜",
      tags: ["已编辑", "收藏稿"]
    }));
    const successMessage = await screen.findByText("收藏稿已更新，不会产生算力消耗。");
    expect(successMessage).toHaveClass("collection-message-success", "success");
    expect(successMessage).toHaveAttribute("role", "status");
  });

  it("keeps the editor open when saving fails", async () => {
    mockedApi.updateContentCollection.mockRejectedValueOnce(new Error("保存失败"));
    render(<ContentCollectionPage />);
    await screen.findByText("前三秒展示成品反差");

    fireEvent.click(screen.getByRole("button", { name: "编辑收藏稿" }));
    fireEvent.change(await screen.findByLabelText("收藏稿标题"), {
      target: { value: "尚未保存的标题" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    const errorMessage = await screen.findByText("保存失败");
    expect(errorMessage).toHaveClass("error");
    expect(errorMessage).toHaveAttribute("role", "alert");
    expect(screen.getByLabelText("收藏稿标题")).toHaveValue("尚未保存的标题");
  });

  it("identifies AI Agent collections without presenting them as viral analysis", async () => {
    const inspirationCollection: ContentCollection = {
      ...collection,
      id: 22,
      source_type: "inspiration",
      source_id: 502,
      title: "AI Agent 对话收藏",
      rewritten_script: "这是从 AI Agent 保存的完整回答。",
      source_context: { session_id: 41, ai_provider: "deepseek", ai_model: "deepseek-chat" }
    };
    mockedApi.listContentCollections.mockResolvedValue({
      items: [inspirationCollection],
      page: 1,
      page_size: 20,
      total: 1
    });
    mockedApi.getContentCollection.mockResolvedValue(inspirationCollection);

    render(<ContentCollectionPage />);

    expect(await screen.findByText("来自 Karries AI · 消息 #502")).toBeInTheDocument();
    expect(screen.queryByText("来自爆款解析 · #502")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI 对话内容" })).toBeInTheDocument();
    expect(screen.getByText("这是从 AI Agent 保存的完整回答。")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "改写脚本" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "脚本拆解与分镜" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "编辑收藏稿" }));
    expect(screen.getByLabelText("AI 对话内容")).toHaveValue(
      "这是从 AI Agent 保存的完整回答。"
    );
    expect(screen.queryByLabelText("改写脚本")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("脚本拆解与分镜")).not.toBeInTheDocument();
  });
});
