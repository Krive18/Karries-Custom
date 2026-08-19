# Shared Rich Content Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw long-text blocks in video creation history and content collections with a shared, safe, collapsible Markdown reader while preserving raw-text editing and copy behavior.

**Architecture:** Extract the existing `react-markdown`/GFM rendering from `AssistantMessageContent` into a focused shared component. `RichContentReader` owns read-only presentation, expand/collapse state, character count, and raw-text copy; chat messages keep a lightweight renderer and editing surfaces remain plain textareas.

**Tech Stack:** React 19, TypeScript 6, react-markdown 10, remark-gfm 4, Vitest, Testing Library, existing CSS token system.

**Spec:** `docs/superpowers/specs/2026-08-19-content-readability-project-groups-delivery-zip-design.md`

## Global Constraints

- Do not render raw HTML; `ReactMarkdown` must keep `skipHtml` enabled.
- External links use `target="_blank"` and `rel="noopener noreferrer"`.
- Content longer than 800 characters is collapsed by default and exposes “展开全文/收起”.
- Copy actions copy the original string, not rendered DOM text.
- Empty content displays the caller-provided empty copy.
- Editing views and saved payloads remain unchanged.
- Use the current light/dark tokens and do not add a new visual theme.

---

## File Structure

- Create `apps/desktop/src/renderer/components/content/RichContentReader.tsx`: shared Markdown renderer plus document-style reader.
- Create `apps/desktop/src/renderer/components/content/RichContentReader.test.tsx`: security, structure, collapse, and copy tests.
- Modify `apps/desktop/src/renderer/components/inspiration/AssistantMessageContent.tsx`: delegate Markdown rendering to the shared primitive.
- Modify `apps/desktop/src/renderer/components/collection/ContentCollectionDetail.tsx`: render AI content, rewritten scripts, and shot breakdowns with the reader in read-only mode.
- Create `apps/desktop/src/renderer/components/collection/ContentCollectionDetail.test.tsx`: prove reader integration and textarea preservation.
- Modify `apps/desktop/src/renderer/pages/VideoEditPage.tsx`: render locked script and requirement snapshots as reader cards.
- Modify `apps/desktop/src/renderer/test/App.test.tsx`: prove the video history dialog exposes structured reader controls.
- Modify `apps/desktop/src/renderer/styles.css`: shared reader, collection, history, responsive, focus, and dark-theme rules.

### Task 1: Shared safe Markdown primitive and reader

**Files:**
- Create: `apps/desktop/src/renderer/components/content/RichContentReader.tsx`
- Create: `apps/desktop/src/renderer/components/content/RichContentReader.test.tsx`
- Modify: `apps/desktop/src/renderer/components/inspiration/AssistantMessageContent.tsx:1-36`

**Interfaces:**
- Produces: `RichContentMarkdown({ content, className? })` for safe Markdown-only rendering.
- Produces: `RichContentReader({ title, content, emptyText, variant, collapseThreshold?, onCopy? })` where `variant` is `"script" | "assistant"` and `onCopy` receives the original string.
- Consumes: `navigator.clipboard.writeText` only when no `onCopy` callback is supplied.

- [ ] **Step 1: Write failing reader tests**

```tsx
it("renders GFM without executing raw html", () => {
  const { container } = render(
    <RichContentReader
      title="AI 对话内容"
      content={'## 方案\n\n- 第一项\n- 第二项\n\n<script>alert(1)</script>'}
      emptyText="暂无内容"
      variant="assistant"
    />
  );
  expect(screen.getByRole("heading", { name: "方案" })).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(container.querySelector("script")).toBeNull();
});

it("collapses long content and copies the original text", async () => {
  const onCopy = vi.fn().mockResolvedValue(undefined);
  const content = "脚本段落".repeat(210);
  render(
    <RichContentReader
      title="提交脚本"
      content={content}
      emptyText="未填写脚本"
      variant="script"
      onCopy={onCopy}
    />
  );
  expect(screen.getByRole("button", { name: "展开全文" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "复制提交脚本" }));
  expect(onCopy).toHaveBeenCalledWith(content);
  fireEvent.click(screen.getByRole("button", { name: "展开全文" }));
  expect(screen.getByRole("button", { name: "收起" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `cd apps/desktop && npm test -- RichContentReader.test.tsx`

Expected: FAIL because `RichContentReader` does not exist.

- [ ] **Step 3: Implement the shared component**

```tsx
export type RichContentReaderProps = {
  title: string;
  content: string;
  emptyText: string;
  variant: "script" | "assistant";
  collapseThreshold?: number;
  onCopy?: (content: string) => void | Promise<void>;
};

export function RichContentMarkdown({ content, className = "" }: {
  content: string;
  className?: string;
}) {
  return (
    <div className={`rich-content-markdown ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents} skipHtml>
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

Implement `RichContentReader` with `useState(false)`, `collapseThreshold = 800`, `isLong = content.length > collapseThreshold`, a header showing `title` and `${content.length} 字`, a copy button labelled `复制${title}`, and a body class of `collapsed` until expanded. Render `emptyText` through the same Markdown primitive when `content.trim()` is empty.

- [ ] **Step 4: Refactor chat rendering to the primitive**

```tsx
export const AssistantMessageContent = memo(function AssistantMessageContent({
  content
}: AssistantMessageContentProps) {
  return <RichContentMarkdown content={content} className="assistant-markdown" />;
});
```

Delete duplicate `react-markdown`, `remark-gfm`, link, and table component definitions from `AssistantMessageContent.tsx`.

- [ ] **Step 5: Run reader and existing inspiration tests**

Run: `cd apps/desktop && npm test -- RichContentReader.test.tsx InspirationMessages`

Expected: PASS; existing assistant message headings, lists, links, and tables still render.

- [ ] **Step 6: Commit the primitive**

```bash
git add apps/desktop/src/renderer/components/content/RichContentReader.tsx apps/desktop/src/renderer/components/content/RichContentReader.test.tsx apps/desktop/src/renderer/components/inspiration/AssistantMessageContent.tsx
git commit -m "feat: add shared rich content reader"
```

### Task 2: Content collection read-only integration

**Files:**
- Modify: `apps/desktop/src/renderer/components/collection/ContentCollectionDetail.tsx:1-227`
- Create: `apps/desktop/src/renderer/components/collection/ContentCollectionDetail.test.tsx`

**Interfaces:**
- Consumes: `RichContentReader` from Task 1.
- Preserves: `onCopy(text, label)`, `onSave(payload)`, edit-mode textareas, and `fullDraftText` output.

- [ ] **Step 1: Write failing content collection tests**

```tsx
it("uses document readers in read-only mode and raw textareas in edit mode", async () => {
  const item = {
    ...collectionFixture,
    source_type: "inspiration" as const,
    rewritten_script: "## 标题\n\n- 卖点一\n- 卖点二"
  };
  render(<ContentCollectionDetail item={item} isSaving={false} onSave={vi.fn()} onCopy={vi.fn()} onDelete={vi.fn()} />);
  expect(screen.getByRole("heading", { name: "标题" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制AI 对话内容" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "编辑收藏稿" }));
  expect(screen.getByRole("textbox", { name: "AI 对话内容" })).toHaveValue(item.rewritten_script);
});
```

Add a non-inspiration fixture and assert both “改写脚本” and “脚本拆解与分镜” use reader regions in read-only mode.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `cd apps/desktop && npm test -- ContentCollectionDetail.test.tsx`

Expected: FAIL because the detail still renders raw `<p>`/`<pre>` blocks.

- [ ] **Step 3: Replace raw read-only blocks**

```tsx
<RichContentReader
  title="AI 对话内容"
  content={item.rewritten_script}
  emptyText="暂无 AI 对话内容"
  variant="assistant"
  onCopy={(text) => onCopy(text, "AI 对话内容")}
/>
```

Use `variant="script"` for “改写脚本” and “脚本拆解与分镜”. Remove only the duplicated section copy headers; keep the surrounding collection layout, tags, edit actions, and visual-analysis component.

- [ ] **Step 4: Run collection tests**

Run: `cd apps/desktop && npm test -- ContentCollectionDetail.test.tsx`

Expected: PASS; read-only mode is structured and edit mode still saves raw strings.

- [ ] **Step 5: Commit collection integration**

```bash
git add apps/desktop/src/renderer/components/collection/ContentCollectionDetail.tsx apps/desktop/src/renderer/components/collection/ContentCollectionDetail.test.tsx
git commit -m "feat: improve saved content readability"
```

### Task 3: Video history integration and visual polish

**Files:**
- Modify: `apps/desktop/src/renderer/pages/VideoEditPage.tsx:814-836`
- Modify: `apps/desktop/src/renderer/test/App.test.tsx`
- Modify: `apps/desktop/src/renderer/styles.css:249-295,8608-8744,15451-15678,16183-16204,18609-18720`

**Interfaces:**
- Consumes: `RichContentReader` from Task 1.
- Preserves: immutable `historyDetail.request_snapshot` data and existing history modal lifecycle.

- [ ] **Step 1: Extend the video history test fixture**

In the existing customer app test fixture, set:

```tsx
request_snapshot: {
  ...existingSnapshot,
  script_text: "## 开场\n\n- 产品特写\n- 场景切换",
  requirement_text: "节奏自然，避免硬广"
}
```

Open the creation record and assert:

```tsx
expect(screen.getByRole("heading", { name: "开场" })).toBeInTheDocument();
expect(screen.getByRole("button", { name: "复制提交脚本" })).toBeInTheDocument();
expect(screen.getByRole("button", { name: "复制制作要求" })).toBeInTheDocument();
```

- [ ] **Step 2: Run the focused app test and verify it fails**

Run: `cd apps/desktop && npm test -- App.test.tsx`

Expected: FAIL because the history modal has no reader buttons and Markdown remains literal.

- [ ] **Step 3: Integrate reader cards in the modal**

```tsx
<RichContentReader
  title="提交脚本"
  content={historyDetail.request_snapshot.script_text}
  emptyText="未填写脚本"
  variant="script"
/>
<RichContentReader
  title="制作要求"
  content={historyDetail.request_snapshot.requirement_text}
  emptyText="未填写补充要求"
  variant="script"
/>
```

Import the shared component and leave facts, materials, and delivery-version sections unchanged.

- [ ] **Step 4: Add shared styles**

Add `.rich-content-reader`, `.rich-content-reader-header`, `.rich-content-reader-body`, `.rich-content-reader-body.collapsed`, `.rich-content-reader-actions`, and `.rich-content-markdown` rules. Use a 12-line collapsed mask, `overflow-wrap:anywhere`, visible `:focus-visible`, a scrollable table wrapper, and the existing surface/border/text variables. Add dark selectors beside the existing dark collection/history rules and a `max-width:680px` rule that stacks the header without hiding actions.

- [ ] **Step 5: Run frontend verification**

Run: `cd apps/desktop && npm test -- RichContentReader.test.tsx ContentCollectionDetail.test.tsx App.test.tsx`

Expected: PASS.

Run: `cd apps/desktop && npm run typecheck`

Expected: exit 0.

- [ ] **Step 6: Commit integration and styles**

```bash
git add apps/desktop/src/renderer/pages/VideoEditPage.tsx apps/desktop/src/renderer/test/App.test.tsx apps/desktop/src/renderer/styles.css
git commit -m "feat: render video history as readable documents"
```

### Task 4: Browser-level visual verification

**Files:**
- Modify only if verification reveals a regression: `apps/desktop/src/renderer/styles.css`

**Interfaces:**
- Consumes: completed Tasks 1–3.
- Produces: verified light/dark and narrow-window behavior with no content overflow.

- [ ] **Step 1: Start the existing customer portal**

Run: `powershell -ExecutionPolicy Bypass -File scripts/start_local_portals.ps1`

Expected: customer portal is available on its configured local port.

- [ ] **Step 2: Inspect four states**

Open a video history modal and a content collection containing headings, lists, a table, and more than 800 characters. Verify both collapsed and expanded states at desktop width and at a narrow window. Confirm focus rings for copy and expand actions and that raw `<script>` text never becomes an element.

- [ ] **Step 3: Run final frontend suite**

Run: `cd apps/desktop && npm test`

Expected: PASS.

Run: `cd apps/desktop && npm run build:customer`

Expected: exit 0.

- [ ] **Step 4: Commit any verification-only style correction**

```bash
git add apps/desktop/src/renderer/styles.css
git commit -m "fix: polish rich content reader layout"
```
