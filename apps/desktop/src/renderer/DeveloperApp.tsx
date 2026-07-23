import { useEffect, useState } from "react";

import { api } from "./api/client";
import {
  DeveloperShell,
  type DeveloperPageKey
} from "./components/DeveloperShell";
import { DeveloperAIJobsPage } from "./pages/DeveloperAIJobsPage";
import { DeveloperVideoJobsPage } from "./pages/DeveloperVideoJobsPage";


function hasDeveloperRole(role: string) {
  return role === "platform_admin" || role === "developer_admin";
}


export function DeveloperApp() {
  const [activePage, setActivePage] = useState<DeveloperPageKey>("aiJobs");
  const [authState, setAuthState] = useState<"loading" | "ready" | "error">("loading");
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    let active = true;
    void api.getCurrentUser()
      .then((user) => {
        if (!active) return;
        if (!hasDeveloperRole(user.user_role)) {
          setAuthError("当前账号没有开发者端访问权限");
          setAuthState("error");
          return;
        }
        setAuthState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setAuthError(error instanceof Error ? error.message : "登录信息加载失败");
        setAuthState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  if (authState === "loading") {
    return <main className="auth-gate" role="status">正在验证开发者权限...</main>;
  }

  if (authState === "error") {
    return (
      <main className="auth-gate auth-gate-error">
        <h1>无法进入开发者端</h1>
        <p>{authError}</p>
      </main>
    );
  }

  return (
    <DeveloperShell activePage={activePage} onNavigate={setActivePage}>
      {activePage === "videoJobs" ? <DeveloperVideoJobsPage /> : <DeveloperAIJobsPage />}
    </DeveloperShell>
  );
}
