export type FontScale = "compact" | "standard" | "large";

export const FONT_SCALE_STORAGE_KEY = "karries-font-scale";
const FONT_SCALE_CHANGE_EVENT = "karries-font-scale-change";

function isFontScale(value: string | null): value is FontScale {
  return value === "compact" || value === "standard" || value === "large";
}

export function readFontScale(): FontScale {
  try {
    const stored = window.localStorage.getItem(FONT_SCALE_STORAGE_KEY);
    return isFontScale(stored) ? stored : "standard";
  } catch {
    return "standard";
  }
}

export function applyFontScale(scale: FontScale): void {
  document.documentElement.dataset.fontScale = scale;
}

export function initializeFontScale(): FontScale {
  const scale = readFontScale();
  applyFontScale(scale);
  return scale;
}

export function setFontScale(scale: FontScale): void {
  try {
    window.localStorage.setItem(FONT_SCALE_STORAGE_KEY, scale);
  } catch {
    // Font scaling still works for the current page without persistence.
  }
  applyFontScale(scale);
  window.dispatchEvent(new CustomEvent<FontScale>(FONT_SCALE_CHANGE_EVENT, {
    detail: scale
  }));
}

export function subscribeToFontScaleChanges(
  listener: (scale: FontScale) => void
): () => void {
  const onScaleChange = (event: Event) => {
    const scale = (event as CustomEvent<FontScale>).detail;
    listener(scale);
  };

  window.addEventListener(FONT_SCALE_CHANGE_EVENT, onScaleChange);
  return () => {
    window.removeEventListener(FONT_SCALE_CHANGE_EVENT, onScaleChange);
  };
}
