import { MoonStar } from "lucide-react";
import { useEffect, useState } from "react";

import {
  readThemePreference,
  setThemePreference,
  subscribeToThemeChanges,
  type ThemePreference
} from "../theme";


const themeOptions: Array<{ value: ThemePreference; label: string }> = [
  { value: "light", label: "浅色" },
  { value: "dark", label: "深色" },
  { value: "system", label: "跟随系统" }
];

export function ThemeSelector() {
  const [preference, setPreference] = useState<ThemePreference>(readThemePreference);

  useEffect(() => subscribeToThemeChanges(setPreference), []);

  return (
    <label className="theme-selector">
      <span><MoonStar size={16} aria-hidden="true" />界面主题</span>
      <select
        aria-label="界面主题"
        value={preference}
        onChange={(event) => {
          const nextPreference = event.target.value as ThemePreference;
          setPreference(nextPreference);
          setThemePreference(nextPreference);
        }}
      >
        {themeOptions.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}
