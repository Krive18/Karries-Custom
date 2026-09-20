import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  FileStack,
  Filter,
  RefreshCw,
  Search,
  Sparkles,
  UserRound
} from "lucide-react";

import { managerApi } from "../api/managerClient";
import { ManagerEmployeeSelect } from "../components/ManagerEmployeeSelect";
import { ViralAnalysisResult } from "../components/viral/ViralAnalysisResult";
import { viralAnalysisStatusLabel } from "../components/viral/status";
import type { ViralAnalysisJob, ViralAnalysisStatus } from "../types";

const pageSize = 20;

type Filters = {
  userId: string;
  startDate: string;
  endDate: string;
  status: "" | ViralAnalysisStatus;
  keyword: string;
};

const emptyFilters: Filters = {
  userId: "",
  startDate: "",
  endDate: "",
  status: "",
  keyword: ""
};

function toTimestamp(value: string, endOfDay = false) {
  if (!value) return "";
  return String(
    Math.floor(
      new Date(`${value}T${endOfDay ? "23:59:59" : "00:00:00"}`).getTime() / 1000
    )
  );
}

function toParams(page: number, filters: Filters) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });
  if (filters.userId) params.set("user_id", filters.userId);
  if (filters.status) params.set("status", filters.status);
  if (filters.keyword.trim()) params.set("keyword", filters.keyword.trim());

  const start = toTimestamp(filters.startDate);
  const end = toTimestamp(filters.endDate, true);
  if (start) params.set("start_time", start);
  if (end) params.set("end_time", end);
  return params;
}

function formatTime(timestamp: number) {
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

function friendlyFailure(message: string) {
  const normalized = message.toLowerCase();
  if (!message.trim()) return "解析服务未返回结果，请检查素材后重新创建任务。";
  if (normalized.includes("configuration") || normalized.includes("provider")) {
    return "AI 解析服务暂时不可用，请联系点绘环球技术人员检查服务配置。";
  }
  if (normalized.includes("invalid analysis") || normalized.includes("invalid result")) {
    return "素材解析结果不完整，请补充清晰素材后重新创建任务。";
  }
  if (normalized.includes("request failed") || normalized.includes("timeout")) {
    return "AI 解析服务连接超时，请稍后重新创建任务。";
  }
  return message;
}

export function ManagerViralAnalysisPage() {
  const [filters, setFilters] = useState(emptyFilters);
  const [jobs, setJobs] = useState<ViralAnalysisJob[]>([]);
  const [detail, setDetail] = useState<ViralAnalysisJob | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const listRequest = useRef(0);
  const detailRequest = useRef(0);
  const selectedId = useRef<number | null>(null);
  const appliedFilters = useRef(emptyFilters);

  const selectJob = useCallback(async (jobId: number) => {
    const requestId = ++detailRequest.current;
    selectedId.current = jobId;
    try {
      const result = await managerApi.getViralAnalysisJob(jobId);
      if (requestId !== detailRequest.current || selectedId.current !== jobId) return;
      setDetail(result);
      setMessage("");
    } catch (error) {
      if (requestId === detailRequest.current && selectedId.current === jobId) {
        setMessage(error instanceof Error ? error.message : "详情加载失败。");
      }
    }
  }, []);

  const loadJobs = useCallback(
    async (requestedPage = 1, nextFilters = appliedFilters.current) => {
      const requestId = ++listRequest.current;
      setLoading(true);
      try {
        const result = await managerApi.listViralAnalysisJobs(
          toParams(requestedPage, nextFilters)
        );
        if (requestId !== listRequest.current) return;
        if (!result.items.length && result.total > 0 && requestedPage > 1) {
          void loadJobs(requestedPage - 1, nextFilters);
          return;
        }

        setJobs(result.items);
        setPage(result.page);
        setTotal(result.total);
        setMessage("");

        const selectedVisible =
          selectedId.current !== null &&
          result.items.some((item) => item.id === selectedId.current);
        if (!selectedVisible) {
          ++detailRequest.current;
          selectedId.current = null;
          setDetail(null);
          if (result.items[0]) await selectJob(result.items[0].id);
        }
      } catch (error) {
        if (requestId === listRequest.current) {
          setMessage(error instanceof Error ? error.message : "记录加载失败。");
        }
      } finally {
        if (requestId === listRequest.current) setLoading(false);
      }
    },
    [selectJob]
  );

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  function applyFilters() {
    appliedFilters.current = filters;
    void loadJobs(1, filters);
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="page-stack manager-history-page manager-viral-page">
      <div className="manager-history-heading">
        <div>
          <h1>爆款解析记录</h1>
          <p>查看团队解析任务、素材与结构化结果。</p>
        </div>
        <button
          className="secondary-button compact"
          type="button"
          onClick={() => void loadJobs(page)}
        >
          <RefreshCw size={16} aria-hidden="true" />
          刷新记录
        </button>
      </div>

      {message ? <div className="form-message" role="status">{message}</div> : null}

      <section className="panel manager-history-filters" aria-label="爆款解析筛选">
        <div className="manager-filter-title">
          <Filter size={18} aria-hidden="true" />
          <strong>筛选记录</strong>
        </div>
        <ManagerEmployeeSelect
          value={filters.userId}
          onChange={(userId) => setFilters({ ...filters, userId })}
        />
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
        <label>
          任务状态
          <select
            aria-label="任务状态"
            value={filters.status}
            onChange={(event) =>
              setFilters({ ...filters, status: event.target.value as Filters["status"] })
            }
          >
            <option value="">全部状态</option>
            <option value="pending">待解析</option>
            <option value="processing">解析中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
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
        <button className="primary-button compact manager-filter-action" type="button" onClick={applyFilters}>
          应用筛选
        </button>
      </section>

      <div className="manager-history-workspace manager-viral-workspace">
        <section className="panel manager-history-list manager-viral-list" aria-busy={loading}>
          <div className="panel-title">
            <h2>任务列表</h2>
            <span>{total} 项</span>
          </div>
          {loading ? (
            <div className="inspiration-session-skeleton"><span /><span /><span /></div>
          ) : jobs.length ? (
            <div className="manager-record-list">
              {jobs.map((job) => (
                <button
                  key={job.id}
                  className={detail?.id === job.id ? "manager-record-row active" : "manager-record-row"}
                  type="button"
                  onClick={() => void selectJob(job.id)}
                >
                  <span className="manager-record-row-top">
                    <strong>{job.title}</strong>
                    <span className={`viral-status ${job.status}`}>
                      {viralAnalysisStatusLabel(job.status)}
                    </span>
                  </span>
                  <span className="manager-record-row-meta">
                    <span><UserRound size={13} aria-hidden="true" />员工 {job.user_id}</span>
                    <span><CalendarClock size={13} aria-hidden="true" />{formatTime(job.create_time)}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-list-state">没有符合筛选条件的记录。</div>
          )}
          <div className="inspiration-pagination manager-history-pagination">
            <button
              className="table-action compact"
              type="button"
              disabled={loading || page <= 1}
              onClick={() => void loadJobs(page - 1)}
            >
              <ChevronLeft size={15} aria-hidden="true" />上一页
            </button>
            <span>第 {page} / {pageCount} 页</span>
            <button
              className="table-action compact"
              type="button"
              disabled={loading || page >= pageCount}
              onClick={() => void loadJobs(page + 1)}
            >
              下一页<ChevronRight size={15} aria-hidden="true" />
            </button>
          </div>
        </section>

        <section className="panel manager-history-detail manager-viral-detail">
          {!detail ? (
            <div className="manager-history-empty">
              <Sparkles size={24} aria-hidden="true" />
              <strong>选择一项解析任务</strong>
              <span>完整的开场、结构、节奏与脚本会显示在这里。</span>
            </div>
          ) : (
            <>
              <header className="manager-detail-heading">
                <div>
                  <span className="manager-detail-eyebrow">解析结果</span>
                  <h2>{detail.title}</h2>
                </div>
                <span className={`viral-status ${detail.status}`}>
                  {viralAnalysisStatusLabel(detail.status)}
                </span>
              </header>
              <div className="manager-record-meta-grid">
                <span><UserRound size={15} aria-hidden="true" /><small>员工</small><strong>{detail.user_id}</strong></span>
                <span><FileStack size={15} aria-hidden="true" /><small>素材</small><strong>{detail.materials?.length ?? 0} 份</strong></span>
                <span><Sparkles size={15} aria-hidden="true" /><small>算力</small><strong>{detail.credit_cost}</strong></span>
                <span><CalendarClock size={15} aria-hidden="true" /><small>创建时间</small><strong>{formatTime(detail.create_time)}</strong></span>
              </div>
              {detail.status === "failed" ? (
                <div className="manager-failure-callout" role="status">
                  <AlertCircle size={20} aria-hidden="true" />
                  <div>
                    <strong>任务未完成</strong>
                    <p>{friendlyFailure(detail.error_message || "")}</p>
                  </div>
                </div>
              ) : (
                <ViralAnalysisResult
                  result={detail.result}
                  emptyText={detail.status === "processing" ? "AI 正在整理解析结果。" : "该任务暂未生成解析结果。"}
                />
              )}
            </>
          )}
        </section>
      </div>
    </section>
  );
}
