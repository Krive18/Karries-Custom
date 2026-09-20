import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BadgeCheck,
  ChevronDown,
  Coins,
  Crown,
  RefreshCw,
  Search,
  Send,
  WalletCards,
  XCircle
} from "lucide-react";

import { developerApi } from "../api/developerClient";
import type {
  DeveloperBillingCustomer,
  DeveloperCreditLedgerItem,
  DeveloperPaymentRecord,
  DeveloperRechargeOrder,
  DeveloperTenantMembership,
  MembershipUpgradeOrder
} from "../types";


const formatTime = (value: number) =>
  value
    ? new Intl.DateTimeFormat("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false
      }).format(new Date(value * 1000))
    : "-";

const formatMoney = (value: number) =>
  new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2
  }).format(value / 100);

const formatCredits = (value: number) =>
  new Intl.NumberFormat("zh-CN").format(value);

const LEDGER_EXPANDED_STORAGE_KEY = "developer-billing-ledger-expanded";

const paymentChannelLabels: Record<string, string> = {
  alipay: "支付宝",
  wechat: "微信支付",
  manual: "人工收款"
};

const membershipStatusLabels: Record<number, string> = {
  1: "生效中",
  2: "已到期",
  3: "已取消"
};


export function DeveloperBillingPage() {
  const [customers, setCustomers] = useState<DeveloperBillingCustomer[]>([]);
  const [orders, setOrders] = useState<DeveloperRechargeOrder[]>([]);
  const [membershipOrders, setMembershipOrders] = useState<MembershipUpgradeOrder[]>([]);
  const [ledger, setLedger] = useState<DeveloperCreditLedgerItem[]>([]);
  const [paymentRecords, setPaymentRecords] = useState<DeveloperPaymentRecord[]>([]);
  const [selectedUserId, setSelectedUserId] = useState(0);
  const [credits, setCredits] = useState("");
  const [reason, setReason] = useState("运营调整算力");
  const [keyword, setKeyword] = useState("");
  const [selectedTenantId, setSelectedTenantId] = useState(0);
  const [tenantMembership, setTenantMembership] =
    useState<DeveloperTenantMembership | null>(null);
  const [membershipPlanId, setMembershipPlanId] = useState(0);
  const [membershipDuration, setMembershipDuration] = useState("1");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [ledgerExpanded, setLedgerExpanded] = useState(() => {
    try {
      return window.localStorage.getItem(LEDGER_EXPANDED_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  const selectedCustomer = useMemo(
    () => customers.find((customer) => customer.id === selectedUserId),
    [customers, selectedUserId]
  );

  const tenantOptions = useMemo(() => {
    const seen = new Map<number, string>();
    customers.forEach((customer) => {
      if (!seen.has(customer.tenant_id)) {
        seen.set(
          customer.tenant_id,
          customer.tenant_name || `租户 ${customer.tenant_id}`
        );
      }
    });
    return Array.from(seen, ([tenant_id, tenant_name]) => ({
      tenant_id,
      tenant_name
    }));
  }, [customers]);

  const loadTenantMembership = useCallback(async (tenantId: number) => {
    if (!tenantId) {
      setTenantMembership(null);
      return;
    }
    try {
      const result = await developerApi.getTenantMembership(tenantId);
      setTenantMembership(result);
      setMembershipPlanId((current) => (
        current || result.membership?.plan_id || result.plans[0]?.id || 0
      ));
    } catch (caught) {
      setTenantMembership(null);
      setError(caught instanceof Error ? caught.message : "租户会员信息加载失败");
    }
  }, []);

  useEffect(() => {
    const fallback = tenantOptions[0]?.tenant_id ?? 0;
    const next = tenantOptions.some((tenant) => tenant.tenant_id === selectedTenantId)
      ? selectedTenantId
      : fallback;
    if (next !== selectedTenantId) {
      setSelectedTenantId(next);
    }
    void loadTenantMembership(next);
  }, [tenantOptions, selectedTenantId, loadTenantMembership]);

  const toggleLedger = () => {
    setLedgerExpanded((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(
          LEDGER_EXPANDED_STORAGE_KEY,
          next ? "1" : "0"
        );
      } catch {
        // The panel remains usable when browser storage is unavailable.
      }
      return next;
    });
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const orderParams = new URLSearchParams({
        page: "1",
        page_size: "50",
        status: "6"
      });
      const ledgerParams = new URLSearchParams({
        page: "1",
        page_size: "50"
      });
      const membershipParams = new URLSearchParams({
        page: "1",
        page_size: "50",
        status: "2"
      });
      const paymentParams = new URLSearchParams({
        page: "1",
        page_size: "50"
      });
      const [
        customerResult,
        orderResult,
        ledgerResult,
        membershipResult,
        paymentResult
      ] = await Promise.all([
        developerApi.listBillingCustomers(keyword),
        developerApi.listRechargeOrders(orderParams),
        developerApi.listCreditLedger(ledgerParams),
        developerApi.listMembershipOrders(membershipParams),
        developerApi.listPaymentRecords(paymentParams)
      ]);
      setCustomers(customerResult);
      setOrders(orderResult.items);
      setLedger(ledgerResult.items);
      setMembershipOrders(membershipResult.items);
      setPaymentRecords(paymentResult.items);
      setSelectedUserId((current) => (
        customerResult.some((customer) => customer.id === current)
          ? current
          : (customerResult[0]?.id ?? 0)
      ));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "算力数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [keyword]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const grantOrder = async (order: DeveloperRechargeOrder) => {
    if (!window.confirm(
      `确认向 ${order.employee_name} 发放 ${formatCredits(order.requested_credits)} 算力？`
    )) return;
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      await developerApi.grantRechargeOrder(order.id);
      setMessage(`订单 ${order.order_no} 已完成算力发放`);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "算力发放失败");
    } finally {
      setSubmitting(false);
    }
  };

  const approveMembershipOrder = async (order: MembershipUpgradeOrder) => {
    if (!window.confirm(
      `确认审核通过 ${order.tenant_name} 的 ${order.plan.plan_name} 申请？通过后将立即同步到团队在用账号。`
    )) return;
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const result = await developerApi.approveMembershipOrder(order.id);
      setMessage(
        `订单 ${order.order_no} 已审核通过，共同步 ${result.affected_user_count} 个账号`
      );
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "会员审核开通失败");
    } finally {
      setSubmitting(false);
    }
  };

  const rejectMembershipOrder = async (order: MembershipUpgradeOrder) => {
    const reason = window.prompt("请输入驳回原因（至少 2 个字）", "收款记录无法核对")?.trim();
    if (!reason) return;
    if (reason.length < 2) {
      setError("驳回原因至少需要 2 个字");
      return;
    }
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      await developerApi.rejectMembershipOrder(order.id, reason);
      setMessage(`订单 ${order.order_no} 已驳回，会员方案未变更`);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "会员申请驳回失败");
    } finally {
      setSubmitting(false);
    }
  };

  const adjustManualCredits = async () => {
    const parsedCredits = Number.parseInt(credits, 10);
    if (!selectedUserId || !Number.isFinite(parsedCredits) || parsedCredits === 0) {
      setError("请选择员工并填写非 0 的整数算力；正数增加，负数扣减");
      return;
    }
    if (!reason.trim()) {
      setError("请填写本次发放原因");
      return;
    }
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      await developerApi.adjustCredits({
        user_id: selectedUserId,
        change_amount: parsedCredits,
        reason: reason.trim()
      });
      setCredits("");
      setMessage(
        `已为 ${selectedCustomer?.nickname || "所选员工"} 调整 ${parsedCredits > 0 ? "+" : ""}${formatCredits(parsedCredits)} 算力`
      );
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人工调整失败");
    } finally {
      setSubmitting(false);
    }
  };

  const adjustTenantMembership = async () => {
    const duration = Number.parseInt(membershipDuration, 10);
    if (!selectedTenantId || !membershipPlanId) {
      setError("请选择租户与会员方案");
      return;
    }
    if (!Number.isFinite(duration) || duration < 0 || duration > 36) {
      setError("请输入 0-36 的月数，0 表示长期有效");
      return;
    }
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const result = await developerApi.adjustTenantMembership(selectedTenantId, {
        plan_id: membershipPlanId,
        duration_months: duration
      });
      setTenantMembership(result);
      setMessage(
        `租户会员已调整为 ${result.membership?.plan.plan_name ?? "所选方案"}，共同步 ${result.affected_user_count} 个账号`
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "租户会员调整失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="developer-page developer-billing-page">
      <header className="developer-page-header">
        <div>
          <h1>资金与会员审核中心</h1>
          <p>审核团队会员付款申请，处理算力充值，并查看付款与算力变动记录。</p>
        </div>
        <button
          className="secondary-button"
          type="button"
          disabled={loading}
          onClick={() => void loadData()}
        >
          <RefreshCw size={17} aria-hidden="true" />
          刷新
        </button>
      </header>

      {error ? <div className="inline-alert error">{error}</div> : null}
      {message ? <div className="inline-alert success">{message}</div> : null}

      <div className="developer-billing-metrics">
        <article>
          <WalletCards size={22} aria-hidden="true" />
          <span>待发放订单</span>
          <strong>{orders.length}</strong>
        </article>
        <article>
          <Coins size={22} aria-hidden="true" />
          <span>待发放算力</span>
          <strong>
            {formatCredits(
              orders.reduce((total, order) => total + order.requested_credits, 0)
            )}
          </strong>
        </article>
        <article>
          <Crown size={22} aria-hidden="true" />
          <span>待审核会员</span>
          <strong>{membershipOrders.length}</strong>
        </article>
        <article>
          <BadgeCheck size={22} aria-hidden="true" />
          <span>可服务员工</span>
          <strong>{customers.length}</strong>
        </article>
      </div>

      <section className="developer-panel developer-membership-review-panel">
        <div className="developer-panel-heading">
          <div>
            <span>01</span>
            <h2>会员付款审核</h2>
          </div>
          <small>{membershipOrders.length} 笔</small>
        </div>
        <div className="developer-order-list">
          {loading ? (
            <div className="developer-empty-state">正在加载会员申请...</div>
          ) : membershipOrders.length === 0 ? (
            <div className="developer-empty-state">暂无待审核会员申请</div>
          ) : membershipOrders.map((order) => (
            <article className="developer-order-item membership-order-item" key={order.id}>
              <div className="developer-order-main">
                <div>
                  <strong>{order.plan.plan_name}</strong>
                  <span>{order.tenant_name} · {order.applicant_name}</span>
                </div>
                <div className="developer-order-amount">
                  <strong>{formatMoney(order.amount_cent)}</strong>
                  <span>{order.duration_months} 个月</span>
                </div>
              </div>
              <div className="developer-order-meta">
                <span>{order.order_no}</span>
                <span>付款确认 {formatTime(order.paid_time)}</span>
                <span>{order.payment_channel === "wechat" ? "微信支付" : "支付宝"}</span>
              </div>
              <div className="developer-membership-actions">
                <button
                  className="secondary-button danger"
                  type="button"
                  disabled={submitting}
                  onClick={() => void rejectMembershipOrder(order)}
                >
                  <XCircle size={16} aria-hidden="true" />
                  驳回
                </button>
                <button
                  className="primary-button"
                  type="button"
                  disabled={submitting}
                  onClick={() => void approveMembershipOrder(order)}
                >
                  <Crown size={16} aria-hidden="true" />
                  审核开通
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className="developer-billing-grid">
        <section className="developer-panel">
          <div className="developer-panel-heading">
            <div>
              <span>02</span>
              <h2>已付款待发放</h2>
            </div>
            <small>{orders.length} 笔</small>
          </div>
          <div className="developer-order-list">
            {loading ? (
              <div className="developer-empty-state">正在加载订单...</div>
            ) : orders.length === 0 ? (
              <div className="developer-empty-state">
                暂无已付款待发放订单
              </div>
            ) : orders.map((order) => (
              <article className="developer-order-item" key={order.id}>
                <div className="developer-order-main">
                  <div>
                    <strong>{order.employee_name}</strong>
                    <span>{order.tenant_name} · {order.employee_login}</span>
                  </div>
                  <div className="developer-order-amount">
                    <strong>{formatMoney(order.amount_cent)}</strong>
                    <span>{formatCredits(order.requested_credits)} 算力</span>
                  </div>
                </div>
                <div className="developer-order-meta">
                  <span>{order.order_no}</span>
                  <span>付款确认 {formatTime(order.paid_time)}</span>
                  {order.proof_file_name ? <span>已上传付款凭证</span> : null}
                </div>
                <button
                  className="primary-button"
                  type="button"
                  disabled={submitting}
                  onClick={() => void grantOrder(order)}
                >
                  <Send size={16} aria-hidden="true" />
                  发放算力
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="developer-panel developer-manual-grant">
          <div className="developer-panel-heading">
            <div>
              <span>03</span>
              <h2>人工调整</h2>
            </div>
          </div>
          <label>
            <span>搜索员工</span>
            <div className="developer-search-field">
              <Search size={17} aria-hidden="true" />
              <input
                value={keyword}
                placeholder="员工姓名、账号或团队"
                onChange={(event) => setKeyword(event.target.value)}
              />
            </div>
          </label>
          <label>
            <span>调整用户</span>
            <select
              value={selectedUserId || ""}
              onChange={(event) => setSelectedUserId(Number(event.target.value))}
            >
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.tenant_name} / {customer.nickname}（余额 {formatCredits(customer.balance)}）
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>调整算力</span>
            <input
              inputMode="numeric"
              type="number"
              value={credits}
              placeholder="正数增加，负数扣减"
              onChange={(event) => setCredits(event.target.value)}
            />
          </label>
          <label>
            <span>调整原因</span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={submitting || customers.length === 0}
            onClick={() => void adjustManualCredits()}
          >
            <Coins size={17} aria-hidden="true" />
            确认调整
          </button>
        </section>
      </div>

      <section className="developer-panel developer-ledger-panel">
        <div className="developer-panel-heading">
          <div>
            <span>04</span>
            <h2>付款记录</h2>
          </div>
          <small>最近 {paymentRecords.length} 条</small>
        </div>
        <div className="developer-ledger-scroll">
          <div className="developer-ledger-table">
            <div className="developer-ledger-row header">
              <span>类型 / 订单</span>
              <span>团队 / 客户</span>
              <span>金额</span>
              <span>状态</span>
              <span>内容</span>
              <span>付款时间</span>
            </div>
            {paymentRecords.map((record) => (
              <div className="developer-ledger-row" key={record.record_key}>
                <span>
                  {record.record_type_text}
                  <small>{record.order_no}</small>
                </span>
                <span>
                  {record.tenant_name || "-"}
                  <small>{record.customer_name} · {record.customer_login}</small>
                </span>
                <strong>{formatMoney(record.amount_cent)}</strong>
                <span>{record.status_text}</span>
                <span>
                  {record.description}
                  <small>
                    {paymentChannelLabels[record.payment_channel] || record.payment_channel || "-"}
                    {record.credits > 0 ? ` · ${formatCredits(record.credits)} 算力` : ""}
                  </small>
                </span>
                <span>{formatTime(record.paid_time || record.update_time)}</span>
              </div>
            ))}
            {!loading && paymentRecords.length === 0 ? (
              <div className="developer-empty-state">暂无付款记录</div>
            ) : null}
          </div>
        </div>
      </section>

      <section className="developer-panel developer-ledger-panel">
        <div className="developer-panel-heading">
          <div>
            <span>05</span>
            <h2>算力明细</h2>
          </div>
          <div className="developer-ledger-heading-actions">
            <small>最近 {ledger.length} 条</small>
            <button
              className="developer-panel-toggle"
              type="button"
              aria-expanded={ledgerExpanded}
              aria-controls="developer-credit-ledger"
              onClick={toggleLedger}
            >
              {ledgerExpanded ? "收起明细" : "展开明细"}
              <ChevronDown
                size={16}
                aria-hidden="true"
                className={ledgerExpanded ? "is-expanded" : undefined}
              />
            </button>
          </div>
        </div>
        {ledgerExpanded ? (
          <div
            className="developer-ledger-scroll"
            id="developer-credit-ledger"
          >
            <div className="developer-ledger-table">
              <div className="developer-ledger-row header">
                <span>员工</span>
                <span>团队</span>
                <span>变动</span>
                <span>余额</span>
                <span>原因</span>
                <span>时间</span>
              </div>
              {ledger.map((item) => (
                <div className="developer-ledger-row" key={item.id}>
                  <span>{item.employee_name}<small>{item.employee_login}</small></span>
                  <span>{item.tenant_name}</span>
                  <strong className={item.change_amount >= 0 ? "credit-plus" : "credit-minus"}>
                    {item.change_amount >= 0 ? "+" : ""}
                    {formatCredits(item.change_amount)}
                  </strong>
                  <span>{formatCredits(item.after_balance)}</span>
                  <span>{item.reason}</span>
                  <span>{formatTime(item.create_time)}</span>
                </div>
              ))}
              {!loading && ledger.length === 0 ? (
                <div className="developer-empty-state">暂无算力流水</div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      <section className="developer-panel developer-tenant-membership-panel">
        <div className="developer-panel-heading">
          <div>
            <span>06</span>
            <h2>租户会员管理</h2>
          </div>
          <small>
            {tenantMembership ? `${tenantMembership.affected_user_count} 个账号` : "-"}
          </small>
        </div>
        <label>
          <span>选择租户</span>
          <select
            value={selectedTenantId || ""}
            onChange={(event) => setSelectedTenantId(Number(event.target.value))}
          >
            {tenantOptions.map((tenant) => (
              <option key={tenant.tenant_id} value={tenant.tenant_id}>
                {tenant.tenant_name}
              </option>
            ))}
          </select>
        </label>
        <div className="developer-order-meta">
          {tenantMembership?.membership ? (
            <>
              <span>当前方案：{tenantMembership.membership.plan.plan_name}</span>
              <span>
                到期时间：
                {tenantMembership.membership.expire_time
                  ? formatTime(tenantMembership.membership.expire_time)
                  : "长期有效"}
              </span>
              <span>
                状态：
                {membershipStatusLabels[tenantMembership.membership.status] || "未知"}
              </span>
              <span>受影响用户数：{tenantMembership.affected_user_count}</span>
            </>
          ) : (
            <span>该租户暂未开通会员</span>
          )}
        </div>
        <label>
          <span>会员方案</span>
          <select
            value={membershipPlanId || ""}
            onChange={(event) => setMembershipPlanId(Number(event.target.value))}
          >
            {(tenantMembership?.plans ?? []).map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.plan_name}（每月 {formatCredits(plan.monthly_credits)} 算力）
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>有效月数</span>
          <input
            inputMode="numeric"
            type="number"
            min={0}
            max={36}
            value={membershipDuration}
            placeholder="0 表示长期有效"
            onChange={(event) => setMembershipDuration(event.target.value)}
          />
        </label>
        <button
          className="primary-button"
          type="button"
          disabled={submitting || tenantOptions.length === 0}
          onClick={() => void adjustTenantMembership()}
        >
          <Crown size={17} aria-hidden="true" />
          确认调整
        </button>
      </section>
    </section>
  );
}
