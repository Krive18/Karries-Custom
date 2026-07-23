import { Archive, Plus, X } from "lucide-react";

import type {
  InspirationGoalType,
  InspirationSession,
  InspirationSessionCreate
} from "../../types";

export type InspirationSessionDraft = InspirationSessionCreate;

type InspirationContextPanelProps = {
  draft: InspirationSessionDraft;
  session: InspirationSession | null;
  isCreating: boolean;
  isOpen: boolean;
  onDraftChange: (draft: InspirationSessionDraft) => void;
  onCreate: () => void;
  onClose: () => void;
  onArchive: () => void;
};

const goalOptions: Array<{ value: InspirationGoalType; label: string }> = [
  { value: "topic", label: "选题策划" },
  { value: "title", label: "标题优化" },
  { value: "body", label: "正文创作" },
  { value: "script", label: "视频脚本" },
  { value: "strategy", label: "运营策略" },
  { value: "optimize", label: "内容优化" }
];

function toOptionalId(value: string) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

export function InspirationContextPanel({
  draft,
  session,
  isCreating,
  isOpen,
  onDraftChange,
  onCreate,
  onClose,
  onArchive
}: InspirationContextPanelProps) {
  if (!isOpen && session) {
    return (
      <aside className="inspiration-context-panel" aria-label="会话上下文">
        <div className="panel-title">
          <h2>会话上下文</h2>
          <span className={`status-badge inspiration-status-${session.status}`}>
            {session.status === "archived" ? "已归档" : session.status === "generating" ? "生成中" : "进行中"}
          </span>
        </div>
        <dl className="context-summary-list">
          <div><dt>目标类型</dt><dd>{goalOptions.find((item) => item.value === session.goal_type)?.label ?? session.goal_type}</dd></div>
          <div><dt>文案语气</dt><dd>{session.tone}</dd></div>
          <div><dt>产品 ID</dt><dd>{session.linked_product_id || "未关联"}</dd></div>
          <div><dt>账号 ID</dt><dd>{session.linked_xhs_account_id || "未关联"}</dd></div>
          <div className="wide"><dt>补充要求</dt><dd>{session.extra_requirement || "无"}</dd></div>
        </dl>
        {session.status === "active" ? (
          <button className="quiet-danger compact" type="button" onClick={onArchive}>
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
        <h2>新建会话</h2>
        <button className="icon-button compact-icon" type="button" aria-label="关闭新建会话" onClick={onClose}>
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="form-grid single">
        <label>
          会话标题
          <input value={draft.title} onChange={(event) => onDraftChange({ ...draft, title: event.target.value })} placeholder="例如：新品夏季种草选题" />
        </label>
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
        <div className="context-id-grid">
          <label>
            产品 ID（可选）
            <input type="number" min="0" value={draft.linked_product_id || ""} onChange={(event) => onDraftChange({ ...draft, linked_product_id: toOptionalId(event.target.value) })} />
          </label>
          <label>
            小红书账号 ID（可选）
            <input type="number" min="0" value={draft.linked_xhs_account_id || ""} onChange={(event) => onDraftChange({ ...draft, linked_xhs_account_id: toOptionalId(event.target.value) })} />
          </label>
        </div>
        <label>
          补充要求
          <textarea rows={4} value={draft.extra_requirement} onChange={(event) => onDraftChange({ ...draft, extra_requirement: event.target.value })} placeholder="例如：突出门店体验，避免硬性促销表达" />
        </label>
      </div>
      <button className="primary-button" type="button" disabled={isCreating} onClick={onCreate}>
        <Plus size={17} aria-hidden="true" />
        {isCreating ? "创建中" : "创建会话"}
      </button>
    </aside>
  );
}
