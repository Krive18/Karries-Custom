import { useCallback, useEffect, useState } from "react";
import { Lightbulb, Plus, RefreshCw } from "lucide-react";

import { ApiRequestError, api } from "../api/client";
import {
  InspirationContextPanel,
  type InspirationSessionDraft
} from "../components/inspiration/InspirationContextPanel";
import { InspirationMessages } from "../components/inspiration/InspirationMessages";
import type {
  InspirationMessage,
  InspirationSession,
  InspirationSessionDetail
} from "../types";

const initialDraft: InspirationSessionDraft = {
  title: "",
  linked_product_id: 0,
  linked_xhs_account_id: 0,
  goal_type: "topic",
  tone: "自然真诚",
  extra_requirement: ""
};

function explainError(error: unknown) {
  if (error instanceof ApiRequestError) {
    if (error.code === "SESSION_GENERATING") return "上一条建议正在生成，请稍后再试。";
    if (error.code === "SESSION_ARCHIVED") return "会话已经归档，不能继续发送消息。";
    if (error.code === "AI_PROVIDER_ERROR") return "灵感服务暂时无法响应，请稍后重试。";
  }
  return error instanceof Error ? error.message : "操作未完成，请稍后重试。";
}

export function InspirationPage() {
  const [sessions, setSessions] = useState<InspirationSession[]>([]);
  const [detail, setDetail] = useState<InspirationSessionDetail | null>(null);
  const [isListLoading, setIsListLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isNewSessionOpen, setIsNewSessionOpen] = useState(false);
  const [sessionDraft, setSessionDraft] = useState(initialDraft);
  const [messageDraft, setMessageDraft] = useState("");
  const [savedMessageIds, setSavedMessageIds] = useState<Set<number>>(new Set());
  const [message, setMessage] = useState("");

  const loadSessions = useCallback(async () => {
    setIsListLoading(true);
    try {
      const result = await api.listInspirationSessions();
      setSessions(result.items);
      setMessage("");
      if (detail && !result.items.some((item) => item.id === detail.session.id)) setDetail(null);
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsListLoading(false);
    }
  }, [detail]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const selectSession = useCallback(async (sessionId: number) => {
    setIsDetailLoading(true);
    try {
      setDetail(await api.getInspirationSession(sessionId));
      setMessage("");
      setIsNewSessionOpen(false);
      setMessageDraft("");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsDetailLoading(false);
    }
  }, []);

  async function createSession() {
    if (!sessionDraft.title.trim()) {
      setMessage("请先填写会话标题。");
      return;
    }
    setIsCreating(true);
    try {
      const created = await api.createInspirationSession({ ...sessionDraft, title: sessionDraft.title.trim() });
      setSessions((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setDetail({ session: created, messages: [] });
      setIsNewSessionOpen(false);
      setSessionDraft(initialDraft);
      setMessage("会话已创建，可以开始提问。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsCreating(false);
    }
  }

  async function sendMessage() {
    if (!detail || !messageDraft.trim()) return;
    setIsSending(true);
    try {
      const response = await api.sendInspirationMessage(detail.session.id, { content: messageDraft.trim() });
      const nextMessages: InspirationMessage[] = [...detail.messages, response.user_message, response.assistant_message];
      const nextSession = {
        ...detail.session,
        status: "active" as const,
        message_count: nextMessages.length,
        total_credit_cost: detail.session.total_credit_cost + response.credit_cost
      };
      setDetail({ session: nextSession, messages: nextMessages });
      setSessions((current) => current.map((item) => item.id === nextSession.id ? nextSession : item));
      setMessageDraft("");
      setMessage("");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsSending(false);
    }
  }

  async function archiveSession() {
    if (!detail) return;
    try {
      const archived = await api.archiveInspirationSession(detail.session.id);
      setDetail((current) => current ? { ...current, session: archived } : current);
      setSessions((current) => current.map((item) => item.id === archived.id ? archived : item));
      setMessage("会话已归档。");
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  async function saveDraft(messageId: number) {
    try {
      await api.saveInspirationMessageDraft(messageId);
      setSavedMessageIds((current) => new Set([...current, messageId]));
      setMessage("已保存为内容草稿。");
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  return (
    <section className="page-stack inspiration-page">
      <div className="page-heading horizontal-heading">
        <div>
          <h1>灵感对话</h1>
          <p>围绕产品、账号定位和运营目标连续讨论，生成可继续编辑的内容思路。</p>
        </div>
        <div className="heading-actions">
          <button className="secondary-button compact" type="button" onClick={() => void loadSessions()}>
            <RefreshCw size={16} aria-hidden="true" />刷新
          </button>
          <button className="primary-button compact" type="button" onClick={() => setIsNewSessionOpen(true)}>
            <Plus size={17} aria-hidden="true" />新建会话
          </button>
        </div>
      </div>
      {message ? <div className="form-message" role="status">{message}</div> : null}
      <div className="inspiration-workspace">
        <aside className="inspiration-session-panel" aria-label="会话列表">
          <div className="panel-title"><h2><Lightbulb size={18} aria-hidden="true" />会话</h2><span>{sessions.length}</span></div>
          {isListLoading ? <div className="inspiration-session-skeleton" aria-label="正在加载会话"><span /><span /><span /></div> : null}
          {!isListLoading && sessions.length === 0 ? <div className="empty-list-state">暂无会话，点击“新建会话”开始。</div> : null}
          {!isListLoading ? <div className="inspiration-session-list">
            {sessions.map((session) => <button key={session.id} type="button" className={detail?.session.id === session.id ? "inspiration-session-item active" : "inspiration-session-item"} onClick={() => void selectSession(session.id)}>
              <strong>{session.title}</strong>
              <span>{session.status === "archived" ? "已归档" : session.status === "generating" ? "生成中" : "进行中"} · {session.total_credit_cost} 算力</span>
            </button>)}
          </div> : null}
        </aside>
        <InspirationMessages session={detail?.session ?? null} messages={detail?.messages ?? []} draftMessage={messageDraft} isLoading={isDetailLoading} isSending={isSending} savedMessageIds={savedMessageIds} onDraftMessageChange={setMessageDraft} onSend={() => void sendMessage()} onSaveDraft={(messageId) => void saveDraft(messageId)} />
        <InspirationContextPanel draft={sessionDraft} session={detail?.session ?? null} isCreating={isCreating} isOpen={isNewSessionOpen || !detail} onDraftChange={setSessionDraft} onCreate={() => void createSession()} onClose={() => setIsNewSessionOpen(false)} onArchive={() => void archiveSession()} />
      </div>
    </section>
  );
}
