import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RichContentMarkdown, RichContentReader } from "./RichContentReader";


describe("RichContentMarkdown", () => {
  it("renders GFM while suppressing raw HTML and scripts", () => {
    const { container } = render(
      <RichContentReader
        title="AI 对话内容"
        content={[
          "## 方案",
          "",
          "- 第一项",
          "- 第二项",
          "",
          "<script>alert(1)</script>"
        ].join("\n")}
        emptyText="暂无内容"
        variant="assistant"
      />
    );

    expect(screen.getByRole("heading", { name: "方案" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(container.querySelector("script")).toBeNull();
    expect(screen.queryByText("alert(1)")).not.toBeInTheDocument();
  });

  it("preserves tables and opens safe Markdown links in a protected new tab", () => {
    render(
      <RichContentMarkdown
        content={[
          "[查看资料](https://example.com/guide)",
          "",
          "| 阶段 | 任务 |",
          "| --- | --- |",
          "| 1 | 准备 |"
        ].join("\n")}
      />
    );

    const link = screen.getByRole("link", { name: "查看资料" });
    expect(link).toHaveAttribute("href", "https://example.com/guide");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});


describe("RichContentReader", () => {
  it("renders a meaningful Markdown empty state", () => {
    render(
      <RichContentReader
        title="提交脚本"
        content={"  \n "}
        emptyText="**未填写脚本**"
        variant="script"
      />
    );

    expect(screen.getByText("未填写脚本").tagName).toBe("STRONG");
    expect(screen.getByText("4 字")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "展开全文" })).not.toBeInTheDocument();
  });

  it("collapses long content and copies the original text through the supplied callback", async () => {
    const onCopy = vi.fn().mockResolvedValue(undefined);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });
    const content = "脚本段落".repeat(210);
    const { container } = render(
      <RichContentReader
        title="提交脚本"
        content={content}
        emptyText="未填写脚本"
        variant="script"
        onCopy={onCopy}
      />
    );

    expect(container.querySelector(".rich-content-reader-body")).toHaveClass("collapsed");
    expect(screen.getByRole("button", { name: "展开全文" })).toHaveAttribute(
      "aria-expanded",
      "false"
    );

    fireEvent.click(screen.getByRole("button", { name: "复制提交脚本" }));
    await waitFor(() => expect(onCopy).toHaveBeenCalledWith(content));
    expect(writeText).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "展开全文" }));
    expect(container.querySelector(".rich-content-reader-body")).not.toHaveClass("collapsed");
    expect(screen.getByRole("button", { name: "收起" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
  });

  it("falls back to the Clipboard API only when no copy callback is supplied", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });

    render(
      <RichContentReader
        title="AI 对话内容"
        content="## 原始内容"
        emptyText="暂无内容"
        variant="assistant"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "复制AI 对话内容" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("## 原始内容"));
  });
});
