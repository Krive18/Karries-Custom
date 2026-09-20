import { useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  ClipboardCopy,
  FileImage,
  FolderOpen,
  History,
  Loader2,
  Sparkles,
  Trash2
} from "lucide-react";

import { api } from "../api/client";
import { MaterialLibraryPicker } from "../components/material/MaterialLibraryPicker";
import { MaterialThumbnail } from "../components/material/MaterialThumbnail";
import type {
  ContentDraftView,
  ImageCopyResult,
  MaterialAsset,
  TaskCreateRequest,
  XHSAccountView
} from "../types";
import { brandAssets } from "../assets";


type SmartCreatePageProps = {
  accounts: XHSAccountView[];
  onCreateTask: (payload: TaskCreateRequest) => Promise<void>;
};

type AnalysisResult = ImageCopyResult & {
  summary: string;
  historyId: number;
  materialIds: number[];
};


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

function historyMaterialIds(draft: ContentDraftView) {
  const rawIds = draft.material.material_ids;
  return Array.isArray(rawIds)
    ? rawIds.filter((value): value is number => typeof value === "number")
    : [];
}


function formatHistoryTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}


export function SmartCreatePage({ accounts, onCreateTask }: SmartCreatePageProps) {
  const [materials, setMaterials] = useState<MaterialAsset[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | "">("");
  const [customDirection, setCustomDirection] = useState("");
  const [publishType, setPublishType] = useState("图文笔记");
  const [scheduleTime, setScheduleTime] = useState(defaultScheduleValue);
  const [extraPrompt, setExtraPrompt] = useState("");
  const [result, setResult] = useState<null | AnalysisResult>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLibraryPickerOpen, setIsLibraryPickerOpen] = useState(false);
  const [history, setHistory] = useState<ContentDraftView[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const imageFiles = useMemo(
    () => materials.filter((material) => material.file_type === "image"),
    [materials],
  );

  useEffect(() => {
    if (!selectedAccountId && accounts.length > 0) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accounts, selectedAccountId]);

  useEffect(() => {
    void refreshHistory();
  }, []);

  async function refreshHistory() {
    setIsHistoryLoading(true);
    try {
      setHistory(await api.listSmartCreationHistory());
    } finally {
      setIsHistoryLoading(false);
    }
  }

  async function handleGenerate() {
    const materialIds = imageFiles.map((material) => material.id);
    if (materialIds.length === 0) {
      setErrorMessage("请先从产品知识库选择至少 1 张图片素材");
      return;
    }

    setIsGenerating(true);
    setErrorMessage("");
    try {
      const generated = await api.generateImageCopy({
        image_paths: [],
        material_ids: materialIds,
        xhs_account_id: Number(selectedAccountId || 0),
        style: customDirection.trim() || "小红书种草",
        extra_prompt: extraPrompt.trim()
      });
      setResult({
        ...generated,
        summary: `已解析 ${materialIds.length} 张产品库图片，可用于小红书图文笔记创作。`,
        historyId: generated.history_id ?? 0,
        materialIds
      });
      await refreshHistory();
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
        draft_id: result.historyId || undefined,
        account_id: accountId,
        task_title: result.title,
        task_body: result.body,
        tags: result.tags,
        image_paths: [],
        material_ids: result.materialIds,
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
      <div className="page-heading compact-page-heading">
        <div className="page-heading-copy">
          <h1>素材智能解析</h1>
          <p>从产品知识库选图，生成标题、正文、标签和素材摘要。</p>
        </div>
      </div>

      <section className="panel material-panel">
        <div className="panel-title">
          <h2>创作素材</h2>
          <div className="panel-actions">
            <button className="primary-button" type="button" onClick={() => setIsLibraryPickerOpen(true)}>
              <FolderOpen size={16} aria-hidden="true" />
              <span>从产品知识库选择</span>
            </button>
            <button className="quiet-danger" type="button" onClick={() => setMaterials([])}>
              <Trash2 size={16} aria-hidden="true" />
              清空素材
            </button>
          </div>
        </div>

        {materials.length === 0 ? (
          <button
            className="knowledge-library-source"
            type="button"
            onClick={() => setIsLibraryPickerOpen(true)}
          >
            <FolderOpen size={42} aria-hidden="true" />
            <strong>从产品知识库选择图片</strong>
            <span>素材统一在产品知识库中归档，本次创作只需选用已有产品图片。</span>
          </button>
        ) : null}

        <div className="material-counts">
          <span>素材 {materials.length}</span>
          <span>图片 {imageFiles.length}</span>
          <span>视频 {materials.filter((material) => material.file_type === "video").length}</span>
        </div>
        {materials.length ? (
          <div className="smart-material-strip">
            {materials.map((material) => (
              <article key={material.id}>
                <MaterialThumbnail asset={material} />
                <span title={material.file_name}>{material.file_name}</span>
                <button
                  type="button"
                  aria-label={`移除 ${material.file_name}`}
                  title="从本次创作移除"
                  onClick={() => setMaterials((current) => current.filter((item) => item.id !== material.id))}
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </article>
            ))}
          </div>
        ) : null}
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
            <strong>选择产品图片后点击「AI 智能解析」</strong>
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
          <span className={result ? "key-status connected" : "key-status"}>{result ? "已生成" : "待生成"}</span>
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
                <option key={account.id} value={account.id}>{account.display_name}</option>
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

      <section className="panel creation-history-panel">
        <div className="panel-title">
          <h2>
            <History size={18} aria-hidden="true" />
            创作历史
          </h2>
          <button className="icon-button" type="button" title="刷新创作历史" onClick={() => void refreshHistory()}>
            {isHistoryLoading ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <History size={17} aria-hidden="true" />}
          </button>
        </div>
        {history.length ? (
          <div className="creation-history-list">
            {history.slice(0, 20).map((draft) => (
              <button
                className={result?.historyId === draft.id ? "creation-history-item active" : "creation-history-item"}
                key={draft.id}
                type="button"
                onClick={() => {
                  const materialIds = historyMaterialIds(draft);
                  setResult({
                    title: draft.title,
                    body: draft.body,
                    tags: draft.tags,
                    history_id: draft.id,
                    historyId: draft.id,
                    materialIds,
                    summary: `已恢复历史任务，共关联 ${materialIds.length} 张产品库图片。`
                  });
                  if (draft.xhs_account_id > 0) {
                    setSelectedAccountId(draft.xhs_account_id);
                  }
                  setErrorMessage("");
                }}
              >
                <span>
                  <strong>{draft.title}</strong>
                  <small>{formatHistoryTime(draft.create_time)}</small>
                </span>
                <em>{draft.status === "confirmed" ? "已加入发布" : "草稿"}</em>
              </button>
            ))}
          </div>
        ) : (
          <div className="creation-history-empty">
            {isHistoryLoading ? "正在加载创作历史" : "完成一次 AI 智能解析后，记录会自动保存在这里"}
          </div>
        )}
      </section>

      <MaterialLibraryPicker
        open={isLibraryPickerOpen}
        allowedTypes={["image"]}
        initialSelection={imageFiles}
        onClose={() => setIsLibraryPickerOpen(false)}
        onConfirm={(selectedAssets) => {
          setMaterials(selectedAssets);
          setResult(null);
          setErrorMessage("");
          setIsLibraryPickerOpen(false);
        }}
      />
    </section>
  );
}
