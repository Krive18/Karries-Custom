import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


function readRendererFile(relativePath: string) {
  return readFileSync(resolve(process.cwd(), "src/renderer", relativePath), "utf8");
}


describe("KARRIES UI refinement regression coverage", () => {
  it("uses the Karries AI product name and the new viral-analysis promise", () => {
    const shell = readRendererFile("components/AppShell.tsx");
    const inspiration = readRendererFile("pages/InspirationPage.tsx");
    const viralAnalysis = readRendererFile("pages/ViralAnalysisPage.tsx");

    expect(shell).toContain("<span>Karries AI</span>");
    expect(inspiration).toContain("<h1>Karries AI</h1>");
    expect(viralAnalysis).toContain("<h1>一键拆解爆款视频，生成 AI 视频提示词。</h1>");
    expect(viralAnalysis).not.toContain("拆解开场、结构、节奏和转化方式，沉淀可复用的创作思路。");
  });

  it("keeps the current-plan badge readable and separates the sidebar canvas", () => {
    const designSystem = readRendererFile("styles/karries-design-system.css");
    const productPages = readRendererFile("styles/karries-product-pages.css");

    expect(designSystem).toMatch(
      /\.sidebar\s*\{[\s\S]*border-right: 1px solid var\(--karries-border-strong\);[\s\S]*box-shadow: 4px 0 18px rgb\(24 28 42 \/ 5%\);/
    );
    expect(productPages).toMatch(
      /\.membership-plan-title \.current-plan-badge\s*\{[\s\S]*background: var\(--karries-brand-600\);[\s\S]*color: #ffffff;/
    );
  });

  it("makes video mode selection visibly stateful", () => {
    const page = readRendererFile("pages/VideoEditPage.tsx");
    const stylesheet = readRendererFile("styles/karries-design-system.css");

    expect(page).toContain('className="video-creation-mode-status"');
    expect(page).toContain("已选择");
    expect(stylesheet).toMatch(
      /\.video-creation-mode-grid button\[aria-pressed="true"\][\s\S]*transform: translateY\(-2px\)/
    );
  });

  it("uses readable neutral dark controls for account, login and conversation chrome", () => {
    const designSystem = readRendererFile("styles/karries-design-system.css");
    const login = readRendererFile("styles/login.css");

    expect(designSystem).toMatch(
      /\.account-dropdown > button\s*\{[\s\S]*color: var\(--karries-text-secondary\)/
    );
    expect(designSystem).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.ai-conversation-identity h2[\s\S]*color: var\(--karries-text\)/
    );
    expect(login).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.lux-login-page--customer[\s\S]*\.lux-login-input input[\s\S]*background: transparent;/
    );
  });

  it("keeps the selected conversation template readable in the composer", () => {
    const designSystem = readRendererFile("styles/karries-design-system.css");
    const triggerRule = designSystem.match(
      /:is\(\.customer-shell, \.manager-shell\) \.inspiration-space-trigger \{([^}]*)\}/
    )?.[1] ?? "";
    const currentLabelRule = designSystem.match(
      /:is\(\.customer-shell, \.manager-shell\) \.inspiration-space-selector-current \{([^}]*)\}/
    )?.[1] ?? "";

    expect(triggerRule).toContain("color: var(--karries-text);");
    expect(currentLabelRule).toContain("color: var(--karries-text);");
    expect(currentLabelRule).not.toContain("color: inherit;");
  });

  it("keeps successful collection alerts green after the generic error alert rule", () => {
    const designSystem = readRendererFile("styles/karries-design-system.css");
    const genericErrorRule = designSystem.indexOf(
      ':is(.customer-shell, .manager-shell) :is(.form-message.error, .app-alert)'
    );
    const semanticSuccessRule = designSystem.lastIndexOf(
      ':is(.customer-shell, .manager-shell) :is(.form-message.success, .app-alert.success, .collection-message-success)'
    );

    expect(genericErrorRule).toBeGreaterThan(-1);
    expect(semanticSuccessRule).toBeGreaterThan(genericErrorRule);
  });
});
