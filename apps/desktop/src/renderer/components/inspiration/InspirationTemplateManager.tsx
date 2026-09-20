import { Copy, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import type {
  InspirationPersonalizationTemplate,
  InspirationPersonalizationTemplateUpdate
} from "../../types";


const blankTemplate: InspirationPersonalizationTemplateUpdate = {
  template_name: "",
  assistant_name: "Karries AI",
  assistant_traits: "专业、耐心、务实",
  preferred_address: "",
  occupation: "",
  user_details: "",
  response_preferences: "回答清晰、准确，并优先给出可执行的建议"
};

export function InspirationTemplateManager({
  templates,
  isSaving,
  onClose,
  onCreate,
  onUpdate,
  onDuplicate,
  onArchive
}: {
  templates: InspirationPersonalizationTemplate[];
  isSaving: boolean;
  onClose: () => void;
  onCreate: (payload: InspirationPersonalizationTemplateUpdate) => Promise<void>;
  onUpdate: (templateId: number, payload: InspirationPersonalizationTemplateUpdate) => Promise<void>;
  onDuplicate: (templateId: number) => Promise<void>;
  onArchive: (templateId: number) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState(blankTemplate);

  useEffect(() => {
    if (editingId === null) return;
    const template = templates.find((item) => item.id === editingId);
    if (!template) {
      setEditingId(null);
      setDraft(blankTemplate);
    }
  }, [editingId, templates]);

  function edit(template: InspirationPersonalizationTemplate) {
    setEditingId(template.id);
    setDraft({
      template_name: template.template_name,
      assistant_name: template.assistant_name,
      assistant_traits: template.assistant_traits,
      preferred_address: template.preferred_address,
      occupation: template.occupation,
      user_details: template.user_details,
      response_preferences: template.response_preferences
    });
  }

  async function save() {
    const payload = Object.fromEntries(
      Object.entries(draft).map(([key, value]) => [key, value.trim()])
    ) as InspirationPersonalizationTemplateUpdate;
    if (!payload.template_name || !payload.assistant_name) return;
    if (editingId === null) await onCreate(payload);
    else await onUpdate(editingId, payload);
    setEditingId(null);
    setDraft(blankTemplate);
  }

  return (
    <section className="personalization-dialog template-manager-dialog" role="dialog" aria-modal="true" aria-labelledby="template-manager-title">
      <header>
        <div>
          <h2 id="template-manager-title">个性化模板</h2>
          <p>为不同角色保存独立的身份和回答偏好；每个模板拥有自己的历史会话。</p>
        </div>
        <button className="icon-button compact-icon" type="button" aria-label="关闭个性化模板" disabled={isSaving} onClick={onClose}>
          <X size={17} aria-hidden="true" />
        </button>
      </header>
      <div className="template-manager-body">
        <aside className="template-manager-list" aria-label="模板列表">
          <button className="secondary-button" type="button" onClick={() => { setEditingId(null); setDraft(blankTemplate); }}>
            <Plus size={15} aria-hidden="true" />新建模板
          </button>
          {templates.filter((template) => template.status === "active").map((template) => (
            <div className={editingId === template.id ? "template-manager-item active" : "template-manager-item"} key={template.id}>
              <button type="button" onClick={() => edit(template)}>
                <strong>{template.template_name}</strong>
                <span>{template.assistant_name}</span>
              </button>
              <div>
                <button type="button" aria-label={`编辑模板 ${template.template_name}`} onClick={() => edit(template)}><Pencil size={14} /></button>
                <button type="button" aria-label={`复制模板 ${template.template_name}`} onClick={() => void onDuplicate(template.id)}><Copy size={14} /></button>
                <button type="button" aria-label={`归档模板 ${template.template_name}`} onClick={() => void onArchive(template.id)}><Trash2 size={14} /></button>
              </div>
            </div>
          ))}
          {templates.filter((template) => template.status === "active").length === 0 ? <p>还没有模板，先创建第一个角色。</p> : null}
        </aside>
        <div className="personalization-form template-editor-form">
          <label>模板名称<input autoFocus maxLength={100} value={draft.template_name} onChange={(event) => setDraft((current) => ({ ...current, template_name: event.target.value }))} placeholder="例如：品牌运营顾问" /></label>
          <label>AI 名称<input maxLength={50} value={draft.assistant_name} onChange={(event) => setDraft((current) => ({ ...current, assistant_name: event.target.value }))} placeholder="例如：小禾" /></label>
          <label className="full-width">AI 性格特征<input maxLength={500} value={draft.assistant_traits} onChange={(event) => setDraft((current) => ({ ...current, assistant_traits: event.target.value }))} placeholder="例如：专业、直接、善于追问" /></label>
          <label>如何称呼你<input maxLength={50} value={draft.preferred_address} onChange={(event) => setDraft((current) => ({ ...current, preferred_address: event.target.value }))} /></label>
          <label>职业或身份<input maxLength={100} value={draft.occupation} onChange={(event) => setDraft((current) => ({ ...current, occupation: event.target.value }))} /></label>
          <label className="full-width">希望 AI 记住的详情<textarea rows={3} maxLength={2000} value={draft.user_details} onChange={(event) => setDraft((current) => ({ ...current, user_details: event.target.value }))} /></label>
          <label className="full-width">回答偏好<textarea rows={3} maxLength={1000} value={draft.response_preferences} onChange={(event) => setDraft((current) => ({ ...current, response_preferences: event.target.value }))} /></label>
        </div>
      </div>
      <footer>
        <span>{editingId === null ? "创建后可立即选择此模板开始对话。" : "修改只影响后续回答，不覆盖历史消息。"}</span>
        <div>
          <button className="secondary-button" type="button" disabled={isSaving} onClick={onClose}>取消</button>
          <button className="primary-button" type="button" disabled={isSaving || !draft.template_name.trim() || !draft.assistant_name.trim()} onClick={() => void save()}>
            {isSaving ? <Loader2 size={16} className="spin" aria-hidden="true" /> : null}
            {isSaving ? "保存中" : editingId === null ? "创建模板" : "保存模板"}
          </button>
        </div>
      </footer>
    </section>
  );
}
