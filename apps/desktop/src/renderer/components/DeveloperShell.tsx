import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Activity,
  BellRing,
  Bell,
  ChevronDown,
  LogOut,
  ListChecks,
  Languages,
  Menu,
  MessageSquareMore,
  ScanSearch,
  Search,
  ScrollText,
  Scissors,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  WalletCards,
  type LucideIcon
} from "lucide-react";

import { brandAssets } from "../assets";
import type { AuthUser } from "../types";


export type DeveloperPageKey =
  | "overview"
  | "tasks"
  | "alerts"
  | "videoJobs"
  | "aiJobs"
  | "translationJobs"
  | "feedback"
  | "billing"
  | "aiSettings"
  | "customers"
  | "access"
  | "audit";

type DeveloperShellProps = {
  activePage: DeveloperPageKey;
  user: AuthUser | null;
  onNavigate: (page: DeveloperPageKey) => void;
  onLogout: () => void;
  children: ReactNode;
};

const navigationGroups: Array<{
  label: string;
  items: Array<{ key: DeveloperPageKey; label: string; icon: LucideIcon }>;
}> = [
  {
    label: "运行监控",
    items: [
      { key: "overview" as const, label: "平台总览", icon: Activity },
      { key: "tasks" as const, label: "统一任务中心", icon: ListChecks },
      { key: "alerts" as const, label: "告警与事件", icon: BellRing }
    ]
  },
  {
    label: "内容交付",
    items: [
      { key: "videoJobs" as const, label: "视频交付中心", icon: Scissors },
      { key: "translationJobs" as const, label: "AI 翻译任务", icon: Languages },
      { key: "aiJobs" as const, label: "AI 任务排查", icon: ScanSearch },
      { key: "feedback" as const, label: "需求反馈", icon: MessageSquareMore }
    ]
  },
  {
    label: "资源管理",
    items: [
      { key: "billing" as const, label: "算力管理", icon: WalletCards },
      { key: "aiSettings" as const, label: "AI Provider 配置", icon: SlidersHorizontal },
      { key: "customers" as const, label: "客户账号管理", icon: Users }
    ]
  },
  {
    label: "平台安全",
    items: [
      { key: "access" as const, label: "内部账号权限", icon: ShieldCheck },
      { key: "audit" as const, label: "审计日志", icon: ScrollText }
    ]
  }
];

const SIDEBAR_STORAGE_KEY = "developer-sidebar-collapsed";


export function DeveloperShell({
  activePage,
  user,
  onNavigate,
  onLogout,
  children
}: DeveloperShellProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const menuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

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

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const displayName =
    user?.nickname.trim() || user?.login_name || "内部管理员";
  const searchableItems = navigationGroups.flatMap((group) => group.items);
  const matchedItems = searchValue.trim()
    ? searchableItems.filter((item) =>
        item.label.toLowerCase().includes(searchValue.trim().toLowerCase())
      )
    : searchableItems.slice(0, 5);

  const openPage = (page: DeveloperPageKey) => {
    onNavigate(page);
    setSearchValue("");
    setSearchOpen(false);
  };

  const toggleSidebar = () => {
    setSidebarCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? "1" : "0");
      } catch {
        // The navigation still works when storage is unavailable.
      }
      return next;
    });
  };

  return (
    <div className={`shell developer-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <a className="developer-skip-link" href="#developer-main-content">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <div className="developer-sidebar-head">
          <div className="brand-lockup">
            <span className="developer-brand-mark-wrap">
              <img
                src={brandAssets.monogram}
                alt=""
                aria-hidden="true"
                className="brand-mark"
                width={25}
                height={25}
              />
            </span>
            <div>
              <div className="brand-name" translate="no">KARRIES</div>
              <div className="brand-cn">内部交付工作台</div>
            </div>
          </div>
        </div>

        <nav className="nav-list" aria-label="开发者导航">
          {navigationGroups.map((group) => (
            <div className="developer-nav-group" key={group.label}>
              <div className="developer-nav-caption">
                <span className="developer-nav-caption-copy">{group.label}</span>
              </div>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={
                      activePage === item.key
                        ? "nav-group-toggle developer-nav-item active"
                        : "nav-group-toggle developer-nav-item"
                    }
                    aria-current={activePage === item.key ? "page" : undefined}
                    title={sidebarCollapsed ? item.label : undefined}
                    onClick={() => onNavigate(item.key)}
                  >
                    <span className="developer-nav-icon">
                      <Icon size={18} aria-hidden="true" />
                    </span>
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="operator-card" title={sidebarCollapsed ? `${displayName} · 内部技术运营` : undefined}>
          <span className="developer-operator-icon">
            <ShieldCheck size={18} aria-hidden="true" />
          </span>
          <div>
            <strong>{displayName}</strong>
            <span><i aria-hidden="true" />内部技术运营</span>
          </div>
        </div>
      </aside>

      <main className="workspace" id="developer-main-content">
        <header className="topbar">
          <button
            className="developer-topbar-menu"
            type="button"
            aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            onClick={toggleSidebar}
          >
            <Menu size={19} aria-hidden="true" />
          </button>
          <form
            className="developer-global-search"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              if (matchedItems[0]) openPage(matchedItems[0].key);
            }}
          >
            <Search size={17} aria-hidden="true" />
            <input
              ref={searchRef}
              type="search"
              value={searchValue}
              placeholder="搜索功能、任务、事件…"
              aria-label="全局搜索"
              autoComplete="off"
              onFocus={() => setSearchOpen(true)}
              onBlur={() => window.setTimeout(() => setSearchOpen(false), 120)}
              onChange={(event) => {
                setSearchValue(event.target.value);
                setSearchOpen(true);
              }}
            />
            <kbd>Ctrl K</kbd>
            {searchOpen ? (
              <div className="developer-search-results" role="listbox" aria-label="功能搜索结果">
                {matchedItems.length ? matchedItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button key={item.key} type="button" onMouseDown={() => openPage(item.key)}>
                      <Icon size={16} aria-hidden="true" />
                      <span>{item.label}</span>
                    </button>
                  );
                }) : <span>没有匹配的功能</span>}
              </div>
            ) : null}
          </form>
          <div className="developer-topbar-actions">
            <button className="icon-button developer-notification-button" type="button" aria-label="查看告警通知" onClick={() => onNavigate("alerts")}>
              <Bell size={19} aria-hidden="true" />
              <span>6</span>
            </button>
            <button className="developer-runtime-pill" type="button" onClick={() => onNavigate("overview")}>
              <i aria-hidden="true" />运行正常
            </button>
          <div className="account-menu" ref={menuRef}>
            <button
              className="avatar-button"
              type="button"
              aria-label="开发者账号菜单"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((current) => !current)}
            >
              <img
                src={brandAssets.monogram}
                alt=""
                aria-hidden="true"
                width={25}
                height={25}
              />
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {menuOpen ? (
              <div className="account-dropdown">
                <div className="account-dropdown-user">
                  <strong>{displayName}</strong>
                  <span>{user?.login_name}</span>
                </div>
                <button type="button" onClick={onLogout}>
                  <LogOut size={16} aria-hidden="true" />
                  退出登录
                </button>
              </div>
            ) : null}
          </div>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
