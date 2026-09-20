import { ALargeSmall } from "lucide-react";
import { useEffect, useState } from "react";

import {
  readFontScale,
  setFontScale,
  subscribeToFontScaleChanges,
  type FontScale
} from "../fontScale";


const fontScaleOptions: Array<{ value: FontScale; label: string }> = [
  { value: "compact", label: "紧凑" },
  { value: "standard", label: "标准" },
  { value: "large", label: "大字" }
];

export function FontScaleSelector() {
  const [scale, setScale] = useState<FontScale>(readFontScale);

  useEffect(() => subscribeToFontScaleChanges(setScale), []);

  return (
    <label className="theme-selector font-scale-selector">
      <span><ALargeSmall size={16} aria-hidden="true" />界面缩放</span>
      <select
        aria-label="界面缩放"
        value={scale}
        onChange={(event) => {
          const nextScale = event.target.value as FontScale;
          setScale(nextScale);
          setFontScale(nextScale);
        }}
      >
        {fontScaleOptions.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}
