import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BellRing,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  ListChecks,
  RefreshCw,
  ScanSearch,
  Scissors,
  ScrollText,
  Settings2,
  ShieldCheck,
  Users,
  WalletCards
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { developerApi } from "../api/developerClient";
import type { DeveloperPageKey } from "../components/DeveloperShell";
import type { DeveloperAlert, DeveloperPlatformOverview } from "../types";
import {
  alertServiceLabel,
  derivePlatformState,
  formatDuration,
  formatLatency,
  selectPrimaryIssue
} from "./developerOverviewModel";

type DeveloperOverviewPageProps = {
  onNavigate: (page: DeveloperPageKey) => void;
};

const countFormatter = new Intl.NumberFormat("zh-CN");
const formatCount = (value: number) => countFormatter.format(value);
const formatDateTime = (timestamp: number) => timestamp
  ? new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false
    }).format(new Date(timestamp * 1000))
  : "暂无";
const formatHour = (timestamp: number) => new Intl.DateTimeFormat("zh-CN", {
  hour: "2-digit",
  hour12: false
}).format(new Date(timestamp * 1000));

const commonApps = [
  { key: "tasks" as const, label: "统一任务中心", detail: "汇总爆款解析、视频交付与发布任务", Icon: ListChecks, tone: "blue" },
  { key: "alerts" as const, label: "告警与事件", detail: "处理服务异常、超时任务和平台事件", Icon: BellRing, tone: "red" },
  { key: "videoJobs" as const, label: "视频交付中心", detail: "领取制作任务并交付视频与字幕", Icon: Scissors, tone: "cyan" },
  { key: "aiJobs" as const, label: "AI 任务排查", detail: "定位失败原因与模型请求链路", Icon: ScanSearch, tone: "purple" },
  { key: "billing" as const, label: "算力管理", detail: "查看客户算力、充值审核与流水", Icon: WalletCards, tone: "green" },
  { key: "aiSettings" as const, label: "AI Provider 配置", detail: "维护豆包与 DeepSeek 模型连接", Icon: Settings2, tone: "cyan" },
  { key: "customers" as const, label: "客户账号管理", detail: "管理客户、管理员和用户状态", Icon: Users, tone: "teal" },
  { key: "access" as const, label: "内部账号权限", detail: "控制开发者成员及访问权限", Icon: ShieldCheck, tone: "blue" },
  { key: "audit" as const, label: "审计日志", detail: "追溯高风险操作与敏感字段访问", Icon: ScrollText, tone: "cyan" }
];

const stateContent = {
  healthy: { title: "平台运行正常", summary: "核心服务与业务任务均在正常范围内。", Icon: CheckCircle2 },
  degraded: { title: "平台存在性能异常", summary: "部分指标偏离目标值，请尽快检查。", Icon: AlertTriangle },
  down: { title: "平台存在严重异常", summary: "关键服务或紧急告警正在影响交付。", Icon: AlertTriangle }
};

export function DeveloperOverviewPage({ onNavigate }: DeveloperOverviewPageProps) {
  const [overview, setOverview] = useState<DeveloperPlatformOverview | null>(null);
  const [alerts, setAlerts] = useState<DeveloperAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadOverview = useCallback(async () => {
    setLoading(true);
    setError("");
    const [overviewResult, alertsResult] = await Promise.allSettled([
      developerApi.getPlatformOverview(),
      developerApi.listPlatformAlerts(new URLSearchParams({ page: "1", page_size: "6" }))
    ]);
    if (overviewResult.status === "fulfilled") {
      setOverview(overviewResult.value);
    } else {
      setError(overviewResult.reason instanceof Error ? overviewResult.reason.message : "平台运行数据加载失败");
    }
    if (alertsResult.status === "fulfilled") {
      setAlerts(alertsResult.value.items);
    } else if (overviewResult.status === "fulfilled") {
      setError("平台状态已更新，但告警数据加载失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const taskTotals = useMemo(() => {
    if (!overview) return { total: 0, pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0 };
    return Object.values(overview.tasks).reduce((total, task) => ({
      total: total.total + task.total,
      pending: total.pending + task.pending,
      running: total.running + task.running,
      completed: total.completed + task.completed,
      failed: total.failed + task.failed,
      cancelled: total.cancelled + task.cancelled
    }), { total: 0, pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0 });
  }, [overview]);

  const renderOverview = (data: DeveloperPlatformOverview) => {
    const platformState = derivePlatformState(data);
    const platformCopy = stateContent[platformState];
    const StateIcon = platformCopy.Icon;
    const issue = selectPrimaryIssue(data, alerts);
    const healthyServices = data.services.filter((service) => service.status === "healthy").length;
    const activeTasks = taskTotals.pending + taskTotals.running;
    const completedBase = Math.max(1, taskTotals.total - taskTotals.cancelled);
    const deliveryRate = Math.max(0, (taskTotals.completed / completedBase) * 100);
    const currentEpoch = data.updated_at || Math.floor(Date.now() / 1000);
    const pendingAlerts = alerts.filter((alert) => alert.status !== "resolved").slice(0, 3);
    const trend = data.ai.trend || [];

    const metrics = [
      { label: "运行中服务", value: `${healthyServices}`, detail: `共 ${data.services.length} 项核心服务`, delta: data.services.length === healthyServices ? "全部正常" : `${data.services.length - healthyServices} 项需关注`, Icon: Activity, tone: "blue" },
      { label: "待处理任务", value: formatCount(activeTasks), detail: `${formatCount(taskTotals.pending)} 待处理 · ${formatCount(taskTotals.running)} 执行中`, delta: taskTotals.failed ? `${formatCount(taskTotals.failed)} 项失败` : "队列稳定", Icon: ListChecks, tone: "green" },
      { label: "告警事件", value: formatCount(data.open_alerts), detail: data.page_alerts ? `${formatCount(data.page_alerts)} 条紧急告警` : "暂无紧急告警", delta: data.page_alerts ? "较高风险" : "风险可控", Icon: BellRing, tone: "red" },
      { label: "交付成功率", value: `${deliveryRate.toFixed(1)}%`, detail: `${formatCount(taskTotals.completed)} 项已完成`, delta: "今日", Icon: CircleDot, tone: "purple" }
    ];

    return <>
      <section className="developer-overview-kpis" aria-label="核心运行指标">
        {metrics.map(({ label, value, detail, delta, Icon, tone }) => <article className={`developer-overview-kpi ${tone}`} key={label}>
          <span className="developer-overview-kpi-icon"><Icon size={25} aria-hidden="true" /></span>
          <div><small>{label}</small><strong>{value}</strong><p>{detail}</p></div>
          <em>{delta}</em>
        </article>)}
      </section>

      <section className="developer-apps-section" aria-labelledby="developer-apps-title">
        <header>
          <div><span><CircleDot size={15} aria-hidden="true" /></span><h2 id="developer-apps-title">常用应用</h2></div>
          <button type="button" onClick={() => onNavigate("access")}><Settings2 size={14} aria-hidden="true" />自定义</button>
        </header>
        <div className="developer-apps-grid">
          {commonApps.map(({ key, label, detail, Icon, tone }) => <button type="button" key={key} onClick={() => onNavigate(key)}>
            <span className={`developer-app-icon ${tone}`}><Icon size={20} aria-hidden="true" /></span>
            <span><strong>{label}</strong><small>{detail}</small></span>
            {key === "alerts" && data.open_alerts ? <i>{data.open_alerts} 条未处理</i> : null}
            {key === "tasks" && activeTasks ? <i>{activeTasks} 项进行中</i> : null}
            {key === "aiJobs" && taskTotals.failed ? <i>{taskTotals.failed} 个失败</i> : null}
            <ChevronRight size={16} aria-hidden="true" />
          </button>)}
        </div>
      </section>

      <div className="developer-overview-lower-grid">
        <section className={`developer-home-panel developer-critical-panel ${platformState}`} aria-labelledby="developer-critical-title">
          <header><span><AlertTriangle size={17} aria-hidden="true" />需要立即处理</span></header>
          <div className="developer-critical-copy"><StateIcon size={26} aria-hidden="true" /><h2 id="developer-critical-title">{platformCopy.title}</h2><p>{platformCopy.summary}</p></div>
          {issue ? <div className="developer-critical-issue"><small>主要问题</small><strong>{issue.title}</strong><span>{issue.summary}{issue.value ? ` · ${issue.value}` : ""}</span></div> : null}
          <footer><button type="button" onClick={() => onNavigate(issue?.targetPage || "alerts")}>立即处理 <ArrowRight size={15} aria-hidden="true" /></button><small>数据更新于 {formatDateTime(data.updated_at)}</small></footer>
        </section>

        <section className="developer-home-panel developer-pending-panel" aria-labelledby="developer-pending-title">
          <header><div><span className="developer-section-icon"><BellRing size={16} aria-hidden="true" /></span><div><h2 id="developer-pending-title">待处理事项</h2><p>真实告警按优先级排列</p></div></div><button type="button" onClick={() => onNavigate("alerts")}>全部事项 <ChevronRight size={14} aria-hidden="true" /></button></header>
          {pendingAlerts.length ? <ol>{pendingAlerts.map((alert) => <li key={alert.id}>
            <span className={`developer-alert-priority ${alert.severity}`}>{alert.severity === "page" ? "P1" : "P2"}</span>
            <div><strong>{alert.title}</strong><small>{alertServiceLabel(alert.alert_type)} · 已持续 {formatDuration(alert.detected_at, currentEpoch)} · {alert.assigned_user_name || "未分配负责人"}</small></div>
            <button type="button" aria-label={`查看告警：${alert.title}`} onClick={() => onNavigate("alerts")}><ChevronRight size={16} aria-hidden="true" /></button>
          </li>)}</ol> : <div className="developer-command-empty compact"><CheckCircle2 size={24} aria-hidden="true" /><strong>当前没有待处理告警</strong><span>系统将持续监测异常事件</span></div>}
        </section>

        <section className="developer-home-panel developer-trend-panel" aria-labelledby="developer-trend-title">
          <header><div><span className="developer-section-icon"><Activity size={16} aria-hidden="true" /></span><div><h2 id="developer-trend-title">24 小时运行趋势</h2><p>AI 成功率与调用耗时</p></div></div><span>近 24 小时</span></header>
          <div className="developer-trend-summary"><div><small>调用量</small><strong>{formatCount(data.ai.calls_24h)}</strong></div><div><small>失败</small><strong>{formatCount(data.ai.failures_24h)}</strong></div><div><small>成功率</small><strong>{(100 - data.ai.failure_rate).toFixed(1)}%</strong></div><div><small>P95</small><strong>{formatLatency(data.ai.p95_latency_ms)}</strong></div></div>
          {trend.length ? <div className="developer-trend-chart" aria-label="AI 调用趋势图"><ResponsiveContainer width="100%" height="100%"><LineChart data={trend} margin={{ top: 12, right: 8, left: -28, bottom: 0 }}><CartesianGrid stroke="var(--developer-border)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="timestamp" tickFormatter={formatHour} axisLine={false} tickLine={false} tick={{ fill: "var(--developer-text-muted)", fontSize: 10 }} /><YAxis axisLine={false} tickLine={false} tick={{ fill: "var(--developer-text-muted)", fontSize: 10 }} /><Tooltip labelFormatter={(value) => formatDateTime(Number(value))} contentStyle={{ border: "1px solid var(--developer-border)", borderRadius: 8, background: "var(--developer-surface)" }} /><Line name="调用量" type="monotone" dataKey="calls" stroke="var(--developer-accent)" strokeWidth={2.5} dot={{ r: 3, fill: "var(--developer-accent)", stroke: "#fff", strokeWidth: 2 }} activeDot={{ r: 4 }} /></LineChart></ResponsiveContainer></div> : <div className="developer-command-empty trend"><Activity size={26} aria-hidden="true" /><strong>近 24 小时暂无可绘制的 AI 调用趋势</strong><span>产生真实 AI 调用记录后，趋势将自动显示。</span></div>}
        </section>
      </div>
    </>;
  };

  return <section className="developer-page developer-command-page developer-overview-page">
    <header className="developer-overview-header">
      <div><h1>平台工作台</h1><p>集中进入日常运营模块，并从真实业务数据中定位需要处理的事项。</p></div>
      <div><span>更新于 {formatDateTime(overview?.updated_at || 0)}</span><button type="button" disabled={loading} onClick={() => void loadOverview()}><RefreshCw className={loading ? "is-spinning" : ""} size={16} aria-hidden="true" />{loading ? "刷新中" : "刷新数据"}</button></div>
    </header>
    {error ? <div className="inline-alert error" role="alert">{error}</div> : null}
    {loading && !overview ? <div className="developer-command-loading" aria-busy="true" role="status"><RefreshCw className="is-spinning" size={20} aria-hidden="true" />正在汇总平台运行数据…</div> : overview ? renderOverview(overview) : null}
  </section>;
}
