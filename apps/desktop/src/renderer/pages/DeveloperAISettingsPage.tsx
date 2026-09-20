import { useCallback, useEffect, useState } from "react";
import {
  Bot,
  Eye,
  KeyRound,
  PlugZap,
  RefreshCw,
  Save,
  Sparkles,
  Trash2
} from "lucide-react";

import { developerApi } from "../api/developerClient";
import type {
  AIProviderSettings,
  AISettingSlot,
  AISettingTestResult
} from "../types";


type SlotDraft = { apiKey: string; model: string; enabled: boolean };
type Drafts = Record<AISettingSlot, SlotDraft>;
type SlotMessages = Record<AISettingSlot, string>;
type MessageTone = "neutral" | "success" | "error";
type SlotMessageTones = Record<AISettingSlot, MessageTone>;

const slotOrder: AISettingSlot[] = ["vision", "copywriting", "pro_copywriting"];
const slotMeta = {
  vision: {
    title: "豆包视觉解析",
    description: "用于图片识别、视频理解和爆款内容解析。",
    keyLabel: "豆包 API Key",
    saveLabel: "保存豆包配置",
    testLabel: "测试豆包连接",
    clearLabel: "清除豆包 Key",
    icon: Eye
  },
  copywriting: {
    title: "DeepSeek 文案生成",
    description: "用于 Karries AI 对话、脚本优化和文案生成。",
    keyLabel: "DeepSeek API Key",
    saveLabel: "保存 DeepSeek 配置",
    testLabel: "测试 DeepSeek 连接",
    clearLabel: "清除 DeepSeek Key",
    icon: Bot
  },
  pro_copywriting: {
    title: "豆包 Pro 对话",
    description: "用于 Karries AI Pro 模式的高质量对话。",
    keyLabel: "豆包 Pro API Key",
    saveLabel: "保存豆包 Pro 配置",
    testLabel: "测试豆包 Pro 连接",
    clearLabel: "清除豆包 Pro Key",
    icon: Sparkles
  }
} as const;

const emptyDrafts: Drafts = {
  vision: { apiKey: "", model: "", enabled: true },
  copywriting: { apiKey: "", model: "", enabled: true },
  pro_copywriting: { apiKey: "", model: "", enabled: true }
};

const emptyMessages: SlotMessages = {
  vision: "",
  copywriting: "",
  pro_copywriting: ""
};
const emptyMessageTones: SlotMessageTones = {
  vision: "neutral",
  copywriting: "neutral",
  pro_copywriting: "neutral"
};


function draftsFromSettings(settings: AIProviderSettings): Drafts {
  return {
    vision: {
      apiKey: "",
      model: settings.vision.model,
      enabled: settings.vision.enabled
    },
    copywriting: {
      apiKey: "",
      model: settings.copywriting.model,
      enabled: settings.copywriting.enabled
    },
    pro_copywriting: {
      apiKey: "",
      model: settings.pro_copywriting.model,
      enabled: settings.pro_copywriting.enabled
    }
  };
}


export function DeveloperAISettingsPage() {
  const [settings, setSettings] = useState<AIProviderSettings | null>(null);
  const [drafts, setDrafts] = useState<Drafts>(emptyDrafts);
  const [messages, setMessages] = useState<SlotMessages>(emptyMessages);
  const [messageTones, setMessageTones] = useState<SlotMessageTones>(emptyMessageTones);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busySlot, setBusySlot] = useState<AISettingSlot | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await developerApi.getAISettings();
      setSettings(result);
      setDrafts(draftsFromSettings(result));
      setMessages(emptyMessages);
      setMessageTones(emptyMessageTones);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI Provider 配置加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const updateDraft = (slot: AISettingSlot, patch: Partial<SlotDraft>) => {
    setDrafts((current) => ({
      ...current,
      [slot]: { ...current[slot], ...patch }
    }));
  };

  const setSlotMessage = (
    slot: AISettingSlot,
    message: string,
    tone: MessageTone = "neutral"
  ) => {
    setMessages((current) => ({ ...current, [slot]: message }));
    setMessageTones((current) => ({ ...current, [slot]: tone }));
  };

  const syncSavedSlot = (slot: AISettingSlot, result: AIProviderSettings) => {
    setSettings(result);
    setDrafts((current) => ({
      ...current,
      [slot]: {
        apiKey: "",
        model: result[slot].model,
        enabled: result[slot].enabled
      }
    }));
  };

  const save = async (slot: AISettingSlot) => {
    const draft = drafts[slot];
    if (!draft.model.trim()) {
      setSlotMessage(slot, "模型名称不能为空", "error");
      return;
    }
    setBusySlot(slot);
    setSlotMessage(slot, "");
    try {
      const result = await developerApi.updateAISetting(slot, {
        api_key: draft.apiKey,
        model: draft.model.trim(),
        enabled: draft.enabled
      });
      syncSavedSlot(slot, result);
      setSlotMessage(slot, "配置已安全保存；Key 输入框已清空", "success");
    } catch (caught) {
      setSlotMessage(
        slot,
        caught instanceof Error ? caught.message : "配置保存失败",
        "error"
      );
    } finally {
      setBusySlot(null);
    }
  };

  const testConnection = async (slot: AISettingSlot) => {
    setBusySlot(slot);
    setSlotMessage(slot, "正在连接 Provider...");
    try {
      const result: AISettingTestResult = await developerApi.testAISetting(slot);
      setSlotMessage(slot, `连接正常 · ${result.latency_ms} ms`, "success");
    } catch (caught) {
      setSlotMessage(
        slot,
        caught instanceof Error ? caught.message : "连接测试失败",
        "error"
      );
    } finally {
      setBusySlot(null);
    }
  };

  const clearKey = async (slot: AISettingSlot) => {
    const meta = slotMeta[slot];
    if (!window.confirm(`确认清除${meta.title}已保存的 API Key？`)) return;
    setBusySlot(slot);
    setSlotMessage(slot, "");
    try {
      const result = await developerApi.clearAISettingKey(slot);
      syncSavedSlot(slot, result);
      setSlotMessage(slot, "API Key 已清除", "success");
    } catch (caught) {
      setSlotMessage(
        slot,
        caught instanceof Error ? caught.message : "API Key 清除失败",
        "error"
      );
    } finally {
      setBusySlot(null);
    }
  };

  return (
    <section className="developer-page developer-ops-page developer-ai-settings-page">
      <header className="developer-page-header">
        <div>
          <h1>AI Provider 配置</h1>
          <p>
            管理豆包视觉解析、DeepSeek 标准对话与豆包 Pro 对话。API 地址由系统锁定，
            已保存的完整密钥不会在页面或接口中回显。
          </p>
        </div>
        <button
          className="secondary-button"
          type="button"
          disabled={loading || busySlot !== null}
          onClick={() => void load()}
        >
          <RefreshCw size={17} aria-hidden="true" />
          刷新配置
        </button>
      </header>

      {error ? <div className="inline-alert error" role="alert">{error}</div> : null}
      {loading && !settings ? (
        <div className="developer-empty-state" aria-busy="true">正在读取安全配置...</div>
      ) : settings ? (
        <div className="developer-ai-provider-grid">
          {slotOrder.map((slot, index) => {
            const setting = settings[slot];
            const draft = drafts[slot];
            const meta = slotMeta[slot];
            const Icon = meta.icon;
            const busy = busySlot === slot;
            return (
              <article className="developer-ai-provider-card" key={slot}>
                <header className="developer-ai-provider-card-head">
                  <div className="developer-ai-provider-title">
                    <span className="developer-ai-provider-icon"><Icon size={21} /></span>
                    <div>
                      <span className="developer-ai-provider-index">0{index + 1}</span>
                      <h2>{meta.title}</h2>
                      <p>{meta.description}</p>
                    </div>
                  </div>
                  <span className={`developer-provider-state ${setting.enabled ? "enabled" : "disabled"}`}>
                    {setting.enabled ? "已启用" : "已停用"}
                  </span>
                </header>

                <div className="developer-ai-provider-summary">
                  <div><span>Provider</span><strong>{setting.provider}</strong></div>
                  <div><span>密钥状态</span><strong>{setting.has_key ? setting.masked_key : "未配置"}</strong></div>
                </div>

                <div className="developer-ai-provider-form">
                  <label>
                    <span>固定 API 地址</span>
                    <input value={setting.base_url} readOnly aria-readonly="true" />
                    <small>由后端固定，前端不可修改，避免请求被转发到未知地址。</small>
                  </label>
                  <label>
                    <span>模型名称</span>
                    <input
                      value={draft.model}
                      maxLength={100}
                      onChange={(event) => updateDraft(slot, { model: event.target.value })}
                    />
                  </label>
                  <label>
                    <span>{meta.keyLabel}</span>
                    <input
                      type="password"
                      aria-label={meta.keyLabel}
                      value={draft.apiKey}
                      maxLength={512}
                      autoComplete="new-password"
                      placeholder={setting.has_key ? "留空则保留当前 Key" : "请输入 API Key"}
                      onChange={(event) => updateDraft(slot, { apiKey: event.target.value })}
                    />
                    <small>仅在保存时提交；保存成功后立即清空输入框。</small>
                  </label>
                  <label className="developer-provider-toggle">
                    <input
                      type="checkbox"
                      checked={draft.enabled}
                      onChange={(event) => updateDraft(slot, { enabled: event.target.checked })}
                    />
                    <span>启用该 Provider</span>
                  </label>
                </div>

                {messages[slot] ? (
                  <div
                    className={`developer-provider-message ${messageTones[slot]}`}
                    role={messageTones[slot] === "error" ? "alert" : "status"}
                    aria-live="polite"
                  >
                    {messages[slot]}
                  </div>
                ) : null}

                <footer className="developer-ai-provider-actions">
                  <button
                    className="primary-button"
                    type="button"
                    disabled={busySlot !== null}
                    onClick={() => void save(slot)}
                  >
                    <Save size={16} aria-hidden="true" />
                    {meta.saveLabel}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busySlot !== null || !setting.has_key}
                    onClick={() => void testConnection(slot)}
                  >
                    <PlugZap size={16} aria-hidden="true" />
                    {busy ? "处理中..." : meta.testLabel}
                  </button>
                  <button
                    className="secondary-button developer-provider-clear"
                    type="button"
                    disabled={busySlot !== null || !setting.has_key}
                    onClick={() => void clearKey(slot)}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    {meta.clearLabel}
                  </button>
                </footer>
              </article>
            );
          })}
        </div>
      ) : null}

      <aside className="developer-ai-security-note">
        <KeyRound size={20} aria-hidden="true" />
        <div>
          <strong>密钥安全说明</strong>
          <p>完整 API Key 只在后端加密存储；连接测试使用已保存密钥，结果仅返回 Provider、模型、请求编号和耗时。</p>
        </div>
      </aside>
    </section>
  );
}
