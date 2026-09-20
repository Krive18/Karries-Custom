import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Building2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Eye,
  RefreshCw,
  RotateCcw,
  Search,
  Users,
  X
} from "lucide-react";

import { developerApi } from "../api/developerClient";
import type { DeveloperAuditEntry } from "../types";


type AuditFilters = {
  action: string;
  targetType: string;
  operatorId: string;
  tenantId: string;
  keyword: string;
  startDate: string;
  endDate: string;
};

const EMPTY_FILTERS: AuditFilters = {
  action: "",
  targetType: "",
  operatorId: "",
  tenantId: "",
  keyword: "",
  startDate: "",
  endDate: ""
};

const PAGE_SIZE = 20;

const ACTION_LABELS: Record<string, string> = {
  "developer.account.create": "创建内部账号",
  "developer.account.password_reset": "重置账号密码",
  "developer.account.status_update": "更新账号状态",
  "developer.alert.acknowledge": "确认告警",
  "developer.alert.resolve": "解决告警",
  "developer.billing.adjust": "调整算力",
  "developer.customer_account.status_update": "更新客户账号状态",
  "developer.membership.approve": "审核通过会员",
  "developer.membership.reject": "驳回会员申请",
  "developer.task.cancel": "取消任务",
  "developer.task.retry": "重试任务",
  "developer.user_creation.approve": "通过新增用户",
  "developer.user_creation.reject": "驳回新增用户",
  video_job_claimed: "领取视频制作任务",
  video_delivery_uploaded: "上传视频交付资源",
  video_delivery_replaced: "替换视频交付资源",
  view_viral_analysis_job: "查看爆款解析任务",
  "billing.recharge_order_create": "创建算力充值订单",
  "billing.recharge_order_review": "审核算力充值订单",
  "billing.membership_order_create": "创建会员申请"
};

const TARGET_LABELS: Record<string, string> = {
  app_user: "账号",
  platform_alert: "平台告警",
  recharge_order: "充值订单",
  membership_upgrade_order: "会员订单",
  user_creation_request: "用户申请",
  video_edit_job: "视频制作任务",
  viral_analysis_job: "爆款解析任务"
};

const formatTime = (value: number) => new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false
}).format(new Date(value * 1000));

const getDayBoundary = (date: string, endOfDay = false) => {
  if (!date) return 0;
  const suffix = endOfDay ? "T23:59:59" : "T00:00:00";
  return Math.floor(new Date(`${date}${suffix}`).getTime() / 1000);
};

const buildAuditParams = (filters: AuditFilters, page: number) => {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(PAGE_SIZE)
  });
  const trimmed = {
    action: filters.action.trim(),
    target_type: filters.targetType.trim(),
    operator_id: filters.operatorId.trim(),
    tenant_id: filters.tenantId.trim(),
    keyword: filters.keyword.trim()
  };
  Object.entries(trimmed).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const startTime = getDayBoundary(filters.startDate);
  const endTime = getDayBoundary(filters.endDate, true);
  if (startTime) params.set("start_time", String(startTime));
  if (endTime) params.set("end_time", String(endTime));
  return params;
};

const getDetailSummary = (entry: DeveloperAuditEntry) => {
  const detail = entry.detail ?? {};
  for (const key of ["reason", "review_note", "message", "remark"]) {
    const value = detail[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return `记录 #${entry.id}`;
};

const renderDetailValue = (value: unknown) => {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return JSON.stringify(value, null, 2);
};


export function DeveloperAuditPage() {
  const [items, setItems] = useState<DeveloperAuditEntry[]>([]);
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<DeveloperAuditEntry | null>(null);

  const load = useCallback(async (
    requestedFilters: AuditFilters,
    requestedPage: number
  ) => {
    setLoading(true);
    setMessage("");
    try {
      const result = await developerApi.listPlatformAuditLogs(
        buildAuditParams(requestedFilters, requestedPage)
      );
      setItems(result.items);
      setTotal(result.total);
      setPage(result.page);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "审计日志加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(EMPTY_FILTERS, 1);
  }, [load]);

  useEffect(() => {
    if (!selectedEntry) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedEntry(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [selectedEntry]);

  const metrics = useMemo(() => ({
    pageRecords: items.length,
    tenantCount: new Set(items.map((item) => item.tenant_id)).size,
    operatorCount: new Set(items.map((item) => item.admin_user_id)).size
  }), [items]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const updateFilter = (key: keyof AuditFilters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const applyFilters = () => {
    if (
      filters.startDate
      && filters.endDate
      && filters.startDate > filters.endDate
    ) {
      setMessage("开始日期不能晚于结束日期");
      return;
    }
    const nextFilters = { ...filters };
    setAppliedFilters(nextFilters);
    void load(nextFilters, 1);
  };

  const resetFilters = () => {
    setFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    void load(EMPTY_FILTERS, 1);
  };

  const goToPage = (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages || nextPage === page) return;
    void load(appliedFilters, nextPage);
  };

  return (
    <section className="developer-page developer-ops-page developer-audit-workbench">
      <header className="developer-page-header">
        <div>
          <span className="developer-page-eyebrow">平台安全 / 操作追踪</span>
          <h1>审计日志</h1>
          <p>查询内部人员对任务、告警、账号和算力执行的真实操作，敏感字段由服务端统一脱敏。</p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => void load(appliedFilters, page)}
          disabled={loading}
        >
          <RefreshCw size={17} aria-hidden="true" />
          刷新数据
        </button>
      </header>

      <section className="developer-audit-metrics" aria-label="审计查询指标">
        <article>
          <span><Activity size={19} aria-hidden="true" /></span>
          <div><small>查询结果</small><strong>{total}</strong><p>符合当前筛选条件</p></div>
        </article>
        <article>
          <span><CalendarDays size={19} aria-hidden="true" /></span>
          <div><small>当前页记录</small><strong>{metrics.pageRecords}</strong><p>第 {page} / {totalPages} 页</p></div>
        </article>
        <article>
          <span><Building2 size={19} aria-hidden="true" /></span>
          <div><small>涉及团队</small><strong>{metrics.tenantCount}</strong><p>当前页真实去重</p></div>
        </article>
        <article>
          <span><Users size={19} aria-hidden="true" /></span>
          <div><small>操作人员</small><strong>{metrics.operatorCount}</strong><p>当前页真实去重</p></div>
        </article>
      </section>

      <section className="developer-audit-filter-panel" aria-label="审计筛选">
        <div className="developer-audit-filter-grid">
          <label>
            <span>开始日期</span>
            <input
              type="date"
              value={filters.startDate}
              onChange={(event) => updateFilter("startDate", event.target.value)}
            />
          </label>
          <label>
            <span>结束日期</span>
            <input
              type="date"
              value={filters.endDate}
              onChange={(event) => updateFilter("endDate", event.target.value)}
            />
          </label>
          <label>
            <span>操作人 ID</span>
            <input
              inputMode="numeric"
              value={filters.operatorId}
              onChange={(event) => updateFilter("operatorId", event.target.value)}
              placeholder="全部操作人"
            />
          </label>
          <label>
            <span>团队 ID</span>
            <input
              inputMode="numeric"
              value={filters.tenantId}
              onChange={(event) => updateFilter("tenantId", event.target.value)}
              placeholder="全部团队"
            />
          </label>
          <label>
            <span>动作</span>
            <input
              value={filters.action}
              onChange={(event) => updateFilter("action", event.target.value)}
              placeholder="例如 developer.alert.resolve"
            />
          </label>
          <label>
            <span>目标类型</span>
            <input
              value={filters.targetType}
              onChange={(event) => updateFilter("targetType", event.target.value)}
              placeholder="例如 app_user"
            />
          </label>
          <label className="developer-audit-keyword-field">
            <span>关键词</span>
            <input
              value={filters.keyword}
              onChange={(event) => updateFilter("keyword", event.target.value)}
              placeholder="搜索动作、目标或操作人"
              onKeyDown={(event) => {
                if (event.key === "Enter") applyFilters();
              }}
            />
          </label>
          <div className="developer-audit-filter-actions">
            <button className="secondary-button" type="button" onClick={resetFilters}>
              <RotateCcw size={16} aria-hidden="true" />
              重置
            </button>
            <button className="primary-button compact" type="button" onClick={applyFilters}>
              <Search size={16} aria-hidden="true" />
              查询
            </button>
          </div>
        </div>
      </section>

      {message ? <div className="form-message" role="status">{message}</div> : null}

      <section className="developer-ops-table-panel developer-audit-table-panel">
        <div className="developer-panel-heading">
          <div>
            <span>01</span>
            <h2>操作记录</h2>
          </div>
          <small>共 {total} 条</small>
        </div>
        <div className="developer-ops-table-wrap">
          <table className="developer-ops-table developer-audit-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>操作人</th>
                <th>动作</th>
                <th>目标</th>
                <th>团队</th>
                <th>操作摘要</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => (
                <tr key={entry.id}>
                  <td>{formatTime(entry.created_at)}</td>
                  <td>
                    <strong>{entry.operator_name || entry.operator_login_name}</strong>
                    <small>{entry.operator_login_name}</small>
                  </td>
                  <td>
                    <strong>{ACTION_LABELS[entry.action] || entry.action}</strong>
                    <small>{entry.action}</small>
                  </td>
                  <td>
                    {TARGET_LABELS[entry.target_type] || entry.target_type}
                    <small>#{entry.target_id}</small>
                  </td>
                  <td>{entry.tenant_id || "平台"}</td>
                  <td className="developer-audit-summary">{getDetailSummary(entry)}</td>
                  <td>
                    <button
                      className="table-action compact"
                      type="button"
                      aria-label="查看详情"
                      onClick={() => setSelectedEntry(entry)}
                    >
                      <Eye size={15} aria-hidden="true" />
                      查看
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && !items.length ? (
                <tr>
                  <td colSpan={7} className="developer-ops-empty">
                    暂无符合条件的审计记录
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <footer className="developer-audit-pagination">
          <span>第 {page} 页，共 {totalPages} 页</span>
          <div>
            <button
              type="button"
              aria-label="上一页"
              disabled={page <= 1 || loading}
              onClick={() => goToPage(page - 1)}
            >
              <ChevronLeft size={17} aria-hidden="true" />
            </button>
            <strong>{page}</strong>
            <button
              type="button"
              aria-label="下一页"
              disabled={page >= totalPages || loading}
              onClick={() => goToPage(page + 1)}
            >
              <ChevronRight size={17} aria-hidden="true" />
            </button>
          </div>
        </footer>
      </section>

      {selectedEntry ? (
        <div
          className="developer-audit-drawer-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelectedEntry(null);
          }}
        >
          <aside
            className="developer-audit-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="audit-drawer-title"
          >
            <header>
              <div>
                <span>审计记录 #{selectedEntry.id}</span>
                <h2 id="audit-drawer-title">审计记录详情</h2>
              </div>
              <button
                type="button"
                aria-label="关闭审计详情"
                onClick={() => setSelectedEntry(null)}
              >
                <X size={19} aria-hidden="true" />
              </button>
            </header>
            <dl className="developer-audit-meta">
              <div><dt>操作时间</dt><dd>{formatTime(selectedEntry.created_at)}</dd></div>
              <div><dt>操作人员</dt><dd>{selectedEntry.operator_name || selectedEntry.operator_login_name}</dd></div>
              <div><dt>登录账号</dt><dd>{selectedEntry.operator_login_name}</dd></div>
              <div><dt>团队 ID</dt><dd>{selectedEntry.tenant_id || "平台"}</dd></div>
              <div>
                <dt>动作</dt>
                <dd>{ACTION_LABELS[selectedEntry.action] || selectedEntry.action}</dd>
              </div>
              <div>
                <dt>目标</dt>
                <dd>{TARGET_LABELS[selectedEntry.target_type] || selectedEntry.target_type} #{selectedEntry.target_id}</dd>
              </div>
            </dl>
            <section className="developer-audit-detail-list">
              <h3>操作详情</h3>
              {Object.entries(selectedEntry.detail ?? {}).map(([key, value]) => (
                <div key={key}>
                  <span>{key}</span>
                  <pre>{renderDetailValue(value)}</pre>
                </div>
              ))}
              {!Object.keys(selectedEntry.detail ?? {}).length ? (
                <p>本条记录没有附加详情。</p>
              ) : null}
            </section>
            <p className="developer-audit-security-note">
              API Key、令牌和密码等敏感信息由服务端脱敏后返回。
            </p>
          </aside>
        </div>
      ) : null}
    </section>
  );
}
