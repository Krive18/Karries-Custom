import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api/client";
import { AppShell } from "./components/AppShell";
import { DeveloperVideoJobsPage } from "./pages/DeveloperVideoJobsPage";
import { DeveloperAIJobsPage } from "./pages/DeveloperAIJobsPage";
import { ManagerOverviewPage } from "./pages/ManagerOverviewPage";
import { ManagerInspirationPage } from "./pages/ManagerInspirationPage";
import { InspirationPage } from "./pages/InspirationPage";
import { ManagerViralAnalysisPage } from "./pages/ManagerViralAnalysisPage";
import { SmartCreatePage } from "./pages/SmartCreatePage";
import { PublishTasksPage } from "./pages/PublishTasksPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VideoEditPage } from "./pages/VideoEditPage";
import { ViralAnalysisPage } from "./pages/ViralAnalysisPage";
import type {
  AccountView,
  AuthUser,
  PageKey,
  PortalKey,
  ScheduledTask,
  TaskCreateRequest,
  TaskView
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


function toScheduledTask(task: TaskView, accounts: AccountView[]): ScheduledTask {
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
  const [activePortal, setActivePortal] = useState<PortalKey>("user");
  const [activePage, setActivePage] = useState<PageKey>("create");
  const [accounts, setAccounts] = useState<AccountView[]>([]);
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [appError, setAppError] = useState("");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [nextAccounts, nextTasks] = await Promise.all([
        api.listAccounts(),
        api.listTasks()
      ]);
      setAccounts(nextAccounts);
      setTasks(nextTasks.map((task) => toScheduledTask(task, nextAccounts)));
      setAppError("");
    } catch (error) {
      setAppError(error instanceof Error ? error.message : "本地服务连接失败");
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    let active = true;
    void api.getCurrentUser().then((user) => {
      if (active) setAuthUser(user);
    }).catch((error: unknown) => {
      if (active) setAppError(error instanceof Error ? error.message : "登录信息加载失败");
    });
    return () => { active = false; };
  }, []);

  const allowedPortals: PortalKey[] = authUser?.user_role === "platform_admin" || authUser?.user_role === "developer_admin"
    ? ["developer"]
    : authUser?.user_role === "client_owner" || authUser?.user_role === "client_admin"
      ? ["user", "manager"]
      : ["user"];

  const handleCreateTask = useCallback(async (payload: TaskCreateRequest) => {
    const createdTask = await api.createTask(payload);
    setTasks((current) => [
      toScheduledTask(createdTask, accounts),
      ...current.filter((task) => task.id !== createdTask.id)
    ]);
    setActivePage("schedule");
  }, [accounts]);

  const handleSubmitTask = useCallback(async (taskId: number) => {
    setTasks((current) =>
      current.map((task) => task.id === taskId ? { ...task, status: "提交中" } : task)
    );
    const submittedTask = await api.submitTask(taskId);
    setTasks((current) =>
      current.map((task) =>
        task.id === taskId ? toScheduledTask(submittedTask, accounts) : task
      )
    );
  }, [accounts]);

  const handlePortalChange = useCallback((portal: PortalKey) => {
    if (!allowedPortals.includes(portal)) return;
    setActivePortal(portal);
    if (portal === "user") {
      setActivePage("create");
    } else if (portal === "manager") {
      setActivePage("managerOverview");
    } else {
      setActivePage("developerVideoJobs");
    }
  }, [allowedPortals]);

  useEffect(() => {
    if (!allowedPortals.includes(activePortal)) {
      setActivePortal(allowedPortals[0]);
      setActivePage(allowedPortals[0] === "developer" ? "developerAIJobs" : "create");
    }
  }, [activePortal, allowedPortals]);

  const page = useMemo(() => {
    if (activePage === "videoEdit") {
      return <VideoEditPage />;
    }
    if (activePage === "inspiration") {
      return <InspirationPage />;
    }
    if (activePage === "viralAnalysis") {
      return <ViralAnalysisPage onStartInspiration={() => setActivePage("inspiration")} />;
    }
    if (activePage === "managerOverview") {
      return <ManagerOverviewPage />;
    }
    if (activePage === "managerInspiration") {
      return <ManagerInspirationPage />;
    }
    if (activePage === "managerViralAnalysis") {
      return <ManagerViralAnalysisPage />;
    }
    if (activePage === "developerVideoJobs") {
      return <DeveloperVideoJobsPage />;
    }
    if (activePage === "developerAIJobs") {
      return <DeveloperAIJobsPage />;
    }
    if (activePage === "schedule") {
      return (
        <PublishTasksPage
          tasks={tasks}
          onCreate={() => setActivePage("create")}
          onRefresh={loadData}
          onSubmitTask={handleSubmitTask}
        />
      );
    }
    if (activePage === "settings") {
      return <SettingsPage />;
    }
    return (
      <SmartCreatePage
        accounts={accounts}
        onCreateTask={handleCreateTask}
      />
    );
  }, [accounts, activePage, handleCreateTask, handleSubmitTask, loadData, tasks]);

  return (
    <AppShell
      activePage={activePage}
      activePortal={activePortal}
      allowedPortals={allowedPortals}
      onNavigate={setActivePage}
      onPortalChange={handlePortalChange}
    >
      {appError ? <div className="app-alert">{appError}</div> : null}
      {page}
    </AppShell>
  );
}
