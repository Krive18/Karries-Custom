import {
  useCallback,
  useEffect,
  useRef,
  useState
} from "react";
import {
  ChevronRight,
  FileImage,
  FileText,
  Film,
  Folder,
  FolderOpen,
  FolderPlus,
  Folders,
  HardDrive,
  Loader2,
  PackageSearch,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload
} from "lucide-react";

import { managerApi } from "../api/managerClient";
import { ManagerEmployeeSelect } from "../components/ManagerEmployeeSelect";
import type {
  AdminProduct,
  AdminProductLibrarySummary,
  MaterialAsset,
  MaterialFolder,
  MaterialLibraryListing,
  MaterialProjectGroup
} from "../types";


type LibraryTab = "products" | "materials";

const emptySummary: AdminProductLibrarySummary = {
  product_count: 0,
  active_product_count: 0,
  folder_count: 0,
  asset_count: 0,
  image_count: 0,
  video_count: 0,
  document_count: 0,
  storage_bytes: 0
};

const emptyListing: MaterialLibraryListing = {
  project_group_id: 0,
  current_folder: null,
  breadcrumbs: [],
  folders: [],
  assets: []
};

type ProjectGroupDialogState = {
  mode: "create" | "rename";
  group: MaterialProjectGroup | null;
} | null;

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatMoney(value: number) {
  return value ? `¥${(value / 100).toLocaleString("zh-CN")}` : "-";
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

function ManagerAssetThumbnail({ asset }: { asset: MaterialAsset }) {
  const [source, setSource] = useState("");
  const [previewError, setPreviewError] = useState("");

  useEffect(() => {
    if (asset.file_type !== "image" && asset.file_type !== "video") return;
    let objectUrl = "";
    let active = true;
    const previewRequest = asset.file_type === "video"
      ? managerApi.getAdminMaterialAssetThumbnailBlob(asset.id)
      : managerApi.getAdminMaterialAssetBlob(asset.id);
    void previewRequest
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
        setPreviewError("");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setSource("");
        setPreviewError(error instanceof Error ? error.message : "缩略图加载失败");
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [asset.id, asset.file_type]);

  if (source) return <img src={source} alt={asset.file_name} loading="lazy" decoding="async" />;
  if (asset.file_type === "video") return <Film size={30} aria-hidden="true" />;
  if (asset.file_type === "image") {
    return (
      <span title={previewError || "图片预览"}>
        <FileImage size={30} aria-hidden="true" />
      </span>
    );
  }
  return <FileText size={30} aria-hidden="true" />;
}


export function ManagerProductLibraryPage() {
  const [tab, setTab] = useState<LibraryTab>("products");
  const [summary, setSummary] = useState(emptySummary);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [productTotal, setProductTotal] = useState(0);
  const [employeeId, setEmployeeId] = useState("");
  const [productStatus, setProductStatus] = useState("");
  const [productKeyword, setProductKeyword] = useState("");
  const [appliedProductKeyword, setAppliedProductKeyword] = useState("");
  const [projectGroups, setProjectGroups] = useState<MaterialProjectGroup[]>([]);
  const [projectGroupId, setProjectGroupId] = useState<number | null>(null);
  const [folderId, setFolderId] = useState(0);
  const [listing, setListing] = useState(emptyListing);
  const [materialKeyword, setMaterialKeyword] = useState("");
  const [appliedMaterialKeyword, setAppliedMaterialKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [materialLoading, setMaterialLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [projectGroupDialog, setProjectGroupDialog] = useState<ProjectGroupDialogState>(null);
  const [projectGroupName, setProjectGroupName] = useState("");
  const [projectGroupError, setProjectGroupError] = useState("");
  const [isProjectGroupSaving, setIsProjectGroupSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const projectGroupInputRef = useRef<HTMLInputElement | null>(null);
  const listingRequestRef = useRef(0);
  const projectGroupRequestRef = useRef(0);
  const selectedProjectGroup = projectGroups.find((group) => group.id === projectGroupId) ?? null;

  const loadSummary = useCallback(async () => {
    setSummary(await managerApi.getAdminProductLibrarySummary());
  }, []);

  const loadProducts = useCallback(async () => {
    const params = new URLSearchParams({ page: "1", page_size: "100" });
    if (employeeId) params.set("employee_id", employeeId);
    if (productStatus) params.set("status", productStatus);
    if (appliedProductKeyword) params.set("keyword", appliedProductKeyword);
    const result = await managerApi.listAdminProducts(params);
    setProducts(result.items);
    setProductTotal(result.total);
  }, [appliedProductKeyword, employeeId, productStatus]);

  const loadProjectGroups = useCallback(async () => {
    const requestId = ++projectGroupRequestRef.current;
    setMaterialLoading(true);
    try {
      const nextGroups = await managerApi.listAdminMaterialProjectGroups();
      if (requestId !== projectGroupRequestRef.current) return;
      setProjectGroups(nextGroups);
    } catch (loadError) {
      if (requestId !== projectGroupRequestRef.current) return;
      throw loadError;
    } finally {
      if (requestId === projectGroupRequestRef.current) setMaterialLoading(false);
    }
  }, []);

  const loadMaterials = useCallback(async (
    nextFolderId: number,
    nextKeyword: string,
    nextProjectGroupId: number
  ) => {
    const requestId = ++listingRequestRef.current;
    const params = new URLSearchParams({
      folder_id: String(nextFolderId),
      project_group_id: String(nextProjectGroupId)
    });
    if (nextKeyword.trim()) params.set("keyword", nextKeyword.trim());
    setMaterialLoading(true);
    try {
      const nextListing = await managerApi.listAdminMaterialItems(params);
      if (requestId !== listingRequestRef.current) return;
      setListing(nextListing);
      setFolderId(nextFolderId);
      setAppliedMaterialKeyword(nextKeyword.trim());
      setError("");
    } catch (loadError) {
      if (requestId !== listingRequestRef.current) return;
      setError(loadError instanceof Error ? loadError.message : "共享素材加载失败");
    } finally {
      if (requestId === listingRequestRef.current) setMaterialLoading(false);
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([loadSummary(), loadProducts(), loadProjectGroups()]);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "产品库数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [loadProducts, loadProjectGroups, loadSummary]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function changeProductStatus(product: AdminProduct) {
    try {
      await managerApi.updateAdminProductStatus(
        product.id,
        product.status === 1 ? 2 : 1
      );
      setMessage(`已${product.status === 1 ? "停用" : "启用"}商品“${product.product_name}”。`);
      await Promise.all([loadProducts(), loadSummary()]);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "商品状态更新失败");
    }
  }

  async function openProjectGroup(group: MaterialProjectGroup) {
    setProjectGroupId(group.id);
    setFolderId(0);
    setMaterialKeyword("");
    setAppliedMaterialKeyword("");
    setListing(emptyListing);
    setMessage("");
    setError("");
    await loadMaterials(0, "", group.id);
  }

  function returnToProjectGroups() {
    listingRequestRef.current += 1;
    setProjectGroupId(null);
    setFolderId(0);
    setMaterialKeyword("");
    setAppliedMaterialKeyword("");
    setListing(emptyListing);
    setMessage("");
    setError("");
    setMaterialLoading(false);
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
        const created = await managerApi.createAdminMaterialProjectGroup(name);
        projectGroupRequestRef.current += 1;
        setMaterialLoading(false);
        setProjectGroups((current) => [...current, created]);
      } else if (projectGroupDialog.group) {
        const renamed = await managerApi.renameAdminMaterialProjectGroup(
          projectGroupDialog.group.id,
          name
        );
        projectGroupRequestRef.current += 1;
        setMaterialLoading(false);
        setProjectGroups((current) => current.map((group) => (
          group.id === renamed.id ? renamed : group
        )));
      }
      setProjectGroupDialog(null);
      setProjectGroupName("");
      setError("");
    } catch (submitError) {
      setProjectGroupError(submitError instanceof Error ? submitError.message : "项目组操作失败");
      projectGroupInputRef.current?.focus();
    } finally {
      setIsProjectGroupSaving(false);
    }
  }

  async function deleteProjectGroup(group: MaterialProjectGroup) {
    if (!window.confirm(`确认删除空项目组“${group.group_name}”吗？`)) return;
    try {
      await managerApi.deleteAdminMaterialProjectGroup(group.id);
      projectGroupRequestRef.current += 1;
      setMaterialLoading(false);
      setProjectGroups((current) => current.filter((item) => item.id !== group.id));
      setError("");
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "项目组内仍有文件夹或素材，请先清空后再删除"
      );
    }
  }

  async function createFolder() {
    if (!projectGroupId) return;
    const name = window.prompt("请输入新文件夹名称");
    if (!name?.trim()) return;
    try {
      await managerApi.createAdminMaterialFolder(folderId, name.trim(), projectGroupId);
      setMessage("文件夹已创建。");
      await Promise.all([
        loadMaterials(folderId, appliedMaterialKeyword, projectGroupId),
        loadSummary()
      ]);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "文件夹创建失败");
    }
  }

  async function renameFolder(folder: MaterialFolder) {
    if (!projectGroupId) return;
    const name = window.prompt("请输入新的文件夹名称", folder.folder_name);
    if (!name?.trim() || name.trim() === folder.folder_name) return;
    try {
      await managerApi.renameAdminMaterialFolder(folder.id, name.trim());
      await loadMaterials(folderId, appliedMaterialKeyword, projectGroupId);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "文件夹重命名失败");
    }
  }

  async function deleteFolder(folder: MaterialFolder) {
    if (!projectGroupId) return;
    if (!window.confirm(`确认删除空文件夹“${folder.folder_name}”吗？`)) return;
    try {
      await managerApi.deleteAdminMaterialFolder(folder.id);
      await Promise.all([
        loadMaterials(folderId, appliedMaterialKeyword, projectGroupId),
        loadSummary()
      ]);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "文件夹内仍有内容，无法删除"
      );
    }
  }

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return;
    if (!projectGroupId || folderId === 0) {
      setMessage("请先进入产品文件夹后再上传素材。");
      return;
    }
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        await managerApi.uploadAdminMaterialAsset(folderId, file);
      }
      setMessage(`已上传 ${files.length} 个素材。`);
      await Promise.all([
        loadMaterials(folderId, appliedMaterialKeyword, projectGroupId),
        loadSummary()
      ]);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "素材上传失败");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function deleteAsset(asset: MaterialAsset) {
    if (!projectGroupId) return;
    if (!window.confirm(`确认删除素材“${asset.file_name}”吗？`)) return;
    try {
      await managerApi.deleteAdminMaterialAsset(asset.id);
      await Promise.all([
        loadMaterials(folderId, appliedMaterialKeyword, projectGroupId),
        loadSummary()
      ]);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "素材删除失败");
    }
  }

  return (
    <section className="manager-product-library-page">
      <header className="manager-page-header">
        <div>
          <h1>产品库管理</h1>
          <p>查看员工维护的商品档案，并统一管理团队共享素材</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void loadAll()}>
          <RefreshCw size={16} className={loading ? "spin" : ""} />刷新数据
        </button>
      </header>

      {error ? <div className="form-message error" role="alert">{error}</div> : null}
      {message ? <div className="form-message success" role="status">{message}</div> : null}

      <div className="manager-library-kpis">
        <article><PackageSearch size={20} /><span>商品档案</span><strong>{summary.product_count}</strong><small>{summary.active_product_count} 个启用</small></article>
        <article><FolderOpen size={20} /><span>素材文件夹</span><strong>{summary.folder_count}</strong><small>团队共享目录</small></article>
        <article><FileImage size={20} /><span>图片素材</span><strong>{summary.image_count}</strong><small>{summary.video_count} 个视频</small></article>
        <article><HardDrive size={20} /><span>已用存储</span><strong>{formatBytes(summary.storage_bytes)}</strong><small>{summary.asset_count} 个素材文件</small></article>
      </div>

      <div className="manager-library-tabs" role="tablist" aria-label="产品库分类">
        <button type="button" className={tab === "products" ? "active" : ""} onClick={() => setTab("products")}>
          <PackageSearch size={17} />商品档案
        </button>
        <button type="button" className={tab === "materials" ? "active" : ""} onClick={() => setTab("materials")}>
          <FolderOpen size={17} />共享素材
        </button>
      </div>

      {tab === "products" ? (
        <section className="manager-products-section">
          <form
            className="manager-product-filters"
            onSubmit={(event) => {
              event.preventDefault();
              setAppliedProductKeyword(productKeyword.trim());
            }}
          >
            <ManagerEmployeeSelect value={employeeId} onChange={setEmployeeId} />
            <label>
              商品状态
              <select value={productStatus} onChange={(event) => setProductStatus(event.target.value)}>
                <option value="">全部状态</option>
                <option value="1">启用</option>
                <option value="2">停用</option>
              </select>
            </label>
            <label className="manager-product-search">
              搜索商品
              <span><Search size={16} /><input value={productKeyword} placeholder="名称、品牌或 SKU" onChange={(event) => setProductKeyword(event.target.value)} /></span>
            </label>
            <button className="primary-button" type="submit">查询</button>
          </form>

          <div className="manager-product-list-heading">
            <div><h2>商品档案</h2><p>共 {productTotal} 个商品</p></div>
            <span>商品资料由员工在用户端录入，管理端负责查看与停用</span>
          </div>
          <div className="manager-product-list">
            {products.map((product) => (
              <article key={product.id}>
                <div className="manager-product-avatar">
                  <PackageSearch size={24} aria-hidden="true" />
                </div>
                <div className="manager-product-main">
                  <div>
                    <strong>{product.product_name}</strong>
                    <span className={product.status === 1 ? "active" : "disabled"}>{product.status === 1 ? "启用" : "停用"}</span>
                  </div>
                  <p>{product.brand_name || "未填写品牌"} · {product.category || "未分类"} · SKU {product.sku || "-"}</p>
                </div>
                <div><span>负责员工</span><strong>{product.employee_name}</strong><small>{product.employee_login}</small></div>
                <div><span>素材</span><strong>{product.material_count}</strong><small>个关联文件</small></div>
                <div><span>价格</span><strong>{formatMoney(product.activity_price_cent || product.price_cent)}</strong><small>{product.activity_price_cent ? `原价 ${formatMoney(product.price_cent)}` : "当前价格"}</small></div>
                <button className="secondary-button" type="button" onClick={() => void changeProductStatus(product)}>
                  {product.status === 1 ? "停用商品" : "重新启用"}
                </button>
              </article>
            ))}
            {!products.length ? <div className="manager-empty-state">暂无符合条件的商品档案</div> : null}
          </div>
        </section>
      ) : (
        <section className="manager-materials-section">
          {projectGroupId && selectedProjectGroup ? (
            <>
              <div className="manager-material-toolbar">
                <nav aria-label="素材文件夹路径">
                  <button
                    type="button"
                    aria-label="返回共享素材项目组"
                    onClick={returnToProjectGroups}
                  >
                    <FolderOpen size={17} aria-hidden="true" />共享素材
                  </button>
                  <span>
                    <ChevronRight size={14} aria-hidden="true" />
                    <button
                      type="button"
                      onClick={() => {
                        setAppliedMaterialKeyword("");
                        setMaterialKeyword("");
                        void loadMaterials(0, "", projectGroupId);
                      }}
                    >
                      {selectedProjectGroup.group_name}
                    </button>
                  </span>
                  {listing.breadcrumbs.map((folder) => (
                    <span key={folder.id}>
                      <ChevronRight size={14} aria-hidden="true" />
                      <button
                        type="button"
                        onClick={() => {
                          setAppliedMaterialKeyword("");
                          setMaterialKeyword("");
                          void loadMaterials(folder.id, "", projectGroupId);
                        }}
                      >
                        {folder.folder_name}
                      </button>
                    </span>
                  ))}
                </nav>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void loadMaterials(folderId, materialKeyword.trim(), projectGroupId);
                  }}
                >
                  <Search size={16} aria-hidden="true" />
                  <input
                    aria-label="搜索当前文件夹"
                    value={materialKeyword}
                    placeholder="搜索当前文件夹"
                    onChange={(event) => setMaterialKeyword(event.target.value)}
                  />
                </form>
                <button className="secondary-button" type="button" onClick={() => void createFolder()}>
                  <FolderPlus size={17} aria-hidden="true" />新建文件夹
                </button>
                {folderId > 0 ? (
                  <button className="primary-button" type="button" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
                    {uploading ? <Loader2 className="spin" size={17} aria-hidden="true" /> : <Upload size={17} aria-hidden="true" />}
                    {uploading ? "上传中" : "上传素材"}
                  </button>
                ) : <span aria-hidden="true" />}
                <input
                  ref={fileInputRef}
                  className="hidden-file-input"
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,.doc,.docx,.xls,.xlsx,.pdf"
                  onChange={(event) => void uploadFiles(event.target.files)}
                />
              </div>

              <div className="manager-material-summary-line">
                <span><Folder size={15} aria-hidden="true" />{listing.folders.length} 个文件夹</span>
                <span><FileImage size={15} aria-hidden="true" />{listing.assets.filter((asset) => asset.file_type === "image").length} 张图片</span>
                <span><Film size={15} aria-hidden="true" />{listing.assets.filter((asset) => asset.file_type === "video").length} 个视频</span>
                <span><FileText size={15} aria-hidden="true" />{listing.assets.filter((asset) => !["image", "video"].includes(asset.file_type)).length} 个文档</span>
              </div>

              {materialLoading ? (
                <div className="manager-material-empty" role="status">
                  <Loader2 className="spin" size={28} aria-hidden="true" />
                  <strong>正在整理共享素材</strong>
                </div>
              ) : (
                <div className="manager-material-browser">
                  {listing.folders.map((folder) => (
                    <article className="manager-folder-tile" key={folder.id}>
                      <button
                        type="button"
                        aria-label={`打开文件夹 ${folder.folder_name}`}
                        onClick={() => {
                          setMaterialKeyword("");
                          void loadMaterials(folder.id, "", projectGroupId);
                        }}
                      >
                        <Folder size={56} aria-hidden="true" />
                        <strong title={folder.folder_name}>{folder.folder_name}</strong>
                        <span>{folder.asset_count ?? 0} 个素材</span>
                      </button>
                      <div>
                        <button type="button" title="重命名" aria-label={`重命名文件夹 ${folder.folder_name}`} onClick={() => void renameFolder(folder)}><Pencil size={14} aria-hidden="true" /></button>
                        <button type="button" title="删除空文件夹" aria-label={`删除文件夹 ${folder.folder_name}`} onClick={() => void deleteFolder(folder)}><Trash2 size={14} aria-hidden="true" /></button>
                      </div>
                    </article>
                  ))}
                  {listing.assets.map((asset) => (
                    <article className="manager-asset-tile" key={asset.id}>
                      <div className="manager-asset-preview"><ManagerAssetThumbnail asset={asset} /></div>
                      <strong title={asset.file_name}>{asset.file_name}</strong>
                      <span>{formatBytes(asset.file_size)}</span>
                      <button type="button" title="删除素材" aria-label={`删除素材 ${asset.file_name}`} onClick={() => void deleteAsset(asset)}><Trash2 size={14} aria-hidden="true" /></button>
                    </article>
                  ))}
                  {!listing.folders.length && !listing.assets.length ? (
                    <div className="manager-material-empty">
                      <FolderOpen size={44} aria-hidden="true" />
                      <strong>当前文件夹还没有内容</strong>
                      <span>可新建文件夹，或上传产品图片、视频和脚本文档</span>
                    </div>
                  ) : null}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="manager-material-project-toolbar">
                <div>
                  <strong>公司共享项目组</strong>
                  <span>按产品线或活动组织文件夹与素材，团队成员统一使用。</span>
                </div>
                <button className="primary-button" type="button" onClick={() => openProjectGroupDialog("create")}>
                  <Plus size={17} aria-hidden="true" />新建项目组
                </button>
              </div>
              {materialLoading ? (
                <div className="manager-material-empty material-project-loading" role="status">
                  <Loader2 className="spin" size={28} aria-hidden="true" />
                  <strong>正在加载项目组</strong>
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
                            <span className="material-project-card-icon" aria-hidden="true"><Folders size={24} /></span>
                            <span className="material-project-card-copy">
                              <strong title={group.group_name}>{group.group_name}</strong>
                              <span className="material-project-card-counts">
                                <small>{group.folder_count} 个文件夹</small>
                                <small>{group.asset_count} 个素材</small>
                              </span>
                              <small className="material-project-card-time">更新于 {formatUpdateTime(group.update_time)}</small>
                            </span>
                          </button>
                          <div className="material-project-card-actions">
                            <button
                              type="button"
                              title="重命名项目组"
                              aria-label={`重命名项目组 ${group.group_name}`}
                              onClick={() => openProjectGroupDialog("rename", group)}
                            >
                              <Pencil size={15} aria-hidden="true" />
                            </button>
                            <button
                              type="button"
                              title="删除空项目组"
                              aria-label={`删除项目组 ${group.group_name}`}
                              onClick={() => void deleteProjectGroup(group)}
                            >
                              <Trash2 size={15} aria-hidden="true" />
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="manager-material-empty material-project-empty">
                      <Folders size={44} aria-hidden="true" />
                      <strong>先建立一个团队项目组</strong>
                      <span>按产品线或活动归档文件夹与素材，团队成员都能共享使用。</span>
                      <button className="primary-button" type="button" onClick={() => openProjectGroupDialog("create")}>
                        <Plus size={16} aria-hidden="true" />新建第一个项目组
                      </button>
                    </div>
                  )}
                </section>
              )}
            </>
          )}

          {projectGroupDialog ? (
            <div className="material-picker-backdrop" role="presentation">
              <section
                className="folder-dialog material-project-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="manager-material-project-dialog-title"
              >
                <h2 id="manager-material-project-dialog-title">
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
                {projectGroupError ? <div className="material-project-dialog-error" role="alert">{projectGroupError}</div> : null}
                <div>
                  <button className="secondary-button" type="button" onClick={() => setProjectGroupDialog(null)}>取消</button>
                  <button className="primary-button" type="button" disabled={isProjectGroupSaving} onClick={() => void saveProjectGroup()}>
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
        </section>
      )}
    </section>
  );
}
