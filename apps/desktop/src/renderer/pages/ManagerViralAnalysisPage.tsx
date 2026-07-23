import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Filter, RefreshCw, Search } from "lucide-react";

import { api } from "../api/client";
import { ViralAnalysisResult } from "../components/viral/ViralAnalysisResult";
import type { ViralAnalysisJob, ViralAnalysisStatus } from "../types";

const pageSize = 20;
type Filters = { userId: string; startDate: string; endDate: string; status: "" | ViralAnalysisStatus; keyword: string };
const emptyFilters: Filters = { userId: "", startDate: "", endDate: "", status: "", keyword: "" };

function toTimestamp(value: string, endOfDay = false) { return value ? String(Math.floor(new Date(`${value}T${endOfDay ? "23:59:59" : "00:00:00"}`).getTime() / 1000)) : ""; }
function toParams(page: number, filters: Filters) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (filters.userId) params.set("user_id", filters.userId);
  if (filters.status) params.set("status", filters.status);
  if (filters.keyword.trim()) params.set("keyword", filters.keyword.trim());
  const start = toTimestamp(filters.startDate); const end = toTimestamp(filters.endDate, true);
  if (start) params.set("start_time", start); if (end) params.set("end_time", end);
  return params;
}
function formatTime(timestamp: number) { return timestamp ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(timestamp * 1000)) : "未记录"; }

export function ManagerViralAnalysisPage() {
  const [filters, setFilters] = useState(emptyFilters);
  const [jobs, setJobs] = useState<ViralAnalysisJob[]>([]); const [detail, setDetail] = useState<ViralAnalysisJob | null>(null);
  const [page, setPage] = useState(1); const [total, setTotal] = useState(0); const [loading, setLoading] = useState(true); const [message, setMessage] = useState("");
  const listRequest = useRef(0); const detailRequest = useRef(0); const selectedId = useRef<number | null>(null); const appliedFilters = useRef(emptyFilters);
  const selectJob = useCallback(async (jobId: number) => {
    const requestId = ++detailRequest.current; selectedId.current = jobId;
    try { const result = await api.getAdminViralAnalysisJob(jobId); if (requestId === detailRequest.current && selectedId.current === jobId) { setDetail(result); setMessage(""); } }
    catch (error) { if (requestId === detailRequest.current && selectedId.current === jobId) setMessage(error instanceof Error ? error.message : "详情加载失败。"); }
  }, []);
  const loadJobs = useCallback(async (requestedPage = 1, nextFilters = appliedFilters.current) => {
    const requestId = ++listRequest.current; setLoading(true);
    try {
      const result = await api.listAdminViralAnalysisJobs(toParams(requestedPage, nextFilters));
      if (requestId !== listRequest.current) return;
      if (!result.items.length && result.total > 0 && requestedPage > 1) { void loadJobs(requestedPage - 1, nextFilters); return; }
      setJobs(result.items); setPage(result.page); setTotal(result.total); setMessage("");
      if (selectedId.current && !result.items.some((item) => item.id === selectedId.current)) { ++detailRequest.current; selectedId.current = null; setDetail(null); }
    } catch (error) { if (requestId === listRequest.current) setMessage(error instanceof Error ? error.message : "记录加载失败。"); }
    finally { if (requestId === listRequest.current) setLoading(false); }
  }, []);
  useEffect(() => { void loadJobs(); }, [loadJobs]);
  function applyFilters() { appliedFilters.current = filters; void loadJobs(1, filters); }
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return <section className="page-stack manager-viral-page"><div className="page-heading horizontal-heading"><div><h1>爆款解析记录</h1><p>只读查看团队的解析任务、素材概况与结构化结果。</p></div><button className="secondary-button compact" type="button" onClick={() => void loadJobs(page)}><RefreshCw size={16} />刷新记录</button></div>{message ? <div className="form-message" role="status">{message}</div> : null}
    <section className="panel manager-viral-filters" aria-label="爆款解析筛选"><Filter size={18} /><label>员工 ID<input aria-label="员工 ID" inputMode="numeric" value={filters.userId} onChange={(event) => setFilters({ ...filters, userId: event.target.value })} /></label><label>开始时间<input aria-label="开始时间" type="date" value={filters.startDate} onChange={(event) => setFilters({ ...filters, startDate: event.target.value })} /></label><label>结束时间<input aria-label="结束时间" type="date" value={filters.endDate} onChange={(event) => setFilters({ ...filters, endDate: event.target.value })} /></label><label>任务状态<select aria-label="任务状态" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value as Filters["status"] })}><option value="">全部状态</option><option value="pending">待解析</option><option value="processing">解析中</option><option value="completed">已完成</option><option value="failed">失败</option><option value="cancelled">已取消</option></select></label><label className="manager-keyword-filter">关键词<div className="input-with-icon"><input aria-label="关键词" value={filters.keyword} onChange={(event) => setFilters({ ...filters, keyword: event.target.value })} /><Search size={16} /></div></label><button className="primary-button compact" type="button" onClick={applyFilters}>应用筛选</button></section>
    <div className="manager-viral-workspace"><section className="panel manager-viral-list"><div className="panel-title"><h2>任务列表</h2><span>{total} 项</span></div>{loading ? <div className="inspiration-session-skeleton"><span /><span /><span /></div> : jobs.length ? <div className="viral-job-rows">{jobs.map((job) => <button key={job.id} className={detail?.id === job.id ? "viral-job-row active" : "viral-job-row"} type="button" onClick={() => void selectJob(job.id)}><span><strong>{job.title}</strong><small>员工 {job.user_id} · {formatTime(job.create_time)}</small></span><span className={`viral-status ${job.status}`}>{job.status}</span></button>)}</div> : <div className="empty-list-state">没有符合筛选条件的记录。</div>}<div className="inspiration-pagination"><button className="table-action compact" type="button" disabled={loading || page <= 1} onClick={() => void loadJobs(page - 1)}><ChevronLeft size={15} />上一页</button><span>第 {page} 页 / 共 {total} 项</span><button className="table-action compact" type="button" disabled={loading || page >= pageCount} onClick={() => void loadJobs(page + 1)}>下一页<ChevronRight size={15} /></button></div></section>
      <section className="panel manager-viral-detail"><div className="panel-title"><h2>只读详情</h2>{detail ? <span>员工 {detail.user_id}</span> : null}</div>{detail ? <><div className="viral-detail-meta"><strong>{detail.title}</strong><span>{detail.materials?.length ?? 0} 份素材</span><span>消耗 {detail.credit_cost} 算力</span><span>{formatTime(detail.create_time)}</span></div><ViralAnalysisResult result={detail.result} /></> : <div className="empty-list-state">选择一项任务查看完整解析结果。</div>}</section></div>
  </section>;
}
