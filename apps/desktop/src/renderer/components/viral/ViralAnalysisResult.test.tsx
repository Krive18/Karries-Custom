import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ViralAnalysisResult as ViralResult } from "../../types";
import { ViralAnalysisResult } from "./ViralAnalysisResult";


const result: ViralResult = {
  hook_summary: "首秒产品特写",
  structure_summary: "特写、演示、成品展示",
  shot_rhythm: "前快后稳",
  original_transcript: "[口播 0-3秒] 还在为桌面杂乱发愁吗？\n[画面字幕 3-6秒] 一秒收纳",
  transcript_analysis: "疑问句先制造痛点，再用短句给出结果承诺；信息密度高，行动指向明确。",
  script_breakdown: "",
  selling_points: "细节清楚",
  reuse_suggestions: "替换产品即可复用",
  rewritten_script: "先展示产品，再演示使用。",
  setting_analysis: "室内桌面拍摄，浅色背景，主体位于画面中心。",
  lighting_analysis: "左前侧暖色柔光，阴影边缘柔和。",
  visual_style: "清透、暖调、生活化",
  timeline_visual_analysis: [
    {
      time_range: "0-3秒",
      setting: "浅色桌面产品布景",
      lighting: "暖色侧光",
      visual_style: "清透生活化",
      evidence_type: "visible_confirmed",
      confidence: "high",
      visible_evidence: "产品左侧高光明显，右侧阴影柔和"
    }
  ],
  visual_evidence: [
    {
      conclusion: "可能采用浅景深",
      evidence_type: "inferred",
      confidence: "medium",
      visible_evidence: "主体清晰、背景虚化"
    }
  ],
  tags: ["产品展示"],
  create_time: 1782570700
};

describe("ViralAnalysisResult", () => {
  it("shows the original subtitle script and a grounded language analysis before the rewrite", () => {
    render(<ViralAnalysisResult result={result} />);

    expect(screen.getByRole("heading", { name: "原视频字幕脚本" })).toBeInTheDocument();
    expect(screen.getByText(/还在为桌面杂乱发愁吗/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "字幕脚本分析" })).toBeInTheDocument();
    expect(screen.getByText(/疑问句先制造痛点/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "改写脚本" })).toBeInTheDocument();
  });

  it("keeps the subtitle sections visible for legacy results that predate transcript storage", () => {
    render(
      <ViralAnalysisResult
        result={{ ...result, original_transcript: "", transcript_analysis: "" }}
      />
    );

    expect(screen.getByRole("heading", { name: "原视频字幕脚本" })).toBeInTheDocument();
    expect(screen.getByText(/该历史记录未保存原视频字幕/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "字幕脚本分析" })).toBeInTheDocument();
    expect(screen.getByText(/暂不生成推测性分析/)).toBeInTheDocument();
  });

  it("turns a JSON subtitle payload into a readable timestamped transcript", () => {
    render(
      <ViralAnalysisResult
        result={{
          ...result,
          original_transcript: JSON.stringify([
            { timestamp: "0.0-2.0", content: "[口播] ok ok ok" },
            { timestamp: "3.0-6.0", content: "[画面字幕] 哇塞哇塞" }
          ])
        }}
      />
    );

    expect(screen.getByText("0.0-2.0秒")).toBeInTheDocument();
    expect(screen.getByText("[口播] ok ok ok")).toBeInTheDocument();
    expect(screen.getByText("3.0-6.0秒")).toBeInTheDocument();
    expect(screen.getByText("[画面字幕] 哇塞哇塞")).toBeInTheDocument();
    expect(screen.queryByText("[")).not.toBeInTheDocument();
  });

  it("renders grounded scene, lighting, style and timeline evidence without flattening confidence", () => {
    render(<ViralAnalysisResult result={result} />);

    expect(screen.getByRole("heading", { name: "布景分析" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "光影分析" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "画面风格" })).toBeInTheDocument();
    expect(screen.getByText("0-3秒")).toBeInTheDocument();
    expect(screen.getByText("画面可确认")).toBeInTheDocument();
    expect(screen.getByText("根据画面推测")).toBeInTheDocument();
    expect(screen.getByText("高可信度")).toBeInTheDocument();
    expect(screen.getByText("中可信度")).toBeInTheDocument();
    expect(screen.getByText("主体清晰、背景虚化")).toBeInTheDocument();
  });
});
