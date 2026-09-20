import type { VideoEditJobView } from "../types";


export type VideoEditHistoryStatusKind = "completed" | "pending" | "returned";

type VideoEditHistoryStatusSource = Pick<
  VideoEditJobView,
  "status_name" | "status_text" | "delivered_time"
> & Partial<Pick<
  VideoEditJobView,
  "delivery_version_count" | "delivery_versions" | "delivery_assets"
>>;


export function resolveVideoEditHistoryStatus(
  job: VideoEditHistoryStatusSource,
): { kind: VideoEditHistoryStatusKind; label: string } {
  if (job.status_name === "returned" || job.status_name === "cancelled") {
    return {
      kind: "returned",
      label: job.status_text.trim() || "已退回",
    };
  }

  if (
    job.status_name === "revision_requested"
    || job.status_name === "in_production"
  ) {
    return { kind: "pending", label: "视频待生成" };
  }

  const hasVideoDelivery = (
    job.status_name === "delivered"
    || job.delivered_time > 0
    || (job.delivery_version_count ?? 0) > 0
    || (job.delivery_versions?.length ?? 0) > 0
    || (job.delivery_assets ?? []).some((asset) => asset.resource_type === "video")
  );

  return hasVideoDelivery
    ? { kind: "completed", label: "视频生成完毕" }
    : { kind: "pending", label: "视频待生成" };
}
