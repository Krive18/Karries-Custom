import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  Download,
  FileAudio2,
  FileText,
  FileVideo2,
  FolderOpen,
  Languages,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  Upload,
  X
} from "lucide-react";

import { customerApi } from "../api/client";
import { MaterialLibraryPicker } from "../components/material/MaterialLibraryPicker";
import type {
  AiTranslationDelivery,
  AiTranslationLanguage,
  AiTranslationStatus,
  AiTranslationTask,
  MaterialAsset
} from "../types";


const languageOptions: Array<{ value: AiTranslationLanguage; label: string }> = [
  { value: "auto", label: "自动识别" },
  { value: "zh", label: "中文" },
  { value: "en", label: "英语" },
  { value: "vi", label: "越南语" },
  { value: "ms", label: "马来语" },
  { value: "th", label: "泰语" },
  { value: "tl", label: "菲律宾语" },
  { value: "ja", label: "日语" },
  { value: "ko", label: "韩语" },
  { value: "es", label: "西班牙语" }
];

const customerSteps = ["已提交", "处理中", "待确认", "已完成"] as const;

const customerStatusLabels: Record<AiTranslationStatus, string> = {
  pending: "准备中",
  claimed: "翻译处理中",
  in_progress: "翻译处理中",
  awaiting_customer: "待确认",
  revision_requested: "优化中",
  completed: "已完成",
  cancelled: "已取消",
  failed: "处理失败，可重试"
};

function customerProgressStep(status: AiTranslationStatus) {
  if (status === "completed") return 3;
  if (status === "awaiting_customer") return 2;
  if (["claimed", "in_progress", "revision_requested"].includes(status)) return 1;
  return 0;
}

function explainError(error: unknown) {
  return error instanceof Error ? error.message : "请求未完成，请稍后重试。";
}

function requestId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function formatTime(timestamp: number) {
  return timestamp
    ? new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false
    }).format(new Date(timestamp * 1000))
    : "--";
}

function formatSize(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function languageName(code: string) {
  return languageOptions.find((item) => item.value === code)?.label ?? code;
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function AiTranslationPage() {
  const [tasks, setTasks] = useState<AiTranslationTask[]>([]);
  const [selectedId, setSelectedId] = useState(0);
  const [sourceLanguage, setSourceLanguage] = useState<AiTranslationLanguage>("auto");
  const [targetLanguage, setTargetLanguage] = useState<Exclude<AiTranslationLanguage, "auto">>("en");
  const [file, setFile] = useState<File | null>(null);
  const [libraryAsset, setLibraryAsset] = useState<MaterialAsset | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [message, setMessage] = useState("");
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewType, setPreviewType] = useState<"video" | "audio">("video");
  const [sourcePreviewLoading, setSourcePreviewLoading] = useState(false);
  const [activeDeliveryAction, setActiveDeliveryAction] = useState<{
    id: number;
    mode: "preview" | "download";
  } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => tasks.find((task) => task.id === selectedId) ?? null,
    [selectedId, tasks]
  );

  const loadTasks = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    try {
      const next = await customerApi.listAiTranslationTasks();
      setTasks(next);
      setSelectedId((current) => (
        current > 0 && next.some((task) => task.id === current) ? current : 0
      ));
      if (!quiet) setMessage("");
    } catch (error) {
      if (!quiet) setMessage(explainError(error));
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
    const timer = window.setInterval(() => void loadTasks(true), 30_000);
    return () => window.clearInterval(timer);
  }, [loadTasks]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  async function submitTask() {
    if ((!file && !libraryAsset) || isSubmitting) return;
    setIsSubmitting(true);
    setMessage("");
    try {
      const id = requestId("translation");
      const created = file
        ? await customerApi.uploadAiTranslationTask(file, sourceLanguage, targetLanguage, id)
        : await customerApi.createAiTranslationTaskFromMaterial({
          material_file_id: libraryAsset!.id,
          source_language: sourceLanguage,
          target_language: targetLanguage,
          client_request_id: id
        });
      setFile(null);
      setLibraryAsset(null);
      if (fileRef.current) fileRef.current.value = "";
      await loadTasks(true);
      setSelectedId(created.id);
      setMessage("翻译任务已创建，可在任务记录中查看进度。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runAction(action: "cancel" | "accept" | "revision") {
    if (!selected || busyAction) return;
    setBusyAction(action);
    setMessage("");
    try {
      const updated = action === "cancel"
        ? await customerApi.cancelAiTranslationTask(selected.id)
        : action === "accept"
          ? await customerApi.acceptAiTranslationTask(selected.id)
          : await customerApi.requestAiTranslationRevision(selected.id, feedback.trim());
      setTasks((current) => current.map((task) => task.id === updated.id ? updated : task));
      if (action === "revision") {
        setRevisionOpen(false);
        setFeedback("");
      }
      setMessage(action === "accept" ? "成片已确认完成。" : action === "cancel" ? "任务已取消。" : "修改意见已提交，任务正在优化。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setBusyAction("");
    }
  }

  async function previewSource() {
    if (!selected || sourcePreviewLoading) return;
    setSourcePreviewLoading(true);
    setMessage("");
    try {
      const blob = await customerApi.getAiTranslationSourceBlob(selected.id);
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return URL.createObjectURL(blob);
      });
      setPreviewType("video");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setSourcePreviewLoading(false);
    }
  }

  async function handleDelivery(delivery: AiTranslationDelivery, mode: "preview" | "download") {
    if (!selected || activeDeliveryAction) return;
    setActiveDeliveryAction({ id: delivery.id, mode });
    setMessage("");
    try {
      const blob = await customerApi.getAiTranslationDeliveryBlob(selected.id, delivery.id);
      if (mode === "download") {
        downloadBlob(blob, delivery.file_name);
        return;
      }
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return URL.createObjectURL(blob);
      });
      setPreviewType(delivery.resource_type === "voiceover" ? "audio" : "video");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setActiveDeliveryAction(null);
    }
  }

  const activeStep = selected ? customerProgressStep(selected.status) : 0;

  return (
    <section className="translation-page">
      <header className="translation-heading">
        <h1>AI智能翻译</h1>
        <button className="secondary-button" type="button" disabled={isLoading} onClick={() => void loadTasks()}>
          <RefreshCw size={16} />刷新任务
        </button>
      </header>
      {message ? <div className="app-alert" role="status">{message}</div> : null}

      <div className="translation-create-grid">
        <section className="panel translation-create-card">
          <header><Languages size={20} /><div><h2>新建翻译任务</h2><p>支持本地视频和产品知识库视频。</p></div></header>
          <div className="translation-source-actions">
            <input
              ref={fileRef}
              type="file"
              accept="video/*,.mp4,.mov,.m4v,.webm"
              hidden
              onChange={(event) => {
                const next = event.target.files?.[0] ?? null;
                setFile(next);
                if (next) setLibraryAsset(null);
              }}
            />
            <button className="secondary-button" type="button" onClick={() => fileRef.current?.click()}><Upload size={16} />本地上传</button>
            <button className="secondary-button" type="button" onClick={() => setPickerOpen(true)}><FolderOpen size={16} />从产品知识库选择</button>
          </div>
          <div className="translation-selected-source">
            <FileVideo2 size={24} />
            <span>
              <strong>{file?.name ?? libraryAsset?.file_name ?? "尚未选择视频"}</strong>
              <small>{file ? `${formatSize(file.size)} · 本地上传` : libraryAsset ? `${formatSize(libraryAsset.file_size)} · 产品知识库` : "单个视频最大 500 MB"}</small>
            </span>
            {file || libraryAsset ? <button type="button" aria-label="移除已选视频" onClick={() => { setFile(null); setLibraryAsset(null); }}><X size={16} /></button> : null}
          </div>
          <div className="translation-language-fields">
            <label>原始语言<select value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value as AiTranslationLanguage)}>{languageOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <span>→</span>
            <label>目标语言<select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value as Exclude<AiTranslationLanguage, "auto">)}>{languageOptions.filter((option) => option.value !== "auto").map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          </div>
          <button className="primary-button translation-submit" type="button" disabled={(!file && !libraryAsset) || isSubmitting || (sourceLanguage !== "auto" && sourceLanguage === targetLanguage)} onClick={() => void submitTask()}>
            {isSubmitting ? <><Loader2 className="spin" size={17} />正在上传并提交</> : <><Languages size={17} />提交翻译任务</>}
          </button>
        </section>

        <section className="panel translation-history-card">
          <header><h2>任务记录</h2><span>{tasks.length} 项</span></header>
          <div className="translation-history-list" aria-busy={isLoading}>
            {isLoading && !tasks.length ? <div className="translation-empty"><Loader2 className="spin" />正在加载任务</div> : null}
            {!isLoading && !tasks.length ? <div className="translation-empty"><Languages /><strong>暂无翻译任务</strong><span>选择视频并提交后，进度会显示在这里。</span></div> : null}
            {tasks.map((task) => <button key={task.id} type="button" className={task.id === selected?.id ? "translation-task-item active" : "translation-task-item"} onClick={() => setSelectedId(task.id)}>
              <span><strong>{task.source_file_name}</strong><small>{languageName(task.source_language)} → {languageName(task.target_language)} · {formatTime(task.create_time)}</small></span>
              <em data-status={task.status}>{customerStatusLabels[task.status]}</em>
            </button>)}
          </div>
        </section>
      </div>

      {selected ? (
        <section className="panel translation-detail-card">
          <header className="translation-detail-heading">
            <div><span>翻译任务 #{selected.id}</span><h2>{selected.source_file_name}</h2><p>{languageName(selected.source_language)} → {languageName(selected.target_language)} · {customerStatusLabels[selected.status]}</p></div>
            <div>
              <button
                aria-busy={sourcePreviewLoading}
                className="secondary-button"
                disabled={sourcePreviewLoading}
                type="button"
                onClick={() => void previewSource()}
              >
                {sourcePreviewLoading ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
                {sourcePreviewLoading ? "正在打开" : "预览原视频"}
              </button>
              {selected.status === "pending" ? <button className="danger-button" disabled={Boolean(busyAction)} type="button" onClick={() => void runAction("cancel")}>取消任务</button> : null}
            </div>
          </header>
          <div className="translation-progress">
            {customerSteps.map((label, index) => <div key={label} className={index <= activeStep && !["cancelled", "failed"].includes(selected.status) ? "done" : ""}><i>{index < activeStep ? "✓" : index + 1}</i><span>{label}</span></div>)}
          </div>
          {selected.revision_feedback ? <div className="translation-feedback"><strong>最新修改意见</strong><p>{selected.revision_feedback}</p></div> : null}
          {selected.deliveries.length ? (
            <div className="translation-deliveries">
              <header><h3>交付资源</h3><span>视频 {selected.delivery_resource_counts?.video ?? 0} · 口播 {selected.delivery_resource_counts?.voiceover ?? 0} · 字幕 {selected.delivery_resource_counts?.subtitle ?? 0}</span></header>
              {selected.deliveries.map((delivery) => {
                const isPreviewing = activeDeliveryAction?.id === delivery.id && activeDeliveryAction.mode === "preview";
                const isDownloading = activeDeliveryAction?.id === delivery.id && activeDeliveryAction.mode === "download";
                return (
                  <div className="translation-delivery-row" key={delivery.id}>
                    {delivery.resource_type === "voiceover" ? <FileAudio2 size={19} /> : delivery.resource_type === "subtitle" ? <FileText size={19} /> : <FileVideo2 size={19} />}
                    <span><strong>V{delivery.delivery_no}.{delivery.asset_no} · {delivery.file_name}</strong><small>{delivery.resource_type === "voiceover" ? "口播音频" : delivery.resource_type === "subtitle" ? "字幕文件" : "翻译视频"} · {formatSize(delivery.file_size)} · {formatTime(delivery.create_time)}</small></span>
                    {delivery.resource_type !== "subtitle" ? (
                      <button
                        aria-busy={isPreviewing}
                        disabled={Boolean(activeDeliveryAction)}
                        type="button"
                        onClick={() => void handleDelivery(delivery, "preview")}
                      >
                        {isPreviewing ? <Loader2 className="spin" size={15} /> : <Play size={15} />}
                        {isPreviewing ? "正在打开" : "预览"}
                      </button>
                    ) : null}
                    <button
                      aria-busy={isDownloading}
                      disabled={Boolean(activeDeliveryAction)}
                      type="button"
                      onClick={() => void handleDelivery(delivery, "download")}
                    >
                      {isDownloading ? <Loader2 className="spin" size={15} /> : <Download size={15} />}
                      {isDownloading ? "正在下载" : "下载"}
                    </button>
                  </div>
                );
              })}
            </div>
          ) : <div className="translation-empty compact"><Clock3 /><span>成片准备完成后会在这里显示。</span></div>}
          {selected.status === "awaiting_customer" ? <footer className="translation-detail-actions"><button className="secondary-button" type="button" onClick={() => setRevisionOpen(true)}><RotateCcw size={16} />提交修改意见</button><button className="primary-button" type="button" disabled={Boolean(busyAction)} onClick={() => void runAction("accept")}><CheckCircle2 size={16} />确认完成</button></footer> : null}
        </section>
      ) : null}

      <MaterialLibraryPicker open={pickerOpen} allowedTypes={["video"]} selectionLimit={1} initialSelection={libraryAsset ? [libraryAsset] : []} onClose={() => setPickerOpen(false)} onConfirm={(assets) => { setLibraryAsset(assets[0] ?? null); setFile(null); setPickerOpen(false); }} />

      {revisionOpen ? <div className="translation-modal-backdrop"><section className="translation-modal" role="dialog" aria-modal="true"><header><div><h2>提交修改意见</h2><p>系统将根据修改意见继续处理。</p></div><button type="button" aria-label="关闭" onClick={() => setRevisionOpen(false)}><X /></button></header><label>修改意见<textarea value={feedback} maxLength={2000} placeholder="请明确说明需要修改的画面、字幕或语言表达，至少 5 个字。" onChange={(event) => setFeedback(event.target.value)} /></label><footer><button className="secondary-button" type="button" onClick={() => setRevisionOpen(false)}>取消</button><button className="primary-button" type="button" disabled={feedback.trim().length < 5 || Boolean(busyAction)} onClick={() => void runAction("revision")}>确认提交</button></footer></section></div> : null}
      {previewUrl ? <div className="translation-modal-backdrop"><section className="translation-preview-modal" role="dialog" aria-modal="true"><header><h2>{previewType === "audio" ? "口播预览" : "视频预览"}</h2><button type="button" aria-label="关闭预览" onClick={() => setPreviewUrl("")}><X /></button></header>{previewType === "audio" ? <audio src={previewUrl} controls autoPlay /> : <video src={previewUrl} controls autoPlay playsInline />}</section></div> : null}
    </section>
  );
}
