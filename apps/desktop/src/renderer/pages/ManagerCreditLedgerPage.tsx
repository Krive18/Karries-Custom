import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  Download,
  Filter,
  RefreshCw,
  WalletCards
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { managerApi } from "../api/managerClient";
import { ManagerEmployeeSelect } from "../components/ManagerEmployeeSelect";
import type {
  AdminBillingOverview,
  AdminCreditLedgerResult
} from "../types";


const emptyLedger: AdminCreditLedgerResult = {
  items: [],
  page: 1,
  page_size: 20,
  total: 0,
  summary: { income: 0, expense: 0 }
};

function formatCredits(value: number) {
  return value.toLocaleString("zh-CN");
}

function formatDate(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}

function businessLabel(type: string) {
  const labels: Record<string, string> = {
    recharge: "充值到账",
    daily_checkin: "每日签到",
    membership_monthly: "会员月度发放",
    inspiration: "AI 灵感对话",
    viral_analysis: "爆款解析",
    ai_copy: "AI 内容生成",
    refund: "算力退回"
  };
  return labels[type] ?? type;
}


export function ManagerCreditLedgerPage() {
  const [overview, setOverview] = useState<AdminBillingOverview | null>(null);
  const [ledger, setLedger] = useState(emptyLedger);
  const [employeeId, setEmployeeId] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [direction, setDirection] = useState("");
  const [keyword, setKeyword] = useState("");
  const [appliedKeyword, setAppliedKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({
      page: String(page),
      page_size: "20"
    });
    if (employeeId) params.set("employee_id", employeeId);
    if (businessType) params.set("business_type", businessType);
    if (direction) params.set("direction", direction);
    if (appliedKeyword) params.set("keyword", appliedKeyword);
    try {
      const [nextOverview, nextLedger] = await Promise.all([
        managerApi.getBillingOverview(30),
        managerApi.listAdminCreditLedger(params)
      ]);
      setOverview(nextOverview);
      setLedger(nextLedger);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "算力流水加载失败");
    } finally {
      setLoading(false);
    }
  }, [appliedKeyword, businessType, direction, employeeId, page]);

  useEffect(() => {
    void load();
  }, [load]);

  function exportCsv() {
    const rows = [
      ["流水时间", "员工", "业务类型", "变动前", "变动数量", "变动后", "说明"],
      ...ledger.items.map((item) => [
        formatDate(item.create_time),
        `${item.employee_name}(${item.employee_login})`,
        businessLabel(item.business_type),
        String(item.before_balance),
        String(item.change_amount),
        String(item.after_balance),
        item.reason
      ])
    ];
    const csv = `\uFEFF${rows.map((row) => row.map((cell) => `"${cell.replaceAll("\"", "\"\"")}"`).join(",")).join("\n")}`;
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `算力流水-${Date.now()}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="manager-ledger-page">
      <header className="manager-page-header">
        <div>
          <h1>算力流水</h1>
          <p>追踪每位员工的充值、赠送和 AI 功能消耗</p>
        </div>
        <div className="manager-header-actions">
          <button className="secondary-button" type="button" onClick={exportCsv}>
            <Download size={16} />导出当前结果
          </button>
          <button className="secondary-button" type="button" onClick={() => void load()}>
            <RefreshCw size={16} className={loading ? "spin" : ""} />刷新
          </button>
        </div>
      </header>

      {error ? <div className="form-message error" role="alert">{error}</div> : null}

      <div className="manager-ledger-kpis">
        <article>
          <WalletCards size={20} />
          <span>团队当前余额</span>
          <strong>{formatCredits(overview?.wallet.balance ?? 0)}</strong>
        </article>
        <article className="income">
          <ArrowUpCircle size={20} />
          <span>筛选范围增加</span>
          <strong>+{formatCredits(ledger.summary.income)}</strong>
        </article>
        <article className="expense">
          <ArrowDownCircle size={20} />
          <span>筛选范围消耗</span>
          <strong>-{formatCredits(ledger.summary.expense)}</strong>
        </article>
        <article>
          <span>流水记录</span>
          <strong>{ledger.total}</strong>
          <small>满足当前筛选条件</small>
        </article>
      </div>

      <section className="manager-ledger-chart">
        <div className="manager-section-heading">
          <div><h2>近 30 天算力变化</h2><p>充值与消耗按日汇总</p></div>
          <div className="manager-chart-legend">
            <span><i className="income" />增加</span>
            <span><i className="expense" />消耗</span>
          </div>
        </div>
        <div>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={overview?.credit_trend ?? []} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="#eee5da" vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip />
              <Area type="monotone" dataKey="income" name="增加" stroke="#4c8b63" fill="#dcecdf" fillOpacity={0.75} />
              <Area type="monotone" dataKey="expense" name="消耗" stroke="#b17a3a" fill="#f2dfc5" fillOpacity={0.62} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="manager-ledger-table-section">
        <form
          className="manager-ledger-filters"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedKeyword(keyword.trim());
          }}
        >
          <Filter size={18} aria-hidden="true" />
          <ManagerEmployeeSelect value={employeeId} onChange={(value) => { setEmployeeId(value); setPage(1); }} />
          <label>
            业务类型
            <select value={businessType} onChange={(event) => { setBusinessType(event.target.value); setPage(1); }}>
              <option value="">全部业务</option>
              <option value="recharge">充值到账</option>
              <option value="membership_monthly">会员月度发放</option>
              <option value="daily_checkin">每日签到</option>
              <option value="inspiration">AI 灵感对话</option>
              <option value="viral_analysis">爆款解析</option>
              <option value="ai_copy">AI 内容生成</option>
            </select>
          </label>
          <label>
            变动方向
            <select value={direction} onChange={(event) => { setDirection(event.target.value); setPage(1); }}>
              <option value="">全部方向</option>
              <option value="income">增加</option>
              <option value="expense">消耗</option>
            </select>
          </label>
          <label className="manager-ledger-keyword">
            关键词
            <input value={keyword} placeholder="员工、账号或说明" onChange={(event) => setKeyword(event.target.value)} />
          </label>
          <button className="primary-button" type="submit">应用筛选</button>
        </form>

        <div className="manager-ledger-table-wrap">
          <table className="manager-data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>员工</th>
                <th>业务类型</th>
                <th>变动前</th>
                <th>变动</th>
                <th>变动后</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {ledger.items.map((item) => (
                <tr key={item.id}>
                  <td>{formatDate(item.create_time)}</td>
                  <td><strong>{item.employee_name}</strong><small>{item.employee_login}</small></td>
                  <td>{businessLabel(item.business_type)}</td>
                  <td>{formatCredits(item.before_balance)}</td>
                  <td className={item.change_amount >= 0 ? "credit-positive" : "credit-negative"}>
                    {item.change_amount >= 0 ? "+" : ""}{formatCredits(item.change_amount)}
                  </td>
                  <td><strong>{formatCredits(item.after_balance)}</strong></td>
                  <td>{item.reason || "-"}</td>
                </tr>
              ))}
              {!ledger.items.length ? (
                <tr><td className="manager-table-empty" colSpan={7}>暂无符合条件的算力流水</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <footer className="manager-table-pagination">
          <span>第 {ledger.page} 页，共 {ledger.total} 条</span>
          <div>
            <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button>
            <button type="button" disabled={page * ledger.page_size >= ledger.total} onClick={() => setPage((value) => value + 1)}>下一页</button>
          </div>
        </footer>
      </section>
    </section>
  );
}
