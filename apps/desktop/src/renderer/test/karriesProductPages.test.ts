import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


function readRendererFile(relativePath: string) {
  return readFileSync(resolve(process.cwd(), "src/renderer", relativePath), "utf8");
}


describe("KARRIES representative product pages", () => {
  const customerEntry = readRendererFile("main.tsx");
  const managerEntry = readRendererFile("manager-main.tsx");

  it("loads migrated page styles after the shared foundation", () => {
    const importSequence = /import "\.\/styles\/karries-design-system\.css";\s*import "\.\/styles\/karries-product-pages\.css";/;
    expect(customerEntry).toMatch(importSequence);
    expect(managerEntry).toMatch(importSequence);
  });

  it("makes the product library a neutral content canvas with brown-gold selection", () => {
    const stylesheet = readRendererFile("styles/karries-product-pages.css");

    expect(stylesheet).toMatch(
      /\.product-library-content[\s\S]*background: var\(--karries-surface\)/
    );
    expect(stylesheet).toMatch(
      /\.material-project-card-open[\s\S]*background: var\(--karries-surface\)/
    );
    expect(stylesheet).toMatch(
      /\.material-project-card:focus-within[\s\S]*border-color: var\(--karries-brand-300\)/
    );
  });

  it("uses readable neutral surfaces for viral transcripts and rewritten scripts", () => {
    const stylesheet = readRendererFile("styles/karries-product-pages.css");

    expect(stylesheet).toMatch(
      /\.viral-transcript-section[\s\S]*background: var\(--karries-surface-soft\)/
    );
    expect(stylesheet).toMatch(
      /\.viral-rewritten-section[\s\S]*box-shadow: inset 3px 0 var\(--karries-brand-500\)/
    );
    expect(stylesheet).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.viral-transcript-segment[\s\S]*background: var\(--karries-surface-elevated\)/
    );
  });

  it("keeps the dark viral-analysis form on one coherent surface hierarchy", () => {
    const stylesheet = readRendererFile("styles/karries-product-pages.css");

    expect(stylesheet).toMatch(
      /\.viral-form-section[\s\S]*background: transparent/
    );
    expect(stylesheet).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.viral-create-panel[\s\S]*background: var\(--karries-surface\)/
    );
    expect(stylesheet).toMatch(
      /:root\[data-theme="dark"\][\s\S]*\.viral-create-panel[\s\S]*:is\(input, select, textarea\)[\s\S]*background: var\(--karries-input\)/
    );
  });

  it("keeps membership and payment cards neutral while emphasizing the current plan in brown-gold", () => {
    const stylesheet = readRendererFile("styles/karries-product-pages.css");

    expect(stylesheet).toMatch(
      /\.membership-plan[\s\S]*background: var\(--karries-surface\)/
    );
    expect(stylesheet).toMatch(
      /\.membership-plan\.current[\s\S]*border-color: var\(--karries-brand-500\)/
    );
    expect(stylesheet).toMatch(
      /\.recharge-package\.hot[\s\S]*border-color: var\(--karries-brand-400\)/
    );
  });

  it("gives manager tables and data sections the same restrained hierarchy", () => {
    const stylesheet = readRendererFile("styles/karries-product-pages.css");

    expect(stylesheet).toMatch(
      /\.manager-data-table th[\s\S]*background: var\(--karries-surface-soft\)/
    );
    expect(stylesheet).toMatch(
      /\.manager-billing-section[\s\S]*background: var\(--karries-surface\)/
    );
    expect(stylesheet).not.toContain("linear-gradient");
    expect(stylesheet).not.toContain("rgb(101 88 245");
    expect(stylesheet).not.toContain("rgb(46 43 82");
  });

  it("keeps feedback page actions clear of the global account toolbar", () => {
    const stylesheet = readRendererFile("styles/karries-product-pages.css");

    expect(stylesheet).toMatch(
      /\.feedback-page-heading\s*\{[^}]*padding-right:\s*150px/
    );
    expect(stylesheet).toMatch(
      /@media \(max-width: 620px\)[\s\S]*\.feedback-page-heading[\s\S]*padding-right:\s*0/
    );
  });
});
