import { useEffect, useState } from "react";
import { BarChart3, CalendarClock, Scissors, UsersRound } from "lucide-react";

import { api } from "../api/client";
import type { AdminSummary } from "../types";


const emptySummary: AdminSummary = {
  total_users: 0,
  total_xhs_accounts: 0,
  total_matrix_plans: 0,
  total_video_edit_jobs: 0,
  pending_video_edit_jobs: 0
};


export function ManagerOverviewPage() {
  const [summary, setSummary] = useState<AdminSummary>(emptySummary);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getAdminSummary()
      .then((nextSummary) => {
        setSummary(nextSummary);
        setMessage("");
      })
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : "管理端数据加载失败");
      });
  }, []);

  return (
    <section className="page-stack">
      <div className="page-heading">
        <h1>管理端 · 运营总览</h1>
        <p>提供给禾一斯老板和管理层查看账号矩阵、发布计划、内容生产和智能剪辑进度。</p>
      </div>

      {message ? <div className="form-message">{message}</div> : null}

      <div className="metric-grid">
        <section className="panel metric-card">
          <UsersRound size={24} aria-hidden="true" />
          <span>系统用户</span>
          <strong>{summary.total_users}</strong>
        </section>
        <section className="panel metric-card">
          <BarChart3 size={24} aria-hidden="true" />
          <span>小红书账号</span>
          <strong>{summary.total_xhs_accounts}</strong>
        </section>
        <section className="panel metric-card">
          <CalendarClock size={24} aria-hidden="true" />
          <span>发布计划</span>
          <strong>{summary.total_matrix_plans}</strong>
        </section>
        <section className="panel metric-card">
          <Scissors size={24} aria-hidden="true" />
          <span>待处理剪辑</span>
          <strong>{summary.pending_video_edit_jobs}</strong>
        </section>
      </div>

      <section className="panel manager-note-panel">
        <h2>团队运营范围</h2>
        <p>当前数据按禾一斯团队隔离统计，用于查看成员规模、账号矩阵、发布计划和待处理剪辑任务。</p>
      </section>
    </section>
  );
}
