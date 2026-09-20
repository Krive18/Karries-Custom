import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ChevronDown,
  CalendarClock,
  CreditCard,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  MessageSquareText,
  MonitorCheck,
  PanelLeftClose,
  PanelLeftOpen,
  ReceiptText,
  ScanSearch,
  ShieldCheck,
  UsersRound
} from "lucide-react";

import { brandAssets } from "../assets";
import type { AuthUser } from "../types";
import { ManagerNotificationBell } from "./ManagerNotificationBell";
import { FontScaleSelector } from "./FontScaleSelector";
import { ThemeSelector } from "./ThemeSelector";


export type ManagerPageKey =
  | "overview"
  | "users"
  | "xhsAccounts"
  | "publishing"
  | "inspiration"
  | "viralAnalysis"
  | "billing"
  | "creditLedger"
  | "productLibrary";

type ManagerNavigationGroupKey = "publishing" | "content" | "billing";

type ManagerShellProps = {
  activePage: ManagerPageKey;
  user: AuthUser | null;
  onNavigate: (page: ManagerPageKey) => void;
  onLogout: () => void;
  children: ReactNode;
};

type ManagerNavigationGroupProps = {
  title: string;
  icon: typeof LayoutDashboard;
  expanded: boolean;
  active: boolean;
  onToggle: () => void;
  children: ReactNode;
  collapsed?: boolean;
};

const publishingNavigation = [
  { key: "xhsAccounts" as const, label: "账号监控", icon: MonitorCheck },
  { key: "publishing" as const, label: "发布运营中心", icon: CalendarClock }
];

const contentNavigation = [
  { key: "viralAnalysis" as const, label: "爆款解析记录", icon: ScanSearch },
  { key: "inspiration" as const, label: "Karries AI 记录", icon: MessageSquareText }
];

const billingNavigation = [
  { key: "billing" as const, label: "会员与充值", icon: CreditCard },
  { key: "creditLedger" as const, label: "算力流水", icon: ReceiptText }
];

const SIDEBAR_STORAGE_KEY = "manager-sidebar-collapsed";

function ManagerNavigationGroup({
  title,
  icon: Icon,
  expanded,
  active,
  onToggle,
  children,
  collapsed = false
}: ManagerNavigationGroupProps) {
  return (
    <div className="nav-group">
      <button
        type="button"
        className={active ? "nav-group-toggle active" : "nav-group-toggle"}
        aria-expanded={expanded}
        title={collapsed ? title : undefined}
        onClick={onToggle}
      >
        <Icon size={19} aria-hidden="true" />
        <span>{title}</span>
        <ChevronDown
          className={expanded ? "nav-group-chevron expanded" : "nav-group-chevron"}
          size={16}
          aria-hidden="true"
        />
      </button>
      <div
        className={expanded ? "nav-sublist expanded" : "nav-sublist"}
        aria-label={`${title}子菜单`}
        hidden={!expanded}
      >
        {children}
      </div>
    </div>
  );
}


export function ManagerShell({
  activePage,
  user,
  onNavigate,
  onLogout,
  children
}: ManagerShellProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [expandedGroups, setExpandedGroups] = useState<
    Record<ManagerNavigationGroupKey, boolean>
  >({
    publishing: true,
    content: true,
    billing: true
  });
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const closeMenu = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", closeMenu);
    return () => document.removeEventListener("mousedown", closeMenu);
  }, [menuOpen]);

  const displayName =
    user?.nickname.trim() || user?.login_name || "禾一斯老板";

  useEffect(() => {
    if (activePage === "overview" || activePage === "users") return;
    let group: ManagerNavigationGroupKey = "content";
    if (activePage === "xhsAccounts" || activePage === "publishing") {
      group = "publishing";
    } else if (activePage === "billing" || activePage === "creditLedger") {
      group = "billing";
    }
    setExpandedGroups((current) =>
      current[group] ? current : { ...current, [group]: true }
    );
  }, [activePage]);

  const toggleGroup = (group: ManagerNavigationGroupKey) => {
    setExpandedGroups((current) => ({
      ...current,
      [group]: !current[group]
    }));
  };

  const toggleSidebar = () => {
    setSidebarCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? "1" : "0");
      } catch {
        // Keep the control usable when storage is unavailable.
      }
      return next;
    });
  };

  const renderNavigationItems = (
    items:
      | typeof publishingNavigation
      | typeof contentNavigation
      | typeof billingNavigation
  ) => items.map((item) => {
    const Icon = item.icon;
    return (
      <button
        key={item.key}
        type="button"
        className={activePage === item.key ? "nav-subitem active" : "nav-subitem"}
        aria-current={activePage === item.key ? "page" : undefined}
        title={sidebarCollapsed ? item.label : undefined}
        onClick={() => onNavigate(item.key)}
      >
        <Icon size={17} aria-hidden="true" />
        <span>{item.label}</span>
      </button>
    );
  });

  return (
    <div className={`shell manager-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-head">
          <div className="brand-lockup">
            <img src={brandAssets.monogram} alt="" className="brand-mark" />
            <div>
              <div className="brand-name">KARRIES</div>
              <div className="brand-cn">运营管理中心</div>
            </div>
          </div>
          <button
            className="sidebar-collapse-button"
            type="button"
            aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            onClick={toggleSidebar}
          >
            {sidebarCollapsed
              ? <PanelLeftOpen size={18} aria-hidden="true" />
              : <PanelLeftClose size={18} aria-hidden="true" />}
          </button>
        </div>

        <nav className="nav-list" aria-label="管理端导航">
          <button
            type="button"
            className={activePage === "overview" ? "nav-group-toggle active" : "nav-group-toggle"}
            aria-current={activePage === "overview" ? "page" : undefined}
            title={sidebarCollapsed ? "运营总览" : undefined}
            onClick={() => onNavigate("overview")}
          >
            <LayoutDashboard size={19} aria-hidden="true" />
            <span>运营总览</span>
          </button>
          <button
            type="button"
            className={activePage === "users" ? "nav-group-toggle active" : "nav-group-toggle"}
            aria-current={activePage === "users" ? "page" : undefined}
            title={sidebarCollapsed ? "员工账号管理" : undefined}
            onClick={() => onNavigate("users")}
          >
            <UsersRound size={19} aria-hidden="true" />
            <span>员工账号管理</span>
          </button>
          <button
            type="button"
            className={activePage === "productLibrary" ? "nav-group-toggle active" : "nav-group-toggle"}
            aria-current={activePage === "productLibrary" ? "page" : undefined}
            title={sidebarCollapsed ? "产品库管理" : undefined}
            onClick={() => onNavigate("productLibrary")}
          >
            <FolderOpen size={19} aria-hidden="true" />
            <span>产品库管理</span>
          </button>
          <ManagerNavigationGroup
            title="账号与发布"
            icon={CalendarClock}
            expanded={expandedGroups.publishing}
            active={publishingNavigation.some((item) => item.key === activePage)}
            onToggle={() => toggleGroup("publishing")}
            collapsed={sidebarCollapsed}
          >
            {renderNavigationItems(publishingNavigation)}
          </ManagerNavigationGroup>
          <ManagerNavigationGroup
            title="内容记录"
            icon={ScanSearch}
            expanded={expandedGroups.content}
            active={contentNavigation.some((item) => item.key === activePage)}
            onToggle={() => toggleGroup("content")}
            collapsed={sidebarCollapsed}
          >
            {renderNavigationItems(contentNavigation)}
          </ManagerNavigationGroup>
          <ManagerNavigationGroup
            title="会员与算力"
            icon={CreditCard}
            expanded={expandedGroups.billing}
            active={billingNavigation.some((item) => item.key === activePage)}
            onToggle={() => toggleGroup("billing")}
            collapsed={sidebarCollapsed}
          >
            {renderNavigationItems(billingNavigation)}
          </ManagerNavigationGroup>
        </nav>

        <div className="operator-card">
          <ShieldCheck size={20} aria-hidden="true" />
          <div>
            <strong>{displayName}</strong>
            <span>老板账号</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <ManagerNotificationBell />
          <div className="account-menu" ref={menuRef}>
            <button
              className="avatar-button"
              type="button"
              aria-label="管理账号菜单"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((current) => !current)}
            >
              <img src={brandAssets.monogram} alt="" />
              <ChevronDown size={16} />
            </button>
            {menuOpen ? (
              <div className="account-dropdown">
                <div className="account-dropdown-user">
                  <strong>{displayName}</strong>
                  <span>{user?.login_name}</span>
                </div>
                <ThemeSelector />
                <FontScaleSelector />
                <button type="button" onClick={onLogout}>
                  <LogOut size={16} aria-hidden="true" />
                  退出登录
                </button>
              </div>
            ) : null}
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
