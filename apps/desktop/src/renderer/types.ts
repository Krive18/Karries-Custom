export type PageKey = "create" | "schedule" | "settings";

export type ScheduledTask = {
  id: number;
  account: string;
  title: string;
  publishType: string;
  scheduleTime: string;
  status: "待提交" | "提交中" | "已提交平台" | "失败";
};

export type ProviderOption = {
  label: string;
  value: string;
  models: string[];
};
