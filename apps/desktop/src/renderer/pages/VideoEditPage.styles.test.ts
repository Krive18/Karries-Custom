import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const styles = readFileSync(resolve(process.cwd(), "src/renderer/styles.css"), "utf8");
const designSystem = readFileSync(
  resolve(process.cwd(), "src/renderer/styles/karries-design-system.css"),
  "utf8",
);
const videoEditPage = readFileSync(
  resolve(process.cwd(), "src/renderer/pages/VideoEditPage.tsx"),
  "utf8",
);

describe("video creation history dialog dark theme", () => {
  it("uses dark surfaces and readable text", () => {
    expect(styles).toMatch(
      /:root\[data-theme="dark"\] \.video-history-dialog\s*\{[^}]*background:\s*var\(--theme-surface-solid\)/s,
    );
    expect(styles).toMatch(
      /:root\[data-theme="dark"\] \.video-history-dialog \.dialog-header h2,[\s\S]*?color:\s*var\(--theme-text\)/,
    );
    expect(styles).toMatch(
      /:root\[data-theme="dark"\] \.video-history-facts > div,[\s\S]*?background:\s*var\(--theme-surface-elevated\)/,
    );
  });
});

describe("video creation side rail hierarchy", () => {
  it("uses stronger card boundaries and a branded history rail", () => {
    expect(designSystem).toMatch(
      /\.video-edit-side-rail > \.panel\s*\{[^}]*border-color:\s*var\(--karries-border-strong\);[^}]*box-shadow:/s,
    );
    expect(designSystem).toMatch(
      /\.video-edit-history-card\s*\{[^}]*border-left:\s*3px solid var\(--karries-brand-400\);/s,
    );
  });

  it("connects the workflow and separates interactive history rows", () => {
    expect(videoEditPage).toContain('aria-current="step"');
    expect(designSystem).toMatch(
      /\.video-edit-progress-card li:not\(:last-child\)::after\s*\{[^}]*height:\s*2px;[^}]*background:\s*var\(--karries-border-strong\);/s,
    );
    expect(designSystem).toMatch(
      /\.video-edit-history-list > button\s*\{[^}]*border-bottom:\s*1px solid var\(--karries-border\);/s,
    );
    expect(designSystem).toMatch(
      /\.video-edit-history-list > button:hover,[\s\S]*box-shadow:\s*inset 3px 0 var\(--karries-brand-500\);/,
    );
  });

  it("keeps the stronger hierarchy in dark mode", () => {
    expect(designSystem).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.video-edit-side-rail > \.panel\s*\{[^}]*box-shadow:\s*0 2px 12px rgb\(0 0 0 \/ 24%\);/,
    );
  });

  it("uses semantic colors for generated, pending and returned video states", () => {
    expect(designSystem).toMatch(
      /em\[data-history-status="completed"\]\s*\{[^}]*background:\s*var\(--karries-success-soft\);[^}]*color:\s*var\(--karries-success\);/s,
    );
    expect(designSystem).toMatch(
      /em\[data-history-status="pending"\]\s*\{[^}]*background:\s*var\(--karries-warning-soft\);[^}]*color:\s*var\(--karries-warning\);/s,
    );
    expect(designSystem).toMatch(
      /em\[data-history-status="returned"\]\s*\{[^}]*background:\s*var\(--karries-danger-soft\);[^}]*color:\s*var\(--karries-danger\);/s,
    );
  });
});
