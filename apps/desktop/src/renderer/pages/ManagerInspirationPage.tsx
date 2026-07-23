import { useCallback, useEffect, useMemo, useState } from "react";
import { Filter, RefreshCw, Search } from "lucide-react";

import { api } from "../api/client";
import type { InspirationSession, InspirationSessionDetail } from "../types";

function formatDate(timestamp: number) {
  if (!timestamp) return "未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false
  }).format(new Date(timestamp * 1000));
}

export function ManagerInspirationPage() {
  const [sessions, setSessions] = useState<InspirationSession[]>([]);
  const [detail, setDetail] = useState<InspirationSessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [productId, setProductId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const loadSessions = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await api.listAdminInspirationSessions(new URLSearchParams({ page: "1", page_size: "100" }));
      setSessions(result.items);
      setMessage("");
      setDetail(result.items[0] ? await api.getAdminInspirationSession(result.items[0].id) : null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "灵感对话记录加载失败。");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const filteredSessions = useMemo(() => {
    const start = startDate ? new Date(`${startDate}T00:00:00`).getTime() / 1000 : 0;
    const end = endDate ? new Date(`${endDate}T23:59:59`).getTime() / 1000 : 0;
    const normalizedKeyword = keyword.trim().toLowerCase();
    return sessions.filter((session) => {
      if (employeeId && String(session.user_id) !== employeeId) return false;
      if (productId && String(session.linked_product_id) !== productId) return false;
      if (start && session.create_time < start) return false;
      if (end && session.create_time > end) return false;
      return !normalizedKeyword || [session.title, session.tone, session.extra_requirement].join(" ").toLowerCase().includes(normalizedKeyword);
    });
  }, [employeeId, endDate, keyword, productId, sessions, startDate]);

  async function selectSession(sessionId: number) {
    try {
      setDetail(await api.getAdminInspirationSession(sessionId));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "会话详情加载失败。");
    }
  }

  return (
    <section className="page-stack manager-inspiration-page">
      <div className="page-heading horizontal-heading">
        <div><h1>灵感对话记录</h1><p>只读查看团队成员的会话内容与算力消耗，帮助管理层复盘内容生产过程。</p></div>
        <button className="secondary-button compact" type="button" onClick={() => void loadSessions()}><RefreshCw size={16} aria-hidden="true" />刷新记录</button>
      </div>
      {message ? <div className="form-message" role="status">{message}</div> : null}
      <section className="panel manager-inspiration-filters" aria-label="会话筛选">
        <Filter size={18} aria-hidden="true" />
        <label>员工 ID<input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} inputMode="numeric" /></label>
        <label>产品 ID<input value={productId} onChange={(event) => setProductId(event.target.value)} inputMode="numeric" /></label>
        <label>开始时间<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        <label>结束时间<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
        <label className="manager-keyword-filter">关键词筛选<div className="input-with-icon"><input value={keyword} onChange={(event) => setKeyword(event.target.value)} /><Search size={16} aria-hidden="true" /></div></label>
      </section>
      <div className="manager-inspiration-workspace">
        <section className="panel manager-inspiration-list" aria-busy={isLoading}>
          <div className="panel-title"><h2>会话列表</h2><span>{filteredSessions.length} 条</span></div>
          {isLoading ? <div className="inspiration-session-skeleton"><span /><span /><span /></div> : null}
          {!isLoading && filteredSessions.length === 0 ? <div className="empty-list-state">没有符合筛选条件的会话记录</div> : null}
          {!isLoading ? <div className="inspiration-session-list">{filteredSessions.map((session) => <button key={session.id} className={detail?.session.id === session.id ? "inspiration-session-item active" : "inspiration-session-item"} type="button" onClick={() => void selectSession(session.id)}><strong>{session.title}</strong><span>员工 {session.user_id} · 产品 {session.linked_product_id || "未关联"}</span><span>{formatDate(session.create_time)}</span></button>)}</div> : null}
        </section>
        <section className="panel manager-inspiration-detail">
          <div className="panel-title"><h2>会话详情</h2>{detail ? <span className="key-status connected">总算力 {detail.session.total_credit_cost}</span> : null}</div>
          {!detail ? <div className="empty-list-state">选择一条会话记录查看完整内容。</div> : <>
            <div className="manager-detail-meta"><span>员工 ID：{detail.session.user_id}</span><span>产品 ID：{detail.session.linked_product_id || "未关联"}</span><span>创建时间：{formatDate(detail.session.create_time)}</span><span>草稿状态：当前接口未返回关联状态</span></div>
            <div className="manager-message-list">{detail.messages.map((item) => <article className={`inspiration-message ${item.role}`} key={item.id}><div className="inspiration-message-meta">{item.role === "user" ? "员工提问" : "AI 建议"}</div><p>{item.content}</p></article>)}</div>
          </>}
        </section>
      </div>
    </section>
  );
}
