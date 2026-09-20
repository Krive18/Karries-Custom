import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { ApiRequestError } from "../api/httpClient";
import { PublishTasksPage } from "../pages/PublishTasksPage";
import type { VideoEditJobView } from "../types";


vi.mock("../api/client", () => ({
  api: {
    listContentDrafts: vi.fn(),
    listXHSAccounts: vi.fn(),
    listMatrixPlans: vi.fn(),
    checkRuntime: vi.fn(),
    listVideoEditJobs: vi.fn(),
    getVideoEditDeliveryArchiveBlob: vi.fn(),
    getVideoEditDeliveryVersionBlob: vi.fn(),
    getVideoEditDeliveryResourceBlob: vi.fn()
  }
}));


const mockedApi = vi.mocked(api);


describe("PublishTasksPage video delivery", () => {
  let anchorClick: () => void;
  let appendChildSpy: ReturnType<typeof vi.spyOn>;
  let createObjectUrlSpy: ReturnType<typeof vi.spyOn>;
  let revokeObjectUrlSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
    anchorClick = vi.fn();
    appendChildSpy = vi.spyOn(document.body, "appendChild");
    createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:delivery-archive");
    revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      anchorClick();
    });
    mockedApi.listContentDrafts.mockResolvedValue([]);
    mockedApi.listXHSAccounts.mockResolvedValue([]);
    mockedApi.listMatrixPlans.mockResolvedValue([]);
    mockedApi.checkRuntime.mockResolvedValue({ publish_worker_running: false } as never);
    mockedApi.getVideoEditDeliveryArchiveBlob.mockResolvedValue(
      new Blob(["zip"], { type: "application/zip" })
    );
    mockedApi.getVideoEditDeliveryVersionBlob.mockResolvedValue(
      new Blob(["video"], { type: "video/mp4" })
    );
    mockedApi.getVideoEditDeliveryResourceBlob.mockResolvedValue(
      new Blob(["resource"], { type: "application/octet-stream" })
    );
    mockedApi.listVideoEditJobs.mockResolvedValue([
      {
        id: 31,
        job_title: "多视频交付任务",
        post_title: "多视频交付任务",
        post_body: "交付说明",
        post_tags: [],
        review_status: "confirmed",
        status: 3,
        status_name: "delivered",
        status_text: "已交付",
        user_progress_text: "已交付",
        delivery_version_count: 2,
        delivery_versions: [
          { version: 1, delivery_file_name: "first-cut.mp4" },
          { version: 2, delivery_file_name: "final-cut.mp4" }
        ],
        delivery_assets: [
          { resource_type: "video", version: 1, delivery_file_name: "first-cut.mp4" },
          { resource_type: "video", version: 2, delivery_file_name: "final-cut.mp4" },
          { resource_type: "voiceover", version: 1, delivery_file_name: "voiceover.mp3" },
          { resource_type: "subtitle", version: 1, delivery_file_name: "captions.srt" }
        ],
        delivery_resource_counts: { video: 2, voiceover: 1, subtitle: 1 },
        delivery: {},
        create_time: 1
      } as unknown as VideoEditJobView
    ]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps the complete archive download and renders a download action for every resource", async () => {
    render(<PublishTasksPage mode="review" />);

    expect(await screen.findByText(/first-cut\.mp4/)).toBeInTheDocument();
    expect(screen.getByText(/final-cut\.mp4/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "一键下载全部（4）" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^预览视频/ })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /^下载视频/ })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "下载口播 voiceover.mp3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "下载字幕 captions.srt" })).toBeInTheDocument();
  });

  it("renders voiceover and subtitle resources independently from videos", async () => {
    render(<PublishTasksPage mode="review" />);

    expect(await screen.findByText("共 1 个可用口播音频")).toBeInTheDocument();
    expect(screen.getByText("voiceover.mp3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "播放 voiceover.mp3" })).toBeInTheDocument();
    expect(screen.getByText("共 1 个可用字幕")).toBeInTheDocument();
    expect(screen.getByText("captions.srt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看 captions.srt" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "复制 captions.srt" })).toBeInTheDocument();
  });

  it("downloads a complete delivery archive with a stable job filename", async () => {
    render(<PublishTasksPage mode="review" />);

    fireEvent.click(await screen.findByRole("button", { name: "一键下载全部（4）" }));

    await waitFor(() => expect(mockedApi.getVideoEditDeliveryArchiveBlob).toHaveBeenCalledWith(31));
    await waitFor(() => expect(createObjectUrlSpy).toHaveBeenCalledWith(expect.any(Blob)));
    expect(appendChildSpy).toHaveBeenCalledWith(expect.any(HTMLAnchorElement));
    const appendedNodes = appendChildSpy.mock.calls as unknown as Array<[Node]>;
    const anchor = appendedNodes
      .map(([node]) => node)
      .find((node): node is HTMLAnchorElement => node instanceof HTMLAnchorElement);
    if (!anchor) {
      throw new Error("delivery archive anchor was not appended");
    }
    expect(anchor.download).toBe("多视频交付任务-完整交付包.zip");
    expect(anchor.href).toBe("blob:delivery-archive");
    expect(anchorClick).toHaveBeenCalledTimes(1);
    expect(revokeObjectUrlSpy).not.toHaveBeenCalled();
  });

  it("downloads video, voiceover and subtitle resources as their original files", async () => {
    render(<PublishTasksPage mode="review" />);

    fireEvent.click(await screen.findByRole("button", { name: "下载视频 first-cut.mp4" }));
    await waitFor(() => expect(mockedApi.getVideoEditDeliveryVersionBlob).toHaveBeenCalledWith(31, 1));

    fireEvent.click(screen.getByRole("button", { name: "下载口播 voiceover.mp3" }));
    await waitFor(() => expect(mockedApi.getVideoEditDeliveryResourceBlob).toHaveBeenCalledWith(31, "voiceover", 1));

    fireEvent.click(screen.getByRole("button", { name: "下载字幕 captions.srt" }));
    await waitFor(() => expect(mockedApi.getVideoEditDeliveryResourceBlob).toHaveBeenCalledWith(31, "subtitle", 1));

    const downloads = (appendChildSpy.mock.calls as unknown as Array<[Node]>)
      .map(([node]) => node)
      .filter((node): node is HTMLAnchorElement => node instanceof HTMLAnchorElement)
      .map((anchor) => anchor.download);
    expect(downloads).toEqual(["first-cut.mp4", "voiceover.mp3", "captions.srt"]);
  });

  it("shows a packing state while the complete archive is being built", async () => {
    let resolveArchive: (blob: Blob) => void = () => undefined;
    mockedApi.getVideoEditDeliveryArchiveBlob.mockReturnValue(
      new Promise((resolve) => {
        resolveArchive = resolve;
      })
    );
    render(<PublishTasksPage mode="review" />);

    fireEvent.click(await screen.findByRole("button", { name: "一键下载全部（4）" }));

    expect(screen.getByRole("button", { name: "正在打包…" })).toBeDisabled();
    resolveArchive(new Blob(["zip"], { type: "application/zip" }));
    expect(await screen.findByRole("button", { name: "一键下载全部（4）" })).toBeEnabled();
  });

  it("shows the API error when the complete archive download fails", async () => {
    mockedApi.getVideoEditDeliveryArchiveBlob.mockRejectedValue(
      new ApiRequestError("交付文件不完整，请稍后重试或联系管理员", "DELIVERY_ARCHIVE_INCOMPLETE", 409)
    );
    render(<PublishTasksPage mode="review" />);

    fireEvent.click(await screen.findByRole("button", { name: "一键下载全部（4）" }));

    expect(await screen.findByText("交付文件不完整，请稍后重试或联系管理员")).toBeInTheDocument();
  });

  it("filters real video jobs by unfinished and completed status", async () => {
    const delivered = (await mockedApi.listVideoEditJobs()) as VideoEditJobView[];
    mockedApi.listVideoEditJobs.mockResolvedValue([
      ...delivered,
      {
        ...delivered[0],
        id: 32,
        job_title: "刚提交的视频任务",
        post_title: "刚提交的视频任务",
        status: 1,
        status_name: "submitted",
        status_text: "视频待生成",
        user_progress_text: "素材与制作要求已提交",
        delivery_versions: []
      },
      {
        ...delivered[0],
        id: 33,
        job_title: "已退回的视频任务",
        post_title: "已退回的视频任务",
        status: 5,
        status_name: "returned",
        status_text: "已退回",
        user_progress_text: "该视频任务已退回",
        delivery_versions: []
      }
    ]);

    render(<PublishTasksPage mode="review" />);

    const contentPanel = (await screen.findByRole("heading", { name: "内容制定" }))
      .closest("section");
    expect(contentPanel).not.toBeNull();
    const content = within(contentPanel as HTMLElement);
    expect(content.getByText("刚提交的视频任务")).toBeInTheDocument();
    expect(content.getByText("多视频交付任务")).toBeInTheDocument();
    expect(content.getByText("已退回的视频任务")).toBeInTheDocument();

    fireEvent.click(content.getByRole("button", { name: /^未完成/ }));
    expect(content.getByText("刚提交的视频任务")).toBeInTheDocument();
    expect(content.queryByText("多视频交付任务")).not.toBeInTheDocument();
    expect(content.queryByText("已退回的视频任务")).not.toBeInTheDocument();

    fireEvent.click(content.getByRole("button", { name: /^已完成/ }));
    expect(content.getByText("多视频交付任务")).toBeInTheDocument();
    expect(content.queryByText("刚提交的视频任务")).not.toBeInTheDocument();
    expect(content.queryByText("已退回的视频任务")).not.toBeInTheDocument();
  });

  it("keeps long resource names and their actions on one stable row", () => {
    const stylesheet = readFileSync(resolve(process.cwd(), "src/renderer/styles.css"), "utf8");

    expect(stylesheet).toMatch(
      /\.delivery-archive-actions\s*\{[^}]*display:\s*flex;[^}]*justify-content:\s*flex-end;/s
    );
    expect(stylesheet).toMatch(
      /\.delivery-video-row\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto;/s
    );
    expect(stylesheet).toMatch(
      /\.delivery-video-row\s*>\s*span\s*\{[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/s
    );
    expect(stylesheet).toMatch(
      /\.delivery-video-row\s*>\s*div\s*\{[^}]*flex-wrap:\s*nowrap;[^}]*white-space:\s*nowrap;/s
    );
  });
});
