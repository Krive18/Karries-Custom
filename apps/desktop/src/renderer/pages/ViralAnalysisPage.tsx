import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleStop,
  ExternalLink,
  FileSearch,
  FileVideo,
  FolderOpen,
  History,
  Image as ImageIcon,
  Lightbulb,
  Loader2,
  Play,
  RefreshCw,
  Save,
  Sparkles,
  X
} from "lucide-react";

import { ApiRequestError, api } from "../api/client";
import { MaterialLibraryPicker } from "../components/material/MaterialLibraryPicker";
import { ViralAnalysisResult } from "../components/viral/ViralAnalysisResult";
import type {
  MaterialAsset,
  ViralAnalysisAgentHandoff,
  ViralAnalysisGoal,
  ViralAnalysisJob,
  ViralAnalysisMaterial,
  ViralAnalysisSourceType
} from "../types";

const pageSize = 20;
const historyExpandedStorageKey = "viral-analysis-history-expanded";
const uploadAccept = ".jpg,.jpeg,.png,.webp,.mp4,.mov,image/jpeg,image/png,image/webp,video/mp4,video/quicktime";
const goalOptions: Array<{ value: ViralAnalysisGoal; label: string }> = [
  { value: "hook", label: "开场钩子" }, { value: "structure", label: "内容结构" },
  { value: "rhythm", label: "镜头节奏" }, { value: "script", label: "脚本拆解" },
  { value: "selling", label: "卖点" }, { value: "reuse", label: "复用建议" },
  { value: "setting", label: "布景分析" }, { value: "lighting", label: "光影分析" }
];
type ViralReferenceSource = ViralAnalysisSourceType | "library";
type OperationPhase = "creating" | "uploading" | "attaching" | "running" | "cancelling" | "saving" | "inspiration";
type ActiveOperation = { phase: OperationPhase; jobId: number | null } | null;

function statusText(status: ViralAnalysisJob["status"]) {
  return ({ pending: "待解析", processing: "解析中", completed: "已完成", failed: "解析失败，可重试", cancelled: "已取消" })[status];
}

function phaseText(phase: OperationPhase) {
  return ({ creating: "创建中", uploading: "上传中", attaching: "关联素材中", running: "解析中", cancelling: "取消中", saving: "保存中", inspiration: "正在转入 Karries AI" })[phase];
}

function isSuccessMessage(message: string) {
  return [
    "解析任务已完成",
    "已保存至",
    "该解析结果已收藏",
    "爆款解析上下文已带入"
  ].some((prefix) => message.startsWith(prefix));
}

function explainError(error: unknown) {
  if (error instanceof ApiRequestError) {
    if (error.status === 413) return "素材超过 200 MB 限制，请压缩后重新上传。";
    if (error.status === 409) return "当前任务状态已变化，请刷新后重试。";
    if (error.status === 502) return "解析服务暂时不可用，任务可稍后重试。";
    if (error.code === "CAPABILITY_UNAVAILABLE") return "当前任务缺少可解析的视频或文字内容。";
  }
  return error instanceof Error ? error.message : "操作未完成，请稍后重试。";
}

function toParams(page: number) { return new URLSearchParams({ page: String(page), page_size: String(pageSize) }); }
function needsMaterialUpload(job: ViralAnalysisJob) {
  return job.source_type === "upload"
    && Array.isArray(job.materials)
    && job.materials.length === 0
    && ["pending", "failed"].includes(job.status);
}
function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
function materialTypeLabel(fileType: ViralAnalysisMaterial["file_type"]) {
  if (fileType === "video") return "视频";
  if (fileType === "image") return "图片";
  if (fileType === "document") return "文档";
  return "文件";
}
type ViralAnalysisPageProps = {
  onStartInspiration: (handoff: ViralAnalysisAgentHandoff) => void;
};

const referenceUrlPattern = /https?:\/\/[^\s<>"']+/i;

function extractReferenceVideoUrl(sourceText: string) {
  const match = sourceText.trim().match(referenceUrlPattern);
  if (!match) return "";
  const candidate = match[0].replace(/[。；，、！？!?,;:）)\]}】>]+$/u, "");
  try {
    const url = new URL(candidate);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : "";
  } catch {
    return "";
  }
}

export function ViralAnalysisPage({ onStartInspiration }: ViralAnalysisPageProps) {
  const [jobs, setJobs] = useState<ViralAnalysisJob[]>([]);
  const [detail, setDetail] = useState<ViralAnalysisJob | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState(() => {
    try {
      return window.localStorage.getItem(historyExpandedStorageKey) === "1";
    } catch {
      return false;
    }
  });
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1); const [total, setTotal] = useState(0); const [isLoading, setIsLoading] = useState(true);
  const [operation, setOperation] = useState<ActiveOperation>(null);
  const [message, setMessage] = useState(""); const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<ViralReferenceSource>("upload"); const [sourceUrl, setSourceUrl] = useState("");
  const [supplementText, setSupplementText] = useState(""); const [goals, setGoals] = useState<ViralAnalysisGoal[]>(["hook", "structure", "script", "reuse"]);
  const estimatedCreditCost = goals.includes("setting") || goals.includes("lighting") ? 120 : 100;
  const [file, setFile] = useState<File | null>(null);
  const [libraryAsset, setLibraryAsset] = useState<MaterialAsset | null>(null);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [previewMaterial, setPreviewMaterial] = useState<ViralAnalysisMaterial | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const listRequest = useRef(0); const detailRequest = useRef(0); const selectedId = useRef<number | null>(null);
  const previewRequest = useRef(0); const previewUrlRef = useRef("");
  const isBusy = operation !== null;
  const detailIsProcessing = Boolean(
    detail
      && (
        detail.status === "processing"
        || (operation?.phase === "running" && operation.jobId === detail.id)
      ),
  );
  const referenceVideoUrl = detail?.source_type === "link"
    ? extractReferenceVideoUrl(detail.source_url)
    : "";

  const writeSelectedDetail = useCallback((job: ViralAnalysisJob) => {
    if (selectedId.current === job.id) {
      setDetail(job);
      setDetailLoading(false);
    }
  }, []);

  const closeReferencePreview = useCallback(() => {
    ++previewRequest.current;
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = "";
    setPreviewMaterial(null);
    setPreviewUrl("");
    setPreviewError("");
    setPreviewLoading(false);
  }, []);

  useEffect(() => () => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
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
    closeReferencePreview();
    const requestId = ++detailRequest.current; selectedId.current = jobId; setDetail(null); setDetailLoading(true); setFile(null);
    try {
      const job = await api.getViralAnalysisJob(jobId);
      if (requestId === detailRequest.current && selectedId.current === jobId) { setDetail(job); setDetailLoading(false); setMessage(""); }
    } catch (error) { if (requestId === detailRequest.current && selectedId.current === jobId) { setDetailLoading(false); setMessage(explainError(error)); } }
  }, [closeReferencePreview, isBusy]);

  async function openReferencePreview(material: ViralAnalysisMaterial) {
    if (!detail || !["image", "video"].includes(material.file_type)) return;
    const jobId = detail.id;
    const requestId = ++previewRequest.current;
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = "";
    setPreviewMaterial(material);
    setPreviewUrl("");
    setPreviewError("");
    setPreviewLoading(true);
    try {
      const blob = await api.getViralAnalysisMaterialBlob(jobId, material.id);
      if (requestId !== previewRequest.current) return;
      const objectUrl = URL.createObjectURL(blob);
      previewUrlRef.current = objectUrl;
      setPreviewUrl(objectUrl);
    } catch (error) {
      if (requestId === previewRequest.current) setPreviewError(explainError(error));
    } finally {
      if (requestId === previewRequest.current) setPreviewLoading(false);
    }
  }

  async function runCreatedJob(created: ViralAnalysisJob) {
    setOperation({ phase: "running", jobId: created.id });
    const completed = await api.runViralAnalysisJob(created.id);
    writeSelectedDetail(completed);
    return completed;
  }

  async function uploadMaterial(created: ViralAnalysisJob, uploadFile: File) {
    setOperation({ phase: "uploading", jobId: created.id });
    try {
      const uploadedMaterial = await api.uploadViralAnalysisMaterial(created.id, uploadFile);
      const uploadedJob = { ...created, materials: [uploadedMaterial] };
      writeSelectedDetail(uploadedJob);
      return uploadedJob;
    } catch (error) {
      writeSelectedDetail(created);
      throw error;
    }
  }

  async function attachLibraryMaterial(created: ViralAnalysisJob, asset: MaterialAsset) {
    setOperation({ phase: "attaching", jobId: created.id });
    try {
      const selectedMaterial = await api.selectViralAnalysisLibraryMaterial(
        created.id,
        asset.id
      );
      const attachedJob = { ...created, materials: [selectedMaterial] };
      writeSelectedDetail(attachedJob);
      return attachedJob;
    } catch (error) {
      writeSelectedDetail(created);
      throw error;
    }
  }

  async function createAndRun() {
    if (isBusy) return;
    if (!title.trim()) { setMessage("请填写任务名称。"); return; }
    if (sourceType === "upload" && !file) { setMessage("上传素材类型需要选择一个本地文件。"); return; }
    if (sourceType === "library" && !libraryAsset) { setMessage("请从产品知识库选择一个图片或视频素材。"); return; }
    if (sourceType === "link" && !sourceUrl.trim()) {
      setMessage("请粘贴视频分享口令或视频链接。");
      return;
    }
    if (sourceType === "text" && !supplementText.trim()) {
      setMessage("文本任务需要补充口播稿、观察笔记等可分析内容。");
      return;
    }
    setOperation({ phase: "creating", jobId: null });
    let latestDetail: ViralAnalysisJob | undefined;
    try {
      const normalizedSourceUrl = sourceType === "link"
        ? extractReferenceVideoUrl(sourceUrl) || sourceUrl.trim()
        : sourceUrl.trim();
      const created = await api.createViralAnalysisJob({ title: title.trim(), source_type: sourceType === "library" ? "upload" : sourceType, source_url: normalizedSourceUrl, analysis_goal: goals, supplement_text: supplementText.trim() });
      selectedId.current = created.id; ++detailRequest.current; setDetail(created); setDetailLoading(false);
      latestDetail = created;
      let runnableJob = created;
      if (sourceType === "upload" && file) {
        runnableJob = await uploadMaterial(created, file);
        latestDetail = runnableJob;
      } else if (sourceType === "library" && libraryAsset) {
        runnableJob = await attachLibraryMaterial(created, libraryAsset);
        latestDetail = runnableJob;
      }
      latestDetail = await runCreatedJob(runnableJob);
      setTitle(""); setSourceUrl(""); setSupplementText(""); setFile(null); setLibraryAsset(null); setMessage("解析任务已完成，可查看结构化结果。");
    } catch (error) { setMessage(explainError(error)); }
    finally { setOperation(null); await loadJobs(1, latestDetail); }
  }

  async function retryUpload() {
    if (!detail || !needsMaterialUpload(detail) || !file || isBusy) return;
    setOperation({ phase: "uploading", jobId: detail.id });
    let latestDetail: ViralAnalysisJob | undefined;
    try {
      const uploadedJob = await uploadMaterial(detail, file);
      latestDetail = uploadedJob;
      latestDetail = await runCreatedJob(uploadedJob);
      setMessage("素材上传并解析完成。");
    }
    catch (error) { setMessage(explainError(error)); }
    finally { setOperation(null); await loadJobs(page, latestDetail); }
  }

  async function retry(job: ViralAnalysisJob) {
    if (isBusy) return;
    if (job.source_type === "link" && !job.source_url.trim()) {
      setMessage("该任务缺少视频分享口令或链接。");
      return;
    }
    if (job.source_type === "text" && !job.supplement_text.trim()) {
      setMessage("该任务缺少可供分析的文字内容。");
      return;
    }
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
    try {
      const saved = await api.createContentCollection({
        source_type: "viral_analysis",
        source_id: job.id
      });
      if (selectedId.current === job.id) {
        setMessage(
          saved.created
            ? `已保存至“发布管理 → 内容收藏”（收藏稿 #${saved.item.id}）。`
            : `该解析结果已收藏（收藏稿 #${saved.item.id}），可前往“发布管理 → 内容收藏”查看。`
        );
      }
    }
    catch (error) { setMessage(explainError(error)); }
    finally { setOperation(null); }
  }

  function startInspiration(job: ViralAnalysisJob) {
    if (isBusy) return;
    const result = job.result;
    if (!result || job.status !== "completed") {
      setMessage("请先完成爆款解析，再转入 Karries AI。");
      return;
    }
    const initialMessage = [
      "以下内容来自已完成的爆款解析。请只借鉴结构、节奏和转化方法，不照搬原文表达。",
      `参考任务：${job.title}`,
      result.hook_summary ? `开场钩子：\n${result.hook_summary}` : "",
      result.structure_summary ? `内容结构：\n${result.structure_summary}` : "",
      result.shot_rhythm ? `镜头节奏：\n${result.shot_rhythm}` : "",
      result.script_breakdown ? `脚本拆解：\n${result.script_breakdown}` : "",
      result.selling_points ? `卖点提炼：\n${result.selling_points}` : "",
      result.reuse_suggestions ? `复用建议：\n${result.reuse_suggestions}` : "",
      result.rewritten_script ? `参考改写：\n${result.rewritten_script}` : "",
      result.tags?.length ? `参考标签：${result.tags.join("、")}` : "",
      "请结合本会话中关联的产品资料，先提炼真实产品卖点，再生成一版原创小红书视频脚本。输出应包含开场钩子、分镜画面、口播或字幕、节奏安排和结尾行动引导。"
    ].filter(Boolean).join("\n\n");
    onStartInspiration({
      key: `viral:${job.id}:${job.update_time}`,
      source_job_id: job.id,
      source_title: job.title,
      session_draft: {
        title: `爆款脚本融合：${job.title}`.slice(0, 200),
        linked_product_id: 0,
        linked_xhs_account_id: 0,
        goal_type: "script",
        interaction_mode: "personalized",
        tone: "自然真诚",
        extra_requirement: "基于爆款结构融合关联产品，保留方法但不照搬表达，生成原创视频脚本。"
      },
      initial_message: initialMessage
    });
    setMessage("爆款解析上下文已带入 Karries AI，请选择要融合的产品资料。");
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const phase = operation?.phase;
  const detailNeedsMaterial = detail ? needsMaterialUpload(detail) : false;
  return (
    <section className="page-stack viral-page">
      <div className="page-heading horizontal-heading viral-page-heading compact-page-heading">
        <div className="page-heading-copy">
          <h1>一键拆解爆款视频，生成 AI 视频提示词。</h1>
        </div>
        <button className="secondary-button compact" type="button" disabled={isBusy} onClick={() => void loadJobs(page)}>
          <RefreshCw size={16} aria-hidden="true" />
          刷新任务
        </button>
      </div>

      {phase ? <div className="form-message" role="status">{phaseText(phase)}</div> : null}
      {message ? (
        <div
          className={`form-message${isSuccessMessage(message) ? " success" : ""}`}
          role="status"
        >
          {message}
        </div>
      ) : null}

      <div className="viral-user-workspace" aria-label="爆款解析工作区">
        <section className="panel viral-create-panel">
          <div className="panel-title">
            <div>
              <span className="section-step">01</span>
              <h2><Sparkles size={18} aria-hidden="true" />创建解析任务</h2>
            </div>
            <span className="credit-estimate">预计 {estimatedCreditCost} 算力</span>
          </div>

          <div className="viral-form-section">
            <h3>参考内容</h3>
            <div className="form-grid viral-title-source-grid">
              <label>
                任务名称
                <input aria-label="任务名称" disabled={isBusy} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：新品种草视频拆解" />
              </label>
              <label>
                素材来源
                <select aria-label="素材来源" disabled={isBusy} value={sourceType} onChange={(event) => {
                  const next = event.target.value as ViralReferenceSource;
                  setSourceType(next);
                  if (next !== "upload") setFile(null);
                  if (next !== "library") setLibraryAsset(null);
                }}>
                  <option value="text">文本观察</option>
                  <option value="link">视频链接</option>
                  <option value="upload">本地素材</option>
                  <option value="library">产品知识库</option>
                </select>
              </label>
            </div>
            {sourceType === "link" ? (
              <label>
                参考链接
                <input aria-label="参考链接" disabled={isBusy} value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://..." />
              </label>
            ) : null}
            {sourceType === "upload" ? (
              <label className="viral-file-field">
                上传参考素材
                <input aria-label="上传参考素材" disabled={isBusy} type="file" accept={uploadAccept} onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                <span>{file ? file.name : "支持 JPG、PNG、WEBP、MP4、MOV，最大 200 MB"}</span>
              </label>
            ) : null}
            {sourceType === "library" ? (
              <div className="viral-library-source">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={isBusy}
                  onClick={() => setLibraryPickerOpen(true)}
                >
                  <FolderOpen size={16} aria-hidden="true" />
                  从产品知识库选择
                </button>
                <div className={libraryAsset ? "viral-library-selection selected" : "viral-library-selection"}>
                  <span>{libraryAsset ? libraryAsset.file_name : "尚未选择参考素材"}</span>
                  <small>{libraryAsset ? (libraryAsset.file_type === "video" ? "视频素材" : "图片素材") : "支持图片和视频，每个解析任务选择 1 份"}</small>
                </div>
              </div>
            ) : null}
          </div>

          <div className="viral-form-section">
            <h3>解析目标</h3>
            <fieldset className="goal-fieldset" disabled={isBusy}>
              <legend>选择需要重点拆解的维度</legend>
              <div>
                {goalOptions.map((goal) => (
                  <label className={goals.includes(goal.value) ? "active" : ""} key={goal.value}>
                    <input type="checkbox" checked={goals.includes(goal.value)} onChange={() => setGoals((current) => current.includes(goal.value) ? current.filter((item) => item !== goal.value) : [...current, goal.value])} />
                    {goal.label}
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

          <div className="viral-form-section">
            <h3>内容补充</h3>
            <label>
              口播稿或观察笔记
              <textarea aria-label="补充口播稿或观察笔记" disabled={isBusy} value={supplementText} onChange={(event) => setSupplementText(event.target.value)} placeholder={sourceType === "upload" || sourceType === "library" ? "选填。AI 会直接理解视频画面、口播、节奏和场景变化；可补充你特别关注的内容。" : "请补充开头、内容节奏、核心卖点和结尾引导。"} rows={6} />
            </label>
          </div>

          <button className="primary-button viral-run-button" type="button" disabled={isBusy} onClick={() => void createAndRun()}>
            {phase === "creating" || phase === "uploading" || phase === "attaching" || phase === "running" ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
            {phase ? phaseText(phase) : "创建并开始解析"}
          </button>
        </section>

        <section className="panel viral-detail-panel">
          <div className="panel-title">
            <div>
              <span className="section-step">02</span>
              <h2><FileSearch size={18} aria-hidden="true" />解析结果</h2>
            </div>
            {detail ? (
              <span className={`viral-status ${detailIsProcessing ? "processing" : detail.status}`}>
                {statusText(detailIsProcessing ? "processing" : detail.status)}
              </span>
            ) : null}
          </div>
          {detailLoading ? (
            <div className="empty-list-state viral-result-empty" role="status">正在加载任务详情</div>
          ) : detail ? (
            <div className="viral-detail-body">
              <div className="viral-detail-meta">
                <strong>{detail.title}</strong>
                <span>{detail.source_type === "upload" ? "参考素材" : detail.source_type === "link" ? "视频链接" : "文本观察"}</span>
                <span>{detail.materials?.length ?? 0} 份素材</span>
              </div>
              {detail.source_type === "upload" ? (
                <section className="viral-reference-section" aria-labelledby="viral-reference-title">
                  <h3 id="viral-reference-title">本次参考素材</h3>
                  {detail.materials?.length ? (
                    <div className="viral-reference-list">
                      {detail.materials.map((material) => (
                        <article className="viral-reference-card" key={material.id}>
                          <span className="viral-reference-icon" aria-hidden="true">
                            {material.file_type === "video" ? <FileVideo size={20} /> : <ImageIcon size={20} />}
                          </span>
                          <span className="viral-reference-copy">
                            <strong title={material.file_name}>{material.file_name}</strong>
                            <small>{materialTypeLabel(material.file_type)} · {formatFileSize(material.file_size)}</small>
                          </span>
                          {["image", "video"].includes(material.file_type) ? (
                            <button
                              className="secondary-button compact"
                              type="button"
                              aria-label={`预览参考素材 ${material.file_name}`}
                              onClick={() => void openReferencePreview(material)}
                            >
                              <Play size={15} aria-hidden="true" />
                              预览
                            </button>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="viral-reference-missing">
                      {detailNeedsMaterial ? "参考素材尚未上传" : "历史参考素材文件暂时无法定位"}
                    </p>
                  )}
                </section>
              ) : detail.source_type === "link" && detail.source_url ? (
                <section className="viral-reference-section" aria-labelledby="viral-reference-title">
                  <h3 id="viral-reference-title">本次参考视频</h3>
                  {referenceVideoUrl ? (
                    <a
                      className="viral-reference-link"
                      href={referenceVideoUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`打开原视频：${referenceVideoUrl}`}
                    >
                      <span>{referenceVideoUrl}</span>
                      <ExternalLink size={15} aria-hidden="true" />
                    </a>
                  ) : (
                    <p className="viral-reference-missing">分享内容中未找到可打开的视频链接</p>
                  )}
                </section>
              ) : null}
              {detailNeedsMaterial ? (
                <>
                  <p className="viral-upload-retry-note">该任务还没有可解析的素材，请重新选择文件；上传完成后会继续解析。</p>
                  <label className="viral-file-field">
                    重新选择解析素材
                    <input aria-label="重新选择解析素材" disabled={isBusy} type="file" accept={uploadAccept} onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                    <span>{file ? file.name : "请选择原任务对应的图片或视频"}</span>
                  </label>
                </>
              ) : null}
              <ViralAnalysisResult result={detail.result} emptyText={detailIsProcessing ? "任务正在解析中，请勿重复提交。" : "任务尚未生成解析结果。"} />
              {detailIsProcessing ? (
                <div className="viral-detail-progress" role="status" aria-label="解析进度">
                  <Loader2 size={18} className="spin" aria-hidden="true" />
                  <div>
                    <strong>正在解析内容</strong>
                    <span>AI 正在理解画面、布景、光影和脚本，请稍候。</span>
                  </div>
                </div>
              ) : (
                <div className="primary-row viral-detail-actions">
                  {detailNeedsMaterial ? (
                    <button className="primary-button" type="button" disabled={isBusy || !file} onClick={() => void retryUpload()}>
                      {phase === "uploading" ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
                      重新上传并继续解析
                    </button>
                  ) : null}
                  <button className="secondary-button" type="button" disabled={isBusy || !["pending", "failed"].includes(detail.status) || detailNeedsMaterial} onClick={() => void retry(detail)}>
                    <Play size={16} aria-hidden="true" />
                    {detail.status === "failed" ? "重试解析" : "开始解析"}
                  </button>
                  <button className="quiet-danger" type="button" disabled={isBusy || detail.status !== "pending"} onClick={() => void cancel(detail)}>
                    <CircleStop size={16} aria-hidden="true" />
                    取消任务
                  </button>
                  {detail.status === "completed" ? (
                    <>
                      <button className="secondary-button" type="button" disabled={isBusy} onClick={() => void saveDraft(detail)}><Save size={16} aria-hidden="true" />保存视频草稿</button>
                      <button className="secondary-button" type="button" disabled={isBusy} onClick={() => startInspiration(detail)}><Lightbulb size={16} aria-hidden="true" />转入 Karries AI</button>
                    </>
                  ) : null}
                </div>
              )}
            </div>
          ) : (
            <div className="viral-result-welcome">
              <span><FileSearch size={28} aria-hidden="true" /></span>
              <h3>等待解析内容</h3>
              <p>创建新任务，或从下方历史任务中选择一项查看完整拆解。</p>
              <div>
                <small>开场钩子</small>
                <small>结构节奏</small>
                <small>脚本复用</small>
              </div>
            </div>
          )}
        </section>
      </div>

      <section className={historyExpanded ? "panel viral-job-list" : "panel viral-job-list collapsed"}>
        <div className="panel-title">
          <h2><History size={18} aria-hidden="true" />历史解析任务</h2>
          <button
            className="viral-history-toggle"
            type="button"
            aria-expanded={historyExpanded}
            aria-label={historyExpanded ? "收起历史解析任务" : "展开历史解析任务"}
            onClick={() => {
              setHistoryExpanded((current) => {
                const next = !current;
                try {
                  window.localStorage.setItem(historyExpandedStorageKey, next ? "1" : "0");
                } catch {
                  // The control remains usable when browser storage is unavailable.
                }
                return next;
              });
            }}
          >
            <span>{total} 项</span>
            <span>{historyExpanded ? "收起" : "展开"}</span>
            <ChevronDown
              className={historyExpanded ? "expanded" : ""}
              size={16}
              aria-hidden="true"
            />
          </button>
        </div>
        {historyExpanded ? (
          <div className="viral-history-content">
            {isLoading ? <div className="inspiration-session-skeleton"><span /><span /><span /></div> : jobs.length ? (
              <div className="viral-job-rows">
                {jobs.map((job) => (
                  <button key={job.id} type="button" disabled={isBusy} className={detail?.id === job.id ? "viral-job-row active" : "viral-job-row"} onClick={() => void selectJob(job.id)}>
                    <span>
                      <strong>{job.title}</strong>
                      <small>{job.source_type === "upload" ? "参考素材" : job.source_type === "link" ? "视频链接" : "文本观察"}</small>
                    </span>
                    <small className="viral-job-goals">{job.analysis_goal.map((goal) => goalOptions.find((item) => item.value === goal)?.label).filter(Boolean).slice(0, 3).join(" · ")}</small>
                    <span className={`viral-status ${job.status}`}>{statusText(job.status)}</span>
                  </button>
                ))}
              </div>
            ) : <div className="empty-list-state viral-history-empty">还没有解析任务，创建后会在这里保留记录。</div>}
            <div className="inspiration-pagination">
              <button className="table-action compact" type="button" disabled={isBusy || page <= 1 || isLoading} onClick={() => void loadJobs(page - 1)}><ChevronLeft size={15} aria-hidden="true" />上一页</button>
              <span>第 {page} 页 / 共 {total} 项</span>
              <button className="table-action compact" type="button" disabled={isBusy || page >= pageCount || isLoading} onClick={() => void loadJobs(page + 1)}>下一页<ChevronRight size={15} aria-hidden="true" /></button>
            </div>
          </div>
        ) : null}
      </section>

      <MaterialLibraryPicker
        open={libraryPickerOpen}
        allowedTypes={["image", "video"]}
        initialSelection={libraryAsset ? [libraryAsset] : []}
        selectionLimit={1}
        onClose={() => setLibraryPickerOpen(false)}
        onConfirm={(assets) => {
          setLibraryAsset(assets[0] ?? null);
          setLibraryPickerOpen(false);
          setMessage("");
        }}
      />
      {previewMaterial ? (
        <div
          className="material-picker-backdrop material-preview-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeReferencePreview();
          }}
        >
          <section
            className="material-preview-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="viral-material-preview-title"
          >
            <header>
              <div>
                <strong id="viral-material-preview-title">预览参考素材 {previewMaterial.file_name}</strong>
                <span>{materialTypeLabel(previewMaterial.file_type)} · {formatFileSize(previewMaterial.file_size)}</span>
              </div>
              <button className="icon-button" type="button" aria-label="关闭参考素材预览" onClick={closeReferencePreview}>
                <X size={18} aria-hidden="true" />
              </button>
            </header>
            <div className="material-preview-stage">
              {previewLoading ? (
                <div className="material-preview-state" role="status">
                  <Loader2 size={28} className="spin" aria-hidden="true" />
                  正在加载参考素材
                </div>
              ) : previewError ? (
                <div className="material-preview-state error" role="alert">{previewError}</div>
              ) : previewUrl && previewMaterial.file_type === "video" ? (
                <video src={previewUrl} controls playsInline preload="metadata" />
              ) : previewUrl ? (
                <img src={previewUrl} alt={previewMaterial.file_name} />
              ) : null}
            </div>
            <footer>
              <button className="primary-button" type="button" onClick={closeReferencePreview}>关闭</button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
