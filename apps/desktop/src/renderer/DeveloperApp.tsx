import { useCallback, useEffect, useState } from "react";

import { developerApi } from "./api/developerClient";
import { ApiRequestError } from "./api/httpClient";
import { clearPortalToken } from "./auth/portalSession";
import {
  DeveloperShell,
  type DeveloperPageKey
} from "./components/DeveloperShell";
import { PortalLoginPage } from "./components/PortalLoginPage";
import { DeveloperAIJobsPage } from "./pages/DeveloperAIJobsPage";
import { DeveloperAISettingsPage } from "./pages/DeveloperAISettingsPage";
import { DeveloperAccessPage } from "./pages/DeveloperAccessPage";
import { DeveloperAlertsPage } from "./pages/DeveloperAlertsPage";
import { DeveloperAuditPage } from "./pages/DeveloperAuditPage";
import { DeveloperBillingPage } from "./pages/DeveloperBillingPage";
import { DeveloperOverviewPage } from "./pages/DeveloperOverviewPage";
import { DeveloperTasksPage } from "./pages/DeveloperTasksPage";
import { DeveloperUsersPage } from "./pages/DeveloperUsersPage";
import { DeveloperVideoJobsPage } from "./pages/DeveloperVideoJobsPage";
import { DeveloperAITranslationPage } from "./pages/DeveloperAITranslationPage";
import { DeveloperFeedbackPage } from "./pages/DeveloperFeedbackPage";
import type { AuthUser, LoginRequest } from "./types";


function hasDeveloperRole(user: AuthUser) {
  return user.user_role === "platform_admin"
    || user.user_role === "developer_admin";
}


export function DeveloperApp() {
  const [activePage, setActivePage] = useState<DeveloperPageKey>("overview");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authState, setAuthState] = useState<
    "loading" | "login" | "ready" | "error"
  >("loading");
  const [authError, setAuthError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    void developerApi.getCurrentUser()
      .then((user) => {
        if (!active) return;
        if (!hasDeveloperRole(user)) {
          clearPortalToken("developer");
          setAuthError("当前账号没有开发者端访问权限");
          setAuthState("login");
          return;
        }
        setAuthUser(user);
        setAuthState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiRequestError && error.status === 401) {
          clearPortalToken("developer");
          setAuthState("login");
          return;
        }
        setAuthError(
          error instanceof Error ? error.message : "登录信息加载失败"
        );
        setAuthState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  const handleLogin = useCallback(async (credentials: LoginRequest) => {
    setIsSubmitting(true);
    setAuthError("");
    clearPortalToken("developer");
    try {
      const result = await developerApi.login(credentials);
      if (!hasDeveloperRole(result.user)) {
        clearPortalToken("developer");
        setAuthError("当前账号没有开发者端访问权限");
        return;
      }
      setAuthUser(result.user);
      setAuthState("ready");
    } catch (error) {
      clearPortalToken("developer");
      setAuthError(
        error instanceof ApiRequestError
          && (error.status === 401 || error.status === 403)
          ? "账号或密码错误，或账号没有内部权限"
          : "登录服务暂时不可用，请稍后重试"
      );
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const handleLogout = useCallback(() => {
    clearPortalToken("developer");
    setAuthUser(null);
    setAuthError("");
    setAuthState("login");
  }, []);

  if (authState === "loading") {
    return (
      <main className="auth-gate" role="status">
        正在验证开发者权限...
      </main>
    );
  }

  if (authState === "login") {
    return (
      <PortalLoginPage
        portal="developer"
        error={authError}
        isSubmitting={isSubmitting}
        onSubmit={handleLogin}
      />
    );
  }

  if (authState === "error") {
    return (
      <main className="auth-gate auth-gate-error">
        <h1>暂时无法进入内部系统</h1>
        <p>{authError}</p>
      </main>
    );
  }

  return (
    <DeveloperShell
      activePage={activePage}
      user={authUser}
      onNavigate={setActivePage}
      onLogout={handleLogout}
    >
      {activePage === "overview" ? <DeveloperOverviewPage onNavigate={setActivePage} /> : null}
      {activePage === "tasks" ? <DeveloperTasksPage /> : null}
      {activePage === "alerts" ? <DeveloperAlertsPage /> : null}
      {activePage === "videoJobs" ? <DeveloperVideoJobsPage currentUser={authUser} /> : null}
      {activePage === "translationJobs" ? <DeveloperAITranslationPage /> : null}
      {activePage === "aiJobs" ? <DeveloperAIJobsPage /> : null}
      {activePage === "feedback" ? <DeveloperFeedbackPage /> : null}
      {activePage === "billing" ? <DeveloperBillingPage /> : null}
      {activePage === "aiSettings" ? <DeveloperAISettingsPage /> : null}
      {activePage === "customers" ? <DeveloperUsersPage /> : null}
      {activePage === "access" ? <DeveloperAccessPage currentUser={authUser} /> : null}
      {activePage === "audit" ? <DeveloperAuditPage /> : null}
    </DeveloperShell>
  );
}
