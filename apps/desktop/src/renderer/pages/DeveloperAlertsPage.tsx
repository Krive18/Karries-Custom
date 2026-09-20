import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BellRing,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Download,
  RefreshCw,
  Search,
  ShieldAlert,
  X
} from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { developerApi } from "../api/developerClient";
import type { DeveloperAlert } from "../types";

const statusLabels = { open: "待处理", acknowledged: "处理中", resolved: "已解决" };
const severityLabels = { page: "紧急", ticket: "工单" };
const formatTime = (value: number) => value
  ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value * 1000))
  : "-";

type AlertStatusFilter = "" | DeveloperAlert["status"];

export function DeveloperAlertsPage() {
  const [items, setItems] = useState<DeveloperAlert[]>([]);
  const [status, setStatus] = useState<AlertStatusFilter>("");
  const [severity, setSeverity] = useState("");
  const [source, setSource] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState<DeveloperAlert | null>(null);
  const [detailAlert, setDetailAlert] = useState<DeveloperAlert | null>(null);
  const [action, setAction] = useState<"acknowledge" | "resolve">("acknowledge");
  const [reason, setReason] = useState("");
  const initialized = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setMessage("");
    try {
      const result = await developerApi.listPlatformAlerts(new URLSearchParams({ page: "1", page_size: "100" }));
      setItems(result.items);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "告警加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void load();
  }, [load]);

  const counts = useMemo(() => ({
    all: items.length,
    open: items.filter((item) => item.status === "open").length,
    acknowledged: items.filter((item) => item.status === "acknowledged").length,
    resolved: items.filter((item) => item.status === "resolved").length,
    urgent: items.filter((item) => item.severity === "page" && item.status !== "resolved").length,
    today: items.filter((item) => new Date(item.detected_at * 1000).toDateString() === new Date().toDateString()).length
  }), [items]);

  const filteredItems = useMemo(() => items.filter((item) => {
    const matchesKeyword = !keyword.trim() || `${item.title} ${item.summary} ${item.source_type}`.toLowerCase().includes(keyword.trim().toLowerCase());
    return matchesKeyword
      && (!status || item.status === status)
      && (!severity || item.severity === severity)
      && (!source || item.source_type === source);
  }), [items, keyword, severity, source, status]);

  const sourceOptions = useMemo(() => Array.from(new Set(items.map((item) => item.source_type))).filter(Boolean), [items]);
  const distribution = [
    { name: "待处理", value: counts.open, color: "#ef5350" },
    { name: "处理中", value: counts.acknowledged, color: "#f5a623" },
    { name: "已解决", value: counts.resolved, color: "#2db878" }
  ].filter((item) => item.value > 0);

  const openAction = (alert: DeveloperAlert, next: "acknowledge" | "resolve") => {
    setSelected(alert);
    setAction(next);
    setReason("");
    setMessage("");
  };

  const submit = async () => {
    if (!selected || reason.trim().length < 3) {
      setMessage("请填写至少 3 个字的处理说明");
      return;
    }
    setLoading(true);
    try {
      if (action === "acknowledge") await developerApi.acknowledgePlatformAlert(selected.id, reason.trim());
      else await developerApi.resolvePlatformAlert(selected.id, reason.trim());
      setSelected(null);
      setReason("");
      await load();
      setMessage("告警状态已更新，并已写入审计日志");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "告警操作失败");
      setLoading(false);
    }
  };

  const exportCsv = () => {
    const header = ["级别", "事件", "来源", "最近发生", "负责人", "状态"];
    const rows = filteredItems.map((item) => [severityLabels[item.severity], item.title, `${item.source_type} #${item.source_id}`, formatTime(item.last_seen_at), item.assigned_user_name || "待认领", statusLabels[item.status]]);
    const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `platform-alerts-${Date.now()}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return <section className="developer-page developer-ops-page developer-alerts-workbench">
    <header className="developer-alerts-header">
      <div><span className="developer-page-icon"><ShieldAlert size={22} aria-hidden="true" /></span><div><h1>告警与事件</h1><p>实时跟踪任务失败、视频逾期与调用异常，及时处理以保障业务稳定运行。</p></div></div>
      <div><button className="primary-button" type="button" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "is-spinning" : ""} size={16} aria-hidden="true" />重新检测</button><button className="secondary-button" type="button" onClick={() => setStatus("open")}><ClipboardCheck size={16} aria-hidden="true" />批量处理</button><button className="secondary-button" type="button" onClick={exportCsv}><Download size={16} aria-hidden="true" />导出</button></div>
    </header>

    <div className="developer-alerts-layout">
      <main>
        <section className="developer-alert-summary" aria-label="告警概览">
          <article className="red"><span><BellRing size={21} aria-hidden="true" /></span><div><small>待处理事件</small><strong>{counts.open}</strong><p>需要尽快处理</p></div></article>
          <article className="orange"><span><AlertTriangle size={21} aria-hidden="true" /></span><div><small>紧急告警</small><strong>{counts.urgent}</strong><p>优先级最高</p></div></article>
          <article className="blue"><span><ClipboardCheck size={21} aria-hidden="true" /></span><div><small>今日新增</small><strong>{counts.today}</strong><p>按首次发现统计</p></div></article>
          <article className="green"><span><CheckCircle2 size={21} aria-hidden="true" /></span><div><small>已关闭</small><strong>{counts.resolved}</strong><p>已形成处理记录</p></div></article>
        </section>

        <section className="developer-alert-filters" aria-label="告警筛选">
          <label className="developer-alert-search"><Search size={16} aria-hidden="true" /><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索事件标题或来源" /></label>
          <label><span>处理状态</span><select value={status} onChange={(event) => setStatus(event.target.value as AlertStatusFilter)}><option value="">全部</option><option value="open">待处理</option><option value="acknowledged">处理中</option><option value="resolved">已解决</option></select><ChevronDown size={14} aria-hidden="true" /></label>
          <label><span>严重程度</span><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="">全部</option><option value="page">紧急</option><option value="ticket">工单</option></select><ChevronDown size={14} aria-hidden="true" /></label>
          <label><span>业务线</span><select value={source} onChange={(event) => setSource(event.target.value)}><option value="">全部</option>{sourceOptions.map((item) => <option value={item} key={item}>{item}</option>)}</select><ChevronDown size={14} aria-hidden="true" /></label>
          <button type="button" onClick={() => { setKeyword(""); setStatus(""); setSeverity(""); setSource(""); }}>重置筛选</button>
        </section>

        {message ? <div className={`form-message${message.includes("已更新") ? " success" : ""}`} role="status">{message}</div> : null}
        {selected ? <section className="developer-action-panel"><div><strong>{action === "acknowledge" ? "确认告警" : "解决告警"}：{selected.title}</strong><span>处理说明会写入审计日志。</span></div><label>处理说明<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} /></label><div><button className="secondary-button compact" type="button" onClick={() => setSelected(null)}>返回</button><button className="primary-button compact" type="button" onClick={() => void submit()} disabled={loading}>确认提交</button></div></section> : null}

        <section className="developer-alert-table-panel">
          <div className="developer-alert-tabs">
            {([
              ["", "全部", counts.all],
              ["open", "待处理", counts.open],
              ["acknowledged", "处理中", counts.acknowledged],
              ["resolved", "已关闭", counts.resolved]
            ] as Array<[AlertStatusFilter, string, number]>).map(([value, label, count]) => <button type="button" className={status === value ? "active" : ""} key={label} onClick={() => setStatus(value)}>{label} <span>{count}</span></button>)}
          </div>
          <div className="developer-alert-table-scroll">
            <table className="developer-ops-table developer-alert-table" aria-label="告警事件列表">
              <thead><tr><th>事件信息</th><th>来源</th><th>最近发生</th><th>负责人</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>{filteredItems.map((alert) => <tr key={alert.id}>
                <td><div className="developer-alert-title"><i className={alert.severity} /><span><b className={alert.severity}>{severityLabels[alert.severity]}</b><strong>{alert.title}</strong><small>{alert.summary || "未提供错误摘要"}</small></span></div></td>
                <td><span className="developer-table-stack"><span>{alert.source_type}</span><small>#{alert.source_id}</small></span></td>
                <td>{formatTime(alert.last_seen_at)}</td>
                <td>{alert.assigned_user_name || "待认领"}</td>
                <td><span className={`developer-status-pill ${alert.status}`}>{statusLabels[alert.status]}</span></td>
                <td><div className="table-actions">{alert.status === "open" ? <button className="primary-button compact" type="button" onClick={() => openAction(alert, "acknowledge")}>确认并认领</button> : null}{alert.status !== "resolved" ? <button className="table-action compact" type="button" onClick={() => openAction(alert, "resolve")}>标记已解决</button> : null}<button className="table-action compact" type="button" onClick={() => setDetailAlert(alert)}>查看详情</button></div></td>
              </tr>)}</tbody>
            </table>
            {!loading && !filteredItems.length ? <div className="developer-ops-empty">当前没有符合条件的告警</div> : null}
          </div>
          <footer><span>共 {filteredItems.length} 条</span><span>数据来自实时告警中心</span></footer>
        </section>
      </main>

      <aside className="developer-alert-insights">
        <section><header><h2>事件分布</h2><span>总数 {counts.all}</span></header><div className="developer-alert-distribution">
          {distribution.length ? <div><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={distribution} dataKey="value" nameKey="name" innerRadius={48} outerRadius={70} paddingAngle={2}>{distribution.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer><strong>{counts.all}<small>总数</small></strong></div> : <div className="developer-command-empty compact"><CheckCircle2 size={22} aria-hidden="true" /><span>暂无事件</span></div>}
          <ul>{distribution.map((item) => <li key={item.name}><i style={{ background: item.color }} /><span>{item.name}</span><strong>{item.value}</strong></li>)}</ul>
        </div></section>
        <section><header><h2>处理建议</h2></header><ul className="developer-alert-advice"><li><CheckCircle2 size={15} aria-hidden="true" />优先处理紧急告警，避免影响扩大</li><li><CheckCircle2 size={15} aria-hidden="true" />核对任务状态与日志，定位根因</li><li><CheckCircle2 size={15} aria-hidden="true" />处理完成后及时标记并关闭事件</li><li><CheckCircle2 size={15} aria-hidden="true" />定期复盘，优化预警策略</li></ul></section>
        <section><header><h2>最近处理记录</h2></header><ul className="developer-alert-history">{items.filter((item) => item.status !== "open").slice(0, 4).map((item) => <li key={item.id}><i className={item.status} /><span><strong>{item.title}</strong><small>{statusLabels[item.status]} · {formatTime(item.last_seen_at)}</small></span></li>)}{!items.some((item) => item.status !== "open") ? <li className="empty">暂无处理记录</li> : null}</ul></section>
      </aside>
    </div>

    {detailAlert ? <div className="developer-alert-drawer" role="dialog" aria-modal="true" aria-labelledby="developer-alert-detail-title"><button className="developer-alert-drawer-backdrop" type="button" aria-label="关闭详情" onClick={() => setDetailAlert(null)} /><section><header><div><span className={`developer-severity ${detailAlert.severity}`}>{severityLabels[detailAlert.severity]}</span><h2 id="developer-alert-detail-title">{detailAlert.title}</h2></div><button type="button" aria-label="关闭详情" onClick={() => setDetailAlert(null)}><X size={18} aria-hidden="true" /></button></header><p>{detailAlert.summary || "未提供错误摘要"}</p><dl><div><dt>事件来源</dt><dd>{detailAlert.source_type} #{detailAlert.source_id}</dd></div><div><dt>租户</dt><dd>{detailAlert.tenant_id}</dd></div><div><dt>首次发现</dt><dd>{formatTime(detailAlert.detected_at)}</dd></div><div><dt>最近发生</dt><dd>{formatTime(detailAlert.last_seen_at)}</dd></div><div><dt>负责人</dt><dd>{detailAlert.assigned_user_name || "待认领"}</dd></div><div><dt>当前状态</dt><dd>{statusLabels[detailAlert.status]}</dd></div></dl></section></div> : null}
  </section>;
}
