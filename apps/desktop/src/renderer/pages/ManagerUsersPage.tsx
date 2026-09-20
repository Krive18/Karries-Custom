import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  Eye,
  KeyRound,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRoundCheck,
  UserRoundX,
  UsersRound,
  X
} from "lucide-react";

import { managerApi } from "../api/managerClient";
import type {
  AdminEmployeeCreate,
  AdminEmployeeDetail,
  AdminEmployeeSummary,
  AdminEmployeeUpdate,
  AdminEmployeeView
} from "../types";


const emptyCreateForm: AdminEmployeeCreate = {
  login_name: "",
  nickname: "",
  password: "",
  status: 1
};

const emptySummary: AdminEmployeeSummary = {
  total: 0,
  active: 0,
  disabled: 0,
  recent_login: 0
};

function formatTime(timestamp: number) {
  if (!timestamp) return "尚未登录";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


export function ManagerUsersPage() {
  const [employees, setEmployees] = useState<AdminEmployeeView[]>([]);
  const [summary, setSummary] = useState(emptySummary);
  const [searchInput, setSearchInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState<"" | "1" | "2">("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [editTarget, setEditTarget] = useState<AdminEmployeeView | null>(null);
  const [editForm, setEditForm] = useState<AdminEmployeeUpdate>({
    login_name: "",
    nickname: ""
  });
  const [detailTarget, setDetailTarget] = useState<AdminEmployeeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [resetTarget, setResetTarget] = useState<AdminEmployeeView | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [statusTarget, setStatusTarget] = useState<AdminEmployeeView | null>(null);

  const loadEmployees = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({
        page: "1",
        page_size: "100"
      });
      if (keyword) params.set("keyword", keyword);
      if (status) params.set("status", status);
      const [result, employeeSummary] = await Promise.all([
        managerApi.listEmployees(params),
        managerApi.getEmployeeSummary()
      ]);
      setEmployees(result.items);
      setSummary(employeeSummary);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "员工列表加载失败");
    } finally {
      setIsLoading(false);
    }
  }, [keyword, status]);

  useEffect(() => {
    void loadEmployees();
  }, [loadEmployees]);

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setKeyword(searchInput.trim());
  };

  const submitCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSaving) return;
    setIsSaving(true);
    setMessage("");
    try {
      const result = await managerApi.createEmployee({
        ...createForm,
        login_name: createForm.login_name.trim(),
        nickname: createForm.nickname.trim()
      });
      setCreateForm(emptyCreateForm);
      setCreateOpen(false);
      await loadEmployees();
      setMessage(
        "approval_required" in result && result.approval_required
          ? "已超过 2 个员工账号额度，新增申请已提交开发者审核。审核通过前不会创建账号或发放会员算力。"
          : "员工账号已创建，可直接登录用户端。"
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "员工创建失败");
    } finally {
      setIsSaving(false);
    }
  };

  const openEdit = (employee: AdminEmployeeView) => {
    setEditTarget(employee);
    setEditForm({
      login_name: employee.login_name,
      nickname: employee.nickname
    });
  };

  const submitEdit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editTarget || isSaving) return;
    setIsSaving(true);
    setMessage("");
    try {
      await managerApi.updateEmployee(editTarget.id, {
        login_name: editForm.login_name.trim(),
        nickname: editForm.nickname.trim()
      });
      setEditTarget(null);
      await loadEmployees();
      setMessage("员工资料已更新。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "员工资料更新失败");
    } finally {
      setIsSaving(false);
    }
  };

  const openDetail = async (employee: AdminEmployeeView) => {
    setDetailLoading(true);
    setMessage("");
    try {
      setDetailTarget(await managerApi.getEmployee(employee.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "员工详情加载失败");
    } finally {
      setDetailLoading(false);
    }
  };

  const submitPasswordReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!resetTarget || resetPassword.length < 8 || isSaving) return;
    setIsSaving(true);
    setMessage("");
    try {
      await managerApi.resetEmployeePassword(
        resetTarget.id,
        { password: resetPassword }
      );
      const employeeName = resetTarget.nickname;
      setResetTarget(null);
      setResetPassword("");
      setMessage(`${employeeName} 的密码已重置，原登录已强制退出。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "密码重置失败");
    } finally {
      setIsSaving(false);
    }
  };

  const confirmStatusChange = async () => {
    if (!statusTarget || isSaving) return;
    setIsSaving(true);
    setMessage("");
    try {
      const nextStatus = statusTarget.status === 1 ? 2 : 1;
      await managerApi.updateEmployeeStatus(statusTarget.id, nextStatus);
      setStatusTarget(null);
      await loadEmployees();
      setMessage(
        nextStatus === 1
          ? "员工账号已启用，可重新登录用户端。"
          : "员工账号已停用，现有登录已强制退出。"
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "账号状态修改失败");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="page-stack manager-users-page">
      <div className="page-heading horizontal-heading manager-users-heading">
        <div>
          <h1>员工账号管理</h1>
          <p>由老板统一创建和维护员工的用户端登录账号。</p>
        </div>
        <button
          className="primary-button"
          type="button"
          onClick={() => setCreateOpen(true)}
        >
          <Plus size={17} aria-hidden="true" />
          新增员工
        </button>
      </div>

      {message ? (
        <div className="form-message" role="status">{message}</div>
      ) : null}

      <section className="employee-summary-grid" aria-label="员工账号概览">
        <div className="employee-summary-item">
          <UsersRound size={20} aria-hidden="true" />
          <span>员工总数</span>
          <strong>{summary.total}</strong>
        </div>
        <div className="employee-summary-item">
          <UserRoundCheck size={20} aria-hidden="true" />
          <span>正常使用</span>
          <strong>{summary.active}</strong>
        </div>
        <div className="employee-summary-item">
          <UserRoundX size={20} aria-hidden="true" />
          <span>已停用</span>
          <strong>{summary.disabled}</strong>
        </div>
        <div className="employee-summary-item">
          <Activity size={20} aria-hidden="true" />
          <span>近 7 天登录</span>
          <strong>{summary.recent_login}</strong>
        </div>
      </section>

      <form className="panel manager-user-toolbar" onSubmit={submitSearch}>
        <label className="manager-user-search">
          <span>搜索员工</span>
          <span className="input-with-icon">
            <Search size={16} aria-hidden="true" />
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="输入员工姓名或登录账号"
            />
          </span>
        </label>
        <label>
          <span>账号状态</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as typeof status)}
          >
            <option value="">全部状态</option>
            <option value="1">正常使用</option>
            <option value="2">已停用</option>
          </select>
        </label>
        <div className="manager-toolbar-actions">
          <button className="secondary-button" type="submit">
            <Search size={16} aria-hidden="true" />
            查询
          </button>
          <button
            className="icon-button"
            type="button"
            title="刷新员工列表"
            aria-label="刷新员工列表"
            onClick={() => void loadEmployees()}
          >
            <RefreshCw size={17} aria-hidden="true" />
          </button>
        </div>
      </form>

      <section className="panel manager-user-table-panel">
        <div className="panel-title">
          <h2>员工列表</h2>
          <span>当前显示 {employees.length} 人</span>
        </div>
        <div className="responsive-table">
          <table className="manager-user-table">
            <thead>
              <tr>
                <th>员工</th>
                <th>登录账号</th>
                <th>状态</th>
                <th>小红书账号</th>
                <th>发布计划</th>
                <th>算力余额</th>
                <th>最近登录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((employee) => (
                <tr key={employee.id}>
                  <td>
                    <strong>{employee.nickname}</strong>
                    <span>员工 ID {employee.id}</span>
                  </td>
                  <td>{employee.login_name}</td>
                  <td>
                    <span className={`employee-status status-${employee.status}`}>
                      {employee.status === 1 ? "正常使用" : "已停用"}
                    </span>
                  </td>
                  <td>{employee.xhs_account_count} 个</td>
                  <td>{employee.publish_plan_count} 个</td>
                  <td>{employee.wallet_balance}</td>
                  <td>{formatTime(employee.last_login_time)}</td>
                  <td>
                    <div className="table-actions employee-action-icons">
                      <button
                        className="table-action"
                        type="button"
                        title="查看详情"
                        aria-label={`查看 ${employee.nickname} 详情`}
                        disabled={detailLoading}
                        onClick={() => void openDetail(employee)}
                      >
                        <Eye size={16} aria-hidden="true" />
                      </button>
                      <button
                        className="table-action"
                        type="button"
                        title="编辑资料"
                        aria-label={`编辑 ${employee.nickname} 资料`}
                        onClick={() => openEdit(employee)}
                      >
                        <Pencil size={16} aria-hidden="true" />
                      </button>
                      <button
                        className="table-action"
                        type="button"
                        title="重置密码"
                        aria-label={`重置 ${employee.nickname} 密码`}
                        onClick={() => {
                          setResetTarget(employee);
                          setResetPassword("");
                        }}
                      >
                        <KeyRound size={16} aria-hidden="true" />
                      </button>
                      <button
                        className="table-action"
                        type="button"
                        title={employee.status === 1 ? "停用账号" : "启用账号"}
                        aria-label={`${employee.status === 1 ? "停用" : "启用"} ${employee.nickname}`}
                        onClick={() => setStatusTarget(employee)}
                      >
                        <Power size={16} aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {isLoading ? (
          <div className="table-state">正在加载员工账号...</div>
        ) : null}
        {!isLoading && employees.length === 0 ? (
          <div className="table-state">没有符合条件的员工账号</div>
        ) : null}
      </section>

      {createOpen ? (
        <div className="dialog-backdrop" role="presentation">
          <section
            className="dialog-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-employee-title"
          >
            <header className="dialog-header">
              <div>
                <h2 id="create-employee-title">新增员工账号</h2>
                <p>员工保存后即可使用账号和长期密码登录用户端。</p>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label="关闭新增员工"
                onClick={() => {
                  setCreateOpen(false);
                  setCreateForm(emptyCreateForm);
                }}
              >
                <X size={18} />
              </button>
            </header>
            <form className="dialog-form" onSubmit={submitCreate}>
              <label>
                <span>员工姓名</span>
                <input
                  value={createForm.nickname}
                  onChange={(event) => setCreateForm({
                    ...createForm,
                    nickname: event.target.value
                  })}
                  placeholder="例如：张小禾"
                  maxLength={100}
                  required
                />
              </label>
              <label>
                <span>登录账号</span>
                <input
                  value={createForm.login_name}
                  onChange={(event) => setCreateForm({
                    ...createForm,
                    login_name: event.target.value
                  })}
                  placeholder="至少 3 个字符"
                  minLength={3}
                  maxLength={100}
                  autoComplete="off"
                  required
                />
              </label>
              <label>
                <span>长期密码</span>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(event) => setCreateForm({
                    ...createForm,
                    password: event.target.value
                  })}
                  placeholder="至少 8 个字符"
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                  required
                />
              </label>
              <label>
                <span>初始状态</span>
                <select
                  value={createForm.status}
                  onChange={(event) => setCreateForm({
                    ...createForm,
                    status: Number(event.target.value) as 1 | 2
                  })}
                >
                  <option value={1}>正常使用，可立即登录</option>
                  <option value={2}>暂不启用</option>
                </select>
              </label>
              <div className="employee-role-note">
                <ShieldCheck size={18} aria-hidden="true" />
                <div>
                  <strong>固定为员工权限</strong>
                  <span>只能进入用户端，不具备老板管理权限。前 2 个员工可直接创建，第 3 个起需开发者审核。</span>
                </div>
              </div>
              <footer className="dialog-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setCreateOpen(false)}
                >
                  取消
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={isSaving}
                >
                  <Plus size={16} aria-hidden="true" />
                  {isSaving ? "正在创建..." : "创建员工"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}

      {editTarget ? (
        <div className="dialog-backdrop" role="presentation">
          <section
            className="dialog-panel dialog-panel-compact"
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-employee-title"
          >
            <header className="dialog-header">
              <div>
                <h2 id="edit-employee-title">编辑员工资料</h2>
                <p>修改姓名或用户端登录账号。</p>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label="关闭编辑员工"
                onClick={() => setEditTarget(null)}
              >
                <X size={18} />
              </button>
            </header>
            <form className="dialog-form" onSubmit={submitEdit}>
              <label>
                <span>员工姓名</span>
                <input
                  value={editForm.nickname}
                  onChange={(event) => setEditForm({
                    ...editForm,
                    nickname: event.target.value
                  })}
                  maxLength={100}
                  required
                />
              </label>
              <label>
                <span>登录账号</span>
                <input
                  value={editForm.login_name}
                  onChange={(event) => setEditForm({
                    ...editForm,
                    login_name: event.target.value
                  })}
                  minLength={3}
                  maxLength={100}
                  required
                />
              </label>
              <footer className="dialog-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setEditTarget(null)}
                >
                  取消
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={isSaving}
                >
                  <Pencil size={16} aria-hidden="true" />
                  保存修改
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}

      {detailTarget ? (
        <div className="dialog-backdrop" role="presentation">
          <section
            className="dialog-panel employee-detail-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="employee-detail-title"
          >
            <header className="dialog-header">
              <div>
                <h2 id="employee-detail-title">{detailTarget.nickname}</h2>
                <p>{detailTarget.login_name} · 员工 ID {detailTarget.id}</p>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label="关闭员工详情"
                onClick={() => setDetailTarget(null)}
              >
                <X size={18} />
              </button>
            </header>
            <div className="employee-detail-body">
              <div className="employee-detail-metrics">
                <div><span>小红书账号</span><strong>{detailTarget.xhs_account_count}</strong></div>
                <div><span>发布计划</span><strong>{detailTarget.publish_plan_count}</strong></div>
                <div><span>灵感对话</span><strong>{detailTarget.inspiration_session_count}</strong></div>
                <div><span>爆款解析</span><strong>{detailTarget.viral_analysis_count}</strong></div>
                <div><span>算力余额</span><strong>{detailTarget.wallet_balance}</strong></div>
              </div>
              <dl className="employee-detail-list">
                <div>
                  <dt>账号状态</dt>
                  <dd>{detailTarget.status === 1 ? "正常使用" : "已停用"}</dd>
                </div>
                <div>
                  <dt>最近登录</dt>
                  <dd>{formatTime(detailTarget.last_login_time)}</dd>
                </div>
                <div>
                  <dt>创建时间</dt>
                  <dd>{formatTime(detailTarget.create_time)}</dd>
                </div>
                <div>
                  <dt>权限范围</dt>
                  <dd>员工用户端</dd>
                </div>
              </dl>
            </div>
            <footer className="dialog-actions employee-detail-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setDetailTarget(null);
                  openEdit(detailTarget);
                }}
              >
                <Pencil size={16} aria-hidden="true" />
                编辑资料
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={() => setDetailTarget(null)}
              >
                完成
              </button>
            </footer>
          </section>
        </div>
      ) : null}

      {resetTarget ? (
        <div className="dialog-backdrop" role="presentation">
          <section
            className="dialog-panel dialog-panel-compact"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-password-title"
          >
            <header className="dialog-header">
              <div>
                <h2 id="reset-password-title">重置员工密码</h2>
                <p>{resetTarget.nickname} · {resetTarget.login_name}</p>
              </div>
            </header>
            <form className="dialog-form" onSubmit={submitPasswordReset}>
              <label>
                <span>新长期密码</span>
                <input
                  type="password"
                  value={resetPassword}
                  onChange={(event) => setResetPassword(event.target.value)}
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                  autoFocus
                  required
                />
              </label>
              <p className="dialog-security-note">
                保存后该员工在其他设备上的原登录会立即失效。
              </p>
              <footer className="dialog-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => {
                    setResetTarget(null);
                    setResetPassword("");
                  }}
                >
                  取消
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={isSaving || resetPassword.length < 8}
                >
                  <KeyRound size={16} aria-hidden="true" />
                  确认重置
                </button>
              </footer>
            </form>
          </section>
        </div>
      ) : null}

      {statusTarget ? (
        <div className="dialog-backdrop" role="presentation">
          <section
            className="dialog-panel dialog-panel-compact"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="status-confirm-title"
          >
            <header className="dialog-header">
              <div>
                <h2 id="status-confirm-title">
                  {statusTarget.status === 1 ? "停用员工账号" : "启用员工账号"}
                </h2>
                <p>
                  {statusTarget.status === 1
                    ? `停用后，${statusTarget.nickname} 会立即退出且无法登录用户端。`
                    : `启用后，${statusTarget.nickname} 可使用现有密码重新登录。`}
                </p>
              </div>
            </header>
            <footer className="dialog-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setStatusTarget(null)}
              >
                取消
              </button>
              <button
                className="primary-button"
                type="button"
                disabled={isSaving}
                onClick={() => void confirmStatusChange()}
              >
                <Power size={16} aria-hidden="true" />
                确认{statusTarget.status === 1 ? "停用" : "启用"}
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
