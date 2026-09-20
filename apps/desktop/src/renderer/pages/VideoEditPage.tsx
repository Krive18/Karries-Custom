import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  Download,
  Eye,
  FileClock,
  FileImage,
  FileText,
  FileVideo2,
  Film,
  FolderOpen,
  LockKeyhole,
  Loader2,
  Music2,
  Scissors,
  Sparkles,
  Upload,
  X
} from "lucide-react";

import { api } from "../api/client";
import { RichContentReader } from "../components/content/RichContentReader";
import { dedupeMaterialAssets } from "../components/material/dedupeMaterialAssets";
import { MaterialLibraryPicker } from "../components/material/MaterialLibraryPicker";
import type {
  AgentVideoCreationHandoff,
  MaterialAsset,
  VideoEditJobCreate,
  VideoEditJobHistory,
  VideoEditJobView,
  VideoEditMaterial,
  VideoEditRequestSnapshot,
  VideoScriptOptimizeResult,
  VideoEditDeliveryAsset
} from "../types";
import { resolveVideoEditHistoryStatus } from "./videoEditHistoryStatus";


const LOCAL_UPLOAD_FOLDER_NAME = "视频创作本地上传";
const MATERIAL_LIST_COLLAPSE_THRESHOLD = 4;
const MATERIAL_LIST_EXPANDED_STORAGE_KEY = "video-edit-materials-expanded";


function materialFromLibrary(
  asset: MaterialAsset,
  isLocalUpload = false
): VideoEditMaterial {
  return {
    material_file_id: asset.id,
    file_name: asset.file_name,
    file_type: asset.file_type === "image" || asset.file_type === "video"
      ? asset.file_type
      : "document",
    file_path: "",
    mime_type: asset.mime_type,
    file_size: asset.file_size,
    remark: isLocalUpload ? "本地上传素材" : "产品知识库素材"
  };
}


function historyFromJob(job: VideoEditJobView): VideoEditJobHistory {
  const requestSnapshot: VideoEditRequestSnapshot = Object.assign({}, {
    creation_mode: job.creation_mode,
    creation_mode_label: job.creation_mode_label,
    credit_cost: job.credit_cost,
    job_title: job.job_title,
    post_title: job.post_title,
    post_body: job.post_body,
    post_tags: job.post_tags,
    script_text: job.script_text,
    requirement_text: job.requirement_text,
    materials: job.materials,
    xhs_account_id: job.xhs_account_id,
    xhs_account_name: job.xhs_account_name,
    planned_publish_time: job.planned_publish_time,
    submitted_at: job.create_time
  }, job.request_snapshot ?? {});
  if (
    (!Array.isArray(requestSnapshot.materials) || requestSnapshot.materials.length === 0)
    && job.materials.length > 0
  ) {
    requestSnapshot.materials = job.materials;
  }

  return {
    id: job.id,
    request_snapshot: requestSnapshot,
    creation_mode: job.creation_mode,
    creation_mode_label: job.creation_mode_label,
    credit_cost: job.credit_cost,
    status: job.status,
    status_name: job.status_name,
    status_text: job.status_text,
    delivery_versions: job.delivery_versions ?? [],
    delivery_assets: job.delivery_assets ?? [],
    revision_count: job.revision_count ?? 0,
    create_time: job.create_time,
    update_time: job.update_time,
    delivered_time: job.delivered_time
  };
}

function formatVideoEditDateTime(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString("zh-CN");
}


type VideoEditPageProps = {
  initialHandoff?: AgentVideoCreationHandoff | null;
  onInitialHandoffConsumed?: (key: string) => void;
};

type HistoryPreview = {
  objectUrl: string;
  fileName: string;
  mimeType: string;
};


export function VideoEditPage({
  initialHandoff = null,
  onInitialHandoffConsumed
}: VideoEditPageProps) {
  const handledHandoffKeyRef = useRef("");
  const localUploadInputRef = useRef<HTMLInputElement>(null);
  const historyPreviewUrlRef = useRef("");
  const [libraryAssets, setLibraryAssets] = useState<MaterialAsset[]>([]);
  const [localUploadAssetIds, setLocalUploadAssetIds] = useState<number[]>([]);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [jobTitle, setJobTitle] = useState("小红书视频制作需求");
  const [creationMode, setCreationMode] = useState<"standard" | "pro">("standard");
  const [scriptText, setScriptText] = useState("");
  const [requirementText, setRequirementText] = useState("");
  const [message, setMessage] = useState("");
  const [jobs, setJobs] = useState<VideoEditJobView[]>([]);
  const [historyDetail, setHistoryDetail] = useState<VideoEditJobHistory | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isUploadingLocal, setIsUploadingLocal] = useState(false);
  const [optimizationResult, setOptimizationResult] =
    useState<VideoScriptOptimizeResult | null>(null);
  const [optimizationAdjustment, setOptimizationAdjustment] = useState("");
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [historyPreview, setHistoryPreview] = useState<HistoryPreview | null>(null);
  const [historyActionLoading, setHistoryActionLoading] = useState("");
  const [materialsExpanded, setMaterialsExpanded] = useState(() => {
    try {
      return window.localStorage.getItem(MATERIAL_LIST_EXPANDED_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  const materials = useMemo(
    () => libraryAssets.map((asset) => materialFromLibrary(
      asset,
      localUploadAssetIds.includes(asset.id)
    )),
    [libraryAssets, localUploadAssetIds]
  );
  const hasCollapsibleMaterialList = materials.length > MATERIAL_LIST_COLLAPSE_THRESHOLD;
  const showMaterialList = materials.length > 0
    && (!hasCollapsibleMaterialList || materialsExpanded);
  const creationCreditCost = creationMode === "pro" ? 180 : 160;

  async function loadPage() {
    try {
      const nextJobs = await api.listVideoEditJobs();
      setJobs(nextJobs);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频创作记录加载失败");
    }
  }

  useEffect(() => {
    void loadPage();
  }, []);

  useEffect(() => () => {
    if (historyPreviewUrlRef.current) {
      URL.revokeObjectURL(historyPreviewUrlRef.current);
    }
  }, []);

  useEffect(() => {
    if (
      !initialHandoff
      || handledHandoffKeyRef.current === initialHandoff.key
    ) return;
    handledHandoffKeyRef.current = initialHandoff.key;
    setJobTitle(initialHandoff.job_title || "爆款融合视频创作");
    setScriptText(initialHandoff.script_text.trim());
    setRequirementText(initialHandoff.requirement_text.trim());
    setOptimizationResult(null);
    setMessage("已从 Karries AI 带入视频脚本，可继续修改或使用 AI 优化");
    if (initialHandoff.linked_product_id > 0) {
      void api.listMaterialLibraryItems(
        initialHandoff.linked_product_id,
        "",
        "",
        false,
        0
      )
        .then((listing) => {
          const uniqueAssets = dedupeMaterialAssets(listing.assets);
          setLibraryAssets(uniqueAssets);
          if (!uniqueAssets.length) {
            setMessage("脚本已带入；所选产品文件夹暂无素材，请重新选择产品素材。");
          }
        })
        .catch(() => {
          setMessage("脚本已带入；产品资料加载失败，请从产品知识库重新选择。");
        });
    }
    onInitialHandoffConsumed?.(initialHandoff.key);
  }, [initialHandoff, onInitialHandoffConsumed]);

  function validateJob() {
    if (!materials.length) {
      setMessage("请先从产品知识库选择视频、图片或脚本文档");
      return false;
    }
    if (!scriptText.trim() && !requirementText.trim()) {
      setMessage("请至少填写视频脚本或制作补充要求");
      return false;
    }
    setMessage("");
    return true;
  }

  function submitJob() {
    if (validateJob()) setIsConfirmOpen(true);
  }

  async function uploadLocalMaterials(files: FileList | null) {
    const selectedFiles = Array.from(files ?? []);
    if (!selectedFiles.length) return;
    if (libraryAssets.length + selectedFiles.length > 50) {
      setMessage("单个视频创作任务最多可选择 50 个素材");
      return;
    }

    setIsUploadingLocal(true);
    setMessage("");
    try {
      const rootListing = await api.listMaterialLibraryItems(0, "", "", false, 0);
      let uploadFolder = rootListing.folders.find(
        (folder) => folder.folder_name === LOCAL_UPLOAD_FOLDER_NAME
      );
      if (!uploadFolder) {
        uploadFolder = await api.createMaterialFolder(0, LOCAL_UPLOAD_FOLDER_NAME, 0);
      }

      const uploadedAssets: MaterialAsset[] = [];
      for (const file of selectedFiles) {
        uploadedAssets.push(await api.uploadMaterialAsset(uploadFolder.id, file));
      }
      setLibraryAssets((current) => dedupeMaterialAssets([
        ...current,
        ...uploadedAssets
      ]));
      setLocalUploadAssetIds((current) => Array.from(new Set([
        ...current,
        ...uploadedAssets.map((asset) => asset.id)
      ])));
      setMessage(`已上传 ${uploadedAssets.length} 个本地素材，可直接用于本次视频制作。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "本地素材上传失败");
    } finally {
      setIsUploadingLocal(false);
    }
  }

  async function confirmSubmitJob() {
    const normalizedJobTitle = jobTitle.trim() || "小红书视频制作需求";
    const payload: VideoEditJobCreate = {
      creation_mode: creationMode,
      job_title: normalizedJobTitle,
      post_title: normalizedJobTitle,
      post_body: "",
      post_tags: [],
      script_text: scriptText.trim(),
      requirement_text: requirementText.trim(),
      materials,
      xhs_account_id: 0,
      planned_publish_time: 0
    };

    setIsSubmitting(true);
    try {
      const created = await api.createVideoEditJob(payload);
      setJobs((current) => [created, ...current.filter((job) => job.id !== created.id)]);
      setScriptText("");
      setRequirementText("");
      setLibraryAssets([]);
      setLocalUploadAssetIds([]);
      setOptimizationResult(null);
      setOptimizationAdjustment("");
      setIsConfirmOpen(false);
      setMessage("视频创作需求已提交，已进入制作流程");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频制作需求提交失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function openHistory(job: VideoEditJobView) {
    setIsHistoryLoading(true);
    setMessage("");
    try {
      const fallback = historyFromJob(job);
      const history = await api.getVideoEditJobHistory(job.id);
      setHistoryDetail({
        ...fallback,
        ...history,
        request_snapshot: {
          ...fallback.request_snapshot,
          ...(history.request_snapshot ?? {}),
          materials: Array.isArray(history.request_snapshot?.materials)
            && history.request_snapshot.materials.length > 0
            ? history.request_snapshot.materials
            : fallback.request_snapshot.materials
        }
      });
    } catch {
      // The list endpoint already contains the immutable request snapshot.
      // Keep historical records usable when an older deployment does not yet
      // expose the dedicated history route.
      setHistoryDetail(historyFromJob(job));
    } finally {
      setIsHistoryLoading(false);
    }
  }

  function replaceHistoryPreview(blob: Blob, fileName: string, mimeType: string) {
    if (historyPreviewUrlRef.current) {
      URL.revokeObjectURL(historyPreviewUrlRef.current);
    }
    const objectUrl = URL.createObjectURL(blob);
    historyPreviewUrlRef.current = objectUrl;
    setHistoryPreview({ objectUrl, fileName, mimeType: mimeType || blob.type });
  }

  function closeHistoryPreview() {
    if (historyPreviewUrlRef.current) {
      URL.revokeObjectURL(historyPreviewUrlRef.current);
      historyPreviewUrlRef.current = "";
    }
    setHistoryPreview(null);
  }

  function downloadBlob(blob: Blob, fileName: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  async function openMaterialPreview(material: VideoEditMaterial) {
    const actionKey = `material-preview-${material.material_file_id}`;
    setHistoryActionLoading(actionKey);
    try {
      const blob = await api.getMaterialAssetBlob(material.material_file_id);
      replaceHistoryPreview(blob, material.file_name, material.mime_type);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "素材预览加载失败");
    } finally {
      setHistoryActionLoading("");
    }
  }

  async function downloadMaterial(material: VideoEditMaterial) {
    const actionKey = `material-download-${material.material_file_id}`;
    setHistoryActionLoading(actionKey);
    try {
      downloadBlob(await api.getMaterialAssetBlob(material.material_file_id), material.file_name);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "素材下载失败");
    } finally {
      setHistoryActionLoading("");
    }
  }

  async function loadDeliveryBlob(jobId: number, asset: VideoEditDeliveryAsset) {
    return asset.resource_type === "video"
      ? api.getVideoEditDeliveryVersionBlob(jobId, asset.version)
      : api.getVideoEditDeliveryResourceBlob(jobId, asset.resource_type, asset.version);
  }

  async function openDeliveryPreview(jobId: number, asset: VideoEditDeliveryAsset) {
    const actionKey = `delivery-preview-${asset.resource_type}-${asset.version}`;
    setHistoryActionLoading(actionKey);
    try {
      const blob = await loadDeliveryBlob(jobId, asset);
      replaceHistoryPreview(
        blob,
        asset.delivery_file_name || `交付版本-V${asset.version}`,
        asset.mime_type || (asset.resource_type === "video" ? "video/mp4" : asset.resource_type === "voiceover" ? "audio/mpeg" : "text/plain")
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付文件预览失败");
    } finally {
      setHistoryActionLoading("");
    }
  }

  async function downloadDelivery(jobId: number, asset: VideoEditDeliveryAsset) {
    const actionKey = `delivery-download-${asset.resource_type}-${asset.version}`;
    setHistoryActionLoading(actionKey);
    try {
      const blob = await loadDeliveryBlob(jobId, asset);
      downloadBlob(blob, asset.delivery_file_name || `交付版本-V${asset.version}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付文件下载失败");
    } finally {
      setHistoryActionLoading("");
    }
  }

  async function optimizeScript(sourceScript = scriptText) {
    const normalizedScript = sourceScript.trim();
    if (!normalizedScript) {
      setMessage("请先填写需要优化的视频脚本");
      return;
    }
    setIsOptimizing(true);
    setMessage("");
    try {
      const result = await api.optimizeVideoScript({
        script_text: normalizedScript,
        requirement_text: requirementText.trim(),
        material_file_ids: materials.map((material) => material.material_file_id),
        adjustment: optimizationAdjustment.trim()
      });
      setOptimizationResult(result);
      setOptimizationAdjustment("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "脚本优化暂时不可用");
    } finally {
      setIsOptimizing(false);
    }
  }

  return (
    <section className="page-stack video-edit-page">
      <div className="page-heading horizontal-heading compact-page-heading">
        <div className="page-heading-copy">
          <h1>视频创作</h1>
          <p>从产品知识库选择素材，填写脚本与制作要求后提交。</p>
        </div>
      </div>

      {message ? <div className="form-message">{message}</div> : null}

      <div className="video-edit-grid video-edit-product-layout">
        <section className="panel video-edit-submit-panel video-request-panel">
          <div className="panel-title">
            <h2>
              <Scissors size={18} aria-hidden="true" />
              制定视频制作需求
            </h2>
          </div>

          <fieldset className="video-creation-mode-fieldset">
            <legend>创作模式</legend>
            <div className="video-creation-mode-grid">
              <button
                type="button"
                className={creationMode === "standard" ? "active" : ""}
                aria-pressed={creationMode === "standard"}
                onClick={() => setCreationMode("standard")}
              >
                <Film size={19} aria-hidden="true" />
                <span><strong>标准模式</strong><small>适合常规剪辑与内容整理</small></span>
                <span className="video-creation-mode-meta">
                  <em>160 算力</em>
                  <small className="video-creation-mode-status">
                    {creationMode === "standard" ? <Check size={13} aria-hidden="true" /> : null}
                    {creationMode === "standard" ? "已选择" : "点击选择"}
                  </small>
                </span>
              </button>
              <button
                type="button"
                className={creationMode === "pro" ? "active" : ""}
                aria-pressed={creationMode === "pro"}
                onClick={() => setCreationMode("pro")}
              >
                <Sparkles size={19} aria-hidden="true" />
                <span><strong>AI智能创作 Pro</strong><small>更精细的结构、节奏与画面处理</small></span>
                <span className="video-creation-mode-meta">
                  <em>180 算力</em>
                  <small className="video-creation-mode-status">
                    {creationMode === "pro" ? <Check size={13} aria-hidden="true" /> : null}
                    {creationMode === "pro" ? "已选择" : "点击选择"}
                  </small>
                </span>
              </button>
            </div>
          </fieldset>

          <div className="form-grid two-column video-edit-fields">
            <label className="full-span">
              任务标题
              <input
                value={jobTitle}
                onChange={(event) => setJobTitle(event.target.value)}
                placeholder="例如：新品项链小红书种草视频"
              />
            </label>
            <div className="full-span video-script-field">
              <div className="video-script-field-heading">
                <label htmlFor="video-script-input">视频脚本（可选）</label>
                <button
                  className="secondary-button compact-action-button"
                  type="button"
                  disabled={isOptimizing || !scriptText.trim()}
                  onClick={() => void optimizeScript()}
                >
                  {isOptimizing
                    ? <Loader2 size={16} className="spin" aria-hidden="true" />
                    : <Sparkles size={16} aria-hidden="true" />}
                  AI 优化脚本
                </button>
              </div>
              <textarea
                id="video-script-input"
                value={scriptText}
                onChange={(event) => {
                  setScriptText(event.target.value);
                  setOptimizationResult(null);
                }}
                rows={5}
                placeholder="例如：前 3 秒展示产品细节，中段展示使用场景，结尾引导收藏咨询。"
              />
            </div>
            {optimizationResult ? (
              <section className="full-span script-optimization-panel">
                <div className="script-optimization-heading">
                  <div>
                    <Sparkles size={17} aria-hidden="true" />
                    <strong>AI 脚本优化结果</strong>
                  </div>
                  <span>提交前可继续调整，确认提交后将锁定</span>
                </div>
                <div className="script-comparison-grid">
                  <div>
                    <span>优化前</span>
                    <p>{optimizationResult.original_script}</p>
                  </div>
                  <div>
                    <span>优化后</span>
                    <p>{optimizationResult.optimized_script}</p>
                  </div>
                </div>
                <label className="script-adjustment-field">
                  继续调整（可选）
                  <input
                    value={optimizationAdjustment}
                    onChange={(event) => setOptimizationAdjustment(event.target.value)}
                    placeholder="例如：开头更有冲击力，口播更自然，压缩到 30 秒"
                  />
                </label>
                <div className="script-optimization-actions">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => {
                      setOptimizationResult(null);
                      setOptimizationAdjustment("");
                    }}
                  >
                    保留原脚本
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={isOptimizing}
                    onClick={() => void optimizeScript(optimizationResult.optimized_script)}
                  >
                    {isOptimizing
                      ? <Loader2 size={16} className="spin" aria-hidden="true" />
                      : <Sparkles size={16} aria-hidden="true" />}
                    继续优化
                  </button>
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => {
                      setScriptText(optimizationResult.optimized_script);
                      setOptimizationResult(null);
                      setOptimizationAdjustment("");
                      setMessage("已采用 AI 优化脚本");
                    }}
                  >
                    <Check size={16} aria-hidden="true" />
                    采用优化结果
                  </button>
                </div>
              </section>
            ) : null}
            <label className="full-span">
              制作补充要求（可选）
              <textarea
                value={requirementText}
                onChange={(event) => setRequirementText(event.target.value)}
                rows={4}
                placeholder="例如：节奏自然、保留高级感、避免过度营销，使用轻快音乐。"
              />
            </label>
          </div>

          <div className="video-material-actions">
            <div>
              <strong>制作素材</strong>
              <span>可从本地直接上传，也可从产品知识库选择。</span>
            </div>
            <div className="video-material-action-buttons">
              <input
                ref={localUploadInputRef}
                className="sr-only"
                type="file"
                multiple
                accept="image/*,video/mp4,video/quicktime,.doc,.docx,.xls,.xlsx,.txt,.pdf"
                aria-label="本地上传制作素材"
                onChange={(event) => {
                  void uploadLocalMaterials(event.target.files);
                  event.target.value = "";
                }}
              />
              <button
                className="secondary-button"
                type="button"
                disabled={isUploadingLocal}
                onClick={() => localUploadInputRef.current?.click()}
              >
                {isUploadingLocal
                  ? <Loader2 size={17} className="spin" aria-hidden="true" />
                  : <Upload size={17} aria-hidden="true" />}
                {isUploadingLocal ? "上传中" : "本地上传"}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setIsLibraryOpen(true)}
              >
                <FolderOpen size={17} aria-hidden="true" />
                从产品知识库选择
              </button>
            </div>
          </div>

          <div className="knowledge-library-source video-library-source">
            <FolderOpen size={34} aria-hidden="true" />
            <strong>
              {materials.length
                ? `已选择 ${materials.length} 个制作素材`
                : "请从本地上传或产品知识库选择视频、图片或脚本文档"}
            </strong>
            <span>本地上传的文件会同步保存到素材库，方便后续复用。</span>
          </div>

          {hasCollapsibleMaterialList ? (
            <div className="video-material-list-controls">
              <button
                className="viral-history-toggle video-material-list-toggle"
                type="button"
                aria-expanded={materialsExpanded}
                aria-label={materialsExpanded
                  ? "收起素材列表"
                  : `展开素材列表（${materials.length}）`}
                onClick={() => {
                  setMaterialsExpanded((current) => {
                    const next = !current;
                    try {
                      window.localStorage.setItem(
                        MATERIAL_LIST_EXPANDED_STORAGE_KEY,
                        next ? "1" : "0"
                      );
                    } catch {
                      // The list toggle stays usable when browser storage is unavailable.
                    }
                    return next;
                  });
                }}
              >
                <span>{materials.length} 项</span>
                <span>{materialsExpanded ? "收起" : "展开"}</span>
                <ChevronDown
                  className={materialsExpanded ? "expanded" : ""}
                  size={16}
                  aria-hidden="true"
                />
              </button>
            </div>
          ) : null}

          {showMaterialList ? (
            <div className={hasCollapsibleMaterialList
              ? "material-list video-material-list-scroll"
              : "material-list"}
            >
              {materials.map((material) => (
                <div key={material.material_file_id}>
                  <strong>{material.file_name}</strong>
                  <span>
                    {material.file_type === "image"
                      ? "图片"
                      : material.file_type === "video"
                        ? "视频"
                        : "脚本文档"}
                    {localUploadAssetIds.includes(material.material_file_id)
                      ? " · 本地上传 · "
                      : " · 产品知识库 · "}
                    {Math.max(1, Math.round(material.file_size / 1024))} KB
                  </span>
                </div>
              ))}
            </div>
          ) : null}

          <div className="primary-row video-edit-submit-action">
            <span className="feature-credit-note">本次创作模式：{creationMode === "pro" ? "AI智能创作 Pro" : "标准模式"}</span>
            <button
              className="primary-button"
              type="button"
              disabled={isSubmitting}
              onClick={submitJob}
            >
              {isSubmitting
                ? <Loader2 size={18} className="spin" aria-hidden="true" />
                : <Check size={18} aria-hidden="true" />}
              确定
            </button>
          </div>
        </section>

        <aside className="video-edit-side-rail">
          <section className="panel video-edit-summary-card">
            <header><strong>需求摘要</strong><span>{creationMode === "pro" ? "PRO" : "STANDARD"}</span></header>
            <dl>
              <div><dt>制作素材</dt><dd>{materials.length} 项</dd></div>
              <div><dt>预计消耗</dt><dd>{creationCreditCost} 算力</dd></div>
            </dl>
          </section>
          <section className="panel video-edit-progress-card">
            <header><Clock3 size={18} aria-hidden="true" /><strong>制作流程</strong></header>
            <ol>
              <li className="active" aria-current="step"><i>1</i><span>提交需求</span></li>
              <li><i>2</i><span>制作处理</span></li>
              <li><i>3</i><span>客户确认</span></li>
              <li><i>4</i><span>完成交付</span></li>
            </ol>
          </section>
          <section className="panel video-edit-history-card">
            <header><div><FileClock size={18} aria-hidden="true" /><strong>创作记录</strong></div><span>{jobs.length} 项</span></header>
            <div className="video-edit-history-list">
              {jobs.length ? jobs.slice(0, 8).map((job) => {
                const historyStatus = resolveVideoEditHistoryStatus(job);
                return (
                  <button key={job.id} type="button" onClick={() => void openHistory(job)}>
                    <span className="video-edit-history-copy">
                      <strong>{job.job_title}</strong>
                      <small>{job.creation_mode_label} · {job.materials.length} 个素材</small>
                      <small className="video-edit-history-time">
                        生成时间：{job.delivered_time > 0 ? formatVideoEditDateTime(job.delivered_time) : "等待生成"}
                      </small>
                      <small className="video-edit-history-action">查看脚本与素材</small>
                    </span>
                    <span className="video-edit-history-meta">
                      <em data-history-status={historyStatus.kind}>{historyStatus.label}</em>
                      <ChevronRight size={16} aria-hidden="true" />
                    </span>
                  </button>
                );
              }) : <div className="video-edit-history-empty">首次提交后，脚本、素材和交付版本会记录在这里。</div>}
            </div>
          </section>
        </aside>
      </div>

      <MaterialLibraryPicker
        open={isLibraryOpen}
        allowedTypes={["image", "video", "word", "excel", "other"]}
        initialSelection={libraryAssets}
        onClose={() => setIsLibraryOpen(false)}
        onConfirm={(assets) => {
          const nextAssets = dedupeMaterialAssets(assets);
          setLibraryAssets(nextAssets);
          setLocalUploadAssetIds((current) => current.filter((assetId) => (
            nextAssets.some((asset) => asset.id === assetId)
          )));
          setIsLibraryOpen(false);
        }}
      />

      {isConfirmOpen ? (
        <div
          className="dialog-backdrop"
          role="presentation"
          onMouseDown={() => {
            if (!isSubmitting) setIsConfirmOpen(false);
          }}
        >
          <section
            className="dialog-panel dialog-panel-compact video-submit-confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="video-submit-confirm-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="dialog-header">
              <div>
                <h2 id="video-submit-confirm-title">确认视频制作需求</h2>
                <p>提交后将进入制作流程，请在确认前完成脚本与需求调整。</p>
              </div>
            </header>
            <div className="video-submit-confirm-content">
              <div className="video-submit-lock-note">
                <LockKeyhole size={20} aria-hidden="true" />
                <div>
                  <strong>提交后需求将锁定</strong>
                  <span>
                    本次素材、脚本和制作要求将作为本次任务的提交快照保存。
                  </span>
                </div>
              </div>
              <dl className="video-submit-summary">
                <div>
                  <dt>创作模式</dt>
                  <dd>{creationMode === "pro" ? "AI智能创作 Pro（180 算力）" : "标准模式（160 算力）"}</dd>
                </div>
                <div>
                  <dt>任务名称</dt>
                  <dd>{jobTitle.trim() || "小红书视频制作需求"}</dd>
                </div>
                <div>
                  <dt>制作素材</dt>
                  <dd>{materials.length} 个素材文件</dd>
                </div>
              </dl>
            </div>
            <footer className="dialog-actions">
              <button
                className="secondary-button"
                type="button"
                disabled={isSubmitting}
                onClick={() => setIsConfirmOpen(false)}
              >
                返回检查
              </button>
              <button
                className="primary-button"
                type="button"
                disabled={isSubmitting}
                onClick={() => void confirmSubmitJob()}
              >
                {isSubmitting
                  ? <Loader2 size={17} className="spin" aria-hidden="true" />
                  : <LockKeyhole size={17} aria-hidden="true" />}
                确认并提交
              </button>
            </footer>
          </section>
        </div>
      ) : null}

      {historyDetail ? (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => { closeHistoryPreview(); setHistoryDetail(null); }}>
          <section className="dialog-panel video-history-dialog" role="dialog" aria-modal="true" aria-labelledby="video-history-title" onMouseDown={(event) => event.stopPropagation()}>
            <header className="dialog-header">
              <div><h2 id="video-history-title">视频创作记录 #{historyDetail.id}</h2><p>展示提交时锁定的脚本、素材与历次交付，不受后续编辑影响。</p></div>
              <button className="icon-button" type="button" aria-label="关闭创作记录" onClick={() => { closeHistoryPreview(); setHistoryDetail(null); }}><X size={18} /></button>
            </header>
            <div className="video-history-content">
              <dl className="video-history-facts">
                <div><dt>创作模式</dt><dd>{historyDetail.creation_mode_label}</dd></div>
                <div><dt>算力</dt><dd>{historyDetail.credit_cost}</dd></div>
                <div><dt>提交时间</dt><dd>{formatVideoEditDateTime(historyDetail.create_time)}</dd></div>
                <div>
                  <dt>生成时间</dt>
                  <dd>{historyDetail.delivered_time > 0 ? formatVideoEditDateTime(historyDetail.delivered_time) : "尚未生成"}</dd>
                </div>
                <div><dt>当前状态</dt><dd>{resolveVideoEditHistoryStatus(historyDetail).label}</dd></div>
              </dl>
              <RichContentReader
                title="提交脚本"
                content={historyDetail.request_snapshot.script_text}
                emptyText="未填写脚本"
                variant="script"
              />
              <RichContentReader
                title="制作要求"
                content={historyDetail.request_snapshot.requirement_text}
                emptyText="未填写补充要求"
                variant="script"
              />
              <section className="video-history-file-section">
                <h3>提交素材（{historyDetail.request_snapshot.materials.length}）</h3>
                <div className="video-history-file-grid">
                  {historyDetail.request_snapshot.materials.map((material) => {
                    const MaterialIcon = material.file_type === "video"
                      ? FileVideo2
                      : material.file_type === "image" ? FileImage : FileText;
                    return (
                      <article className="video-history-file-card" key={material.material_file_id}>
                        <span className="video-history-file-icon"><MaterialIcon size={21} aria-hidden="true" /></span>
                        <div className="video-history-file-copy">
                          <strong title={material.file_name}>{material.file_name}</strong>
                          <span>{material.file_type} · {Math.max(1, Math.round(material.file_size / 1024))} KB</span>
                        </div>
                        <div className="video-history-file-actions">
                          <button type="button" aria-label={`预览素材 ${material.file_name}`} disabled={Boolean(historyActionLoading)} onClick={() => void openMaterialPreview(material)}>
                            {historyActionLoading === `material-preview-${material.material_file_id}` ? <Loader2 size={15} className="spin" /> : <Eye size={15} />}
                            预览
                          </button>
                          <button type="button" aria-label={`下载素材 ${material.file_name}`} disabled={Boolean(historyActionLoading)} onClick={() => void downloadMaterial(material)}>
                            {historyActionLoading === `material-download-${material.material_file_id}` ? <Loader2 size={15} className="spin" /> : <Download size={15} />}
                            下载
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
              <section className="video-history-file-section">
                <h3>交付版本（{historyDetail.delivery_assets.length}）</h3>
                {historyDetail.delivery_assets.length ? (
                  <div className="video-history-file-grid">
                    {historyDetail.delivery_assets.map((asset, index) => {
                      const DeliveryIcon = asset.resource_type === "video"
                        ? FileVideo2
                        : asset.resource_type === "voiceover" ? Music2 : FileText;
                      const fileName = asset.delivery_file_name || "交付文件";
                      return (
                        <article className="video-history-file-card delivery" key={`${asset.resource_type}-${asset.version}-${index}`}>
                          <span className="video-history-file-icon"><DeliveryIcon size={21} aria-hidden="true" /></span>
                          <div className="video-history-file-copy">
                            <strong title={fileName}>V{asset.version} · {fileName}</strong>
                            <span>{asset.resource_type} · {asset.delivered_time ? new Date(asset.delivered_time * 1000).toLocaleString("zh-CN") : "等待交付"}</span>
                          </div>
                          <div className="video-history-file-actions">
                            <button type="button" aria-label={`预览交付版本 ${fileName}`} disabled={Boolean(historyActionLoading)} onClick={() => void openDeliveryPreview(historyDetail.id, asset)}>
                              {historyActionLoading === `delivery-preview-${asset.resource_type}-${asset.version}` ? <Loader2 size={15} className="spin" /> : <Eye size={15} />}
                              预览
                            </button>
                            <button type="button" aria-label={`下载交付版本 ${fileName}`} disabled={Boolean(historyActionLoading)} onClick={() => void downloadDelivery(historyDetail.id, asset)}>
                              {historyActionLoading === `delivery-download-${asset.resource_type}-${asset.version}` ? <Loader2 size={15} className="spin" /> : <Download size={15} />}
                              下载
                            </button>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                ) : <p className="video-history-empty-copy">尚未产生交付版本。</p>}
              </section>
            </div>
          </section>
        </div>
      ) : null}
      {historyPreview ? (
        <div className="dialog-backdrop video-history-preview-backdrop" role="presentation" onMouseDown={closeHistoryPreview}>
          <section className="dialog-panel video-history-preview-dialog" role="dialog" aria-modal="true" aria-label={`预览 ${historyPreview.fileName}`} onMouseDown={(event) => event.stopPropagation()}>
            <header className="dialog-header">
              <div><h2>{historyPreview.fileName}</h2><p>可在此检查素材或交付内容，也可以返回列表下载原文件。</p></div>
              <button className="icon-button" type="button" aria-label="关闭文件预览" onClick={closeHistoryPreview}><X size={18} /></button>
            </header>
            <div className="video-history-preview-stage">
              {historyPreview.mimeType.startsWith("image/") ? <img src={historyPreview.objectUrl} alt={historyPreview.fileName} /> : null}
              {historyPreview.mimeType.startsWith("video/") ? <video src={historyPreview.objectUrl} controls autoPlay /> : null}
              {historyPreview.mimeType.startsWith("audio/") ? <audio src={historyPreview.objectUrl} controls autoPlay /> : null}
              {!/^(image|video|audio)\//.test(historyPreview.mimeType) ? <object data={historyPreview.objectUrl} type={historyPreview.mimeType}><a href={historyPreview.objectUrl} download={historyPreview.fileName}>下载文件查看</a></object> : null}
            </div>
          </section>
        </div>
      ) : null}
      {isHistoryLoading ? <div className="video-history-loading" role="status"><Loader2 className="spin" size={18} />正在读取创作记录</div> : null}
    </section>
  );
}
