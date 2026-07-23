import { RefreshCw, Send, SquarePen } from "lucide-react";

import { StatusBadge } from "../components/StatusBadge";
import type { ScheduledTask } from "../types";


type PublishTasksPageProps = {
  tasks: ScheduledTask[];
  onCreate: () => void;
  onRefresh: () => void;
  onSubmitTask: (taskId: number) => void;
};


export function PublishTasksPage({ tasks, onCreate, onRefresh, onSubmitTask }: PublishTasksPageProps) {
  return (
    <section className="page-stack">
      <div className="page-heading horizontal-heading">
        <div>
          <h1>定时发布任务</h1>
          <p>管理已经生成的小红书图文任务，并提交到平台内置定时发布。</p>
        </div>
        <div className="heading-actions">
          <button className="primary-button compact" type="button" onClick={onCreate}>
            <SquarePen size={17} aria-hidden="true" />
            新建任务
          </button>
          <button className="secondary-button compact" type="button" onClick={onRefresh}>
            <RefreshCw size={16} aria-hidden="true" />
            刷新状态
          </button>
        </div>
      </div>

      <section className="panel task-panel">
        <table className="task-table">
          <thead>
            <tr>
              <th>账号</th>
              <th>标题</th>
              <th>类型</th>
              <th>发布时间</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={6}>暂无任务，请先新建小红书图文发布任务。</td>
              </tr>
            ) : tasks.map((task) => (
              <tr key={task.id}>
                <td>{task.account}</td>
                <td>{task.title}</td>
                <td>{task.publishType}</td>
                <td>{task.scheduleTime}</td>
                <td><StatusBadge status={task.status} /></td>
                <td>
                  <button
                    className="table-action"
                    type="button"
                    onClick={() => {
                      if (task.status === "待提交") {
                        onSubmitTask(task.id);
                      }
                    }}
                  >
                    <Send size={15} aria-hidden="true" />
                    {task.status === "待提交" ? "提交" : "查看日志"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </section>
  );
}
