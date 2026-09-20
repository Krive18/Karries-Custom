import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


describe("shared dark theme styles", () => {
  const stylesheet = readFileSync(
    resolve(process.cwd(), "src/renderer/styles.css"),
    "utf8"
  );
  const darkThemeStyles = stylesheet.slice(
    stylesheet.indexOf(':root[data-theme="dark"]')
  );

  it("uses a neutral graphite surface hierarchy", () => {
    expect(darkThemeStyles).toContain("--theme-page-bg: #20211f;");
    expect(darkThemeStyles).toContain("--theme-sidebar: #1c1d1b;");
    expect(darkThemeStyles).toContain("--theme-surface-solid: #292a27;");
    expect(darkThemeStyles).toContain("--theme-surface-elevated: #32332f;");
    expect(darkThemeStyles).toContain("--theme-input: #2f302c;");
  });

  it("keeps the complete AI Agent workspace on dark semantic surfaces", () => {
    expect(darkThemeStyles).toMatch(
      /\.inspiration-message-list\s*\{[^}]*background:\s*var\(--theme-page-bg\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.inspiration-message-body\s*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.inspiration-composer\s*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.inspiration-session-search\s*\{[^}]*background:\s*var\(--theme-input\)/s
    );
  });

  it("keeps content review surfaces within the graphite hierarchy", () => {
    expect(darkThemeStyles).toMatch(
      /\.publish-summary\s*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.publish-draft-list\s*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.publish-draft-editor\s*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.publish-video-job\s*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.publish-video-filters\s*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
  });

  it("uses dark semantic surfaces for successful delivery resources", () => {
    expect(darkThemeStyles).toContain("--theme-success-surface: #20362a;");
    expect(darkThemeStyles).toContain("--theme-info-surface: #25333d;");
    expect(darkThemeStyles).toContain("--theme-secondary-surface: #312a3a;");
    expect(darkThemeStyles).toMatch(
      /\.delivery-box\s*\{[^}]*background:\s*var\(--theme-success-surface\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.delivery-audio-list\s*\{[^}]*background:\s*var\(--theme-info-surface\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.delivery-subtitle-list\s*\{[^}]*background:\s*var\(--theme-secondary-surface\)/s
    );
  });

  it("covers shared nested surfaces across customer manager and developer portals", () => {
    expect(darkThemeStyles).toMatch(
      /\.product-library-toolbar[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.manager-billing-section[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.developer-panel[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.notification-popover[^{]*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
  });

  it("maps the complete developer command center to the shared dark palette", () => {
    expect(darkThemeStyles).toMatch(
      /\.developer-command-page\s*\{[^}]*--command-surface:\s*var\(--theme-surface-solid\)[^}]*--command-text:\s*var\(--theme-text\)[^}]*--command-muted:\s*var\(--theme-text-muted\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.developer-service-table th\s*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.developer-quick-actions > button\s*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.developer-trend-chart \.recharts-default-tooltip\s*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
  });

  it("keeps publish plan navigation and details on dark surfaces", () => {
    expect(darkThemeStyles).toMatch(
      /\.publish-plan-list\s*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.publish-plan-detail\s*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.publish-item-table-wrap\s*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
  });

  it("keeps saved AI conversation content on a graphite reading surface", () => {
    expect(darkThemeStyles).toMatch(
      /\.collection-long-section\s*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.collection-ai-content\s*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.collection-ai-content > p\s*\{[^}]*color:\s*var\(--theme-text\)/s
    );
  });

  it("keeps video creation headings labels and material metadata readable", () => {
    expect(darkThemeStyles).toMatch(
      /\.video-edit-page \.form-grid > label[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-edit-page \.video-material-actions strong[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-edit-page \.knowledge-library-source[^{]*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-edit-page \.material-list span[^{]*\{[^}]*color:\s*var\(--theme-text-muted\)/s
    );
  });

  it("keeps the complete product library canvas and controls dark", () => {
    expect(darkThemeStyles).toMatch(
      /\.product-library-content\s*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.product-storage-meter\s*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.material-search\s*\{[^}]*background:\s*var\(--theme-input\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.product-folder-open strong\s*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.product-folder-open small\s*\{[^}]*color:\s*var\(--theme-text-muted\)/s
    );
  });

  it("keeps project groups and every viral-analysis result surface in the dark hierarchy", () => {
    expect(darkThemeStyles).toMatch(
      /\.material-project-card-open[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.manager-viral-detail \.viral-result-section[^{]*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.viral-visual-summary[^{]*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.viral-visual-segment[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.viral-script-segment[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.viral-transcript-section,[\s\S]*?\.viral-transcript-analysis-section,[\s\S]*?\.viral-rewritten-section\s*\{[^}]*background:\s*var\(--theme-surface-soft\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.viral-transcript-segment\s*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
  });

  it("keeps personal center and recharge center on readable semantic surfaces", () => {
    expect(darkThemeStyles).toMatch(
      /\.personal-identity-band[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.personal-grid \.panel[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.personal-detail-list dd[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.personal-plan-summary > div[^{]*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.credit-live-balance strong[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.membership-plan[^{]*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.recharge-workbench[^{]*\{[^}]*background:\s*var\(--theme-surface-solid\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.recharge-package[^{]*\{[^}]*background:\s*var\(--theme-surface-elevated\)/s
    );
  });

  it("keeps all video delivery labels and values readable on dark surfaces", () => {
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-metric span[^{]*\{[^}]*color:\s*var\(--theme-text-muted\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-queue-item > strong[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-detail-head h2[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-copy-grid p[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-material-row strong[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-item-client[^{]*\{[^}]*color:\s*var\(--theme-text-muted\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-owner strong[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-upload strong[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-upload small[^{]*\{[^}]*color:\s*var\(--theme-text-muted\)/s
    );
    expect(darkThemeStyles).toMatch(
      /\.video-delivery-queue-item\.selected > strong[^{]*\{[^}]*color:\s*var\(--theme-text\)/s
    );
  });

  it("does not regress to the near-black form fill that caused split white and black panels", () => {
    expect(darkThemeStyles).not.toContain("background: #1d1a17;");
  });
});
