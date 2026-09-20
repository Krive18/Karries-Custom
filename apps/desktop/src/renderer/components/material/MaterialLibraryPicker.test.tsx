import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import type {
  MaterialAsset,
  MaterialFolder,
  MaterialLibraryListing,
  MaterialProjectGroup
} from "../../types";
import { MaterialLibraryPicker } from "./MaterialLibraryPicker";


vi.mock("../../api/client", () => ({
  api: {
    listMaterialProjectGroups: vi.fn(),
    listMaterialLibraryItems: vi.fn(),
    getMaterialAssetBlob: vi.fn(),
    getMaterialAssetThumbnailBlob: vi.fn()
  }
}));

vi.mock("./MaterialThumbnail", () => ({
  MaterialThumbnail: ({ asset }: { asset: MaterialAsset }) => (
    <span aria-hidden="true">{asset.file_type}</span>
  )
}));

const mockedApi = vi.mocked(api);
const noInitialSelection: MaterialAsset[] = [];

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

const groups: MaterialProjectGroup[] = [
  {
    id: 17,
    tenant_id: 1,
    group_name: "秋季上新",
    created_by_user_id: 1,
    folder_count: 1,
    asset_count: 2,
    create_time: 1,
    update_time: 1
  },
  {
    id: 18,
    tenant_id: 1,
    group_name: "常青产品",
    created_by_user_id: 1,
    folder_count: 1,
    asset_count: 1,
    create_time: 1,
    update_time: 1
  }
];

const autumnFolder: MaterialFolder = {
  id: 71,
  tenant_id: 1,
  project_group_id: 17,
  parent_id: 0,
  folder_name: "产品图",
  created_by_user_id: 1,
  child_folder_count: 0,
  asset_count: 2,
  create_time: 1,
  update_time: 1
};

const evergreenFolder: MaterialFolder = {
  ...autumnFolder,
  id: 81,
  project_group_id: 18,
  folder_name: "常青资料",
  asset_count: 1
};

const autumnAsset: MaterialAsset = {
  id: 701,
  tenant_id: 1,
  user_id: 1,
  folder_id: autumnFolder.id,
  product_id: 0,
  package_id: 0,
  file_name: "秋季主图.png",
  file_type: "image",
  mime_type: "image/png",
  file_size: 1024,
  create_time: 1,
  update_time: 1
};

const recursiveAsset: MaterialAsset = {
  ...autumnAsset,
  id: 702,
  file_name: "秋季详情.png"
};

const evergreenAsset: MaterialAsset = {
  ...autumnAsset,
  id: 801,
  folder_id: evergreenFolder.id,
  file_name: "常青视频.mp4",
  file_type: "video",
  mime_type: "video/mp4"
};

function listing(
  projectGroupId: number,
  folder: MaterialFolder | null,
  folders: MaterialFolder[],
  assets: MaterialAsset[]
): MaterialLibraryListing {
  return {
    project_group_id: projectGroupId,
    current_folder: folder,
    breadcrumbs: folder ? [folder] : [],
    folders,
    assets
  };
}

describe("MaterialLibraryPicker project-group navigation", () => {
  beforeEach(() => {
    mockedApi.listMaterialProjectGroups.mockResolvedValue(groups);
    mockedApi.listMaterialLibraryItems.mockImplementation(async (
      folderId = 0,
      _keyword = "",
      _fileType = "",
      recursive = false,
      projectGroupId = 0
    ) => {
      if (projectGroupId === 17 && folderId === 0) {
        return listing(17, null, [autumnFolder], []);
      }
      if (projectGroupId === 17 && folderId === autumnFolder.id) {
        return listing(
          17,
          autumnFolder,
          [],
          recursive ? [autumnAsset, recursiveAsset] : [autumnAsset]
        );
      }
      if (projectGroupId === 18 && folderId === 0) {
        return listing(18, null, [evergreenFolder], []);
      }
      if (projectGroupId === 18 && folderId === evergreenFolder.id) {
        return listing(18, evergreenFolder, [], [evergreenAsset]);
      }
      return listing(projectGroupId, null, [], []);
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("selects assets across groups while preserving navigation and confirmation order", async () => {
    const onConfirm = vi.fn();
    render(
      <MaterialLibraryPicker
        open
        initialSelection={noInitialSelection}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />
    );

    expect(await screen.findByRole("button", { name: "打开项目组 秋季上新" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开项目组 常青产品" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /全选当前/ })).not.toBeInTheDocument();
    expect(mockedApi.listMaterialLibraryItems).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "打开项目组 秋季上新" }));
    await waitFor(() => {
      expect(mockedApi.listMaterialLibraryItems).toHaveBeenCalledWith(0, "", "", false, 17);
    });
    fireEvent.click(await screen.findByRole("button", { name: "打开文件夹 产品图" }));
    await waitFor(() => {
      expect(mockedApi.listMaterialLibraryItems).toHaveBeenCalledWith(71, "", "", false, 17);
    });
    fireEvent.click(await screen.findByRole("button", { name: "秋季主图.png" }));
    fireEvent.click(screen.getByRole("button", { name: "全选当前文件夹" }));
    await waitFor(() => {
      expect(mockedApi.listMaterialLibraryItems).toHaveBeenCalledWith(71, "", "", true, 17);
      expect(screen.getByText("已选择 2 个素材")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "全部项目组" }));
    expect(await screen.findByRole("button", { name: "打开项目组 常青产品" })).toBeInTheDocument();
    expect(screen.getByText("已选择 2 个素材")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "打开项目组 常青产品" }));
    fireEvent.click(await screen.findByRole("button", { name: "打开文件夹 常青资料" }));
    fireEvent.click(await screen.findByRole("button", { name: "常青视频.mp4" }));

    expect(screen.getByText("已选择 3 个素材")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认使用" }));
    expect(onConfirm).toHaveBeenCalledWith([
      autumnAsset,
      recursiveAsset,
      evergreenAsset
    ]);
  });

  it("ignores a stale group listing after returning home and opening another group", async () => {
    const staleAutumnListing = deferred<MaterialLibraryListing>();
    mockedApi.listMaterialLibraryItems.mockImplementation(async (
      _folderId = 0,
      _keyword = "",
      _fileType = "",
      _recursive = false,
      projectGroupId = 0
    ) => {
      if (projectGroupId === 17) return staleAutumnListing.promise;
      return listing(18, null, [evergreenFolder], []);
    });

    render(
      <MaterialLibraryPicker
        open
        initialSelection={noInitialSelection}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));
    fireEvent.click(screen.getByRole("button", { name: "全部项目组" }));
    fireEvent.click(screen.getByRole("button", { name: "打开项目组 常青产品" }));
    expect(await screen.findByRole("button", { name: "打开文件夹 常青资料" })).toBeInTheDocument();

    staleAutumnListing.resolve(listing(17, null, [autumnFolder], []));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "打开文件夹 常青资料" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "打开文件夹 产品图" })).not.toBeInTheDocument();
    });
  });

  it("ignores a recursive selection from a closed picker session after reopening", async () => {
    const staleRecursiveListing = deferred<MaterialLibraryListing>();
    mockedApi.listMaterialLibraryItems.mockImplementation(async (
      folderId = 0,
      _keyword = "",
      _fileType = "",
      recursive = false,
      projectGroupId = 0
    ) => {
      if (projectGroupId === 17 && folderId === autumnFolder.id && recursive) {
        return staleRecursiveListing.promise;
      }
      if (projectGroupId === 17 && folderId === 0) {
        return listing(17, null, [autumnFolder], []);
      }
      if (projectGroupId === 17) {
        return listing(17, autumnFolder, [], [autumnAsset]);
      }
      if (projectGroupId === 18) {
        return listing(18, null, [evergreenFolder], []);
      }
      return listing(projectGroupId, null, [], []);
    });
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    const view = render(
      <MaterialLibraryPicker
        open
        initialSelection={noInitialSelection}
        onClose={onClose}
        onConfirm={onConfirm}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 秋季上新" }));
    fireEvent.click(await screen.findByRole("button", { name: "打开文件夹 产品图" }));
    fireEvent.click(await screen.findByRole("button", { name: "全选当前文件夹" }));
    expect(screen.getByRole("button", { name: "全选当前文件夹" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    view.rerender(
      <MaterialLibraryPicker
        open={false}
        initialSelection={noInitialSelection}
        onClose={onClose}
        onConfirm={onConfirm}
      />
    );
    view.rerender(
      <MaterialLibraryPicker
        open
        initialSelection={[evergreenAsset]}
        onClose={onClose}
        onConfirm={onConfirm}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "打开项目组 常青产品" }));
    expect(await screen.findByRole("button", { name: "全选当前文件夹" })).not.toBeDisabled();
    expect(screen.getByText("已选择 1 个素材")).toBeInTheDocument();

    await act(async () => {
      staleRecursiveListing.resolve(
        listing(17, autumnFolder, [], [autumnAsset, recursiveAsset])
      );
      await staleRecursiveListing.promise;
    });

    expect(screen.getByText("已选择 1 个素材")).toBeInTheDocument();
    expect(screen.queryByText("已选中当前文件夹及子文件夹中的全部可用素材")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认使用" }));
    expect(onConfirm).toHaveBeenCalledWith([evergreenAsset]);
  });

  it("does not reload or reset when initialSelection is omitted", async () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    const view = render(
      <MaterialLibraryPicker open onClose={onClose} onConfirm={onConfirm} />
    );

    expect(await screen.findByRole("button", { name: "打开项目组 秋季上新" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "打开项目组 秋季上新" }));
    expect(await screen.findByRole("button", { name: "打开文件夹 产品图" })).toBeInTheDocument();

    view.rerender(
      <MaterialLibraryPicker open onClose={onClose} onConfirm={onConfirm} />
    );
    await waitFor(() => {
      expect(mockedApi.listMaterialProjectGroups).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByRole("button", { name: "打开文件夹 产品图" })).toBeInTheDocument();
  });
});
