import { BookmarkPlus, Loader2, Send } from "lucide-react";

import type { InspirationMessage, InspirationSession } from "../../types";

type InspirationMessagesProps = {
  session: InspirationSession | null;
  messages: InspirationMessage[];
  draftMessage: string;
  isLoading: boolean;
  isSending: boolean;
  onDraftMessageChange: (value: string) => void;
  onSend: () => void;
  onSaveDraft: (messageId: number) => void;
};

export function InspirationMessages({
  session,
  messages,
  draftMessage,
  isLoading,
  isSending,
  onDraftMessageChange,
  onSend,
  onSaveDraft
}: InspirationMessagesProps) {
  if (!session) {
    return <section className="inspiration-message-panel empty-list-state">从左侧新建或选择一个会话，开始整理运营灵感。</section>;
  }

  const canSend = session.status === "active" && !isSending;
  return (
    <section className="inspiration-message-panel" aria-busy={isLoading || isSending}>
      <div className="inspiration-message-header">
        <div>
          <h2>{session.title}</h2>
          <span>本次预计消耗 1 算力</span>
        </div>
        {isSending ? <span className="key-status"><Loader2 size={14} className="spin" aria-hidden="true" /> 正在生成</span> : null}
      </div>
      <div className="inspiration-message-list" aria-live="polite">
        {isLoading ? (
          <div className="inspiration-message-skeleton" aria-label="正在加载会话内容"><span /><span /><span /></div>
        ) : messages.length === 0 ? (
          <div className="empty-list-state">还没有对话内容，输入一个运营问题开始吧。</div>
        ) : messages.map((message) => (
          <article className={`inspiration-message ${message.role}`} key={message.id}>
            <div className="inspiration-message-meta">{message.role === "user" ? "你" : "AI 建议"}</div>
            <p>{message.content}</p>
            {message.status === "failed" ? <span className="message-error">本次生成未完成，请重新提问。</span> : null}
            {message.role === "assistant" && message.status === "success" ? (
              <button className="table-action compact" type="button" disabled={message.content_draft_id > 0} onClick={() => onSaveDraft(message.id)}>
                <BookmarkPlus size={15} aria-hidden="true" />
                {message.content_draft_id > 0 ? "已保存为内容草稿" : "保存为内容草稿"}
              </button>
            ) : null}
            {message.role === "assistant" && message.content_draft_id > 0 ? <span className="message-draft-id">草稿 ID：{message.content_draft_id}</span> : null}
          </article>
        ))}
      </div>
      <div className="inspiration-composer">
        <label htmlFor="inspiration-message">输入运营问题</label>
        <textarea id="inspiration-message" value={draftMessage} disabled={!canSend} onChange={(event) => onDraftMessageChange(event.target.value)} placeholder={session.status === "archived" ? "此会话已归档" : "例如：给我 5 个新品选题，分别适合哪些内容角度？"} rows={4} />
        <button className="primary-button" type="button" disabled={!canSend || !draftMessage.trim()} onClick={onSend}>
          {isSending ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <Send size={17} aria-hidden="true" />}
          {isSending ? "生成中" : "发送"}
        </button>
      </div>
    </section>
  );
}
