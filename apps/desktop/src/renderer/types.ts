export type PortalKey = "user" | "manager" | "developer";

export type PageKey =
  | "create"
  | "videoEdit"
  | "schedule"
  | "managerOverview"
  | "developerVideoJobs"
  | "settings";

export type ScheduledTask = {
  id: number;
  accountId: number;
  account: string;
  title: string;
  publishType: string;
  scheduleTime: string;
  status: "待提交" | "提交中" | "已提交平台" | "失败";
  body: string;
  tags: string[];
  imagePaths: string[];
  scheduleTimestamp: number;
  lastError: string;
};

export type ProviderOption = {
  label: string;
  value: string;
  models: string[];
};

export type ApiResponse<T> = {
  success: boolean;
  data: T;
  error: null | {
    code: string;
    message: string;
  };
};

export type AccountView = {
  id: number;
  account_name: string;
  platform: string;
  cookie_path: string;
  status: number;
  last_checked_time: number;
  create_time: number;
  update_time: number;
};

export type AccountCreateRequest = {
  account_name: string;
  cookie_path: string;
};

export type TaskView = {
  id: number;
  account_id: number;
  task_title: string;
  task_body: string;
  tags: string[];
  image_paths: string[];
  schedule_time: number;
  status: number;
  last_error: string;
  submitted_time: number;
  create_time: number;
  update_time: number;
};

export type TaskCreateRequest = {
  account_id: number;
  task_title: string;
  task_body: string;
  tags: string[];
  image_paths: string[];
  schedule_time: number;
};

export type ImageCopyRequest = {
  image_paths: string[];
  style: string;
  extra_prompt: string;
};

export type ImageCopyResult = {
  title: string;
  body: string;
  tags: string[];
};

export type AISettingSlot = "vision" | "copywriting";

export type AISettingView = {
  provider: string;
  base_url: string;
  model: string;
  enabled: boolean;
  has_key: boolean;
  masked_key: string;
};

export type AISettingsView = {
  vision: AISettingView;
  copywriting: AISettingView;
};

export type AISettingUpdate = {
  provider: string;
  api_key: string;
  base_url: string;
  model: string;
  enabled: boolean;
};

export type VideoEditMaterial = {
  file_name: string;
  file_type: "image" | "video" | "document" | "other";
  file_path: string;
  mime_type: string;
  file_size: number;
  remark: string;
};

export type VideoEditJobCreate = {
  job_title: string;
  script_text: string;
  requirement_text: string;
  materials: VideoEditMaterial[];
};

export type VideoEditJobView = {
  id: number;
  user_id: number;
  job_title: string;
  script_text: string;
  requirement_text: string;
  materials: VideoEditMaterial[];
  status: number;
  status_name: "submitted" | "in_production" | "delivered" | "revision_requested" | "cancelled";
  status_text: string;
  user_progress_text: string;
  expected_delivery_time: number;
  operator_user_id: number;
  developer_note: string;
  delivery: Record<string, unknown>;
  delivered_time: number;
  create_time: number;
  update_time: number;
};

export type VideoEditJobClaimRequest = {
  note: string;
};

export type VideoEditJobDeliverRequest = {
  delivery_file_name: string;
  delivery_file_path: string;
  delivery_url: string;
  note: string;
};

export type AdminSummary = {
  total_users: number;
  total_xhs_accounts: number;
  total_matrix_plans: number;
  total_video_edit_jobs: number;
  pending_video_edit_jobs: number;
};

export type DesktopBridge = {
  version: string;
  selectMaterials?: () => Promise<string[]>;
};

declare global {
  interface Window {
    karriesPublisher?: DesktopBridge;
  }
}
