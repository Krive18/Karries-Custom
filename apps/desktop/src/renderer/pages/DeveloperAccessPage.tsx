import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";

import { developerApi } from "../api/developerClient";
import type { AuthUser, DeveloperAccount } from "../types";


type Props = { currentUser: AuthUser | null };
const formatTime = (value: number) => value
  ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value * 1000))
  : "从未登录";


export function DeveloperAccessPage({ currentUser }: Props) {
  const [items, setItems] = useState<DeveloperAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [loginName, setLoginName] = useState("");
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<DeveloperAccount["role"]>("developer_admin");
  const [selected, setSelected] = useState<DeveloperAccount | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setMessage("");
    try { setItems((await developerApi.listDeveloperAccounts(new URLSearchParams({ page_size: "100" }))).items); }
    catch (caught) { setMessage(caught instanceof Error ? caught.message : "内部账号加载失败"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const createAccount = async (event: FormEvent) => {
    event.preventDefault(); setLoading(true); setMessage("");
    try {
      await developerApi.createDeveloperAccount({ login_name: loginName.trim(), nickname: nickname.trim(), password, role });
      setLoginName(""); setNickname(""); setPassword(""); setShowCreate(false); await load(); setMessage("内部账号已创建");
    } catch (caught) { setMessage(caught instanceof Error ? caught.message : "账号创建失败"); setLoading(false); }
  };
  const resetPassword = async () => {
    if (!selected || newPassword.length < 8 || reason.trim().length < 3) { setMessage("新密码至少 8 位，操作原因至少 3 个字"); return; }
    setLoading(true);
    try { await developerApi.resetDeveloperAccountPassword(selected.id, newPassword, reason.trim()); setSelected(null); setNewPassword(""); setReason(""); await load(); setMessage("密码已重置，旧会话已失效"); }
    catch (caught) { setMessage(caught instanceof Error ? caught.message : "密码重置失败"); setLoading(false); }
  };
  const toggleStatus = async (account: DeveloperAccount) => {
    if (reason.trim().length < 3) { setSelected(account); setMessage("请先填写至少 3 个字的操作原因"); return; }
    setLoading(true);
    try { await developerApi.updateDeveloperAccountStatus(account.id, account.status === 1 ? 2 : 1, reason.trim()); setSelected(null); setReason(""); await load(); setMessage("账号状态已更新，旧会话已失效"); }
    catch (caught) { setMessage(caught instanceof Error ? caught.message : "状态更新失败"); setLoading(false); }
  };

  return <section className="developer-page developer-ops-page">
    <header className="developer-page-header"><div><h1>内部账号权限</h1><p>管理开发者端账号、角色、状态和凭据轮换；敏感信息不会出现在列表或日志中。</p></div><div className="developer-header-actions"><button className="secondary-button" type="button" onClick={() => void load()}><RefreshCw size={17} />刷新</button><button className="primary-button" type="button" onClick={() => setShowCreate((value) => !value)}><Plus size={17} />新建账号</button></div></header>
    {message ? <div className="form-message" role="status">{message}</div> : null}
    {showCreate ? <form className="developer-access-form" onSubmit={(event) => void createAccount(event)}><label>登录账号<input required minLength={3} maxLength={64} value={loginName} onChange={(event) => setLoginName(event.target.value)} /></label><label>显示名称<input required maxLength={100} value={nickname} onChange={(event) => setNickname(event.target.value)} /></label><label>初始密码<input required type="password" minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><label>角色<select value={role} onChange={(event) => setRole(event.target.value as DeveloperAccount["role"])}><option value="developer_admin">开发者管理员</option>{currentUser?.user_role === "platform_admin" ? <option value="platform_admin">平台管理员</option> : null}</select></label><button className="primary-button compact" type="submit" disabled={loading}>创建账号</button></form> : null}
    {selected ? <section className="developer-action-panel"><div><strong>管理账号：{selected.nickname || selected.login_name}</strong><span>不能操作当前登录账号，平台管理员也不能停用最后一个同级账号。</span></div><label>操作原因<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} /></label><label>新密码（仅重置密码时填写）<input type="password" minLength={8} maxLength={128} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label><div><button className="secondary-button compact" type="button" onClick={() => setSelected(null)}>返回</button><button className="table-action compact" type="button" onClick={() => void resetPassword()}>重置密码</button><button className="primary-button compact" type="button" onClick={() => void toggleStatus(selected)}>{selected.status === 1 ? "停用账号" : "启用账号"}</button></div></section> : null}
    <section className="developer-ops-table-panel"><div className="developer-panel-heading"><div><span>01</span><h2>内部账号</h2></div><small>{items.length} 个账号</small></div><div className="developer-ops-table-wrap"><table className="developer-ops-table"><thead><tr><th>账号</th><th>角色</th><th>状态</th><th>最近登录</th><th>操作</th></tr></thead><tbody>{items.map((account) => <tr key={account.id}><td><strong>{account.nickname || account.login_name}</strong><small>{account.login_name}</small></td><td>{account.role === "platform_admin" ? "平台管理员" : "开发者管理员"}</td><td><span className={`developer-status-pill ${account.status === 1 ? "completed" : "cancelled"}`}>{account.status === 1 ? "启用" : "停用"}</span></td><td>{formatTime(account.last_login_at)}</td><td><button className="table-action compact" type="button" disabled={account.id === currentUser?.id} onClick={() => { setSelected(account); setReason(""); setNewPassword(""); }}>管理</button></td></tr>)}{!loading && !items.length ? <tr><td colSpan={5} className="developer-ops-empty">暂无内部账号</td></tr> : null}</tbody></table></div></section>
  </section>;
}
