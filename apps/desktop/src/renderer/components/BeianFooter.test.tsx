import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BeianFooter } from "./BeianFooter";


describe("BeianFooter", () => {
  it("renders the ICP record number linking to the MIIT site", () => {
    render(<BeianFooter />);

    const link = screen.getByRole("link", { name: "粤ICP备2025511993号-3" });
    expect(link).toHaveAttribute("href", "https://beian.miit.gov.cn/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });
});
