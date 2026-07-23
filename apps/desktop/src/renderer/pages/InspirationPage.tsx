import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Lightbulb, Plus, RefreshCw } from "lucide-react";

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

const pageSize = 20;
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
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isListLoading, setIsListLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [sendingSessionId, setSendingSessionId] = useState<number | null>(null);
  const [isNewSessionOpen, setIsNewSessionOpen] = useState(false);
  const [sessionDraft, setSessionDraft] = useState(initialDraft);
  const [messageDraft, setMessageDraft] = useState("");
  const [message, setMessage] = useState("");
  const listRequestRef = useRef(0);
  const detailRequestRef = useRef(0);
  const sendRequestRef = useRef(0);
  const pendingMessageRequestRef = useRef<{
    sessionId: number;
    content: string;
    clientRequestId: string;
  } | null>(null);
  const selectedSessionIdRef = useRef<number | null>(null);

  const loadSessions = useCallback(async (requestedPage = 1) => {
    const requestId = ++listRequestRef.current;
    setIsListLoading(true);
    try {
      const result = await api.listInspirationSessions(new URLSearchParams({
        page: String(requestedPage),
        page_size: String(pageSize)
      }));
      if (requestId !== listRequestRef.current) return;
      if (result.items.length === 0 && result.total > 0 && requestedPage > 1) {
        void loadSessions(requestedPage - 1);
        return;
      }
      setSessions(result.items);
      setPage(result.page);
      setTotal(result.total);
      setMessage("");
    } catch (error) {
      if (requestId === listRequestRef.current) setMessage(explainError(error));
    } finally {
      if (requestId === listRequestRef.current) setIsListLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const selectSession = useCallback(async (sessionId: number) => {
    const requestId = ++detailRequestRef.current;
    selectedSessionIdRef.current = sessionId;
    setIsDetailLoading(true);
    setIsNewSessionOpen(false);
    setMessageDraft("");
    try {
      const nextDetail = await api.getInspirationSession(sessionId);
      if (requestId !== detailRequestRef.current || selectedSessionIdRef.current !== sessionId) return;
      setDetail(nextDetail);
      setMessage("");
    } catch (error) {
      if (requestId === detailRequestRef.current && selectedSessionIdRef.current === sessionId) {
        setMessage(explainError(error));
      }
    } finally {
      if (requestId === detailRequestRef.current) setIsDetailLoading(false);
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
      selectedSessionIdRef.current = created.id;
      setSessions((current) => [created, ...current.filter((item) => item.id !== created.id)].slice(0, pageSize));
      setDetail({ session: created, messages: [] });
      setPage(1);
      setTotal((current) => current + 1);
      setIsNewSessionOpen(false);
      setSessionDraft(initialDraft);
      setMessage("会话已创建，可以开始提问。");
      void loadSessions(1);
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsCreating(false);
    }
  }

  async function sendMessage() {
    if (!detail || !messageDraft.trim()) return;
    const session = detail.session;
    const requestId = ++sendRequestRef.current;
    const content = messageDraft.trim();
    const pendingRequest = pendingMessageRequestRef.current;
    const clientRequestId = pendingRequest?.sessionId === session.id
      && pendingRequest.content === content
      ? pendingRequest.clientRequestId
      : globalThis.crypto.randomUUID();
    pendingMessageRequestRef.current = {
      sessionId: session.id,
      content,
      clientRequestId
    };
    setSendingSessionId(session.id);
    try {
      const response = await api.sendInspirationMessage(session.id, {
        content,
        client_request_id: clientRequestId
      });
      const nextSession = {
        ...session,
        status: "active" as const,
        message_count: session.message_count + 2,
        total_credit_cost: session.total_credit_cost + response.credit_cost
      };
      setSessions((current) => current.map((item) => item.id === session.id ? nextSession : item));
      if (requestId !== sendRequestRef.current || selectedSessionIdRef.current !== session.id) return;
      setDetail((current) => {
        if (!current || current.session.id !== session.id) return current;
        const nextMessages: InspirationMessage[] = [...current.messages, response.user_message, response.assistant_message];
        return { session: nextSession, messages: nextMessages };
      });
      setMessageDraft("");
      pendingMessageRequestRef.current = null;
      setMessage("");
    } catch (error) {
      if (requestId === sendRequestRef.current && selectedSessionIdRef.current === session.id) {
        setMessage(explainError(error));
      }
    } finally {
      if (requestId === sendRequestRef.current) setSendingSessionId(null);
    }
  }

  async function archiveSession() {
    if (!detail || sendingSessionId === detail.session.id) return;
    const sessionId = detail.session.id;
    try {
      const archived = await api.archiveInspirationSession(sessionId);
      if (selectedSessionIdRef.current !== sessionId) return;
      setDetail((current) => current?.session.id === sessionId ? { ...current, session: archived } : current);
      setSessions((current) => current.map((item) => item.id === archived.id ? archived : item));
      setMessage("会话已归档。");
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  async function saveDraft(messageId: number) {
    try {
      const result = await api.saveInspirationMessageDraft(messageId);
      setDetail((current) => current ? {
        ...current,
        messages: current.messages.map((item) => item.id === messageId ? { ...item, content_draft_id: result.draft_id } : item)
      } : current);
      setMessage("已保存为内容草稿。");
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const selectedSession = detail?.session ?? null;
  return (
    <section className="page-stack inspiration-page">
      <div className="page-heading horizontal-heading">
        <div><h1>灵感对话</h1><p>围绕产品、账号定位和运营目标连续讨论，生成可继续编辑的内容思路。</p></div>
        <div className="heading-actions">
          <button className="secondary-button compact" type="button" onClick={() => void loadSessions(page)}><RefreshCw size={16} aria-hidden="true" />刷新</button>
          <button className="primary-button compact" type="button" onClick={() => setIsNewSessionOpen(true)}><Plus size={17} aria-hidden="true" />新建会话</button>
        </div>
      </div>
      {message ? <div className="form-message" role="status">{message}</div> : null}
      <div className="inspiration-workspace">
        <aside className="inspiration-session-panel" aria-label="会话列表">
          <div className="panel-title"><h2><Lightbulb size={18} aria-hidden="true" />会话</h2><span>{total} 条</span></div>
          {isListLoading ? <div className="inspiration-session-skeleton" aria-label="正在加载会话"><span /><span /><span /></div> : null}
          {!isListLoading && sessions.length === 0 ? <div className="empty-list-state">暂无会话，点击“新建会话”开始。</div> : null}
          {!isListLoading ? <div className="inspiration-session-list">{sessions.map((session) => <button key={session.id} type="button" className={selectedSession?.id === session.id ? "inspiration-session-item active" : "inspiration-session-item"} onClick={() => void selectSession(session.id)}><strong>{session.title}</strong><span>{session.status === "archived" ? "已归档" : session.status === "generating" ? "生成中" : "进行中"} · {session.total_credit_cost} 算力</span></button>)}</div> : null}
          <div className="inspiration-pagination" aria-label="会话分页"><button className="table-action compact" type="button" disabled={page <= 1 || isListLoading} onClick={() => void loadSessions(page - 1)}><ChevronLeft size={15} aria-hidden="true" />上一页</button><span>第 {page} 页 / 共 {total} 条</span><button className="table-action compact" type="button" disabled={page >= pageCount || isListLoading} onClick={() => void loadSessions(page + 1)}>下一页<ChevronRight size={15} aria-hidden="true" /></button></div>
        </aside>
        <InspirationMessages session={selectedSession} messages={detail?.messages ?? []} draftMessage={messageDraft} isLoading={isDetailLoading} isSending={sendingSessionId === selectedSession?.id} onDraftMessageChange={setMessageDraft} onSend={() => void sendMessage()} onSaveDraft={(messageId) => void saveDraft(messageId)} />
        <InspirationContextPanel draft={sessionDraft} session={selectedSession} isCreating={isCreating} isArchiveDisabled={sendingSessionId === selectedSession?.id} isOpen={isNewSessionOpen} onDraftChange={setSessionDraft} onCreate={() => void createSession()} onClose={() => setIsNewSessionOpen(false)} onArchive={() => void archiveSession()} />
      </div>
    </section>
  );
}
