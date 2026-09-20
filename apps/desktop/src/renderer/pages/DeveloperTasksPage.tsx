import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, Search } from "lucide-react";

import { developerApi } from "../api/developerClient";
import type { DeveloperUnifiedTask } from "../types";


const kindLabels = {
  viral_analysis: "爆款解析",
  video_edit: "视频交付",
  matrix_publish: "矩阵发布"
};
const statusLabels = {
  pending: "待处理",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  unknown: "未知"
};
const getTaskStatusLabel = (task: DeveloperUnifiedTask) => (
  task.kind === "video_edit" && task.status === "cancelled"
    ? "已退回"
    : statusLabels[task.status]
);
const formatTime = (value: number) => value
  ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value * 1000))
  : "-";


export function DeveloperTasksPage() {
  const [items, setItems] = useState<DeveloperUnifiedTask[]>([]);
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [keyword, setKeyword] = useState("");
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [actionTask, setActionTask] = useState<DeveloperUnifiedTask | null>(null);
  const [action, setAction] = useState<"cancel" | "retry">("cancel");
  const [reason, setReason] = useState("");
  const initialized = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setMessage("");
    const params = new URLSearchParams({ page: "1", page_size: "100" });
    if (kind) params.set("kind", kind);
    if (status) params.set("status", status);
    if (keyword.trim()) params.set("keyword", keyword.trim());
    try {
      const result = await developerApi.listPlatformTasks(params);
      setItems(result.items);
      setTotal(result.total);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "任务列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [kind, keyword, status]);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void load();
  }, [load]);

  const openAction = (task: DeveloperUnifiedTask, nextAction: "cancel" | "retry") => {
    setActionTask(task);
    setAction(nextAction);
    setReason("");
    setMessage("");
  };

  const submitAction = async () => {
    if (!actionTask || reason.trim().length < 3) {
      setMessage("请填写至少 3 个字的操作原因");
      return;
    }
    setLoading(true);
    try {
      await developerApi.actOnPlatformTask(actionTask.id, action, reason.trim());
      setActionTask(null);
      setReason("");
      await load();
      setMessage("任务状态已更新，并已写入审计日志");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "任务操作失败");
      setLoading(false);
    }
  };

  return (
    <section className="developer-page developer-ops-page">
      <header className="developer-page-header">
        <div><h1>统一任务中心</h1><p>统一查看视频、爆款解析和矩阵发布任务，仅对安全状态开放人工操作。</p></div>
        <button className="secondary-button" type="button" onClick={() => void load()} disabled={loading}><RefreshCw size={17} />刷新</button>
      </header>
      <section className="developer-ops-filters" aria-label="任务筛选">
        <label>任务类型<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="">全部类型</option><option value="viral_analysis">爆款解析</option><option value="video_edit">视频交付</option><option value="matrix_publish">矩阵发布</option></select></label>
        <label>状态<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">全部状态</option><option value="pending">待处理</option><option value="running">执行中</option><option value="completed">已完成</option><option value="failed">失败</option><option value="cancelled">已取消 / 已退回</option></select></label>
        <label>关键词<input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="任务、账号或用户" /></label>
        <button className="primary-button compact" type="button" onClick={() => void load()}><Search size={16} />查询</button>
      </section>
      {message ? <div className="form-message" role="status">{message}</div> : null}
      {actionTask ? (
        <section className="developer-action-panel" aria-label="任务操作确认">
          <div><strong>{action === "retry" ? "重试" : "取消"}：{actionTask.title}</strong><span>操作原因会永久写入审计日志。</span></div>
          <label>操作原因<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} /></label>
          <div><button className="secondary-button compact" type="button" onClick={() => setActionTask(null)}>返回</button><button className="primary-button compact" type="button" onClick={() => void submitAction()} disabled={loading}>确认{action === "retry" ? "重试" : "取消"}</button></div>
        </section>
      ) : null}
      <section className="developer-ops-table-panel">
        <div className="developer-panel-heading"><div><span>01</span><h2>任务队列</h2></div><small>{total} 项</small></div>
        <div className="developer-ops-table-wrap"><table className="developer-ops-table"><thead><tr><th>任务</th><th>租户 / 用户</th><th>状态</th><th>错误摘要</th><th>更新时间</th><th>操作</th></tr></thead><tbody>
          {items.map((task) => <tr key={`${task.kind}-${task.id}`}><td><strong>#{task.id} {task.title}</strong><small>{kindLabels[task.kind]}</small></td><td><strong>{task.tenant_name}</strong><small>{task.user_name}（{task.login_name}）</small></td><td><span className={`developer-status-pill ${task.status}`}>{getTaskStatusLabel(task)}</span></td><td>{task.error_summary || "-"}</td><td>{formatTime(task.updated_at)}</td><td><div className="table-actions">{task.available_actions.map((item) => <button className="table-action compact" type="button" key={item} onClick={() => openAction(task, item)}>{item === "retry" ? "重试" : "取消"}</button>)}</div></td></tr>)}
          {!loading && !items.length ? <tr><td colSpan={6} className="developer-ops-empty">暂无符合条件的任务</td></tr> : null}
        </tbody></table></div>
      </section>
    </section>
  );
}
