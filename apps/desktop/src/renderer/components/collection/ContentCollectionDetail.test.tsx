import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ContentCollection } from "../../types";
import { ContentCollectionDetail } from "./ContentCollectionDetail";


const collectionFixture: ContentCollection = {
  id: 21,
  tenant_id: 1,
  user_id: 7,
  source_type: "viral_analysis",
  source_id: 71,
  title: "美甲教程爆款拆解",
  hook_summary: "前三秒展示成品反差",
  structure_summary: "痛点、演示、结果、行动引导",
  shot_rhythm: "开场快切，中段放慢",
  script_breakdown: "### 镜头一\n\n- 0-3 秒：展示成品",
  selling_points: "步骤清晰，效果直观",
  reuse_suggestions: "替换产品和场景即可复用",
  rewritten_script: "## 改写标题\n\n1. 展示反差\n2. 演示步骤",
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
  tags: ["美甲教程", "#爆款脚本"],
  source_context: {
    analysis_goal: ["hook", "structure", "script"],
    source_type: "text",
    source_url: ""
  },
  create_time: 1782570700,
  update_time: 1782570700
};

function renderDetail(
  item: ContentCollection,
  overrides: Partial<React.ComponentProps<typeof ContentCollectionDetail>> = {}
) {
  const props = {
    item,
    isSaving: false,
    onSave: vi.fn().mockResolvedValue(true),
    onCopy: vi.fn().mockResolvedValue(undefined),
    onDelete: vi.fn().mockResolvedValue(undefined),
    ...overrides
  };
  return { ...render(<ContentCollectionDetail {...props} />), props };
}

describe("ContentCollectionDetail", () => {
  it("renders an inspiration conversation as rich read-only content and preserves the raw editor value", async () => {
    const item: ContentCollection = {
      ...collectionFixture,
      source_type: "inspiration",
      source_id: 502,
      title: "AI Agent 对话收藏",
      rewritten_script: "## 对话标题\n\n- 卖点一\n- 卖点二",
      source_context: { session_id: 41, ai_provider: "deepseek", ai_model: "deepseek-chat" }
    };
    const { container, props } = renderDetail(item);

    expect(screen.getByRole("heading", { name: "对话标题" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(container.querySelector(".rich-content-reader--assistant")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "复制AI 对话内容" }));
    await waitFor(() => expect(props.onCopy).toHaveBeenCalledWith(
      item.rewritten_script,
      "AI 对话内容"
    ));

    fireEvent.click(screen.getByRole("button", { name: "编辑收藏稿" }));
    expect(screen.getByRole("textbox", { name: "AI 对话内容" })).toHaveValue(
      item.rewritten_script
    );
  });

  it("keeps the inspiration empty state copyable with the original empty string", async () => {
    const item: ContentCollection = {
      ...collectionFixture,
      source_type: "inspiration",
      rewritten_script: ""
    };
    const { props } = renderDetail(item);

    expect(screen.getByText("暂无 AI 对话内容")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "复制AI 对话内容" }));

    await waitFor(() => expect(props.onCopy).toHaveBeenCalledWith("", "AI 对话内容"));
  });

  it("renders both viral-analysis documents with script readers while retaining analysis, tags, and actions", async () => {
    const { container, props } = renderDetail(collectionFixture);

    expect(screen.getByRole("heading", { name: "改写标题" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "镜头一" })).toBeInTheDocument();
    expect(container.querySelectorAll(".rich-content-reader--script")).toHaveLength(2);
    expect(screen.getByLabelText("画面分析")).toBeInTheDocument();
    expect(screen.getByText("#美甲教程")).toBeInTheDocument();
    expect(screen.getByText("#爆款脚本")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除收藏" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "编辑收藏稿" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "复制改写脚本" }));
    fireEvent.click(screen.getByRole("button", { name: "复制脚本拆解与分镜" }));
    await waitFor(() => {
      expect(props.onCopy).toHaveBeenCalledWith(collectionFixture.rewritten_script, "改写脚本");
      expect(props.onCopy).toHaveBeenCalledWith(collectionFixture.script_breakdown, "脚本拆解与分镜");
    });
  });

  it("preserves full-draft copy output and saves edited raw strings", async () => {
    const onSave = vi.fn().mockResolvedValue(true);
    const onCopy = vi.fn().mockResolvedValue(undefined);
    renderDetail(collectionFixture, { onSave, onCopy });

    fireEvent.click(screen.getByRole("button", { name: "复制完整草稿" }));
    await waitFor(() => expect(onCopy).toHaveBeenCalledWith(
      expect.stringContaining(`改写脚本：\n${collectionFixture.rewritten_script}`),
      "完整草稿"
    ));
    const fullDraft = onCopy.mock.calls.find((call) => call[1] === "完整草稿")?.[0];
    expect(fullDraft).toContain(`脚本拆解与分镜：\n${collectionFixture.script_breakdown}`);
    expect(fullDraft).toContain("布景分析：\n室内桌面拍摄，产品位于中景。");
    expect(fullDraft).toContain("标签：#美甲教程 #爆款脚本");

    fireEvent.click(screen.getByRole("button", { name: "编辑收藏稿" }));
    expect(screen.getByRole("textbox", { name: "改写脚本" })).toHaveValue(
      collectionFixture.rewritten_script
    );
    expect(screen.getByRole("textbox", { name: "脚本拆解与分镜" })).toHaveValue(
      collectionFixture.script_breakdown
    );

    fireEvent.change(screen.getByRole("textbox", { name: "收藏稿标题" }), {
      target: { value: "  编辑后的标题  " }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "改写脚本" }), {
      target: { value: "  ## 新脚本\n\n原始 Markdown  " }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "脚本拆解与分镜" }), {
      target: { value: "  ### 新分镜\n\n- 镜头  " }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "标签" }), {
      target: { value: " #新标签, 新标签， 收藏稿 " }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith({
      title: "编辑后的标题",
      rewritten_script: "## 新脚本\n\n原始 Markdown",
      script_breakdown: "### 新分镜\n\n- 镜头",
      tags: ["新标签", "收藏稿"]
    }));
  });
});
