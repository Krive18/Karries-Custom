import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("AI translation light theme", () => {
  const stylesheet = readFileSync(
    resolve(process.cwd(), "src/renderer/styles.css"),
    "utf8"
  );

  it("owns complete semantic colors instead of inheriting undefined developer tokens", () => {
    expect(stylesheet).toContain("--translation-card: #fffdfa;");
    expect(stylesheet).toContain("--translation-border: #d8c9b8;");
    expect(stylesheet).toContain("--translation-field: #f7f1e8;");
    expect(stylesheet).toContain(".translation-page .panel {");
  });

  it("gives the source picker, language controls and empty history visible structure", () => {
    expect(stylesheet).toContain(".translation-source-actions {");
    expect(stylesheet).toContain(".translation-language-fields {");
    expect(stylesheet).toContain(".translation-history-list:empty");
  });
});
