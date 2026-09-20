import type {
  DeveloperAlert,
  DeveloperPlatformOverview,
  DeveloperServiceHealth
} from "../types";
import type { DeveloperPageKey } from "../components/DeveloperShell";

export const AI_P95_LATENCY_THRESHOLD_MS = 30_000;

export type PlatformState = "healthy" | "degraded" | "down";

export type DeveloperPrimaryIssue = {
  kind: "service" | "alert" | "latency" | "task";
  title: string;
  summary: string;
  value?: string;
  targetPage: DeveloperPageKey;
};

const alertServiceLabels: Record<string, string> = {
  ai_call_failed: "AI Provider",
  matrix_publish_failed: "矩阵发布",
  video_delivery_overdue: "视频交付",
  viral_analysis_failed: "爆款解析"
};

export function derivePlatformState(
  overview: DeveloperPlatformOverview
): PlatformState {
  const failedTasks = Object.values(overview.tasks)
    .reduce((total, task) => total + task.failed, 0);
  if (
    overview.services.some((service) => service.status === "down")
    || overview.page_alerts > 0
  ) {
    return "down";
  }
  if (
    overview.services.some((service) => service.status === "degraded")
    || overview.open_alerts > 0
    || failedTasks > 0
    || (overview.ai.calls_24h > 0
      && overview.ai.p95_latency_ms >= AI_P95_LATENCY_THRESHOLD_MS)
  ) {
    return "degraded";
  }
  return "healthy";
}

export function selectPrimaryIssue(
  overview: DeveloperPlatformOverview,
  alerts: DeveloperAlert[]
): DeveloperPrimaryIssue | null {
  const downService = overview.services.find((service) => service.status === "down");
  if (downService) return serviceIssue(downService);

  const urgentAlert = alerts.find((alert) => alert.severity === "page");
  if (urgentAlert) {
    return {
      kind: "alert",
      title: urgentAlert.title,
      summary: urgentAlert.summary || "该事件需要尽快处理",
      targetPage: "alerts"
    };
  }

  if (overview.page_alerts > 0) {
    return {
      kind: "alert",
      title: `${overview.page_alerts} 个紧急告警待处理`,
      summary: "进入告警中心查看事件详情和负责人",
      value: `${overview.page_alerts} 个`,
      targetPage: "alerts"
    };
  }

  if (
    overview.ai.calls_24h > 0
    && overview.ai.p95_latency_ms >= AI_P95_LATENCY_THRESHOLD_MS
  ) {
    const provider = overview.services.find(
      (service) => service.key.startsWith("provider_")
        && service.status === "degraded"
    );
    return {
      kind: "latency",
      title: `${provider?.label || "AI 调用"} 响应延迟过高`,
      summary: "近 24 小时 P95 高于 30 秒目标值",
      value: formatLatency(overview.ai.p95_latency_ms),
      targetPage: "aiJobs"
    };
  }

  const alert = alerts[0];
  if (alert) {
    return {
      kind: "alert",
      title: alert.title,
      summary: alert.summary || "该事件需要处理",
      targetPage: "alerts"
    };
  }

  const failedTasks = Object.values(overview.tasks)
    .reduce((total, task) => total + task.failed, 0);
  if (failedTasks > 0) {
    return {
      kind: "task",
      title: `${failedTasks} 个失败任务待排查`,
      summary: "失败任务来自用户端和管理端的真实业务记录",
      value: `${failedTasks} 个`,
      targetPage: "tasks"
    };
  }

  const degradedService = overview.services.find(
    (service) => service.status === "degraded"
  );
  return degradedService ? serviceIssue(degradedService) : null;
}

function serviceIssue(service: DeveloperServiceHealth): DeveloperPrimaryIssue {
  return {
    kind: "service",
    title: `${service.label}状态异常`,
    summary: service.detail,
    targetPage: service.key.startsWith("provider_") ? "aiSettings" : "alerts"
  };
}

export function formatLatency(value: number): string {
  if (value < 1_000) return `${Math.max(0, Math.round(value))} ms`;
  return `${(value / 1_000).toFixed(1)} 秒`;
}

export function formatDuration(startedAt: number, now: number): string {
  const seconds = Math.max(0, now - startedAt);
  if (seconds < 60) return "少于 1 分钟";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes
    ? `${hours} 小时 ${remainingMinutes} 分钟`
    : `${hours} 小时`;
}

export function alertServiceLabel(alertType: string): string {
  return alertServiceLabels[alertType] || "平台服务";
}

export function statusLabel(status: DeveloperServiceHealth["status"]): string {
  return {
    healthy: "正常",
    degraded: "性能下降",
    down: "异常",
    unknown: "未配置"
  }[status];
}
