import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ChevronDown,
  CircleUserRound,
  Bookmark,
  Clock3,
  Film,
  FileImage,
  FolderOpen,
  LogOut,
  Languages,
  MessageSquareText,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  ScanSearch,
  Settings,
  Sparkles,
  WalletCards
} from "lucide-react";

import { brandAssets } from "../assets";
import type { AuthUser, CreateMode, PageKey } from "../types";
import { CustomerNotificationBell } from "./CustomerNotificationBell";
import { BeianFooter } from "./BeianFooter";
import { FontScaleSelector } from "./FontScaleSelector";
import { ThemeSelector } from "./ThemeSelector";


type AppShellProps = {
  activePage: PageKey;
  activeCreateMode: CreateMode;
  user: AuthUser | null;
  onNavigate: (page: PageKey) => void;
  onCreateModeChange: (mode: CreateMode) => void;
  onLogout: () => void;
  children: ReactNode;
};

type NavigationGroupKey = "create" | "operations" | "publish";

const SIDEBAR_STORAGE_KEY = "customer-sidebar-collapsed";

type NavigationGroupProps = {
  title: string;
  icon: typeof Sparkles;
  expanded: boolean;
  active: boolean;
  onToggle: () => void;
  children: ReactNode;
};

const operationsNavigation = [
  { key: "productLibrary" as const, label: "产品知识库", icon: FolderOpen },
  { key: "viralAnalysis" as const, label: "爆款解析", icon: ScanSearch },
  { key: "aiTranslation" as const, label: "AI智能翻译", icon: Languages }
];

const publishNavigation = [
  { key: "contentCollection" as const, label: "内容收藏", icon: Bookmark },
  { key: "publishReview" as const, label: "内容审核", icon: FileImage },
  { key: "schedule" as const, label: "发布计划", icon: Clock3 },
  { key: "settings" as const, label: "账号管理", icon: Settings }
];

function NavigationGroup({
  title,
  icon: Icon,
  expanded,
  active,
  onToggle,
  children
}: NavigationGroupProps) {
  return (
    <div className="nav-group">
      <button
        type="button"
        className={active ? "nav-group-toggle active" : "nav-group-toggle"}
        aria-expanded={expanded}
        title={title}
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


export function AppShell({
  activePage,
  activeCreateMode,
  user,
  onNavigate,
  onCreateModeChange,
  onLogout,
  children
}: AppShellProps) {
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [expandedGroups, setExpandedGroups] = useState<
    Record<NavigationGroupKey, boolean>
  >({
    create: true,
    operations: true,
    publish: true
  });
  const accountMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accountMenuOpen) return;
    const closeMenu = (event: MouseEvent) => {
      if (!accountMenuRef.current?.contains(event.target as Node)) {
        setAccountMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", closeMenu);
    return () => document.removeEventListener("mousedown", closeMenu);
  }, [accountMenuOpen]);

  useEffect(() => {
    const group: NavigationGroupKey | null =
      activePage === "create" || activePage === "inspiration"
        ? "create"
        : activePage === "contentCollection" || activePage === "publishReview" || activePage === "schedule" || activePage === "settings"
          ? "publish"
          : operationsNavigation.some((item) => item.key === activePage)
            ? "operations"
            : null;
    if (!group) return;
    setExpandedGroups((current) =>
      current[group] ? current : { ...current, [group]: true }
    );
  }, [activePage]);

  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [activePage]);

  const displayName =
    user?.nickname.trim() || user?.login_name || "禾一斯员工";

  const toggleGroup = (group: NavigationGroupKey) => {
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
        // Navigation remains available when storage is unavailable.
      }
      return next;
    });
  };

  const renderPageItems = (
    items:
      | typeof operationsNavigation
      | typeof publishNavigation
  ) => items.map((item) => {
    const Icon = item.icon;
    return (
      <button
        key={item.key}
        type="button"
        className={activePage === item.key ? "nav-subitem active" : "nav-subitem"}
        aria-current={activePage === item.key ? "page" : undefined}
        title={item.label}
        onClick={() => onNavigate(item.key)}
      >
        <Icon size={17} aria-hidden="true" />
        <span>{item.label}</span>
      </button>
    );
  });

  return (
    <div className={`shell customer-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-head">
          <div className="brand-lockup">
            <img src={brandAssets.monogram} alt="" className="brand-mark" />
            <div>
              <div className="brand-name">KARRIES</div>
              <div className="brand-cn">禾一斯</div>
            </div>
          </div>
          <button className="sidebar-collapse-button" type="button" aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"} title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"} onClick={toggleSidebar}>
            {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        <nav className="nav-list" aria-label="主导航">
          <NavigationGroup
            title="智能创作"
            icon={Sparkles}
            expanded={expandedGroups.create}
            active={activePage === "create" || activePage === "inspiration"}
            onToggle={() => toggleGroup("create")}
          >
            <button
              type="button"
              className={activePage === "inspiration" ? "nav-subitem active" : "nav-subitem"}
              aria-current={activePage === "inspiration" ? "page" : undefined}
              title="Karries AI"
              onClick={() => onNavigate("inspiration")}
            >
              <MessageSquareText size={17} aria-hidden="true" />
              <span>Karries AI</span>
            </button>
            <button
              type="button"
              className={
                activePage === "create" && activeCreateMode === "video"
                  ? "nav-subitem active"
                  : "nav-subitem"
              }
              aria-current={
                activePage === "create" && activeCreateMode === "video"
                  ? "page"
                  : undefined
              }
              onClick={() => onCreateModeChange("video")}
              title="视频创作"
            >
              <Film size={17} aria-hidden="true" />
              <span>视频创作</span>
            </button>
          </NavigationGroup>

          <NavigationGroup
            title="运营工具"
            icon={ScanSearch}
            expanded={expandedGroups.operations}
            active={operationsNavigation.some((item) => item.key === activePage)}
            onToggle={() => toggleGroup("operations")}
          >
            {renderPageItems(operationsNavigation)}
          </NavigationGroup>

          <NavigationGroup
            title="发布管理"
            icon={Clock3}
            expanded={expandedGroups.publish}
            active={publishNavigation.some((item) => item.key === activePage)}
            onToggle={() => toggleGroup("publish")}
          >
            {renderPageItems(publishNavigation)}
          </NavigationGroup>

          <button
            type="button"
            className={activePage === "feedback" ? "nav-primary-item active" : "nav-primary-item"}
            aria-current={activePage === "feedback" ? "page" : undefined}
            title="需求反馈"
            onClick={() => onNavigate("feedback")}
          >
            <MessageSquarePlus size={19} aria-hidden="true" />
            <span>需求反馈</span>
          </button>

        </nav>

      </aside>

      <main className="workspace">
        <header className="topbar">
          <CustomerNotificationBell onNavigate={onNavigate} />
          <div className="account-menu" ref={accountMenuRef}>
            <button
              className="avatar-button"
              type="button"
              aria-label="账号菜单"
              aria-expanded={accountMenuOpen}
              onClick={() => setAccountMenuOpen((current) => !current)}
            >
              <img src={brandAssets.monogram} alt="" />
              <ChevronDown size={16} />
            </button>
            {accountMenuOpen ? (
              <div className="account-dropdown">
                <div className="account-dropdown-user">
                  <strong>{displayName}</strong>
                  <span>{user?.login_name}</span>
                </div>
                <ThemeSelector />
                <FontScaleSelector />
                <button
                  type="button"
                  onClick={() => {
                    setAccountMenuOpen(false);
                    onNavigate("profile");
                  }}
                >
                  <CircleUserRound size={16} aria-hidden="true" />
                  个人中心
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAccountMenuOpen(false);
                    onNavigate("recharge");
                  }}
                >
                  <WalletCards size={16} aria-hidden="true" />
                  充值中心
                </button>
                <button type="button" onClick={onLogout}>
                  <LogOut size={16} aria-hidden="true" />
                  退出登录
                </button>
              </div>
            ) : null}
          </div>
        </header>
        {children}
        <BeianFooter />
      </main>
    </div>
  );
}
