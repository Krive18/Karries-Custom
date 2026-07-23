import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { DeveloperApp } from "../DeveloperApp";
import { api } from "../api/client";
import { developerApi } from "../api/developerClient";


vi.mock("../api/client", () => ({
  api: {
    getCurrentUser: vi.fn()
  }
}));

vi.mock("../api/developerClient", () => ({
  developerApi: {
    listViralAnalysisJobs: vi.fn(),
    getViralAnalysisJob: vi.fn(),
    listVideoEditJobs: vi.fn(),
    claimVideoEditJob: vi.fn(),
    deliverVideoEditJob: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);
const mockedDeveloperApi = vi.mocked(developerApi);


beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.getCurrentUser.mockResolvedValue({
    id: 1,
    tenant_id: 0,
    login_name: "developer",
    nickname: "开发者",
    user_role: "developer_admin",
    wallet_balance: 0
  });
  mockedDeveloperApi.listViralAnalysisJobs.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 20,
    total: 0
  });
  mockedDeveloperApi.listVideoEditJobs.mockResolvedValue([]);
});


it("opens the separately built developer workspace for a developer role", async () => {
  render(<DeveloperApp />);

  expect(await screen.findByRole("button", { name: "AI 任务排查" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "人工剪辑工单" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "智能创作" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "人工剪辑工单" }));
  expect(await screen.findByRole("heading", { name: "开发者端 · 剪辑工单" })).toBeInTheDocument();
});


it("rejects a customer role before loading internal data", async () => {
  mockedApi.getCurrentUser.mockResolvedValue({
    id: 9,
    tenant_id: 1,
    login_name: "operator",
    nickname: "运营",
    user_role: "client_member",
    wallet_balance: 0
  });

  render(<DeveloperApp />);

  expect(await screen.findByRole("heading", { name: "无法进入开发者端" })).toBeInTheDocument();
  expect(screen.getByText("当前账号没有开发者端访问权限")).toBeInTheDocument();
  expect(mockedDeveloperApi.listViralAnalysisJobs).not.toHaveBeenCalled();
  expect(mockedDeveloperApi.listVideoEditJobs).not.toHaveBeenCalled();
});
