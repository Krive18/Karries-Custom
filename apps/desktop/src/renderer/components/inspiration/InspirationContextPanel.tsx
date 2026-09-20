import { Archive, Plus, Target, X } from "lucide-react";

import type {
  InspirationGoalType,
  InspirationSession,
  InspirationSessionCreate,
  MaterialFolder
} from "../../types";

export type InspirationSessionDraft = InspirationSessionCreate;

type InspirationContextPanelProps = {
  draft: InspirationSessionDraft;
  session: InspirationSession | null;
  isCreating: boolean;
  isArchiveDisabled: boolean;
  isOpen: boolean;
  productFolders: MaterialFolder[];
  conversationSpaceLabel?: string;
  onDraftChange: (draft: InspirationSessionDraft) => void;
  onCreate: () => void;
  onClose: () => void;
  onArchive: () => void;
};

const goalOptions: Array<{ value: InspirationGoalType; label: string }> = [
  { value: "general", label: "通用大模型对话" },
  { value: "topic", label: "选题策划" },
  { value: "title", label: "标题优化" },
  { value: "body", label: "正文创作" },
  { value: "script", label: "视频脚本" },
  { value: "strategy", label: "运营策略" },
  { value: "optimize", label: "内容优化" }
];

export function InspirationContextPanel({
  draft,
  session,
  isCreating,
  isArchiveDisabled,
  isOpen,
  productFolders,
  conversationSpaceLabel,
  onDraftChange,
  onCreate,
  onClose,
  onArchive
}: InspirationContextPanelProps) {
  const linkedProductName = productFolders.find(
    (folder) => folder.id === session?.linked_product_id
  )?.folder_name;

  if (!isOpen && !session) {
    return null;
  }

  if (!isOpen && session) {
    return (
      <aside className="inspiration-context-panel" aria-label="会话上下文">
        <div className="panel-title">
          <h2><Target size={17} aria-hidden="true" />创作上下文</h2>
          <div className="inspiration-context-panel-actions">
            <span className={`status-badge inspiration-status-${session.status}`}>
              {session.status === "archived" ? "已归档" : session.status === "generating" ? "生成中" : "进行中"}
            </span>
            <button className="icon-button compact-icon" type="button" aria-label="关闭创作上下文" onClick={onClose}>
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
        <dl className="context-summary-list">
          <div className="wide">
            <dt>交互模式</dt>
            <dd>{conversationSpaceLabel ?? (session.interaction_mode === "normal" ? "普通对话" : "个性化模板")}</dd>
          </div>
          <div><dt>目标类型</dt><dd>{goalOptions.find((item) => item.value === session.goal_type)?.label ?? session.goal_type}</dd></div>
          <div><dt>文案语气</dt><dd>{session.tone}</dd></div>
          <div className="wide">
            <dt>关联产品资料</dt>
            <dd>{session.linked_product_id ? linkedProductName ?? "已关联产品资料" : "未关联"}</dd>
          </div>
          <div className="wide"><dt>补充要求</dt><dd>{session.extra_requirement || "无"}</dd></div>
        </dl>
        {session.status === "active" ? (
          <button className="quiet-danger compact" type="button" disabled={isArchiveDisabled} onClick={onArchive}>
            <Archive size={16} aria-hidden="true" />
            归档会话
          </button>
        ) : null}
      </aside>
    );
  }

  return (
    <aside className="inspiration-context-panel" aria-label="新建会话">
      <div className="panel-title">
        <h2><Plus size={17} aria-hidden="true" />新建会话</h2>
        <button className="icon-button compact-icon" type="button" aria-label="关闭新建会话" onClick={onClose}>
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="inspiration-dialog-space">
        <span>对话模式</span>
        <strong>{conversationSpaceLabel ?? (draft.interaction_mode === "normal" ? "普通对话" : "个性化模板")}</strong>
      </div>
      <div className="form-grid single">
        <label>
          会话标题
          <input value={draft.title} onChange={(event) => onDraftChange({ ...draft, title: event.target.value })} placeholder="例如：新品夏季种草选题" />
        </label>
        {draft.interaction_mode === "personalized" ? (
          <>
            <label>
              目标类型
              <select value={draft.goal_type} onChange={(event) => onDraftChange({ ...draft, goal_type: event.target.value as InspirationGoalType })}>
                {goalOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label>
              文案语气
              <select value={draft.tone} onChange={(event) => onDraftChange({ ...draft, tone: event.target.value })}>
                <option value="自然真诚">自然真诚</option>
                <option value="精致高级">精致高级</option>
                <option value="轻松活泼">轻松活泼</option>
              </select>
            </label>
            <label>
              关联产品资料（可选）
              <select
                aria-label="关联产品资料（可选）"
                value={draft.linked_product_id || 0}
                onChange={(event) => onDraftChange({ ...draft, linked_product_id: Number(event.target.value), linked_xhs_account_id: 0 })}
              >
                <option value={0}>不关联产品资料</option>
                {productFolders.map((folder) => <option key={folder.id} value={folder.id}>{folder.folder_name}</option>)}
              </select>
              <small>来自产品知识库，可帮助 AI 按指定产品持续回答。</small>
            </label>
            <label>
              补充要求
              <textarea rows={4} value={draft.extra_requirement} onChange={(event) => onDraftChange({ ...draft, extra_requirement: event.target.value })} placeholder="例如：突出门店体验，避免硬性促销表达" />
            </label>
          </>
        ) : <p className="inspiration-general-note">普通对话不会加载产品资料、创作目标或个性化角色。</p>}
      </div>
      <button className="primary-button" type="button" disabled={isCreating} onClick={onCreate}>
        <Plus size={17} aria-hidden="true" />
        {isCreating ? "创建中" : "创建会话"}
      </button>
    </aside>
  );
}
