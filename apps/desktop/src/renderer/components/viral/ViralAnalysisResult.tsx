import { CheckCircle2, FileText, Lightbulb, ListTree, Sparkles, Tags } from "lucide-react";

import type { ViralAnalysisResult as ViralResult } from "../../types";

type ViralAnalysisResultProps = {
  result: ViralResult | null | undefined;
  emptyText?: string;
};

const sections: Array<{
  key: keyof Pick<ViralResult, "hook_summary" | "structure_summary" | "shot_rhythm" | "script_breakdown" | "selling_points" | "reuse_suggestions" | "rewritten_script">;
  label: string;
  icon: typeof Sparkles;
}> = [
  { key: "hook_summary", label: "开场钩子", icon: Sparkles },
  { key: "structure_summary", label: "内容结构", icon: ListTree },
  { key: "shot_rhythm", label: "节奏建议", icon: CheckCircle2 },
  { key: "script_breakdown", label: "脚本拆解", icon: FileText },
  { key: "selling_points", label: "卖点提炼", icon: Lightbulb },
  { key: "reuse_suggestions", label: "复用建议", icon: Lightbulb },
  { key: "rewritten_script", label: "改写脚本", icon: FileText }
];

export function ViralAnalysisResult({ result, emptyText = "完成解析后，这里会显示结构化结果。" }: ViralAnalysisResultProps) {
  if (!result) return <div className="empty-list-state viral-result-empty">{emptyText}</div>;

  return (
    <section className="viral-result" aria-label="爆款解析结果">
      {sections.map(({ key, label, icon: Icon }) => result[key] ? (
        <article className="viral-result-section" key={key}>
          <h3><Icon size={16} aria-hidden="true" />{label}</h3>
          <p>{result[key]}</p>
        </article>
      ) : null)}
      <div className="viral-tags"><Tags size={16} aria-hidden="true" />{result.tags.map((tag) => <span key={tag}>#{tag.replace(/^#/, "")}</span>)}</div>
    </section>
  );
}
