import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Archive,
  Building2,
  Captions,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Download,
  FileText,
  Film,
  FileVideo2,
  Headphones,
  History,
  Loader2,
  PackageOpen,
  RefreshCw,
  Search,
  Send,
  TimerReset,
  Upload,
  UserRound
} from "lucide-react";

import { developerApi } from "../api/developerClient";
import type {
  AuthUser,
  VideoEditHistoryEntry,
  VideoEditDeliveryAsset,
  VideoEditDeliveryResourceType,
  VideoEditJobView,
  VideoEditMaterial
} from "../types";


const STATUS_OPTIONS = [
  { value: "all", label: "全部工单" },
  { value: "1", label: "待领取" },
  { value: "2", label: "制作中" },
  { value: "3", label: "已交付" },
  { value: "4", label: "待返修" },
  { value: "5", label: "已退回" }
];

const SLA_OPTIONS = [
  { value: "all", label: "全部时限" },
  { value: "overdue", label: "已超时" },
  { value: "due_soon", label: "即将到期" },
  { value: "normal", label: "正常" },
  { value: "completed", label: "已完成" }
];


function formatDateTime(timestamp: number) {
  if (!timestamp) return "待确认";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


function formatBytes(size: number) {
  if (!size) return "0 KB";
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}


function formatRemainingTime(seconds: number, status: VideoEditJobView["sla_status"]) {
  if (status === "completed") return "已完成交付";
  if (status === "returned") return "客户已退回";
  const absoluteSeconds = Math.abs(seconds);
  const hours = Math.floor(absoluteSeconds / 3600);
  const minutes = Math.floor((absoluteSeconds % 3600) / 60);
  const time = hours > 0 ? `${hours} 小时 ${minutes} 分` : `${minutes} 分钟`;
  return status === "overdue" ? `已超时 ${time}` : `剩余 ${time}`;
}


function getSlaLabel(status: VideoEditJobView["sla_status"]) {
  return {
    normal: "正常",
    due_soon: "即将到期",
    overdue: "已超时",
    completed: "已完成",
    returned: "已退回"
  }[status];
}


function getHistoryLabel(action: string) {
  return {
    video_job_claimed: "领取制作任务",
    video_delivery_uploaded: "上传首版成片",
    video_delivery_replaced: "替换交付成片",
    video_voiceover_uploaded: "上传口播音频",
    video_subtitle_uploaded: "上传字幕文件"
  }[action] || action;
}


function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}


type DeveloperVideoJobsPageProps = {
  currentUser: AuthUser | null;
};


export function DeveloperVideoJobsPage({ currentUser }: DeveloperVideoJobsPageProps) {
  const [jobs, setJobs] = useState<VideoEditJobView[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [historyEntries, setHistoryEntries] = useState<VideoEditHistoryEntry[]>([]);
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [slaFilter, setSlaFilter] = useState("all");
  const [deliveryFiles, setDeliveryFiles] = useState<File[]>([]);
  const [voiceoverFiles, setVoiceoverFiles] = useState<File[]>([]);
  const [subtitleFiles, setSubtitleFiles] = useState<File[]>([]);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");

  const loadJobs = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const result = await developerApi.listVideoEditJobs();
      setJobs(result);
      setSelectedJobId((current) => (
        current && result.some((job) => job.id === current)
          ? current
          : result[0]?.id ?? null
      ));
      if (!quiet) setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频交付工单加载失败");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async (jobId: number) => {
    try {
      setHistoryEntries(await developerApi.getVideoEditHistory(jobId));
    } catch {
      setHistoryEntries([]);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
    const refreshTimer = window.setInterval(() => void loadJobs(true), 60_000);
    return () => window.clearInterval(refreshTimer);
  }, [loadJobs]);

  useEffect(() => {
    setDeliveryFiles([]);
    setVoiceoverFiles([]);
    setSubtitleFiles([]);
    setNote("");
    if (selectedJobId) void loadHistory(selectedJobId);
    else setHistoryEntries([]);
  }, [loadHistory, selectedJobId]);

  const summary = useMemo(() => ({
    all: jobs.length,
    submitted: jobs.filter((job) => job.status === 1).length,
    revisions: jobs.filter((job) => job.status === 4).length,
    returned: jobs.filter((job) => job.status === 5).length,
    producing: jobs.filter((job) => job.status === 2).length,
    overdue: jobs.filter((job) => job.sla_status === "overdue").length,
    delivered: jobs.filter((job) => job.status === 3).length
  }), [jobs]);

  const visibleJobs = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return jobs.filter((job) => {
      const matchesStatus = statusFilter === "all" || job.status === Number(statusFilter);
      const matchesSla = slaFilter === "all" || job.sla_status === slaFilter;
      const haystack = [
        job.job_title,
        job.tenant_name,
        job.user_nickname,
        job.user_login_name,
        job.xhs_account_name
      ].join(" ").toLowerCase();
      return matchesStatus && matchesSla && (!normalizedKeyword || haystack.includes(normalizedKeyword));
    });
  }, [jobs, keyword, slaFilter, statusFilter]);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;
  const selectedDeliveryAssets: VideoEditDeliveryAsset[] = selectedJob
    ? (selectedJob.delivery_assets?.length
      ? selectedJob.delivery_assets
      : selectedJob.delivery_versions.map((item) => ({ ...item, resource_type: "video" as const })))
    : [];
  const canClaimSelectedJob = Boolean(
    selectedJob
    && [1, 4].includes(selectedJob.status)
  );

  function replaceJob(updated: VideoEditJobView) {
    setJobs((current) => current.map((job) => job.id === updated.id ? updated : job));
  }

  async function claimJob() {
    if (!selectedJob) return;
    setBusyAction("claim");
    try {
      const updated = await developerApi.claimVideoEditJob(selectedJob.id, {
        note: note.trim() || "已进入视频制作流程"
      });
      replaceJob(updated);
      setNote("");
      setMessage(selectedJob.status === 4
        ? "已接收客户退回，工单状态已更新为制作中。"
        : "任务已领取，工单状态已更新为制作中。");
      await loadHistory(selectedJob.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "领取任务失败");
    } finally {
      setBusyAction("");
    }
  }

  async function uploadDelivery(resourceType: VideoEditDeliveryResourceType) {
    const selectedFiles = resourceType === "video"
      ? deliveryFiles
      : resourceType === "voiceover"
        ? voiceoverFiles
        : subtitleFiles;
    if (!selectedJob || selectedFiles.length === 0) {
      setMessage("请先选择需要上传的交付文件。");
      return;
    }
    setBusyAction(`delivery-${resourceType}`);
    try {
      const replacing = selectedJob.status === 3;
      const updated = await developerApi.uploadVideoEditDelivery(
        selectedJob.id,
        selectedFiles,
        note.trim() || ({
          video: replacing ? "已更新视频成片" : "视频成片已生成",
          voiceover: "已上传口播音频",
          subtitle: "已上传字幕文件"
        }[resourceType]),
        resourceType
      );
      replaceJob(updated);
      if (resourceType === "video") setDeliveryFiles([]);
      if (resourceType === "voiceover") setVoiceoverFiles([]);
      if (resourceType === "subtitle") setSubtitleFiles([]);
      setNote("");
      setMessage(resourceType === "video"
        ? (replacing
          ? "新版本已上传，旧版本仍保留在交付记录中。"
          : "视频成片已交付，用户端状态已更新为视频待发布。")
        : `${resourceType === "voiceover" ? "口播音频" : "字幕文件"}已交付，用户端可立即查看。`);
      await loadHistory(selectedJob.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付文件上传失败");
    } finally {
      setBusyAction("");
    }
  }

  async function downloadMaterial(job: VideoEditJobView, material: VideoEditMaterial) {
    setBusyAction(`material-${material.material_file_id}`);
    try {
      const blob = await developerApi.getVideoEditMaterialBlob(
        job.id,
        material.material_file_id
      );
      downloadBlob(blob, material.file_name);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "素材下载失败");
    } finally {
      setBusyAction("");
    }
  }

  async function downloadArchive(job: VideoEditJobView) {
    setBusyAction("archive");
    try {
      const blob = await developerApi.getVideoEditMaterialsArchiveBlob(job.id);
      downloadBlob(blob, `视频工单-${job.id}-素材.zip`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "素材包下载失败");
    } finally {
      setBusyAction("");
    }
  }

  async function downloadDeliveryVersion(version: number, fileName?: string) {
    if (!selectedJob) return;
    setBusyAction(`version-${version}`);
    try {
      const blob = await developerApi.getVideoEditDeliveryVersionBlob(
        selectedJob.id,
        version
      );
      downloadBlob(blob, fileName || `视频工单-${selectedJob.id}-v${version}.mp4`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付版本下载失败");
    } finally {
      setBusyAction("");
    }
  }

  async function downloadDeliveryResource(resource: VideoEditDeliveryAsset) {
    if (!selectedJob || resource.resource_type === "video") return;
    setBusyAction(`resource-${resource.resource_type}-${resource.version}`);
    try {
      const blob = await developerApi.getVideoEditDeliveryResourceBlob(
        selectedJob.id,
        resource.resource_type,
        resource.version
      );
      downloadBlob(blob, resource.delivery_file_name || `${resource.resource_type}-${resource.version}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付资源下载失败");
    } finally {
      setBusyAction("");
    }
  }

  return (
    <section className="video-delivery-page">
      <div className="video-delivery-heading">
        <div>
          <h1>视频交付中心</h1>
          <p>集中处理客户视频需求、制作素材与成片交付。</p>
        </div>
        <button
          className="secondary-button"
          type="button"
          disabled={loading}
          onClick={() => void loadJobs()}
        >
          <RefreshCw size={16} className={loading ? "spin" : ""} aria-hidden="true" />
          刷新工单
        </button>
      </div>

      {message ? (
        <div className="video-delivery-message" role="status">
          <CircleAlert size={16} aria-hidden="true" />
          {message}
        </div>
      ) : null}

      <div className="video-delivery-summary" aria-label="工单概览">
        <div className="video-delivery-metric">
          <PackageOpen size={18} aria-hidden="true" />
          <span>全部工单</span>
          <strong>{summary.all}</strong>
        </div>
        <div className="video-delivery-metric attention">
          <Clock3 size={18} aria-hidden="true" />
          <span>待领取</span>
          <strong>{summary.submitted}</strong>
        </div>
        <div className="video-delivery-metric attention">
          <TimerReset size={18} aria-hidden="true" />
          <span>待返修</span>
          <strong>{summary.revisions}</strong>
        </div>
        <div className="video-delivery-metric">
          <FileVideo2 size={18} aria-hidden="true" />
          <span>制作中</span>
          <strong>{summary.producing}</strong>
        </div>
        <div className="video-delivery-metric danger">
          <TimerReset size={18} aria-hidden="true" />
          <span>已超时</span>
          <strong>{summary.overdue}</strong>
        </div>
        <div className="video-delivery-metric success">
          <CheckCircle2 size={18} aria-hidden="true" />
          <span>已交付</span>
          <strong>{summary.delivered}</strong>
        </div>
      </div>

      <div className="video-delivery-filterbar">
        <label className="video-delivery-search">
          <Search size={17} aria-hidden="true" />
          <input
            type="search"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索任务、客户、员工或小红书账号"
          />
        </label>
        <label>
          <span className="sr-only">工单状态</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">交付时限</span>
          <select value={slaFilter} onChange={(event) => setSlaFilter(event.target.value)}>
            {SLA_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="video-delivery-layout">
        <aside className="video-delivery-queue">
          <div className="video-delivery-queue-head">
            <strong>制作队列</strong>
            <span>{visibleJobs.length} 项</span>
          </div>
          <div className="video-delivery-list">
            {loading ? (
              <div className="video-delivery-empty">
                <Loader2 size={22} className="spin" aria-hidden="true" />
                正在加载工单
              </div>
            ) : visibleJobs.length === 0 ? (
              <div className="video-delivery-empty">没有符合当前筛选条件的工单</div>
            ) : visibleJobs.map((job) => (
              <button
                className={`video-delivery-queue-item${selectedJobId === job.id ? " selected" : ""}`}
                type="button"
                key={job.id}
                onClick={() => setSelectedJobId(job.id)}
              >
                <span className="video-delivery-item-top">
                  <span className={`sla-badge ${job.sla_status}`}>
                    {getSlaLabel(job.sla_status)}
                  </span>
                  <small>#{job.id}</small>
                </span>
                <strong>{job.job_title}</strong>
                <span className="video-delivery-item-client">
                  {job.tenant_name} · {job.user_nickname || job.user_login_name}
                </span>
                <span className={`video-creation-mode-badge ${job.creation_mode}`}>
                  {job.creation_mode_label}
                </span>
                <span className="video-delivery-item-time">
                  <Clock3 size={14} aria-hidden="true" />
                  {formatRemainingTime(job.seconds_to_delivery, job.sla_status)}
                </span>
              </button>
            ))}
          </div>
        </aside>

        <main className="video-delivery-detail">
          {!selectedJob ? (
            <div className="video-delivery-detail-empty">
              <Archive size={34} aria-hidden="true" />
              <strong>选择一个视频工单</strong>
              <p>客户素材、制作要求、交付版本和操作记录会集中显示在这里。</p>
            </div>
          ) : (
            <>
              <header className="video-delivery-detail-head">
                <div>
                  <div className="video-delivery-detail-tags">
                    <span className={`video-creation-mode-badge ${selectedJob.creation_mode}`}>
                      {selectedJob.creation_mode_label}
                    </span>
                    {selectedJob.sla_status === "returned" ? (
                      <span className="sla-badge returned">已退回</span>
                    ) : (
                      <>
                        <span className={`sla-badge ${selectedJob.sla_status}`}>
                          {formatRemainingTime(selectedJob.seconds_to_delivery, selectedJob.sla_status)}
                        </span>
                        <span className="key-status">{selectedJob.status_text}</span>
                      </>
                    )}
                  </div>
                  <h2>{selectedJob.job_title}</h2>
                  <p>工单 #{selectedJob.id} · 创建于 {formatDateTime(selectedJob.create_time)}</p>
                </div>
                <div className="video-delivery-owner">
                  <span>制作负责人</span>
                  <strong>{selectedJob.operator_name || "尚未领取"}</strong>
                </div>
              </header>

              <section className="video-delivery-meta">
                <div>
                  <Building2 size={17} aria-hidden="true" />
                  <span>客户团队</span>
                  <strong>{selectedJob.tenant_name}</strong>
                </div>
                <div>
                  <UserRound size={17} aria-hidden="true" />
                  <span>提交员工</span>
                  <strong>{selectedJob.user_nickname || selectedJob.user_login_name}</strong>
                </div>
                <div>
                  <FileVideo2 size={17} aria-hidden="true" />
                  <span>发布账号</span>
                  <strong>
                    {selectedJob.xhs_account_name ||
                      (selectedJob.xhs_account_id > 0 ? `账号 #${selectedJob.xhs_account_id}` : "未指定账号")}
                  </strong>
                </div>
                <div>
                  <Clock3 size={17} aria-hidden="true" />
                  <span>计划发布时间</span>
                  <strong>{formatDateTime(selectedJob.planned_publish_time)}</strong>
                </div>
                <div>
                  <Film size={17} aria-hidden="true" />
                  <span>创作模式</span>
                  <strong>{selectedJob.creation_mode_label} · {selectedJob.credit_cost} 算力</strong>
                </div>
              </section>

              <section className="video-delivery-section">
                <div className="video-delivery-section-title">
                  <FileText size={18} aria-hidden="true" />
                  <h3>制作说明</h3>
                </div>
                <div className="video-delivery-copy-grid">
                  <div>
                    <span>视频脚本</span>
                    <p>{selectedJob.script_text || "客户未填写视频脚本。"}</p>
                  </div>
                  <div>
                    <span>补充要求</span>
                    <p>{selectedJob.requirement_text || "客户未填写补充要求。"}</p>
                  </div>
                </div>
              </section>

              {(selectedJob.revision_count ?? 0) > 0 && selectedJob.latest_revision_feedback ? (
                <section className="video-delivery-section video-revision-feedback">
                  <div className="video-delivery-section-title">
                    <TimerReset size={18} aria-hidden="true" />
                    <h3>客户返修意见</h3>
                    <span>第 {selectedJob.revision_count ?? 0} 次返修</span>
                  </div>
                  <p>{selectedJob.latest_revision_feedback}</p>
                  <small>请按照该意见完成新版本，原交付版本保留可供对照。</small>
                </section>
              ) : null}

              <section className="video-delivery-section">
                <div className="video-delivery-section-heading">
                  <div className="video-delivery-section-title">
                    <PackageOpen size={18} aria-hidden="true" />
                    <h3>制作素材</h3>
                    <span>{selectedJob.materials.length} 个文件</span>
                  </div>
                  <button
                    className="secondary-button compact"
                    type="button"
                    disabled={!selectedJob.materials.length || busyAction === "archive"}
                    onClick={() => void downloadArchive(selectedJob)}
                  >
                    {busyAction === "archive"
                      ? <Loader2 size={15} className="spin" aria-hidden="true" />
                      : <Archive size={15} aria-hidden="true" />}
                    打包下载
                  </button>
                </div>
                <div className="video-delivery-material-list">
                  {selectedJob.materials.map((material) => (
                    <div className="video-delivery-material-row" key={material.material_file_id}>
                      <span className="video-delivery-file-icon">
                        {material.file_type === "video"
                          ? <FileVideo2 size={18} aria-hidden="true" />
                          : <FileText size={18} aria-hidden="true" />}
                      </span>
                      <span>
                        <strong>{material.file_name}</strong>
                        <small>{material.file_type} · {formatBytes(material.file_size)}</small>
                      </span>
                      <button
                        className="icon-button"
                        type="button"
                        title="下载素材"
                        disabled={busyAction === `material-${material.material_file_id}`}
                        onClick={() => void downloadMaterial(selectedJob, material)}
                      >
                        {busyAction === `material-${material.material_file_id}`
                          ? <Loader2 size={16} className="spin" aria-hidden="true" />
                          : <Download size={16} aria-hidden="true" />}
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              {selectedDeliveryAssets.length > 0 ? (
                <section className="video-delivery-section">
                  <div className="video-delivery-section-title">
                    <CheckCircle2 size={18} aria-hidden="true" />
                    <h3>交付资源</h3>
                    <span>{selectedDeliveryAssets.length} 个文件</span>
                  </div>
                  <div className="video-delivery-version-list">
                    {[...selectedDeliveryAssets].reverse().map((resource) => {
                      const resourceLabel = resource.resource_type === "video"
                        ? "视频成片"
                        : resource.resource_type === "voiceover"
                          ? "口播音频"
                          : "字幕文件";
                      const ResourceIcon = resource.resource_type === "video"
                        ? FileVideo2
                        : resource.resource_type === "voiceover"
                          ? Headphones
                          : Captions;
                      const busyKey = resource.resource_type === "video"
                        ? `version-${resource.version}`
                        : `resource-${resource.resource_type}-${resource.version}`;
                      return (
                      <div key={`${resource.resource_type}-${resource.version}`}>
                        <ResourceIcon size={17} aria-hidden="true" />
                        <span>
                          <strong>{resourceLabel} {resource.version} · {resource.delivery_file_name || resourceLabel}</strong>
                          <small>
                            {formatDateTime(resource.delivered_time || 0)}
                            {resource.note ? ` · ${resource.note}` : ""}
                          </small>
                        </span>
                        <button
                          className="secondary-button compact"
                          type="button"
                          disabled={busyAction === busyKey}
                          onClick={() => void (resource.resource_type === "video"
                            ? downloadDeliveryVersion(resource.version, resource.delivery_file_name)
                            : downloadDeliveryResource(resource))}
                        >
                          {busyAction === busyKey
                            ? <Loader2 size={15} className="spin" aria-hidden="true" />
                            : <Download size={15} aria-hidden="true" />}
                          下载
                        </button>
                      </div>
                    );})}
                  </div>
                </section>
              ) : null}

              <section className="video-delivery-section">
                <div className="video-delivery-section-title">
                  <History size={18} aria-hidden="true" />
                  <h3>操作记录</h3>
                </div>
                <div className="video-delivery-timeline">
                  {historyEntries.length === 0 ? (
                    <p>暂无内部操作记录。</p>
                  ) : historyEntries.map((entry) => (
                    <div key={entry.id}>
                      <span aria-hidden="true" />
                      <p>
                        <strong>{getHistoryLabel(entry.action)}</strong>
                        <small>{entry.operator_name || "内部制作人员"} · {formatDateTime(entry.create_time)}</small>
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              <section className="video-delivery-action">
                <label>
                  内部制作备注
                  <textarea
                    rows={3}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="记录排期、修改说明或本次交付备注"
                  />
                </label>

                {[2, 3].includes(selectedJob.status) ? (
                  <div className="video-delivery-upload-grid">
                    <label className="video-delivery-upload">
                      <input
                        type="file"
                        multiple
                        accept="video/mp4,video/quicktime,.mp4,.mov"
                        onChange={(event) => setDeliveryFiles(Array.from(event.target.files || []))}
                      />
                      <span>
                        <FileVideo2 size={18} aria-hidden="true" />
                        <strong>{deliveryFiles.length ? `已选择 ${deliveryFiles.length} 个视频` : "视频成片（MP4 / MOV）"}</strong>
                        <small>{deliveryFiles.length
                          ? `${deliveryFiles.map((item) => item.name).join("、")} · ${formatBytes(deliveryFiles.reduce((total, item) => total + item.size, 0))}`
                          : "MP4、MOV，可多选"}</small>
                      </span>
                    </label>
                    <label className="video-delivery-upload">
                      <input
                        type="file"
                        multiple
                        accept="audio/mpeg,.mp3"
                        onChange={(event) => setVoiceoverFiles(Array.from(event.target.files || []))}
                      />
                      <span>
                        <Headphones size={18} aria-hidden="true" />
                        <strong>{voiceoverFiles.length ? `已选择 ${voiceoverFiles.length} 个音频` : "口播音频（MP3）"}</strong>
                        <small>{voiceoverFiles.length
                          ? `${voiceoverFiles.map((item) => item.name).join("、")} · ${formatBytes(voiceoverFiles.reduce((total, item) => total + item.size, 0))}`
                          : "MP3，可多选"}</small>
                      </span>
                    </label>
                    <label className="video-delivery-upload">
                      <input
                        type="file"
                        multiple
                        accept="application/x-subrip,text/plain,.srt,.txt"
                        onChange={(event) => setSubtitleFiles(Array.from(event.target.files || []))}
                      />
                      <span>
                        <Captions size={18} aria-hidden="true" />
                        <strong>{subtitleFiles.length ? `已选择 ${subtitleFiles.length} 个字幕` : "字幕文件（SRT / TXT）"}</strong>
                        <small>{subtitleFiles.length
                          ? `${subtitleFiles.map((item) => item.name).join("、")} · ${formatBytes(subtitleFiles.reduce((total, item) => total + item.size, 0))}`
                          : "SRT、TXT，可多选"}</small>
                      </span>
                    </label>
                  </div>
                ) : null}

                <div className="video-delivery-action-row">
                  {canClaimSelectedJob ? (
                    <button
                      className="primary-button"
                      type="button"
                      disabled={busyAction === "claim"}
                      onClick={() => void claimJob()}
                    >
                      {busyAction === "claim"
                        ? <Loader2 size={17} className="spin" aria-hidden="true" />
                        : <Send size={17} aria-hidden="true" />}
                      领取制作任务
                    </button>
                  ) : null}
                  {[2, 3].includes(selectedJob.status) ? (
                    <>
                      <button
                        className="primary-button"
                        type="button"
                        disabled={deliveryFiles.length === 0 || busyAction !== ""}
                        onClick={() => void uploadDelivery("video")}
                      >
                        {busyAction === "delivery-video" ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <Upload size={17} aria-hidden="true" />}
                        上传视频成片
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={voiceoverFiles.length === 0 || busyAction !== ""}
                        onClick={() => void uploadDelivery("voiceover")}
                      >
                        {busyAction === "delivery-voiceover" ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <Headphones size={17} aria-hidden="true" />}
                        上传口播音频
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={subtitleFiles.length === 0 || busyAction !== ""}
                        onClick={() => void uploadDelivery("subtitle")}
                      >
                        {busyAction === "delivery-subtitle" ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <Captions size={17} aria-hidden="true" />}
                        上传字幕文件
                      </button>
                    </>
                  ) : null}
                </div>
              </section>
            </>
          )}
        </main>
      </div>
    </section>
  );
}
