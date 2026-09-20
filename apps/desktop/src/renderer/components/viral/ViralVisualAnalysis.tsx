import { Clock3, Eye, Lightbulb, Palette, ScanSearch, SunMedium } from "lucide-react";

import type {
  ViralAnalysisResult,
  ViralVisualConfidence,
  ViralVisualEvidenceType
} from "../../types";


export type ViralVisualAnalysisData = Pick<
  ViralAnalysisResult,
  | "setting_analysis"
  | "lighting_analysis"
  | "visual_style"
  | "timeline_visual_analysis"
  | "visual_evidence"
>;

const evidenceLabels: Record<ViralVisualEvidenceType, string> = {
  visible_confirmed: "画面可确认",
  inferred: "根据画面推测"
};

const confidenceLabels: Record<ViralVisualConfidence, string> = {
  high: "高可信度",
  medium: "中可信度",
  low: "低可信度"
};

export function visualAnalysisPlainText(data: ViralVisualAnalysisData): string {
  const timeline = (data.timeline_visual_analysis ?? []).map((segment) => (
    `${segment.time_range}｜布景：${segment.setting || "未确认"}｜光影：${segment.lighting || "未确认"}`
    + `｜风格：${segment.visual_style || "未确认"}｜${evidenceLabels[segment.evidence_type]}`
    + `｜${confidenceLabels[segment.confidence]}｜依据：${segment.visible_evidence}`
  ));
  const evidence = (data.visual_evidence ?? []).map((item) => (
    `${item.conclusion}｜${evidenceLabels[item.evidence_type]}｜${confidenceLabels[item.confidence]}`
    + `｜可见依据：${item.visible_evidence}`
  ));
  return [
    data.setting_analysis ? `布景分析：\n${data.setting_analysis}` : "",
    data.lighting_analysis ? `光影分析：\n${data.lighting_analysis}` : "",
    data.visual_style ? `画面风格：\n${data.visual_style}` : "",
    timeline.length ? `分时段画面分析：\n${timeline.join("\n")}` : "",
    evidence.length ? `可信度和可见依据：\n${evidence.join("\n")}` : ""
  ].filter(Boolean).join("\n\n");
}

export function ViralVisualAnalysis({ data }: { data: ViralVisualAnalysisData }) {
  const summaries = [
    { key: "setting", label: "布景分析", value: data.setting_analysis, icon: ScanSearch },
    { key: "lighting", label: "光影分析", value: data.lighting_analysis, icon: SunMedium },
    { key: "style", label: "画面风格", value: data.visual_style, icon: Palette }
  ];
  const timeline = data.timeline_visual_analysis ?? [];
  const evidence = data.visual_evidence ?? [];
  if (!summaries.some((item) => item.value) && !timeline.length && !evidence.length) return null;

  return (
    <div className="viral-visual-analysis" aria-label="画面分析">
      <div className="viral-visual-summary-grid">
        {summaries.map(({ key, label, value, icon: Icon }) => value ? (
          <article className="viral-visual-summary" key={key}>
            <h3><Icon size={17} aria-hidden="true" />{label}</h3>
            <p>{value}</p>
          </article>
        ) : null)}
      </div>

      {timeline.length ? (
        <article className="viral-result-section viral-visual-timeline-section">
          <h3><Clock3 size={16} aria-hidden="true" />分时段画面分析</h3>
          <div className="viral-visual-timeline">
            {timeline.map((segment, index) => (
              <div className="viral-visual-segment" key={`${segment.time_range}-${index}`}>
                <div className="viral-visual-segment-meta">
                  <strong>{segment.time_range}</strong>
                  <span className={`viral-evidence-badge ${segment.evidence_type}`}>
                    {evidenceLabels[segment.evidence_type]}
                  </span>
                  <span className={`viral-confidence-badge ${segment.confidence}`}>
                    {confidenceLabels[segment.confidence]}
                  </span>
                </div>
                <dl>
                  {segment.setting ? <div><dt>布景</dt><dd>{segment.setting}</dd></div> : null}
                  {segment.lighting ? <div><dt>光影</dt><dd>{segment.lighting}</dd></div> : null}
                  {segment.visual_style ? <div><dt>风格</dt><dd>{segment.visual_style}</dd></div> : null}
                </dl>
                <p><Eye size={14} aria-hidden="true" /><span>可见依据</span>{segment.visible_evidence}</p>
              </div>
            ))}
          </div>
        </article>
      ) : null}

      {evidence.length ? (
        <article className="viral-result-section viral-evidence-section">
          <h3><Lightbulb size={16} aria-hidden="true" />可信度和可见依据</h3>
          <div className="viral-evidence-list">
            {evidence.map((item, index) => (
              <div className="viral-evidence-item" key={`${item.conclusion}-${index}`}>
                <div>
                  <span className={`viral-evidence-badge ${item.evidence_type}`}>
                    {evidenceLabels[item.evidence_type]}
                  </span>
                  <span className={`viral-confidence-badge ${item.confidence}`}>
                    {confidenceLabels[item.confidence]}
                  </span>
                </div>
                <strong>{item.conclusion}</strong>
                <p><Eye size={14} aria-hidden="true" />{item.visible_evidence}</p>
              </div>
            ))}
          </div>
        </article>
      ) : null}
    </div>
  );
}
