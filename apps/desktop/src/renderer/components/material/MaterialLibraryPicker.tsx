import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronRight,
  Folder,
  FolderCheck,
  FolderOpen,
  Folders,
  ListChecks,
  Loader2,
  Search,
  X
} from "lucide-react";

import { api } from "../../api/client";
import type {
  MaterialAsset,
  MaterialLibraryListing,
  MaterialProjectGroup
} from "../../types";
import { MaterialThumbnail } from "./MaterialThumbnail";


type MaterialLibraryPickerProps = {
  open: boolean;
  allowedTypes?: Array<MaterialAsset["file_type"]>;
  initialSelection?: MaterialAsset[];
  selectionLimit?: number;
  onClose: () => void;
  onConfirm: (assets: MaterialAsset[]) => void;
};

const emptyListing: MaterialLibraryListing = {
  project_group_id: 0,
  current_folder: null,
  breadcrumbs: [],
  folders: [],
  assets: []
};
const emptyInitialSelection: MaterialAsset[] = [];

function materialTypeLabel(fileType: MaterialAsset["file_type"]) {
  if (fileType === "image") return "图片";
  if (fileType === "video") return "视频";
  return "脚本文档";
}


export function MaterialLibraryPicker({
  open,
  allowedTypes = ["image", "video"],
  initialSelection = emptyInitialSelection,
  selectionLimit,
  onClose,
  onConfirm
}: MaterialLibraryPickerProps) {
  const [folderId, setFolderId] = useState(0);
  const [projectGroups, setProjectGroups] = useState<MaterialProjectGroup[]>([]);
  const [projectGroupId, setProjectGroupId] = useState<number | null>(null);
  const [listing, setListing] = useState<MaterialLibraryListing>(emptyListing);
  const [selected, setSelected] = useState<Map<number, MaterialAsset>>(new Map());
  const [keyword, setKeyword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSelectingFolder, setIsSelectingFolder] = useState(false);
  const [message, setMessage] = useState("");
  const requestRef = useRef(0);
  const recursiveSelectionRequestRef = useRef(0);
  const selectedProjectGroup = projectGroups.find(
    (group) => group.id === projectGroupId
  ) ?? null;

  const invalidateRecursiveSelection = useCallback(() => {
    recursiveSelectionRequestRef.current += 1;
    setIsSelectingFolder(false);
  }, []);

  const load = useCallback(async (
    nextFolderId: number,
    nextKeyword: string,
    nextProjectGroupId: number
  ) => {
    invalidateRecursiveSelection();
    const requestId = ++requestRef.current;
    setIsLoading(true);
    try {
      const next = await api.listMaterialLibraryItems(
        nextFolderId,
        nextKeyword,
        "",
        false,
        nextProjectGroupId
      );
      if (requestId !== requestRef.current) return;
      setListing(next);
      setFolderId(nextFolderId);
      setMessage("");
    } catch (error) {
      if (requestId === requestRef.current) {
        setMessage(error instanceof Error ? error.message : "素材库加载失败");
      }
    } finally {
      if (requestId === requestRef.current) setIsLoading(false);
    }
  }, [invalidateRecursiveSelection]);

  const loadProjectGroups = useCallback(async () => {
    invalidateRecursiveSelection();
    const requestId = ++requestRef.current;
    setIsLoading(true);
    try {
      const nextGroups = await api.listMaterialProjectGroups();
      if (requestId !== requestRef.current) return;
      setProjectGroups(nextGroups);
      setMessage("");
    } catch (error) {
      if (requestId === requestRef.current) {
        setProjectGroups([]);
        setMessage(error instanceof Error ? error.message : "项目组加载失败");
      }
    } finally {
      if (requestId === requestRef.current) setIsLoading(false);
    }
  }, [invalidateRecursiveSelection]);

  useEffect(() => {
    invalidateRecursiveSelection();
    if (!open) {
      requestRef.current += 1;
      setIsLoading(false);
    } else {
      setSelected(new Map(initialSelection.map((asset) => [asset.id, asset])));
      setProjectGroupId(null);
      setFolderId(0);
      setListing(emptyListing);
      setKeyword("");
      void loadProjectGroups();
    }
    return () => {
      requestRef.current += 1;
      recursiveSelectionRequestRef.current += 1;
    };
  }, [initialSelection, invalidateRecursiveSelection, loadProjectGroups, open]);

  const visibleAssets = useMemo(
    () => listing.assets.filter((asset) => allowedTypes.includes(asset.file_type)),
    [allowedTypes, listing.assets]
  );

  if (!open) return null;

  function toggleAsset(asset: MaterialAsset) {
    setSelected((current) => {
      if (selectionLimit === 1 && !current.has(asset.id)) {
        return new Map([[asset.id, asset]]);
      }
      const next = new Map(current);
      if (next.has(asset.id)) next.delete(asset.id);
      else next.set(asset.id, asset);
      return next;
    });
  }

  const areVisibleAssetsSelected = visibleAssets.length > 0
    && visibleAssets.every((asset) => selected.has(asset.id));

  function toggleVisibleAssets() {
    setSelected((current) => {
      const next = new Map(current);
      if (areVisibleAssetsSelected) {
        visibleAssets.forEach((asset) => next.delete(asset.id));
      } else {
        visibleAssets.forEach((asset) => next.set(asset.id, asset));
      }
      return next;
    });
  }

  function returnToProjectGroups() {
    requestRef.current += 1;
    invalidateRecursiveSelection();
    setProjectGroupId(null);
    setFolderId(0);
    setListing(emptyListing);
    setKeyword("");
    setIsLoading(false);
    setMessage("");
  }

  function openProjectGroup(group: MaterialProjectGroup) {
    setProjectGroupId(group.id);
    setFolderId(0);
    setListing(emptyListing);
    setKeyword("");
    void load(0, "", group.id);
  }

  async function selectCurrentFolder() {
    if (!projectGroupId) return;
    const requestId = ++recursiveSelectionRequestRef.current;
    setIsSelectingFolder(true);
    try {
      const recursiveListing = await api.listMaterialLibraryItems(
        folderId,
        "",
        "",
        true,
        projectGroupId
      );
      if (requestId !== recursiveSelectionRequestRef.current) return;
      const compatibleAssets = recursiveListing.assets.filter((asset) =>
        allowedTypes.includes(asset.file_type)
      );
      setSelected((current) => {
        const next = new Map(current);
        compatibleAssets.forEach((asset) => next.set(asset.id, asset));
        return next;
      });
      setMessage(
        compatibleAssets.length
          ? "已选中当前文件夹及子文件夹中的全部可用素材"
          : "当前文件夹及子文件夹中没有可用素材"
      );
    } catch (error) {
      if (requestId === recursiveSelectionRequestRef.current) {
        setMessage(error instanceof Error ? error.message : "文件夹素材加载失败");
      }
    } finally {
      if (requestId === recursiveSelectionRequestRef.current) {
        setIsSelectingFolder(false);
      }
    }
  }

  function closePicker() {
    requestRef.current += 1;
    invalidateRecursiveSelection();
    setIsLoading(false);
    onClose();
  }

  return (
    <div className="material-picker-backdrop" role="presentation">
      <section
        className="material-picker-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="material-picker-title"
      >
        <header>
          <div>
            <span className="page-eyebrow">产品知识库</span>
            <h2 id="material-picker-title">选择创作素材</h2>
          </div>
          <button className="icon-button" type="button" aria-label="关闭素材选择" onClick={closePicker}>
            <X size={19} aria-hidden="true" />
          </button>
        </header>

        <div className="material-picker-tools">
          <nav className="material-breadcrumbs" aria-label="素材文件夹路径">
            <button type="button" onClick={returnToProjectGroups}>
              <FolderOpen size={16} aria-hidden="true" />
              全部项目组
            </button>
            {selectedProjectGroup ? (
              <span>
                <ChevronRight size={14} aria-hidden="true" />
                <button
                  type="button"
                  onClick={() => void load(0, "", selectedProjectGroup.id)}
                >
                  {selectedProjectGroup.group_name}
                </button>
              </span>
            ) : null}
            {projectGroupId ? listing.breadcrumbs.map((item) => (
              <span key={item.id}>
                <ChevronRight size={14} aria-hidden="true" />
                <button type="button" onClick={() => void load(item.id, "", projectGroupId)}>
                  {item.folder_name}
                </button>
              </span>
            )) : null}
          </nav>
          {projectGroupId ? (
            <form
              className="material-search"
              onSubmit={(event) => {
                event.preventDefault();
                void load(folderId, keyword, projectGroupId);
              }}
            >
              <Search size={16} aria-hidden="true" />
              <input
                aria-label="搜索素材"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="搜索当前文件夹"
              />
            </form>
          ) : null}
        </div>

        {message ? <div className="form-message">{message}</div> : null}
        <div className="material-picker-body">
          {isLoading ? (
            <div className="material-library-loading" role="status">
              <Loader2 size={24} className="spin" aria-hidden="true" />
              {projectGroupId ? "正在加载素材" : "正在加载项目组"}
            </div>
          ) : projectGroupId ? (
            <>
              {listing.folders.map((folder) => (
                <button
                  className="material-folder-tile"
                  type="button"
                  key={folder.id}
                  aria-label={`打开文件夹 ${folder.folder_name}`}
                  onClick={() => void load(folder.id, "", projectGroupId)}
                >
                  <Folder size={34} aria-hidden="true" />
                  <span>
                    <strong>{folder.folder_name}</strong>
                    <small>{folder.asset_count ?? 0} 个素材</small>
                  </span>
                </button>
              ))}
              {visibleAssets.map((asset) => {
                const isSelected = selected.has(asset.id);
                return (
                  <button
                    className={isSelected ? "material-asset-tile selected" : "material-asset-tile"}
                    type="button"
                    key={asset.id}
                    aria-label={asset.file_name}
                    aria-pressed={isSelected}
                    onClick={() => toggleAsset(asset)}
                  >
                    <MaterialThumbnail asset={asset} />
                    <span className="material-select-indicator">
                      {isSelected ? <Check size={14} aria-hidden="true" /> : null}
                    </span>
                    <span className="material-asset-copy">
                      <strong title={asset.file_name}>{asset.file_name}</strong>
                      <small>{materialTypeLabel(asset.file_type)}</small>
                    </span>
                  </button>
                );
              })}
              {!listing.folders.length && !visibleAssets.length ? (
                <div className="material-library-empty">
                  <FolderOpen size={34} aria-hidden="true" />
                  <strong>当前文件夹暂无可选素材</strong>
                  <span>请先到“产品知识库”上传图片、视频或脚本文档。</span>
                </div>
              ) : null}
            </>
          ) : projectGroups.length ? (
            <section className="material-project-home material-picker-project-home" aria-label="公司共享项目组">
              <div className="material-project-grid">
                {projectGroups.map((group) => (
                  <article className="material-project-card" key={group.id}>
                    <button
                      className="material-project-card-open"
                      type="button"
                      aria-label={`打开项目组 ${group.group_name}`}
                      onClick={() => openProjectGroup(group)}
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
                      </span>
                    </button>
                  </article>
                ))}
              </div>
            </section>
          ) : (
            <div className="material-library-empty">
              <Folders size={40} aria-hidden="true" />
              <strong>暂无可选项目组</strong>
              <span>请先到“产品知识库”建立项目组并上传素材。</span>
            </div>
          )}
        </div>

        <footer>
          <div className="material-picker-batch-actions">
            <span>已选择 {selected.size} 个素材</span>
            {selectionLimit !== 1 && projectGroupId ? (
              <>
                <button
                  className="secondary-button compact"
                  type="button"
                  disabled={visibleAssets.length === 0}
                  onClick={toggleVisibleAssets}
                >
                  <ListChecks size={15} aria-hidden="true" />
                  {areVisibleAssetsSelected ? "取消全选素材" : "全选当前素材"}
                </button>
                <button
                  className="secondary-button compact"
                  type="button"
                  disabled={isSelectingFolder}
                  onClick={() => void selectCurrentFolder()}
                >
                  {isSelectingFolder ? (
                    <Loader2 size={15} className="spin" aria-hidden="true" />
                  ) : (
                    <FolderCheck size={15} aria-hidden="true" />
                  )}
                  全选当前文件夹
                </button>
              </>
            ) : null}
          </div>
          <div>
            <button className="secondary-button" type="button" onClick={closePicker}>取消</button>
            <button
              className="primary-button"
              type="button"
              disabled={selected.size === 0}
              onClick={() => onConfirm(Array.from(selected.values()))}
            >
              确认使用
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
