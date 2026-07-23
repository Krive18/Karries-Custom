import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, PackageOpen, PlayCircle } from "lucide-react";

import { developerApi } from "../api/developerClient";
import type { VideoEditJobView } from "../types";


function formatDateTime(timestamp: number) {
  if (!timestamp) {
    return "待确认";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


export function DeveloperVideoJobsPage() {
  const [jobs, setJobs] = useState<VideoEditJobView[]>([]);
  const [message, setMessage] = useState("");
  const [busyJobId, setBusyJobId] = useState<number | null>(null);

  async function loadJobs() {
    try {
      setJobs(await developerApi.listVideoEditJobs());
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "开发者工单加载失败");
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  async function claimJob(job: VideoEditJobView) {
    setBusyJobId(job.id);
    try {
      const updated = await developerApi.claimVideoEditJob(job.id, {
        note: "已进入内部剪辑排期"
      });
      setJobs((current) => current.map((item) => item.id === job.id ? updated : item));
      setMessage("工单已接入内部剪辑流程");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "接单失败");
    } finally {
      setBusyJobId(null);
    }
  }

  async function deliverJob(job: VideoEditJobView) {
    setBusyJobId(job.id);
    try {
      const updated = await developerApi.deliverVideoEditJob(job.id, {
        delivery_file_name: `${job.job_title}-成片.mp4`,
        delivery_file_path: `/deliveries/video-edit-${job.id}.mp4`,
        delivery_url: "",
        note: "内部剪辑已完成，等待客户确认"
      });
      setJobs((current) => current.map((item) => item.id === job.id ? updated : item));
      setMessage("成片已交付到用户端");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "交付失败");
    } finally {
      setBusyJobId(null);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-heading horizontal-heading">
        <div>
          <h1>开发者端 · 剪辑工单</h1>
          <p>该页面仅供点绘环球内部查看客户素材、剪辑脚本和交付状态，不在客户侧暴露。</p>
        </div>
        <button className="secondary-button compact" type="button" onClick={loadJobs}>
          <PackageOpen size={16} aria-hidden="true" />
          刷新工单
        </button>
      </div>

      {message ? <div className="form-message">{message}</div> : null}

      <section className="developer-job-board">
        {jobs.length === 0 ? (
          <div className="panel empty-list-state">暂无智能剪辑工单。</div>
        ) : jobs.map((job) => (
          <article className="panel developer-job-card" key={job.id}>
            <div className="developer-job-head">
              <div>
                <span className="eyebrow">工单 #{job.id} · 用户 {job.user_id}</span>
                <h2>{job.job_title}</h2>
              </div>
              <span className={job.status === 3 ? "key-status connected" : "key-status"}>
                {job.status_text}
              </span>
            </div>

            <div className="developer-job-grid">
              <div>
                <strong>剪辑脚本</strong>
                <p>{job.script_text}</p>
              </div>
              <div>
                <strong>补充要求</strong>
                <p>{job.requirement_text || "无补充要求"}</p>
              </div>
              <div>
                <strong>预计交付</strong>
                <p>{formatDateTime(job.expected_delivery_time)}</p>
              </div>
              <div>
                <strong>内部备注</strong>
                <p>{job.developer_note || "暂无备注"}</p>
              </div>
            </div>

            <div className="material-list developer-material-list">
              {job.materials.length === 0 ? (
                <div>
                  <strong>未上传素材</strong>
                  <span>需要联系用户补充素材</span>
                </div>
              ) : job.materials.map((material) => (
                <div key={`${job.id}-${material.file_name}`}>
                  <strong>{material.file_name}</strong>
                  <span>{material.file_type} · {material.file_path || "待同步文件路径"}</span>
                </div>
              ))}
            </div>

            <div className="primary-row">
              <button
                className="secondary-button"
                type="button"
                disabled={busyJobId === job.id || ![1, 4].includes(job.status)}
                onClick={() => claimJob(job)}
              >
                {busyJobId === job.id ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <PlayCircle size={16} aria-hidden="true" />}
                接入内部剪辑
              </button>
              <button
                className="primary-button"
                type="button"
                disabled={busyJobId === job.id || job.status !== 2}
                onClick={() => deliverJob(job)}
              >
                {busyJobId === job.id ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
                上传交付结果
              </button>
            </div>
          </article>
        ))}
      </section>
    </section>
  );
}
