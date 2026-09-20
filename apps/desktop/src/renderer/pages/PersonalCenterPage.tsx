import { useCallback, useEffect, useState } from "react";
import {
  ALargeSmall,
  CalendarCheck,
  ChevronRight,
  CircleUserRound,
  Clock3,
  Coins,
  Loader2,
  LockKeyhole,
  Sparkles,
  UserRound
} from "lucide-react";

import { customerApi } from "../api/client";
import { FontScaleSelector } from "../components/FontScaleSelector";
import type {
  AuthUser,
  CreditLedgerView,
  DailyCheckinStatus,
  UserMembership,
  WalletView
} from "../types";


type PersonalCenterPageProps = {
  user: AuthUser;
  onOpenRecharge: () => void;
};

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


export function PersonalCenterPage({
  user,
  onOpenRecharge
}: PersonalCenterPageProps) {
  const [wallet, setWallet] = useState<WalletView | null>(null);
  const [membership, setMembership] = useState<UserMembership | null>(null);
  const [ledger, setLedger] = useState<CreditLedgerView[]>([]);
  const [checkin, setCheckin] = useState<DailyCheckinStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkingIn, setCheckingIn] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextWallet, nextMembership, nextLedger, nextCheckin] = await Promise.all([
        customerApi.getWallet(),
        customerApi.getCurrentMembership(),
        customerApi.listCreditLedger(),
        customerApi.getDailyCheckinStatus()
      ]);
      setWallet(nextWallet);
      setMembership(nextMembership);
      setLedger(nextLedger.slice(0, 6));
      setCheckin(nextCheckin);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "个人中心加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const refreshWallet = async () => {
      try {
        setWallet(await customerApi.getWallet());
      } catch {
        // Keep the last confirmed balance when a background refresh fails.
      }
    };
    const intervalId = window.setInterval(() => {
      void refreshWallet();
    }, 10_000);
    const handleFocus = () => {
      void refreshWallet();
    };

    window.addEventListener("focus", handleFocus);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
    };
  }, []);

  async function handleCheckin() {
    if (checkin?.checked_in || checkingIn) {
      return;
    }
    setCheckingIn(true);
    setError("");
    setMessage("");
    try {
      const nextCheckin = await customerApi.dailyCheckIn();
      const [nextWallet, nextLedger] = await Promise.all([
        customerApi.getWallet(),
        customerApi.listCreditLedger()
      ]);
      setCheckin(nextCheckin);
      setWallet(nextWallet);
      setLedger(nextLedger.slice(0, 6));
      setMessage(`签到成功，已获得 ${nextCheckin.credits} 算力`);
    } catch (checkinError) {
      setError(checkinError instanceof Error ? checkinError.message : "签到失败，请稍后重试");
    } finally {
      setCheckingIn(false);
    }
  }

  const displayName = user.nickname.trim() || user.login_name;

  return (
    <section className="personal-page page-stack">
      <header className="compact-page-heading">
        <div className="page-heading-copy">
          <h1>个人中心</h1>
          <p>管理个人账号信息，查看会员与算力使用情况。</p>
        </div>
      </header>

      {error ? <div className="form-message error" role="alert">{error}</div> : null}
      {message ? <div className="form-message success" role="status">{message}</div> : null}
      {loading ? (
        <div className="billing-loading" role="status">
          <Loader2 className="spin" size={22} />
          正在加载个人信息
        </div>
      ) : (
        <>
          <section className="personal-identity-band">
            <div className="personal-avatar">
              <CircleUserRound size={34} aria-hidden="true" />
            </div>
            <div className="personal-identity-copy">
              <span>禾一斯运营成员</span>
              <h2>{displayName}</h2>
              <p>@{user.login_name} · 员工编号 {user.id}</p>
            </div>
            <div className="personal-quick-stats">
              <div><span>当前会员</span><strong>{membership?.plan.plan_name ?? "Pro"}</strong></div>
              <div><span>可用算力</span><strong>{wallet?.balance ?? user.wallet_balance}</strong></div>
            </div>
            <button
              type="button"
              className={checkin?.checked_in ? "daily-checkin-button checked" : "daily-checkin-button"}
              disabled={Boolean(checkin?.checked_in || checkingIn)}
              onClick={() => void handleCheckin()}
            >
              {checkingIn ? <Loader2 className="spin" size={18} /> : <CalendarCheck size={18} />}
              <span>
                <strong>{checkin?.checked_in ? "今日已签到" : "每日签到"}</strong>
                <small>{checkin?.checked_in ? `已获得 ${checkin.credits} 算力` : `签到 +${checkin?.credits ?? 20} 算力`}</small>
              </span>
            </button>
          </section>

          <section className="panel personal-display-panel">
            <div className="section-title-row">
              <div><ALargeSmall size={19} /><h2>界面显示</h2></div>
            </div>
            <div className="personal-display-setting">
              <p>不同电脑的屏幕缩放可能让界面字忽大忽小，可在这里调整界面缩放档位，立即生效并记住选择。</p>
              <FontScaleSelector />
            </div>
          </section>

          <div className="personal-grid">
            <section className="panel personal-account-panel">
              <div className="section-title-row">
                <div><UserRound size={19} /><h2>账号资料</h2></div>
              </div>
              <dl className="personal-detail-list">
                <div><dt>显示名称</dt><dd>{displayName}</dd></div>
                <div><dt>登录账号</dt><dd>{user.login_name}</dd></div>
                <div><dt>所属团队</dt><dd>禾一斯运营团队</dd></div>
                <div><dt>账号角色</dt><dd>运营成员</dd></div>
              </dl>
            </section>

            <section className="panel personal-membership-panel">
              <div className="section-title-row">
                <div><Sparkles size={19} /><h2>会员与算力</h2></div>
              </div>
              <div className="personal-plan-summary">
                <div>
                  <span>当前订阅</span>
                  <strong>{membership?.plan.plan_name ?? "Pro"}</strong>
                  <small>{membership?.expire_time ? `${formatDate(membership.expire_time)} 到期` : "长期有效"}</small>
                </div>
                <div>
                  <span>可用算力</span>
                  <strong>{wallet?.balance ?? 0}</strong>
                  <small>累计使用 {wallet?.total_consumed ?? 0}</small>
                </div>
              </div>
              <div className="personal-plan-benefits">
                <span>每月发放 <strong>{membership?.plan.monthly_credits ?? 1500}</strong> 算力</span>
                <span>每日签到 <strong>+{membership?.plan.daily_checkin_credits ?? 20}</strong></span>
                <span>云空间 <strong>{membership?.plan.storage_gb ?? 100} GB</strong></span>
              </div>
              <button type="button" className="personal-link-button" onClick={onOpenRecharge}>
                进入充值中心
                <ChevronRight size={17} aria-hidden="true" />
              </button>
            </section>
          </div>

          <div className="personal-grid personal-lower-grid">
            <section className="panel personal-ledger-panel">
              <div className="section-title-row">
                <div><Coins size={19} /><h2>最近算力记录</h2></div>
                <span>{ledger.length} 条</span>
              </div>
              {ledger.length ? (
                <div className="personal-ledger-list">
                  {ledger.map((item) => (
                    <div key={item.id}>
                      <span className={item.change_amount >= 0 ? "ledger-icon positive" : "ledger-icon"}>
                        <Coins size={16} />
                      </span>
                      <div>
                        <strong>{item.reason || item.business_type}</strong>
                        <span><Clock3 size={13} />{formatDate(item.create_time)}</span>
                      </div>
                      <strong className={item.change_amount >= 0 ? "positive" : ""}>
                        {item.change_amount >= 0 ? "+" : ""}{item.change_amount}
                      </strong>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-inline">暂无算力变动记录</div>
              )}
            </section>

            <section className="panel personal-security-panel">
              <div className="section-title-row">
                <div><LockKeyhole size={19} /><h2>账号安全</h2></div>
              </div>
              <div className="personal-security-content">
                <span><LockKeyhole size={22} /></span>
                <div>
                  <strong>登录密码已设置</strong>
                  <p>员工账号由禾一斯负责人统一创建和维护。如需修改密码，请联系负责人处理。</p>
                </div>
              </div>
            </section>
          </div>
        </>
      )}
    </section>
  );
}
