import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, CircleStop, Lightbulb, Loader2, Play, RefreshCw, Save, Sparkles } from "lucide-react";

import { ApiRequestError, api } from "../api/client";
import { ViralAnalysisResult } from "../components/viral/ViralAnalysisResult";
import type { ViralAnalysisGoal, ViralAnalysisJob, ViralAnalysisSourceType } from "../types";

const pageSize = 20;
const uploadAccept = ".jpg,.jpeg,.png,.webp,.mp4,.mov,image/jpeg,image/png,image/webp,video/mp4,video/quicktime";
const goalOptions: Array<{ value: ViralAnalysisGoal; label: string }> = [
  { value: "hook", label: "开场钩子" }, { value: "structure", label: "内容结构" },
  { value: "rhythm", label: "镜头节奏" }, { value: "script", label: "脚本拆解" },
  { value: "selling", label: "卖点" }, { value: "reuse", label: "复用建议" }
];
type OperationPhase = "creating" | "uploading" | "running" | "cancelling" | "saving" | "inspiration";
type ActiveOperation = { phase: OperationPhase; jobId: number | null } | null;

function statusText(status: ViralAnalysisJob["status"]) {
  return ({ pending: "待解析", processing: "解析中", completed: "已完成", failed: "解析失败，可重试", cancelled: "已取消" })[status];
}

function phaseText(phase: OperationPhase) {
  return ({ creating: "创建中", uploading: "上传中", running: "解析中", cancelling: "取消中", saving: "保存中", inspiration: "正在转入灵感对话" })[phase];
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

function toParams(page: number) { return new URLSearchParams({ page: String(page), page_size: String(pageSize) }); }
type ViralAnalysisPageProps = { onStartInspiration: () => void };

export function ViralAnalysisPage({ onStartInspiration }: ViralAnalysisPageProps) {
  const [jobs, setJobs] = useState<ViralAnalysisJob[]>([]);
  const [detail, setDetail] = useState<ViralAnalysisJob | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1); const [total, setTotal] = useState(0); const [isLoading, setIsLoading] = useState(true);
  const [operation, setOperation] = useState<ActiveOperation>(null); const [pendingUploadJobId, setPendingUploadJobId] = useState<number | null>(null);
  const [message, setMessage] = useState(""); const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<ViralAnalysisSourceType>("text"); const [sourceUrl, setSourceUrl] = useState("");
  const [supplementText, setSupplementText] = useState(""); const [goals, setGoals] = useState<ViralAnalysisGoal[]>(["hook", "structure", "script", "reuse"]);
  const [file, setFile] = useState<File | null>(null);
  const listRequest = useRef(0); const detailRequest = useRef(0); const selectedId = useRef<number | null>(null);
  const isBusy = operation !== null;

  const writeSelectedDetail = useCallback((job: ViralAnalysisJob) => {
    if (selectedId.current === job.id) {
      setDetail(job);
      setDetailLoading(false);
    }
  }, []);

  const loadJobs = useCallback(async (requestedPage = 1, selectedDetail?: ViralAnalysisJob) => {
    const requestId = ++listRequest.current; setIsLoading(true);
    try {
      const result = await api.listViralAnalysisJobs(toParams(requestedPage));
      if (requestId !== listRequest.current) return;
      if (!result.items.length && result.total > 0 && requestedPage > 1) { void loadJobs(requestedPage - 1); return; }
      const nextJobs = selectedDetail && selectedId.current === selectedDetail.id
        ? result.items.map((item) => item.id === selectedDetail.id ? selectedDetail : item)
        : result.items;
      setJobs(nextJobs); setPage(result.page); setTotal(result.total);
      const selectedJob = nextJobs.find((item) => item.id === selectedId.current);
      if (selectedId.current && !selectedJob) { selectedId.current = null; ++detailRequest.current; setDetail(null); setDetailLoading(false); }
      if (selectedJob) { ++detailRequest.current; setDetail(selectedJob); setDetailLoading(false); }
    } catch (error) { if (requestId === listRequest.current) setMessage(explainError(error)); }
    finally { if (requestId === listRequest.current) setIsLoading(false); }
  }, []);

  useEffect(() => { void loadJobs(); }, [loadJobs]);

  const selectJob = useCallback(async (jobId: number) => {
    if (isBusy) return;
    const requestId = ++detailRequest.current; selectedId.current = jobId; setDetail(null); setDetailLoading(true); setPendingUploadJobId(null);
    try {
      const job = await api.getViralAnalysisJob(jobId);
      if (requestId === detailRequest.current && selectedId.current === jobId) { setDetail(job); setDetailLoading(false); setMessage(""); }
    } catch (error) { if (requestId === detailRequest.current && selectedId.current === jobId) { setDetailLoading(false); setMessage(explainError(error)); } }
  }, [isBusy]);

  async function runCreatedJob(created: ViralAnalysisJob) {
    setOperation({ phase: "running", jobId: created.id });
    const completed = await api.runViralAnalysisJob(created.id);
    writeSelectedDetail(completed);
    setPendingUploadJobId(null);
    return completed;
  }

  async function uploadAndRun(created: ViralAnalysisJob, uploadFile: File) {
    setOperation({ phase: "uploading", jobId: created.id });
    try {
      await api.uploadViralAnalysisMaterial(created.id, uploadFile);
      setPendingUploadJobId(null);
    } catch (error) {
      setPendingUploadJobId(created.id);
      writeSelectedDetail(created);
      throw error;
    }
    return runCreatedJob(created);
  }

  async function createAndRun() {
    if (isBusy) return;
    if (!title.trim()) { setMessage("请填写任务名称。"); return; }
    if (!supplementText.trim()) { setMessage("请补充口播稿或观察笔记；当前尚未接入视频画面理解。"); return; }
    if (sourceType === "upload" && !file) { setMessage("上传素材类型需要选择一个本地文件。"); return; }
    setOperation({ phase: "creating", jobId: null });
    let latestDetail: ViralAnalysisJob | undefined;
    try {
      const created = await api.createViralAnalysisJob({ title: title.trim(), source_type: sourceType, source_url: sourceUrl.trim(), analysis_goal: goals, supplement_text: supplementText.trim() });
      selectedId.current = created.id; ++detailRequest.current; setDetail(created); setDetailLoading(false);
      latestDetail = sourceType === "upload" && file ? await uploadAndRun(created, file) : await runCreatedJob(created);
      setTitle(""); setSourceUrl(""); setSupplementText(""); setFile(null); setMessage("解析任务已完成，可查看结构化结果。");
    } catch (error) { setMessage(explainError(error)); }
    finally { setOperation(null); await loadJobs(1, latestDetail); }
  }

  async function retryUpload() {
    if (!detail || pendingUploadJobId !== detail.id || !file || isBusy) return;
    setOperation({ phase: "uploading", jobId: detail.id });
    let latestDetail: ViralAnalysisJob | undefined;
    try { latestDetail = await uploadAndRun(detail, file); setMessage("素材上传并解析完成。"); }
    catch (error) { setMessage(explainError(error)); }
    finally { setOperation(null); await loadJobs(page, latestDetail); }
  }

  async function retry(job: ViralAnalysisJob) {
    if (isBusy || !job.supplement_text.trim()) { if (!job.supplement_text.trim()) setMessage("该任务缺少补充文本，当前未接入视频画面理解，无法运行。"); return; }
    setOperation({ phase: "running", jobId: job.id });
    try { const updated = await api.runViralAnalysisJob(job.id); writeSelectedDetail(updated); await loadJobs(page, updated); }
    catch (error) { setMessage(explainError(error)); await loadJobs(page); }
    finally { setOperation(null); }
  }

  async function cancel(job: ViralAnalysisJob) {
    if (isBusy || job.status !== "pending") return;
    setOperation({ phase: "cancelling", jobId: job.id });
    try { const updated = await api.cancelViralAnalysisJob(job.id); writeSelectedDetail(updated); await loadJobs(page, updated); }
    catch (error) { setMessage(explainError(error)); await loadJobs(page); }
    finally { setOperation(null); }
  }

  async function saveDraft(job: ViralAnalysisJob) {
    if (isBusy) return;
    setOperation({ phase: "saving", jobId: job.id });
    try { const saved = await api.saveViralAnalysisDraft(job.id); if (selectedId.current === job.id) setMessage(`已保存为视频内容草稿（ID：${saved.draft_id}）。`); }
    catch (error) { setMessage(explainError(error)); }
    finally { setOperation(null); }
  }

  async function startInspiration(job: ViralAnalysisJob) {
    if (isBusy) return;
    setOperation({ phase: "inspiration", jobId: job.id });
    try {
      const advice = job.result?.reuse_suggestions || job.result?.rewritten_script || "";
      await api.createInspirationSession({ title: `爆款脚本延展：${job.title}`.slice(0, 200), linked_product_id: 0, linked_xhs_account_id: 0, goal_type: "script", tone: "自然真诚", extra_requirement: advice.slice(0, 1000) });
      if (selectedId.current === job.id) onStartInspiration();
    } catch (error) { setMessage(explainError(error)); }
    finally { setOperation(null); }
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const phase = operation?.phase;
  return <section className="page-stack viral-page">
    <div className="page-heading horizontal-heading"><div><h1>爆款解析</h1><p>基于补充的口播稿与观察笔记，拆解内容结构并生成可复用脚本建议。</p></div><button className="secondary-button compact" type="button" disabled={isBusy} onClick={() => void loadJobs(page)}><RefreshCw size={16} />刷新任务</button></div>
    {phase ? <div className="form-message" role="status">{phaseText(phase)}</div> : null}
    {message ? <div className="form-message" role="status">{message}</div> : null}
    <div className="viral-user-workspace"><section className="panel viral-create-panel"><div className="panel-title"><h2><Sparkles size={18} />创建解析任务</h2><span>预计消耗 3 算力</span></div>
      <div className="form-grid"><label>任务名称<input aria-label="任务名称" disabled={isBusy} value={title} onChange={(event) => setTitle(event.target.value)} /></label><label>素材来源<select aria-label="素材来源" disabled={isBusy} value={sourceType} onChange={(event) => { const next = event.target.value as ViralAnalysisSourceType; setSourceType(next); if (next !== "upload") setFile(null); }}><option value="text">文本观察</option><option value="link">视频链接</option><option value="upload">本地素材</option></select></label></div>
      {sourceType === "link" ? <label>参考链接<input aria-label="参考链接" disabled={isBusy} value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://..." /></label> : null}
      {sourceType === "upload" ? <label className="viral-file-field">上传参考素材<input aria-label="上传参考素材" disabled={isBusy} type="file" accept={uploadAccept} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><span>{file ? file.name : "仅支持 JPG、PNG、WEBP、MP4、MOV，最大 200 MB"}</span></label> : null}
      <fieldset className="goal-fieldset" disabled={isBusy}><legend>解析维度</legend><div>{goalOptions.map((goal) => <label key={goal.value}><input type="checkbox" checked={goals.includes(goal.value)} onChange={() => setGoals((current) => current.includes(goal.value) ? current.filter((item) => item !== goal.value) : [...current, goal.value])} />{goal.label}</label>)}</div></fieldset>
      <label>补充口播稿或观察笔记<textarea aria-label="补充口播稿或观察笔记" disabled={isBusy} value={supplementText} onChange={(event) => setSupplementText(event.target.value)} placeholder="请说明你观察到的开头、内容节奏、卖点与结尾引导。当前还未接入视频画面理解。" /></label>
      <button className="primary-button" type="button" disabled={isBusy} onClick={() => void createAndRun()}>{phase === "creating" || phase === "uploading" || phase === "running" ? <Loader2 size={16} className="spin" /> : <Play size={16} />}{phase ? phaseText(phase) : "创建并开始解析"}</button>
    </section>
    <section className="panel viral-detail-panel"><div className="panel-title"><h2>解析结果</h2>{detail ? <span className={`viral-status ${detail.status}`}>{statusText(detail.status)}</span> : null}</div>{detailLoading ? <div className="empty-list-state" role="status">正在加载任务详情</div> : detail ? <><div className="viral-detail-meta"><strong>{detail.title}</strong><span>{detail.source_type === "upload" ? "本地素材" : detail.source_type === "link" ? "视频链接" : "文本观察"}</span><span>{detail.materials?.length ?? 0} 份素材</span></div>{pendingUploadJobId === detail.id ? <p className="viral-upload-retry-note">素材上传未完成，已保留该任务；重新上传后会继续解析。</p> : null}<ViralAnalysisResult result={detail.result} emptyText={detail.status === "processing" ? "任务正在解析中，请勿重复提交。" : "任务尚未生成解析结果。"} /><div className="primary-row">{pendingUploadJobId === detail.id ? <button className="primary-button" type="button" disabled={isBusy || !file} onClick={() => void retryUpload()}>{phase === "uploading" ? <Loader2 size={16} className="spin" /> : <Play size={16} />}重新上传并继续解析</button> : null}<button className="secondary-button" type="button" disabled={isBusy || !["pending", "failed"].includes(detail.status) || pendingUploadJobId === detail.id} onClick={() => void retry(detail)}><Play size={16} />{detail.status === "failed" ? "重试解析" : "开始解析"}</button><button className="quiet-danger" type="button" disabled={isBusy || detail.status !== "pending"} onClick={() => void cancel(detail)}><CircleStop size={16} />取消任务</button>{detail.status === "completed" ? <><button className="secondary-button" type="button" disabled={isBusy} onClick={() => void saveDraft(detail)}><Save size={16} />保存视频草稿</button><button className="secondary-button" type="button" disabled={isBusy} onClick={() => void startInspiration(detail)}><Lightbulb size={16} />转入灵感对话</button></> : null}</div></> : <div className="empty-list-state">从下方任务列表选择一项查看详情。</div>}</section></div>
    <section className="panel viral-job-list"><div className="panel-title"><h2>我的解析任务</h2><span>{total} 项</span></div>{isLoading ? <div className="inspiration-session-skeleton"><span /><span /><span /></div> : jobs.length ? <div className="viral-job-rows">{jobs.map((job) => <button key={job.id} type="button" disabled={isBusy} className={detail?.id === job.id ? "viral-job-row active" : "viral-job-row"} onClick={() => void selectJob(job.id)}><span><strong>{job.title}</strong><small>{job.source_type === "upload" ? "本地素材" : job.source_type === "link" ? "视频链接" : "文本观察"}</small></span><span className={`viral-status ${job.status}`}>{statusText(job.status)}</span></button>)}</div> : <div className="empty-list-state">还没有解析任务。</div>}<div className="inspiration-pagination"><button className="table-action compact" type="button" disabled={isBusy || page <= 1 || isLoading} onClick={() => void loadJobs(page - 1)}><ChevronLeft size={15} />上一页</button><span>第 {page} 页 / 共 {total} 项</span><button className="table-action compact" type="button" disabled={isBusy || page >= pageCount || isLoading} onClick={() => void loadJobs(page + 1)}>下一页<ChevronRight size={15} /></button></div></section>
  </section>;
}
