import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BadgeCheck,
  Check,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
  UsersRound,
  X
} from "lucide-react";

import { developerApi } from "../api/developerClient";
import type {
  DeveloperCustomerAccount,
  UserCreationRequest
} from "../types";


const formatCredits = (value: number) =>
  new Intl.NumberFormat("zh-CN").format(value);

const formatTime = (value: number) => value
  ? new Intl.DateTimeFormat("zh-CN", {
      dateStyle: "short",
      timeStyle: "short"
    }).format(new Date(value * 1000))
  : "从未登录";


export function DeveloperUsersPage() {
  const [accounts, setAccounts] = useState<DeveloperCustomerAccount[]>([]);
  const [requests, setRequests] = useState<UserCreationRequest[]>([]);
  const [keyword, setKeyword] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [selectedAccount, setSelectedAccount] = useState<DeveloperCustomerAccount | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<UserCreationRequest | null>(null);
  const [reviewAction, setReviewAction] = useState<"approve" | "reject">("approve");
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setMessage("");
    try {
      const params = new URLSearchParams({ page: "1", page_size: "100" });
      if (keyword.trim()) params.set("keyword", keyword.trim());
      if (role) params.set("role", role);
      const [accountResult, requestResult] = await Promise.all([
        developerApi.listCustomerAccounts(params),
        developerApi.listUserCreationRequests("pending")
      ]);
      setAccounts(accountResult.items);
      setRequests(requestResult);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "客户账号数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [keyword, role]);

  useEffect(() => {
    void load();
  }, [load]);

  const metrics = useMemo(() => ({
    owners: accounts.filter((item) => item.user_role === "client_owner").length,
    users: accounts.filter((item) => item.user_role === "customer").length,
    balance: accounts.reduce((total, item) => total + item.balance, 0)
  }), [accounts]);

  const submitAccountStatus = async () => {
    if (!selectedAccount || reason.trim().length < 3) {
      setMessage("请填写至少 3 个字的操作原因");
      return;
    }
    try {
      await developerApi.updateCustomerAccountStatus(
        selectedAccount.id,
        selectedAccount.status === 1 ? 2 : 1,
        reason.trim()
      );
      setSelectedAccount(null);
      setReason("");
      await load();
      setMessage("客户账号状态已更新，原会话已失效。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号状态更新失败");
    }
  };

  const submitReview = async () => {
    if (!selectedRequest || reason.trim().length < 3) {
      setMessage("请填写至少 3 个字的审核说明");
      return;
    }
    try {
      await developerApi.reviewUserCreationRequest(
        selectedRequest.id,
        reviewAction,
        reason.trim()
      );
      setSelectedRequest(null);
      setReason("");
      await load();
      setMessage(reviewAction === "approve" ? "新增用户申请已通过。" : "新增用户申请已拒绝。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "审核操作失败");
    }
  };

  return (
    <section className="developer-page developer-users-page">
      <header className="developer-page-header">
        <div>
          <h1>管理员与用户管理</h1>
          <p>统一查看客户管理员、员工账号和算力余额，并审核超过 2 人额度的新增申请。</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void load()}>
          <RefreshCw size={17} aria-hidden="true" />
          刷新
        </button>
      </header>

      {message ? <div className="form-message" role="status">{message}</div> : null}

      <div className="developer-user-metrics">
        <article><ShieldCheck size={21} /><span>客户管理员</span><strong>{metrics.owners}</strong></article>
        <article><UsersRound size={21} /><span>用户账号</span><strong>{metrics.users}</strong></article>
        <article><BadgeCheck size={21} /><span>待审核新增</span><strong>{requests.length}</strong></article>
        <article><UserRound size={21} /><span>用户算力合计</span><strong>{formatCredits(metrics.balance)}</strong></article>
      </div>

      {selectedAccount || selectedRequest ? (
        <section className="developer-action-panel developer-user-action-panel">
          <div>
            <strong>
              {selectedRequest
                ? `${reviewAction === "approve" ? "通过" : "拒绝"}新增申请：${selectedRequest.nickname}`
                : `${selectedAccount?.status === 1 ? "停用" : "启用"}账号：${selectedAccount?.nickname}`}
            </strong>
            <span>所有操作都会记录到审计日志。</span>
          </div>
          <label>
            操作原因
            <textarea value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} />
          </label>
          <div>
            <button className="secondary-button compact" type="button" onClick={() => {
              setSelectedAccount(null);
              setSelectedRequest(null);
              setReason("");
            }}>取消</button>
            <button className="primary-button compact" type="button" onClick={() => void (selectedRequest ? submitReview() : submitAccountStatus())}>
              确认操作
            </button>
          </div>
        </section>
      ) : null}

      {requests.length ? (
        <section className="developer-panel developer-review-panel">
          <div className="developer-panel-heading"><div><span>01</span><h2>待审核新增用户</h2></div><small>{requests.length} 条</small></div>
          <div className="developer-review-list">
            {requests.map((item) => (
              <article key={item.id}>
                <div><strong>{item.nickname}</strong><span>{item.login_name} · {item.tenant_name || `租户 ${item.tenant_id}`}</span></div>
                <small>{item.requester_name} 申请 · {formatTime(item.create_time)}</small>
                <div>
                  <button className="secondary-button compact" type="button" onClick={() => { setSelectedRequest(item); setReviewAction("reject"); setReason(""); }}><X size={15} />拒绝</button>
                  <button className="primary-button compact" type="button" onClick={() => { setSelectedRequest(item); setReviewAction("approve"); setReason(""); }}><Check size={15} />通过</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="developer-panel developer-user-table-panel">
        <div className="developer-panel-heading"><div><span>02</span><h2>客户账号</h2></div><small>{accounts.length} 个</small></div>
        <form className="developer-user-filters" onSubmit={(event) => { event.preventDefault(); void load(); }}>
          <label><span>账号角色</span><select value={role} onChange={(event) => setRole(event.target.value)}><option value="">全部角色</option><option value="client_owner">客户管理员</option><option value="customer">用户</option></select></label>
          <label><span>搜索</span><div className="developer-search-field"><Search size={16} /><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="团队、姓名或账号" /></div></label>
          <button className="secondary-button" type="submit"><Search size={16} />查询</button>
        </form>
        <div className="developer-ops-table-wrap">
          <table className="developer-ops-table">
            <thead><tr><th>账号</th><th>团队</th><th>角色</th><th>会员</th><th>算力</th><th>状态</th><th>最近登录</th><th>操作</th></tr></thead>
            <tbody>
              {accounts.map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.nickname || item.login_name}</strong><small>{item.login_name}</small></td>
                  <td>{item.tenant_name || `租户 ${item.tenant_id}`}</td>
                  <td>{item.user_role === "client_owner" ? "客户管理员" : "用户"}</td>
                  <td>{item.membership_plan_name || "未激活"}</td>
                  <td>{formatCredits(item.balance)}</td>
                  <td><span className={`developer-status-pill ${item.status === 1 ? "completed" : "cancelled"}`}>{item.status === 1 ? "启用" : "停用"}</span></td>
                  <td>{formatTime(item.last_login_time)}</td>
                  <td><button className="table-action compact" type="button" onClick={() => { setSelectedAccount(item); setSelectedRequest(null); setReason(""); }}>{item.status === 1 ? "停用" : "启用"}</button></td>
                </tr>
              ))}
              {!loading && !accounts.length ? <tr><td colSpan={8} className="developer-ops-empty">暂无客户账号</td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
