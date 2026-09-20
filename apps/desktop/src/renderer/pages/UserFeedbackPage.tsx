import { useCallback, useEffect, useState } from "react";
import {
  Bug,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Lightbulb,
  Loader2,
  MessageSquarePlus,
  RefreshCw,
  Sparkles
} from "lucide-react";

import { api } from "../api/client";
import type {
  UserFeedback,
  UserFeedbackCategory,
  UserFeedbackStatus
} from "../types";


const categories: Array<{
  key: UserFeedbackCategory;
  label: string;
  description: string;
  icon: typeof Bug;
}> = [
  { key: "bug", label: "问题反馈", description: "功能异常、页面错误或无法操作", icon: Bug },
  { key: "feature", label: "功能需求", description: "希望新增或增强的产品能力", icon: Lightbulb },
  { key: "experience", label: "体验建议", description: "流程、交互或视觉体验建议", icon: Sparkles },
  { key: "other", label: "其他", description: "其他需要开发团队关注的内容", icon: CircleHelp }
];

const statusLabels: Record<UserFeedbackStatus, string> = {
  pending: "待处理",
  in_progress: "处理中",
  completed: "已完成"
};

const statusFilters: Array<{
  key: "" | UserFeedbackStatus;
  label: string;
  icon: typeof MessageSquarePlus;
}> = [
  { key: "", label: "全部", icon: MessageSquarePlus },
  { key: "pending", label: "待处理", icon: Clock3 },
  { key: "in_progress", label: "处理中", icon: RefreshCw },
  { key: "completed", label: "已完成", icon: CheckCircle2 }
];

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString("zh-CN");
}

function explainError(error: unknown) {
  return error instanceof Error ? error.message : "请求未完成，请稍后重试。";
}


export function UserFeedbackPage() {
  const [items, setItems] = useState<UserFeedback[]>([]);
  const [category, setCategory] = useState<UserFeedbackCategory>("bug");
  const [status, setStatus] = useState<"" | UserFeedbackStatus>("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadFeedback = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({ page_size: "50" });
      if (status) params.set("status", status);
      const result = await api.listUserFeedback(params);
      setItems(result.items);
      setMessage("");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void loadFeedback();
  }, [loadFeedback]);

  async function submitFeedback() {
    const normalizedTitle = title.trim();
    const normalizedDescription = description.trim();
    if (normalizedTitle.length < 2 || normalizedDescription.length < 10) {
      setMessage("请填写清晰的反馈标题，并至少用 10 个字说明具体情况。");
      return;
    }
    setIsSubmitting(true);
    setMessage("");
    try {
      const created = await api.createUserFeedback({
        category,
        title: normalizedTitle,
        description: normalizedDescription
      });
      setItems((current) => [created, ...current]);
      setTitle("");
      setDescription("");
      setMessage("反馈已提交，我们会尽快处理。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="feedback-page">
      <header className="page-heading feedback-page-heading">
        <div>
          <span className="feedback-heading-icon"><MessageSquarePlus size={20} /></span>
          <div>
            <h1>需求反馈</h1>
            <p>告诉我们遇到的问题或期待的能力，处理进度会第一时间同步给你。</p>
          </div>
        </div>
        <button className="secondary-button" type="button" onClick={() => void loadFeedback()} disabled={isLoading}>
          <RefreshCw size={16} className={isLoading ? "spin" : ""} />刷新进度
        </button>
      </header>

      {message ? (
        <div className={message.startsWith("反馈已提交") ? "app-alert success feedback-success" : "app-alert"} role="status">
          {message}
        </div>
      ) : null}

      <div className="feedback-layout">
        <section className="panel feedback-compose-card">
          <div className="feedback-section-title">
            <span>01</span><div><h2>提交新反馈</h2><p>描述越具体，定位和处理越快</p></div>
          </div>
          <div className="feedback-category-grid" aria-label="反馈类型">
            {categories.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.key}
                  type="button"
                  className={category === item.key ? "active" : ""}
                  aria-pressed={category === item.key}
                  aria-label={item.label}
                  onClick={() => setCategory(item.key)}
                >
                  <Icon size={18} />
                  <span><strong>{item.label}</strong><small>{item.description}</small></span>
                </button>
              );
            })}
          </div>
          <label>
            反馈标题
            <input value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} placeholder="一句话说明你遇到的问题或想要的功能" />
          </label>
          <label>
            详细说明
            <textarea value={description} maxLength={5000} rows={8} onChange={(event) => setDescription(event.target.value)} placeholder="请说明发生场景、操作步骤和期待结果；若是新需求，可描述你希望解决的实际问题。" />
          </label>
          <div className="feedback-submit-row">
            <span>{description.length} / 5000</span>
            <button className="primary-button" type="button" disabled={isSubmitting} onClick={() => void submitFeedback()}>
              {isSubmitting ? <Loader2 size={17} className="spin" /> : <MessageSquarePlus size={17} />}
              提交反馈
            </button>
          </div>
        </section>

        <section className="panel feedback-history-card">
          <div className="feedback-history-head">
            <div><h2>我的反馈</h2><p>开发者回复和完成状态会显示在这里</p></div>
            <div className="feedback-status-tabs" role="tablist" aria-label="反馈状态筛选">
              {statusFilters.map((item) => {
                const Icon = item.icon;
                const isSelected = status === item.key;
                return (
                  <button
                    key={item.key || "all"}
                    type="button"
                    role="tab"
                    className={isSelected ? "active" : ""}
                    aria-selected={isSelected}
                    aria-controls="feedback-history-list"
                    onClick={() => setStatus(item.key)}
                  >
                    {isLoading && isSelected
                      ? <Loader2 size={14} className="spin" aria-hidden="true" />
                      : <Icon size={14} aria-hidden="true" />}
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="feedback-list" id="feedback-history-list" aria-busy={isLoading}>
            {isLoading && !items.length ? <div className="feedback-empty"><Loader2 className="spin" />正在读取反馈...</div> : null}
            {!isLoading && !items.length ? <div className="feedback-empty"><MessageSquarePlus /><strong>还没有反馈记录</strong><span>提交后可在这里跟踪处理进度</span></div> : null}
            {items.map((item) => (
              <article className="feedback-item" key={item.id}>
                <header>
                  <span className={`feedback-status ${item.status}`}>{item.status === "completed" ? <CheckCircle2 size={14} /> : null}{statusLabels[item.status]}</span>
                  <time>{formatTime(item.update_time)}</time>
                </header>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
                {item.developer_reply ? (
                  <div className="feedback-reply"><strong>开发团队回复</strong><p>{item.developer_reply}</p></div>
                ) : (
                  <div className="feedback-awaiting">已收到，开发团队正在查看</div>
                )}
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
