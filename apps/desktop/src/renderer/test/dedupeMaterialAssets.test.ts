import { describe, expect, it } from "vitest";

import { dedupeMaterialAssets } from "../components/material/dedupeMaterialAssets";
import type { MaterialAsset } from "../types";


function asset(overrides: Partial<MaterialAsset> = {}): MaterialAsset {
  return {
    id: 1,
    tenant_id: 1,
    user_id: 1,
    folder_id: 1,
    product_id: 0,
    package_id: 0,
    file_name: "product.jpg",
    file_type: "image",
    mime_type: "image/jpeg",
    file_size: 1024,
    create_time: 1,
    update_time: 1,
    ...overrides
  };
}


describe("dedupeMaterialAssets", () => {
  it("keeps only one copy of duplicate product material records", () => {
    const result = dedupeMaterialAssets([
      asset(),
      asset({ id: 2, create_time: 2, update_time: 2 }),
      asset({ id: 3, file_name: "detail.jpg" })
    ]);

    expect(result.map((item) => item.id)).toEqual([1, 3]);
  });

  it("does not collapse files with different sizes", () => {
    const result = dedupeMaterialAssets([
      asset(),
      asset({ id: 2, file_size: 2048 })
    ]);

    expect(result).toHaveLength(2);
  });
});
