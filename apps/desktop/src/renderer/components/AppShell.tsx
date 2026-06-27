import type { ReactNode } from "react";
import { Bell, ChevronDown, Clock3, Settings, Sparkles, UserRound } from "lucide-react";

import { brandAssets } from "../assets";
import type { PageKey } from "../types";


type AppShellProps = {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  children: ReactNode;
};

const navItems: Array<{ key: PageKey; label: string; icon: typeof Sparkles }> = [
  { key: "create", label: "智能创作", icon: Sparkles },
  { key: "schedule", label: "定时发布", icon: Clock3 },
  { key: "settings", label: "系统配置", icon: Settings }
];


export function AppShell({ activePage, onNavigate, children }: AppShellProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <img src={brandAssets.monogram} alt="" className="brand-mark" />
          <div>
            <div className="brand-name">KARRIES</div>
            <div className="brand-cn">禾一斯</div>
          </div>
        </div>

        <nav className="nav-list" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                type="button"
                className={activePage === item.key ? "nav-item active" : "nav-item"}
                onClick={() => onNavigate(item.key)}
              >
                <Icon size={20} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="operator-card">
          <UserRound size={20} aria-hidden="true" />
          <div>
            <strong>禾一斯运营团队</strong>
            <span>管理员</span>
          </div>
          <ChevronDown size={16} aria-hidden="true" />
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <img src={brandAssets.angelMark} alt="" className="top-ornament" />
          <button className="icon-button" type="button" aria-label="通知">
            <Bell size={20} />
          </button>
          <button className="avatar-button" type="button" aria-label="账号菜单">
            <img src={brandAssets.monogram} alt="" />
            <ChevronDown size={16} />
          </button>
        </header>
        {children}
      </main>
    </div>
  );
}
