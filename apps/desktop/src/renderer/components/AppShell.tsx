import type { ReactNode } from "react";
import {
  Bell,
  ChevronDown,
  Clock3,
  LayoutDashboard,
  Lightbulb,
  Settings,
  ShieldCheck,
  Sparkles,
  Scissors,
  ScanSearch,
  UserRound
} from "lucide-react";

import { brandAssets } from "../assets";
import type { PageKey, PortalKey } from "../types";


type AppShellProps = {
  activePage: PageKey;
  activePortal: PortalKey;
  allowedPortals: PortalKey[];
  onNavigate: (page: PageKey) => void;
  onPortalChange: (portal: PortalKey) => void;
  children: ReactNode;
};

const portalItems: Array<{ key: PortalKey; label: string; description: string }> = [
  { key: "user", label: "用户端", description: "禾一斯员工" },
  { key: "manager", label: "管理端", description: "老板/管理层" },
  { key: "developer", label: "开发者端", description: "内部隐藏" }
];

const navItemsByPortal: Record<PortalKey, Array<{ key: PageKey; label: string; icon: typeof Sparkles }>> = {
  user: [
    { key: "create", label: "智能创作", icon: Sparkles },
    { key: "inspiration", label: "灵感对话", icon: Lightbulb },
    { key: "viralAnalysis", label: "爆款解析", icon: ScanSearch },
    { key: "videoEdit", label: "智能剪辑", icon: Scissors },
    { key: "schedule", label: "定时发布", icon: Clock3 },
    { key: "settings", label: "系统配置", icon: Settings }
  ],
  manager: [
    { key: "managerOverview", label: "运营总览", icon: LayoutDashboard },
    { key: "managerInspiration", label: "灵感对话记录", icon: Lightbulb },
    { key: "managerViralAnalysis", label: "爆款解析记录", icon: ScanSearch },
    { key: "schedule", label: "发布监控", icon: Clock3 }
  ],
  developer: [
    { key: "developerAIJobs", label: "AI 任务排查", icon: ShieldCheck }
  ]
};


export function AppShell({
  activePage,
  activePortal,
  allowedPortals,
  onNavigate,
  onPortalChange,
  children
}: AppShellProps) {
  const navItems = navItemsByPortal[activePortal];

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

        <div className="portal-switcher" aria-label="端切换">
          {portalItems.filter((item) => allowedPortals.includes(item.key)).map((item) => (
            <button
              key={item.key}
              type="button"
              className={activePortal === item.key ? "portal-tab active" : "portal-tab"}
              onClick={() => onPortalChange(item.key)}
            >
              <strong>{item.label}</strong>
              <span>{item.description}</span>
            </button>
          ))}
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
