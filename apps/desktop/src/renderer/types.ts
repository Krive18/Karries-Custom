export type PortalKey = "user" | "manager" | "developer";

export type PageKey =
  | "create"
  | "inspiration"
  | "viralAnalysis"
  | "videoEdit"
  | "schedule"
  | "managerOverview"
  | "managerInspiration"
  | "managerViralAnalysis"
  | "developerVideoJobs"
  | "developerAIJobs"
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

export type XHSAccountProfile = {
  domain_name: string;
  persona: string;
  target_audience: string;
  content_style: string;
  tone: string;
  common_phrases: string;
  forbidden_phrases: string;
  tag_preferences: string;
  word_count_preference: number;
  topic_preferences: string;
};

export type XHSAccountView = {
  id: number;
  user_id: number;
  display_name: string;
  account_group: string;
  status: number;
  daily_limit: number;
  min_interval_minutes: number;
  last_publish_time: number;
  today_publish_count: number;
  login_state_path: string;
  create_time: number;
  update_time: number;
  profile: XHSAccountProfile & {
    id?: number;
    create_time?: number;
    update_time?: number;
  };
};

export type XHSAccountCreate = {
  display_name: string;
  account_group: string;
  daily_limit: number;
  min_interval_minutes: number;
  profile: XHSAccountProfile;
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

export type InspirationGoalType = "topic" | "title" | "body" | "script" | "strategy" | "optimize";
export type InspirationSessionStatus = "active" | "generating" | "archived";
export type InspirationMessageRole = "user" | "assistant";
export type InspirationMessageStatus = "success" | "failed";

export type InspirationSession = {
  id: number;
  tenant_id: number;
  user_id: number;
  title: string;
  linked_product_id: number;
  linked_xhs_account_id: number;
  goal_type: InspirationGoalType;
  tone: string;
  extra_requirement: string;
  generation_token: string;
  generation_started_time: number;
  status: InspirationSessionStatus;
  message_count: number;
  total_credit_cost: number;
  create_time: number;
  update_time: number;
};

export type InspirationMessage = {
  id: number;
  tenant_id: number;
  session_id: number;
  user_id: number;
  role: InspirationMessageRole;
  content: string;
  context: Record<string, unknown>;
  ai_provider: string;
  ai_model: string;
  credit_cost: number;
  latency_ms: number;
  status: InspirationMessageStatus;
  error_message: string;
  content_draft_id: number;
  create_time: number;
};

export type InspirationSessionDetail = {
  session: InspirationSession;
  messages: InspirationMessage[];
};

export type PaginatedResult<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type InspirationSessionCreate = {
  title: string;
  linked_product_id: number;
  linked_xhs_account_id: number;
  goal_type: InspirationGoalType;
  tone: string;
  extra_requirement: string;
};

export type InspirationMessageCreate = {
  content: string;
};

export type InspirationMessageResponse = {
  user_message: InspirationMessage;
  assistant_message: InspirationMessage;
  credit_cost: number;
};

export type AuthUser = {
  id: number;
  tenant_id: number;
  login_name: string;
  nickname: string;
  user_role: "customer" | "client_owner" | "client_admin" | "platform_admin" | "developer_admin";
  wallet_balance: number;
};

export type ViralAnalysisStatus = "pending" | "processing" | "completed" | "failed" | "cancelled";
export type ViralAnalysisSourceType = "upload" | "link" | "text";
export type ViralAnalysisGoal = "hook" | "structure" | "rhythm" | "script" | "selling" | "reuse";

export type ViralAnalysisResult = {
  hook_summary: string;
  structure_summary: string;
  shot_rhythm: string;
  script_breakdown: string;
  selling_points: string;
  reuse_suggestions: string;
  rewritten_script: string;
  tags: string[];
  create_time: number;
};

export type ViralAnalysisMaterial = {
  id: number;
  job_id: number;
  file_name: string;
  file_type: "image" | "video" | "document" | "other";
  mime_type: string;
  file_size: number;
  create_time: number;
};

export type ViralAnalysisJob = {
  id: number;
  tenant_id: number;
  user_id: number;
  title: string;
  source_type: ViralAnalysisSourceType;
  source_url: string;
  material_file_id: number;
  analysis_goal: ViralAnalysisGoal[];
  supplement_text: string;
  status: ViralAnalysisStatus;
  credit_cost: number;
  create_time: number;
  update_time: number;
  materials?: ViralAnalysisMaterial[];
  result?: ViralAnalysisResult | null;
};

export type ViralAnalysisJobCreate = {
  title: string;
  source_type: ViralAnalysisSourceType;
  source_url: string;
  analysis_goal: ViralAnalysisGoal[];
  supplement_text: string;
};

export type DeveloperAIUsage = {
  id: number;
  status: "success" | "failed";
  provider: string;
  model_name: string;
  latency_ms: number;
  input_chars: number;
  output_chars: number;
  credit_cost: number;
  error_message: string;
  create_time: number;
};

export type DeveloperViralAnalysisJob = ViralAnalysisJob & {
  ai_provider: string;
  ai_model: string;
  error_message: string;
  latest_ai_usage: DeveloperAIUsage | null;
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
