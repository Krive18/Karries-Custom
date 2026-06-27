import { useMemo, useRef, useState } from "react";
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

import type { ProviderOption, ScheduledTask } from "../types";
import { brandAssets } from "../assets";


const providers: ProviderOption[] = [
  { label: "DeepSeek", value: "deepseek", models: ["deepseek-chat", "deepseek-reasoner"] },
  { label: "GPT", value: "gpt", models: ["gpt-4.1", "gpt-4.1-mini"] },
  { label: "豆包", value: "doubao", models: ["doubao-vision-pro", "doubao-lite"] },
  { label: "Gemini", value: "gemini", models: ["gemini-1.5-pro", "gemini-1.5-flash"] }
];


type SmartCreatePageProps = {
  onSaveTask: (task: ScheduledTask) => void;
};


export function SmartCreatePage({ onSaveTask }: SmartCreatePageProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [provider, setProvider] = useState(providers[0].value);
  const [model, setModel] = useState(providers[0].models[0]);
  const [customDirection, setCustomDirection] = useState("");
  const [publishType, setPublishType] = useState("图文笔记");
  const [scheduleTime, setScheduleTime] = useState("2026/06/27 18:30");
  const [result, setResult] = useState<null | {
    title: string;
    body: string;
    tags: string[];
    summary: string;
  }>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const selectedProvider = useMemo(
    () => providers.find((item) => item.value === provider) ?? providers[0],
    [provider],
  );

  function handleProviderChange(nextProvider: string) {
    const option = providers.find((item) => item.value === nextProvider) ?? providers[0];
    setProvider(option.value);
    setModel(option.models[0]);
  }

  function updateFiles(nextFiles: FileList | File[]) {
    setFiles(Array.from(nextFiles));
  }

  function handleGenerate() {
    setIsGenerating(true);
    window.setTimeout(() => {
      const direction = customDirection.trim() || "小红书种草";
      setResult({
        title: "夏日松弛感穿搭，轻盈又显气质",
        body:
          `这组素材适合围绕「${direction}」来写，重点放在面料质感、上身氛围和日常搭配场景。开头可以先抓住季节感，再自然带出禾一斯的优雅调性，最后引导用户收藏或到店体验。`,
        tags: ["禾一斯", "小红书种草", "通勤穿搭", "气质穿搭"],
        summary: files.length > 0 ? `已识别 ${files.length} 个本地素材，适合做生活方式种草笔记。` : "可先上传图片或视频，AI 会结合素材内容生成文案。"
      });
      setIsGenerating(false);
    }, 450);
  }

  function handleSaveTask() {
    const taskTitle = result?.title || "待解析素材任务";
    onSaveTask({
      id: Date.now(),
      account: "品牌运营号",
      title: taskTitle,
      publishType,
      scheduleTime: scheduleTime.replace("2026/", ""),
      status: "待提交"
    });
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
            <button className="soft-button" type="button" onClick={() => fileInputRef.current?.click()}>
              <ImagePlus size={16} aria-hidden="true" />
              <span>选择图片/视频</span>
            </button>
            <button className="quiet-danger" type="button" onClick={() => setFiles([])}>
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
          onClick={() => fileInputRef.current?.click()}
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
          <span>素材 {files.length}</span>
          <span>图片 {files.filter((file) => file.type.startsWith("image/")).length}</span>
          <span>视频 {files.filter((file) => file.type.startsWith("video/")).length}</span>
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
            AI 服务商
            <select value={provider} onChange={(event) => handleProviderChange(event.target.value)}>
              {providers.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label>
            模型
            <select value={model} onChange={(event) => setModel(event.target.value)}>
              {selectedProvider.models.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            计划发布时间
            <div className="input-with-icon">
              <CalendarClock size={16} aria-hidden="true" />
              <input value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} />
            </div>
          </label>
          <label className="wide-field">
            补充要求
            <textarea placeholder="例如：突出新品、强调门店体验、语气更生活化" rows={3} />
          </label>
        </div>

        <div className="primary-row">
          <button className="primary-button" type="button" onClick={handleGenerate}>
            {isGenerating ? <Loader2 size={18} className="spin" aria-hidden="true" /> : <Sparkles size={18} aria-hidden="true" />}
            AI 智能解析
          </button>
          <button className="secondary-button" type="button" onClick={handleSaveTask}>
            <ClipboardCopy size={17} aria-hidden="true" />
            生成发布任务
          </button>
        </div>
      </section>
    </section>
  );
}
