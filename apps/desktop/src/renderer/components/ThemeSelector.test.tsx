import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeSelector } from "./ThemeSelector";


describe("ThemeSelector", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-theme-preference");
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn()
      })
    });
  });

  it("persists a dark preference and applies it immediately", () => {
    render(<ThemeSelector />);

    fireEvent.change(screen.getByLabelText("界面主题"), {
      target: { value: "dark" }
    });

    expect(window.localStorage.getItem("karries-theme-preference")).toBe("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(document.documentElement).toHaveAttribute("data-theme-preference", "dark");
  });

  it("resolves the system preference without losing the system setting", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn()
      })
    });
    render(<ThemeSelector />);

    fireEvent.change(screen.getByLabelText("界面主题"), {
      target: { value: "system" }
    });

    expect(window.localStorage.getItem("karries-theme-preference")).toBe("system");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(document.documentElement).toHaveAttribute("data-theme-preference", "system");
  });
});
