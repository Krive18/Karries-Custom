import { useEffect, useState } from "react";
import { FileImage, FileText, Film, Loader2 } from "lucide-react";

import { api } from "../../api/client";
import type { MaterialAsset } from "../../types";


type MaterialThumbnailProps = {
  asset: MaterialAsset;
  className?: string;
};


export function MaterialThumbnail({
  asset,
  className = ""
}: MaterialThumbnailProps) {
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewKind, setPreviewKind] = useState<"image" | "video">("image");
  const isPreviewable = asset.file_type === "image" || asset.file_type === "video";
  const [isLoading, setIsLoading] = useState(isPreviewable);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!isPreviewable) {
      setPreviewUrl("");
      setIsLoading(false);
      setFailed(false);
      return;
    }

    let active = true;
    let objectUrl = "";
    setIsLoading(true);
    setFailed(false);
    setPreviewKind("image");
    const previewRequest = asset.file_type === "video"
      ? api.getMaterialAssetThumbnailBlob(asset.id)
          .then((blob) => ({ blob, kind: "image" as const }))
          .catch(async () => ({
            blob: await api.getMaterialAssetBlob(asset.id),
            kind: "video" as const
          }))
      : api.getMaterialAssetBlob(asset.id)
          .then((blob) => ({ blob, kind: "image" as const }));
    void previewRequest
      .then(({ blob, kind }) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewKind(kind);
        setPreviewUrl(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [asset.file_type, asset.id, isPreviewable]);

  const classes = `material-thumbnail ${className}`.trim();
  if (asset.file_type !== "image") {
    if (asset.file_type === "video" && isLoading) {
      return (
        <div className={`${classes} loading`} aria-label="正在加载视频封面">
          <Loader2 size={24} className="spin" aria-hidden="true" />
        </div>
      );
    }
    if (asset.file_type === "video" && !failed && previewUrl) {
      return (
        <div className={`${classes} video has-preview`}>
          {previewKind === "video" ? (
            <video
              src={previewUrl}
              aria-label="视频素材预览"
              muted
              playsInline
              preload="metadata"
            />
          ) : (
            <img src={previewUrl} alt={asset.file_name} loading="lazy" decoding="async" />
          )}
          <span className="material-video-badge" aria-label="视频素材">
            <Film size={13} aria-hidden="true" />
          </span>
        </div>
      );
    }
    if (asset.file_type === "video") {
      return (
        <div className={`${classes} video failed`} aria-label="视频封面不可用">
          <Film size={30} aria-hidden="true" />
          <span>VIDEO</span>
        </div>
      );
    }
    return (
      <div className={`${classes} document`} aria-label="脚本文档">
        <FileText size={30} aria-hidden="true" />
        <span>{asset.file_type === "word" ? "WORD" : asset.file_type === "excel" ? "EXCEL" : "FILE"}</span>
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className={`${classes} loading`} aria-label="正在加载图片">
        <Loader2 size={24} className="spin" aria-hidden="true" />
      </div>
    );
  }
  if (failed || !previewUrl) {
    return (
      <div className={`${classes} failed`} aria-label="图片预览不可用">
        <FileImage size={28} aria-hidden="true" />
      </div>
    );
  }
  return (
    <img
      className={classes}
      src={previewUrl}
      alt={asset.file_name}
      loading="lazy"
      decoding="async"
    />
  );
}
