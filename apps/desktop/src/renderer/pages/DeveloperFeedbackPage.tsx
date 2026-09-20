import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, MessageSquareMore, RefreshCw, Search } from "lucide-react";

import { developerApi } from "../api/developerClient";
import type { UserFeedback, UserFeedbackStatus } from "../types";


const statusLabels: Record<UserFeedbackStatus, string> = {
  pending: "待处理",
  in_progress: "处理中",
  completed: "已完成"
};

const categoryLabels = {
  bug: "问题反馈",
  feature: "功能需求",
  experience: "体验建议",
  other: "其他"
};

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString("zh-CN");
}


export function DeveloperFeedbackPage() {
  const selectedIdRef = useRef(0);
  const [items, setItems] = useState<UserFeedback[]>([]);
  const [selectedId, setSelectedId] = useState(0);
  const [status, setStatus] = useState<"" | UserFeedbackStatus>("");
  const [keyword, setKeyword] = useState("");
  const [reply, setReply] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const selected = items.find((item) => item.id === selectedId) ?? items[0] ?? null;

  const loadFeedback = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({ page_size: "100" });
      if (status) params.set("status", status);
      if (keyword.trim()) params.set("keyword", keyword.trim());
      const result = await developerApi.listUserFeedback(params);
      setItems(result.items);
      const nextSelected = result.items.find((item) => item.id === selectedIdRef.current)
        ?? result.items[0]
        ?? null;
      selectedIdRef.current = nextSelected?.id ?? 0;
      setSelectedId(selectedIdRef.current);
      setReply(nextSelected?.developer_reply ?? "");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "用户反馈加载失败");
    } finally {
      setIsLoading(false);
    }
  }, [keyword, status]);

  useEffect(() => {
    void loadFeedback();
  }, [loadFeedback]);

  async function save(statusToSave: UserFeedbackStatus) {
    if (!selected || isSaving) return;
    if (statusToSave === "completed" && reply.trim().length < 2) {
      setMessage("完成反馈前请填写给用户的处理回复。");
      return;
    }
    setIsSaving(true);
    setMessage("");
    try {
      const updated = await developerApi.updateUserFeedback(selected.id, {
        status: statusToSave,
        developer_reply: reply.trim()
      });
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage(statusToSave === "completed" ? "反馈已完成，用户已收到站内通知。" : "反馈处理状态已更新。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "反馈更新失败");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="developer-page developer-feedback-page">
      <header className="developer-page-header">
        <div><span className="developer-eyebrow">CUSTOMER VOICE</span><h1>用户需求反馈</h1><p>集中处理客户问题与新需求，完成后自动通知原提交用户。</p></div>
        <button type="button" onClick={() => void loadFeedback()} disabled={isLoading}><RefreshCw size={16} className={isLoading ? "spin" : ""} />刷新</button>
      </header>
      {message ? <div className={message.startsWith("反馈已完成") ? "developer-feedback-message success" : "developer-feedback-message"} role="status">{message}</div> : null}
      <div className="developer-feedback-toolbar">
        <label><Search size={16} /><input aria-label="搜索用户反馈" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索标题、客户或团队" /></label>
        <div>{(["", "pending", "in_progress", "completed"] as const).map((item) => <button key={item || "all"} type="button" className={status === item ? "active" : ""} onClick={() => setStatus(item)}>{item ? statusLabels[item] : "全部"}</button>)}</div>
      </div>
      <div className="developer-feedback-layout">
        <aside className="developer-feedback-list" aria-busy={isLoading}>
          {isLoading && !items.length ? <div className="developer-feedback-empty"><Loader2 className="spin" />加载中</div> : null}
          {!isLoading && !items.length ? <div className="developer-feedback-empty"><MessageSquareMore /><span>没有匹配的反馈</span></div> : null}
          {items.map((item) => <button key={item.id} type="button" className={selected?.id === item.id ? "active" : ""} onClick={() => { selectedIdRef.current = item.id; setSelectedId(item.id); setReply(item.developer_reply); }}><span><b>{categoryLabels[item.category]}</b><i className={item.status}>{statusLabels[item.status]}</i></span><strong>{item.title}</strong><small>{item.tenant_name} · {item.user_nickname || item.user_login_name}</small><time>{formatTime(item.update_time)}</time></button>)}
        </aside>
        <section className="developer-feedback-detail">
          {selected ? <>
            <header><div><span>{categoryLabels[selected.category]} · #{selected.id}</span><h2>{selected.title}</h2><p>{selected.tenant_name} / {selected.user_nickname || selected.user_login_name}</p></div><span className={`developer-feedback-status ${selected.status}`}>{statusLabels[selected.status]}</span></header>
            <div className="developer-feedback-description"><strong>用户说明</strong><p>{selected.description}</p></div>
            <label>处理回复<textarea rows={8} value={reply} onChange={(event) => setReply(event.target.value)} placeholder="向用户说明处理结果、使用方式或后续计划" /></label>
            <footer>
              <button type="button" disabled={isSaving} onClick={() => void save("in_progress")}>保存为处理中</button>
              <button className="complete" type="button" disabled={isSaving || selected.status === "completed"} onClick={() => void save("completed")}><CheckCircle2 size={16} />完成并通知用户</button>
            </footer>
          </> : <div className="developer-feedback-empty"><MessageSquareMore /><span>请选择一条反馈</span></div>}
        </section>
      </div>
    </section>
  );
}
