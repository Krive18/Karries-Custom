import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  RefreshCw,
  Smartphone,
  UsersRound
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { managerApi } from "../api/managerClient";
import type { OperationsOverview } from "../types";


const chartColors = ["#9a5d1d", "#4c8b63", "#d2993d", "#c34d43", "#846650", "#6b7280", "#b5a48f"];

const emptyOverview: OperationsOverview = {
  summary: {
    total_employees: 0,
    active_employees: 0,
    total_accounts: 0,
    normal_accounts: 0,
    expired_accounts: 0,
    risk_accounts: 0,
    today_scheduled: 0,
    today_submitted: 0,
    today_failed: 0,
    pending_items: 0,
    success_rate: 0,
    team_credit_balance: 0
  },
  publish_trend: [],
  status_distribution: [],
  employee_ranking: [],
  alerts: []
};


export function ManagerOverviewPage() {
  const [overview, setOverview] = useState(emptyOverview);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");

  const loadOverview = useCallback(async () => {
    setIsLoading(true);
    try {
      setOverview(await managerApi.getOperationsOverview(7));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "运营数据加载失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const { summary } = overview;

  return (
    <section className="manager-operations-page">
      <header className="manager-page-header">
        <div>
          <h1>运营总览</h1>
          <p>账号健康、发布进度和团队产能集中查看</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void loadOverview()}>
          <RefreshCw size={16} className={isLoading ? "spin" : ""} />
          刷新数据
        </button>
      </header>

      {message ? <div className="form-message">{message}</div> : null}

      <div className="operations-kpi-grid">
        <article className="operations-kpi">
          <UsersRound size={21} />
          <div><span>在岗员工</span><strong>{summary.active_employees}</strong></div>
          <small>共 {summary.total_employees} 名员工</small>
        </article>
        <article className="operations-kpi">
          <Smartphone size={21} />
          <div><span>正常账号</span><strong>{summary.normal_accounts}</strong></div>
          <small>共 {summary.total_accounts} 个账号</small>
        </article>
        <article className="operations-kpi">
          <Clock3 size={21} />
          <div><span>待发布内容</span><strong>{summary.pending_items}</strong></div>
          <small>今日排期 {summary.today_scheduled} 条</small>
        </article>
        <article className="operations-kpi">
          <CheckCircle2 size={21} />
          <div><span>发布成功率</span><strong>{summary.success_rate}%</strong></div>
          <small>今日已提交 {summary.today_submitted} 条</small>
        </article>
        <article className="operations-kpi">
          <CircleDollarSign size={21} />
          <div><span>团队剩余算力</span><strong>{summary.team_credit_balance.toLocaleString()}</strong></div>
          <small>员工账户余额合计</small>
        </article>
      </div>

      <div className="operations-chart-grid">
        <article className="panel operations-chart operations-trend-chart">
          <header>
            <div><span>近 7 天</span><h2>发布趋势</h2></div>
            <div className="chart-legend">
              <span><i className="scheduled" />排期</span>
              <span><i className="submitted" />已提交</span>
              <span><i className="failed" />失败</span>
            </div>
          </header>
          <div className="chart-canvas">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={overview.publish_trend} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="#eee5da" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip />
                <Area type="monotone" dataKey="scheduled" name="排期" stroke="#b17a3a" fill="#ead6bb" fillOpacity={0.45} />
                <Area type="monotone" dataKey="submitted" name="已提交" stroke="#4c8b63" fill="#cfe5d6" fillOpacity={0.55} />
                <Area type="monotone" dataKey="failed" name="失败" stroke="#c34d43" fill="#f1d2cf" fillOpacity={0.42} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel operations-chart">
          <header><div><span>全部任务</span><h2>发布状态分布</h2></div></header>
          <div className="chart-canvas chart-canvas-pie">
            {overview.status_distribution.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={overview.status_distribution}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={62}
                    outerRadius={92}
                    paddingAngle={3}
                  >
                    {overview.status_distribution.map((entry, index) => (
                      <Cell key={entry.status} fill={chartColors[index % chartColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : <div className="chart-empty">暂无发布任务</div>}
          </div>
          <div className="status-mini-legend">
            {overview.status_distribution.map((item, index) => (
              <span key={item.status}><i style={{ background: chartColors[index % chartColors.length] }} />{item.name} {item.value}</span>
            ))}
          </div>
        </article>
      </div>

      <div className="operations-bottom-grid">
        <article className="panel operations-chart">
          <header><div><span>近 7 天</span><h2>员工发布产能</h2></div></header>
          <div className="chart-canvas compact">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={overview.employee_ranking} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid stroke="#eee5da" vertical={false} />
                <XAxis dataKey="nickname" tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="publish_count" name="已提交" fill="#9a5d1d" radius={[4, 4, 0, 0]} />
                <Bar dataKey="failed_count" name="失败" fill="#d98a82" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel operations-alerts">
          <header><AlertTriangle size={19} /><h2>运营提醒</h2></header>
          <div>
            {overview.alerts.map((alert) => (
              <div className={alert.count ? "operations-alert active" : "operations-alert"} key={alert.type}>
                <span>{alert.title}</span>
                <strong>{alert.count}</strong>
              </div>
            ))}
          </div>
          <footer><Activity size={15} /> 数据来自账号登录态与发布执行记录</footer>
        </article>
      </div>
    </section>
  );
}
