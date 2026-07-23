import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, CircleStop, FileUp, Lightbulb, Loader2, Play, Plus, RefreshCw, Save, Sparkles } from "lucide-react";

import { ApiRequestError, api } from "../api/client";
import { ViralAnalysisResult } from "../components/viral/ViralAnalysisResult";
import type { ViralAnalysisGoal, ViralAnalysisJob, ViralAnalysisSourceType } from "../types";

const pageSize = 20;
const goalOptions: Array<{ value: ViralAnalysisGoal; label: string }> = [
  { value: "hook", label: "开场钩子" }, { value: "structure", label: "内容结构" },
  { value: "rhythm", label: "镜头节奏" }, { value: "script", label: "脚本拆解" },
  { value: "selling", label: "卖点" }, { value: "reuse", label: "复用建议" }
];

function statusText(status: ViralAnalysisJob["status"]) {
  return ({ pending: "待解析", processing: "解析中", completed: "已完成", failed: "解析失败，可重试", cancelled: "已取消" })[status];
}

function explainError(error: unknown) {
  if (error instanceof ApiRequestError) {
    if (error.status === 413) return "素材超过 200 MB 限制，请压缩后重新上传。";
    if (error.status === 409) return "当前任务状态已变化，请刷新后重试。";
    if (error.status === 502) return "解析服务暂时不可用，任务可稍后重试。";
    if (error.code === "CAPABILITY_UNAVAILABLE") return "请补充口播稿或观察笔记；当前尚未接入视频画面理解。";
  }
  return error instanceof Error ? error.message : "操作未完成，请稍后重试。";
}

function toParams(page: number) {
  return new URLSearchParams({ page: String(page), page_size: String(pageSize) });
}

type ViralAnalysisPageProps = { onStartInspiration: () => void };

export function ViralAnalysisPage({ onStartInspiration }: ViralAnalysisPageProps) {
  const [jobs, setJobs] = useState<ViralAnalysisJob[]>([]);
  const [detail, setDetail] = useState<ViralAnalysisJob | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [busyJobId, setBusyJobId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<ViralAnalysisSourceType>("text");
  const [sourceUrl, setSourceUrl] = useState("");
  const [supplementText, setSupplementText] = useState("");
  const [goals, setGoals] = useState<ViralAnalysisGoal[]>(["hook", "structure", "script", "reuse"]);
  const [file, setFile] = useState<File | null>(null);
  const listRequest = useRef(0);
  const detailRequest = useRef(0);
  const selectedId = useRef<number | null>(null);

  const loadJobs = useCallback(async (requestedPage = 1) => {
    const requestId = ++listRequest.current;
    setIsLoading(true);
    try {
      const result = await api.listViralAnalysisJobs(toParams(requestedPage));
      if (requestId !== listRequest.current) return;
      if (!result.items.length && result.total > 0 && requestedPage > 1) {
        void loadJobs(requestedPage - 1);
        return;
      }
      setJobs(result.items);
      setPage(result.page);
      setTotal(result.total);
      if (selectedId.current && !result.items.some((item) => item.id === selectedId.current)) {
        selectedId.current = null;
        ++detailRequest.current;
        setDetail(null);
      }
    } catch (error) {
      if (requestId === listRequest.current) setMessage(explainError(error));
    } finally {
      if (requestId === listRequest.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => { void loadJobs(); }, [loadJobs]);

  const selectJob = useCallback(async (jobId: number) => {
    const requestId = ++detailRequest.current;
    selectedId.current = jobId;
    try {
      const job = await api.getViralAnalysisJob(jobId);
      if (requestId !== detailRequest.current || selectedId.current !== jobId) return;
      setDetail(job);
      setMessage("");
    } catch (error) {
      if (requestId === detailRequest.current && selectedId.current === jobId) setMessage(explainError(error));
    }
  }, []);

  async function createAndRun() {
    if (!title.trim()) { setMessage("请填写任务名称。"); return; }
    if (!supplementText.trim()) { setMessage("请补充口播稿或观察笔记；当前尚未接入视频画面理解。"); return; }
    if (sourceType === "upload" && !file) { setMessage("上传素材类型需要选择一个本地文件。"); return; }
    setBusyJobId(-1);
    try {
      const created = await api.createViralAnalysisJob({ title: title.trim(), source_type: sourceType, source_url: sourceUrl.trim(), analysis_goal: goals, supplement_text: supplementText.trim() });
      if (file) await api.uploadViralAnalysisMaterial(created.id, file);
      const completed = await api.runViralAnalysisJob(created.id);
      selectedId.current = completed.id;
      setDetail(completed);
      setTitle(""); setSourceUrl(""); setSupplementText(""); setFile(null);
      setMessage("解析任务已完成，可查看结构化结果。 ");
      await loadJobs(1);
    } catch (error) {
      setMessage(explainError(error));
      await loadJobs(1);
    } finally { setBusyJobId(null); }
  }

  async function retry(job: ViralAnalysisJob) {
    if (!job.supplement_text.trim()) { setMessage("该任务缺少补充文本，当前未接入视频画面理解，无法运行。"); return; }
    setBusyJobId(job.id);
    try { const updated = await api.runViralAnalysisJob(job.id); setDetail(updated); await loadJobs(page); }
    catch (error) { setMessage(explainError(error)); await loadJobs(page); }
    finally { setBusyJobId(null); }
  }

  async function cancel(jobId: number) {
    setBusyJobId(jobId);
    try { const updated = await api.cancelViralAnalysisJob(jobId); setDetail((current) => current?.id === jobId ? updated : current); await loadJobs(page); }
    catch (error) { setMessage(explainError(error)); }
    finally { setBusyJobId(null); }
  }

  async function saveDraft(jobId: number) {
    setBusyJobId(jobId);
    try { const saved = await api.saveViralAnalysisDraft(jobId); setMessage(`已保存为视频内容草稿（ID：${saved.draft_id}）。`); }
    catch (error) { setMessage(explainError(error)); }
    finally { setBusyJobId(null); }
  }

  async function startInspiration(job: ViralAnalysisJob) {
    const advice = job.result?.reuse_suggestions || job.result?.rewritten_script || "";
    setBusyJobId(job.id);
    try {
      await api.createInspirationSession({
        title: `爆款脚本延展：${job.title}`.slice(0, 200), linked_product_id: 0, linked_xhs_account_id: 0,
        goal_type: "script", tone: "自然真诚", extra_requirement: advice.slice(0, 1000)
      });
      onStartInspiration();
    } catch (error) { setMessage(explainError(error)); }
    finally { setBusyJobId(null); }
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return <section className="page-stack viral-page">
    <div className="page-heading horizontal-heading"><div><h1>爆款解析</h1><p>基于你补充的口播稿与观察笔记，拆解内容结构并生成可复用的脚本建议。</p></div><button className="secondary-button compact" type="button" onClick={() => void loadJobs(page)}><RefreshCw size={16} />刷新任务</button></div>
    {message ? <div className="form-message" role="status">{message}</div> : null}
    <div className="viral-user-workspace">
      <section className="panel viral-create-panel"><div className="panel-title"><h2><Sparkles size={18} />创建解析任务</h2><span>预计消耗 3 算力</span></div>
        <div className="form-grid"><label>任务名称<input aria-label="任务名称" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：护肤类爆款视频拆解" /></label><label>素材来源<select aria-label="素材来源" value={sourceType} onChange={(event) => setSourceType(event.target.value as ViralAnalysisSourceType)}><option value="text">文本观察</option><option value="link">视频链接</option><option value="upload">本地素材</option></select></label></div>
        {sourceType === "link" ? <label>参考链接<input aria-label="参考链接" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://..." /></label> : null}
        {sourceType === "upload" ? <label className="viral-file-field">上传参考素材<input aria-label="上传参考素材" type="file" accept="video/*,image/*,.pdf,.doc,.docx,.xls,.xlsx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><span>{file ? file.name : "可选视频、图片或资料文件，最大 200 MB"}</span></label> : null}
        <fieldset className="goal-fieldset"><legend>解析维度</legend><div>{goalOptions.map((goal) => <label key={goal.value}><input type="checkbox" checked={goals.includes(goal.value)} onChange={() => setGoals((current) => current.includes(goal.value) ? current.filter((item) => item !== goal.value) : [...current, goal.value])} />{goal.label}</label>)}</div></fieldset>
        <label>补充口播稿或观察笔记<textarea aria-label="补充口播稿或观察笔记" value={supplementText} onChange={(event) => setSupplementText(event.target.value)} placeholder="请写明你观察到的开头、内容节奏、卖点与结尾引导。当前还未接入视频画面理解。" /></label>
        <button className="primary-button" type="button" disabled={busyJobId !== null} onClick={() => void createAndRun()}>{busyJobId === -1 ? <Loader2 size={16} className="spin" /> : <Play size={16} />}创建并开始解析</button>
      </section>
      <section className="panel viral-detail-panel"><div className="panel-title"><h2>解析结果</h2>{detail ? <span className={`viral-status ${detail.status}`}>{statusText(detail.status)}</span> : null}</div>
        {detail ? <><div className="viral-detail-meta"><strong>{detail.title}</strong><span>{detail.source_type === "upload" ? "已上传素材" : detail.source_type === "link" ? "视频链接" : "文本观察"}</span><span>{detail.materials?.length ?? 0} 份素材</span></div><ViralAnalysisResult result={detail.result} emptyText={detail.status === "processing" ? "任务正在解析中，请勿重复提交。" : "任务尚未生成解析结果。"} /><div className="primary-row"><button className="secondary-button" type="button" disabled={busyJobId === detail.id || !["pending", "failed"].includes(detail.status)} onClick={() => void retry(detail)}><Play size={16} />{detail.status === "failed" ? "重试解析" : "开始解析"}</button><button className="quiet-danger" type="button" disabled={busyJobId === detail.id || !["pending", "failed", "processing"].includes(detail.status)} onClick={() => void cancel(detail.id)}><CircleStop size={16} />取消任务</button>{detail.status === "completed" ? <><button className="secondary-button" type="button" disabled={busyJobId === detail.id} onClick={() => void saveDraft(detail.id)}><Save size={16} />保存视频草稿</button><button className="secondary-button" type="button" disabled={busyJobId === detail.id} onClick={() => void startInspiration(detail)}><Lightbulb size={16} />转入灵感对话</button></> : null}</div></> : <div className="empty-list-state">从左侧任务列表选择一项查看详情。</div>}
      </section>
    </div>
    <section className="panel viral-job-list"><div className="panel-title"><h2>我的解析任务</h2><span>{total} 项</span></div>{isLoading ? <div className="inspiration-session-skeleton"><span /><span /><span /></div> : jobs.length ? <div className="viral-job-rows">{jobs.map((job) => <button key={job.id} type="button" className={detail?.id === job.id ? "viral-job-row active" : "viral-job-row"} onClick={() => void selectJob(job.id)}><span><strong>{job.title}</strong><small>{job.source_type === "upload" ? "本地素材" : job.source_type === "link" ? "视频链接" : "文本观察"}</small></span><span className={`viral-status ${job.status}`}>{statusText(job.status)}</span></button>)}</div> : <div className="empty-list-state">还没有解析任务。</div>}<div className="inspiration-pagination"><button className="table-action compact" type="button" disabled={page <= 1 || isLoading} onClick={() => void loadJobs(page - 1)}><ChevronLeft size={15} />上一页</button><span>第 {page} 页 / 共 {total} 项</span><button className="table-action compact" type="button" disabled={page >= pageCount || isLoading} onClick={() => void loadJobs(page + 1)}>下一页<ChevronRight size={15} /></button></div></section>
  </section>;
}
