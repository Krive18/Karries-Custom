import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { FontScaleSelector } from "./FontScaleSelector";


describe("FontScaleSelector", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-font-scale");
  });

  it("persists a compact scale and applies it immediately", () => {
    render(<FontScaleSelector />);

    fireEvent.change(screen.getByLabelText("界面缩放"), {
      target: { value: "compact" }
    });

    expect(window.localStorage.getItem("karries-font-scale")).toBe("compact");
    expect(document.documentElement).toHaveAttribute("data-font-scale", "compact");
  });

  it("persists a large scale and applies it immediately", () => {
    render(<FontScaleSelector />);

    fireEvent.change(screen.getByLabelText("界面缩放"), {
      target: { value: "large" }
    });

    expect(window.localStorage.getItem("karries-font-scale")).toBe("large");
    expect(document.documentElement).toHaveAttribute("data-font-scale", "large");
  });

  it("defaults to the standard scale", () => {
    render(<FontScaleSelector />);

    expect(screen.getByLabelText("界面缩放")).toHaveValue("standard");
  });
});
