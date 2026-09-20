import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpDown,
  ChevronRight,
  Download,
  FileImage,
  FileText,
  Film,
  Folder,
  FolderOpen,
  FolderPlus,
  Folders,
  Loader2,
  Pencil,
  Plus,
  Search,
  Trash2,
  Upload,
  X
} from "lucide-react";

import { api } from "../api/client";
import { MaterialThumbnail } from "../components/material/MaterialThumbnail";
import type {
  MaterialAsset,
  MaterialFolder,
  MaterialLibraryListing,
  MaterialProjectGroup,
  MaterialStorageUsage
} from "../types";


const emptyListing: MaterialLibraryListing = {
  project_group_id: 0,
  current_folder: null,
  breadcrumbs: [],
  folders: [],
  assets: []
};

type FolderDialogState = {
  mode: "create" | "rename";
  folder: MaterialFolder | null;
} | null;

type ProjectGroupDialogState = {
  mode: "create" | "rename";
  group: MaterialProjectGroup | null;
} | null;

type MaterialSortMode = "updated-desc" | "updated-asc" | "name-asc";

const materialNameCollator = new Intl.Collator("zh-CN", {
  numeric: true,
  sensitivity: "base"
});

function sortMaterialsBy<T extends { id: number; file_name?: string; folder_name?: string; update_time: number; activity_time?: number }>(
  items: T[],
  mode: MaterialSortMode
) {
  return [...items].sort((left, right) => {
    if (mode === "name-asc") {
      const nameResult = materialNameCollator.compare(
        left.folder_name ?? left.file_name ?? "",
        right.folder_name ?? right.file_name ?? ""
      );
      return nameResult || left.id - right.id;
    }
    const leftTime = left.activity_time ?? left.update_time;
    const rightTime = right.activity_time ?? right.update_time;
    const timeResult = mode === "updated-desc"
      ? rightTime - leftTime
      : leftTime - rightTime;
    if (timeResult) return timeResult;
    return materialNameCollator.compare(
      left.folder_name ?? left.file_name ?? "",
      right.folder_name ?? right.file_name ?? ""
    );
  });
}


function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatStorageSize(bytes: number) {
  const gigabytes = bytes / 1024**3;
  if (gigabytes >= 1) return `${gigabytes.toFixed(3)} GB`;
  return formatFileSize(bytes);
}

function materialTypeLabel(fileType: "image" | "video" | "word" | "excel" | "other") {
  if (fileType === "image") return "图片";
  if (fileType === "video") return "视频";
  return "脚本文档";
}

function formatUpdateTime(timestamp: number) {
  if (!timestamp) return "暂无更新时间";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(timestamp * 1000));
}


export function ProductLibraryPage() {
  const [projectGroups, setProjectGroups] = useState<MaterialProjectGroup[]>([]);
  const [projectGroupId, setProjectGroupId] = useState<number | null>(null);
  const [folderId, setFolderId] = useState(0);
  const [listing, setListing] = useState<MaterialLibraryListing>(emptyListing);
  const [keyword, setKeyword] = useState("");
  const [sortMode, setSortMode] = useState<MaterialSortMode>("updated-desc");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [folderDialog, setFolderDialog] = useState<FolderDialogState>(null);
  const [folderName, setFolderName] = useState("");
  const [projectGroupDialog, setProjectGroupDialog] = useState<ProjectGroupDialogState>(null);
  const [projectGroupName, setProjectGroupName] = useState("");
  const [projectGroupError, setProjectGroupError] = useState("");
  const [isProjectGroupSaving, setIsProjectGroupSaving] = useState(false);
  const [storageUsage, setStorageUsage] = useState<MaterialStorageUsage | null>(null);
  const [previewAsset, setPreviewAsset] = useState<MaterialAsset | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const projectGroupInputRef = useRef<HTMLInputElement | null>(null);
  const previewObjectUrlRef = useRef("");
  const previewRequestRef = useRef(0);
  const listingRequestRef = useRef(0);
  const projectGroupRequestRef = useRef(0);
  const selectedProjectGroup = projectGroups.find((group) => group.id === projectGroupId) ?? null;
  const sortedFolders = useMemo(
    () => sortMaterialsBy(listing.folders, sortMode),
    [listing.folders, sortMode]
  );
  const sortedAssets = useMemo(
    () => sortMaterialsBy(listing.assets, sortMode),
    [listing.assets, sortMode]
  );

  const loadStorageUsage = useCallback(async () => {
    try {
      setStorageUsage(await api.getMaterialStorageUsage());
    } catch {
      setStorageUsage(null);
    }
  }, []);

  const loadProjectGroups = useCallback(async () => {
    const requestId = ++projectGroupRequestRef.current;
    setIsLoading(true);
    try {
      const nextGroups = await api.listMaterialProjectGroups();
      if (requestId !== projectGroupRequestRef.current) return;
      setProjectGroups(nextGroups);
      setMessage("");
    } catch (error) {
      if (requestId !== projectGroupRequestRef.current) return;
      setMessage(error instanceof Error ? error.message : "项目组加载失败");
    } finally {
      if (requestId === projectGroupRequestRef.current) setIsLoading(false);
    }
  }, []);

  const load = useCallback(async (
    nextFolderId: number,
    nextKeyword: string,
    nextProjectGroupId: number
  ) => {
    const requestId = ++listingRequestRef.current;
    setIsLoading(true);
    try {
      const next = await api.listMaterialLibraryItems(
        nextFolderId,
        nextKeyword,
        "",
        false,
        nextProjectGroupId
      );
      if (requestId !== listingRequestRef.current) return;
      setListing(next);
      setFolderId(nextFolderId);
      setMessage("");
    } catch (error) {
      if (requestId !== listingRequestRef.current) return;
      setMessage(error instanceof Error ? error.message : "产品知识库加载失败");
    } finally {
      if (requestId === listingRequestRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjectGroups();
  }, [loadProjectGroups]);

  useEffect(() => {
    const refreshStorageUsage = () => void loadStorageUsage();
    refreshStorageUsage();
    window.addEventListener("focus", refreshStorageUsage);
    const refreshTimer = window.setInterval(refreshStorageUsage, 30_000);
    return () => {
      window.removeEventListener("focus", refreshStorageUsage);
      window.clearInterval(refreshTimer);
    };
  }, [loadStorageUsage]);

  useEffect(() => () => {
    if (previewObjectUrlRef.current) {
      URL.revokeObjectURL(previewObjectUrlRef.current);
    }
  }, []);

  useEffect(() => {
    if (!previewAsset) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closePreview();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [previewAsset]);

  function releasePreviewUrl() {
    if (!previewObjectUrlRef.current) return;
    URL.revokeObjectURL(previewObjectUrlRef.current);
    previewObjectUrlRef.current = "";
  }

  function closePreview() {
    previewRequestRef.current += 1;
    releasePreviewUrl();
    setPreviewAsset(null);
    setPreviewUrl("");
    setPreviewError("");
    setIsPreviewLoading(false);
  }

  async function openPreview(asset: MaterialAsset) {
    const requestId = ++previewRequestRef.current;
    releasePreviewUrl();
    setPreviewAsset(asset);
    setPreviewUrl("");
    setPreviewError("");
    setIsPreviewLoading(true);
    try {
      const blob = await api.getMaterialAssetBlob(asset.id);
      if (requestId !== previewRequestRef.current) return;
      const objectUrl = URL.createObjectURL(blob);
      previewObjectUrlRef.current = objectUrl;
      setPreviewUrl(objectUrl);
    } catch (error) {
      if (requestId === previewRequestRef.current) {
        setPreviewError(error instanceof Error ? error.message : "素材预览加载失败");
      }
    } finally {
      if (requestId === previewRequestRef.current) setIsPreviewLoading(false);
    }
  }

  async function openProjectGroup(group: MaterialProjectGroup) {
    setProjectGroupId(group.id);
    setFolderId(0);
    setKeyword("");
    setListing(emptyListing);
    setMessage("");
    await load(0, "", group.id);
  }

  function returnToProjectGroups() {
    listingRequestRef.current += 1;
    closePreview();
    setProjectGroupId(null);
    setFolderId(0);
    setKeyword("");
    setListing(emptyListing);
    setFolderDialog(null);
    setMessage("");
    setIsLoading(false);
  }

  function openProjectGroupDialog(
    mode: "create" | "rename",
    group: MaterialProjectGroup | null = null
  ) {
    setProjectGroupDialog({ mode, group });
    setProjectGroupName(group?.group_name ?? "");
    setProjectGroupError("");
  }

  async function saveProjectGroup() {
    const name = projectGroupName.trim();
    if (!projectGroupDialog || !name) {
      setProjectGroupError("请填写项目组名称。");
      projectGroupInputRef.current?.focus();
      return;
    }
    setIsProjectGroupSaving(true);
    setProjectGroupError("");
    try {
      if (projectGroupDialog.mode === "create") {
        const created = await api.createMaterialProjectGroup(name);
        projectGroupRequestRef.current += 1;
        setIsLoading(false);
        setProjectGroups((current) => [...current, created]);
      } else if (projectGroupDialog.group) {
        const renamed = await api.renameMaterialProjectGroup(
          projectGroupDialog.group.id,
          name
        );
        projectGroupRequestRef.current += 1;
        setIsLoading(false);
        setProjectGroups((current) => current.map((group) => (
          group.id === renamed.id ? renamed : group
        )));
      }
      setProjectGroupDialog(null);
      setProjectGroupName("");
    } catch (error) {
      setProjectGroupError(error instanceof Error ? error.message : "项目组操作失败");
      projectGroupInputRef.current?.focus();
    } finally {
      setIsProjectGroupSaving(false);
    }
  }

  async function deleteProjectGroup(group: MaterialProjectGroup) {
    if (!window.confirm(`确认删除空项目组“${group.group_name}”吗？`)) return;
    try {
      await api.deleteMaterialProjectGroup(group.id);
      projectGroupRequestRef.current += 1;
      setIsLoading(false);
      setProjectGroups((current) => current.filter((item) => item.id !== group.id));
      setMessage("");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "项目组内仍有文件夹或素材，请先清空后再删除"
      );
    }
  }

  async function saveFolder() {
    const name = folderName.trim();
    if (!folderDialog || !name || !projectGroupId) {
      setMessage("请填写文件夹名称。");
      return;
    }
    try {
      if (folderDialog.mode === "create") {
        await api.createMaterialFolder(folderId, name, projectGroupId);
      } else if (folderDialog.folder) {
        await api.renameMaterialFolder(folderDialog.folder.id, name);
      }
      setFolderDialog(null);
      setFolderName("");
      await load(folderId, keyword, projectGroupId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "文件夹操作失败");
    }
  }

  async function deleteFolder(folder: MaterialFolder) {
    if (!projectGroupId) return;
    if (!window.confirm(`确认删除空文件夹“${folder.folder_name}”吗？`)) return;
    try {
      await api.deleteMaterialFolder(folder.id);
      await load(folderId, keyword, projectGroupId);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "文件夹内仍有内容，请先清空后再删除"
      );
    }
  }

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return;
    if (!projectGroupId || folderId === 0) {
      setMessage("请先新建或进入产品文件夹后再上传素材。");
      return;
    }
    setIsUploading(true);
    setMessage("");
    try {
      for (const file of Array.from(files)) {
        await api.uploadMaterialAsset(folderId, file);
      }
      setMessage(`已上传 ${files.length} 个素材。`);
      await load(folderId, keyword, projectGroupId);
      await loadStorageUsage();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "素材上传失败");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function deleteAsset(assetId: number, fileName: string) {
    if (!projectGroupId) return;
    if (!window.confirm(`确认删除素材“${fileName}”吗？`)) return;
    try {
      await api.deleteMaterialAsset(assetId);
      await load(folderId, keyword, projectGroupId);
      await loadStorageUsage();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "素材删除失败");
    }
  }

  return (
    <section className="page-stack product-library-page">
      <div className="page-heading horizontal-heading compact-page-heading">
        <div className="page-heading-copy">
          <h1>产品知识库</h1>
          <p>集中整理图片、视频和脚本文档，创作时可直接选用。</p>
        </div>
        <div className="product-library-header-actions">
          {storageUsage ? (
            <div
              className="product-storage-meter"
              title={`已使用 ${formatFileSize(storageUsage.used_bytes)}`}
            >
              <span>云空间剩余</span>
              <strong>
                {formatStorageSize(storageUsage.remaining_bytes)} / {storageUsage.quota_gb} GB
              </strong>
              <small>已使用 {formatStorageSize(storageUsage.used_bytes)}</small>
              <i
                role="progressbar"
                aria-label="云空间使用情况"
                aria-valuemin={0}
                aria-valuenow={storageUsage.used_bytes}
                aria-valuemax={storageUsage.quota_bytes}
              >
                <b style={{ width: `${storageUsage.usage_percent}%` }} />
              </i>
            </div>
          ) : null}
          {projectGroupId ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                setFolderDialog({ mode: "create", folder: null });
                setFolderName("");
              }}
            >
              <FolderPlus size={17} aria-hidden="true" />
              新建文件夹
            </button>
          ) : (
            <button
              className="primary-button"
              type="button"
              onClick={() => openProjectGroupDialog("create")}
            >
              <Plus size={17} aria-hidden="true" />
              新建项目组
            </button>
          )}
          {projectGroupId && folderId > 0 ? (
            <button
              className="primary-button"
              type="button"
              disabled={isUploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {isUploading ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <Upload size={17} aria-hidden="true" />}
              {isUploading ? "正在上传" : "上传素材"}
            </button>
          ) : null}
          <input
            ref={fileInputRef}
            className="hidden-file-input"
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,application/pdf,.docx,.xlsx"
            onChange={(event) => void uploadFiles(event.target.files)}
          />
        </div>
      </div>

      {message ? <div className="form-message" role="status">{message}</div> : null}

      {projectGroupId && selectedProjectGroup ? (
        <>
      <section className="product-library-toolbar" aria-label="产品知识库工具栏">
        <nav className="material-breadcrumbs" aria-label="当前文件夹路径">
          <button
            type="button"
            aria-label="返回产品知识库项目组"
            onClick={returnToProjectGroups}
          >
            <FolderOpen size={17} aria-hidden="true" />
            产品知识库
          </button>
          <span>
            <ChevronRight size={14} aria-hidden="true" />
            <button type="button" onClick={() => void load(0, "", projectGroupId)}>
              {selectedProjectGroup.group_name}
            </button>
          </span>
          {listing.breadcrumbs.map((item) => (
            <span key={item.id}>
              <ChevronRight size={14} aria-hidden="true" />
              <button type="button" onClick={() => void load(item.id, "", projectGroupId)}>
                {item.folder_name}
              </button>
            </span>
          ))}
        </nav>
        <div className="material-list-controls">
          <label className="material-sort-control">
            <ArrowUpDown size={15} aria-hidden="true" />
            <span>排序</span>
            <select
              aria-label="排序方式"
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as MaterialSortMode)}
            >
              <option value="updated-desc">最近更新</option>
              <option value="updated-asc">最早更新</option>
              <option value="name-asc">名称 A-Z</option>
            </select>
          </label>
          <form
            className="material-search"
            onSubmit={(event) => {
              event.preventDefault();
              void load(folderId, keyword, projectGroupId);
            }}
          >
            <Search size={16} aria-hidden="true" />
            <input
              aria-label="搜索当前文件夹"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索当前文件夹"
            />
          </form>
        </div>
      </section>

      <div className="product-library-summary">
        <span><Folder size={16} aria-hidden="true" />{listing.folders.length} 个文件夹</span>
        <span><FileImage size={16} aria-hidden="true" />{listing.assets.filter((asset) => asset.file_type === "image").length} 张图片</span>
        <span><Film size={16} aria-hidden="true" />{listing.assets.filter((asset) => asset.file_type === "video").length} 个视频</span>
        <span><FileText size={16} aria-hidden="true" />{listing.assets.filter((asset) => !["image", "video"].includes(asset.file_type)).length} 个文档</span>
      </div>

      {isLoading ? (
        <div className="material-library-loading" role="status">
          <Loader2 size={24} className="spin" aria-hidden="true" />
          正在整理素材
        </div>
      ) : (
        <div className="product-library-content">
          {listing.folders.length ? (
            <div className="windows-folder-grid" aria-label="文件夹">
              {sortedFolders.map((folder) => (
                <article className="product-folder-item" key={folder.id}>
                  <button
                    className="product-folder-open"
                    type="button"
                    aria-label={`打开文件夹 ${folder.folder_name}`}
                    onClick={() => void load(folder.id, "", projectGroupId)}
                  >
                    <Folder className="windows-folder-icon" size={54} aria-hidden="true" />
                    <span>
                      <strong title={folder.folder_name}>{folder.folder_name}</strong>
                      <small>{folder.asset_count ?? 0} 个素材</small>
                    </span>
                  </button>
                  <div className="product-item-actions">
                    <button
                      type="button"
                      title="重命名文件夹"
                      aria-label={`重命名 ${folder.folder_name}`}
                      onClick={() => {
                        setFolderDialog({ mode: "rename", folder });
                        setFolderName(folder.folder_name);
                      }}
                    >
                      <Pencil size={14} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      title="删除空文件夹"
                      aria-label={`删除 ${folder.folder_name}`}
                      onClick={() => void deleteFolder(folder)}
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : null}

          {listing.assets.length ? (
            <div className="product-asset-grid" aria-label="素材文件">
              {sortedAssets.map((asset) => (
                <article className="product-asset-item" key={asset.id}>
                  {asset.file_type === "image" || asset.file_type === "video" ? (
                    <button
                      className="product-asset-preview"
                      type="button"
                      aria-label={`预览 ${asset.file_name}`}
                      onClick={() => void openPreview(asset)}
                    >
                      <MaterialThumbnail asset={asset} />
                      <span className="product-asset-meta">
                        <strong title={asset.file_name}>{asset.file_name}</strong>
                        <small>{materialTypeLabel(asset.file_type)} · {formatFileSize(asset.file_size)}</small>
                      </span>
                    </button>
                  ) : (
                    <>
                      <MaterialThumbnail asset={asset} />
                      <div className="product-asset-meta">
                        <strong title={asset.file_name}>{asset.file_name}</strong>
                        <small>{materialTypeLabel(asset.file_type)} · {formatFileSize(asset.file_size)}</small>
                      </div>
                    </>
                  )}
                  <button
                    className="product-asset-delete"
                    type="button"
                    title="删除素材"
                    aria-label={`删除 ${asset.file_name}`}
                    onClick={() => void deleteAsset(asset.id, asset.file_name)}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                </article>
              ))}
            </div>
          ) : null}

          {!listing.folders.length && !listing.assets.length ? (
            <div className="material-library-empty">
              <FolderOpen size={42} aria-hidden="true" />
              <strong>{folderId === 0 ? "先为产品建立文件夹" : "这个文件夹还是空的"}</strong>
              <span>
                {folderId === 0
                  ? "产品图片、视频和脚本文档需要归档到明确的产品文件夹中。"
                  : "上传产品图片、视频和脚本文档，后续创作可直接选用。"}
              </span>
              {folderId === 0 ? (
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => {
                    setFolderDialog({ mode: "create", folder: null });
                    setFolderName("");
                  }}
                >
                  <FolderPlus size={16} aria-hidden="true" />
                  新建第一个文件夹
                </button>
              ) : (
                <button className="primary-button" type="button" onClick={() => fileInputRef.current?.click()}>
                  <Upload size={16} aria-hidden="true" />
                  上传第一个素材
                </button>
              )}
            </div>
          ) : null}
        </div>
      )}
        </>
      ) : isLoading ? (
        <div className="material-library-loading material-project-loading" role="status">
          <Loader2 size={24} className="spin" aria-hidden="true" />
          正在加载项目组
        </div>
      ) : (
        <section className="material-project-home" aria-label="公司共享项目组">
          {projectGroups.length ? (
            <div className="material-project-grid">
              {projectGroups.map((group) => (
                <article className="material-project-card" key={group.id}>
                  <button
                    className="material-project-card-open"
                    type="button"
                    aria-label={`打开项目组 ${group.group_name}`}
                    onClick={() => void openProjectGroup(group)}
                  >
                    <span className="material-project-card-icon" aria-hidden="true">
                      <Folders size={24} />
                    </span>
                    <span className="material-project-card-copy">
                      <strong title={group.group_name}>{group.group_name}</strong>
                      <span className="material-project-card-counts">
                        <small>{group.folder_count} 个文件夹</small>
                        <small>{group.asset_count} 个素材</small>
                      </span>
                      <small className="material-project-card-time">
                        更新于 {formatUpdateTime(group.update_time)}
                      </small>
                    </span>
                  </button>
                  <div className="material-project-card-actions">
                    <button
                      type="button"
                      aria-label={`重命名项目组 ${group.group_name}`}
                      title="重命名项目组"
                      onClick={() => openProjectGroupDialog("rename", group)}
                    >
                      <Pencil size={15} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label={`删除项目组 ${group.group_name}`}
                      title="删除空项目组"
                      onClick={() => void deleteProjectGroup(group)}
                    >
                      <Trash2 size={15} aria-hidden="true" />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="material-library-empty material-project-empty">
              <Folders size={42} aria-hidden="true" />
              <strong>先建立一个团队项目组</strong>
              <span>按产品线或活动归档文件夹与素材，团队成员都能共享使用。</span>
              <button
                className="primary-button"
                type="button"
                onClick={() => openProjectGroupDialog("create")}
              >
                <Plus size={16} aria-hidden="true" />
                新建第一个项目组
              </button>
            </div>
          )}
        </section>
      )}

      {projectGroupDialog ? (
        <div className="material-picker-backdrop" role="presentation">
          <section
            className="folder-dialog material-project-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="material-project-dialog-title"
          >
            <h2 id="material-project-dialog-title">
              {projectGroupDialog.mode === "create" ? "新建项目组" : "重命名项目组"}
            </h2>
            <label>
              项目组名称
              <input
                ref={projectGroupInputRef}
                autoFocus
                value={projectGroupName}
                maxLength={80}
                onChange={(event) => {
                  setProjectGroupName(event.target.value);
                  if (projectGroupError) setProjectGroupError("");
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void saveProjectGroup();
                }}
              />
            </label>
            {projectGroupError ? (
              <div className="material-project-dialog-error" role="alert">
                {projectGroupError}
              </div>
            ) : null}
            <div>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setProjectGroupDialog(null)}
              >
                取消
              </button>
              <button
                className="primary-button"
                type="button"
                disabled={isProjectGroupSaving}
                onClick={() => void saveProjectGroup()}
              >
                {isProjectGroupSaving
                  ? "正在保存"
                  : projectGroupDialog.mode === "create"
                    ? "创建项目组"
                    : "保存项目组名称"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {folderDialog ? (
        <div className="material-picker-backdrop" role="presentation">
          <section className="folder-dialog" role="dialog" aria-modal="true" aria-labelledby="folder-dialog-title">
            <h2 id="folder-dialog-title">{folderDialog.mode === "create" ? "新建文件夹" : "重命名文件夹"}</h2>
            <label>
              文件夹名称
              <input
                autoFocus
                value={folderName}
                maxLength={100}
                onChange={(event) => setFolderName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void saveFolder();
                }}
              />
            </label>
            <div>
              <button className="secondary-button" type="button" onClick={() => setFolderDialog(null)}>取消</button>
              <button className="primary-button" type="button" onClick={() => void saveFolder()}>保存</button>
            </div>
          </section>
        </div>
      ) : null}

      {previewAsset ? (
        <div
          className="material-picker-backdrop material-preview-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closePreview();
          }}
        >
          <section
            className="material-preview-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="material-preview-title"
          >
            <header>
              <div>
                <strong id="material-preview-title">预览素材 {previewAsset.file_name}</strong>
                <span>{materialTypeLabel(previewAsset.file_type)} · {formatFileSize(previewAsset.file_size)}</span>
              </div>
              <button className="icon-button" type="button" aria-label="关闭素材预览" onClick={closePreview}>
                <X size={18} aria-hidden="true" />
              </button>
            </header>
            <div className="material-preview-stage">
              {isPreviewLoading ? (
                <div className="material-preview-state" role="status">
                  <Loader2 size={28} className="spin" aria-hidden="true" />
                  正在加载素材
                </div>
              ) : previewError ? (
                <div className="material-preview-state error" role="alert">{previewError}</div>
              ) : previewUrl && previewAsset.file_type === "video" ? (
                <video src={previewUrl} controls playsInline preload="metadata" />
              ) : previewUrl ? (
                <img src={previewUrl} alt={previewAsset.file_name} />
              ) : null}
            </div>
            <footer>
              {previewUrl ? (
                <a className="secondary-button" href={previewUrl} download={previewAsset.file_name}>
                  <Download size={16} aria-hidden="true" />
                  下载素材
                </a>
              ) : null}
              <button className="primary-button" type="button" onClick={closePreview}>关闭</button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
