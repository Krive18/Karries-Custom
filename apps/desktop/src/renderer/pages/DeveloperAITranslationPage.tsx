import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Download,
  FileAudio2,
  FileText,
  FileVideo2,
  Languages,
  Loader2,
  Play,
  RefreshCw,
  Search,
  Upload,
  XCircle
} from "lucide-react";

import { developerApi } from "../api/developerClient";
import type { AiTranslationDelivery, AiTranslationStatus, AiTranslationTask } from "../types";


const statuses: Array<{ value: "" | AiTranslationStatus; label: string }> = [
  { value: "", label: "全部状态" },
  { value: "pending", label: "待接取" },
  { value: "claimed", label: "已接取" },
  { value: "in_progress", label: "制作中" },
  { value: "awaiting_customer", label: "待客户确认" },
  { value: "revision_requested", label: "客户要求修改" },
  { value: "completed", label: "已完成" },
  { value: "cancelled", label: "已取消" },
  { value: "failed", label: "失败" }
];

const languages: Record<string, string> = {
  auto: "自动识别", vi: "越南语", en: "英语", zh: "中文", ms: "马来语",
  th: "泰语", tl: "菲律宾语", ja: "日语", ko: "韩语", es: "西班牙语"
};

function explainError(error: unknown) {
  return error instanceof Error ? error.message : "请求未完成，请稍后重试。";
}

function formatTime(timestamp: number) {
  return timestamp
    ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(timestamp * 1000))
    : "--";
}

function formatSize(bytes: number) {
  return bytes >= 1024 ** 2 ? `${(bytes / 1024 ** 2).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function requestId(taskId: number) {
  return `delivery-${taskId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function DeveloperAITranslationPage() {
  const [tasks, setTasks] = useState<AiTranslationTask[]>([]);
  const [selectedId, setSelectedId] = useState(0);
  const [status, setStatus] = useState<"" | AiTranslationStatus>("");
  const [keyword, setKeyword] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [operationNote, setOperationNote] = useState("");
  const [deliveryFiles, setDeliveryFiles] = useState<File[]>([]);
  const [deliveryResourceType, setDeliveryResourceType] = useState<"video" | "voiceover" | "subtitle">("video");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewType, setPreviewType] = useState<"video" | "audio">("video");
  const deliveryRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => tasks.find((task) => task.id === selectedId) ?? tasks[0] ?? null,
    [selectedId, tasks]
  );

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (keyword) params.set("keyword", keyword);
      const next = await developerApi.listAiTranslationTasks(params);
      setTasks(next);
      setSelectedId((current) => next.some((task) => task.id === current) ? current : (next[0]?.id ?? 0));
      if (!quiet) setMessage("");
    } catch (error) {
      if (!quiet) setMessage(explainError(error));
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, [keyword, status]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(true), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  async function action(nextAction: "claim" | "start" | "fail") {
    if (!selected || busy) return;
    if (nextAction === "fail" && !operationNote.trim()) {
      setMessage("请填写失败原因后再标记失败。");
      return;
    }
    setBusy(nextAction);
    setMessage("");
    try {
      const updated = nextAction === "claim"
        ? await developerApi.claimAiTranslationTask(selected.id, operationNote)
        : nextAction === "start"
          ? await developerApi.startAiTranslationTask(selected.id, operationNote)
          : await developerApi.failAiTranslationTask(selected.id, operationNote);
      setTasks((current) => current.map((task) => task.id === updated.id ? updated : task));
      setOperationNote("");
      setMessage(nextAction === "claim" ? "任务已接取。" : nextAction === "start" ? "任务已进入制作中。" : "任务已标记失败，未扣除客户算力。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setBusy("");
    }
  }

  async function deliver() {
    if (!selected || !deliveryFiles.length || busy) return;
    setBusy("deliver");
    setMessage("");
    try {
      const updated = await developerApi.uploadAiTranslationDelivery(
        selected.id,
        deliveryFiles,
        deliveryNote,
        requestId(selected.id),
        deliveryResourceType,
        false
      );
      setTasks((current) => current.map((task) => task.id === updated.id ? updated : task));
      setDeliveryFiles([]);
      setDeliveryNote("");
      if (deliveryRef.current) deliveryRef.current.value = "";
      setMessage(`${deliveryResourceType === "video" ? "视频" : deliveryResourceType === "voiceover" ? "口播音频" : "字幕"}已保存，可继续上传其他资源或完成本次交付。`);
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setBusy("");
    }
  }

  async function completeDelivery() {
    if (!selected || !selected.deliveries.length || busy) return;
    setBusy("complete");
    setMessage("");
    try {
      const updated = await developerApi.completeAiTranslationDelivery(selected.id, deliveryNote);
      setTasks((current) => current.map((task) => task.id === updated.id ? updated : task));
      setDeliveryNote("");
      setMessage("本次翻译资源已交付给客户。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setBusy("");
    }
  }

  async function previewSource() {
    if (!selected) return;
    try {
      const blob = await developerApi.getAiTranslationSourceBlob(selected.id);
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return URL.createObjectURL(blob);
      });
      setPreviewType("video");
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  async function handleDelivery(delivery: AiTranslationDelivery, mode: "preview" | "download") {
    if (!selected) return;
    try {
      const blob = await developerApi.getAiTranslationDeliveryBlob(selected.id, delivery.id);
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
    }
  }

  const canDeliver = selected && ["claimed", "in_progress", "revision_requested"].includes(selected.status);

  return (
    <section className="developer-page developer-translation-page">
      <header className="developer-page-heading">
        <div><h1>AI 翻译任务</h1><p>接取用户视频翻译需求、上传翻译成片并形成客户确认闭环。</p></div>
        <button className="secondary-button" type="button" disabled={isLoading} onClick={() => void load()}><RefreshCw size={16} />刷新工单</button>
      </header>
      {message ? <div className="app-alert" role="status">{message}</div> : null}

      <div className="developer-translation-filters panel">
        <form onSubmit={(event) => { event.preventDefault(); setKeyword(keywordInput.trim()); }}><Search size={16} /><input value={keywordInput} placeholder="搜索文件名、客户或团队" onChange={(event) => setKeywordInput(event.target.value)} /><button type="submit">搜索</button></form>
        <select aria-label="翻译任务状态" value={status} onChange={(event) => setStatus(event.target.value as "" | AiTranslationStatus)}>{statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
        <span>共 {tasks.length} 个真实工单</span>
      </div>

      <div className="developer-translation-layout panel">
        <aside className="developer-translation-list" aria-busy={isLoading}>
          {isLoading && !tasks.length ? <div className="translation-empty"><Loader2 className="spin" />正在加载任务</div> : null}
          {!isLoading && !tasks.length ? <div className="translation-empty"><Languages /><strong>没有匹配的翻译任务</strong></div> : null}
          {tasks.map((task) => <button className={task.id === selected?.id ? "active" : ""} type="button" key={task.id} onClick={() => setSelectedId(task.id)}><span><em data-status={task.status}>{task.status_text}</em><strong>{task.source_file_name}</strong><small>{task.tenant_name || `租户 ${task.tenant_id}`} · {task.user_nickname || task.user_login_name}</small></span><i>#{task.id}</i></button>)}
        </aside>

        <main className="developer-translation-detail">
          {selected ? <>
            <header><div><span>翻译工单 #{selected.id}</span><h2>{selected.source_file_name}</h2><p>{languages[selected.source_language] ?? selected.source_language} → {languages[selected.target_language] ?? selected.target_language} · 创建于 {formatTime(selected.create_time)}</p></div><em data-status={selected.status}>{selected.status_text}</em></header>
            <div className="developer-translation-facts"><div><span>客户团队</span><strong>{selected.tenant_name || `租户 ${selected.tenant_id}`}</strong></div><div><span>提交用户</span><strong>{selected.user_nickname || selected.user_login_name}</strong></div><div><span>制作负责人</span><strong>{selected.operator_name || "尚未接取"}</strong></div><div><span>交付资源</span><strong>视频 {selected.delivery_resource_counts?.video ?? 0} · 口播 {selected.delivery_resource_counts?.voiceover ?? 0} · 字幕 {selected.delivery_resource_counts?.subtitle ?? 0}</strong></div></div>
            <section className="developer-translation-source"><header><h3>客户源视频</h3><button className="secondary-button" type="button" onClick={() => void previewSource()}><Play size={15} />预览源视频</button></header><div><FileVideo2 size={21} /><span><strong>{selected.source_file_name}</strong><small>{formatSize(selected.source_file_size)} · {selected.source_type === "material_library" ? "产品知识库" : "本地上传"}</small></span><button type="button" onClick={async () => { const blob = await developerApi.getAiTranslationSourceBlob(selected.id); downloadBlob(blob, selected.source_file_name); }}><Download size={15} />下载</button></div></section>
            {selected.revision_feedback ? <section className="developer-translation-revision"><strong>客户修改意见（第 {selected.revision_count} 次）</strong><p>{selected.revision_feedback}</p></section> : null}
            <section className="developer-translation-operation"><label>内部制作备注<textarea value={operationNote} maxLength={1000} placeholder="记录接单、制作或失败原因" onChange={(event) => setOperationNote(event.target.value)} /></label><div>{selected.status === "pending" ? <button className="primary-button" type="button" disabled={Boolean(busy)} onClick={() => void action("claim")}>接取任务</button> : null}{["claimed", "revision_requested"].includes(selected.status) ? <button className="primary-button" type="button" disabled={Boolean(busy)} onClick={() => void action("start")}>开始制作</button> : null}{["claimed", "in_progress", "revision_requested"].includes(selected.status) ? <button className="danger-button" type="button" disabled={Boolean(busy)} onClick={() => void action("fail")}><XCircle size={15} />标记失败</button> : null}</div></section>
            {canDeliver ? <section className="developer-translation-upload">
              <header><div><h3>上传交付资源</h3><p>视频、口播和字幕可分别上传，不要求三类资源同时齐全。</p></div></header>
              <div className="translation-resource-tabs" role="group" aria-label="交付资源类型">
                {([{"value":"video","label":"翻译视频"},{"value":"voiceover","label":"口播音频"},{"value":"subtitle","label":"字幕文件"}] as const).map((item) => <button key={item.value} type="button" className={deliveryResourceType === item.value ? "active" : ""} onClick={() => { setDeliveryResourceType(item.value); setDeliveryFiles([]); if (deliveryRef.current) deliveryRef.current.value = ""; }}>{item.label}</button>)}
              </div>
              <input ref={deliveryRef} hidden type="file" multiple accept={deliveryResourceType === "video" ? "video/mp4,video/quicktime,.mp4,.mov" : deliveryResourceType === "voiceover" ? "audio/mpeg,.mp3" : "text/plain,application/x-subrip,.srt,.txt"} onChange={(event) => setDeliveryFiles(Array.from(event.target.files ?? []))} />
              <button className="translation-upload-drop" type="button" onClick={() => deliveryRef.current?.click()}><Upload size={22} /><strong>{deliveryFiles.length ? `已选择 ${deliveryFiles.length} 个文件` : `选择${deliveryResourceType === "video" ? "翻译视频" : deliveryResourceType === "voiceover" ? "口播音频" : "字幕文件"}`}</strong><span>{deliveryFiles.length ? deliveryFiles.map((item) => item.name).join("、") : deliveryResourceType === "video" ? "支持 MP4、MOV" : deliveryResourceType === "voiceover" ? "支持 MP3" : "支持 SRT、TXT"}</span></button>
              <label>交付说明<textarea value={deliveryNote} maxLength={1000} placeholder="记录本次资源版本或修改说明" onChange={(event) => setDeliveryNote(event.target.value)} /></label>
              <div className="developer-translation-delivery-actions"><button className="secondary-button" type="button" disabled={!deliveryFiles.length || Boolean(busy)} onClick={() => void deliver()}>{busy === "deliver" ? <><Loader2 className="spin" />正在保存</> : <><Upload size={16} />保存当前资源</>}</button><button className="primary-button" type="button" disabled={!selected.deliveries.length || Boolean(busy)} onClick={() => void completeDelivery()}>{busy === "complete" ? <><Loader2 className="spin" />正在交付</> : <><CheckCircle2 size={16} />完成本次交付</>}</button></div>
            </section> : null}
            {selected.deliveries.length ? <section className="developer-translation-versions"><header><h3>历史交付资源</h3><span>{selected.delivery_count} 个版本 · {selected.deliveries.length} 个文件</span></header>{selected.deliveries.map((delivery) => <div key={delivery.id}>{delivery.resource_type === "voiceover" ? <FileAudio2 size={18} /> : delivery.resource_type === "subtitle" ? <FileText size={18} /> : <FileVideo2 size={18} />}<span><strong>V{delivery.delivery_no}.{delivery.asset_no} · {delivery.file_name}</strong><small>{delivery.resource_type === "voiceover" ? "口播音频" : delivery.resource_type === "subtitle" ? "字幕文件" : "翻译视频"} · {formatSize(delivery.file_size)} · {formatTime(delivery.create_time)}</small></span>{delivery.resource_type !== "subtitle" ? <button type="button" onClick={() => void handleDelivery(delivery, "preview")}><Play size={14} />预览</button> : null}<button type="button" onClick={() => void handleDelivery(delivery, "download")}><Download size={14} />下载</button></div>)}</section> : null}
          </> : <div className="translation-empty"><Languages /><strong>请选择一个翻译工单</strong></div>}
        </main>
      </div>
      {previewUrl ? <div className="translation-modal-backdrop"><section className="translation-preview-modal" role="dialog" aria-modal="true"><header><h2>{previewType === "audio" ? "口播预览" : "视频预览"}</h2><button type="button" aria-label="关闭预览" onClick={() => setPreviewUrl("")}><XCircle /></button></header>{previewType === "audio" ? <audio src={previewUrl} controls autoPlay /> : <video src={previewUrl} controls autoPlay playsInline />}</section></div> : null}
    </section>
  );
}
