import { useId, useState } from "react";
import { ChevronDown, ChevronUp, Copy } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";


const markdownComponents: Components = {
  a: ({ children, href, title }) => (
    <a href={href} title={title} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="assistant-markdown-table" tabIndex={0}>
      <table>{children}</table>
    </div>
  )
};


export type RichContentMarkdownProps = {
  content: string;
  className?: string;
};


export function RichContentMarkdown({
  content,
  className = ""
}: RichContentMarkdownProps) {
  return (
    <div className={`rich-content-markdown ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
        skipHtml
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}


export type RichContentReaderProps = {
  title: string;
  content: string;
  emptyText: string;
  variant: "script" | "assistant";
  collapseThreshold?: number;
  onCopy?: (content: string) => void | Promise<void>;
};


export function RichContentReader({
  title,
  content,
  emptyText,
  variant,
  collapseThreshold = 800,
  onCopy
}: RichContentReaderProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const bodyId = useId();
  const isEmpty = content.trim().length === 0;
  const isLong = !isEmpty && content.length > collapseThreshold;
  const isCollapsed = isLong && !isExpanded;

  async function handleCopy() {
    if (onCopy) {
      await onCopy(content);
      return;
    }
    await navigator.clipboard?.writeText(content);
  }

  return (
    <section className={`rich-content-reader rich-content-reader--${variant}`}>
      <header className="rich-content-reader-header">
        <div className="rich-content-reader-heading">
          <h3>{title}</h3>
          <span>{content.length} 字</span>
        </div>
        <button
          className="rich-content-reader-actions"
          type="button"
          aria-label={`复制${title}`}
          onClick={() => void handleCopy()}
        >
          <Copy size={15} aria-hidden="true" />
          <span>复制</span>
        </button>
      </header>

      <div
        id={bodyId}
        className={`rich-content-reader-body${isCollapsed ? " collapsed" : ""}`}
      >
        <RichContentMarkdown content={isEmpty ? emptyText : content} />
      </div>

      {isLong ? (
        <footer className="rich-content-reader-footer">
          <button
            className="rich-content-reader-actions"
            type="button"
            aria-controls={bodyId}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? "收起" : "展开全文"}
            onClick={() => setIsExpanded((current) => !current)}
          >
            {isExpanded ? (
              <ChevronUp size={15} aria-hidden="true" />
            ) : (
              <ChevronDown size={15} aria-hidden="true" />
            )}
            <span>{isExpanded ? "收起" : "展开全文"}</span>
          </button>
        </footer>
      ) : null}
    </section>
  );
}
