import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


function readRendererFile(relativePath: string) {
  return readFileSync(resolve(process.cwd(), "src/renderer", relativePath), "utf8");
}


describe("KARRIES customer and manager design system", () => {
  const customerEntry = readRendererFile("main.tsx");
  const managerEntry = readRendererFile("manager-main.tsx");
  const customerShell = readRendererFile("components/AppShell.tsx");
  const managerShell = readRendererFile("components/ManagerShell.tsx");
  const loginPage = readRendererFile("pages/Login.tsx");

  it("loads the shared design-system stylesheet after legacy page styles", () => {
    expect(customerEntry).toMatch(
      /import "\.\/styles\.css";\s*import "\.\/styles\/karries-design-system\.css";/
    );
    expect(managerEntry).toMatch(
      /import "\.\/styles\.css";\s*import "\.\/styles\/karries-design-system\.css";/
    );
  });

  it("isolates the redesign from the developer portal", () => {
    expect(customerShell).toContain('className={`shell customer-shell${');
    expect(managerShell).toContain('className={`shell manager-shell${');
  });

  it("defines a restrained brown-gold light and dark semantic token system", () => {
    const stylesheet = readRendererFile("styles/karries-design-system.css");

    expect(stylesheet).toContain("--karries-brand-600: #8f5b23;");
    expect(stylesheet).toContain("--karries-page: #f6f7fb;");
    expect(stylesheet).toContain("--karries-surface: #ffffff;");
    expect(stylesheet).toContain("--karries-text: #20222a;");
    expect(stylesheet).toMatch(
      /:root\[data-theme="dark"\] :is\(\.customer-shell, \.manager-shell\)[\s\S]*--karries-page: var\(--theme-page-bg\);[\s\S]*--karries-surface: var\(--theme-surface-solid\);[\s\S]*--karries-input: var\(--theme-input\);/
    );
  });

  it("uses brown-gold only for product emphasis and keeps surfaces neutral", () => {
    const stylesheet = readRendererFile("styles/karries-design-system.css");

    expect(stylesheet).toMatch(
      /:is\(\.customer-shell, \.manager-shell\) \.primary-button[\s\S]*background: var\(--karries-brand-600\)/
    );
    expect(stylesheet).toMatch(
      /:is\(\.customer-shell, \.manager-shell\) \.panel[\s\S]*background: var\(--karries-surface\)/
    );
    expect(stylesheet).not.toContain("#6558f5");
    expect(stylesheet).not.toContain("#8176ff");
    expect(stylesheet).toMatch(
      /\.brand-mark,[\s\S]*\.avatar-button img[\s\S]*filter: none;/
    );
    expect(stylesheet).not.toContain("linear-gradient");
  });

  it("restores the original customer and manager login presentation", () => {
    expect(loginPage).toMatch(
      /import "\.\.\/styles\/login\.css";\s*import "\.\.\/styles\/developer-login\.css";/
    );
    expect(loginPage).not.toContain("karries-login.css");
    expect(
      existsSync(resolve(process.cwd(), "src/renderer/styles/karries-login.css"))
    ).toBe(false);
  });

  it("uses the shared dark surface hierarchy for panels and form controls", () => {
    const stylesheet = readRendererFile("styles/karries-design-system.css");

    expect(stylesheet).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.panel[\s\S]*background: var\(--karries-surface\)/
    );
    expect(stylesheet).toMatch(
      /:root\[data-theme="dark"\][\s\S]*:is\(input, select, textarea\)[\s\S]*background: var\(--karries-input\)/
    );
  });
});
