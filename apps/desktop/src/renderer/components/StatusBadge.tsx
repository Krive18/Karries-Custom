import type { ScheduledTask } from "../types";


const statusClass: Record<ScheduledTask["status"], string> = {
  "待提交": "status-pending",
  "提交中": "status-running",
  "已提交平台": "status-success",
  "失败": "status-failed"
};


export function StatusBadge({ status }: { status: ScheduledTask["status"] }) {
  return <span className={`status-badge ${statusClass[status]}`}>{status}</span>;
}
