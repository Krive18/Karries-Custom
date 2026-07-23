import type { ViralAnalysisStatus } from "../../types";


const statusLabels: Record<ViralAnalysisStatus, string> = {
  pending: "待解析",
  processing: "解析中",
  completed: "已完成",
  failed: "解析失败",
  cancelled: "已取消"
};


export function viralAnalysisStatusLabel(status: ViralAnalysisStatus) {
  return statusLabels[status];
}
