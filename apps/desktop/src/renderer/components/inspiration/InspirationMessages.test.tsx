import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { InspirationMessage, InspirationSession } from "../../types";
import { InspirationMessages } from "./InspirationMessages";


const session: InspirationSession = {
  id: 1,
  tenant_id: 1,
  user_id: 1,
  title: "日常问答",
  linked_product_id: 0,
  linked_xhs_account_id: 0,
  interaction_mode: "normal",
  goal_type: "general",
  tone: "自然真诚",
  extra_requirement: "",
  generation_token: "",
  generation_started_time: 0,
  status: "active",
  message_count: 1,
  total_credit_cost: 0,
  create_time: 1,
  update_time: 1
};

const assistantMessage: InspirationMessage = {
  id: 2,
  tenant_id: 1,
  session_id: 1,
  user_id: 1,
  role: "assistant",
  content: "你好，我可以帮助你处理日常问题。",
  context: {},
  ai_provider: "provider",
  ai_model: "model",
  credit_cost: 0,
  latency_ms: 1,
  status: "success",
  error_message: "",
  content_draft_id: 0,
  create_time: 1
};

const userMessage: InspirationMessage = {
  ...assistantMessage,
  id: 1,
  role: "user",
  content: "请帮我改写这段提示词",
  revision_root_message_id: 1,
  revision_index: 1,
  revision_count: 1,
  revision_message_ids: [1]
};

describe("InspirationMessages", () => {
  it("keeps model and conversation mode controls together on one accessible row", () => {
    render(
      <InspirationMessages
        session={session}
        messages={[]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
        modelModeControl={<button type="button">Pro</button>}
        conversationSpaceControl={<button type="button">普通对话</button>}
      />
    );

    const row = screen.getByTestId("inspiration-mode-controls");
    expect(row).toContainElement(screen.getByRole("button", { name: "Pro" }));
    expect(row).toContainElement(screen.getByRole("button", { name: "普通对话" }));
  });

  it("renders assistant Markdown without exposing formatting markers and preserves hashtags", () => {
    const markdownMessage: InspirationMessage = {
      ...assistantMessage,
      content: [
        "### 节奏安排",
        "",
        "**字幕重点**：突出产品卖点。",
        "",
        "| 时间 | 内容 |",
        "| --- | --- |",
        "| 0-4秒 | 产品特写 |",
        "",
        "#裸色美甲 #新手美甲"
      ].join("\n")
    };

    render(
      <InspirationMessages
        session={session}
        messages={[markdownMessage]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { level: 3, name: "节奏安排" })).toBeInTheDocument();
    expect(screen.getByText("字幕重点").tagName).toBe("STRONG");
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("#裸色美甲 #新手美甲")).toBeInTheDocument();
    expect(screen.queryByText(/### 节奏安排/)).not.toBeInTheDocument();
  });

  it("keeps normal conversations general while allowing answers to be saved to content collection", () => {
    const onSaveDraft = vi.fn();
    render(
      <InspirationMessages
        session={session}
        messages={[assistantMessage]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={onSaveDraft}
        onSendToVideoCreation={vi.fn()}
      />
    );

    expect(screen.getByLabelText("输入消息")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存到内容收藏" }));
    expect(onSaveDraft).toHaveBeenCalledWith(assistantMessage.id);
    expect(screen.queryByRole("button", { name: "用于视频创作" })).not.toBeInTheDocument();
    expect(screen.getByText("通用对话不会自动加入创作上下文")).toBeInTheDocument();
  });

  it("resizes the message input when its content or the viewport changes", () => {
    const props = {
      session,
      messages: [],
      isLoading: false,
      isSending: false,
      onDraftMessageChange: vi.fn(),
      onSend: vi.fn(),
      onSaveDraft: vi.fn()
    };
    const { rerender } = render(
      <InspirationMessages {...props} draftMessage="短消息" />
    );
    const input = screen.getByLabelText("输入消息");
    Object.defineProperty(input, "scrollHeight", { configurable: true, value: 148 });

    rerender(<InspirationMessages {...props} draftMessage={"较长内容\n".repeat(8)} />);
    expect(input).toHaveStyle({ height: "148px" });

    Object.defineProperty(input, "scrollHeight", { configurable: true, value: 216 });
    fireEvent(window, new Event("resize"));
    expect(input).toHaveStyle({ height: "184px", overflowY: "auto" });
  });

  it("resizes a prefilled draft when the input mounts after session creation", () => {
    const scrollHeightSpy = vi
      .spyOn(HTMLElement.prototype, "scrollHeight", "get")
      .mockReturnValue(248);
    const props = {
      messages: [],
      draftMessage: "爆款解析预填内容\n".repeat(10),
      isLoading: false,
      isSending: false,
      onDraftMessageChange: vi.fn(),
      onSend: vi.fn(),
      onSaveDraft: vi.fn()
    };
    try {
      const { rerender } = render(
        <InspirationMessages {...props} session={null} />
      );

      rerender(<InspirationMessages {...props} session={session} />);

      expect(screen.getByLabelText("输入消息")).toHaveStyle({
        height: "184px",
        overflowY: "auto"
      });
    } finally {
      scrollHeightSpy.mockRestore();
    }
  });

  it("copies user prompts and assistant answers as plain text", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });

    render(
      <InspirationMessages
        session={session}
        messages={[userMessage, assistantMessage]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "复制你的消息" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(userMessage.content));
    expect(screen.getByText("已复制")).toBeInTheDocument();
  });

  it("edits a historical user prompt inline and keeps the editor open while submitting", async () => {
    const revision = new Promise<void>(() => undefined);
    const onReviseMessage = vi.fn().mockReturnValue(revision);
    render(
      <InspirationMessages
        session={session}
        messages={[userMessage, assistantMessage]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
        onReviseMessage={onReviseMessage}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "编辑这条历史提示词" }));
    const editor = screen.getByRole("textbox", { name: "编辑历史提示词" });
    fireEvent.change(editor, { target: { value: "修改后的历史提示词" } });
    fireEvent.click(screen.getByRole("button", { name: "创建新分支并重新生成" }));

    expect(onReviseMessage).toHaveBeenCalledWith(
      userMessage.id,
      "修改后的历史提示词",
      [],
      []
    );
    expect(screen.getByRole("button", { name: "正在重新生成" })).toBeDisabled();
  });

  it("switches between prompt revisions without overwriting messages", () => {
    const onActivateRevision = vi.fn();
    const revisedMessage: InspirationMessage = {
      ...userMessage,
      id: 3,
      content: "第二版提示词",
      revision_index: 2,
      revision_count: 2,
      revision_message_ids: [1, 3]
    };
    render(
      <InspirationMessages
        session={session}
        messages={[revisedMessage, assistantMessage]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
        onActivateRevision={onActivateRevision}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "查看上一版提示词" }));
    expect(onActivateRevision).toHaveBeenCalledWith(1);
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
  });

  it("keeps archived sessions copyable but hides prompt editing", () => {
    render(
      <InspirationMessages
        session={{ ...session, status: "archived" }}
        messages={[userMessage]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
        onReviseMessage={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "复制你的消息" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "编辑这条历史提示词" })).not.toBeInTheDocument();
  });

  it("opens a focused attachment menu before choosing images", () => {
    const onSelectImages = vi.fn();
    render(
      <InspirationMessages
        session={session}
        messages={[]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
        onSelectImages={onSelectImages}
      />
    );

    expect(screen.queryByRole("menu", { name: "添加内容" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "添加内容" }));

    const menu = screen.getByRole("menu", { name: "添加内容" });
    expect(menu).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "上传图片" })).toBeInTheDocument();
    expect(screen.getByText("支持 JPG、PNG、WEBP，最多 4 张")).toBeInTheDocument();
    const input = screen.getByLabelText("输入消息");
    expect(menu.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("lets users quote one of their earlier prompts", () => {
    const onQuoteMessage = vi.fn();
    render(
      <InspirationMessages
        session={session}
        messages={[userMessage, assistantMessage]}
        draftMessage=""
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
        onQuoteMessage={onQuoteMessage}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "引用这条提示词" }));
    expect(onQuoteMessage).toHaveBeenCalledWith(userMessage);
  });

  it("shows the quoted prompt above the input and allows it to be removed", () => {
    const onClearQuote = vi.fn();
    render(
      <InspirationMessages
        session={session}
        messages={[]}
        draftMessage="继续按照这个方向优化"
        quotedMessage={userMessage}
        isLoading={false}
        isSending={false}
        onDraftMessageChange={vi.fn()}
        onSend={vi.fn()}
        onSaveDraft={vi.fn()}
        onClearQuote={onClearQuote}
      />
    );

    expect(screen.getByText("引用你的提示词")).toBeInTheDocument();
    expect(screen.getByText(userMessage.content)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "取消引用" }));
    expect(onClearQuote).toHaveBeenCalledTimes(1);
  });
});
