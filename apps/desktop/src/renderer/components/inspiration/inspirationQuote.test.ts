import { describe, expect, it } from "vitest";

import { composeInspirationPrompt } from "./inspirationQuote";

describe("composeInspirationPrompt", () => {
  it("sends the referenced prompt together with the current request", () => {
    expect(composeInspirationPrompt("继续优化语气", "先写一版专业脚本\n突出产品卖点")).toBe([
      "引用之前的提示词：",
      "> 先写一版专业脚本",
      "> 突出产品卖点",
      "",
      "当前请求：",
      "继续优化语气"
    ].join("\n"));
  });

  it("keeps ordinary prompts unchanged", () => {
    expect(composeInspirationPrompt("普通问题", "")).toBe("普通问题");
  });
});
