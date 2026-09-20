import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


describe("developer demo-aligned operations visual system", () => {
  const stylesheetPath = resolve(
    process.cwd(),
    "src/renderer/styles/developer-silver-lab.css"
  );
  const sharedStylesheetPath = resolve(process.cwd(), "src/renderer/styles.css");
  const entryPath = resolve(process.cwd(), "src/renderer/developer-main.tsx");

  it("loads the developer-only visual layer after the shared stylesheet", () => {
    const entry = readFileSync(entryPath, "utf8");

    expect(entry).toMatch(
      /import "\.\/styles\.css";\s*import "\.\/styles\/developer-silver-lab\.css";/
    );
    expect(entry).toContain('document.documentElement.dataset.theme = "light";');
    expect(entry).not.toContain("initializeTheme");
  });

  it("defines the demo's cool enterprise token set with an explicit dark counterpart", () => {
    const stylesheet = readFileSync(stylesheetPath, "utf8");

    expect(stylesheet).toContain("--developer-canvas: #f6f9fc;");
    expect(stylesheet).toContain("--developer-sidebar: #ffffff;");
    expect(stylesheet).toContain("--developer-surface: #ffffff;");
    expect(stylesheet).toContain("--developer-surface-soft: #f8fbfd;");
    expect(stylesheet).toContain("--developer-border: #e2e8f0;");
    expect(stylesheet).toContain("--developer-text: #10213d;");
    expect(stylesheet).toContain("--developer-accent: #0f9fb5;");
    expect(stylesheet).not.toContain("#0a0e13");
    expect(stylesheet).not.toContain("#111821");
    expect(stylesheet).toContain('root[data-theme="dark"] .developer-shell');
    expect(stylesheet).toContain("color-scheme: dark");
  });

  it("covers the shell navigation topbar account menu and responsive layout", () => {
    const stylesheet = readFileSync(stylesheetPath, "utf8");

    expect(stylesheet).toMatch(/\.developer-shell\s*\{/);
    expect(stylesheet).toMatch(/\.developer-shell \.sidebar\s*\{/);
    expect(stylesheet).toMatch(/\.developer-shell \.developer-nav-item\.active\s*\{/);
    expect(stylesheet).toMatch(/\.developer-shell \.topbar\s*\{/);
    expect(stylesheet).toMatch(/\.developer-shell \.account-dropdown\s*\{/);
    expect(stylesheet).toContain("grid-template-columns: 224px minmax(0, 1fr);");
    expect(stylesheet).toContain("height: 56px;");
    expect(stylesheet).toMatch(
      /:root\[data-theme="dark"\] \.developer-shell \.sidebar\s*\{/
    );
    expect(stylesheet).toContain("color-scheme: light;");
    expect(stylesheet).toContain("@media (max-width: 760px)");
    expect(stylesheet).toContain(".developer-global-search");
    expect(stylesheet).toMatch(
      /\/\* GPT Image 2 reference:[\s\S]*?\.developer-shell\s*\{[^}]*font-size:\s*14px;/
    );
  });

  it("keeps alert workbench typography readable without returning to oversized cards", () => {
    const stylesheet = readFileSync(stylesheetPath, "utf8");

    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-alert-table th\s*\{[^}]*font-size:\s*12px;/
    );
    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-alert-table td\s*\{[^}]*font-size:\s*12px;/
    );
    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-alert-title strong\s*\{[^}]*font-size:\s*13px;/
    );
    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-alert-table \.compact\s*\{[^}]*font-size:\s*11px;/
    );
    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-alert-advice li\s*\{[^}]*font-size:\s*12px;/
    );
  });

  it("contains long AI diagnostics inside the detail panel", () => {
    const stylesheet = readFileSync(stylesheetPath, "utf8");

    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-ai-detail \.viral-result\s*\{[^}]*min-width:\s*0;[^}]*width:\s*100%;[^}]*padding:\s*0;/
    );
    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-ai-detail \.viral-result-section\s*\{[^}]*min-width:\s*0;[^}]*padding:\s*16px 18px;/
    );
    expect(stylesheet).toMatch(
      /\.developer-shell \.developer-ai-detail \.viral-result-section :is\(p, li, strong\)\s*\{[^}]*overflow-wrap:\s*anywhere;[^}]*word-break:\s*break-word;/
    );
  });

  it("keeps navigation icons visible when the developer sidebar is collapsed", () => {
    const sharedStylesheet = readFileSync(sharedStylesheetPath, "utf8");

    expect(sharedStylesheet).not.toContain(
      ".developer-shell.sidebar-collapsed .developer-nav-item > span,"
    );
    expect(sharedStylesheet).toContain(
      ".developer-shell.sidebar-collapsed .developer-nav-item > span:not(.developer-nav-icon),"
    );
  });

  it("covers every developer page family and all shared controls", () => {
    const stylesheet = readFileSync(stylesheetPath, "utf8");
    const requiredSelectors = [
      ".developer-command-page",
      ".developer-ops-page",
      ".developer-ai-jobs-page",
      ".developer-billing-page",
      ".developer-ai-settings-page",
      ".developer-users-page",
      ".developer-audit-workbench",
      ".video-delivery-page",
      ".developer-panel",
      ".developer-ops-table",
      ".developer-action-panel",
      ".developer-ai-provider-card",
      ".developer-audit-drawer",
      ".form-message",
      ".inline-alert"
    ];

    requiredSelectors.forEach((selector) => {
      expect(stylesheet, `missing ${selector}`).toContain(selector);
    });
    expect(stylesheet).toMatch(
      /\.developer-shell input,[\s\S]*\.developer-shell select,[\s\S]*\.developer-shell textarea\s*\{/
    );
  });

  it("uses restrained semantic status colors instead of decorative gradients", () => {
    const stylesheet = readFileSync(stylesheetPath, "utf8");

    expect(stylesheet).toContain("--developer-success: #16835f;");
    expect(stylesheet).toContain("--developer-warning: #ad6b18;");
    expect(stylesheet).toContain("--developer-danger: #c94b55;");
    expect(stylesheet).toContain("--developer-info: #356fc5;");
    expect(stylesheet).toMatch(/\.developer-shell \.developer-status-pill\.completed/);
    expect(stylesheet).toMatch(/\.developer-shell \.form-message\.success/);
    expect(stylesheet).toMatch(/\.developer-shell \.form-message\.error/);
  });

  it("restyles the complete developer login including autofill state", () => {
    const stylesheet = readFileSync(stylesheetPath, "utf8");

    expect(stylesheet).toMatch(/\.lux-login-page--developer\s*\{/);
    expect(stylesheet).toMatch(/\.lux-login-page--developer \.lux-login-access\s*\{/);
    expect(stylesheet).toMatch(/\.lux-login-page--developer \.lux-login-card--developer\s*\{/);
    expect(stylesheet).toMatch(
      /\.lux-login-page--developer \.lux-login-field \.lux-login-input\s*\{/
    );
    expect(stylesheet).toMatch(
      /\.lux-login-page--developer \.lux-login-field \.lux-login-input input\s*\{/
    );
    expect(stylesheet).toContain("input:-webkit-autofill");
  });
});
