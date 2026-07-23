import type {
  DeveloperViralAnalysisJob,
  PaginatedResult,
  VideoEditJobClaimRequest,
  VideoEditJobDeliverRequest,
  VideoEditJobView
} from "../types";
import { request } from "./client";


export const developerApi = {
  listVideoEditJobs: () =>
    request<VideoEditJobView[]>("/api/internal/video-edit/jobs"),
  claimVideoEditJob: (jobId: number, payload: VideoEditJobClaimRequest) =>
    request<VideoEditJobView>(`/api/internal/video-edit/jobs/${jobId}/claim`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deliverVideoEditJob: (jobId: number, payload: VideoEditJobDeliverRequest) =>
    request<VideoEditJobView>(`/api/internal/video-edit/jobs/${jobId}/deliver`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listViralAnalysisJobs: (params?: URLSearchParams) =>
    request<PaginatedResult<DeveloperViralAnalysisJob>>(
      `/api/developer/viral-analysis/jobs${params?.size ? `?${params.toString()}` : ""}`
    ),
  getViralAnalysisJob: (jobId: number) =>
    request<DeveloperViralAnalysisJob>(`/api/developer/viral-analysis/jobs/${jobId}`)
};
