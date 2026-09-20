import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type {
  MaterialAsset,
  MaterialFolder,
  MaterialProjectGroup
} from "../types";
import { ProductLibraryPage } from "./ProductLibraryPage";


vi.mock("../api/client", () => ({
  api: {
    listMaterialProjectGroups: vi.fn(),
    createMaterialProjectGroup: vi.fn(),
    renameMaterialProjectGroup: vi.fn(),
    deleteMaterialProjectGroup: vi.fn(),
    listMaterialLibraryItems: vi.fn(),
    createMaterialFolder: vi.fn(),
    renameMaterialFolder: vi.fn(),
    deleteMaterialFolder: vi.fn(),
    uploadMaterialAsset: vi.fn(),
    getMaterialStorageUsage: vi.fn(),
    getMaterialAssetBlob: vi.fn(),
    getMaterialAssetThumbnailBlob: vi.fn(),
    deleteMaterialAsset: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

const projectGroups: MaterialProjectGroup[] = [
  {
    id: 17,
    tenant_id: 1,
    group_name: "秋季上新",
    created_by_user_id: 1,
    folder_count: 2,
    asset_count: 7,
    create_time: 1787097600,
    update_time: 1787132160
  },
  {
    id: 18,
    tenant_id: 1,
    group_name: "常青产品",
    created_by_user_id: 2,
    folder_count: 1,
    asset_count: 3,
    create_time: 1787011200,
    update_time: 1787040000
  }
];

const productFolder: MaterialFolder = {
  id: 7,
  tenant_id: 1,
  project_group_id: 17,
  parent_id: 0,
  folder_name: "产品图",
  created_by_user_id: 1,
  child_folder_count: 0,
  asset_count: 2,
  create_time: 1787097600,
  update_time: 1787132160
};

const imageAsset: MaterialAsset = {
  id: 11,
  tenant_id: 1,
  user_id: 1,
  folder_id: 7,
  product_id: 0,
  package_id: 0,
  file_name: "产品细节.png",
  file_type: "image",
  mime_type: "image/png",
  file_size: 1024,
  create_time: 1,
  update_time: 1
};

const videoAsset: MaterialAsset = {
  ...imageAsset,
  id: 12,
  file_name: "产品演示.mp4",
  file_type: "video",
  mime_type: "video/mp4"
};

function listing(folderId = 0) {
  return {
    project_group_id: 17,
    current_folder: folderId ? productFolder : null,
    breadcrumbs: folderId ? [productFolder] : [],
    folders: folderId ? [] : [productFolder],
    assets: folderId ? [imageAsset, videoAsset] : []
  };
}

async function openFirstProjectGroup() {
  fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));
  await screen.findByRole("button", { name: "打开文件夹 产品图" });
}

describe("ProductLibraryPage project groups", () => {
  beforeEach(() => {
    mockedApi.listMaterialProjectGroups.mockResolvedValue(projectGroups);
    mockedApi.listMaterialLibraryItems.mockImplementation(async (folderId = 0) => listing(folderId));
    mockedApi.createMaterialProjectGroup.mockImplementation(async (groupName) => ({
      ...projectGroups[0],
      id: 19,
      group_name: groupName,
      folder_count: 0,
      asset_count: 0
    }));
    mockedApi.renameMaterialProjectGroup.mockImplementation(async (groupId, groupName) => ({
      ...projectGroups.find((group) => group.id === groupId)!,
      group_name: groupName
    }));
    mockedApi.deleteMaterialProjectGroup.mockResolvedValue({ deleted: true });
    mockedApi.createMaterialFolder.mockResolvedValue({
      ...productFolder,
      id: 20,
      folder_name: "视频脚本"
    });
    mockedApi.renameMaterialFolder.mockResolvedValue(productFolder);
    mockedApi.deleteMaterialFolder.mockResolvedValue({ deleted: true });
    mockedApi.uploadMaterialAsset.mockResolvedValue(imageAsset);
    mockedApi.getMaterialStorageUsage.mockRejectedValue(new Error("not configured"));
    mockedApi.getMaterialAssetBlob.mockResolvedValue(new Blob(["asset"]));
    mockedApi.getMaterialAssetThumbnailBlob.mockResolvedValue(new Blob(["thumbnail"]));
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn((blob: Blob) => blob.size > 5 ? "blob:asset" : "blob:preview")
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn()
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("opens on the project-group home and loads folder items only after selection", async () => {
    render(<ProductLibraryPage />);

    expect(await screen.findByRole("button", { name: "新建项目组" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开项目组 秋季上新" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开项目组 常青产品" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "上传素材" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("素材文件")).not.toBeInTheDocument();
    expect(mockedApi.listMaterialLibraryItems).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "打开项目组 秋季上新" }));

    await waitFor(() => {
      expect(mockedApi.listMaterialLibraryItems).toHaveBeenCalledWith(0, "", "", false, 17);
    });
  });

  it("ignores a stale folder response after returning home and opening another group", async () => {
    const firstGroupListing = deferred<ReturnType<typeof listing>>();
    const secondGroupFolder = {
      ...productFolder,
      id: 8,
      project_group_id: 18,
      folder_name: "常青资料"
    };
    mockedApi.listMaterialLibraryItems.mockImplementation(async (_folderId, _keyword, _type, _recursive, groupId) => {
      if (groupId === 17) return firstGroupListing.promise;
      return {
        project_group_id: 18,
        current_folder: null,
        breadcrumbs: [],
        folders: [secondGroupFolder],
        assets: []
      };
    });
    render(<ProductLibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));
    fireEvent.click(await screen.findByRole("button", { name: "返回产品知识库项目组" }));
    fireEvent.click(screen.getByRole("button", { name: "打开项目组 常青产品" }));

    expect(await screen.findByRole("button", { name: "打开文件夹 常青资料" })).toBeInTheDocument();
    firstGroupListing.resolve(listing(0));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "打开文件夹 常青资料" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "打开文件夹 产品图" })).not.toBeInTheDocument();
    });
  });

  it("keeps a newly created group when the initial group request resolves late", async () => {
    const initialGroups = deferred<MaterialProjectGroup[]>();
    mockedApi.listMaterialProjectGroups.mockReturnValueOnce(initialGroups.promise);
    render(<ProductLibraryPage />);

    fireEvent.click(screen.getByRole("button", { name: "新建项目组" }));
    fireEvent.change(screen.getByRole("textbox", { name: "项目组名称" }), {
      target: { value: "双十一活动" }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建项目组" }));
    await waitFor(() => {
      expect(mockedApi.createMaterialProjectGroup).toHaveBeenCalledWith("双十一活动");
    });

    initialGroups.resolve(projectGroups);

    expect(await screen.findByRole("button", { name: "打开项目组 双十一活动" })).toBeInTheDocument();
  });

  it("shows project-group folder and asset counts with an update date", async () => {
    render(<ProductLibraryPage />);

    const card = (await screen.findByRole("button", { name: "打开项目组 秋季上新" }))
      .closest(".material-project-card");

    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getByText("2 个文件夹")).toBeInTheDocument();
    expect(within(card as HTMLElement).getByText("7 个素材")).toBeInTheDocument();
    expect(within(card as HTMLElement).getByText(/更新于 .*2026/)).toBeInTheDocument();
  });

  it("shows the most recently updated folders first and lets users change the time order", async () => {
    const oldestFolder = {
      ...productFolder,
      id: 21,
      folder_name: "99 旧项目",
      update_time: 1787011200,
      activity_time: 1787270400
    };
    const middleFolder = {
      ...productFolder,
      id: 22,
      folder_name: "2 中期项目",
      update_time: 1787097600
    };
    const newestFolder = {
      ...productFolder,
      id: 23,
      folder_name: "1 最新项目",
      update_time: 1787184000
    };
    mockedApi.listMaterialLibraryItems.mockResolvedValue({
      project_group_id: 17,
      current_folder: null,
      breadcrumbs: [],
      folders: [oldestFolder, middleFolder, newestFolder],
      assets: []
    });

    render(<ProductLibraryPage />);
    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));

    const folderNames = () => screen.getAllByRole("button", { name: /^打开文件夹 / })
      .map((button) => button.getAttribute("aria-label"));
    const sortSelect = await screen.findByRole("combobox", { name: "排序方式" });

    expect(sortSelect).toHaveValue("updated-desc");
    expect(folderNames()).toEqual([
      "打开文件夹 99 旧项目",
      "打开文件夹 1 最新项目",
      "打开文件夹 2 中期项目"
    ]);

    fireEvent.change(sortSelect, { target: { value: "updated-asc" } });
    expect(folderNames()).toEqual([
      "打开文件夹 2 中期项目",
      "打开文件夹 1 最新项目",
      "打开文件夹 99 旧项目"
    ]);

    fireEvent.change(sortSelect, { target: { value: "name-asc" } });
    expect(folderNames()).toEqual([
      "打开文件夹 1 最新项目",
      "打开文件夹 2 中期项目",
      "打开文件夹 99 旧项目"
    ]);
  });

  it("creates a project group and keeps it on the group home", async () => {
    render(<ProductLibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "新建项目组" }));
    fireEvent.change(screen.getByRole("textbox", { name: "项目组名称" }), {
      target: { value: "  双十一活动  " }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建项目组" }));

    expect(await screen.findByRole("button", { name: "打开项目组 双十一活动" })).toBeInTheDocument();
    expect(mockedApi.createMaterialProjectGroup).toHaveBeenCalledWith("双十一活动");
    expect(mockedApi.listMaterialLibraryItems).not.toHaveBeenCalled();
  });

  it("renames a project group from its card action", async () => {
    render(<ProductLibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "重命名项目组 秋季上新" }));
    const input = screen.getByRole("textbox", { name: "项目组名称" });
    fireEvent.change(input, { target: { value: "秋季上新 2.0" } });
    fireEvent.click(screen.getByRole("button", { name: "保存项目组名称" }));

    expect(await screen.findByRole("button", { name: "打开项目组 秋季上新 2.0" })).toBeInTheDocument();
    expect(mockedApi.renameMaterialProjectGroup).toHaveBeenCalledWith(17, "秋季上新 2.0");
  });

  it("shows a duplicate-name API message and keeps the group-name input focused", async () => {
    mockedApi.createMaterialProjectGroup.mockRejectedValueOnce(
      new Error("同一团队下已存在同名项目组")
    );
    render(<ProductLibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "新建项目组" }));
    const input = screen.getByRole("textbox", { name: "项目组名称" });
    fireEvent.change(input, { target: { value: "秋季上新" } });
    fireEvent.click(screen.getByRole("button", { name: "创建项目组" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("同一团队下已存在同名项目组");
    expect(input).toHaveFocus();
  });

  it("keeps a non-empty group and shows the delete conflict message", async () => {
    mockedApi.deleteMaterialProjectGroup.mockRejectedValueOnce(
      new Error("项目组内仍有文件夹或素材，请先清空后再删除")
    );
    render(<ProductLibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "删除项目组 秋季上新" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "项目组内仍有文件夹或素材，请先清空后再删除"
    );
    expect(screen.getByRole("button", { name: "打开项目组 秋季上新" })).toBeInTheDocument();
  });

  it("passes the selected group id when listing and creating folders", async () => {
    render(<ProductLibraryPage />);
    await openFirstProjectGroup();

    fireEvent.click(screen.getByRole("button", { name: "新建文件夹" }));
    fireEvent.change(screen.getByRole("textbox", { name: "文件夹名称" }), {
      target: { value: "视频脚本" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(mockedApi.createMaterialFolder).toHaveBeenCalledWith(0, "视频脚本", 17);
    });
    expect(mockedApi.listMaterialLibraryItems).toHaveBeenCalledWith(0, "", "", false, 17);
  });

  it("returns to project-group home from the breadcrumb and resets folder search state", async () => {
    render(<ProductLibraryPage />);
    await openFirstProjectGroup();

    fireEvent.change(screen.getByRole("textbox", { name: "搜索当前文件夹" }), {
      target: { value: "口红" }
    });
    fireEvent.click(screen.getByRole("button", { name: "打开文件夹 产品图" }));
    await waitFor(() => {
      expect(mockedApi.listMaterialLibraryItems).toHaveBeenCalledWith(7, "", "", false, 17);
    });

    fireEvent.click(screen.getByRole("button", { name: "返回产品知识库项目组" }));

    expect(await screen.findByRole("button", { name: "打开项目组 秋季上新" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "搜索当前文件夹" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "上传素材" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "打开项目组 秋季上新" }));
    await waitFor(() => {
      expect(mockedApi.listMaterialLibraryItems).toHaveBeenLastCalledWith(0, "", "", false, 17);
    });
  });
});

describe("ProductLibraryPage material preview", () => {
  beforeEach(() => {
    mockedApi.listMaterialProjectGroups.mockResolvedValue(projectGroups);
    mockedApi.listMaterialLibraryItems.mockImplementation(async (folderId = 0) => listing(folderId));
    mockedApi.getMaterialStorageUsage.mockRejectedValue(new Error("not configured"));
    mockedApi.getMaterialAssetBlob.mockResolvedValue(new Blob(["asset"]));
    mockedApi.getMaterialAssetThumbnailBlob.mockResolvedValue(new Blob(["thumbnail"]));
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn((blob: Blob) => blob.size > 5 ? "blob:asset" : "blob:preview")
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn()
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    [imageAsset, "img"],
    [videoAsset, "video"]
  ] as const)("opens %s in a full preview dialog", async (asset, elementName) => {
    const { container } = render(<ProductLibraryPage />);
    await openFirstProjectGroup();
    fireEvent.click(screen.getByRole("button", { name: "打开文件夹 产品图" }));

    fireEvent.click(await screen.findByRole("button", { name: `预览 ${asset.file_name}` }));

    const dialog = await screen.findByRole("dialog", { name: `预览素材 ${asset.file_name}` });
    await waitFor(() => {
      expect(dialog.querySelector(elementName)).not.toBeNull();
    });
    expect(container.querySelector(".material-preview-dialog")).toBe(dialog);
    expect(mockedApi.getMaterialAssetBlob).toHaveBeenCalledWith(asset.id);
  });

  it("keeps the preview content and delete action in separate card columns", async () => {
    render(<ProductLibraryPage />);
    await openFirstProjectGroup();
    fireEvent.click(screen.getByRole("button", { name: "打开文件夹 产品图" }));

    const previewButton = await screen.findByRole("button", { name: `预览 ${imageAsset.file_name}` });
    const card = previewButton.closest(".product-asset-item");
    const stylesheet = readFileSync(resolve(process.cwd(), "src/renderer/styles.css"), "utf8");
    const productPolishStyles = stylesheet.slice(stylesheet.indexOf("/* Product polish"));

    expect(card).not.toBeNull();
    expect(productPolishStyles).toMatch(
      /\.product-asset-item\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+32px;/s
    );
    expect(previewButton).toContainElement(screen.getByText(imageAsset.file_name));
  });

  it("shows precise storage usage and refreshes it when the page regains focus", async () => {
    const quotaBytes = 100 * 1024 ** 3;
    const initialUsedBytes = Math.round(41.2 * 1024 ** 2);
    const refreshedUsedBytes = 50 * 1024 ** 2;
    mockedApi.getMaterialStorageUsage
      .mockResolvedValueOnce({
        used_bytes: initialUsedBytes,
        quota_bytes: quotaBytes,
        remaining_bytes: quotaBytes - initialUsedBytes,
        quota_gb: 100,
        usage_percent: initialUsedBytes * 100 / quotaBytes
      })
      .mockResolvedValueOnce({
        used_bytes: refreshedUsedBytes,
        quota_bytes: quotaBytes,
        remaining_bytes: quotaBytes - refreshedUsedBytes,
        quota_gb: 100,
        usage_percent: refreshedUsedBytes * 100 / quotaBytes
      });

    render(<ProductLibraryPage />);

    expect(await screen.findByText("已使用 41.2 MB")).toBeInTheDocument();
    expect(screen.getByText("99.960 GB / 100 GB")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "云空间使用情况" }))
      .toHaveAttribute("aria-valuemax", String(quotaBytes));

    fireEvent.focus(window);

    expect(await screen.findByText("已使用 50.0 MB")).toBeInTheDocument();
    expect(mockedApi.getMaterialStorageUsage).toHaveBeenCalledTimes(2);
  });
});

describe("ProductLibraryPage project-group visual hierarchy", () => {
  it("keeps each project group as one unified card instead of a glued action rail", () => {
    const stylesheet = readFileSync(resolve(process.cwd(), "src/renderer/styles.css"), "utf8");
    const projectCardStyles = stylesheet.slice(
      stylesheet.indexOf(".material-project-home {"),
      stylesheet.indexOf(".material-project-loading {")
    );

    expect(projectCardStyles).toMatch(
      /\.material-project-card\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s
    );
    expect(projectCardStyles).toMatch(
      /\.material-project-card-actions\s*\{[^}]*position:\s*absolute;[^}]*flex-direction:\s*row;[^}]*background:\s*transparent;/s
    );
    expect(projectCardStyles).not.toMatch(/\.material-project-card-actions\s*\{[^}]*border-left:/s);
  });

  it("stretches the project canvas to use the remaining desktop viewport", () => {
    const stylesheet = readFileSync(resolve(process.cwd(), "src/renderer/styles.css"), "utf8");
    const projectHomeStyles = stylesheet.match(/\.material-project-home\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(projectHomeStyles).toMatch(
      /min-height:\s*max\(520px,\s*calc\(100dvh\s*-\s*140px\)\)/
    );
  });
});
