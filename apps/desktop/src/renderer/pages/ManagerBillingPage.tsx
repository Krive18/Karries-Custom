import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Eye,
  Image,
  Loader2,
  RefreshCw,
  Sparkles,
  UsersRound,
  WalletCards,
  X,
  XCircle,
  Zap
} from "lucide-react";

import { managerApi } from "../api/managerClient";
import alipayCollectionQr from "../assets/payment/alipay-collection.png";
import wechatCollectionQr from "../assets/payment/wechat-collection.png";
import type {
  AdminBillingOverview,
  AdminEmployeeView,
  AdminRechargeOrder,
  MembershipPlan,
  MembershipUpgradeOrder,
  RechargePackage
} from "../types";


const emptyOverview: AdminBillingOverview = {
  membership: {
    id: 0,
    tenant_id: 0,
    user_id: 0,
    plan_id: 0,
    status: 1,
    start_time: 0,
    expire_time: 0,
    auto_renew: 0,
    create_time: 0,
    update_time: 0,
    plan: {
      id: 0,
      plan_code: "free",
      plan_name: "免费版",
      price_cent: 0,
      summary: "",
      features: [],
      monthly_credits: 0,
      daily_checkin_credits: 0,
      storage_gb: 0,
      status: 1,
      sort_order: 0,
      create_time: 0,
      update_time: 0
    }
  },
  wallet: {
    employee_count: 0,
    balance: 0,
    total_recharged: 0,
    total_consumed: 0
  },
  month_orders: {
    order_count: 0,
    pending_order_count: 0,
    completed_amount_cent: 0,
    completed_credits: 0
  },
  credit_trend: [],
  employee_wallets: []
};

const statusLabels: Record<number, string> = {
  1: "待付款",
  2: "待核验",
  3: "已到账",
  4: "已取消",
  5: "核验未通过",
  6: "已付款待发放"
};

const paymentChannelLabels: Record<string, string> = {
  manual: "收款码充值",
  alipay: "支付宝",
  wechat: "微信支付"
};

const membershipOrderStatusLabels: Record<number, string> = {
  1: "待付款",
  2: "开发者审核中",
  3: "已开通",
  4: "已驳回",
  5: "已取消"
};

type CollectionChannel = "wechat" | "alipay";

function formatMoney(value: number) {
  return `¥${(value / 100).toLocaleString("zh-CN")}`;
}

function formatCredits(value: number) {
  return value.toLocaleString("zh-CN");
}

function formatDate(timestamp: number) {
  if (!timestamp) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


export function ManagerBillingPage() {
  const [overview, setOverview] = useState(emptyOverview);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [packages, setPackages] = useState<RechargePackage[]>([]);
  const [orders, setOrders] = useState<AdminRechargeOrder[]>([]);
  const [membershipOrders, setMembershipOrders] = useState<MembershipUpgradeOrder[]>([]);
  const [employees, setEmployees] = useState<AdminEmployeeView[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [selectedPackageId, setSelectedPackageId] = useState(0);
  const [customAmount, setCustomAmount] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [collectionChannel, setCollectionChannel] =
    useState<CollectionChannel>("wechat");
  const [pendingPaymentOrder, setPendingPaymentOrder] =
    useState<AdminRechargeOrder | null>(null);
  const [pendingMembershipOrder, setPendingMembershipOrder] =
    useState<MembershipUpgradeOrder | null>(null);
  const [proofOrder, setProofOrder] = useState<AdminRechargeOrder | null>(null);
  const [proofUrl, setProofUrl] = useState("");
  const [proofLoading, setProofLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [
        nextOverview,
        nextPlans,
        nextPackages,
        nextOrders,
        nextMembershipOrders,
        nextEmployees
      ] = await Promise.all([
        managerApi.getBillingOverview(),
        managerApi.listAdminMembershipPlans(),
        managerApi.listAdminRechargePackages(),
        managerApi.listAdminRechargeOrders(
          new URLSearchParams({ page: "1", page_size: "20" })
        ),
        managerApi.listAdminMembershipOrders(
          new URLSearchParams({ page: "1", page_size: "20" })
        ),
        managerApi.listEmployees(
          new URLSearchParams({ page: "1", page_size: "100", status: "1" })
        )
      ]);
      setOverview(nextOverview);
      setPlans(nextPlans);
      setPackages(nextPackages);
      setOrders(nextOrders.items);
      setMembershipOrders(nextMembershipOrders.items);
      setEmployees(nextEmployees.items);
      setEmployeeId((current) => current || String(nextEmployees.items[0]?.id ?? ""));
      setSelectedPackageId((current) => current || nextPackages[0]?.id || 0);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "会员与充值数据加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    return () => {
      if (proofUrl) URL.revokeObjectURL(proofUrl);
    };
  }, [proofUrl]);

  const selectedPackage = useMemo(
    () => packages.find((item) => item.id === selectedPackageId) ?? null,
    [packages, selectedPackageId]
  );

  async function createMembershipOrder(plan: MembershipPlan) {
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const order = await managerApi.createAdminMembershipOrder({
        plan_id: plan.id,
        duration_months: 1,
        payment_channel: collectionChannel
      });
      setPendingPaymentOrder(null);
      setPendingMembershipOrder(order);
      setMessage(`已创建 ${plan.plan_name} 支付申请，请扫码完成付款。`);
      await load();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "会员支付申请创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function createRechargeOrder() {
    const nextEmployeeId = Number(employeeId);
    const customAmountCent = Math.round(Number(customAmount || 0) * 100);
    if (!nextEmployeeId) {
      setError("请先选择需要充值的员工。");
      return;
    }
    if (!selectedPackage && customAmountCent < 1000) {
      setError("自定义充值金额不能低于 10 元。");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const order = await managerApi.createAdminRechargeOrder({
        employee_id: nextEmployeeId,
        recharge_type: selectedPackage ? "package" : "online",
        package_id: selectedPackage?.id ?? 0,
        amount_cent: selectedPackage ? 0 : customAmountCent,
        payment_channel: "manual"
      });
      setPendingPaymentOrder(order);
      setMessage("充值单已创建，请扫码付款，并在核对实际收款记录后确认到账。");
      setCustomAmount("");
      await load();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "充值处理失败");
    } finally {
      setSubmitting(false);
    }
  }

  function openCollectionPayment(order: AdminRechargeOrder) {
    setPendingMembershipOrder(null);
    setPendingPaymentOrder(order);
    setCollectionChannel("wechat");
    setError("");
    setMessage("");
  }

  function openMembershipPayment(order: MembershipUpgradeOrder) {
    setPendingPaymentOrder(null);
    setPendingMembershipOrder(order);
    setCollectionChannel(order.payment_channel);
    setError("");
    setMessage("");
  }

  function closeCollectionPayment() {
    if (submitting) return;
    setPendingPaymentOrder(null);
    setPendingMembershipOrder(null);
  }

  async function confirmMembershipOrder(orderId: number) {
    setSubmitting(true);
    setError("");
    try {
      await managerApi.confirmAdminMembershipOrder(orderId);
      setMessage("付款已提交，等待开发者审核开通会员。审核前不会变更当前方案。");
      setPendingMembershipOrder(null);
      await load();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "会员订单提交审核失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelMembershipOrder(order: MembershipUpgradeOrder) {
    setSubmitting(true);
    setError("");
    try {
      const cancelled = await managerApi.cancelAdminMembershipOrder(order.id);
      setMembershipOrders((current) =>
        current.map((item) => item.id === cancelled.id ? cancelled : item)
      );
      if (pendingMembershipOrder?.id === order.id) {
        setPendingMembershipOrder(null);
      }
      setMessage(`${order.plan.plan_name}开通申请已取消，当前会员方案不受影响。`);
      await load();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "会员开通申请取消失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmOrder(orderId: number) {
    setSubmitting(true);
    setError("");
    try {
      await managerApi.confirmAdminRechargeOrder(orderId);
      setMessage("已确认付款，等待平台发放算力。");
      setPendingPaymentOrder(null);
      await load();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "订单确认失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function openPaymentProof(order: AdminRechargeOrder) {
    if (proofUrl) URL.revokeObjectURL(proofUrl);
    setProofOrder(order);
    setProofUrl("");
    setRejectReason("");
    setProofLoading(true);
    setError("");
    try {
      const blob = await managerApi.getAdminRechargePaymentProofBlob(order.id);
      setProofUrl(URL.createObjectURL(blob));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "付款凭证加载失败");
      setProofOrder(null);
    } finally {
      setProofLoading(false);
    }
  }

  function closePaymentProof() {
    if (proofUrl) URL.revokeObjectURL(proofUrl);
    setProofUrl("");
    setProofOrder(null);
    setRejectReason("");
  }

  async function confirmProofOrder() {
    if (!proofOrder) return;
    await confirmOrder(proofOrder.id);
    closePaymentProof();
  }

  async function rejectProofOrder() {
    if (!proofOrder) return;
    const reason = rejectReason.trim();
    if (reason.length < 2) {
      setError("请填写至少 2 个字的驳回原因。");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await managerApi.rejectAdminRechargeOrder(proofOrder.id, reason);
      setMessage("付款凭证已驳回，订单未发放算力。");
      closePaymentProof();
      await load();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "付款凭证驳回失败");
    } finally {
      setSubmitting(false);
    }
  }

  const checkoutOrder = pendingMembershipOrder ?? pendingPaymentOrder;

  return (
    <section className="manager-billing-page">
      <header className="manager-page-header">
        <div>
          <h1>会员与充值</h1>
          <p>统一管理团队会员方案，并为指定员工补充算力</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void load()}>
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          刷新数据
        </button>
      </header>

      {error ? <div className="form-message error" role="alert">{error}</div> : null}
      {message ? <div className="form-message success" role="status">{message}</div> : null}

      <div className="manager-billing-kpis">
        <article>
          <Sparkles size={20} />
          <span>当前团队会员</span>
          <strong>{overview.membership.plan.plan_name}</strong>
          <small>{overview.membership.expire_time ? `${formatDate(overview.membership.expire_time)} 到期` : "长期有效"}</small>
        </article>
        <article>
          <UsersRound size={20} />
          <span>在用员工</span>
          <strong>{overview.wallet.employee_count}</strong>
          <small>会员权益同步覆盖</small>
        </article>
        <article>
          <WalletCards size={20} />
          <span>团队剩余算力</span>
          <strong>{formatCredits(overview.wallet.balance)}</strong>
          <small>员工钱包合计</small>
        </article>
        <article>
          <CircleDollarSign size={20} />
          <span>本月充值</span>
          <strong>{formatMoney(overview.month_orders.completed_amount_cent)}</strong>
          <small>{formatCredits(overview.month_orders.completed_credits)} 算力已到账</small>
        </article>
      </div>

      <section className="manager-billing-section">
        <div className="manager-section-heading">
          <div><h2>团队会员方案</h2><p>扫码付款后提交申请，由开发者审核通过再同步团队账号</p></div>
          <span className="manager-section-status"><CheckCircle2 size={15} /> 当前为 {overview.membership.plan.plan_name}</span>
        </div>
        <div className="manager-plan-grid">
          {plans.map((plan) => {
            const current = plan.id === overview.membership.plan.id;
            const included = plan.sort_order < overview.membership.plan.sort_order;
            const unpaidOrder = membershipOrders.find(
              (order) => order.plan_id === plan.id && order.status === 1
            );
            const reviewingOrder = membershipOrders.find(
              (order) => order.plan_id === plan.id && order.status === 2
            );
            return (
              <article className={current ? "manager-plan-card current" : "manager-plan-card"} key={plan.id}>
                <div>
                  <span>{plan.plan_code.toUpperCase()}</span>
                  {current ? <small>当前方案</small> : null}
                </div>
                <h3>{plan.plan_name}</h3>
                <strong>{plan.price_cent ? `${formatMoney(plan.price_cent)} / 月` : "免费"}</strong>
                <p>{plan.summary}</p>
                <ul>
                  <li><Zap size={15} />每月 {formatCredits(plan.monthly_credits)} 算力</li>
                  <li><Check size={15} />每日签到 +{plan.daily_checkin_credits}</li>
                  <li><Check size={15} />{plan.storage_gb} GB 云空间</li>
                </ul>
                <button
                  type="button"
                  disabled={current || included || Boolean(reviewingOrder) || submitting}
                  onClick={() => {
                    if (unpaidOrder) {
                      openMembershipPayment(unpaidOrder);
                      return;
                    }
                    void createMembershipOrder(plan);
                  }}
                >
                  {current
                    ? "当前订阅"
                    : included
                      ? "已开通"
                      : unpaidOrder
                        ? "继续支付"
                        : reviewingOrder
                        ? "等待审核"
                        : "立即开通"}
                </button>
              </article>
            );
          })}
        </div>
        {membershipOrders.length ? (
          <div className="manager-membership-orders" aria-label="会员申请记录">
            {membershipOrders.slice(0, 4).map((order) => (
              <div key={order.id}>
                <span>{order.plan.plan_name} · {order.order_no}</span>
                <div className="manager-membership-order-actions">
                  <strong className={`status-${order.status}`}>
                    {membershipOrderStatusLabels[order.status]}
                  </strong>
                  {order.status === 1 || order.status === 2 ? (
                    <button
                      type="button"
                      disabled={submitting}
                      aria-label={`取消${order.plan.plan_name}申请`}
                      onClick={() => void cancelMembershipOrder(order)}
                    >
                      取消申请
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <div className="manager-billing-workspace">
        <section className="manager-billing-section manager-recharge-panel">
          <div className="manager-section-heading">
            <div><h2>员工算力充值</h2><p>确认后直接记入员工钱包并生成可追溯流水</p></div>
          </div>
          <div className="manager-recharge-fields">
            <label>
              充值员工
              <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}>
                <option value="">请选择员工</option>
                {employees.map((employee) => (
                  <option value={employee.id} key={employee.id}>
                    {employee.nickname}（{employee.login_name}）
                  </option>
                ))}
              </select>
            </label>
            <label>
              自定义金额
              <div className="manager-money-input">
                <span>¥</span>
                <input
                  type="number"
                  min="10"
                  value={customAmount}
                  placeholder="输入金额后使用自定义充值"
                  onChange={(event) => {
                    setCustomAmount(event.target.value);
                    if (event.target.value) setSelectedPackageId(0);
                  }}
                />
              </div>
            </label>
          </div>
          <div className="manager-package-options">
            {packages.map((item) => (
              <button
                type="button"
                className={selectedPackageId === item.id ? "active" : ""}
                key={item.id}
                onClick={() => {
                  setSelectedPackageId(item.id);
                  setCustomAmount("");
                }}
              >
                {item.is_hot ? <span>推荐</span> : null}
                <strong>{formatMoney(item.price_cent)}</strong>
                <small>到账 {formatCredits(item.credits)} 算力</small>
              </button>
            ))}
          </div>
          <div className="manager-recharge-preview">
            <div>
              <span>本次到账</span>
              <strong>
                {formatCredits(
                  selectedPackage?.credits
                    ?? Math.floor(Math.round(Number(customAmount || 0) * 100) / 5)
                )} 算力
              </strong>
            </div>
            <button
              className="primary-button"
              type="button"
              disabled={submitting}
              onClick={() => void createRechargeOrder()}
            >
              {submitting ? <Loader2 size={17} className="spin" /> : <WalletCards size={17} />}
              去支付
            </button>
          </div>
        </section>

        <section className="manager-billing-section manager-order-panel">
          <div className="manager-section-heading">
            <div><h2>最近充值订单</h2><p>员工付款凭证核验通过后，算力才会发放</p></div>
            <span>{orders.length} 笔</span>
          </div>
          <div className="manager-order-list">
            {orders.length ? orders.map((order) => (
              <article key={order.id}>
                <div>
                  <strong>{order.employee_name}</strong>
                  <span>{order.order_no}</span>
                </div>
                <div>
                  <strong>{formatMoney(order.amount_cent)}</strong>
                  <span>
                    {paymentChannelLabels[order.payment_channel] ?? "其他方式"}
                    {" · "}
                    {formatCredits(order.requested_credits)} 算力
                  </span>
                </div>
                <div>
                  <span className={`manager-order-status status-${order.status}`}>
                    {statusLabels[order.status]}
                  </span>
                  <small>{formatDate(order.create_time)}</small>
                </div>
                {order.status === 2 && order.has_payment_proof ? (
                  <button
                    type="button"
                    disabled={submitting || proofLoading}
                    onClick={() => void openPaymentProof(order)}
                  >
                    <Eye size={15} aria-hidden="true" />
                    查看凭证
                  </button>
                ) : order.status === 1 && order.payment_channel === "manual" ? (
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => openCollectionPayment(order)}
                  >
                    继续支付
                  </button>
                ) : <Clock3 size={17} aria-hidden="true" />}
              </article>
            )) : <div className="manager-empty-state">暂无充值订单</div>}
          </div>
        </section>
      </div>

      {checkoutOrder ? (
        <div
          className="payment-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) closeCollectionPayment();
          }}
        >
          <section
            className="payment-checkout-modal manager-payment-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="manager-payment-title"
          >
            <header>
              <div>
                <span><WalletCards size={17} aria-hidden="true" /> 固定收款码</span>
                <h2 id="manager-payment-title">扫码完成付款</h2>
              </div>
              <button
                type="button"
                aria-label="关闭付款窗口"
                onClick={closeCollectionPayment}
                disabled={submitting}
              >
                <X size={20} aria-hidden="true" />
              </button>
            </header>
            <div className="manager-payment-body">
              <div className="manager-payment-channel" role="tablist" aria-label="选择收款方式">
                <button
                  type="button"
                  className={collectionChannel === "wechat" ? "active" : ""}
                  onClick={() => setCollectionChannel("wechat")}
                >
                  微信支付
                </button>
                <button
                  type="button"
                  className={collectionChannel === "alipay" ? "active" : ""}
                  onClick={() => setCollectionChannel("alipay")}
                >
                  支付宝
                </button>
              </div>
              <div className="manager-payment-content">
                <div className="manager-payment-qr">
                  <img
                    src={collectionChannel === "wechat" ? wechatCollectionQr : alipayCollectionQr}
                    alt={collectionChannel === "wechat" ? "微信收款二维码" : "支付宝收款二维码"}
                  />
                </div>
                <div className="manager-payment-summary">
                  <span>应付金额</span>
                  <strong>{formatMoney(checkoutOrder.amount_cent)}</strong>
                  <dl>
                    {pendingMembershipOrder ? (
                      <div>
                        <dt>购买方案</dt>
                        <dd>{pendingMembershipOrder.plan.plan_name}会员升级</dd>
                      </div>
                    ) : (
                      <>
                        <div>
                          <dt>充值员工</dt>
                          <dd>{pendingPaymentOrder?.employee_name}</dd>
                        </div>
                        <div>
                          <dt>到账算力</dt>
                          <dd>{formatCredits(pendingPaymentOrder?.requested_credits ?? 0)}</dd>
                        </div>
                      </>
                    )}
                    <div>
                      <dt>内部单号</dt>
                      <dd>{checkoutOrder.order_no}</dd>
                    </div>
                  </dl>
                  <p>
                    {pendingMembershipOrder
                      ? "本页面不读取微信或支付宝支付结果。请确认付款后提交开发者审核，审核通过后会员才会生效。"
                      : "本页面不读取微信或支付宝支付结果。请先在收款账户中确认实际到账，再标记员工已付款。"}
                  </p>
                  <button
                    type="button"
                    className="primary-button"
                    disabled={submitting}
                    onClick={() => void (
                      pendingMembershipOrder
                        ? confirmMembershipOrder(pendingMembershipOrder.id)
                        : confirmOrder(checkoutOrder.id)
                    )}
                  >
                    {submitting
                      ? <Loader2 className="spin" size={17} />
                      : <CheckCircle2 size={17} />}
                    {pendingMembershipOrder ? "确认已付款，提交审核" : "确认已付款"}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      ) : null}

      {proofOrder ? (
        <div
          className="payment-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target && !submitting) {
              closePaymentProof();
            }
          }}
        >
          <section
            className="manager-proof-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="manager-proof-title"
          >
            <header>
              <div>
                <span><Image size={17} aria-hidden="true" /> 付款凭证核验</span>
                <h2 id="manager-proof-title">{proofOrder.employee_name}</h2>
              </div>
              <button
                type="button"
                aria-label="关闭凭证窗口"
                onClick={closePaymentProof}
                disabled={submitting}
              >
                <X size={20} aria-hidden="true" />
              </button>
            </header>
            <div className="manager-proof-body">
              <div className="manager-proof-image">
                {proofLoading ? (
                  <span><Loader2 className="spin" size={24} /> 正在加载凭证</span>
                ) : proofUrl ? (
                  <img src={proofUrl} alt={`${proofOrder.employee_name} 的付款凭证`} />
                ) : null}
              </div>
              <div className="manager-proof-details">
                <dl>
                  <div><dt>订单号</dt><dd>{proofOrder.order_no}</dd></div>
                  <div><dt>支付方式</dt><dd>{paymentChannelLabels[proofOrder.payment_channel]}</dd></div>
                  <div><dt>应付金额</dt><dd>{formatMoney(proofOrder.amount_cent)}</dd></div>
                  <div><dt>拟发放算力</dt><dd>{formatCredits(proofOrder.requested_credits)}</dd></div>
                  <div><dt>付款信息</dt><dd>{proofOrder.payer_note || "-"}</dd></div>
                  <div>
                    <dt>提交时间</dt>
                    <dd>{proofOrder.proof_submit_time ? formatDate(proofOrder.proof_submit_time) : "-"}</dd>
                  </div>
                </dl>
                <div className="manager-proof-warning">
                  请先核对实际收款记录、金额与付款信息。确认后订单将交由平台发放算力。
                </div>
                <label className="manager-proof-reject-field">
                  核验不通过时填写原因
                  <textarea
                    value={rejectReason}
                    maxLength={200}
                    placeholder="例如：付款金额不一致，请重新提交正确凭证"
                    onChange={(event) => setRejectReason(event.target.value)}
                  />
                </label>
                <div className="manager-proof-actions">
                  <button
                    type="button"
                    className="secondary-button danger"
                    disabled={submitting || proofLoading || !proofUrl}
                    onClick={() => void rejectProofOrder()}
                  >
                    <XCircle size={17} />
                    驳回凭证
                  </button>
                  <button
                    type="button"
                    className="primary-button"
                    disabled={submitting || proofLoading || !proofUrl}
                    onClick={() => void confirmProofOrder()}
                  >
                    {submitting
                      ? <Loader2 className="spin" size={17} />
                      : <CheckCircle2 size={17} />}
                    确认已付款
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
