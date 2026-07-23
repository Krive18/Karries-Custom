import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Filter, RefreshCw, Search } from "lucide-react";

import { api } from "../api/client";
import type { InspirationSession, InspirationSessionDetail } from "../types";

const pageSize = 20;

type InspirationFilters = {
  userId: string;
  productId: string;
  keyword: string;
  startDate: string;
  endDate: string;
};

const emptyFilters: InspirationFilters = {
  userId: "",
  productId: "",
  keyword: "",
  startDate: "",
  endDate: ""
};

function formatDate(timestamp: number) {
  if (!timestamp) return "未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false
  }).format(new Date(timestamp * 1000));
}

function toTimestamp(value: string, endOfDay = false) {
  if (!value) return "";
  return String(Math.floor(new Date(`${value}T${endOfDay ? "23:59:59" : "00:00:00"}`).getTime() / 1000));
}

function toParams(page: number, filters: InspirationFilters) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (filters.userId.trim()) params.set("user_id", filters.userId.trim());
  if (filters.productId.trim()) params.set("product_id", filters.productId.trim());
  if (filters.keyword.trim()) params.set("keyword", filters.keyword.trim());
  const startTime = toTimestamp(filters.startDate);
  const endTime = toTimestamp(filters.endDate, true);
  if (startTime) params.set("start_time", startTime);
  if (endTime) params.set("end_time", endTime);
  return params;
}

export function ManagerInspirationPage() {
  const [sessions, setSessions] = useState<InspirationSession[]>([]);
  const [detail, setDetail] = useState<InspirationSessionDetail | null>(null);
  const [filters, setFilters] = useState(emptyFilters);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");
  const listRequestRef = useRef(0);
  const detailRequestRef = useRef(0);
  const selectedSessionIdRef = useRef<number | null>(null);
  const appliedFiltersRef = useRef(emptyFilters);

  const selectSession = useCallback(async (sessionId: number) => {
    const requestId = ++detailRequestRef.current;
    selectedSessionIdRef.current = sessionId;
    try {
      const nextDetail = await api.getAdminInspirationSession(sessionId);
      if (requestId !== detailRequestRef.current || selectedSessionIdRef.current !== sessionId) return;
      setDetail(nextDetail);
      setMessage("");
    } catch (error) {
      if (requestId === detailRequestRef.current && selectedSessionIdRef.current === sessionId) {
        setMessage(error instanceof Error ? error.message : "会话详情加载失败。");
      }
    }
  }, []);

  const loadSessions = useCallback(async (requestedPage = 1, nextFilters = appliedFiltersRef.current) => {
    const requestId = ++listRequestRef.current;
    setIsLoading(true);
    try {
      const result = await api.listAdminInspirationSessions(toParams(requestedPage, nextFilters));
      if (requestId !== listRequestRef.current) return;
      if (result.items.length === 0 && result.total > 0 && requestedPage > 1) {
        void loadSessions(requestedPage - 1, nextFilters);
        return;
      }
      setSessions(result.items);
      setPage(result.page);
      setTotal(result.total);
      setMessage("");
      const selectedStillVisible = selectedSessionIdRef.current !== null && result.items.some((item) => item.id === selectedSessionIdRef.current);
      if (!selectedStillVisible) {
        ++detailRequestRef.current;
        selectedSessionIdRef.current = null;
        setDetail(null);
        if (result.items[0]) await selectSession(result.items[0].id);
      }
    } catch (error) {
      if (requestId === listRequestRef.current) setMessage(error instanceof Error ? error.message : "灵感对话记录加载失败。");
    } finally {
      if (requestId === listRequestRef.current) setIsLoading(false);
    }
  }, [selectSession]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  function applyFilters() {
    appliedFiltersRef.current = filters;
    void loadSessions(1, filters);
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return (
    <section className="page-stack manager-inspiration-page">
      <div className="page-heading horizontal-heading">
        <div><h1>灵感对话记录</h1><p>只读查看团队成员的会话内容与算力消耗，帮助管理层复盘内容生产过程。</p></div>
        <button className="secondary-button compact" type="button" onClick={() => void loadSessions(page)}><RefreshCw size={16} aria-hidden="true" />刷新记录</button>
      </div>
      {message ? <div className="form-message" role="status">{message}</div> : null}
      <section className="panel manager-inspiration-filters" aria-label="会话筛选">
        <Filter size={18} aria-hidden="true" />
        <label>员工 ID<input value={filters.userId} onChange={(event) => setFilters({ ...filters, userId: event.target.value })} inputMode="numeric" /></label>
        <label>产品 ID<input value={filters.productId} onChange={(event) => setFilters({ ...filters, productId: event.target.value })} inputMode="numeric" /></label>
        <label>开始时间<input type="date" value={filters.startDate} onChange={(event) => setFilters({ ...filters, startDate: event.target.value })} /></label>
        <label>结束时间<input type="date" value={filters.endDate} onChange={(event) => setFilters({ ...filters, endDate: event.target.value })} /></label>
        <label className="manager-keyword-filter">关键词筛选<div className="input-with-icon"><input value={filters.keyword} onChange={(event) => setFilters({ ...filters, keyword: event.target.value })} /><Search size={16} aria-hidden="true" /></div></label>
        <button className="primary-button compact" type="button" onClick={applyFilters}>应用筛选</button>
      </section>
      <div className="manager-inspiration-workspace">
        <section className="panel manager-inspiration-list" aria-busy={isLoading}>
          <div className="panel-title"><h2>会话列表</h2><span>{total} 条</span></div>
          {isLoading ? <div className="inspiration-session-skeleton"><span /><span /><span /></div> : null}
          {!isLoading && sessions.length === 0 ? <div className="empty-list-state">没有符合筛选条件的会话记录</div> : null}
          {!isLoading ? <div className="inspiration-session-list">{sessions.map((session) => <button key={session.id} className={detail?.session.id === session.id ? "inspiration-session-item active" : "inspiration-session-item"} type="button" onClick={() => void selectSession(session.id)}><strong>{session.title}</strong><span>员工 {session.user_id} · 产品 {session.linked_product_id || "未关联"}</span><span>{formatDate(session.create_time)}</span></button>)}</div> : null}
          <div className="inspiration-pagination" aria-label="管理会话分页"><button className="table-action compact" type="button" disabled={page <= 1 || isLoading} onClick={() => void loadSessions(page - 1)}><ChevronLeft size={15} aria-hidden="true" />上一页</button><span>第 {page} 页 / 共 {total} 条</span><button className="table-action compact" type="button" disabled={page >= pageCount || isLoading} onClick={() => void loadSessions(page + 1)}>下一页<ChevronRight size={15} aria-hidden="true" /></button></div>
        </section>
        <section className="panel manager-inspiration-detail">
          <div className="panel-title"><h2>会话详情</h2>{detail ? <span className="key-status connected">总算力 {detail.session.total_credit_cost}</span> : null}</div>
          {!detail ? <div className="empty-list-state">选择一条会话记录查看完整内容。</div> : <>
            <div className="manager-detail-meta"><span>员工 ID：{detail.session.user_id}</span><span>产品 ID：{detail.session.linked_product_id || "未关联"}</span><span>创建时间：{formatDate(detail.session.create_time)}</span></div>
            <div className="manager-message-list">{detail.messages.map((item) => <article className={`inspiration-message ${item.role}`} key={item.id}><div className="inspiration-message-meta">{item.role === "user" ? "员工提问" : "AI 建议"}</div><p>{item.content}</p><span className="message-draft-id">{item.content_draft_id > 0 ? `草稿 ID：${item.content_draft_id}` : "未保存为草稿"}</span></article>)}</div>
          </>}
        </section>
      </div>
    </section>
  );
}
