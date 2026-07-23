import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, MonitorCheck, Plus, ScanLine } from "lucide-react";

import { api } from "../api/client";
import type { AISettingSlot, AISettingsView, AISettingUpdate } from "../types";


const defaultAISettings: AISettingsView = {
  vision: {
    provider: "doubao",
    base_url: "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    model: "doubao-vision-pro",
    enabled: true,
    has_key: false,
    masked_key: ""
  },
  copywriting: {
    provider: "deepseek",
    base_url: "https://api.deepseek.com/chat/completions",
    model: "deepseek-chat",
    enabled: true,
    has_key: false,
    masked_key: ""
  }
};

type AISettingDraft = AISettingUpdate;

type SettingCardProps = {
  title: string;
  slot: AISettingSlot;
  keyLabel: string;
  saveLabel: string;
  providerOptions: string[];
  statusText: string;
  draft: AISettingDraft;
  onDraftChange: (draft: AISettingDraft) => void;
  onSave: (slot: AISettingSlot) => void;
  onClear: (slot: AISettingSlot) => void;
};


function toDraft(settings: AISettingsView, slot: AISettingSlot): AISettingDraft {
  const setting = settings[slot];
  return {
    provider: setting.provider,
    api_key: "",
    base_url: setting.base_url,
    model: setting.model,
    enabled: setting.enabled
  };
}


export function SettingsPage() {
  const [settings, setSettings] = useState<AISettingsView>(defaultAISettings);
  const [visionDraft, setVisionDraft] = useState<AISettingDraft>(() => toDraft(defaultAISettings, "vision"));
  const [copyDraft, setCopyDraft] = useState<AISettingDraft>(() => toDraft(defaultAISettings, "copywriting"));
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getAISettings()
      .then((nextSettings) => {
        setSettings(nextSettings);
        setVisionDraft(toDraft(nextSettings, "vision"));
        setCopyDraft(toDraft(nextSettings, "copywriting"));
      })
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : "AI 配置加载失败");
      });
  }, []);

  async function saveSetting(slot: AISettingSlot) {
    const draft = slot === "vision" ? visionDraft : copyDraft;
    try {
      const nextSettings = await api.saveAISetting(slot, draft);
      setSettings(nextSettings);
      setVisionDraft(toDraft(nextSettings, "vision"));
      setCopyDraft(toDraft(nextSettings, "copywriting"));
      setMessage(slot === "vision" ? "视觉识图配置已保存" : "文案生成配置已保存");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "AI 配置保存失败");
    }
  }

  async function clearKey(slot: AISettingSlot) {
    try {
      const nextSettings = await api.clearAISettingKey(slot);
      setSettings(nextSettings);
      setVisionDraft(toDraft(nextSettings, "vision"));
      setCopyDraft(toDraft(nextSettings, "copywriting"));
      setMessage(slot === "vision" ? "视觉识图 Key 已清除" : "DeepSeek Key 已清除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "AI Key 清除失败");
    }
  }

  return (
    <section className="page-stack">
      <div className="page-heading">
        <h1>系统配置</h1>
        <p>配置 AI 服务商、小红书账号和本机浏览器自动化运行环境。</p>
      </div>

      {message ? <div className="form-message">{message}</div> : null}

      <div className="settings-grid">
        <SettingCard
          title="视觉识图 API"
          slot="vision"
          keyLabel="视觉 API KEY"
          saveLabel="保存视觉配置"
          providerOptions={["doubao", "gpt", "gemini"]}
          statusText={settings.vision.has_key ? `已保存 ${settings.vision.masked_key}` : "未保存"}
          draft={visionDraft}
          onDraftChange={setVisionDraft}
          onSave={saveSetting}
          onClear={clearKey}
        />

        <SettingCard
          title="文案生成 API"
          slot="copywriting"
          keyLabel="DeepSeek API KEY"
          saveLabel="保存文案配置"
          providerOptions={["deepseek"]}
          statusText={settings.copywriting.has_key ? `已保存 ${settings.copywriting.masked_key}` : "未保存"}
          draft={copyDraft}
          onDraftChange={setCopyDraft}
          onSave={saveSetting}
          onClear={clearKey}
        />

        <section className="panel account-panel">
          <div className="panel-title">
            <h2>小红书账号管理</h2>
            <span className="key-status connected">账号 2</span>
          </div>
          <div className="account-actions">
            <button className="primary-button compact" type="button">
              <Plus size={17} aria-hidden="true" />
              新增账号
            </button>
            <button className="secondary-button compact" type="button">
              <ScanLine size={17} aria-hidden="true" />
              扫码登录
            </button>
          </div>
          <div className="account-list">
            <div>
              <strong>品牌运营号</strong>
              <span>浏览器扫码登录 · 待检查</span>
            </div>
            <div>
              <strong>禾一斯门店号</strong>
              <span>浏览器扫码登录 · 已保存</span>
            </div>
          </div>
        </section>

        <section className="panel runtime-panel">
          <div className="panel-title">
            <h2>
              <MonitorCheck size={18} aria-hidden="true" />
              运行环境检测
            </h2>
          </div>
          <div className="runtime-check-row">
            <CheckCircle2 size={22} aria-hidden="true" />
            <div>
              <strong>浏览器自动化组件</strong>
              <span>可通过环境检测接口确认本机组件状态</span>
            </div>
          </div>
          <div className="primary-row">
            <button className="primary-button" type="button">检测环境</button>
            <button className="secondary-button" type="button">安装浏览器组件</button>
          </div>
        </section>
      </div>
    </section>
  );
}


function SettingCard({
  title,
  slot,
  keyLabel,
  saveLabel,
  providerOptions,
  statusText,
  draft,
  onDraftChange,
  onSave,
  onClear
}: SettingCardProps) {
  return (
    <section className="panel config-panel">
      <div className="panel-title">
        <h2>
          <KeyRound size={18} aria-hidden="true" />
          {title}
        </h2>
        <span className={statusText.startsWith("已保存") ? "key-status connected" : "key-status"}>
          {statusText}
        </span>
      </div>
      <div className="form-grid single">
        <label>
          服务商
          <select
            value={draft.provider}
            onChange={(event) => onDraftChange({ ...draft, provider: event.target.value })}
          >
            {providerOptions.map((provider) => (
              <option key={provider} value={provider}>{provider}</option>
            ))}
          </select>
        </label>
        <label>
          {keyLabel}
          <input
            type="password"
            value={draft.api_key}
            placeholder="sk-..."
            onChange={(event) => onDraftChange({ ...draft, api_key: event.target.value })}
          />
        </label>
        <label>
          接口地址
          <input
            value={draft.base_url}
            onChange={(event) => onDraftChange({ ...draft, base_url: event.target.value })}
          />
        </label>
        <label>
          模型
          <input
            value={draft.model}
            onChange={(event) => onDraftChange({ ...draft, model: event.target.value })}
          />
        </label>
      </div>
      <div className="primary-row">
        <button className="primary-button" type="button" onClick={() => onSave(slot)}>{saveLabel}</button>
        <button className="secondary-button" type="button" onClick={() => onClear(slot)}>清除 Key</button>
      </div>
    </section>
  );
}
