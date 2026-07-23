import type { ReactNode } from "react";
import { Bell, ChevronDown, ScanSearch, Scissors, ShieldCheck } from "lucide-react";

import { brandAssets } from "../assets";


export type DeveloperPageKey = "aiJobs" | "videoJobs";

type DeveloperShellProps = {
  activePage: DeveloperPageKey;
  onNavigate: (page: DeveloperPageKey) => void;
  children: ReactNode;
};

const navigation = [
  { key: "aiJobs" as const, label: "AI 任务排查", icon: ScanSearch },
  { key: "videoJobs" as const, label: "人工剪辑工单", icon: Scissors }
];


export function DeveloperShell({
  activePage,
  onNavigate,
  children
}: DeveloperShellProps) {
  return (
    <div className="shell developer-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <img src={brandAssets.monogram} alt="" className="brand-mark" />
          <div>
            <div className="brand-name">KARRIES OPS</div>
            <div className="brand-cn">点绘环球内部运营</div>
          </div>
        </div>

        <div className="portal-switcher">
          <div className="portal-tab active">
            <strong>开发者端</strong>
            <span>内部专用入口</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="开发者导航">
          {navigation.map((item) => {
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
          <ShieldCheck size={20} aria-hidden="true" />
          <div>
            <strong>点绘环球技术运营</strong>
            <span>开发者管理员</span>
          </div>
          <ChevronDown size={16} aria-hidden="true" />
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <button className="icon-button" type="button" aria-label="通知">
            <Bell size={20} />
          </button>
          <button className="avatar-button" type="button" aria-label="开发者账号菜单">
            <img src={brandAssets.monogram} alt="" />
            <ChevronDown size={16} />
          </button>
        </header>
        {children}
      </main>
    </div>
  );
}
