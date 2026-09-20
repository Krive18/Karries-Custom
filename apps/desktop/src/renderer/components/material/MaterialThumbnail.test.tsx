import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import type { MaterialAsset } from "../../types";
import { MaterialThumbnail } from "./MaterialThumbnail";


const videoAsset: MaterialAsset = {
  id: 9,
  tenant_id: 1,
  user_id: 1,
  folder_id: 3,
  product_id: 0,
  package_id: 0,
  file_name: "product-demo.mp4",
  file_type: "video",
  mime_type: "video/mp4",
  file_size: 1024,
  create_time: 1,
  update_time: 1
};


describe("MaterialThumbnail", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("falls back to the video content when thumbnail generation is unavailable", async () => {
    vi.spyOn(api, "getMaterialAssetThumbnailBlob").mockRejectedValue(
      new Error("thumbnail unavailable")
    );
    vi.spyOn(api, "getMaterialAssetBlob").mockResolvedValue(
      new Blob(["video"], { type: "video/mp4" })
    );
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:video-preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    render(<MaterialThumbnail asset={videoAsset} />);

    await waitFor(() => {
      expect(api.getMaterialAssetBlob).toHaveBeenCalledWith(videoAsset.id);
    });
    const preview = screen.getByLabelText("视频素材预览");
    expect(preview.tagName).toBe("VIDEO");
    expect(preview).toHaveAttribute("src", "blob:video-preview");
  });
});
