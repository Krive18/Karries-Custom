import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  CalendarClock,
  Captions,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Copy,
  Download,
  FileCheck2,
  Film,
  Headphones,
  Loader2,
  RefreshCw,
  Rocket,
  Save,
  ShieldCheck,
  XCircle
} from "lucide-react";

import { api } from "../api/client";
import type {
  ContentDraftStatus,
  ContentDraftView,
  MatrixPlanItemStatus,
  MatrixPlanItemView,
  MatrixPlanStatus,
  MatrixPlanView,
  VideoEditDeliveryVersion,
  VideoEditDeliveryAsset,
  VideoEditJobView,
  XHSAccountView
} from "../types";


const planStatusMeta: Record<MatrixPlanStatus, { label: string; className: string }> = {
  1: { label: "草稿", className: "neutral" },
  2: { label: "待确认", className: "pending" },
  3: { label: "待发布", className: "pending" },
  4: { label: "发布中", className: "running" },
  5: { label: "已完成", className: "success" },
  6: { label: "存在异常", className: "danger" },
  7: { label: "已取消", className: "neutral" }
};


function deliveryVersionsFor(job: VideoEditJobView): VideoEditDeliveryVersion[] {
  if (Array.isArray(job.delivery_versions) && job.delivery_versions.length > 0) {
    return job.delivery_versions;
  }
  if (job.delivery?.delivery_file_name) {
    return [{ ...job.delivery, version: job.delivery.version || 1 }];
  }
  return [];
}

function deliveryAssetsFor(job: VideoEditJobView): VideoEditDeliveryAsset[] {
  if (Array.isArray(job.delivery_assets) && job.delivery_assets.length > 0) {
    return job.delivery_assets;
  }
  return deliveryVersionsFor(job).map((item) => ({
    ...item,
    resource_type: "video" as const
  }));
}

function deliveryArchiveName(job: VideoEditJobView) {
  const base = (job.job_title || `视频任务-${job.id}`)
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, "-")
    .trim();
  return `${base || `视频任务-${job.id}`}-完整交付包.zip`;
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

const itemStatusMeta: Record<MatrixPlanItemStatus, { label: string; className: string }> = {
  1: { label: "待确认", className: "pending" },
  2: { label: "等待发布", className: "pending" },
  3: { label: "发布中", className: "running" },
  4: { label: "发布成功", className: "success" },
  5: { label: "发布失败", className: "danger" },
  6: { label: "需人工处理", className: "danger" },
  7: { label: "已取消", className: "neutral" }
};

const draftStatusMeta: Record<ContentDraftStatus, { label: string; className: string }> = {
  draft: { label: "待审核", className: "pending" },
  confirmed: { label: "审核通过", className: "success" },
  rejected: { label: "已退回", className: "danger" }
};


function formatTime(timestamp: number) {
  if (!timestamp) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}

function toDateTimeLocal(date: Date) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 16);
}

function defaultScheduleStart() {
  return toDateTimeLocal(new Date(Date.now() + 3 * 60 * 60 * 1000));
}

function defaultScheduleEnd() {
  return toDateTimeLocal(new Date(Date.now() + 27 * 60 * 60 * 1000));
}

function isLoginStateIssue(message: string) {
  const normalized = message.toLowerCase();
  return [
    "cookie文件已失效",
    "cookie文件不存在",
    "登录已失效",
    "重新扫码登录",
    "login expired"
  ].some((marker) => normalized.includes(marker.toLowerCase()));
}

function isMissingMediaIssue(message: string) {
  const normalized = message.toLowerCase();
  return [
    "没有可用图片",
    "补充素材",
    "image paths",
    "image file"
  ].some((marker) => normalized.includes(marker.toLowerCase()));
}

function hasImageMaterial(item: MatrixPlanItemView) {
  if (item.content_type !== "image_text") return true;
  const imagePaths = item.material.image_paths;
  return Array.isArray(imagePaths) && imagePaths.some((path) => String(path).trim());
}

function getItemMessage(item: MatrixPlanItemView) {
  if (item.status === 2 && item.next_retry_time > 0) {
    const reason = item.last_error ? `，上次原因：${item.last_error}` : "";
    return `系统将在 ${formatTime(item.next_retry_time)} 自动重试（已尝试 ${item.attempt_count}/${item.max_attempts} 次）${reason}`;
  }
  if (item.status === 3) {
    return `正在执行第 ${item.attempt_count}/${item.max_attempts} 次发布`;
  }
  if (item.status === 4 && item.submitted_time > 0) {
    return `已于 ${formatTime(item.submitted_time)} 提交至小红书`;
  }
  if (isLoginStateIssue(item.last_error)) {
    return "账号登录已失效，请到账号管理重新扫码登录后重试";
  }
  if (isMissingMediaIssue(item.last_error)) {
    return "任务没有可发布图片，请从产品知识库补充图片后重新创建发布计划";
  }
  return item.last_error || "-";
}

function getItemStatus(
  item: MatrixPlanItemView,
  publishWorkerRunning: boolean
) {
  if ([5, 6].includes(item.status) && isLoginStateIssue(item.last_error)) {
    return { label: "需重新登录", className: "danger" };
  }
  if ([5, 6].includes(item.status) && isMissingMediaIssue(item.last_error)) {
    return { label: "需补充图片", className: "danger" };
  }
  if (item.status === 2 && item.scheduled_time * 1000 < Date.now()) {
    return publishWorkerRunning
      ? { label: "正在补发", className: "running" }
      : { label: "执行服务未运行", className: "danger" };
  }
  return itemStatusMeta[item.status];
}


type PublishTasksPageProps = {
  mode?: "review" | "plans";
};

type ReviewContentItem =
  | {
      key: string;
      kind: "draft";
      title: string;
      body: string;
      tags: string[];
      status: ContentDraftStatus;
      createTime: number;
      source: ContentDraftView;
    }
  | {
      key: string;
      kind: "video";
      title: string;
      body: string;
      tags: string[];
      status: ContentDraftStatus;
      createTime: number;
      source: VideoEditJobView;
    };

type VideoJobCompletionFilter = "all" | "unfinished" | "completed";


function matchesVideoJobCompletionFilter(
  job: VideoEditJobView,
  filter: VideoJobCompletionFilter
) {
  if (filter === "completed") {
    return job.status === 3;
  }
  if (filter === "unfinished") {
    return [1, 2, 4].includes(job.status);
  }
  return true;
}


function isVideoScriptDraft(item: ReviewContentItem) {
  return item.kind === "draft" && item.source.content_type === "video";
}


export function PublishTasksPage({ mode = "plans" }: PublishTasksPageProps) {
  const [drafts, setDrafts] = useState<ContentDraftView[]>([]);
  const [videoJobs, setVideoJobs] = useState<VideoEditJobView[]>([]);
  const [videoJobFilter, setVideoJobFilter] = useState<VideoJobCompletionFilter>("all");
  const [accounts, setAccounts] = useState<XHSAccountView[]>([]);
  const [plans, setPlans] = useState<MatrixPlanView[]>([]);
  const [selectedReviewKey, setSelectedReviewKey] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [planItems, setPlanItems] = useState<MatrixPlanItemView[]>([]);
  const [editorTitle, setEditorTitle] = useState("");
  const [editorBody, setEditorBody] = useState("");
  const [editorTags, setEditorTags] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingDraft, setSavingDraft] = useState(false);
  const [planActionId, setPlanActionId] = useState<number | null>(null);
  const [publishWorkerRunning, setPublishWorkerRunning] = useState(false);
  const [activeVideoAction, setActiveVideoAction] = useState<string | null>(null);
  const [audioPreview, setAudioPreview] = useState<{ key: string; url: string } | null>(null);
  const [subtitlePreview, setSubtitlePreview] = useState<{ key: string; text: string } | null>(null);
  const [revisionJobId, setRevisionJobId] = useState<number | null>(null);
  const [revisionFeedback, setRevisionFeedback] = useState("");
  const [submittingRevision, setSubmittingRevision] = useState(false);
  const [scheduleDraftId, setScheduleDraftId] = useState<number | null>(null);
  const [schedulePlanName, setSchedulePlanName] = useState("");
  const [scheduleAccountIds, setScheduleAccountIds] = useState<number[]>([]);
  const [scheduleStartTime, setScheduleStartTime] = useState(defaultScheduleStart);
  const [scheduleEndTime, setScheduleEndTime] = useState(defaultScheduleEnd);
  const [scheduleInterval, setScheduleInterval] = useState(360);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [message, setMessage] = useState("");

  const reviewItems = useMemo<ReviewContentItem[]>(
    () =>
      [
        ...drafts.map(
          (draft): ReviewContentItem => ({
            key: `draft-${draft.id}`,
            kind: "draft",
            title: draft.title,
            body: draft.body,
            tags: draft.tags,
            status: draft.status,
            createTime: draft.create_time,
            source: draft
          })
        ),
        ...videoJobs.map(
          (job): ReviewContentItem => ({
            key: `video-${job.id}`,
            kind: "video",
            title: job.post_title || job.job_title,
            body: job.post_body,
            tags: job.post_tags,
            status: job.review_status,
            createTime: job.create_time,
            source: job
          })
        )
      ].sort((left, right) => right.createTime - left.createTime),
    [drafts, videoJobs]
  );
  const selectedReviewItem = useMemo(
    () => reviewItems.find((item) => item.key === selectedReviewKey) ?? null,
    [reviewItems, selectedReviewKey]
  );
  const videoJobCounts = useMemo(
    () => ({
      all: videoJobs.length,
      unfinished: videoJobs.filter((job) => matchesVideoJobCompletionFilter(job, "unfinished")).length,
      completed: videoJobs.filter((job) => matchesVideoJobCompletionFilter(job, "completed")).length
    }),
    [videoJobs]
  );
  const visibleVideoJobs = useMemo(
    () => videoJobs.filter((job) => matchesVideoJobCompletionFilter(job, videoJobFilter)),
    [videoJobFilter, videoJobs]
  );
  const reviewActionsLocked = Boolean(
    selectedReviewItem?.kind === "video"
    && [4, 5].includes(selectedReviewItem.source.status)
  );
  const selectedPlan = useMemo(
    () => plans.find((item) => item.id === selectedPlanId) ?? null,
    [plans, selectedPlanId]
  );
  const availableAccounts = useMemo(
    () => accounts.filter((account) => account.status === 1 && account.login_state_ready),
    [accounts]
  );
  const loadPage = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setMessage("");
    }
    try {
      const [draftResult, accountResult, planResult, runtimeResult, videoJobResult] = await Promise.allSettled([
        api.listContentDrafts(),
        api.listXHSAccounts(),
        api.listMatrixPlans(),
        api.checkRuntime(),
        api.listVideoEditJobs()
      ]);

      const nextDrafts = draftResult.status === "fulfilled" ? draftResult.value : null;
      const nextVideoJobs = videoJobResult.status === "fulfilled" ? videoJobResult.value : null;

      if (nextDrafts) {
        setDrafts(nextDrafts);
      }
      if (nextVideoJobs) {
        setVideoJobs(nextVideoJobs);
      }
      if (accountResult.status === "fulfilled") {
        setAccounts(accountResult.value);
      }
      if (planResult.status === "fulfilled") {
        setPlans(planResult.value);
        setSelectedPlanId((current) =>
          current && planResult.value.some((plan) => plan.id === current)
            ? current
            : planResult.value[0]?.id ?? null
        );
      }
      if (runtimeResult.status === "fulfilled") {
        setPublishWorkerRunning(runtimeResult.value.publish_worker_running === true);
      }
      if (nextDrafts || nextVideoJobs) {
        const reviewKeys = [
          ...(nextDrafts ?? []).map((draft) => `draft-${draft.id}`),
          ...(nextVideoJobs ?? []).map((job) => `video-${job.id}`)
        ];
        setSelectedReviewKey((current) => {
          if (current && reviewKeys.includes(current)) {
            return current;
          }
          if (current && (nextDrafts === null || nextVideoJobs === null)) {
            return current;
          }
          return reviewKeys[0] ?? null;
        });
      }

      const failedSections = [
        { result: draftResult, label: "图文审核内容" },
        { result: accountResult, label: "小红书账号" },
        { result: planResult, label: "发布计划" },
        { result: runtimeResult, label: "发布执行状态" },
        { result: videoJobResult, label: "视频审核内容" }
      ]
        .filter(({ result }) => result.status === "rejected")
        .map(({ label }) => label);

      if (!silent && failedSections.length > 0) {
        setMessage(`部分数据暂时未能加载：${failedSections.join("、")}。其余内容已正常显示，请稍后刷新。`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布工作台加载失败");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  async function openDeliveryVideo(
    job: VideoEditJobView,
    version: VideoEditDeliveryVersion,
    action: "preview"
  ) {
    const actionKey = `${action}-${job.id}-${version.version}`;
    setActiveVideoAction(actionKey);
    try {
      const blob = await api.getVideoEditDeliveryVersionBlob(job.id, version.version);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频成片加载失败");
    } finally {
      setActiveVideoAction(null);
    }
  }

  async function downloadDeliveryArchive(job: VideoEditJobView) {
    setActiveVideoAction(`archive-${job.id}`);
    setMessage("");
    try {
      const blob = await api.getVideoEditDeliveryArchiveBlob(job.id);
      downloadBlob(blob, deliveryArchiveName(job));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "完整交付包下载失败");
    } finally {
      setActiveVideoAction(null);
    }
  }

  async function downloadDeliveryVideo(
    job: VideoEditJobView,
    version: VideoEditDeliveryVersion
  ) {
    const actionKey = `download-video-${job.id}-${version.version}`;
    setActiveVideoAction(actionKey);
    setMessage("");
    try {
      const blob = await api.getVideoEditDeliveryVersionBlob(job.id, version.version);
      downloadBlob(
        blob,
        version.delivery_file_name || `视频成片-V${version.version}.mp4`
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "视频成片下载失败");
    } finally {
      setActiveVideoAction(null);
    }
  }

  async function downloadDeliveryResource(
    job: VideoEditJobView,
    resource: VideoEditDeliveryAsset
  ) {
    if (resource.resource_type === "video") return;
    const actionKey = `download-${resource.resource_type}-${job.id}-${resource.version}`;
    setActiveVideoAction(actionKey);
    setMessage("");
    try {
      const blob = await api.getVideoEditDeliveryResourceBlob(
        job.id,
        resource.resource_type,
        resource.version
      );
      const fallbackName = resource.resource_type === "voiceover"
        ? `口播音频-${resource.version}.mp3`
        : `字幕-${resource.version}.srt`;
      downloadBlob(blob, resource.delivery_file_name || fallbackName);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付资源下载失败");
    } finally {
      setActiveVideoAction(null);
    }
  }

  async function openDeliveryResource(
    job: VideoEditJobView,
    resource: VideoEditDeliveryAsset,
    action: "preview" | "copy"
  ) {
    if (resource.resource_type === "video") return;
    const key = `${resource.resource_type}-${job.id}-${resource.version}`;
    setActiveVideoAction(`${action}-${key}`);
    try {
      const blob = await api.getVideoEditDeliveryResourceBlob(
        job.id,
        resource.resource_type,
        resource.version
      );
      if (resource.resource_type === "voiceover") {
        const url = URL.createObjectURL(blob);
        setAudioPreview((current) => {
          if (current) URL.revokeObjectURL(current.url);
          return { key, url };
        });
      } else {
        const text = await blob.text();
        if (action === "copy") {
          await navigator.clipboard.writeText(text);
          setMessage("字幕内容已复制。");
        } else {
          setSubtitlePreview({ key, text });
        }
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付资源加载失败");
    } finally {
      setActiveVideoAction(null);
    }
  }

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadPage(true);
      if (selectedPlanId) {
        void api.listMatrixPlanItems(selectedPlanId).then(setPlanItems);
      }
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [loadPage, selectedPlanId]);

  useEffect(() => () => {
    if (audioPreview) URL.revokeObjectURL(audioPreview.url);
  }, [audioPreview]);

  useEffect(() => {
    if (!selectedReviewItem) {
      setEditorTitle("");
      setEditorBody("");
      setEditorTags("");
      return;
    }
    setEditorTitle(selectedReviewItem.title);
    setEditorBody(selectedReviewItem.body);
    setEditorTags(selectedReviewItem.tags.join(" "));
  }, [selectedReviewItem]);

  useEffect(() => {
    if (!selectedPlanId) {
      setPlanItems([]);
      return;
    }
    void api
      .listMatrixPlanItems(selectedPlanId)
      .then(setPlanItems)
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : "发布明细加载失败");
      });
  }, [selectedPlanId]);

  function parseTags() {
    return Array.from(
      new Set(
        editorTags
          .split(/[\s,，#]+/)
          .map((tag) => tag.trim())
          .filter(Boolean)
      )
    ).slice(0, 20);
  }

  function openSchedule(draft: ContentDraftView) {
    if (draft.status !== "confirmed") {
      setMessage("请先审核通过内容，再安排发布计划");
      return;
    }
    const accountIds = availableAccounts.map((account) => account.id);
    setScheduleDraftId(draft.id);
    setSchedulePlanName(`${draft.title} 发布计划`);
    setScheduleAccountIds(accountIds);
    setScheduleStartTime(defaultScheduleStart());
    setScheduleEndTime(defaultScheduleEnd());
    setScheduleInterval(
      availableAccounts.length > 0
        ? Math.max(...availableAccounts.map((account) => account.min_interval_minutes))
        : 360
    );
    setMessage(
      accountIds.length > 0
        ? "内容已就绪，请确认发布账号和时间"
        : "当前没有已登录的发布账号，请先到账号管理完成扫码登录"
    );
  }

  async function createPublishingPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!scheduleDraftId) return;
    if (!schedulePlanName.trim()) {
      setMessage("请填写计划名称");
      return;
    }
    if (scheduleAccountIds.length === 0) {
      setMessage("请至少选择一个已登录的小红书账号");
      return;
    }
    const startTime = Math.floor(new Date(scheduleStartTime).getTime() / 1000);
    const endTime = Math.floor(new Date(scheduleEndTime).getTime() / 1000);
    if (!startTime || !endTime || endTime < startTime) {
      setMessage("结束时间不能早于开始时间");
      return;
    }

    setCreatingPlan(true);
    setMessage("");
    try {
      const result = await api.createMatrixPlanFromDrafts({
        plan_name: schedulePlanName.trim(),
        draft_ids: [scheduleDraftId],
        xhs_account_ids: scheduleAccountIds,
        schedule_start_time: startTime,
        schedule_end_time: endTime,
        min_interval_minutes: scheduleInterval
      });
      await loadPage(true);
      setSelectedPlanId(result.id);
      setScheduleDraftId(null);
      setMessage("发布计划已创建，可前往“发布计划”确认进入自动发布队列");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布计划创建失败");
    } finally {
      setCreatingPlan(false);
    }
  }

  async function saveReview(status?: ContentDraftStatus) {
    if (!selectedReviewItem) {
      return;
    }
    if (!editorTitle.trim() || (selectedReviewItem.kind === "draft" && !editorBody.trim())) {
      setMessage(selectedReviewItem.kind === "video" ? "视频发布标题不能为空" : "标题和正文不能为空");
      return;
    }
    setSavingDraft(true);
    setMessage("");
    try {
      if (selectedReviewItem.kind === "draft") {
        const updated = await api.updateContentDraft(selectedReviewItem.source.id, {
          title: editorTitle.trim(),
          body: editorBody.trim(),
          tags: parseTags(),
          status: status ?? selectedReviewItem.status
        });
        setDrafts((current) =>
          current.map((item) => (item.id === updated.id ? updated : item))
        );
        if (status === "confirmed") {
          openSchedule(updated);
        }
      } else {
        const updated = await api.updateVideoEditPublishContent(
          selectedReviewItem.source.id,
          {
            post_title: editorTitle.trim(),
            post_body: editorBody.trim(),
            post_tags: parseTags(),
            review_status: status ?? selectedReviewItem.status
          }
        );
        setVideoJobs((current) =>
          current.map((item) => (item.id === updated.id ? updated : item))
        );
      }
      setMessage(
        status === "confirmed"
          ? selectedReviewItem.kind === "video"
            ? selectedReviewItem.source.status === 3
              ? "视频内容已审核通过，成片已进入待发布状态"
              : "视频内容已审核通过，成片交付后将自动进入待发布状态"
            : availableAccounts.length > 0
              ? "内容已审核通过，请安排发布时间和账号"
              : "内容已审核通过，请先到账号管理完成扫码登录"
          : status === "rejected"
            ? "内容已退回"
            : "内容修改已保存"
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "内容保存失败");
    } finally {
      setSavingDraft(false);
    }
  }

  function openRevisionDialog(job: VideoEditJobView) {
    setRevisionJobId(job.id);
    setRevisionFeedback("");
    setMessage("");
  }

  async function submitVideoRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const feedback = revisionFeedback.trim();
    if (!revisionJobId || feedback.length < 10) {
      setMessage("请输入至少 10 个字的具体修改意见");
      return;
    }
    setSubmittingRevision(true);
    setMessage("");
    try {
      const requestId = typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `video-revision-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const updated = await api.requestVideoEditRevision(revisionJobId, {
        feedback,
        client_request_id: requestId
      });
      setVideoJobs((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setRevisionJobId(null);
      setRevisionFeedback("");
      setMessage("返修任务已提交，已扣除 180 算力，开发者将按修改意见进行二次剪辑。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "返修任务提交失败");
    } finally {
      setSubmittingRevision(false);
    }
  }

  function focusVideoReview(jobId: number) {
    setSelectedReviewKey(`video-${jobId}`);
    window.requestAnimationFrame(() => {
      document
        .getElementById("content-review-editor")
        ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  async function confirmPlan(plan: MatrixPlanView) {
    setPlanActionId(plan.id);
    setMessage("");
    try {
      const items =
        selectedPlanId === plan.id
          ? planItems
          : await api.listMatrixPlanItems(plan.id);
      const unavailableAccount = items.find((item) => {
        const account = accounts.find((entry) => entry.id === item.xhs_account_id);
        return !account || account.status !== 1 || !account.login_state_ready;
      });
      if (unavailableAccount) {
        throw new Error("发布账号尚未完成登录，请先到账号管理重新扫码登录");
      }
      if (items.some((item) => !hasImageMaterial(item))) {
        throw new Error("发布内容没有可用图片，请先从产品知识库补充素材并重新生成内容");
      }
      await api.confirmMatrixPlan(plan.id);
      await loadPage(true);
      setSelectedPlanId(plan.id);
      setPlanItems(await api.listMatrixPlanItems(plan.id));
      setMessage("计划已进入自动发布队列，到达设定时间后将自动执行");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "计划确认失败");
    } finally {
      setPlanActionId(null);
    }
  }

  async function cancelPlan(plan: MatrixPlanView) {
    setPlanActionId(plan.id);
    setMessage("");
    try {
      await api.cancelMatrixPlan(plan.id);
      await loadPage(true);
      setPlanItems(await api.listMatrixPlanItems(plan.id));
      setMessage("发布计划已取消");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "计划取消失败");
    } finally {
      setPlanActionId(null);
    }
  }

  async function retryFailedPlan(plan: MatrixPlanView) {
    setPlanActionId(plan.id);
    setMessage("");
    try {
      if (planItems.some((item) => isMissingMediaIssue(item.last_error))) {
        throw new Error("缺少图片的任务无法直接重试，请补充素材后重新创建发布计划");
      }
      const result = await api.retryFailedMatrixPlanItems(plan.id);
      await loadPage(true);
      setSelectedPlanId(plan.id);
      setPlanItems(await api.listMatrixPlanItems(plan.id));
      setMessage(`已重新加入 ${result.retried_item_count ?? 0} 条任务，请关注账号登录状态`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "失败任务重试失败");
    } finally {
      setPlanActionId(null);
    }
  }

  if (loading) {
    return (
      <section className="publish-loading" role="status">
        <Loader2 className="spin" size={30} aria-hidden="true" />
        正在加载发布管理
      </section>
    );
  }

  return (
    <section className="page-stack publish-workspace">
      <div className="page-heading publish-compact-heading">
        <div className="publish-title-line">
          <h1>{mode === "review" ? "内容审核" : "发布计划"}</h1>
          <span>
            {mode === "review"
              ? "统一审核图文与视频发布内容，成片交付与审核结果一一对应"
              : "统一安排发布时间、发布账号并查看自动执行结果"}
          </span>
        </div>
        <button className="secondary-button compact" type="button" onClick={() => void loadPage()}>
          <RefreshCw size={16} aria-hidden="true" />
          刷新
        </button>
      </div>

      {message ? <div className="form-message">{message}</div> : null}
      {mode === "plans" && !publishWorkerRunning && plans.some((plan) => plan.status === 3) ? (
        <div className="app-alert">
          发布执行服务当前未运行，已到时间的任务不会自动提交，请联系系统维护人员启动发布服务。
        </div>
      ) : null}

      <div className="publish-summary" aria-label="发布状态概览">
        <div><FileCheck2 size={18} aria-hidden="true" /><span>待审核</span><strong>{reviewItems.filter((item) => item.status === "draft").length}</strong></div>
        <div><ShieldCheck size={18} aria-hidden="true" /><span>已通过</span><strong>{reviewItems.filter((item) => item.status === "confirmed").length}</strong></div>
        <div><Clock3 size={18} aria-hidden="true" /><span>待发布</span><strong>{plans.filter((item) => item.status === 3).length}</strong></div>
        <div><CheckCircle2 size={18} aria-hidden="true" /><span>已完成</span><strong>{plans.filter((item) => item.status === 5).length}</strong></div>
      </div>

      {mode === "review" ? (
        <div className="publish-workflow-grid review">
        <section className="panel publish-review-panel">
          <div className="panel-title">
            <h2><FileCheck2 size={19} aria-hidden="true" />内容审核</h2>
            <span className="key-status">{reviewItems.length} 条内容</span>
          </div>

          {reviewItems.length === 0 ? (
            <div className="publish-empty-state">
              <FileCheck2 size={32} aria-hidden="true" />
              <strong>暂无待审核内容</strong>
              <span>图文草稿与视频制作需求会统一进入这里审核。</span>
            </div>
          ) : (
            <div className="publish-draft-layout">
              <div className="publish-draft-list" aria-label="图文与视频内容审核列表">
                {reviewItems.map((item) => {
                  const status = draftStatusMeta[item.status];
                  return (
                    <button
                      className={`publish-draft-item ${selectedReviewKey === item.key ? "active" : ""}`}
                      type="button"
                      key={item.key}
                      onClick={() => setSelectedReviewKey(item.key)}
                    >
                      <span className={`status-pill ${status.className}`}>{status.label}</span>
                      <strong>{item.title}</strong>
                      <small>
                        {item.kind === "video"
                          ? "视频内容"
                          : isVideoScriptDraft(item)
                            ? "视频脚本"
                            : "图文内容"} · #
                        {item.source.id}
                      </small>
                      <ChevronRight size={16} aria-hidden="true" />
                    </button>
                  );
                })}
              </div>

              {selectedReviewItem ? (
                <div className="publish-draft-editor" id="content-review-editor">
                  <div className="publish-review-source">
                    <span className={selectedReviewItem.kind === "video" || isVideoScriptDraft(selectedReviewItem) ? "video" : "image"}>
                      {selectedReviewItem.kind === "video" || isVideoScriptDraft(selectedReviewItem)
                        ? <Film size={15} />
                        : <FileCheck2 size={15} />}
                      {selectedReviewItem.kind === "video"
                        ? "视频内容审核"
                        : isVideoScriptDraft(selectedReviewItem)
                          ? "视频脚本草稿"
                          : "图文内容审核"}
                    </span>
                    <small>
                      {selectedReviewItem.kind === "video"
                        ? `对应视频制作任务 #${selectedReviewItem.source.id}`
                        : selectedReviewItem.source.source_type === "viral_analysis"
                          ? `来自爆款解析 · 草稿 #${selectedReviewItem.source.id}`
                          : `对应图文草稿 #${selectedReviewItem.source.id}`}
                    </small>
                  </div>
                  <label>
                    标题
                    <input value={editorTitle} onChange={(event) => setEditorTitle(event.target.value)} />
                  </label>
                  <label>
                    正文{selectedReviewItem.kind === "video" ? "（可选）" : ""}
                    <textarea rows={10} value={editorBody} onChange={(event) => setEditorBody(event.target.value)} />
                  </label>
                  <label>
                    标签
                    <input
                      value={editorTags}
                      onChange={(event) => setEditorTags(event.target.value)}
                      placeholder="使用空格分隔标签"
                    />
                  </label>
                  {selectedReviewItem.kind === "video" ? (
                    <div className="publish-video-review-state">
                      <Film size={17} aria-hidden="true" />
                      <span>
                        {selectedReviewItem.source.status === 3
                          ? "成片已交付。审核通过后将进入待发布状态。"
                          : "成片尚未交付。可先审核发布文案，交付后将自动进入待发布状态。"}
                      </span>
                    </div>
                  ) : null}
                  <div className="publish-review-actions">
                    <button className="secondary-button" type="button" disabled={savingDraft || reviewActionsLocked} onClick={() => void saveReview()}>
                      <Save size={16} aria-hidden="true" />
                      保存修改
                    </button>
                    <button
                      className="quiet-danger"
                      type="button"
                      disabled={savingDraft || reviewActionsLocked}
                      onClick={() => {
                        if (
                          selectedReviewItem.kind === "video"
                          && selectedReviewItem.source.status === 3
                        ) {
                          openRevisionDialog(selectedReviewItem.source);
                        } else {
                          void saveReview("rejected");
                        }
                      }}
                    >
                      <XCircle size={16} aria-hidden="true" />
                      {selectedReviewItem.kind === "video"
                        && selectedReviewItem.source.status === 3
                        ? "退回修改"
                        : "取消任务"}
                    </button>
                    <button className="primary-button" type="button" disabled={savingDraft || reviewActionsLocked} onClick={() => void saveReview("confirmed")}>
                      {savingDraft ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}
                      审核通过
                    </button>
                    {selectedReviewItem.kind === "draft" && selectedReviewItem.status === "confirmed" ? (
                      <button
                        className="secondary-button selected"
                        type="button"
                        disabled={savingDraft}
                        onClick={() => openSchedule(selectedReviewItem.source)}
                      >
                        <CalendarClock size={16} aria-hidden="true" />
                        安排发布计划
                      </button>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </section>

        <section className="panel publish-video-review-panel">
          <div className="panel-title">
            <h2><Film size={19} aria-hidden="true" />内容制定</h2>
            <span className="key-status">{visibleVideoJobs.length} / {videoJobs.length} 个任务</span>
          </div>
          {videoJobs.length === 0 ? (
            <div className="publish-empty-state">
              <Film size={32} aria-hidden="true" />
              <strong>暂无视频制作任务</strong>
              <span>视频需求提交后会显示制作与交付状态，发布文案统一在左侧审核。</span>
            </div>
          ) : (
            <>
              <div className="publish-video-filters" role="group" aria-label="内容制定状态筛选">
                {([
                  ["all", "全部", videoJobCounts.all],
                  ["unfinished", "未完成", videoJobCounts.unfinished],
                  ["completed", "已完成", videoJobCounts.completed]
                ] as const).map(([value, label, count]) => (
                  <button
                    className={videoJobFilter === value ? "active" : ""}
                    type="button"
                    key={value}
                    aria-pressed={videoJobFilter === value}
                    onClick={() => setVideoJobFilter(value)}
                  >
                    <span>{label}</span>
                    <strong>{count}</strong>
                  </button>
                ))}
              </div>
              {visibleVideoJobs.length === 0 ? (
                <div className="publish-empty-state compact">
                  <Film size={28} aria-hidden="true" />
                  <strong>{videoJobFilter === "completed" ? "暂无已完成任务" : "暂无未完成任务"}</strong>
                  <span>切换到“全部”可查看其他状态的视频制作任务。</span>
                </div>
              ) : (
                <div className="publish-video-job-list">
              {visibleVideoJobs.map((job) => (
                <article
                  className={`publish-video-job ${selectedReviewKey === `video-${job.id}` ? "active" : ""}`}
                  key={job.id}
                >
                  <div>
                    <strong>{job.job_title}</strong>
                    <span>{job.user_progress_text}</span>
                  </div>
                  <div className="publish-video-status-row">
                    <span className={job.status === 3
                      ? "status-pill success"
                      : job.status === 5
                        ? "status-pill neutral"
                        : "status-pill pending"}>
                      {job.status_text}
                    </span>
                    <small>计划完成：{formatTime(job.expected_delivery_time)}</small>
                  </div>
                  {deliveryAssetsFor(job).length > 0 ? (
                    <div className="delivery-archive-actions">
                      <button
                        className="primary-button compact"
                        type="button"
                        aria-label={activeVideoAction === `archive-${job.id}`
                          ? "正在打包…"
                          : `一键下载全部（${deliveryAssetsFor(job).length}）`}
                        disabled={activeVideoAction !== null}
                        onClick={() => void downloadDeliveryArchive(job)}
                      >
                        {activeVideoAction === `archive-${job.id}`
                          ? <Loader2 className="spin" size={15} aria-hidden="true" />
                          : <Download size={15} aria-hidden="true" />}
                        {activeVideoAction === `archive-${job.id}`
                          ? "正在打包…"
                          : `一键下载全部（${deliveryAssetsFor(job).length}）`}
                      </button>
                    </div>
                  ) : null}
                  {deliveryVersionsFor(job).length > 0 ? (
                    <div className="delivery-box delivery-video-list">
                      <span>共 {deliveryVersionsFor(job).length} 个可用视频</span>
                      <div>
                        {deliveryVersionsFor(job).map((version) => (
                          <div className="delivery-video-row" key={version.version}>
                            <span title={`V${version.version} · ${version.delivery_file_name || "视频成片"}`}>
                              V{version.version} · {version.delivery_file_name || "视频成片"}
                            </span>
                            <div className="delivery-resource-actions">
                              <button
                                className="secondary-button compact"
                                type="button"
                                aria-label={`预览视频 ${version.delivery_file_name || `V${version.version}`}`}
                                disabled={activeVideoAction !== null}
                                onClick={() => void openDeliveryVideo(job, version, "preview")}
                              >
                                {activeVideoAction === `preview-${job.id}-${version.version}`
                                  ? <Loader2 className="spin" size={15} aria-hidden="true" />
                                  : <Film size={15} aria-hidden="true" />}
                                预览
                              </button>
                              <button
                                className="secondary-button compact"
                                type="button"
                                aria-label={`下载视频 ${version.delivery_file_name || `V${version.version}`}`}
                                disabled={activeVideoAction !== null}
                                onClick={() => void downloadDeliveryVideo(job, version)}
                              >
                                {activeVideoAction === `download-video-${job.id}-${version.version}`
                                  ? <Loader2 className="spin" size={15} aria-hidden="true" />
                                  : <Download size={15} aria-hidden="true" />}
                                下载
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {deliveryAssetsFor(job).some((item) => item.resource_type === "voiceover") ? (
                    <div className="delivery-box delivery-video-list delivery-audio-list">
                      <span>共 {deliveryAssetsFor(job).filter((item) => item.resource_type === "voiceover").length} 个可用口播音频</span>
                      <div>
                        {deliveryAssetsFor(job)
                          .filter((item) => item.resource_type === "voiceover")
                          .map((resource) => {
                            const resourceKey = `voiceover-${job.id}-${resource.version}`;
                            const fileName = resource.delivery_file_name || `口播音频 ${resource.version}`;
                            return (
                              <div className="delivery-video-row" key={resourceKey}>
                                <span title={fileName}><Headphones size={15} aria-hidden="true" />{fileName}</span>
                                <div className="delivery-resource-actions">
                                  <button
                                    className="secondary-button compact"
                                    type="button"
                                    aria-label={`播放 ${fileName}`}
                                    disabled={activeVideoAction !== null}
                                    onClick={() => void openDeliveryResource(job, resource, "preview")}
                                  >播放</button>
                                  <button
                                    className="secondary-button compact"
                                    type="button"
                                    aria-label={`下载口播 ${fileName}`}
                                    disabled={activeVideoAction !== null}
                                    onClick={() => void downloadDeliveryResource(job, resource)}
                                  >
                                    {activeVideoAction === `download-voiceover-${job.id}-${resource.version}`
                                      ? <Loader2 className="spin" size={15} aria-hidden="true" />
                                      : <Download size={15} aria-hidden="true" />}
                                    下载
                                  </button>
                                </div>
                                {audioPreview?.key === resourceKey ? (
                                  <audio className="delivery-audio-player" controls autoPlay src={audioPreview.url} />
                                ) : null}
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  ) : null}
                  {deliveryAssetsFor(job).some((item) => item.resource_type === "subtitle") ? (
                    <div className="delivery-box delivery-video-list delivery-subtitle-list">
                      <span>共 {deliveryAssetsFor(job).filter((item) => item.resource_type === "subtitle").length} 个可用字幕</span>
                      <div>
                        {deliveryAssetsFor(job)
                          .filter((item) => item.resource_type === "subtitle")
                          .map((resource) => {
                            const resourceKey = `subtitle-${job.id}-${resource.version}`;
                            const fileName = resource.delivery_file_name || `字幕 ${resource.version}`;
                            return (
                              <div className="delivery-video-row" key={resourceKey}>
                                <span title={fileName}><Captions size={15} aria-hidden="true" />{fileName}</span>
                                <div className="delivery-resource-actions">
                                  <button className="secondary-button compact" type="button" aria-label={`查看 ${fileName}`} disabled={activeVideoAction !== null} onClick={() => void openDeliveryResource(job, resource, "preview")}>查看</button>
                                  <button className="secondary-button compact" type="button" aria-label={`复制 ${fileName}`} disabled={activeVideoAction !== null} onClick={() => void openDeliveryResource(job, resource, "copy")}><Copy size={15} aria-hidden="true" />复制</button>
                                  <button className="secondary-button compact" type="button" aria-label={`下载字幕 ${fileName}`} disabled={activeVideoAction !== null} onClick={() => void downloadDeliveryResource(job, resource)}>
                                    {activeVideoAction === `download-subtitle-${job.id}-${resource.version}`
                                      ? <Loader2 className="spin" size={15} aria-hidden="true" />
                                      : <Download size={15} aria-hidden="true" />}
                                    下载
                                  </button>
                                </div>
                                {subtitlePreview?.key === resourceKey ? (
                                  <pre className="delivery-subtitle-preview">{subtitlePreview.text}</pre>
                                ) : null}
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  ) : null}
                  <button
                    className="secondary-button compact publish-video-review-link"
                    type="button"
                    onClick={() => focusVideoReview(job.id)}
                  >
                    <FileCheck2 size={15} aria-hidden="true" />
                    查看对应审核内容
                    <ChevronRight size={15} aria-hidden="true" />
                  </button>
                </article>
              ))}
                </div>
              )}
            </>
          )}
        </section>

        {scheduleDraftId ? (
          <form
            className="panel publish-schedule-panel publish-review-schedule"
            onSubmit={createPublishingPlan}
          >
            <div className="panel-title">
              <div>
                <span className="section-eyebrow">审核后排期</span>
                <h2><CalendarClock size={19} aria-hidden="true" />安排发布计划</h2>
              </div>
              <span className="key-status">1 条已审核内容</span>
            </div>

            <label>
              计划名称
              <input
                value={schedulePlanName}
                onChange={(event) => setSchedulePlanName(event.target.value)}
                placeholder="例如：本周新品发布计划"
              />
            </label>

            <fieldset className="publish-account-fieldset">
              <legend>发布账号</legend>
              {availableAccounts.length === 0 ? (
                <div className="inline-warning">
                  <CircleAlert size={17} aria-hidden="true" />
                  <span>暂无可用账号，请先到账号管理完成扫码登录。</span>
                </div>
              ) : (
                <div className="publish-account-options">
                  {availableAccounts.map((account) => (
                    <label className="publish-account-option" key={account.id}>
                      <input
                        type="checkbox"
                        checked={scheduleAccountIds.includes(account.id)}
                        onChange={(event) => {
                          setScheduleAccountIds((current) =>
                            event.target.checked
                              ? Array.from(new Set([...current, account.id]))
                              : current.filter((id) => id !== account.id)
                          );
                        }}
                      />
                      <span>
                        <strong>{account.display_name}</strong>
                        <small>
                          {account.account_group || "未分组"} · 每日 {account.daily_limit} 篇
                        </small>
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </fieldset>

            <div className="publish-time-grid">
              <label>
                开始时间
                <input
                  type="datetime-local"
                  value={scheduleStartTime}
                  onChange={(event) => setScheduleStartTime(event.target.value)}
                />
              </label>
              <label>
                结束时间
                <input
                  type="datetime-local"
                  value={scheduleEndTime}
                  onChange={(event) => setScheduleEndTime(event.target.value)}
                />
              </label>
            </div>

            <label>
              同账号最小发布间隔（分钟）
              <input
                type="number"
                min={30}
                max={1440}
                value={scheduleInterval}
                onChange={(event) => setScheduleInterval(Number(event.target.value))}
              />
            </label>

            <div className="publish-plan-selection">
              <span>将生成</span>
              <strong>{scheduleAccountIds.length} 条发布任务</strong>
            </div>
            <p className="feature-credit-note">
              定时发布成功后扣除 20 算力 / 条；失败、取消或等待中的任务不扣算力。
            </p>
            <div className="publish-review-actions">
              <button
                className="secondary-button"
                type="button"
                disabled={creatingPlan}
                onClick={() => setScheduleDraftId(null)}
              >
                取消
              </button>
              <button
                className="primary-button publish-create-button"
                type="submit"
                disabled={creatingPlan || availableAccounts.length === 0}
              >
                {creatingPlan
                  ? <Loader2 className="spin" size={17} aria-hidden="true" />
                  : <Rocket size={17} aria-hidden="true" />}
                创建发布计划
              </button>
            </div>
          </form>
        ) : null}
        </div>
      ) : null}

      {mode === "plans" ? (
      <section className="panel publish-plan-panel">
        <div className="panel-title">
          <h2><CalendarClock size={19} aria-hidden="true" />发布计划</h2>
          <span className="key-status">{plans.length} 个计划</span>
        </div>

        {plans.length === 0 ? (
          <div className="publish-empty-state compact">
            <CalendarClock size={30} aria-hidden="true" />
            <strong>尚未创建发布计划</strong>
          </div>
        ) : (
          <div className="publish-plan-layout">
            <div className="publish-plan-list">
              {plans.map((plan) => {
                const status = planStatusMeta[plan.status];
                return (
                  <button
                    type="button"
                    className={`publish-plan-row ${selectedPlanId === plan.id ? "active" : ""}`}
                    key={plan.id}
                    onClick={() => setSelectedPlanId(plan.id)}
                  >
                    <span className={`status-pill ${status.className}`}>{status.label}</span>
                    <strong>{plan.plan_name}</strong>
                    <span>{plan.item_count} 条任务</span>
                    <span>{formatTime(plan.schedule_start_time)}</span>
                    <ChevronRight size={17} aria-hidden="true" />
                  </button>
                );
              })}
            </div>

            {selectedPlan ? (
              <div className="publish-plan-detail">
                <header>
                  <div>
                    <span className={`status-pill ${planStatusMeta[selectedPlan.status].className}`}>
                      {planStatusMeta[selectedPlan.status].label}
                    </span>
                    <h3>{selectedPlan.plan_name}</h3>
                    <p>{formatTime(selectedPlan.schedule_start_time)} 至 {formatTime(selectedPlan.schedule_end_time)}</p>
                  </div>
                  <div className="publish-plan-actions">
                    {selectedPlan.status === 2 ? (
                      <button
                        className="primary-button"
                        type="button"
                        disabled={planActionId === selectedPlan.id}
                        onClick={() => void confirmPlan(selectedPlan)}
                      >
                        <CheckCircle2 size={16} aria-hidden="true" />
                        确认进入发布队列
                      </button>
                    ) : null}
                    {selectedPlan.status === 6 && !planItems.some((item) => isMissingMediaIssue(item.last_error)) ? (
                      <button
                        className="primary-button"
                        type="button"
                        disabled={planActionId === selectedPlan.id}
                        onClick={() => void retryFailedPlan(selectedPlan)}
                      >
                        <RefreshCw size={16} aria-hidden="true" />
                        重试失败任务
                      </button>
                    ) : null}
                    {[1, 2, 3].includes(selectedPlan.status) ? (
                      <button
                        className="quiet-danger"
                        type="button"
                        disabled={planActionId === selectedPlan.id}
                        onClick={() => void cancelPlan(selectedPlan)}
                      >
                        <XCircle size={16} aria-hidden="true" />
                        取消计划
                      </button>
                    ) : null}
                  </div>
                </header>

                <div className="publish-item-table-wrap">
                  <table className="data-table publish-item-table">
                    <thead>
                      <tr>
                        <th>标题</th>
                        <th>账号</th>
                        <th>计划时间</th>
                        <th>状态</th>
                        <th>说明</th>
                      </tr>
                    </thead>
                    <tbody>
                      {planItems.map((item) => {
                        const status = getItemStatus(item, publishWorkerRunning);
                        const account = accounts.find((entry) => entry.id === item.xhs_account_id);
                        return (
                          <tr key={item.id}>
                            <td><strong>{item.title}</strong><span>任务 #{item.id}</span></td>
                            <td>{account?.display_name || `账号 #${item.xhs_account_id}`}</td>
                            <td>{formatTime(item.scheduled_time)}</td>
                            <td>
                              <span className={`status-pill ${status.className}`}>{status.label}</span>
                              {item.attempt_count > 0 ? (
                                <span>尝试 {item.attempt_count}/{item.max_attempts}</span>
                              ) : null}
                            </td>
                            <td className={item.last_error ? "publish-error-cell" : ""}>{getItemMessage(item)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </section>
      ) : null}

      {revisionJobId ? (
        <div className="dialog-backdrop" role="presentation">
          <form
            className="dialog-panel dialog-panel-compact video-revision-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="video-revision-title"
            onSubmit={(event) => void submitVideoRevision(event)}
          >
            <header className="dialog-header">
              <div>
                <h2 id="video-revision-title">提交视频修改意见</h2>
                <p>已交付版本会继续保留，开发者将收到一个新的二次剪辑任务。</p>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label="关闭"
                disabled={submittingRevision}
                onClick={() => setRevisionJobId(null)}
              >
                <XCircle size={19} aria-hidden="true" />
              </button>
            </header>
            <div className="dialog-form video-revision-form">
              <label>
                修改意见
                <textarea
                  rows={6}
                  minLength={10}
                  maxLength={1000}
                  required
                  autoFocus
                  value={revisionFeedback}
                  onChange={(event) => setRevisionFeedback(event.target.value)}
                  placeholder="例如：前 3 秒节奏再快一些，产品特写提前，结尾更换音乐并保留品牌 Logo。"
                />
                <span className="video-revision-counter">
                  {revisionFeedback.length}/1000
                </span>
              </label>
              <div className="video-revision-credit-note">
                <CircleAlert size={17} aria-hidden="true" />
                <span>提交后立即扣除 <strong>180 算力</strong>；重复点击不会重复扣除。</span>
              </div>
            </div>
            <footer className="dialog-actions">
              <button
                className="secondary-button"
                type="button"
                disabled={submittingRevision}
                onClick={() => setRevisionJobId(null)}
              >
                取消
              </button>
              <button
                className="primary-button"
                type="submit"
                disabled={submittingRevision || revisionFeedback.trim().length < 10}
              >
                {submittingRevision
                  ? <Loader2 className="spin" size={16} aria-hidden="true" />
                  : <Check size={16} aria-hidden="true" />}
                确认返修并扣除 180 算力
              </button>
            </footer>
          </form>
        </div>
      ) : null}
    </section>
  );
}
