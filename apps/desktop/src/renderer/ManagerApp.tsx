import { useCallback, useEffect, useState } from "react";

import { managerApi } from "./api/managerClient";
import { ApiRequestError } from "./api/httpClient";
import { clearPortalToken } from "./auth/portalSession";
import {
  ManagerShell,
  type ManagerPageKey
} from "./components/ManagerShell";
import { PortalLoginPage } from "./components/PortalLoginPage";
import { ManagerBillingPage } from "./pages/ManagerBillingPage";
import { ManagerCreditLedgerPage } from "./pages/ManagerCreditLedgerPage";
import { ManagerInspirationPage } from "./pages/ManagerInspirationPage";
import { ManagerOverviewPage } from "./pages/ManagerOverviewPage";
import { ManagerProductLibraryPage } from "./pages/ManagerProductLibraryPage";
import { ManagerPublishingPage } from "./pages/ManagerPublishingPage";
import { ManagerUsersPage } from "./pages/ManagerUsersPage";
import { ManagerViralAnalysisPage } from "./pages/ManagerViralAnalysisPage";
import { ManagerXhsAccountsPage } from "./pages/ManagerXhsAccountsPage";
import type { AuthUser, LoginRequest } from "./types";


function hasManagerRole(user: AuthUser) {
  return user.user_role === "client_owner";
}


export function ManagerApp() {
  const [activePage, setActivePage] = useState<ManagerPageKey>("overview");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authState, setAuthState] = useState<
    "loading" | "login" | "ready" | "error"
  >("loading");
  const [authError, setAuthError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    void managerApi.getCurrentUser()
      .then((user) => {
        if (!active) return;
        if (!hasManagerRole(user)) {
          clearPortalToken("manager");
          setAuthError("当前账号没有管理端访问权限");
          setAuthState("login");
          return;
        }
        setAuthUser(user);
        setAuthState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiRequestError && error.status === 401) {
          clearPortalToken("manager");
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
    clearPortalToken("manager");
    try {
      const result = await managerApi.login(credentials);
      if (!hasManagerRole(result.user)) {
        clearPortalToken("manager");
        setAuthError("当前账号没有管理端访问权限");
        return;
      }
      setAuthUser(result.user);
      setActivePage("overview");
      setAuthState("ready");
    } catch (error) {
      clearPortalToken("manager");
      setAuthError(
        error instanceof ApiRequestError
          && (error.status === 401 || error.status === 403)
          ? "账号或密码错误，或账号没有管理权限"
          : "登录服务暂时不可用，请稍后重试"
      );
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const handleLogout = useCallback(() => {
    clearPortalToken("manager");
    setAuthUser(null);
    setAuthError("");
    setAuthState("login");
  }, []);

  if (authState === "loading") {
    return (
      <main className="auth-gate" role="status">
        正在验证管理权限...
      </main>
    );
  }

  if (authState === "login") {
    return (
      <PortalLoginPage
        portal="manager"
        error={authError}
        isSubmitting={isSubmitting}
        onSubmit={handleLogin}
      />
    );
  }

  if (authState === "error") {
    return (
      <main className="auth-gate auth-gate-error">
        <h1>暂时无法进入管理端</h1>
        <p>{authError}</p>
      </main>
    );
  }

  let page = <ManagerOverviewPage />;
  if (activePage === "users") page = <ManagerUsersPage />;
  if (activePage === "xhsAccounts") page = <ManagerXhsAccountsPage />;
  if (activePage === "publishing") page = <ManagerPublishingPage />;
  if (activePage === "inspiration") page = <ManagerInspirationPage />;
  if (activePage === "viralAnalysis") page = <ManagerViralAnalysisPage />;
  if (activePage === "billing") page = <ManagerBillingPage />;
  if (activePage === "creditLedger") page = <ManagerCreditLedgerPage />;
  if (activePage === "productLibrary") page = <ManagerProductLibraryPage />;

  return (
    <ManagerShell
      activePage={activePage}
      user={authUser}
      onNavigate={setActivePage}
      onLogout={handleLogout}
    >
      {page}
    </ManagerShell>
  );
}
