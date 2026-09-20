import { useEffect, useMemo, useState } from "react";
import { Check, Copy, Edit3, Save, Tags, Trash2, X } from "lucide-react";

import type { ContentCollection, ContentCollectionUpdate } from "../../types";
import {
  ViralVisualAnalysis,
  visualAnalysisPlainText
} from "../viral/ViralVisualAnalysis";
import { RichContentReader } from "../content/RichContentReader";


type ContentCollectionDetailProps = {
  item: ContentCollection;
  isSaving: boolean;
  onSave: (payload: ContentCollectionUpdate) => Promise<boolean>;
  onCopy: (text: string, label: string) => Promise<void>;
  onDelete: () => Promise<void>;
};

const detailSections: Array<{
  key: keyof Pick<
    ContentCollection,
    | "hook_summary"
    | "structure_summary"
    | "shot_rhythm"
    | "selling_points"
    | "reuse_suggestions"
  >;
  label: string;
}> = [
  { key: "hook_summary", label: "开场钩子" },
  { key: "structure_summary", label: "内容结构" },
  { key: "shot_rhythm", label: "镜头节奏" },
  { key: "selling_points", label: "卖点表达" },
  { key: "reuse_suggestions", label: "复用建议" }
];

function fullDraftText(item: ContentCollection) {
  if (item.source_type === "inspiration") {
    return [
      `标题：${item.title}`,
      `AI 对话内容：\n${item.rewritten_script}`,
      `标签：${item.tags.map((tag) => `#${tag.replace(/^#/, "")}`).join(" ")}`
    ].filter((value) => !value.endsWith("：\n") && !value.endsWith("：")).join("\n\n");
  }
  return [
    `标题：${item.title}`,
    ...detailSections.map(({ key, label }) => `${label}：\n${item[key]}`).filter((value) => value.trim()),
    item.original_transcript ? `原视频字幕脚本：\n${item.original_transcript}` : "",
    item.transcript_analysis ? `字幕脚本分析：\n${item.transcript_analysis}` : "",
    visualAnalysisPlainText(item),
    `改写脚本：\n${item.rewritten_script}`,
    `脚本拆解与分镜：\n${item.script_breakdown}`,
    `标签：${item.tags.map((tag) => `#${tag.replace(/^#/, "")}`).join(" ")}`
  ].filter((value) => !value.endsWith("：\n") && !value.endsWith("：")).join("\n\n");
}

function formatTime(timestamp: number) {
  if (!timestamp) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}

export function ContentCollectionDetail({
  item,
  isSaving,
  onSave,
  onCopy,
  onDelete
}: ContentCollectionDetailProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(item.title);
  const [rewrittenScript, setRewrittenScript] = useState(item.rewritten_script);
  const [scriptBreakdown, setScriptBreakdown] = useState(item.script_breakdown);
  const [tagText, setTagText] = useState(item.tags.join(", "));

  useEffect(() => {
    setIsEditing(false);
    setTitle(item.title);
    setRewrittenScript(item.rewritten_script);
    setScriptBreakdown(item.script_breakdown);
    setTagText(item.tags.join(", "));
  }, [item]);

  const parsedTags = useMemo(() => Array.from(new Set(
    tagText
      .split(/[,，\n]/)
      .map((tag) => tag.trim().replace(/^#/, ""))
      .filter(Boolean)
  )).slice(0, 20), [tagText]);

  async function saveChanges() {
    if (!title.trim()) return;
    const payload: ContentCollectionUpdate = {
      title: title.trim(),
      rewritten_script: rewrittenScript.trim(),
      tags: parsedTags
    };
    if (item.source_type !== "inspiration") {
      payload.script_breakdown = scriptBreakdown.trim();
    }
    const saved = await onSave(payload);
    if (saved) setIsEditing(false);
  }

  if (isEditing) {
    return (
      <div className="collection-editor" aria-label="编辑收藏稿">
        <header className="collection-detail-header">
          <div>
            <span>收藏稿 #{item.id}</span>
            <h2>编辑收藏内容</h2>
            <p>仅更新收藏内容，不会触发 AI 调用、发布任务或算力扣除。</p>
          </div>
          <button className="secondary-button" type="button" disabled={isSaving} onClick={() => setIsEditing(false)}>
            <X size={16} aria-hidden="true" />取消编辑
          </button>
        </header>
        <div className="collection-edit-fields">
          <label>
            收藏稿标题
            <input aria-label="收藏稿标题" value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            {item.source_type === "inspiration" ? "AI 对话内容" : "改写脚本"}
            <textarea
              aria-label={item.source_type === "inspiration" ? "AI 对话内容" : "改写脚本"}
              value={rewrittenScript}
              maxLength={10000}
              onChange={(event) => setRewrittenScript(event.target.value)}
            />
          </label>
          {item.source_type !== "inspiration" ? (
            <label>
              脚本拆解与分镜
              <textarea aria-label="脚本拆解与分镜" value={scriptBreakdown} maxLength={10000} onChange={(event) => setScriptBreakdown(event.target.value)} />
            </label>
          ) : null}
          <label>
            标签
            <input aria-label="标签" value={tagText} maxLength={2000} placeholder="使用逗号分隔，最多 20 个" onChange={(event) => setTagText(event.target.value)} />
            <small>已识别 {parsedTags.length} 个标签</small>
          </label>
        </div>
        <div className="collection-editor-actions">
          <button className="primary-button" type="button" disabled={isSaving || !title.trim()} onClick={() => void saveChanges()}>
            {isSaving ? "保存中..." : <><Save size={16} aria-hidden="true" />保存修改</>}
          </button>
        </div>
      </div>
    );
  }

  return (
    <article className="collection-detail">
      <header className="collection-detail-header">
        <div>
          <span>{item.source_type === "inspiration" ? "来自 Karries AI · 消息" : "来自爆款解析 · 任务"} #{item.source_id}</span>
          <h2>{item.title}</h2>
          <p>收藏于 {formatTime(item.create_time)} · 最近更新 {formatTime(item.update_time)}</p>
        </div>
        <div className="collection-header-actions">
          <button className="danger-button" type="button" disabled={isSaving} onClick={() => void onDelete()}>
            <Trash2 size={16} aria-hidden="true" />删除收藏
          </button>
          <button className="secondary-button" type="button" onClick={() => void onCopy(fullDraftText(item), "完整草稿")}>
            <Copy size={16} aria-hidden="true" />复制完整草稿
          </button>
          <button className="primary-button" type="button" onClick={() => setIsEditing(true)}>
            <Edit3 size={16} aria-hidden="true" />编辑收藏稿
          </button>
        </div>
      </header>

      {item.source_type === "inspiration" ? (
        <RichContentReader
          title="AI 对话内容"
          content={item.rewritten_script}
          emptyText="暂无 AI 对话内容"
          variant="assistant"
          onCopy={(text) => onCopy(text, "AI 对话内容")}
        />
      ) : (
        <>
          <div className="collection-section-grid">
            {detailSections.map(({ key, label }) => item[key] ? (
              <section className="collection-section" key={key}>
                <header>
                  <h3><Check size={16} aria-hidden="true" />{label}</h3>
                  <button type="button" aria-label={`复制${label}`} onClick={() => void onCopy(item[key], label)}>
                    <Copy size={15} aria-hidden="true" />
                  </button>
                </header>
                <p>{item[key]}</p>
              </section>
            ) : null)}
          </div>

          {item.original_transcript ? (
            <RichContentReader
              title="原视频字幕脚本"
              content={item.original_transcript}
              emptyText="暂无原视频字幕脚本"
              variant="script"
              onCopy={(text) => onCopy(text, "原视频字幕脚本")}
            />
          ) : null}
          {item.transcript_analysis ? (
            <RichContentReader
              title="字幕脚本分析"
              content={item.transcript_analysis}
              emptyText="暂无字幕脚本分析"
              variant="assistant"
              onCopy={(text) => onCopy(text, "字幕脚本分析")}
            />
          ) : null}

          <ViralVisualAnalysis data={item} />

          <RichContentReader
            title="改写脚本"
            content={item.rewritten_script}
            emptyText="暂无改写脚本"
            variant="script"
            onCopy={(text) => onCopy(text, "改写脚本")}
          />
          <RichContentReader
            title="脚本拆解与分镜"
            content={item.script_breakdown}
            emptyText="暂无脚本拆解"
            variant="script"
            onCopy={(text) => onCopy(text, "脚本拆解与分镜")}
          />
        </>
      )}
      <footer className="collection-tags">
        <Tags size={16} aria-hidden="true" />
        <div>{item.tags.length ? item.tags.map((tag) => <span key={tag}>#{tag.replace(/^#/, "")}</span>) : <small>暂无标签</small>}</div>
        {item.tags.length ? <button type="button" onClick={() => void onCopy(item.tags.map((tag) => `#${tag.replace(/^#/, "")}`).join(" "), "标签")}><Copy size={15} aria-hidden="true" />复制标签</button> : null}
      </footer>
    </article>
  );
}
