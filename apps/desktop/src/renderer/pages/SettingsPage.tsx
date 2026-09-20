import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  LogIn,
  Pencil,
  Plus,
  QrCode,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UsersRound,
  X
} from "lucide-react";

import { api } from "../api/client";
import type {
  XHSAccountCreate,
  XHSAccountLoginSession,
  XHSAccountProfile,
  XHSAccountView
} from "../types";


const emptyProfile: XHSAccountProfile = {
  domain_name: "",
  persona: "",
  target_audience: "",
  content_style: "",
  tone: "",
  common_phrases: "",
  forbidden_phrases: "",
  tag_preferences: "[]",
  word_count_preference: 300,
  topic_preferences: ""
};

const emptyDraft: XHSAccountCreate = {
  display_name: "",
  account_group: "",
  daily_limit: 1,
  min_interval_minutes: 360,
  profile: emptyProfile
};

function newAccountDraft(): XHSAccountCreate {
  return {
    ...emptyDraft,
    profile: { ...emptyProfile }
  };
}

const activeLoginStatuses = new Set(["starting", "awaiting_scan"]);


function accountStatus(account: XHSAccountView) {
  if (account.status === 1 && account.login_state_ready) {
    return { className: "success", label: "已登录" };
  }
  if (account.status === 2 && account.login_state_ready) {
    return { className: "danger", label: "登录已失效" };
  }
  if (account.status === 3) {
    return { className: "neutral", label: "已暂停" };
  }
  if (account.status === 4) {
    return { className: "danger", label: "账号受限" };
  }
  return { className: "pending", label: "待扫码登录" };
}


export function SettingsPage() {
  const [accounts, setAccounts] = useState<XHSAccountView[]>([]);
  const [draft, setDraft] = useState<XHSAccountCreate>(newAccountDraft);
  const [showForm, setShowForm] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingAccountId, setDeletingAccountId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [loginAccount, setLoginAccount] = useState<XHSAccountView | null>(null);
  const [loginSession, setLoginSession] = useState<XHSAccountLoginSession | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);
  const [checkingAccountId, setCheckingAccountId] = useState<number | null>(null);

  const loadAccounts = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setMessage("");
    }
    try {
      const result = await api.listXHSAccounts();
      setAccounts(Array.isArray(result) ? result : []);
    } catch (error) {
      if (!silent) {
        setMessage(error instanceof Error ? error.message : "账号加载失败");
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    if (
      !loginAccount ||
      !loginSession ||
      !activeLoginStatuses.has(loginSession.status)
    ) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void api
        .getLatestXHSAccountLoginSession(loginAccount.id)
        .then((latest) => {
          if (!latest) {
            return;
          }
          setLoginSession(latest);
          if (latest.status === "success") {
            setMessage(`${loginAccount.display_name} 已完成扫码登录`);
            void loadAccounts(true);
          }
        })
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "登录状态刷新失败");
        });
    }, 2000);

    return () => window.clearInterval(timer);
  }, [loadAccounts, loginAccount, loginSession]);

  function updateProfile(field: keyof XHSAccountProfile, value: string | number) {
    setDraft((current) => ({
      ...current,
      profile: { ...current.profile, [field]: value }
    }));
  }

  function openCreateForm() {
    setDraft(newAccountDraft());
    setEditingAccountId(null);
    setShowForm(true);
    setMessage("");
  }

  function openEditForm(account: XHSAccountView) {
    setDraft({
      display_name: account.display_name,
      account_group: account.account_group,
      daily_limit: account.daily_limit,
      min_interval_minutes: account.min_interval_minutes,
      profile: {
        domain_name: account.profile.domain_name,
        persona: account.profile.persona,
        target_audience: account.profile.target_audience,
        content_style: account.profile.content_style,
        tone: account.profile.tone,
        common_phrases: account.profile.common_phrases,
        forbidden_phrases: account.profile.forbidden_phrases,
        tag_preferences: account.profile.tag_preferences,
        word_count_preference: account.profile.word_count_preference,
        topic_preferences: account.profile.topic_preferences
      }
    });
    setEditingAccountId(account.id);
    setShowForm(true);
    setMessage("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function closeAccountForm() {
    setShowForm(false);
    setEditingAccountId(null);
    setDraft(newAccountDraft());
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.display_name.trim()) {
      setMessage("请填写小红书账号名称");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const payload = {
        ...draft,
        display_name: draft.display_name.trim(),
        account_group: draft.account_group.trim()
      };
      const account = editingAccountId
        ? await api.updateXHSAccount(editingAccountId, payload)
        : await api.createXHSAccount(payload);
      setAccounts((current) =>
        editingAccountId
          ? current.map((item) => (item.id === account.id ? account : item))
          : [account, ...current.filter((item) => item.id !== account.id)]
      );
      closeAccountForm();
      setMessage(
        editingAccountId
          ? "账号资料已更新"
          : "账号资料已保存，请继续完成扫码登录"
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function deleteAccount(account: XHSAccountView) {
    if (!window.confirm(`确认删除“小红书账号 ${account.display_name}”吗？`)) {
      return;
    }
    setDeletingAccountId(account.id);
    setMessage("");
    try {
      await api.deleteXHSAccount(account.id);
      setAccounts((current) => current.filter((item) => item.id !== account.id));
      if (editingAccountId === account.id) {
        closeAccountForm();
      }
      if (loginAccount?.id === account.id) {
        closeLoginDialog();
      }
      setMessage("账号已删除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号删除失败");
    } finally {
      setDeletingAccountId(null);
    }
  }

  async function startLogin(account: XHSAccountView) {
    setLoginAccount(account);
    setLoginSession(null);
    setLoginLoading(true);
    setMessage("");
    try {
      const session = await api.startXHSAccountLogin(account.id);
      setLoginSession(session);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法启动扫码登录");
      setLoginSession({
        id: 0,
        xhs_account_id: account.id,
        status: "failed",
        message: "无法启动扫码登录，请稍后重试",
        qrcode_image_data: "",
        started_time: 0,
        expires_time: 0,
        completed_time: 0,
        create_time: 0,
        update_time: 0
      });
    } finally {
      setLoginLoading(false);
    }
  }

  async function checkLogin(account: XHSAccountView) {
    setCheckingAccountId(account.id);
    setMessage("");
    try {
      const result = await api.checkXHSAccountLogin(account.id);
      setAccounts((current) =>
        current.map((item) => (item.id === account.id ? result.account : item))
      );
      setMessage(
        result.valid
          ? `${account.display_name} 登录状态正常，可以执行自动发布`
          : `${account.display_name} 登录已失效，请重新扫码`
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "登录状态检测失败");
    } finally {
      setCheckingAccountId(null);
    }
  }

  function closeLoginDialog() {
    setLoginAccount(null);
    setLoginSession(null);
    setLoginLoading(false);
  }

  return (
    <section className="page-stack">
      <div className="page-heading account-heading compact-page-heading">
        <div className="page-heading-copy">
          <h1>小红书账号管理</h1>
          <p>维护矩阵账号定位、登录状态和自动发布频率。</p>
        </div>
        <button className="primary-button" type="button" onClick={openCreateForm}>
          <Plus size={18} aria-hidden="true" />
          新增账号
        </button>
      </div>

      {message ? <div className="form-message">{message}</div> : null}

      {showForm ? (
        <form className="panel account-create-panel" onSubmit={handleSubmit}>
          <header className="account-create-header">
            <div>
              <span className="section-eyebrow">账号资料</span>
              <h2>{editingAccountId ? "编辑矩阵账号" : "新增矩阵账号"}</h2>
              <p>
                {editingAccountId
                  ? "更新账号定位和发布策略，已保存的登录状态不会受到影响。"
                  : "先完善账号定位，授权登录后即可加入内容发布计划。"}
              </p>
            </div>
            <button
              className="icon-button"
              type="button"
              title={editingAccountId ? "关闭编辑账号" : "关闭新增账号"}
              onClick={closeAccountForm}
            >
              <X size={18} aria-hidden="true" />
            </button>
          </header>

          <section className="account-form-section" aria-labelledby="account-basic-title">
            <div className="account-form-section-heading">
              <span>01</span>
              <div>
                <h3 id="account-basic-title">基础信息</h3>
                <p>用于在矩阵任务中快速识别账号。</p>
              </div>
            </div>
            <div className="form-grid account-form-grid">
              <label>
                账号名称
                <input
                  value={draft.display_name}
                  onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
                  placeholder="例如：禾一斯品牌主号"
                />
              </label>
              <label>
                账号分组
                <input
                  value={draft.account_group}
                  onChange={(event) => setDraft({ ...draft, account_group: event.target.value })}
                  placeholder="例如：品牌号、门店号"
                />
              </label>
            </div>
          </section>

          <section className="account-form-section" aria-labelledby="account-position-title">
            <div className="account-form-section-heading">
              <span>02</span>
              <div>
                <h3 id="account-position-title">账号定位</h3>
                <p>AI 会按照这些信息生成匹配账号风格的内容。</p>
              </div>
            </div>
            <div className="form-grid account-form-grid">
              <label>
                账号领域
                <input
                  value={draft.profile.domain_name}
                  onChange={(event) => updateProfile("domain_name", event.target.value)}
                  placeholder="例如：女装穿搭"
                />
              </label>
              <label>
                账号人设
                <input
                  value={draft.profile.persona}
                  onChange={(event) => updateProfile("persona", event.target.value)}
                  placeholder="例如：专业但亲切的穿搭顾问"
                />
              </label>
              <label>
                目标人群
                <input
                  value={draft.profile.target_audience}
                  onChange={(event) => updateProfile("target_audience", event.target.value)}
                  placeholder="例如：25-35 岁通勤女性"
                />
              </label>
              <label>
                内容语气
                <input
                  value={draft.profile.tone}
                  onChange={(event) => updateProfile("tone", event.target.value)}
                  placeholder="例如：自然真诚、减少营销话术"
                />
              </label>
              <label className="wide-field">
                内容风格
                <textarea
                  rows={4}
                  value={draft.profile.content_style}
                  onChange={(event) => updateProfile("content_style", event.target.value)}
                  placeholder="填写常用内容结构、表达方式和需要突出的特点"
                />
              </label>
            </div>
          </section>

          <section className="account-form-section" aria-labelledby="account-publish-title">
            <div className="account-form-section-heading">
              <span>03</span>
              <div>
                <h3 id="account-publish-title">发布策略</h3>
                <p>限制单账号发布频率，降低连续操作风险。</p>
              </div>
            </div>
            <div className="form-grid account-form-grid">
              <label>
                每日发布上限
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={draft.daily_limit}
                  onChange={(event) => setDraft({ ...draft, daily_limit: Number(event.target.value) })}
                />
              </label>
              <label>
                最小发布间隔（分钟）
                <input
                  type="number"
                  min={30}
                  max={1440}
                  value={draft.min_interval_minutes}
                  onChange={(event) => setDraft({ ...draft, min_interval_minutes: Number(event.target.value) })}
                />
              </label>
            </div>
          </section>

          <div className="primary-row account-create-actions">
            <button className="primary-button" type="submit" disabled={saving}>
              {saving
                ? <Loader2 size={18} className="spin" aria-hidden="true" />
                : editingAccountId
                  ? <Pencil size={18} aria-hidden="true" />
                  : <Plus size={18} aria-hidden="true" />}
              {editingAccountId ? "保存修改" : "保存账号"}
            </button>
            <button className="secondary-button" type="button" onClick={closeAccountForm}>
              取消
            </button>
          </div>
        </form>
      ) : null}

      <section className="panel account-management-panel">
        <div className="panel-title">
          <h2>
            <UsersRound size={19} aria-hidden="true" />
            账号列表
          </h2>
          <button className="icon-button" type="button" title="刷新账号" onClick={() => void loadAccounts()}>
            <RefreshCw size={17} aria-hidden="true" />
          </button>
        </div>

        {loading ? (
          <div className="empty-state-row">
            <Loader2 size={20} className="spin" aria-hidden="true" />
            正在加载账号
          </div>
        ) : accounts.length === 0 ? (
          <div className="empty-state-row">暂无小红书账号，请先新增账号资料。</div>
        ) : (
          <div className="account-table-wrap">
            <table className="data-table account-table">
              <thead>
                <tr>
                  <th>账号</th>
                  <th>分组</th>
                  <th>账号定位</th>
                  <th>发布频率</th>
                  <th>登录状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => {
                  const status = accountStatus(account);
                  const checking = checkingAccountId === account.id;
                  return (
                    <tr key={account.id}>
                      <td>
                        <strong>{account.display_name}</strong>
                        <span>编号 #{account.id}</span>
                      </td>
                      <td>{account.account_group || "未分组"}</td>
                      <td>
                        <strong>{account.profile.domain_name || "待完善"}</strong>
                        <span>{account.profile.persona || "尚未填写账号人设"}</span>
                      </td>
                      <td>每日 {account.daily_limit} 篇，间隔 {account.min_interval_minutes} 分钟</td>
                      <td>
                        <span className={`status-pill ${status.className}`}>{status.label}</span>
                      </td>
                      <td>
                        <div className="account-login-actions">
                          <button
                            className="ghost-button compact-action-button"
                            type="button"
                            aria-label={`编辑 ${account.display_name}`}
                            onClick={() => openEditForm(account)}
                          >
                            <Pencil size={16} aria-hidden="true" />
                            编辑
                          </button>
                          <button
                            className="secondary-button compact-action-button"
                            type="button"
                            onClick={() => void startLogin(account)}
                          >
                            <QrCode size={16} aria-hidden="true" />
                            {account.login_state_ready ? "重新登录" : "扫码登录"}
                          </button>
                          <button
                            className="ghost-button compact-action-button"
                            type="button"
                            disabled={!account.login_state_ready || checking}
                            onClick={() => void checkLogin(account)}
                          >
                            {checking ? (
                              <Loader2 size={16} className="spin" aria-hidden="true" />
                            ) : (
                              <ShieldCheck size={16} aria-hidden="true" />
                            )}
                            检测状态
                          </button>
                          <button
                            className="quiet-danger compact-action-button"
                            type="button"
                            aria-label={`删除 ${account.display_name}`}
                            disabled={deletingAccountId === account.id}
                            onClick={() => void deleteAccount(account)}
                          >
                            {deletingAccountId === account.id
                              ? <Loader2 size={16} className="spin" aria-hidden="true" />
                              : <Trash2 size={16} aria-hidden="true" />}
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {loginAccount ? (
        <div className="dialog-backdrop" role="presentation" onMouseDown={closeLoginDialog}>
          <section
            className="dialog-panel xhs-login-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="xhs-login-dialog-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="dialog-header">
              <div>
                <span className="section-eyebrow">账号授权</span>
                <h2 id="xhs-login-dialog-title">扫码登录小红书</h2>
                <p>{loginAccount.display_name}</p>
              </div>
              <button className="icon-button" type="button" title="关闭" onClick={closeLoginDialog}>
                <X size={18} aria-hidden="true" />
              </button>
            </header>

            <div className="xhs-login-content">
              {loginLoading || !loginSession || loginSession.status === "starting" ? (
                <div className="xhs-login-state">
                  <Loader2 size={34} className="spin" aria-hidden="true" />
                  <strong>正在启动安全登录窗口</strong>
                  <span>二维码生成后会自动显示在这里。</span>
                </div>
              ) : loginSession.status === "awaiting_scan" ? (
                <div className="xhs-login-state">
                  {loginSession.qrcode_image_data ? (
                    <img
                      className="xhs-login-qr"
                      src={loginSession.qrcode_image_data}
                      alt={`${loginAccount.display_name} 小红书登录二维码`}
                    />
                  ) : (
                    <Loader2 size={34} className="spin" aria-hidden="true" />
                  )}
                  <strong>请使用小红书 App 扫码</strong>
                  <span>{loginSession.message || "二维码有效期约 5 分钟，请在手机端确认登录。"}</span>
                </div>
              ) : loginSession.status === "success" ? (
                <div className="xhs-login-state success">
                  <CheckCircle2 size={48} aria-hidden="true" />
                  <strong>账号登录成功</strong>
                  <span>登录状态已安全保存，可用于后续定时发布。</span>
                </div>
              ) : (
                <div className="xhs-login-state failed">
                  <AlertCircle size={48} aria-hidden="true" />
                  <strong>{loginSession.status === "timeout" ? "二维码已过期" : "扫码登录未完成"}</strong>
                  <span>{loginSession.message || "请重新生成二维码后再试。"}</span>
                  <button className="primary-button" type="button" onClick={() => void startLogin(loginAccount)}>
                    <LogIn size={17} aria-hidden="true" />
                    重新生成二维码
                  </button>
                </div>
              )}
            </div>

            <footer className="dialog-actions">
              <button className="secondary-button" type="button" onClick={closeLoginDialog}>
                关闭
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
