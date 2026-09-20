import type { MaterialAsset } from "../../types";


function materialFingerprint(asset: MaterialAsset) {
  return [
    asset.file_name.trim().toLocaleLowerCase(),
    asset.file_size,
    asset.mime_type.trim().toLocaleLowerCase()
  ].join("|");
}


export function dedupeMaterialAssets(assets: MaterialAsset[]) {
  const seen = new Set<string>();
  return assets.filter((asset) => {
    const fingerprint = materialFingerprint(asset);
    if (seen.has(fingerprint)) return false;
    seen.add(fingerprint);
    return true;
  });
}
