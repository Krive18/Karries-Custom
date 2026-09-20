import { Captions, CheckCircle2, FileText, Lightbulb, ListTree, ScanText, Sparkles, Tags } from "lucide-react";

import type { ViralAnalysisResult as ViralResult } from "../../types";
import { ViralVisualAnalysis } from "./ViralVisualAnalysis";

type ViralAnalysisResultProps = {
  result: ViralResult | null | undefined;
  emptyText?: string;
};

const sections: Array<{
  key: keyof Pick<ViralResult, "hook_summary" | "structure_summary" | "shot_rhythm" | "selling_points" | "reuse_suggestions">;
  label: string;
  icon: typeof Sparkles;
}> = [
  { key: "hook_summary", label: "开场钩子", icon: Sparkles },
  { key: "structure_summary", label: "内容结构", icon: ListTree },
  { key: "shot_rhythm", label: "节奏建议", icon: CheckCircle2 },
  { key: "selling_points", label: "卖点提炼", icon: Lightbulb },
  { key: "reuse_suggestions", label: "复用建议", icon: Lightbulb }
];

type ScriptSegment = {
  timestamp: string;
  content: string;
  scene: string;
};

function parseScriptBreakdown(value: string): ScriptSegment[] {
  const segments: ScriptSegment[] = [];
  let current: ScriptSegment | null = null;

  for (const rawLine of value.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;

    const field = line.match(/^(timestamp|content|scene)\s*[:：]\s*(.*)$/i);
    if (!field) {
      if (current) current.content = [current.content, line].filter(Boolean).join(" ");
      continue;
    }

    const key = field[1].toLowerCase() as keyof ScriptSegment;
    const fieldValue = field[2].trim();
    if (key === "timestamp") {
      if (current) segments.push(current);
      current = { timestamp: fieldValue, content: "", scene: "" };
      continue;
    }

    if (!current) current = { timestamp: "", content: "", scene: "" };
    current[key] = fieldValue;
  }

  if (current) segments.push(current);
  return segments.filter((segment) => segment.timestamp || segment.content || segment.scene);
}

function renderText(value: string) {
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/^[-*•]\s*/, ""))
    .filter(Boolean);

  if (lines.length <= 1) return <p>{value}</p>;
  return <ul className="viral-result-points">{lines.map((line) => <li key={line}>{line}</li>)}</ul>;
}

type TranscriptSegment = {
  timestamp: string;
  content: string;
};

function parseTranscriptSegments(value: string): TranscriptSegment[] {
  const normalized = value.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  if (!normalized.startsWith("[")) {
    return [];
  }

  try {
    const parsed: unknown = JSON.parse(normalized);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.flatMap((item) => {
      if (!item || typeof item !== "object") {
        return [];
      }
      const timestamp = "timestamp" in item && typeof item.timestamp === "string" ? item.timestamp.trim() : "";
      const content = "content" in item && typeof item.content === "string" ? item.content.trim() : "";
      return timestamp && content ? [{ timestamp, content }] : [];
    });
  } catch {
    return [];
  }
}

function renderTranscript(value: string) {
  const segments = parseTranscriptSegments(value);
  if (segments.length === 0) {
    return renderText(value);
  }

  return (
    <div className="viral-transcript-timeline" role="list">
      {segments.map((segment, index) => (
        <div className="viral-transcript-segment" role="listitem" key={`${segment.timestamp}-${index}`}>
          <time>{segment.timestamp.endsWith("秒") ? segment.timestamp : `${segment.timestamp}秒`}</time>
          <p>{segment.content}</p>
        </div>
      ))}
    </div>
  );
}

export function ViralAnalysisResult({ result, emptyText = "完成解析后，这里会显示结构化结果。" }: ViralAnalysisResultProps) {
  if (!result) return <div className="empty-list-state viral-result-empty">{emptyText}</div>;
  const scriptSegments = parseScriptBreakdown(result.script_breakdown);

  return (
    <section className="viral-result" aria-label="爆款解析结果">
      {sections.map(({ key, label, icon: Icon }) => result[key] ? (
        <article className="viral-result-section" key={key}>
          <h3><Icon size={16} aria-hidden="true" />{label}</h3>
          {renderText(result[key])}
        </article>
      ) : null)}
      <article className="viral-result-section viral-transcript-section">
        <h3><Captions size={16} aria-hidden="true" />原视频字幕脚本</h3>
        {result.original_transcript
          ? renderTranscript(result.original_transcript)
          : <p className="viral-transcript-empty">该历史记录未保存原视频字幕。请重新提交原视频进行解析，系统会提取口播与画面字幕。</p>}
      </article>
      <article className="viral-result-section viral-transcript-analysis-section">
        <h3><ScanText size={16} aria-hidden="true" />字幕脚本分析</h3>
        {result.transcript_analysis
          ? renderText(result.transcript_analysis)
          : <p className="viral-transcript-empty">缺少可核对的原字幕，暂不生成推测性分析。重新解析后会补充语言钩子、表达结构与行动引导分析。</p>}
      </article>
      <ViralVisualAnalysis data={result} />
      {result.script_breakdown ? (
        <article className="viral-result-section viral-script-section">
          <h3><FileText size={16} aria-hidden="true" />脚本拆解</h3>
          {scriptSegments.length ? (
            <div className="viral-script-timeline">
              {scriptSegments.map((segment, index) => (
                <div className="viral-script-segment" key={`${segment.timestamp}-${index}`}>
                  <span className="viral-script-time">{segment.timestamp || `镜头 ${index + 1}`}</span>
                  <div>
                    {segment.content ? <strong>{segment.content}</strong> : null}
                    {segment.scene ? <p>{segment.scene}</p> : null}
                  </div>
                </div>
              ))}
            </div>
          ) : renderText(result.script_breakdown)}
        </article>
      ) : null}
      {result.rewritten_script ? (
        <article className="viral-result-section viral-rewritten-section">
          <h3><FileText size={16} aria-hidden="true" />改写脚本</h3>
          {renderText(result.rewritten_script)}
        </article>
      ) : null}
      <div className="viral-tags"><Tags size={16} aria-hidden="true" />{result.tags.map((tag) => <span key={tag}>#{tag.replace(/^#/, "")}</span>)}</div>
    </section>
  );
}
