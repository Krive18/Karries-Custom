import { useEffect, useMemo, useRef, useState } from "react";
import { Clock3, Loader2, Scissors, Send, UploadCloud } from "lucide-react";

import { api } from "../api/client";
import type { VideoEditJobCreate, VideoEditJobView, VideoEditMaterial } from "../types";


type BrowserMaterialFile = File & {
  path?: string;
};


function formatDateTime(timestamp: number) {
  if (!timestamp) {
    return "待确认";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


function materialTypeFromFile(file: File): VideoEditMaterial["file_type"] {
  if (file.type.startsWith("image/")) {
    return "image";
  }
  if (file.type.startsWith("video/")) {
    return "video";
  }
  if (
    file.type.includes("word")
    || file.type.includes("excel")
    || file.name.endsWith(".docx")
    || file.name.endsWith(".xlsx")
    || file.name.endsWith(".pdf")
  ) {
    return "document";
  }
  return "other";
}


function materialFromFile(file: BrowserMaterialFile): VideoEditMaterial {
  return {
    file_name: file.name,
    file_type: materialTypeFromFile(file),
    file_path: file.path || file.webkitRelativePath || file.name,
    mime_type: file.type || "application/octet-stream",
    file_size: file.size,
    remark: ""
  };
}


export function VideoEditPage() {
  const [jobs, setJobs] = useState<VideoEditJobView[]>([]);
  const [materials, setMaterials] = useState<VideoEditMaterial[]>([]);
  const [jobTitle, setJobTitle] = useState("禾一斯小红书种草视频剪辑");
  const [scriptText, setScriptText] = useState("");
  const [requirementText, setRequirementText] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeJobs = useMemo(
    () => jobs.filter((job) => job.status !== 3 && job.status !== 5),
    [jobs],
  );

  async function loadJobs() {
    setIsLoading(true);
    try {
      setJobs(await api.listVideoEditJobs());
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "智能剪辑工单加载失败");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  function updateFiles(files: FileList | File[]) {
    setMaterials((Array.from(files) as BrowserMaterialFile[]).map(materialFromFile));
  }

  async function submitJob() {
    if (!scriptText.trim()) {
      setMessage("请先填写剪辑脚本或剪辑要求");
      return;
    }
    const payload: VideoEditJobCreate = {
      job_title: jobTitle.trim() || "禾一斯小红书种草视频剪辑",
      script_text: scriptText.trim(),
      requirement_text: requirementText.trim(),
      materials
    };

    setIsSubmitting(true);
    try {
      const created = await api.createVideoEditJob(payload);
      setJobs((current) => [created, ...current]);
      setScriptText("");
      setRequirementText("");
      setMaterials([]);
      setMessage("素材和脚本已提交，系统将进入智能剪辑生成流程");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "智能剪辑提交失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-heading horizontal-heading">
        <div>
          <h1>智能剪辑</h1>
          <p>提前 24 小时上传素材和剪辑脚本，系统会显示生成进度，完成后可查看交付视频。</p>
        </div>
        <div className="heading-actions">
          <button className="secondary-button compact" type="button" onClick={loadJobs}>
            {isLoading ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Clock3 size={16} aria-hidden="true" />}
            刷新进度
          </button>
        </div>
      </div>

      {message ? <div className="form-message">{message}</div> : null}

      <div className="video-edit-grid">
        <section className="panel video-edit-submit-panel">
          <div className="panel-title">
            <h2>
              <Scissors size={18} aria-hidden="true" />
              提交剪辑需求
            </h2>
            <span className="key-status">24 小时内生成</span>
          </div>

          <div className="form-grid single">
            <label>
              任务标题
              <input
                value={jobTitle}
                onChange={(event) => setJobTitle(event.target.value)}
                placeholder="例如：新品项链小红书种草视频"
              />
            </label>
            <label>
              剪辑脚本
              <textarea
                value={scriptText}
                onChange={(event) => setScriptText(event.target.value)}
                rows={6}
                placeholder="例如：前3秒展示产品细节，中段展示佩戴场景，结尾引导收藏咨询。"
              />
            </label>
            <label>
              补充要求
              <textarea
                value={requirementText}
                onChange={(event) => setRequirementText(event.target.value)}
                rows={4}
                placeholder="例如：整体节奏自然，保留高级感，不要过度营销。"
              />
            </label>
          </div>

          <input
            ref={fileInputRef}
            className="hidden-file-input"
            type="file"
            accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx"
            multiple
            onChange={(event) => updateFiles(event.target.files ?? [])}
          />
          <button
            className="upload-zone compact-upload-zone"
            type="button"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              updateFiles(event.dataTransfer.files);
            }}
          >
            <UploadCloud size={34} aria-hidden="true" />
            <strong>上传视频、图片或脚本文档</strong>
            <span>已选择 {materials.length} 个素材</span>
          </button>

          {materials.length ? (
            <div className="material-list">
              {materials.map((material) => (
                <div key={`${material.file_name}-${material.file_size}`}>
                  <strong>{material.file_name}</strong>
                  <span>{material.file_type} · {Math.max(1, Math.round(material.file_size / 1024))} KB</span>
                </div>
              ))}
            </div>
          ) : null}

          <div className="primary-row">
            <button className="primary-button" type="button" onClick={submitJob}>
              {isSubmitting ? <Loader2 size={18} className="spin" aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
              提交智能剪辑
            </button>
          </div>
        </section>

        <section className="panel video-edit-status-panel">
          <div className="panel-title">
            <h2>剪辑进度</h2>
            <span className="key-status connected">进行中 {activeJobs.length}</span>
          </div>
          <div className="job-card-list">
            {jobs.length === 0 ? (
              <div className="empty-list-state">暂无剪辑需求，请先提交素材和脚本。</div>
            ) : jobs.map((job) => (
              <article className="job-card" key={job.id}>
                <div>
                  <strong>{job.job_title}</strong>
                  <span>{job.user_progress_text}</span>
                </div>
                <div className="job-meta-row">
                  <span>{job.status_text}</span>
                  <span>预计完成 {formatDateTime(job.expected_delivery_time)}</span>
                  <span>素材 {job.materials.length}</span>
                </div>
                {job.status === 3 ? (
                  <div className="delivery-box">
                    已生成：{String(job.delivery.delivery_file_name || "成片文件")}
                  </div>
                ) : (
                  <div className="progress-track" aria-label="智能剪辑生成中">
                    <span style={{ width: job.status === 1 ? "38%" : "68%" }} />
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
