import { describe, expect, it } from "vitest";

import { resolveVideoEditHistoryStatus } from "./videoEditHistoryStatus";


const pendingJob = {
  status_name: "submitted" as const,
  status_text: "视频待生成",
  delivered_time: 0,
  delivery_version_count: 0,
  delivery_versions: [],
  delivery_assets: [],
};


describe("resolveVideoEditHistoryStatus", () => {
  it("shows completed instead of publish-ready when a video was delivered", () => {
    expect(resolveVideoEditHistoryStatus({
      ...pendingJob,
      status_name: "delivered",
      status_text: "视频待发布",
      delivered_time: 1782570660,
      delivery_version_count: 1,
      delivery_versions: [{ version: 1 }],
    })).toEqual({ kind: "completed", label: "视频生成完毕" });
  });

  it("treats submitted and in-production jobs as waiting for generation", () => {
    expect(resolveVideoEditHistoryStatus(pendingJob)).toEqual({
      kind: "pending",
      label: "视频待生成",
    });
    expect(resolveVideoEditHistoryStatus({
      ...pendingJob,
      status_name: "in_production",
      status_text: "视频生成中",
    })).toEqual({ kind: "pending", label: "视频待生成" });
  });

  it("keeps revision requests pending even when an older version exists", () => {
    expect(resolveVideoEditHistoryStatus({
      ...pendingJob,
      status_name: "revision_requested",
      status_text: "待返修",
      delivered_time: 1782570660,
      delivery_version_count: 1,
      delivery_versions: [{ version: 1 }],
    })).toEqual({ kind: "pending", label: "视频待生成" });
  });

  it("keeps returned jobs red even when they once had a delivery", () => {
    expect(resolveVideoEditHistoryStatus({
      ...pendingJob,
      status_name: "returned",
      status_text: "已退回",
      delivered_time: 1782570660,
      delivery_version_count: 1,
      delivery_versions: [{ version: 1 }],
    })).toEqual({ kind: "returned", label: "已退回" });
  });
});
