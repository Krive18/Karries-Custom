import { CheckCircle2, KeyRound, MonitorCheck, Plus, ScanLine } from "lucide-react";


export function SettingsPage() {
  return (
    <section className="page-stack">
      <div className="page-heading">
        <h1>系统配置</h1>
        <p>配置 AI 服务商、小红书账号和本机浏览器自动化运行环境。</p>
      </div>

      <div className="settings-grid">
        <section className="panel config-panel">
          <div className="panel-title">
            <h2>
              <KeyRound size={18} aria-hidden="true" />
              AI API KEY
            </h2>
            <span className="key-status">未保存</span>
          </div>
          <div className="form-grid single">
            <label>
              服务商
              <select defaultValue="DeepSeek">
                <option>DeepSeek</option>
                <option>GPT</option>
                <option>豆包</option>
                <option>Gemini</option>
              </select>
            </label>
            <label>
              API KEY
              <input type="password" placeholder="sk-..." />
            </label>
            <label>
              接口地址
              <input defaultValue="https://api.deepseek.com/chat/completions" />
            </label>
          </div>
          <div className="primary-row">
            <button className="primary-button" type="button">保存 Key</button>
            <button className="secondary-button" type="button">清除 Key</button>
          </div>
        </section>

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
