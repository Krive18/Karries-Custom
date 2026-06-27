import { useMemo, useState } from "react";

import { AppShell } from "./components/AppShell";
import { SmartCreatePage } from "./pages/SmartCreatePage";
import { PublishTasksPage } from "./pages/PublishTasksPage";
import { SettingsPage } from "./pages/SettingsPage";
import type { PageKey, ScheduledTask } from "./types";


const initialTasks: ScheduledTask[] = [
  {
    id: 1,
    account: "品牌运营号",
    title: "夏日通勤穿搭灵感",
    publishType: "图文笔记",
    scheduleTime: "06/27 18:30",
    status: "待提交"
  },
  {
    id: 2,
    account: "禾一斯门店号",
    title: "新品到店试穿记录",
    publishType: "图文笔记",
    scheduleTime: "06/28 10:00",
    status: "已提交平台"
  }
];


export function App() {
  const [activePage, setActivePage] = useState<PageKey>("create");
  const [tasks, setTasks] = useState<ScheduledTask[]>(initialTasks);

  const page = useMemo(() => {
    if (activePage === "schedule") {
      return <PublishTasksPage tasks={tasks} onCreate={() => setActivePage("create")} />;
    }
    if (activePage === "settings") {
      return <SettingsPage />;
    }
    return <SmartCreatePage onSaveTask={(task) => setTasks((current) => [task, ...current])} />;
  }, [activePage, tasks]);

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      {page}
    </AppShell>
  );
}
