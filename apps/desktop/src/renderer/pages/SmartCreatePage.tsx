import { useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarClock,
  ClipboardCopy,
  FileImage,
  ImagePlus,
  Loader2,
  Sparkles,
  Trash2,
  UploadCloud
} from "lucide-react";

import { api } from "../api/client";
import type {
  AccountView,
  ImageCopyResult,
  TaskCreateRequest
} from "../types";
import { brandAssets } from "../assets";


type SmartCreatePageProps = {
  accounts: AccountView[];
  onCreateTask: (payload: TaskCreateRequest) => Promise<void>;
};

type BrowserMaterialFile = File & {
  path?: string;
};

type MaterialItem = {
  name: string;
  path: string;
  type: string;
};

type AnalysisResult = ImageCopyResult & {
  summary: string;
};

const imageExtensions = new Set([".jpg", ".jpeg", ".png", ".webp", ".bmp"]);
const videoExtensions = new Set([".mp4", ".mov", ".webm"]);


function pad(value: number) {
  return String(value).padStart(2, "0");
}


function defaultScheduleValue() {
  const date = new Date(Date.now() + 3 * 60 * 60 * 1000);
  date.setSeconds(0, 0);
  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes())
  ].join("");
}


function toScheduleTimestamp(value: string) {
  const timestamp = Math.floor(new Date(value).getTime() / 1000);
  if (Number.isFinite(timestamp)) {
    return timestamp;
  }
  return Math.floor((Date.now() + 3 * 60 * 60 * 1000) / 1000);
}


function extensionOf(path: string) {
  const dotIndex = path.lastIndexOf(".");
  return dotIndex >= 0 ? path.slice(dotIndex).toLowerCase() : "";
}


function fileNameOf(path: string) {
  return path.split(/[\\/]/).filter(Boolean).at(-1) || path;
}


function typeFromPath(path: string) {
  const extension = extensionOf(path);
  if (imageExtensions.has(extension)) {
    return `image/${extension.replace(".", "")}`;
  }
  if (videoExtensions.has(extension)) {
    return `video/${extension.replace(".", "")}`;
  }
  return "application/octet-stream";
}


function materialFromFile(file: BrowserMaterialFile): MaterialItem {
  return {
    name: file.name,
    path: file.path || file.webkitRelativePath || file.name,
    type: file.type || typeFromPath(file.name)
  };
}


function materialFromPath(path: string): MaterialItem {
  return {
    name: fileNameOf(path),
    path,
    type: typeFromPath(path)
  };
}


function isImageMaterial(material: MaterialItem) {
  return material.type.startsWith("image/") || imageExtensions.has(extensionOf(material.path));
}


export function SmartCreatePage({ accounts, onCreateTask }: SmartCreatePageProps) {
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | "">("");
  const [customDirection, setCustomDirection] = useState("");
  const [publishType, setPublishType] = useState("图文笔记");
  const [scheduleTime, setScheduleTime] = useState(defaultScheduleValue);
  const [extraPrompt, setExtraPrompt] = useState("");
  const [result, setResult] = useState<null | AnalysisResult>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const imageFiles = useMemo(
    () => materials.filter(isImageMaterial),
    [materials],
  );

  useEffect(() => {
    if (!selectedAccountId && accounts.length > 0) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accounts, selectedAccountId]);

  function updateFiles(nextFiles: FileList | File[]) {
    setMaterials((Array.from(nextFiles) as BrowserMaterialFile[]).map(materialFromFile));
    setResult(null);
    setErrorMessage("");
  }

  function updateMaterialPaths(paths: string[]) {
    setMaterials(paths.map(materialFromPath));
    setResult(null);
    setErrorMessage("");
  }

  async function openMaterialPicker() {
    const selectedPaths = await window.karriesPublisher?.selectMaterials?.();
    if (selectedPaths) {
      updateMaterialPaths(selectedPaths);
      return;
    }
    fileInputRef.current?.click();
  }

  async function handleGenerate() {
    const imagePaths = imageFiles.map((material) => material.path);
    if (imagePaths.length === 0) {
      setErrorMessage("请先上传至少 1 张图片素材");
      return;
    }

    setIsGenerating(true);
    setErrorMessage("");
    try {
      const generated = await api.generateImageCopy({
        image_paths: imagePaths,
        style: customDirection.trim() || "小红书种草",
        extra_prompt: extraPrompt.trim()
      });
      setResult({
        ...generated,
        summary: `已解析 ${imagePaths.length} 张图片素材，可用于小红书图文笔记创作。`
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "AI 解析失败，请稍后重试");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSaveTask() {
    if (!result) {
      setErrorMessage("请先点击 AI 智能解析生成文案");
      return;
    }
    const accountId = Number(selectedAccountId || accounts[0]?.id);
    if (!accountId) {
      setErrorMessage("请先在账号管理中新增小红书账号");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");
    try {
      await onCreateTask({
        account_id: accountId,
        task_title: result.title,
        task_body: result.body,
        tags: result.tags,
        image_paths: imageFiles.map((material) => material.path),
        schedule_time: toScheduleTimestamp(scheduleTime)
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "发布任务生成失败");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="page-grid">
      <div className="page-heading">
        <h1>素材智能解析</h1>
        <p>上传本地图片或视频，生成小红书标题、正文、标签和素材摘要。</p>
      </div>

      <section className="panel material-panel">
        <div className="panel-title">
          <h2>本地素材</h2>
          <div className="panel-actions">
            <button className="soft-button" type="button" onClick={openMaterialPicker}>
              <ImagePlus size={16} aria-hidden="true" />
              <span>选择图片/视频</span>
            </button>
            <button className="quiet-danger" type="button" onClick={() => updateMaterialPaths([])}>
              <Trash2 size={16} aria-hidden="true" />
              清空素材
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          className="hidden-file-input"
          type="file"
          accept="image/*,video/mp4,video/quicktime,video/webm"
          multiple
          onChange={(event) => updateFiles(event.target.files ?? [])}
        />
        <button
          className="upload-zone"
          type="button"
          onClick={openMaterialPicker}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            updateFiles(event.dataTransfer.files);
          }}
        >
          <UploadCloud size={42} aria-hidden="true" />
          <strong>拖入图片或视频到此处，或点击上传</strong>
          <span>支持 JPG、PNG、WEBP、MP4、MOV、WEBM 等常见素材</span>
        </button>

        <div className="material-counts">
          <span>素材 {materials.length}</span>
          <span>图片 {imageFiles.length}</span>
          <span>视频 {materials.filter((material) => material.type.startsWith("video/")).length}</span>
        </div>
      </section>

      <section className="panel result-panel">
        <div className="panel-title">
          <h2>
            <Sparkles size={18} aria-hidden="true" />
            AI 解析结果
          </h2>
        </div>

        {result ? (
          <div className="result-content">
            <span className="eyebrow">智能标题生成</span>
            <h3>{result.title}</h3>
            <p>{result.body}</p>
            <div className="tag-list">
              {result.tags.map((tag) => (
                <span key={tag}>#{tag}</span>
              ))}
            </div>
            <div className="summary-row">
              <FileImage size={18} aria-hidden="true" />
              {result.summary}
            </div>
          </div>
        ) : (
          <div className="empty-result">
            <img src={brandAssets.angelMark} alt="" />
            <strong>上传素材后点击「AI 智能解析」</strong>
            <span>这里将展示 AI 解析生成的标题、正文与标签等内容</span>
            <div className="capability-row">
              <span>智能标题生成</span>
              <span>正文内容创作</span>
              <span>标签推荐</span>
              <span>素材摘要</span>
            </div>
          </div>
        )}
      </section>

      <section className="panel parameter-panel">
        <div className="panel-title">
          <h2>创作参数</h2>
          <span className={result ? "key-status connected" : "key-status"}>{result ? "已生成" : "未连接 Key"}</span>
        </div>

        {errorMessage ? <div className="form-message">{errorMessage}</div> : null}

        <div className="form-grid">
          <label>
            内容方向
            <select defaultValue="小红书种草">
              <option>小红书种草</option>
            </select>
          </label>
          <label>
            自定义方向
            <input
              value={customDirection}
              onChange={(event) => setCustomDirection(event.target.value)}
              placeholder="例如：新品发布、门店活动、课程招生"
            />
          </label>
          <label>
            发布账号
            <select
              value={selectedAccountId}
              onChange={(event) => setSelectedAccountId(Number(event.target.value))}
            >
              {accounts.length === 0 ? <option value="">请先新增账号</option> : null}
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>{account.account_name}</option>
              ))}
            </select>
          </label>
          <label>
            文案语气
            <select defaultValue="自然真诚">
              <option>自然真诚</option>
              <option>精致高级</option>
              <option>轻松活泼</option>
            </select>
          </label>
          <label>
            发布内容类型
            <select value={publishType} onChange={(event) => setPublishType(event.target.value)}>
              <option>图文笔记</option>
              <option>视频笔记</option>
            </select>
          </label>
          <label>
            AI 智能体
            <input value="点绘环球 AI 智能体" readOnly />
          </label>
          <label>
            计划发布时间
            <div className="input-with-icon">
              <CalendarClock size={16} aria-hidden="true" />
              <input
                type="datetime-local"
                value={scheduleTime}
                onChange={(event) => setScheduleTime(event.target.value)}
              />
            </div>
          </label>
          <label className="wide-field">
            补充要求
            <textarea
              value={extraPrompt}
              onChange={(event) => setExtraPrompt(event.target.value)}
              placeholder="例如：突出新品、强调门店体验、语气更生活化"
              rows={3}
            />
          </label>
        </div>

        <div className="primary-row">
          <button className="primary-button" type="button" onClick={handleGenerate}>
            {isGenerating ? <Loader2 size={18} className="spin" aria-hidden="true" /> : <Sparkles size={18} aria-hidden="true" />}
            AI 智能解析
          </button>
          <button className="secondary-button" type="button" onClick={handleSaveTask}>
            {isSaving ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <ClipboardCopy size={17} aria-hidden="true" />}
            生成发布任务
          </button>
        </div>
      </section>
    </section>
  );
}
