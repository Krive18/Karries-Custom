import { describe, expect, it } from "vitest";

import type { DeveloperPlatformOverview } from "../types";
import {
  alertServiceLabel,
  derivePlatformState,
  formatDuration,
  formatLatency,
  selectPrimaryIssue
} from "./developerOverviewModel";


const baseOverview: DeveloperPlatformOverview = {
  services: [
    { key: "database", label: "MySQL 数据库", status: "healthy", detail: "连接正常" },
    { key: "provider_deepseek", label: "DeepSeek", status: "healthy", detail: "调用正常" }
  ],
  tasks: {
    viral_analysis: { total: 0, pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0 },
    video_edit: { total: 0, pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0 },
    matrix_publish: { total: 0, pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0 }
  },
  ai: {
    calls_24h: 2,
    failures_24h: 0,
    failure_rate: 0,
    p95_latency_ms: 420,
    trend: []
  },
  pool: {
    size: 10,
    total: 2,
    idle: 1,
    in_use: 1,
    pre_ping: true,
    recycle_seconds: 1800,
    closed: false
  },
  open_alerts: 0,
  page_alerts: 0,
  active_developers: 1,
  updated_at: 1_800_000_000
};


describe("developer overview view model", () => {
  it("derives platform state from real service and alert values", () => {
    expect(derivePlatformState(baseOverview)).toBe("healthy");
    expect(derivePlatformState({
      ...baseOverview,
      services: [{ ...baseOverview.services[0], status: "degraded" }]
    })).toBe("degraded");
    expect(derivePlatformState({
      ...baseOverview,
      services: [{ ...baseOverview.services[0], status: "down" }]
    })).toBe("down");
  });

  it("formats real latency and elapsed time without invented precision", () => {
    expect(formatLatency(420)).toBe("420 ms");
    expect(formatLatency(90_946)).toBe("90.9 秒");
    expect(formatDuration(1_000, 1_125)).toBe("2 分钟");
    expect(formatDuration(1_000, 8_500)).toBe("2 小时 5 分钟");
  });

  it("selects actual high latency as the primary issue", () => {
    const issue = selectPrimaryIssue({
      ...baseOverview,
      services: [
        baseOverview.services[0],
        {
          key: "provider_deepseek",
          label: "DeepSeek",
          status: "degraded",
          detail: "P95 90946 ms"
        }
      ],
      ai: { ...baseOverview.ai, p95_latency_ms: 90_946 }
    }, []);

    expect(issue?.kind).toBe("latency");
    expect(issue?.title).toBe("DeepSeek 响应延迟过高");
    expect(issue?.value).toBe("90.9 秒");
  });

  it("returns no primary issue for a healthy platform", () => {
    expect(selectPrimaryIssue(baseOverview, [])).toBeNull();
  });

  it("maps persisted alert types to readable service labels", () => {
    expect(alertServiceLabel("ai_call_failed")).toBe("AI Provider");
    expect(alertServiceLabel("video_delivery_overdue")).toBe("视频交付");
    expect(alertServiceLabel("custom_detector")).toBe("平台服务");
  });
});
