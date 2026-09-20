export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = Exclude<ThemePreference, "system">;

export const THEME_STORAGE_KEY = "karries-theme-preference";
const THEME_CHANGE_EVENT = "karries-theme-change";
const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

function isThemePreference(value: string | null): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

export function readThemePreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference !== "system") return preference;
  return window.matchMedia?.(DARK_MODE_QUERY).matches ? "dark" : "light";
}

export function applyTheme(preference: ThemePreference): ResolvedTheme {
  const resolved = resolveTheme(preference);
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.dataset.theme = resolved;
  return resolved;
}

export function initializeTheme(): ThemePreference {
  const preference = readThemePreference();
  applyTheme(preference);
  return preference;
}

export function setThemePreference(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Theme switching still works for the current page without persistence.
  }
  applyTheme(preference);
  window.dispatchEvent(new CustomEvent<ThemePreference>(THEME_CHANGE_EVENT, {
    detail: preference
  }));
}

export function subscribeToThemeChanges(
  listener: (preference: ThemePreference) => void
): () => void {
  const media = window.matchMedia?.(DARK_MODE_QUERY);
  const onPreferenceChange = (event: Event) => {
    const preference = (event as CustomEvent<ThemePreference>).detail;
    listener(preference);
  };
  const onSystemThemeChange = () => {
    const preference = readThemePreference();
    if (preference === "system") {
      applyTheme(preference);
      listener(preference);
    }
  };

  window.addEventListener(THEME_CHANGE_EVENT, onPreferenceChange);
  media?.addEventListener?.("change", onSystemThemeChange);
  return () => {
    window.removeEventListener(THEME_CHANGE_EVENT, onPreferenceChange);
    media?.removeEventListener?.("change", onSystemThemeChange);
  };
}
