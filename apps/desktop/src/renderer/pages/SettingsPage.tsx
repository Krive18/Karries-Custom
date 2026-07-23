import { FormEvent, useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, UsersRound } from "lucide-react";

import { api } from "../api/client";
import type {
  XHSAccountCreate,
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


export function SettingsPage() {
  const [accounts, setAccounts] = useState<XHSAccountView[]>([]);
  const [draft, setDraft] = useState<XHSAccountCreate>(emptyDraft);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function loadAccounts() {
    setLoading(true);
    setMessage("");
    try {
      const result = await api.listXHSAccounts();
      setAccounts(Array.isArray(result) ? result : []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAccounts();
  }, []);

  function updateProfile(field: keyof XHSAccountProfile, value: string | number) {
    setDraft((current) => ({
      ...current,
      profile: { ...current.profile, [field]: value }
    }));
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
      const account = await api.createXHSAccount({
        ...draft,
        display_name: draft.display_name.trim(),
        account_group: draft.account_group.trim()
      });
      setAccounts((current) => [account, ...current]);
      setDraft(emptyDraft);
      setShowForm(false);
      setMessage("账号资料已保存，可继续完善扫码登录状态");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-heading account-heading">
        <div>
          <h1>小红书账号管理</h1>
          <p>统一维护矩阵账号、账号定位和发布频率，智能创作会按账号定位生成内容。</p>
        </div>
        <button className="primary-button" type="button" onClick={() => setShowForm((value) => !value)}>
          <Plus size={18} aria-hidden="true" />
          新增账号
        </button>
      </div>

      {message ? <div className="form-message">{message}</div> : null}

      {showForm ? (
        <form className="panel account-create-panel" onSubmit={handleSubmit}>
          <div className="panel-title">
            <h2>新增矩阵账号</h2>
            <span className="key-status">账号资料</span>
          </div>
          <div className="form-grid">
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
                placeholder="例如：自然真诚、少营销话术"
              />
            </label>
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
            <label className="wide-field">
              内容风格
              <textarea
                rows={3}
                value={draft.profile.content_style}
                onChange={(event) => updateProfile("content_style", event.target.value)}
                placeholder="填写常用内容结构、表达方式和希望突出的特点"
              />
            </label>
          </div>
          <div className="primary-row">
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? <Loader2 size={18} className="spin" aria-hidden="true" /> : <Plus size={18} aria-hidden="true" />}
              保存账号
            </button>
            <button className="secondary-button" type="button" onClick={() => setShowForm(false)}>
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
          <div className="empty-state-row">暂未添加小红书账号，请先新增账号资料。</div>
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
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => (
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
                      <span className={account.login_state_path ? "status-pill success" : "status-pill pending"}>
                        {account.login_state_path ? "已保存登录状态" : "待扫码登录"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
