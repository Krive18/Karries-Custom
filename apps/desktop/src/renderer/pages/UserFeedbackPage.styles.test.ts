import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const styles = readFileSync(
  resolve(process.cwd(), "src/renderer/styles/karries-product-pages.css"),
  "utf8",
);


describe("feedback status filter interaction", () => {
  it("gives selected, hover, pressed and keyboard focus states clear feedback", () => {
    expect(styles).toMatch(
      /\.feedback-status-tabs button\[aria-selected="true"\]\s*\{[^}]*background:\s*var\(--karries-brand-600\);[^}]*color:\s*#ffffff;[^}]*box-shadow:/s,
    );
    expect(styles).toMatch(
      /\.feedback-status-tabs button:hover:not\(\[aria-selected="true"\]\)\s*\{[^}]*background:\s*var\(--karries-brand-50\);[^}]*color:\s*var\(--karries-brand-700\);/s,
    );
    expect(styles).toMatch(
      /\.feedback-status-tabs button:active\s*\{[^}]*transform:\s*scale\(0\.96\);/s,
    );
    expect(styles).toMatch(
      /\.feedback-status-tabs button:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--karries-brand-400\);/s,
    );
  });

  it("keeps the selected filter readable in dark mode", () => {
    expect(styles).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.feedback-status-tabs button\[aria-selected="true"\]\s*\{[^}]*background:\s*var\(--karries-brand-200\);[^}]*color:\s*var\(--karries-brand-800\);/,
    );
  });
});
