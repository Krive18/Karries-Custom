import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  CalendarClock,
  CheckCircle2,
  CircleX,
  RefreshCw,
  RotateCcw,
  Search
} from "lucide-react";

import { managerApi } from "../api/managerClient";
import type {
  AdminEmployeeView,
  AdminPublishPlan,
  AdminPublishPlanDetail,
  MatrixPlanItemStatus,
  MatrixPlanStatus
} from "../types";


const planStatus: Record<MatrixPlanStatus, string> = {
  1: "草稿", 2: "待确认", 3: "待提交", 4: "执行中",
  5: "已完成", 6: "存在异常", 7: "已取消"
};
const itemStatus: Record<MatrixPlanItemStatus, string> = {
  1: "待确认", 2: "待发布", 3: "提交中", 4: "已提交",
  5: "发布失败", 6: "人工接管", 7: "已取消"
};

function formatTime(timestamp: number) {
  if (!timestamp) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false
  }).format(new Date(timestamp * 1000));
}


export function ManagerPublishingPage() {
  const [plans, setPlans] = useState<AdminPublishPlan[]>([]);
  const [selected, setSelected] = useState<AdminPublishPlanDetail | null>(null);
  const [employees, setEmployees] = useState<AdminEmployeeView[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [status, setStatus] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isActioning, setIsActioning] = useState(false);

  const loadPlans = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const params = new URLSearchParams({ page_size: "100" });
      if (employeeId) params.set("employee_id", employeeId);
      if (status) params.set("status", status);
      if (keyword) params.set("keyword", keyword);
      const result = await managerApi.listManagedPublishPlans(params);
      setPlans(result.items);
      setMessage("");
      setSelected((current) => (
        current && !result.items.some((item) => item.id === current.id) ? null : current
      ));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布运营数据加载失败");
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [employeeId, keyword, status]);

  useEffect(() => {
    void managerApi.listEmployees(new URLSearchParams({ page_size: "100", status: "1" }))
      .then((result) => setEmployees(result.items))
      .catch(() => setEmployees([]));
  }, []);

  useEffect(() => {
    void loadPlans();
  }, [loadPlans]);

  useEffect(() => {
    const selectedPlanId = selected?.id;
    const timer = window.setInterval(() => {
      void loadPlans(true);
      if (selectedPlanId) {
        void managerApi.getManagedPublishPlan(selectedPlanId)
          .then(setSelected)
          .catch(() => undefined);
      }
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [loadPlans, selected?.id]);

  const openPlan = async (planId: number) => {
    try {
      setSelected(await managerApi.getManagedPublishPlan(planId));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "计划详情加载失败");
    }
  };

  const runAction = async (action: "cancel" | "retry") => {
    if (!selected) return;
    setIsActioning(true);
    try {
      if (action === "cancel") await managerApi.cancelManagedPublishPlan(selected.id);
      else await managerApi.retryManagedPublishPlan(selected.id);
      setSelected(await managerApi.getManagedPublishPlan(selected.id));
      await loadPlans();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败");
    } finally {
      setIsActioning(false);
    }
  };

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setKeyword(keywordInput.trim());
  };

  return (
    <section className="manager-operations-page">
      <header className="manager-page-header">
        <div><h1>发布运营中心</h1><p>跟踪全员定时发布计划，集中处理失败和过期任务</p></div>
        <button className="secondary-button" type="button" onClick={() => void loadPlans()}>
          <RefreshCw size={16} className={isLoading ? "spin" : ""} />刷新计划
        </button>
      </header>

      <form className="manager-operation-filters" onSubmit={submitSearch}>
        <label>所属员工
          <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}>
            <option value="">全部员工</option>
            {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.nickname}</option>)}
          </select>
        </label>
        <label>计划状态
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">全部状态</option>
            {Object.entries(planStatus).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="operation-keyword">搜索计划
          <span><Search size={16} /><input value={keywordInput} onChange={(event) => setKeywordInput(event.target.value)} placeholder="计划名称或员工" /></span>
        </label>
        <button className="primary-button" type="submit">查询</button>
      </form>

      {message ? <div className="form-message">{message}</div> : null}

      <div className="publish-operations-workspace">
        <section className="panel manager-publish-plan-list">
          <header><h2>发布计划</h2><span>{plans.length} 个</span></header>
          <div>
            {plans.map((plan) => (
              <button key={plan.id} className={selected?.id === plan.id ? "manager-publish-plan-row active" : "manager-publish-plan-row"} type="button" onClick={() => void openPlan(plan.id)}>
                <span className={`plan-status status-${plan.status}`}>{planStatus[plan.status]}</span>
                <strong>{plan.plan_name}</strong>
                <small>{plan.employee_name} · {plan.item_count} 条任务</small>
                <footer><span>{formatTime(plan.schedule_start_time)}</span><b>{plan.submitted_count}/{plan.item_count}</b></footer>
              </button>
            ))}
            {!isLoading && !plans.length ? <div className="operation-empty">暂无发布计划</div> : null}
          </div>
        </section>

        <section className="panel manager-publish-plan-detail">
          {selected ? (
            <>
              <header>
                <div><span>{planStatus[selected.status]}</span><h2>{selected.plan_name}</h2><p>{selected.employee_name} · {formatTime(selected.schedule_start_time)} 至 {formatTime(selected.schedule_end_time)}</p></div>
                <div className="manager-publish-plan-actions">
                  {selected.status === 6 ? <button type="button" disabled={isActioning} onClick={() => void runAction("retry")}><RotateCcw size={16} />重试失败任务</button> : null}
                  {[1, 2, 3].includes(selected.status) ? <button className="danger" type="button" disabled={isActioning} onClick={() => void runAction("cancel")}><CircleX size={16} />取消计划</button> : null}
                </div>
              </header>
              <div className="manager-publish-detail-summary">
                <span><CalendarClock size={17} /><b>{selected.items.length}</b>任务</span>
                <span><CheckCircle2 size={17} /><b>{selected.items.filter((item) => item.status === 4).length}</b>已提交</span>
                <span><CircleX size={17} /><b>{selected.items.filter((item) => item.status === 5 || item.status === 6).length}</b>异常</span>
              </div>
              <div className="manager-publish-item-list">
                {selected.items.map((item) => (
                  <article key={item.id}>
                    <div>
                      <strong>{item.title || "未命名发布内容"}</strong>
                      <span>{item.account_name} · {formatTime(item.scheduled_time)}</span>
                      {item.attempt_count > 0 ? <small>执行尝试 {item.attempt_count}/{item.max_attempts}</small> : null}
                    </div>
                    <span className={`item-status item-status-${item.status}`}>{itemStatus[item.status]}</span>
                    {item.status === 2 && item.next_retry_time > 0 ? (
                      <p>将在 {formatTime(item.next_retry_time)} 自动重试{item.last_error ? `：${item.last_error}` : ""}</p>
                    ) : item.status === 4 && item.submitted_time > 0 ? (
                      <p>已于 {formatTime(item.submitted_time)} 提交至小红书</p>
                    ) : item.last_error ? <p>{item.last_error}</p> : null}
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="manager-publish-detail-empty"><CalendarClock size={34} /><strong>选择一个发布计划</strong><span>查看每条内容的定时时间、账号和执行结果</span></div>
          )}
        </section>
      </div>
    </section>
  );
}
