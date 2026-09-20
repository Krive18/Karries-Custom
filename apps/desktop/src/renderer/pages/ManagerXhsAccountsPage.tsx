import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RefreshCw,
  Search,
  ShieldAlert,
  Smartphone
} from "lucide-react";

import { managerApi } from "../api/managerClient";
import type { AdminEmployeeView, AdminXHSAccount } from "../types";


function getStatusMeta(status: number) {
  const metaByStatus: Record<number, { text: string; className: string }> = {
    1: { text: "正常", className: "healthy" },
    2: { text: "登录过期", className: "expired" },
    3: { text: "已暂停", className: "paused" },
    4: { text: "风险提醒", className: "risk" }
  };
  return metaByStatus[status] ?? { text: "未知", className: "unknown" };
}

function formatTime(timestamp: number) {
  if (!timestamp) return "暂无记录";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


export function ManagerXhsAccountsPage() {
  const [accounts, setAccounts] = useState<AdminXHSAccount[]>([]);
  const [employees, setEmployees] = useState<AdminEmployeeView[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [status, setStatus] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const loadAccounts = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({ page_size: "100" });
      if (employeeId) params.set("employee_id", employeeId);
      if (status) params.set("status", status);
      if (keyword) params.set("keyword", keyword);
      const result = await managerApi.listManagedXHSAccounts(params);
      setAccounts(result.items);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号监控数据加载失败");
    } finally {
      setIsLoading(false);
    }
  }, [employeeId, keyword, status]);

  useEffect(() => {
    void managerApi.listEmployees(new URLSearchParams({ page_size: "100", status: "1" }))
      .then((result) => setEmployees(result.items))
      .catch(() => setEmployees([]));
  }, []);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setKeyword(keywordInput.trim());
  };

  const normalCount = accounts.filter((item) => item.status === 1).length;
  const problemCount = accounts.filter((item) => item.status === 2 || item.status === 4).length;

  return (
    <section className="manager-operations-page">
      <header className="manager-page-header">
        <div><h1>小红书账号监控</h1><p>统一查看员工矩阵账号的登录态、风险和发布负载</p></div>
        <button className="secondary-button" type="button" onClick={() => void loadAccounts()}>
          <RefreshCw size={16} className={isLoading ? "spin" : ""} />刷新状态
        </button>
      </header>

      <div className="account-monitor-summary">
        <span><Smartphone size={18} /><strong>{accounts.length}</strong> 当前账号</span>
        <span><CheckCircle2 size={18} /><strong>{normalCount}</strong> 状态正常</span>
        <span className={problemCount ? "warning" : ""}><ShieldAlert size={18} /><strong>{problemCount}</strong> 需要处理</span>
      </div>

      <form className="manager-operation-filters" onSubmit={submitSearch}>
        <label>所属员工
          <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}>
            <option value="">全部员工</option>
            {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.nickname}</option>)}
          </select>
        </label>
        <label>账号状态
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">全部状态</option>
            <option value="1">正常</option><option value="2">登录过期</option>
            <option value="3">已暂停</option><option value="4">风险提醒</option>
          </select>
        </label>
        <label className="operation-keyword">搜索账号
          <span><Search size={16} /><input value={keywordInput} onChange={(event) => setKeywordInput(event.target.value)} placeholder="账号名称、分组或员工" /></span>
        </label>
        <button className="primary-button" type="submit">查询</button>
      </form>

      {message ? <div className="form-message">{message}</div> : null}

      <div className="panel operation-table-panel">
        <table className="operation-table">
          <thead><tr><th>账号</th><th>所属员工</th><th>登录状态</th><th>今日发布</th><th>发布队列</th><th>最近发布</th></tr></thead>
          <tbody>
            {accounts.map((account) => {
              const meta = getStatusMeta(account.status);
              return (
                <tr key={account.id}>
                  <td><strong>{account.display_name}</strong><small>{account.account_group || "未分组"}</small></td>
                  <td><strong>{account.employee_name}</strong><small>{account.employee_login}</small></td>
                  <td>
                    <span className={`operation-status ${meta.className}`}>{meta.text}</span>
                    <small>{account.login_state_ready ? "登录凭证已保存" : "尚未保存登录凭证"}</small>
                  </td>
                  <td><strong>{account.today_publish_count} / {account.daily_limit}</strong><small>间隔 {account.min_interval_minutes} 分钟</small></td>
                  <td>
                    <span className="queue-counts"><b>{account.pending_count}</b>待处理 <b>{account.failed_count}</b>异常</span>
                    <small>累计已提交 {account.submitted_count}</small>
                  </td>
                  <td><Clock3 size={15} /> {formatTime(account.last_publish_time)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!isLoading && !accounts.length ? (
          <div className="operation-empty"><AlertTriangle size={23} /><strong>没有符合条件的账号</strong></div>
        ) : null}
      </div>
    </section>
  );
}
