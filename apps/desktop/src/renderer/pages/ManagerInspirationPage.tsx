import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Filter,
  MessageSquareText,
  Package,
  RefreshCw,
  Search,
  Sparkles,
  UserRound
} from "lucide-react";

import { managerApi } from "../api/managerClient";
import { ManagerEmployeeSelect } from "../components/ManagerEmployeeSelect";
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
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}

function toTimestamp(value: string, endOfDay = false) {
  if (!value) return "";
  return String(
    Math.floor(
      new Date(`${value}T${endOfDay ? "23:59:59" : "00:00:00"}`).getTime() / 1000
    )
  );
}

function toParams(page: number, filters: InspirationFilters) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });
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
      const nextDetail = await managerApi.getInspirationSession(sessionId);
      if (
        requestId !== detailRequestRef.current ||
        selectedSessionIdRef.current !== sessionId
      ) {
        return;
      }
      setDetail(nextDetail);
      setMessage("");
    } catch (error) {
      if (
        requestId === detailRequestRef.current &&
        selectedSessionIdRef.current === sessionId
      ) {
        setMessage(error instanceof Error ? error.message : "会话详情加载失败。");
      }
    }
  }, []);

  const loadSessions = useCallback(
    async (requestedPage = 1, nextFilters = appliedFiltersRef.current) => {
      const requestId = ++listRequestRef.current;
      setIsLoading(true);
      try {
        const result = await managerApi.listInspirationSessions(
          toParams(requestedPage, nextFilters)
        );
        if (requestId !== listRequestRef.current) return;
        if (result.items.length === 0 && result.total > 0 && requestedPage > 1) {
          void loadSessions(requestedPage - 1, nextFilters);
          return;
        }

        setSessions(result.items);
        setPage(result.page);
        setTotal(result.total);
        setMessage("");

        const selectedVisible =
          selectedSessionIdRef.current !== null &&
          result.items.some((item) => item.id === selectedSessionIdRef.current);
        if (!selectedVisible) {
          ++detailRequestRef.current;
          selectedSessionIdRef.current = null;
          setDetail(null);
          if (result.items[0]) await selectSession(result.items[0].id);
        }
      } catch (error) {
        if (requestId === listRequestRef.current) {
          setMessage(
            error instanceof Error ? error.message : "灵感对话记录加载失败。"
          );
        }
      } finally {
        if (requestId === listRequestRef.current) setIsLoading(false);
      }
    },
    [selectSession]
  );

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  function applyFilters() {
    appliedFiltersRef.current = filters;
    void loadSessions(1, filters);
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="page-stack manager-history-page manager-inspiration-page">
      <div className="manager-history-heading">
        <div>
          <h1>Karries AI 记录</h1>
          <p>查看团队会话内容与算力使用情况。</p>
        </div>
        <button
          className="secondary-button compact"
          type="button"
          onClick={() => void loadSessions(page)}
        >
          <RefreshCw size={16} aria-hidden="true" />
          刷新记录
        </button>
      </div>

      {message ? <div className="form-message" role="status">{message}</div> : null}

      <section className="panel manager-history-filters" aria-label="会话筛选">
        <div className="manager-filter-title">
          <Filter size={18} aria-hidden="true" />
          <strong>筛选记录</strong>
        </div>
        <ManagerEmployeeSelect
          value={filters.userId}
          onChange={(userId) => setFilters({ ...filters, userId })}
        />
        <label>
          产品 ID
          <input
            aria-label="产品 ID"
            value={filters.productId}
            onChange={(event) => setFilters({ ...filters, productId: event.target.value })}
            inputMode="numeric"
          />
        </label>
        <label>
          开始时间
          <input
            aria-label="开始时间"
            type="date"
            value={filters.startDate}
            onChange={(event) => setFilters({ ...filters, startDate: event.target.value })}
          />
        </label>
        <label>
          结束时间
          <input
            aria-label="结束时间"
            type="date"
            value={filters.endDate}
            onChange={(event) => setFilters({ ...filters, endDate: event.target.value })}
          />
        </label>
        <label className="manager-keyword-filter">
          关键词
          <div className="input-with-icon">
            <input
              aria-label="关键词"
              value={filters.keyword}
              onChange={(event) => setFilters({ ...filters, keyword: event.target.value })}
            />
            <Search size={16} aria-hidden="true" />
          </div>
        </label>
        <button
          className="primary-button compact manager-filter-action"
          type="button"
          onClick={applyFilters}
        >
          应用筛选
        </button>
      </section>

      <div className="manager-history-workspace manager-inspiration-workspace">
        <section className="panel manager-history-list manager-inspiration-list" aria-busy={isLoading}>
          <div className="panel-title">
            <h2>会话列表</h2>
            <span>{total} 条</span>
          </div>
          {isLoading ? (
            <div className="inspiration-session-skeleton"><span /><span /><span /></div>
          ) : sessions.length ? (
            <div className="manager-record-list">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  className={
                    detail?.session.id === session.id
                      ? "manager-record-row active"
                      : "manager-record-row"
                  }
                  type="button"
                  onClick={() => void selectSession(session.id)}
                >
                  <span className="manager-record-row-top">
                    <strong>{session.title}</strong>
                    <span>{session.message_count} 条</span>
                  </span>
                  <span className="manager-record-row-meta">
                    <span><UserRound size={13} aria-hidden="true" />员工 {session.user_id}</span>
                    <span><CalendarClock size={13} aria-hidden="true" />{formatDate(session.create_time)}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-list-state">没有符合筛选条件的会话记录。</div>
          )}
          <div className="inspiration-pagination manager-history-pagination">
            <button
              className="table-action compact"
              type="button"
              disabled={page <= 1 || isLoading}
              onClick={() => void loadSessions(page - 1)}
            >
              <ChevronLeft size={15} aria-hidden="true" />上一页
            </button>
            <span>第 {page} / {pageCount} 页</span>
            <button
              className="table-action compact"
              type="button"
              disabled={page >= pageCount || isLoading}
              onClick={() => void loadSessions(page + 1)}
            >
              下一页<ChevronRight size={15} aria-hidden="true" />
            </button>
          </div>
        </section>

        <section className="panel manager-history-detail manager-inspiration-detail">
          {!detail ? (
            <div className="manager-history-empty">
              <MessageSquareText size={24} aria-hidden="true" />
              <strong>选择一条会话记录</strong>
              <span>员工与 AI 的完整对话会显示在这里。</span>
            </div>
          ) : (
            <>
              <header className="manager-detail-heading">
                <div>
                  <span className="manager-detail-eyebrow">会话详情</span>
                  <h2>{detail.session.title}</h2>
                </div>
                <span className="manager-credit-pill">
                  <Sparkles size={14} aria-hidden="true" />
                  {detail.session.total_credit_cost} 算力
                </span>
              </header>
              <div className="manager-record-meta-grid manager-session-meta-grid">
                <span><UserRound size={15} aria-hidden="true" /><small>员工</small><strong>{detail.session.user_id}</strong></span>
                <span><Package size={15} aria-hidden="true" /><small>产品</small><strong>{detail.session.linked_product_id || "未关联"}</strong></span>
                <span><MessageSquareText size={15} aria-hidden="true" /><small>消息</small><strong>{detail.messages.length} 条</strong></span>
                <span><CalendarClock size={15} aria-hidden="true" /><small>创建时间</small><strong>{formatDate(detail.session.create_time)}</strong></span>
              </div>
              <div className="manager-conversation">
                {detail.messages.map((item) => {
                  const isUser = item.role === "user";
                  return (
                    <article
                      className={isUser ? "manager-chat-message user" : "manager-chat-message assistant"}
                      key={item.id}
                    >
                      <div className="manager-chat-avatar" aria-hidden="true">
                        {isUser ? <UserRound size={17} /> : <Bot size={17} />}
                      </div>
                      <div className="manager-chat-body">
                        <header>
                          <strong>{isUser ? "员工提问" : "AI 建议"}</strong>
                          <span>{formatDate(item.create_time)}</span>
                        </header>
                        <p>{item.content}</p>
                        {!isUser && (item.credit_cost > 0 || item.content_draft_id > 0 || (item.content_collection_id ?? 0) > 0) ? (
                          <footer>
                            {item.credit_cost > 0 ? <span>{item.credit_cost} 算力</span> : null}
                            {(item.content_collection_id ?? 0) > 0 ? <span>已收藏 #{item.content_collection_id}</span> : null}
                            {item.content_draft_id > 0 ? <span>历史审核草稿 #{item.content_draft_id}</span> : null}
                          </footer>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            </>
          )}
        </section>
      </div>
    </section>
  );
}
