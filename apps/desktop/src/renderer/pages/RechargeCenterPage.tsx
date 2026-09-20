import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  Activity,
  Check,
  Gift,
  History,
  Loader2,
  RefreshCw,
  Sparkles,
  WalletCards,
  Zap
} from "lucide-react";

import { customerApi } from "../api/client";
import type {
  MembershipPlan,
  RechargeOrder,
  RechargePackage,
  UserMembership,
  WalletView
} from "../types";


type RechargeSection = "membership" | "credits";
type RechargeMode = "package" | "custom";

const customAmountOptions = [10000, 50000, 100000, 200000];
const orderStatusLabels: Record<number, string> = {
  1: "待负责人处理",
  2: "待核验",
  3: "已到账",
  4: "已取消",
  5: "核验未通过"
};
const planCategoryLabels: Record<MembershipPlan["plan_code"], string> = {
  free: "基础体验",
  pro: "全功能版",
  max: "全功能 · 大空间",
  storage: "全功能 · 超大存储"
};

const planHighlights: Record<MembershipPlan["plan_code"], string[]> = {
  free: ["基础创作功能", "每月 500 算力", "10GB 云空间"],
  pro: ["平台全部核心功能", "每月 1,500 算力", "100GB 云空间"],
  max: ["包含 Pro 全部功能", "每月 3,000 算力", "180GB 云空间"],
  storage: ["包含 Pro 全部功能", "每月 3,000 算力", "1000GB 云空间"]
};

function formatMoney(priceCent: number) {
  return `¥${(priceCent / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  })}`;
}

function formatCredits(credits: number) {
  return credits.toLocaleString("zh-CN");
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


export function RechargeCenterPage() {
  const [section, setSection] = useState<RechargeSection>("membership");
  const [rechargeMode, setRechargeMode] = useState<RechargeMode>("package");
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [membership, setMembership] = useState<UserMembership | null>(null);
  const [wallet, setWallet] = useState<WalletView | null>(null);
  const [packages, setPackages] = useState<RechargePackage[]>([]);
  const [orders, setOrders] = useState<RechargeOrder[]>([]);
  const [selectedAmount, setSelectedAmount] = useState(100000);
  const [customAmount, setCustomAmount] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [walletSyncing, setWalletSyncing] = useState(false);
  const [walletSyncFailed, setWalletSyncFailed] = useState(false);
  const [lastWalletSync, setLastWalletSync] = useState<Date | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextPlans, nextMembership, nextWallet, nextPackages, nextOrders] =
        await Promise.all([
          customerApi.listMembershipPlans(),
          customerApi.getCurrentMembership(),
          customerApi.getWallet(),
          customerApi.listRechargePackages(),
          customerApi.listRechargeOrders()
        ]);
      setPlans(nextPlans);
      setMembership(nextMembership);
      setWallet(nextWallet);
      setLastWalletSync(new Date());
      setWalletSyncFailed(false);
      setPackages(nextPackages);
      setOrders(nextOrders);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "账户信息加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const refreshWallet = useCallback(async () => {
    setWalletSyncing(true);
    try {
      const nextWallet = await customerApi.getWallet();
      setWallet(nextWallet);
      setLastWalletSync(new Date());
      setWalletSyncFailed(false);
    } catch {
      setWalletSyncFailed(true);
    } finally {
      setWalletSyncing(false);
    }
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refreshWallet();
    }, 10_000);
    const handleFocus = () => {
      void refreshWallet();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void refreshWallet();
      }
    };

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [refreshWallet]);

  const customAmountCent = useMemo(() => {
    const enteredCent = Math.round(Number(customAmount || 0) * 100);
    return customAmount ? enteredCent : selectedAmount;
  }, [customAmount, selectedAmount]);
  const customCredits = Math.floor(customAmountCent / 5);
  const totalCredits = Math.max(
    0,
    (wallet?.balance ?? 0) + (wallet?.total_consumed ?? 0)
  );
  const availableRatio = totalCredits
    ? Math.round(((wallet?.balance ?? 0) / totalCredits) * 100)
    : 0;
  const creditRingStyle = {
    "--credit-available": `${Math.max(0, Math.min(100, availableRatio)) * 3.6}deg`
  } as CSSProperties;

  async function submitCustomRecharge() {
    if (customAmountCent < 1000) {
      setError("单次充值金额不能低于 10 元");
      return;
    }
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const order = await customerApi.createRechargeOrder({
        recharge_type: "online",
        amount_cent: customAmountCent,
        payment_channel: "manual"
      });
      setMessage(
        `充值需求 ${order.order_no} 已提交，请联系负责人完成付款并确认到账。`
      );
      setOrders(await customerApi.listRechargeOrders());
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "充值订单创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function submitPackageRecharge(packageId: number) {
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const order = await customerApi.createRechargeOrder({
        recharge_type: "package",
        package_id: packageId,
        payment_channel: "manual"
      });
      setMessage(
        `算力包需求 ${order.order_no} 已提交，请联系负责人完成付款并确认到账。`
      );
      setOrders(await customerApi.listRechargeOrders());
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "算力包订单创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="billing-page page-stack">
      <header className="compact-page-heading billing-heading">
        <div className="page-heading-copy">
          <h1>充值中心</h1>
          <p>查看当前会员方案、算力余额和充值订单。</p>
        </div>
      </header>

      <div className="billing-section-tabs" role="tablist" aria-label="充值中心分类">
        <button
          type="button"
          className={section === "membership" ? "active" : ""}
          onClick={() => setSection("membership")}
        >
          <Sparkles size={17} aria-hidden="true" />
          会员计划
        </button>
        <button
          type="button"
          className={section === "credits" ? "active" : ""}
          onClick={() => setSection("credits")}
        >
          <WalletCards size={17} aria-hidden="true" />
          算力充值
        </button>
      </div>

      {error ? <div className="form-message error" role="alert">{error}</div> : null}
      {message ? <div className="form-message success" role="status">{message}</div> : null}

      {loading ? (
        <div className="billing-loading" role="status">
          <Loader2 className="spin" size={22} />
          正在加载账户信息
        </div>
      ) : (
        <>
          <section className="credit-live-overview" aria-live="polite">
            <div className="credit-live-balance">
              <span className="credit-live-kicker">
                <Activity size={15} aria-hidden="true" />
                实时算力账户
              </span>
              <strong>{formatCredits(wallet?.balance ?? 0)}</strong>
              <small>当前可用算力</small>
            </div>
            <div
              className="credit-usage-ring"
              style={creditRingStyle}
              aria-label={`当前剩余 ${availableRatio}% 算力`}
            >
              <div>
                <strong>{availableRatio}%</strong>
                <span>剩余</span>
              </div>
            </div>
            <div className="credit-live-metrics">
              <div>
                <span>累计获得</span>
                <strong>{formatCredits(wallet?.total_recharged ?? 0)}</strong>
              </div>
              <div>
                <span>累计使用</span>
                <strong>{formatCredits(wallet?.total_consumed ?? 0)}</strong>
              </div>
            </div>
            <button
              type="button"
              className={walletSyncFailed ? "credit-sync-state failed" : "credit-sync-state"}
              onClick={() => void refreshWallet()}
              disabled={walletSyncing}
              aria-label="立即同步算力"
            >
              <RefreshCw className={walletSyncing ? "spin" : ""} size={16} aria-hidden="true" />
              <span>{walletSyncFailed ? "同步中断，点击重试" : "实时同步"}</span>
              <small>
                {lastWalletSync
                  ? `更新于 ${lastWalletSync.toLocaleTimeString("zh-CN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: false
                  })}`
                  : "正在连接"}
              </small>
            </button>
          </section>

          {section === "membership" ? (
        <div className="membership-content">
          <section className="current-membership-strip">
            <div>
              <span>当前订阅</span>
              <strong>{membership?.plan.plan_name ?? "Pro会员版"}</strong>
              <p>{membership?.expire_time ? `${formatDate(membership.expire_time)} 到期` : "当前账号长期有效"}</p>
            </div>
            <div className="current-membership-benefits">
              {(planHighlights[membership?.plan.plan_code ?? "pro"]).map((highlight, index) => (
                <span key={highlight}>
                  {index === 0 ? <Check size={15} /> : index === 1 ? <Zap size={15} /> : <Gift size={15} />}
                  {highlight}
                </span>
              ))}
            </div>
            <div className="current-membership-price">
              {formatMoney(membership?.plan.price_cent ?? 19900)}
              <span>/ 月</span>
            </div>
          </section>

          <div className="membership-plan-grid">
            {plans.map((plan) => {
              const isCurrent = membership?.plan.plan_code === plan.plan_code;
              return (
                <article
                  className={isCurrent ? "membership-plan current" : "membership-plan"}
                  key={plan.id}
                >
                  <div className="membership-plan-title">
                    <div>
                      <span>{planCategoryLabels[plan.plan_code]}</span>
                      <h2>{plan.plan_name}</h2>
                    </div>
                    {isCurrent ? <span className="current-plan-badge">当前订阅</span> : null}
                  </div>
                  <div className="membership-price">
                    {plan.price_cent ? formatMoney(plan.price_cent) : "免费"}
                    {plan.price_cent ? <span>/ 月</span> : null}
                  </div>
                  <p>{plan.summary}</p>
                  <div className="membership-benefit-stats">
                    <div><span>每月算力</span><strong>{formatCredits(plan.monthly_credits)}</strong></div>
                    <div><span>签到奖励</span><strong>+{formatCredits(plan.daily_checkin_credits)}</strong></div>
                    <div><span>云空间</span><strong>{plan.storage_gb} GB</strong></div>
                  </div>
                  <div className="membership-plan-divider" />
                  <ul>
                    {plan.features.map((feature) => (
                      <li key={feature}>
                        <Check size={16} aria-hidden="true" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    className={isCurrent ? "membership-action current" : "membership-action"}
                    disabled
                  >
                    {isCurrent ? "当前订阅" : "后续开放"}
                  </button>
                </article>
              );
            })}
          </div>
        </div>
          ) : (
        <div className="credits-content">
          <section className="panel recharge-workbench">
            <div className="recharge-mode-tabs" role="tablist" aria-label="充值方式">
              <button
                type="button"
                className={rechargeMode === "package" ? "active" : ""}
                onClick={() => setRechargeMode("package")}
              >
                算力包充值
              </button>
              <button
                type="button"
                className={rechargeMode === "custom" ? "active" : ""}
                onClick={() => setRechargeMode("custom")}
              >
                自定义充值
              </button>
            </div>

            {rechargeMode === "package" ? (
              <div className="package-recharge-panel">
                <div className="package-recharge-heading">
                  <div>
                    <h2>选择算力包</h2>
                    <p>购买后立即增加算力，不会变更当前订阅方案。</p>
                  </div>
                  <Zap size={24} aria-hidden="true" />
                </div>
                <div className="recharge-package-grid">
                  {packages.map((item) => {
                    const bonus = Math.max(0, item.credits - item.base_credits);
                    return (
                      <article key={item.id} className={item.is_hot ? "recharge-package hot" : "recharge-package"}>
                        {item.is_hot ? <span className="package-hot-badge">推荐</span> : null}
                        <span>{item.package_name}</span>
                        <strong>+{formatCredits(item.base_credits)} <small>基础算力</small></strong>
                        <div className="package-credit-breakdown">
                          <span>实际到账</span>
                          <strong>{formatCredits(item.credits)}</strong>
                        </div>
                        {bonus ? <p>额外加赠 {formatCredits(bonus)} 算力</p> : <p>到账算力与基础额度一致</p>}
                        <div className="package-price">{formatMoney(item.price_cent)}</div>
                        <button
                          type="button"
                          disabled={submitting}
                          onClick={() => void submitPackageRecharge(item.id)}
                        >
                          提交充值需求
                        </button>
                      </article>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="online-recharge-panel">
                <h2>选择充值金额</h2>
                <div className="amount-options">
                  {customAmountOptions.map((amount) => (
                    <button
                      type="button"
                      key={amount}
                      className={!customAmount && selectedAmount === amount ? "active" : ""}
                      onClick={() => {
                        setSelectedAmount(amount);
                        setCustomAmount("");
                      }}
                    >
                      {formatMoney(amount)}
                    </button>
                  ))}
                  <label>
                    <span>¥</span>
                    <input
                      aria-label="自定义充值金额"
                      type="number"
                      min="10"
                      step="1"
                      value={customAmount}
                      placeholder="自定义"
                      onChange={(event) => setCustomAmount(event.target.value)}
                    />
                  </label>
                </div>
                <div className="custom-credit-preview">
                  <span>预计实际到账</span>
                  <strong>{formatCredits(customCredits)} 算力</strong>
                  <small>按 1 元 = 20 算力计算，最终以支付确认结果为准</small>
                </div>
                <button
                  type="button"
                  className="primary-button recharge-submit"
                  disabled={submitting}
                  onClick={() => void submitCustomRecharge()}
                >
                  {submitting ? <Loader2 className="spin" size={18} /> : <WalletCards size={18} />}
                  提交 {formatMoney(customAmountCent)} 充值需求
                </button>
              </div>
            )}

            <div className="recharge-request-note">
              <WalletCards size={20} aria-hidden="true" />
              <div>
                <strong>由负责人统一完成付款</strong>
                <p>提交需求后不会立即扣款。老板确认已付款后，由平台完成算力发放，到账后余额自动更新。</p>
              </div>
            </div>
          </section>

          <section className="panel recharge-history">
            <div className="section-title-row">
              <div><History size={19} aria-hidden="true" /><h2>充值订单</h2></div>
              <span>{orders.length} 条</span>
            </div>
            {orders.length ? (
              <div className="recharge-order-list">
                {orders.map((order) => (
                  <div key={order.id} className="recharge-order-row">
                    <div>
                      <strong>{order.package_name || "自定义充值"}</strong>
                      <span>{order.order_no}</span>
                    </div>
                    <div>
                      <strong>{formatMoney(order.amount_cent)}</strong>
                      <span>预计到账 {formatCredits(order.requested_credits)} 算力</span>
                    </div>
                    <div><span>{formatDate(order.create_time)}</span></div>
                    <div className="recharge-order-actions">
                      <span className={`recharge-status status-${order.status}`}>
                        {orderStatusLabels[order.status]}
                      </span>
                      {order.status === 1 ? <small>等待负责人处理</small> : null}
                      {order.status === 5 && order.remark
                        ? <small title={order.remark}>{order.remark}</small>
                        : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-inline">暂无充值订单</div>
            )}
          </section>
        </div>
          )}
        </>
      )}

    </section>
  );
}
