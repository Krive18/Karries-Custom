export type PortalKey = "user" | "manager" | "developer";
export type CustomerPortalKey = Exclude<PortalKey, "developer">;
export type CreateMode = "image" | "video";

export type PageKey =
  | "create"
  | "productLibrary"
  | "inspiration"
  | "viralAnalysis"
  | "aiTranslation"
  | "videoEdit"
  | "publishReview"
  | "contentCollection"
  | "schedule"
  | "managerOverview"
  | "managerInspiration"
  | "managerViralAnalysis"
  | "developerVideoJobs"
  | "developerAIJobs"
  | "recharge"
  | "profile"
  | "feedback"
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
  draft_id?: number;
  account_id: number;
  task_title: string;
  task_body: string;
  tags: string[];
  image_paths: string[];
  material_ids?: number[];
  schedule_time: number;
};

export type ImageCopyRequest = {
  image_paths: string[];
  material_ids?: number[];
  xhs_account_id?: number;
  style: string;
  extra_prompt: string;
};

export type ImageCopyResult = {
  title: string;
  body: string;
  tags: string[];
  history_id?: number;
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
  login_state_ready: boolean;
  create_time: number;
  update_time: number;
  profile: XHSAccountProfile & {
    id?: number;
    create_time?: number;
    update_time?: number;
  };
};

export type XHSAccountLoginStatus =
  | "starting"
  | "awaiting_scan"
  | "success"
  | "failed"
  | "timeout"
  | "cancelled";

export type XHSAccountLoginSession = {
  id: number;
  xhs_account_id: number;
  status: XHSAccountLoginStatus;
  message: string;
  qrcode_image_data: string;
  started_time: number;
  expires_time: number;
  completed_time: number;
  create_time: number;
  update_time: number;
};

export type XHSAccountLoginCheck = {
  valid: boolean;
  account: XHSAccountView;
};

export type XHSAccountCreate = {
  display_name: string;
  account_group: string;
  daily_limit: number;
  min_interval_minutes: number;
  profile: XHSAccountProfile;
};

export type ContentDraftStatus = "draft" | "confirmed" | "rejected";

export type ContentDraftView = {
  id: number;
  user_id: number;
  product_id: number;
  xhs_account_id: number;
  source_type: string;
  content_type: "image_text" | "video";
  title: string;
  body: string;
  tags: string[];
  material: Record<string, unknown>;
  status: ContentDraftStatus;
  ai_provider: string;
  model_name: string;
  prompt: Record<string, unknown>;
  create_time: number;
  update_time: number;
};

export type ContentDraftUpdate = {
  title?: string;
  body?: string;
  tags?: string[];
  status?: ContentDraftStatus;
};

export type ContentDraftManualCreate = {
  xhs_account_id: number;
  content_type: "image_text";
  title: string;
  body: string;
  tags: string[];
  material_ids: number[];
};

export type MatrixPlanStatus = 1 | 2 | 3 | 4 | 5 | 6 | 7;
export type MatrixPlanItemStatus = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type MatrixPlanView = {
  id: number;
  user_id: number;
  plan_name: string;
  source_type: string;
  content_type: string;
  product_id: number;
  status: MatrixPlanStatus;
  schedule_start_time: number;
  schedule_end_time: number;
  scheduling_rule: Record<string, unknown>;
  item_count: number;
  create_time: number;
  update_time: number;
};

export type MatrixPlanItemView = {
  id: number;
  plan_id: number;
  user_id: number;
  xhs_account_id: number;
  content_type: string;
  title: string;
  body: string;
  tags: string[];
  material: Record<string, unknown>;
  scheduled_time: number;
  status: MatrixPlanItemStatus;
  last_error: string;
  attempt_count: number;
  max_attempts: number;
  next_retry_time: number;
  submitted_time: number;
  publish_result: Record<string, unknown>;
  create_time: number;
  update_time: number;
};

export type MatrixPlanFromDraftsCreate = {
  plan_name: string;
  draft_ids: number[];
  xhs_account_ids: number[];
  schedule_start_time: number;
  schedule_end_time: number;
  min_interval_minutes: number;
};

export type MatrixPlanCreateResult = {
  id: number;
  item_count: number;
  draft_count: number;
  account_count: number;
};

export type MatrixPlanActionResult = {
  id: number;
  status: MatrixPlanStatus;
  item_count?: number;
  cancelled_item_count?: number;
  retried_item_count?: number;
};

export type VideoEditMaterial = {
  material_file_id: number;
  file_name: string;
  file_type: "image" | "video" | "document" | "other";
  file_path: string;
  mime_type: string;
  file_size: number;
  remark: string;
};

export type VideoEditJobCreate = {
  creation_mode: "standard" | "pro";
  job_title: string;
  post_title: string;
  post_body: string;
  post_tags: string[];
  script_text: string;
  requirement_text: string;
  materials: VideoEditMaterial[];
  xhs_account_id: number;
  planned_publish_time: number;
};

export type VideoScriptOptimizeRequest = {
  script_text: string;
  requirement_text: string;
  material_file_ids: number[];
  adjustment: string;
};

export type VideoScriptOptimizeResult = {
  original_script: string;
  optimized_script: string;
};

export type VideoEditReviewStatus = "draft" | "confirmed" | "rejected";

export type VideoEditPublishContentUpdate = {
  post_title: string;
  post_body: string;
  post_tags: string[];
  review_status: VideoEditReviewStatus;
};

export type VideoEditRevisionRequestCreate = {
  feedback: string;
  client_request_id: string;
};

export type VideoEditJobView = {
  id: number;
  tenant_id: number;
  tenant_name: string;
  user_id: number;
  user_login_name: string;
  user_nickname: string;
  job_title: string;
  post_title: string;
  post_body: string;
  post_tags: string[];
  review_status: VideoEditReviewStatus;
  script_text: string;
  requirement_text: string;
  materials: VideoEditMaterial[];
  creation_mode: "standard" | "pro";
  creation_mode_label: string;
  request_snapshot: VideoEditRequestSnapshot;
  xhs_account_id: number;
  xhs_account_name: string;
  planned_publish_time: number;
  credit_cost: number;
  publish_credit_cost: number;
  total_credit_cost: number;
  publish_plan_id: number;
  publish_item_id: number;
  status: number;
  status_name: "submitted" | "in_production" | "delivered" | "revision_requested" | "cancelled" | "returned";
  status_text: string;
  user_progress_text: string;
  expected_delivery_time: number;
  sla_status: "normal" | "due_soon" | "overdue" | "completed" | "returned";
  seconds_to_delivery: number;
  operator_user_id: number;
  operator_name: string;
  developer_note: string;
  delivery: VideoEditDelivery;
  delivery_version_count: number;
  delivery_versions: VideoEditDeliveryVersion[];
  delivery_assets?: VideoEditDeliveryAsset[];
  delivery_resource_counts?: Record<VideoEditDeliveryResourceType, number>;
  revision_count?: number;
  latest_revision_request_id?: number;
  latest_revision_feedback?: string;
  latest_revision_status?: "" | "submitted" | "completed";
  delivered_time: number;
  create_time: number;
  update_time: number;
};

export type VideoEditRequestSnapshot = {
  creation_mode: "standard" | "pro";
  creation_mode_label: string;
  credit_cost: number;
  job_title: string;
  post_title: string;
  post_body: string;
  post_tags: string[];
  script_text: string;
  requirement_text: string;
  materials: VideoEditMaterial[];
  xhs_account_id: number;
  xhs_account_name?: string;
  planned_publish_time: number;
  submitted_at: number;
};

export type VideoEditJobHistory = {
  id: number;
  request_snapshot: VideoEditRequestSnapshot;
  creation_mode: "standard" | "pro";
  creation_mode_label: string;
  credit_cost: number;
  status: number;
  status_name: VideoEditJobView["status_name"];
  status_text: string;
  delivery_versions: VideoEditDeliveryVersion[];
  delivery_assets: VideoEditDeliveryAsset[];
  revision_count: number;
  create_time: number;
  update_time: number;
  delivered_time: number;
};

export type VideoEditDeliveryVersion = {
  version: number;
  delivery_file_name?: string;
  delivery_file_path?: string;
  delivery_url?: string;
  note?: string;
  operator_user_id?: number;
  delivered_time?: number;
  publish_plan_id?: number;
  publish_item_id?: number;
  resource_type?: "video";
  mime_type?: string;
  file_size?: number;
};

export type VideoEditDeliveryResourceType = "video" | "voiceover" | "subtitle";

export type VideoEditDeliveryAsset = Omit<VideoEditDeliveryVersion, "resource_type"> & {
  resource_type: VideoEditDeliveryResourceType;
};

export type VideoEditDelivery = VideoEditDeliveryVersion & {
  versions?: VideoEditDeliveryVersion[];
};

export type VideoEditHistoryEntry = {
  id: number;
  tenant_id: number;
  admin_user_id: number;
  operator_name: string;
  action:
    | "video_job_claimed"
    | "video_delivery_uploaded"
    | "video_delivery_replaced"
    | string;
  target_type: string;
  target_id: number;
  detail: Record<string, unknown>;
  create_time: number;
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

export type OperationsOverview = {
  summary: {
    total_employees: number;
    active_employees: number;
    total_accounts: number;
    normal_accounts: number;
    expired_accounts: number;
    risk_accounts: number;
    today_scheduled: number;
    today_submitted: number;
    today_failed: number;
    pending_items: number;
    success_rate: number;
    team_credit_balance: number;
  };
  publish_trend: Array<{
    date: string;
    label: string;
    scheduled: number;
    submitted: number;
    failed: number;
  }>;
  status_distribution: Array<{
    status: number;
    name: string;
    value: number;
  }>;
  employee_ranking: Array<{
    user_id: number;
    nickname: string;
    account_count: number;
    publish_count: number;
    failed_count: number;
    credit_consumed: number;
  }>;
  alerts: Array<{
    type: string;
    title: string;
    count: number;
  }>;
};

export type AdminXHSAccount = {
  id: number;
  user_id: number;
  display_name: string;
  account_group: string;
  status: 1 | 2 | 3 | 4;
  daily_limit: number;
  min_interval_minutes: number;
  last_publish_time: number;
  today_publish_count: number;
  create_time: number;
  update_time: number;
  employee_name: string;
  employee_login: string;
  login_state_ready: boolean;
  latest_login_status: string;
  pending_count: number;
  submitted_count: number;
  failed_count: number;
};

export type AdminPublishPlan = {
  id: number;
  user_id: number;
  plan_name: string;
  source_type: string;
  content_type: string;
  product_id: number;
  status: MatrixPlanStatus;
  schedule_start_time: number;
  schedule_end_time: number;
  create_time: number;
  update_time: number;
  employee_name: string;
  employee_login: string;
  item_count: number;
  pending_count: number;
  submitted_count: number;
  failed_count: number;
  cancelled_count: number;
};

export type AdminPublishPlanDetail = AdminPublishPlan & {
  items: Array<{
    id: number;
    plan_id: number;
    xhs_account_id: number;
    account_name: string;
    account_status: number;
    content_type: string;
    title: string;
    scheduled_time: number;
    status: MatrixPlanItemStatus;
    last_error: string;
    attempt_count: number;
    max_attempts: number;
    next_retry_time: number;
    submitted_time: number;
    publish_result_json: string | null;
    create_time: number;
    update_time: number;
  }>;
};

export type UserNotification = {
  id: number;
  notification_type: "task" | "announcement" | "system";
  title: string;
  content: string;
  priority: 1 | 2 | 3;
  action_path: string;
  business_type: string;
  business_id: number;
  deadline_time: number;
  read_time: number;
  is_read: boolean;
  create_time: number;
  update_time: number;
};

export type UserFeedbackCategory = "bug" | "feature" | "experience" | "other";
export type UserFeedbackStatus = "pending" | "in_progress" | "completed";

export type UserFeedback = {
  id: number;
  tenant_id: number;
  tenant_name: string;
  user_id: number;
  user_login_name: string;
  user_nickname: string;
  category: UserFeedbackCategory;
  title: string;
  description: string;
  status: UserFeedbackStatus;
  developer_reply: string;
  completed_by_user_id: number;
  completed_time: number;
  create_time: number;
  update_time: number;
};

export type UserFeedbackCreate = Pick<
  UserFeedback,
  "category" | "title" | "description"
>;

export type DeveloperFeedbackUpdate = Pick<
  UserFeedback,
  "status" | "developer_reply"
>;

export type AdminSentNotification = {
  id: number;
  notification_type: "task" | "announcement" | "system";
  title: string;
  content: string;
  priority: 1 | 2 | 3;
  action_path: string;
  deadline_time: number;
  create_time: number;
  recipient_count: number;
  read_count: number;
};

export type AdminNotificationCreate = {
  recipient_user_ids: number[];
  notification_type: "task" | "announcement" | "system";
  title: string;
  content: string;
  priority: 1 | 2 | 3;
  action_path: string;
  deadline_time: number;
};

export type AdminEmployeeView = {
  id: number;
  tenant_id: number;
  login_name: string;
  nickname: string;
  user_role: "customer";
  status: 1 | 2;
  wallet_balance: number;
  xhs_account_count: number;
  publish_plan_count: number;
  last_login_time: number;
  create_time: number;
  update_time: number;
};

export type AdminEmployeeDetail = AdminEmployeeView & {
  inspiration_session_count: number;
  viral_analysis_count: number;
};

export type AdminEmployeeCreate = {
  login_name: string;
  nickname: string;
  password: string;
  status: 1 | 2;
};

export type UserCreationRequest = {
  id: number;
  tenant_id: number;
  tenant_name: string;
  requested_by_admin_id: number;
  requester_name: string;
  login_name: string;
  nickname: string;
  requested_status: 1 | 2;
  status: "pending" | "approved" | "rejected";
  reviewed_by_developer_id: number;
  review_note: string;
  reviewed_time: number;
  approved_user_id: number;
  create_time: number;
  update_time: number;
  approval_required?: boolean;
};

export type AdminEmployeeUpdate = {
  login_name: string;
  nickname: string;
};

export type AdminEmployeeSummary = {
  total: number;
  active: number;
  disabled: number;
  recent_login: number;
};

export type AdminEmployeePasswordReset = {
  password: string;
};

export type AdminEmployeeStatusUpdate = {
  status: 1 | 2;
};

export type InspirationGoalType =
  | "general"
  | "topic"
  | "title"
  | "body"
  | "script"
  | "strategy"
  | "optimize";
export type InspirationInteractionMode = "normal" | "personalized";
export type InspirationSessionStatus = "active" | "generating" | "archived";
export type InspirationMessageRole = "user" | "assistant";
export type InspirationMessageStatus = "success" | "failed";

export type InspirationAttachment = {
  id: number;
  session_id: number;
  message_id: number;
  file_name: string;
  mime_type: "image/jpeg" | "image/png" | "image/webp";
  file_size: number;
  status: "pending" | "attached";
  create_time: number;
  update_time: number;
  preview_url?: string;
};

export type InspirationSession = {
  id: number;
  tenant_id: number;
  user_id: number;
  title: string;
  linked_product_id: number;
  linked_xhs_account_id: number;
  goal_type: InspirationGoalType;
  interaction_mode: InspirationInteractionMode;
  personalization_template_id?: number;
  tone: string;
  extra_requirement: string;
  generation_token: string;
  generation_started_time: number;
  active_leaf_message_id?: number;
  status: InspirationSessionStatus;
  is_pinned?: boolean;
  pinned_time?: number;
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
  client_request_id?: string;
  parent_message_id?: number;
  revision_root_message_id?: number;
  revision_source_message_id?: number;
  revision_index?: number;
  revision_count?: number;
  revision_message_ids?: number[];
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
  content_collection_id?: number;
  create_time: number;
  attachments?: InspirationAttachment[];
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
  interaction_mode: InspirationInteractionMode;
  personalization_template_id?: number;
  tone: string;
  extra_requirement: string;
};

export type InspirationMessageCreate = {
  content: string;
  client_request_id: string;
  attachment_ids?: number[];
  model_mode?: InspirationModelMode;
};

export type InspirationModelMode = "standard" | "pro";

export type InspirationMessageRevisionCreate = InspirationMessageCreate & {
  retained_attachment_ids?: number[];
};

export type InspirationMessageResponse = {
  user_message: InspirationMessage;
  assistant_message: InspirationMessage;
  credit_cost: number;
};

export type ViralAnalysisAgentHandoff = {
  key: string;
  source_job_id: number;
  source_title: string;
  session_draft: InspirationSessionCreate;
  initial_message: string;
};

export type AgentVideoCreationHandoff = {
  key: string;
  source_session_id: number;
  source_message_id: number;
  source_viral_job_id: number;
  job_title: string;
  script_text: string;
  requirement_text: string;
  linked_product_id: number;
};

export type InspirationPersonalization = {
  id: number;
  tenant_id: number;
  user_id: number;
  assistant_name: string;
  assistant_traits: string;
  preferred_address: string;
  occupation: string;
  user_details: string;
  response_preferences: string;
  create_time: number;
  update_time: number;
};

export type InspirationPersonalizationUpdate = Pick<
  InspirationPersonalization,
  | "assistant_name"
  | "assistant_traits"
  | "preferred_address"
  | "occupation"
  | "user_details"
  | "response_preferences"
>;

export type InspirationPersonalizationTemplateStatus = "active" | "archived";

export type InspirationPersonalizationTemplate = InspirationPersonalization & {
  template_name: string;
  status: InspirationPersonalizationTemplateStatus;
};

export type InspirationPersonalizationTemplateUpdate =
  InspirationPersonalizationUpdate & {
    template_name: string;
  };

export type InspirationPersonalizationPreference = {
  id: number;
  tenant_id: number;
  user_id: number;
  interaction_mode: InspirationInteractionMode;
  personalization_template_id: number;
  create_time: number;
  update_time: number;
};

export type InspirationPersonalizationPreferenceUpdate = Pick<
  InspirationPersonalizationPreference,
  "interaction_mode" | "personalization_template_id"
>;

export type AuthUser = {
  id: number;
  tenant_id: number;
  login_name: string;
  nickname: string;
  user_role: "customer" | "client_owner" | "client_admin" | "platform_admin" | "developer_admin";
  wallet_balance: number;
};

export type LoginRequest = {
  login_name: string;
  password: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
};

export type WalletView = {
  id: number;
  user_id: number;
  balance: number;
  total_recharged: number;
  total_consumed: number;
  create_time: number;
  update_time: number;
};

export type CreditLedgerView = {
  id: number;
  user_id: number;
  business_type: string;
  business_id: number;
  before_balance: number;
  change_amount: number;
  after_balance: number;
  reason: string;
  create_time: number;
};

export type MembershipPlan = {
  id: number;
  plan_code: "free" | "pro" | "max" | "storage";
  plan_name: string;
  price_cent: number;
  summary: string;
  features: string[];
  monthly_credits: number;
  daily_checkin_credits: number;
  storage_gb: number;
  status: number;
  sort_order: number;
  create_time: number;
  update_time: number;
};

export type UserMembership = {
  id: number;
  tenant_id: number;
  user_id: number;
  plan_id: number;
  status: 1 | 2 | 3;
  start_time: number;
  expire_time: number;
  auto_renew: number;
  create_time: number;
  update_time: number;
  plan: MembershipPlan;
};

export type RechargePackage = {
  id: number;
  package_name: string;
  base_credits: number;
  credits: number;
  price_cent: number;
  is_hot: number;
  status: number;
  sort_order: number;
  create_time: number;
  update_time: number;
};

export type DailyCheckinStatus = {
  checked_in: boolean;
  already_checked_in?: boolean;
  checkin_date: string;
  credits: number;
  balance: number;
};

export type RechargeOrder = {
  id: number;
  order_no: string;
  tenant_id: number;
  user_id: number;
  recharge_type: "online" | "package";
  package_id: number;
  package_name: string;
  amount_cent: number;
  requested_credits: number;
  payment_channel: "manual" | "alipay" | "wechat" | "";
  status: 1 | 2 | 3 | 4 | 5 | 6;
  payer_note?: string;
  proof_file_name?: string;
  proof_mime_type?: string;
  proof_file_size?: number;
  proof_submit_time?: number;
  has_payment_proof?: boolean;
  remark: string;
  paid_time: number;
  completed_time: number;
  create_time: number;
  update_time: number;
};

export type RechargeOrderCreate = {
  recharge_type: "online" | "package";
  package_id?: number;
  amount_cent?: number;
  payment_channel: "manual" | "alipay" | "wechat";
};

export type AdminEmployeeWallet = {
  employee_id: number;
  employee_name: string;
  employee_login: string;
  balance: number;
  total_recharged: number;
  total_consumed: number;
};

export type AdminBillingOverview = {
  membership: UserMembership;
  wallet: {
    employee_count: number;
    balance: number;
    total_recharged: number;
    total_consumed: number;
  };
  month_orders: {
    order_count: number;
    pending_order_count: number;
    completed_amount_cent: number;
    completed_credits: number;
  };
  credit_trend: Array<{
    label: string;
    income: number;
    expense: number;
  }>;
  employee_wallets: AdminEmployeeWallet[];
};

export type AdminMembershipActivation = {
  membership: UserMembership;
  affected_user_count: number;
};

export type MembershipUpgradeOrder = {
  id: number;
  order_no: string;
  tenant_id: number;
  applicant_user_id: number;
  applicant_name: string;
  applicant_login: string;
  tenant_name: string;
  plan_id: number;
  plan: MembershipPlan;
  duration_months: number;
  amount_cent: number;
  payment_channel: "alipay" | "wechat";
  status: 1 | 2 | 3 | 4 | 5;
  paid_time: number;
  reviewed_by_developer_id: number;
  reviewed_time: number;
  affected_user_count: number;
  remark: string;
  create_time: number;
  update_time: number;
};

export type MembershipUpgradeOrderCreate = {
  plan_id: number;
  duration_months: number;
  payment_channel: "alipay" | "wechat";
};

export type AdminRechargeOrder = Omit<RechargeOrder, "payment_channel"> & {
  payment_channel: "manual" | "alipay" | "wechat" | "";
  employee_name: string;
  employee_login: string;
};

export type AdminRechargeOrderCreate = {
  employee_id: number;
  recharge_type: "online" | "package";
  package_id?: number;
  amount_cent?: number;
  payment_channel: "manual" | "alipay" | "wechat";
};

export type AdminCreditLedgerItem = CreditLedgerView & {
  employee_name: string;
  employee_login: string;
};

export type AdminCreditLedgerResult = PaginatedResult<AdminCreditLedgerItem> & {
  summary: {
    income: number;
    expense: number;
  };
};

export type DeveloperBillingCustomer = {
  id: number;
  tenant_id: number;
  tenant_name: string;
  login_name: string;
  nickname: string;
  balance: number;
};

export type DeveloperTenantMembershipPlan = {
  id: number;
  plan_code: string;
  plan_name: string;
  monthly_credits: number;
  daily_checkin_credits: number;
  storage_gb: number;
};

export type DeveloperTenantMembership = {
  tenant_id: number;
  tenant_name: string;
  affected_user_count: number;
  membership: {
    id: number;
    plan_id: number;
    status: number;
    start_time: number;
    expire_time: number;
    auto_renew: number;
    plan: DeveloperTenantMembershipPlan;
  } | null;
  plans: DeveloperTenantMembershipPlan[];
};

export type DeveloperRechargeOrder = AdminRechargeOrder & {
  tenant_name: string;
};

export type DeveloperCreditLedgerItem = AdminCreditLedgerItem & {
  tenant_name: string;
};

export type DeveloperCreditLedgerResult =
  PaginatedResult<DeveloperCreditLedgerItem>;

export type DeveloperPaymentRecord = {
  record_key: string;
  record_type: "credit_recharge" | "membership_purchase";
  record_type_text: string;
  order_id: number;
  order_no: string;
  tenant_id: number;
  tenant_name: string;
  user_id: number;
  customer_name: string;
  customer_login: string;
  description: string;
  amount_cent: number;
  credits: number;
  payment_channel: string;
  status: number;
  status_text: string;
  paid_time: number;
  create_time: number;
  update_time: number;
};

export type DeveloperPaymentRecordResult =
  PaginatedResult<DeveloperPaymentRecord>;

export type DeveloperCreditGrantResult = {
  ledger_id: number;
  user_id: number;
  employee_name: string;
  employee_login: string;
  tenant_name: string;
  before_balance: number;
  change_amount: number;
  after_balance: number;
  reason: string;
  create_time: number;
};

export type AdminProductLibrarySummary = {
  product_count: number;
  active_product_count: number;
  folder_count: number;
  asset_count: number;
  image_count: number;
  video_count: number;
  document_count: number;
  storage_bytes: number;
};

export type AdminProduct = {
  id: number;
  user_id: number;
  product_name: string;
  brand_name: string;
  category: string;
  sku: string;
  price_cent: number;
  activity_price_cent: number;
  status: 1 | 2;
  cover_material_id: number;
  parameter: Record<string, unknown>;
  selling_point: Record<string, unknown>;
  ai_material: Record<string, unknown>;
  material_count: number;
  employee_name: string;
  employee_login: string;
  create_time: number;
  update_time: number;
};

export type ViralAnalysisStatus = "pending" | "processing" | "completed" | "failed" | "cancelled";
export type ViralAnalysisSourceType = "upload" | "link" | "text";
export type ViralAnalysisGoal =
  | "hook"
  | "structure"
  | "rhythm"
  | "script"
  | "selling"
  | "reuse"
  | "setting"
  | "lighting";

export type ViralVisualEvidenceType = "visible_confirmed" | "inferred";
export type ViralVisualConfidence = "high" | "medium" | "low";

export type ViralTimelineVisualAnalysis = {
  time_range: string;
  setting: string;
  lighting: string;
  visual_style: string;
  evidence_type: ViralVisualEvidenceType;
  confidence: ViralVisualConfidence;
  visible_evidence: string;
};

export type ViralVisualEvidence = {
  conclusion: string;
  evidence_type: ViralVisualEvidenceType;
  confidence: ViralVisualConfidence;
  visible_evidence: string;
};

export type ViralAnalysisResult = {
  hook_summary: string;
  structure_summary: string;
  shot_rhythm: string;
  script_breakdown: string;
  original_transcript?: string;
  transcript_analysis?: string;
  selling_points: string;
  reuse_suggestions: string;
  rewritten_script: string;
  setting_analysis: string;
  lighting_analysis: string;
  visual_style: string;
  timeline_visual_analysis: ViralTimelineVisualAnalysis[];
  visual_evidence: ViralVisualEvidence[];
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
  ai_provider?: string;
  ai_model?: string;
  credit_cost: number;
  error_message?: string;
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

export type ContentCollection = {
  id: number;
  tenant_id: number;
  user_id: number;
  source_type: "viral_analysis" | "inspiration";
  source_id: number;
  title: string;
  hook_summary: string;
  structure_summary: string;
  shot_rhythm: string;
  script_breakdown: string;
  original_transcript?: string;
  transcript_analysis?: string;
  selling_points: string;
  reuse_suggestions: string;
  rewritten_script: string;
  setting_analysis: string;
  lighting_analysis: string;
  visual_style: string;
  timeline_visual_analysis: ViralTimelineVisualAnalysis[];
  visual_evidence: ViralVisualEvidence[];
  tags: string[];
  source_context: {
    analysis_goal?: ViralAnalysisGoal[];
    source_type?: ViralAnalysisSourceType;
    source_url?: string;
    session_id?: number;
    ai_provider?: string;
    ai_model?: string;
  };
  create_time: number;
  update_time: number;
};

export type ContentCollectionUpdate = Partial<Pick<
  ContentCollection,
  | "title"
  | "hook_summary"
  | "structure_summary"
  | "shot_rhythm"
  | "script_breakdown"
  | "selling_points"
  | "reuse_suggestions"
  | "rewritten_script"
  | "setting_analysis"
  | "lighting_analysis"
  | "visual_style"
  | "timeline_visual_analysis"
  | "visual_evidence"
  | "tags"
>>;

export type MaterialProjectGroup = {
  id: number;
  tenant_id: number;
  group_name: string;
  created_by_user_id: number;
  folder_count: number;
  asset_count: number;
  create_time: number;
  update_time: number;
};

export type MaterialFolder = {
  id: number;
  tenant_id: number;
  project_group_id: number;
  parent_id: number;
  folder_name: string;
  created_by_user_id: number;
  child_folder_count?: number;
  asset_count?: number;
  activity_time?: number;
  create_time: number;
  update_time: number;
};

export type MaterialBreadcrumb = Pick<
  MaterialFolder,
  "id" | "project_group_id" | "parent_id" | "folder_name"
>;

export type MaterialAsset = {
  id: number;
  tenant_id: number;
  user_id: number;
  folder_id: number;
  product_id: number;
  package_id: number;
  file_name: string;
  file_type: "image" | "video" | "word" | "excel" | "other";
  mime_type: string;
  file_size: number;
  create_time: number;
  update_time: number;
};

export type MaterialLibraryListing = {
  project_group_id: number;
  current_folder: MaterialFolder | null;
  breadcrumbs: MaterialBreadcrumb[];
  folders: MaterialFolder[];
  assets: MaterialAsset[];
};

export type MaterialStorageUsage = {
  used_bytes: number;
  quota_bytes: number;
  remaining_bytes: number;
  quota_gb: number;
  usage_percent: number;
};

export type AiTranslationStatus =
  | "pending"
  | "claimed"
  | "in_progress"
  | "awaiting_customer"
  | "revision_requested"
  | "completed"
  | "cancelled"
  | "failed";

export type AiTranslationLanguage =
  | "auto"
  | "vi"
  | "en"
  | "zh"
  | "ms"
  | "th"
  | "tl"
  | "ja"
  | "ko"
  | "es";

export type AiTranslationDelivery = {
  id: number;
  task_id: number;
  delivery_no: number;
  asset_no: number;
  client_request_id: string;
  developer_user_id: number;
  resource_type: "video" | "voiceover" | "subtitle";
  file_name: string;
  file_path: string;
  mime_type: string;
  file_size: number;
  note: string;
  content_url: string;
  internal_content_url: string;
  create_time: number;
};

export type AiTranslationTask = {
  id: number;
  tenant_id: number;
  tenant_name: string;
  user_id: number;
  user_login_name: string;
  user_nickname: string;
  client_request_id: string;
  source_type: "local_upload" | "material_library";
  material_file_id: number;
  source_file_name: string;
  source_file_path: string;
  source_mime_type: string;
  source_file_size: number;
  source_language: AiTranslationLanguage;
  target_language: Exclude<AiTranslationLanguage, "auto">;
  status: AiTranslationStatus;
  status_text: string;
  operator_user_id: number;
  operator_name: string;
  developer_note: string;
  revision_feedback: string;
  revision_count: number;
  delivery_count: number;
  charged_credit_cost: number;
  credit_ledger_id: number;
  delivered_time: number;
  completed_time: number;
  create_time: number;
  update_time: number;
  deliveries: AiTranslationDelivery[];
  delivery_resource_counts: Record<"video" | "voiceover" | "subtitle", number>;
};

export type DeveloperAIUsage = {
  id: number;
  status: "success" | "failed";
  provider: string;
  model_name: string;
  request_id?: string;
  latency_ms: number;
  input_chars: number;
  output_chars: number;
  credit_cost: number;
  error_message: string;
  create_time: number;
};

export type AISettingSlot = "vision" | "copywriting" | "pro_copywriting";

export type AIProviderSetting = {
  provider: string;
  base_url: string;
  model: string;
  enabled: boolean;
  has_key: boolean;
  masked_key: string;
};

export type AIProviderSettings = Record<AISettingSlot, AIProviderSetting>;

export type AISettingUpdate = {
  api_key: string;
  model: string;
  enabled: boolean;
};

export type AISettingTestResult = {
  success: boolean;
  slot: AISettingSlot;
  provider: string;
  model: string;
  request_id: string;
  latency_ms: number;
};

export type DeveloperViralAnalysisJob = ViralAnalysisJob & {
  ai_provider: string;
  ai_model: string;
  error_message: string;
  latest_ai_usage: DeveloperAIUsage | null;
};

export type DeveloperViralAnalysisSummary = Pick<
  DeveloperViralAnalysisJob,
  | "id"
  | "tenant_id"
  | "user_id"
  | "title"
  | "source_type"
  | "status"
  | "credit_cost"
  | "create_time"
  | "update_time"
>;

export type DeveloperServiceHealth = {
  key: string;
  label: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  detail: string;
};

export type DeveloperTaskCount = {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
};

export type DeveloperPlatformOverview = {
  services: DeveloperServiceHealth[];
  tasks: Record<"viral_analysis" | "video_edit" | "matrix_publish", DeveloperTaskCount>;
  ai: {
    calls_24h: number;
    failures_24h: number;
    failure_rate: number;
    p95_latency_ms: number;
    trend: Array<{
      timestamp: number;
      calls: number;
      failures: number;
      success_rate: number;
      p95_latency_ms: number;
    }>;
  };
  pool: {
    size: number;
    total: number;
    idle: number;
    in_use: number;
    pre_ping: boolean;
    recycle_seconds: number;
    closed: boolean;
  };
  open_alerts: number;
  page_alerts: number;
  active_developers: number;
  updated_at: number;
};

export type DeveloperUnifiedTask = {
  id: number;
  kind: "viral_analysis" | "video_edit" | "matrix_publish";
  title: string;
  tenant_id: number;
  tenant_name: string;
  user_id: number;
  user_name: string;
  login_name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled" | "unknown";
  raw_status: string;
  error_summary: string;
  available_actions: Array<"cancel" | "retry">;
  created_at: number;
  updated_at: number;
};

export type DeveloperAlert = {
  id: number;
  alert_type: string;
  severity: "page" | "ticket";
  status: "open" | "acknowledged" | "resolved";
  title: string;
  summary: string;
  source_type: string;
  source_id: number;
  tenant_id: number;
  assigned_user_id: number;
  assigned_user_name: string;
  detected_at: number;
  last_seen_at: number;
  acknowledged_at: number;
  resolved_at: number;
  resolution: string;
  detail: Record<string, unknown>;
};

export type DeveloperAccount = {
  id: number;
  tenant_id: number;
  login_name: string;
  nickname: string;
  role: "platform_admin" | "developer_admin";
  status: 1 | 2;
  last_login_at: number;
  created_at: number;
  updated_at: number;
};

export type DeveloperCustomerAccount = {
  id: number;
  tenant_id: number;
  tenant_name: string;
  login_name: string;
  nickname: string;
  user_role: "client_owner" | "customer";
  status: 1 | 2;
  balance: number;
  membership_plan_code: string;
  membership_plan_name: string;
  last_login_time: number;
  create_time: number;
  update_time: number;
};

export type DeveloperAuditEntry = {
  id: number;
  tenant_id: number;
  admin_user_id: number;
  operator_name: string;
  operator_login_name: string;
  action: string;
  target_type: string;
  target_id: number;
  detail: Record<string, unknown>;
  created_at: number;
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
