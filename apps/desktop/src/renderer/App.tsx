import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api/client";
import { AppShell } from "./components/AppShell";
import { DeveloperVideoJobsPage } from "./pages/DeveloperVideoJobsPage";
import { ManagerOverviewPage } from "./pages/ManagerOverviewPage";
import { SmartCreatePage } from "./pages/SmartCreatePage";
import { PublishTasksPage } from "./pages/PublishTasksPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VideoEditPage } from "./pages/VideoEditPage";
import type {
  AccountView,
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
    setActivePortal(portal);
    if (portal === "user") {
      setActivePage("create");
    } else if (portal === "manager") {
      setActivePage("managerOverview");
    } else {
      setActivePage("developerVideoJobs");
    }
  }, []);

  const page = useMemo(() => {
    if (activePage === "videoEdit") {
      return <VideoEditPage />;
    }
    if (activePage === "managerOverview") {
      return <ManagerOverviewPage />;
    }
    if (activePage === "developerVideoJobs") {
      return <DeveloperVideoJobsPage />;
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
      onNavigate={setActivePage}
      onPortalChange={handlePortalChange}
    >
      {appError ? <div className="app-alert">{appError}</div> : null}
      {page}
    </AppShell>
  );
}
