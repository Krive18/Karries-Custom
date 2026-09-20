import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


describe("top-level page headings", () => {
  const pagesDirectory = resolve(process.cwd(), "src/renderer/pages");
  const developerPageSources = readdirSync(pagesDirectory)
    .filter((fileName) => /^Developer.*Page\.tsx$/.test(fileName))
    .map((fileName) => readFileSync(resolve(pagesDirectory, fileName), "utf8"))
    .join("\n");

  it("does not add decorative kicker copy above developer page titles", () => {
    expect(developerPageSources).not.toContain("developer-page-kicker");
  });

  it("keeps the video delivery heading free of a decorative eyebrow", () => {
    const source = readFileSync(
      resolve(pagesDirectory, "DeveloperVideoJobsPage.tsx"),
      "utf8"
    );

    expect(source).not.toMatch(
      /video-delivery-heading[\s\S]{0,240}className="eyebrow"/
    );
  });
});
