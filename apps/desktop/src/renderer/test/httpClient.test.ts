import { afterEach, describe, expect, it, vi } from "vitest";

import { createPortalRequest } from "../api/httpClient";
import { customerApi } from "../api/client";
import { managerApi } from "../api/managerClient";


describe("portal API routing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it.each(["customer", "manager", "developer"] as const)(
    "uses same-origin /api paths for the %s portal",
    async (portal) => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { ok: true }, error: null })
      });
      vi.stubGlobal("fetch", fetchMock);

      await createPortalRequest(portal)("/api/health");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/health",
        expect.objectContaining({
          headers: expect.objectContaining({ "Content-Type": "application/json" })
        })
      );
    }
  );

  it("returns a stable error when the server response is empty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      text: async () => ""
    }));

    await expect(createPortalRequest("customer")("/api/viral-analysis/jobs/1/run"))
      .rejects.toMatchObject({
        code: "EMPTY_RESPONSE",
        status: 502
      });
  });

  it("returns a stable error when an upstream proxy returns HTML", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      text: async () => "<html>Bad Gateway</html>"
    }));

    await expect(createPortalRequest("customer")("/api/viral-analysis/jobs/1/run"))
      .rejects.toMatchObject({
        code: "INVALID_RESPONSE",
        status: 502
      });
  });

  it("returns a readable network error when the backend cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(createPortalRequest("customer")("/api/inspiration/sessions/1/attachments"))
      .rejects.toMatchObject({
        code: "NETWORK_ERROR",
        status: 0,
        message: "无法连接本地服务，请确认后端已启动后重试。"
      });
  });

  it("uses the customer material project-group CRUD and group-scoped folder contracts", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: {}, error: null })
    });
    vi.stubGlobal("fetch", fetchMock);

    await customerApi.listMaterialProjectGroups();
    await customerApi.createMaterialProjectGroup("秋季上新");
    await customerApi.renameMaterialProjectGroup(17, "秋季上新 2.0");
    await customerApi.deleteMaterialProjectGroup(17);
    await customerApi.listMaterialLibraryItems(7, "", "", false, 3);
    await customerApi.createMaterialFolder(7, "视频脚本", 3);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/material-library/project-groups",
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/material-library/project-groups",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ group_name: "秋季上新" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/material-library/project-groups/17",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ group_name: "秋季上新 2.0" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/material-library/project-groups/17",
      expect.objectContaining({ method: "DELETE" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/material-library/items?folder_id=7&project_group_id=3",
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/material-library/folders",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          project_group_id: 3,
          parent_id: 7,
          folder_name: "视频脚本"
        })
      })
    );
  });

  it("uses the manager material project-group CRUD and group-scoped folder contracts", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: {}, error: null })
    });
    vi.stubGlobal("fetch", fetchMock);
    const params = new URLSearchParams({ folder_id: "7" });
    params.set("project_group_id", "3");

    await managerApi.listAdminMaterialProjectGroups();
    await managerApi.createAdminMaterialProjectGroup("秋季上新");
    await managerApi.renameAdminMaterialProjectGroup(17, "秋季上新 2.0");
    await managerApi.deleteAdminMaterialProjectGroup(17);
    await managerApi.listAdminMaterialItems(params);
    await managerApi.createAdminMaterialFolder(7, "视频脚本", 3);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/admin/product-library/project-groups",
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/admin/product-library/project-groups",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ group_name: "秋季上新" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/admin/product-library/project-groups/17",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ group_name: "秋季上新 2.0" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/admin/product-library/project-groups/17",
      expect.objectContaining({ method: "DELETE" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/admin/product-library/items?folder_id=7&project_group_id=3",
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/admin/product-library/folders",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          project_group_id: 3,
          parent_id: 7,
          folder_name: "视频脚本"
        })
      })
    );
  });

  it("falls back to the existing job endpoint when the history route is unavailable", async () => {
    const legacyJob = {
      id: 17,
      job_title: "历史视频任务",
      post_title: "",
      post_body: "",
      post_tags: [],
      script_text: "提交时的视频脚本",
      requirement_text: "保留真实使用场景",
      materials: [
        {
          material_file_id: 8,
          file_name: "reference.mp4",
          file_type: "video",
          file_path: "",
          mime_type: "video/mp4",
          file_size: 1024
        }
      ],
      request_snapshot: { job_title: "历史视频任务", materials: [] },
      creation_mode: "standard",
      creation_mode_label: "标准模式",
      credit_cost: 160,
      xhs_account_id: 3,
      xhs_account_name: "账号 1111",
      planned_publish_time: 1_800_000_000,
      status: 2,
      status_name: "in_production",
      status_text: "视频制作中",
      delivery_versions: [],
      revision_count: 0,
      create_time: 1_700_000_000,
      update_time: 1_700_000_100,
      delivered_time: 0
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({
          success: false,
          data: null,
          error: { code: "NOT_FOUND", message: "请求未完成" }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: legacyJob, error: null })
      });
    vi.stubGlobal("fetch", fetchMock);

    const history = await customerApi.getVideoEditJobHistory(17);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/video-edit/jobs/17/history",
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/video-edit/jobs/17",
      expect.any(Object)
    );
    expect(history.request_snapshot.script_text).toBe("提交时的视频脚本");
    expect(history.request_snapshot.materials).toEqual(legacyJob.materials);
    expect(history.delivery_assets).toEqual([]);
  });
});
