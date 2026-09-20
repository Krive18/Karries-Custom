import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiRequestError,
  customerApi
} from "./api/client";
import { clearPortalToken } from "./auth/portalSession";
import { AppShell } from "./components/AppShell";
import { PortalLoginPage } from "./components/PortalLoginPage";
import { ContentWorkspacePage } from "./pages/ContentWorkspacePage";
import { ContentCollectionPage } from "./pages/ContentCollectionPage";
import { InspirationPage } from "./pages/InspirationPage";
import { ProductLibraryPage } from "./pages/ProductLibraryPage";
import { PersonalCenterPage } from "./pages/PersonalCenterPage";
import { PublishTasksPage } from "./pages/PublishTasksPage";
import { RechargeCenterPage } from "./pages/RechargeCenterPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ViralAnalysisPage } from "./pages/ViralAnalysisPage";
import { AiTranslationPage } from "./pages/AiTranslationPage";
import { UserFeedbackPage } from "./pages/UserFeedbackPage";
import type {
  AccountView,
  AgentVideoCreationHandoff,
  AuthUser,
  CreateMode,
  LoginRequest,
  PageKey,
  ScheduledTask,
  TaskCreateRequest,
  TaskView,
  ViralAnalysisAgentHandoff,
  XHSAccountView
} from "./types";


const statusLabels: Record<number, ScheduledTask["status"]> = {
  1: "待提交",
  4: "提交中",
  5: "已提交平台",
  6: "失败"
};


function formatScheduleTime(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


function toScheduledTask(
  task: TaskView,
  accounts: AccountView[]
): ScheduledTask {
  const account = accounts.find((item) => item.id === task.account_id);
  return {
    id: task.id,
    accountId: task.account_id,
    account: account?.account_name ?? `账号 ${task.account_id}`,
    title: task.task_title,
    publishType: "图文笔记",
    scheduleTime: formatScheduleTime(task.schedule_time),
    scheduleTimestamp: task.schedule_time,
    status: statusLabels[task.status] ?? "待提交",
    body: task.task_body,
    tags: task.tags,
    imagePaths: task.image_paths,
    lastError: task.last_error
  };
}


export function App() {
  const [activePage, setActivePage] = useState<PageKey>("inspiration");
  const [createMode, setCreateMode] = useState<CreateMode>("video");
  const [pendingAgentHandoff, setPendingAgentHandoff] =
    useState<ViralAnalysisAgentHandoff | null>(null);
  const [videoCreationHandoff, setVideoCreationHandoff] =
    useState<AgentVideoCreationHandoff | null>(null);
  const [accounts, setAccounts] = useState<AccountView[]>([]);
  const [xhsAccounts, setXHSAccounts] = useState<XHSAccountView[]>([]);
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [appError, setAppError] = useState("");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authState, setAuthState] = useState<
    "loading" | "login" | "ready" | "error"
  >("loading");
  const [authError, setAuthError] = useState("");
  const [authSubmitting, setAuthSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [nextAccounts, nextTasks, nextXHSAccounts] = await Promise.all([
        customerApi.listAccounts(),
        customerApi.listTasks(),
        customerApi.listXHSAccounts()
      ]);
      setAccounts(nextAccounts);
      setXHSAccounts(nextXHSAccounts);
      setTasks(
        nextTasks.map((task) => toScheduledTask(task, nextAccounts))
      );
      setAppError("");
    } catch (error) {
      setAppError(
        error instanceof Error ? error.message : "服务连接失败"
      );
    }
  }, []);

  useEffect(() => {
    let active = true;
    void customerApi.getCurrentUser()
      .then((user) => {
        if (!active) return;
        if (user.user_role !== "customer") {
          clearPortalToken("customer");
          setAuthError("当前账号没有用户端访问权限");
          setAuthState("login");
          return;
        }
        setAuthUser(user);
        setAuthState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiRequestError && error.status === 401) {
          clearPortalToken("customer");
          setAuthError("");
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

  useEffect(() => {
    if (authState === "ready") {
      void loadData();
    }
  }, [authState, loadData]);

  const handleLogin = useCallback(async (credentials: LoginRequest) => {
    setAuthSubmitting(true);
    setAuthError("");
    clearPortalToken("customer");
    try {
      const response = await customerApi.login(credentials);
      if (response.user.user_role !== "customer") {
        clearPortalToken("customer");
        setAuthError("当前账号没有用户端访问权限");
        return;
      }
      setAuthUser(response.user);
      setActivePage("inspiration");
      setAuthState("ready");
    } catch (error) {
      clearPortalToken("customer");
      setAuthError(
        error instanceof ApiRequestError
          && (error.status === 401 || error.status === 403)
          ? "账号或密码错误，请重新输入"
          : "登录服务暂时不可用，请稍后重试"
      );
    } finally {
      setAuthSubmitting(false);
    }
  }, []);

  const handleLogout = useCallback(() => {
    clearPortalToken("customer");
    setAuthUser(null);
    setAccounts([]);
    setXHSAccounts([]);
    setTasks([]);
    setAppError("");
    setAuthError("");
    setAuthState("login");
  }, []);

  const handleCreateTask = useCallback(async (
    payload: TaskCreateRequest
  ) => {
    let draftId = payload.draft_id ?? 0;
    if (draftId > 0) {
      await customerApi.updateContentDraft(draftId, {
        title: payload.task_title,
        body: payload.task_body,
        tags: payload.tags,
        status: "confirmed"
      });
    } else {
      const draft = await customerApi.createManualContentDraft({
        xhs_account_id: payload.account_id,
        content_type: "image_text",
        title: payload.task_title,
        body: payload.task_body,
        tags: payload.tags,
        material_ids: payload.material_ids ?? []
      });
      draftId = draft.id;
    }
    const result = await customerApi.createMatrixPlanFromDrafts({
      plan_name: `${payload.task_title} 发布计划`,
      draft_ids: [draftId],
      xhs_account_ids: [payload.account_id],
      schedule_start_time: payload.schedule_time,
      schedule_end_time: payload.schedule_time,
      min_interval_minutes: 360
    });
    await customerApi.confirmMatrixPlan(result.id);
    setActivePage("schedule");
  }, []);

  const handleSubmitTask = useCallback(async (taskId: number) => {
    setTasks((current) =>
      current.map((task) =>
        task.id === taskId ? { ...task, status: "提交中" } : task
      )
    );
    const submittedTask = await customerApi.submitTask(taskId);
    setTasks((current) =>
      current.map((task) =>
        task.id === taskId
          ? toScheduledTask(submittedTask, accounts)
          : task
      )
    );
  }, [accounts]);

  const page = useMemo(() => {
    if (activePage === "inspiration") {
      return (
        <InspirationPage
          initialHandoff={pendingAgentHandoff}
          onInitialHandoffConsumed={(key) => {
            setPendingAgentHandoff((current) =>
              current?.key === key ? null : current
            );
          }}
          onSendToVideoCreation={(handoff) => {
            setVideoCreationHandoff(handoff);
            setCreateMode("video");
            setActivePage("create");
          }}
        />
      );
    }
    if (activePage === "productLibrary") {
      return <ProductLibraryPage />;
    }
    if (activePage === "viralAnalysis") {
      return (
        <ViralAnalysisPage
          onStartInspiration={(handoff) => {
            setPendingAgentHandoff(handoff);
            setActivePage("inspiration");
          }}
        />
      );
    }
    if (activePage === "aiTranslation") {
      return <AiTranslationPage />;
    }
    if (activePage === "publishReview") {
      return <PublishTasksPage mode="review" />;
    }
    if (activePage === "contentCollection") {
      return <ContentCollectionPage />;
    }
    if (activePage === "schedule") {
      return <PublishTasksPage mode="plans" />;
    }
    if (activePage === "settings") {
      return <SettingsPage />;
    }
    if (activePage === "recharge") {
      return <RechargeCenterPage />;
    }
    if (activePage === "profile" && authUser) {
      return (
        <PersonalCenterPage
          user={authUser}
          onOpenRecharge={() => setActivePage("recharge")}
        />
      );
    }
    if (activePage === "feedback") {
      return <UserFeedbackPage />;
    }
    return (
      <ContentWorkspacePage
        accounts={xhsAccounts.filter(
          (account) => account.status === 1 && account.login_state_ready
        )}
        mode={createMode}
        initialVideoHandoff={videoCreationHandoff}
        onInitialVideoHandoffConsumed={(key) => {
          setVideoCreationHandoff((current) =>
            current?.key === key ? null : current
          );
        }}
        onCreateTask={handleCreateTask}
      />
    );
  }, [
    accounts,
    activePage,
    authUser,
    createMode,
    handleCreateTask,
    loadData,
    pendingAgentHandoff,
    tasks,
    videoCreationHandoff,
    xhsAccounts
  ]);

  if (authState === "loading") {
    return (
      <main className="auth-gate" role="status">
        正在验证登录信息...
      </main>
    );
  }

  if (authState === "login") {
    return (
      <PortalLoginPage
        portal="customer"
        error={authError}
        isSubmitting={authSubmitting}
        onSubmit={handleLogin}
      />
    );
  }

  if (authState === "error") {
    return (
      <main className="auth-gate auth-gate-error">
        <h1>暂时无法连接系统</h1>
        <p>{authError}</p>
        <button
          className="secondary-button"
          type="button"
          onClick={() => setAuthState("login")}
        >
          返回登录
        </button>
      </main>
    );
  }

  return (
    <AppShell
      activePage={activePage}
      activeCreateMode={createMode}
      user={authUser}
      onNavigate={setActivePage}
      onCreateModeChange={(mode) => {
        setCreateMode(mode === "image" ? "video" : mode);
        setActivePage("create");
      }}
      onLogout={handleLogout}
    >
      {appError ? <div className="app-alert">{appError}</div> : null}
      {page}
    </AppShell>
  );
}
