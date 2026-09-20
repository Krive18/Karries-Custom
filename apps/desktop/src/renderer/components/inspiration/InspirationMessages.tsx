import { type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  BookmarkPlus,
  Bot,
  Check,
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  Copy,
  ImagePlus,
  Loader2,
  Pencil,
  Plus,
  Quote,
  Send,
  Sparkles,
  UserRound,
  X
} from "lucide-react";

import { api } from "../../api/client";
import type { InspirationAttachment, InspirationMessage, InspirationSession } from "../../types";
import { AssistantMessageContent } from "./AssistantMessageContent";

type InspirationMessagesProps = {
  session: InspirationSession | null;
  messages: InspirationMessage[];
  draftMessage: string;
  isLoading: boolean;
  isSending: boolean;
  assistantName?: string;
  conversationSpaceControl?: ReactNode;
  modelModeControl?: ReactNode;
  onOpenContext?: () => void;
  onDraftMessageChange: (value: string) => void;
  onSend: () => void;
  onSaveDraft: (messageId: number) => void;
  onSendToVideoCreation?: (message: InspirationMessage) => void;
  pendingAttachments?: InspirationAttachment[];
  isUploadingImages?: boolean;
  onSelectImages?: (files: File[]) => void;
  onRemoveAttachment?: (attachmentId: number) => void;
  quotedMessage?: InspirationMessage | null;
  onQuoteMessage?: (message: InspirationMessage) => void;
  onClearQuote?: () => void;
  onReviseMessage?: (
    messageId: number,
    content: string,
    retainedAttachmentIds: number[],
    files: File[]
  ) => Promise<void>;
  onActivateRevision?: (messageId: number) => void | Promise<void>;
};

type RevisionDraft = {
  messageId: number;
  content: string;
  retainedAttachments: InspirationAttachment[];
  files: File[];
};

const personalizedStarterPrompts = [
  "根据产品卖点，给我 5 个小红书选题",
  "把这段产品资料改成自然种草文案",
  "为账号规划一周的内容发布主题"
];

const generalStarterPrompts = [
  "帮我梳理一下今天的待办事项",
  "解释一个我不熟悉的概念",
  "帮我润色这段文字"
];

const MAX_COMPOSER_HEIGHT = 184;

function AttachmentPreview({ attachment }: { attachment: InspirationAttachment }) {
  const [source, setSource] = useState(attachment.preview_url || "");

  useEffect(() => {
    if (attachment.preview_url) {
      setSource(attachment.preview_url);
      return undefined;
    }
    let active = true;
    let objectUrl = "";
    void api.getInspirationAttachmentBlob(attachment.id).then((blob) => {
      if (!active) return;
      objectUrl = URL.createObjectURL(blob);
      setSource(objectUrl);
    }).catch(() => setSource(""));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachment.id, attachment.preview_url]);

  return source ? (
    <img src={source} alt={attachment.file_name} loading="lazy" />
  ) : (
    <span className="inspiration-attachment-placeholder">图片加载失败</span>
  );
}

export function InspirationMessages({
  session,
  messages,
  draftMessage,
  isLoading,
  isSending,
  assistantName = "Karries AI",
  conversationSpaceControl,
  modelModeControl,
  onOpenContext,
  onDraftMessageChange,
  onSend,
  onSaveDraft,
  onSendToVideoCreation,
  pendingAttachments = [],
  isUploadingImages = false,
  onSelectImages,
  onRemoveAttachment,
  quotedMessage = null,
  onQuoteMessage,
  onClearQuote,
  onReviseMessage,
  onActivateRevision
}: InspirationMessagesProps) {
  const messageListRef = useRef<HTMLDivElement>(null);
  const messageInputRef = useRef<HTMLTextAreaElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const revisionImageInputRef = useRef<HTMLInputElement>(null);
  const [revisionDraft, setRevisionDraft] = useState<RevisionDraft | null>(null);
  const [isRevisionSubmitting, setIsRevisionSubmitting] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null);
  const [isAttachmentMenuOpen, setIsAttachmentMenuOpen] = useState(false);

  const resizeMessageInput = useCallback(() => {
    const input = messageInputRef.current;
    if (!input) return;
    input.style.height = "auto";
    if (input.scrollHeight > 0) {
      const nextHeight = Math.min(input.scrollHeight, MAX_COMPOSER_HEIGHT);
      input.style.height = `${nextHeight}px`;
      input.style.overflowY = input.scrollHeight > MAX_COMPOSER_HEIGHT ? "auto" : "hidden";
    }
  }, []);

  useEffect(() => {
    const messageList = messageListRef.current;
    if (messageList) messageList.scrollTop = messageList.scrollHeight;
  }, [messages, isSending]);

  useLayoutEffect(() => {
    resizeMessageInput();
  }, [draftMessage, resizeMessageInput, session?.id]);

  useEffect(() => {
    window.addEventListener("resize", resizeMessageInput);
    return () => window.removeEventListener("resize", resizeMessageInput);
  }, [resizeMessageInput]);

  const canSend = session?.status === "active" && !isSending && !isUploadingImages;
  const isNormalMode = session?.interaction_mode === "normal";
  const starterPrompts = isNormalMode ? generalStarterPrompts : personalizedStarterPrompts;

  async function copyMessage(message: InspirationMessage) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(message.content);
      } else {
        const fallback = document.createElement("textarea");
        fallback.value = message.content;
        fallback.setAttribute("readonly", "");
        fallback.style.position = "fixed";
        fallback.style.opacity = "0";
        document.body.appendChild(fallback);
        fallback.select();
        const copied = document.execCommand("copy");
        fallback.remove();
        if (!copied) throw new Error("copy is unavailable");
      }
      setCopiedMessageId(message.id);
    } catch {
      setCopiedMessageId(null);
    }
  }

  function startRevision(message: InspirationMessage) {
    if (session?.status !== "active" || isSending || !onReviseMessage) return;
    setRevisionDraft({
      messageId: message.id,
      content: message.content,
      retainedAttachments: message.attachments ?? [],
      files: []
    });
  }

  async function submitRevision() {
    if (!revisionDraft || !onReviseMessage || !revisionDraft.content.trim()) return;
    setIsRevisionSubmitting(true);
    try {
      await onReviseMessage(
        revisionDraft.messageId,
        revisionDraft.content.trim(),
        revisionDraft.retainedAttachments.map((attachment) => attachment.id),
        revisionDraft.files
      );
      setRevisionDraft(null);
    } catch {
      // The page owns the error banner. Keep the editor intact so the user can retry.
    } finally {
      setIsRevisionSubmitting(false);
    }
  }

  function selectRevisionImages(files: File[]) {
    if (!revisionDraft) return;
    const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
    const remaining = Math.max(
      0,
      4 - revisionDraft.retainedAttachments.length - revisionDraft.files.length
    );
    const validFiles = files
      .filter((file) => allowedTypes.has(file.type) && file.size <= 10 * 1024 * 1024)
      .slice(0, remaining);
    if (!validFiles.length) return;
    setRevisionDraft((current) => current ? {
      ...current,
      files: [...current.files, ...validFiles]
    } : current);
  }

  return (
    <section className="inspiration-message-panel" aria-busy={isLoading || isSending}>
      <div className="inspiration-message-header">
        <div className="ai-conversation-identity">
          <span className="ai-conversation-mark"><Sparkles size={17} aria-hidden="true" /></span>
          <div>
            <h2>{session?.title || "开始一个新对话"}</h2>
            <span>{session ? (isNormalMode ? "通用对话，不自动加入创作上下文" : "已结合当前模板与会话上下文") : "选择对话模式后开始讨论"}</span>
          </div>
        </div>
        {isSending ? (
          <span className="key-status">
            <Loader2 size={14} className="spin" aria-hidden="true" />
            正在生成
          </span>
        ) : null}
      </div>

      <div className="inspiration-message-list" ref={messageListRef} aria-live="polite">
        {isLoading ? (
          <div className="inspiration-message-skeleton" aria-label="正在加载会话内容"><span /><span /><span /></div>
        ) : messages.length === 0 ? (
          <div className="ai-chat-welcome">
            <span className="ai-welcome-mark"><Sparkles size={24} aria-hidden="true" /></span>
            <h3>{session ? (isNormalMode ? "开始一段普通对话" : "从一个角色问题开始") : "选择一个对话空间"}</h3>
            <p>{session ? (isNormalMode ? "像平常使用大语言模型一样直接提问，不会默认讨论小红书。" : "AI 会按照当前个性化模板，并结合本会话的创作上下文回答。") : "先选择普通对话或一个个性化模板，再新建或打开会话。"}</p>
            {session ? (
              <div className="ai-starter-prompts" aria-label="推荐问题">
                {starterPrompts.map((prompt) => (
                  <button type="button" key={prompt} onClick={() => onDraftMessageChange(prompt)}>
                    {prompt}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : messages.map((message) => {
          const isEditing = revisionDraft?.messageId === message.id;
          const revisionIds = message.revision_message_ids ?? [message.id];
          const revisionIndex = Math.max(1, message.revision_index ?? 1);
          const revisionCount = Math.max(1, message.revision_count ?? revisionIds.length);
          return (
          <article className={`inspiration-message ${message.role}`} key={message.id}>
            <span className="inspiration-message-avatar" aria-hidden="true">
              {message.role === "user" ? <UserRound size={16} /> : <Bot size={17} />}
            </span>
            <div className="inspiration-message-body">
              <div className="inspiration-message-meta">{message.role === "user" ? "你" : assistantName}</div>
              {isEditing && revisionDraft ? (
                <div className="inspiration-revision-editor">
                  <label htmlFor={`inspiration-revision-${message.id}`}>修改历史提示词</label>
                  <textarea
                    id={`inspiration-revision-${message.id}`}
                    aria-label="编辑历史提示词"
                    value={revisionDraft.content}
                    disabled={isRevisionSubmitting}
                    onChange={(event) => setRevisionDraft((current) => current ? {
                      ...current,
                      content: event.target.value
                    } : current)}
                    rows={4}
                  />
                  {revisionDraft.retainedAttachments.length || revisionDraft.files.length ? (
                    <div className="inspiration-revision-attachments" aria-label="本次分支保留的图片">
                      {revisionDraft.retainedAttachments.map((attachment) => (
                        <div key={`retained-${attachment.id}`}>
                          <AttachmentPreview attachment={attachment} />
                          <button
                            type="button"
                            aria-label={`移除 ${attachment.file_name}`}
                            disabled={isRevisionSubmitting}
                            onClick={() => setRevisionDraft((current) => current ? {
                              ...current,
                              retainedAttachments: current.retainedAttachments.filter(
                                (item) => item.id !== attachment.id
                              )
                            } : current)}
                          >
                            <X size={13} aria-hidden="true" />
                          </button>
                        </div>
                      ))}
                      {revisionDraft.files.map((file, index) => (
                        <div className="inspiration-revision-file" key={`${file.name}-${file.size}-${index}`}>
                          <ImagePlus size={18} aria-hidden="true" />
                          <span title={file.name}>{file.name}</span>
                          <button
                            type="button"
                            aria-label={`移除 ${file.name}`}
                            disabled={isRevisionSubmitting}
                            onClick={() => setRevisionDraft((current) => current ? {
                              ...current,
                              files: current.files.filter((_, fileIndex) => fileIndex !== index)
                            } : current)}
                          >
                            <X size={13} aria-hidden="true" />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <input
                    ref={revisionImageInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    hidden
                    onChange={(event) => {
                      selectRevisionImages(Array.from(event.target.files ?? []));
                      event.target.value = "";
                    }}
                  />
                  <div className="inspiration-revision-note">
                    将从此处创建新分支，原提示词、回答和后续对话不会被覆盖。
                  </div>
                  <div className="inspiration-revision-actions">
                    <button
                      className="table-action compact"
                      type="button"
                      disabled={
                        isRevisionSubmitting
                        || revisionDraft.retainedAttachments.length + revisionDraft.files.length >= 4
                      }
                      onClick={() => revisionImageInputRef.current?.click()}
                    >
                      <ImagePlus size={15} aria-hidden="true" />
                      添加图片
                    </button>
                    <span className="inspiration-revision-spacer" />
                    <button
                      className="table-action compact"
                      type="button"
                      disabled={isRevisionSubmitting}
                      onClick={() => setRevisionDraft(null)}
                    >
                      取消
                    </button>
                    <button
                      className="primary-button inspiration-revision-submit"
                      type="button"
                      aria-label={isRevisionSubmitting ? "正在重新生成" : "创建新分支并重新生成"}
                      disabled={isRevisionSubmitting || !revisionDraft.content.trim()}
                      onClick={() => void submitRevision()}
                    >
                      {isRevisionSubmitting ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />}
                      {isRevisionSubmitting ? "正在重新生成" : "创建新分支并重新生成"}
                    </button>
                  </div>
                </div>
              ) : message.role === "assistant" ? (
                <AssistantMessageContent content={message.content} />
              ) : (
                <p>{message.content}</p>
              )}
              {!isEditing && message.attachments?.length ? (
                <div className="inspiration-attachment-grid" aria-label="消息图片">
                  {message.attachments.map((attachment) => (
                    <AttachmentPreview attachment={attachment} key={attachment.id} />
                  ))}
                </div>
              ) : null}
              {!isEditing ? (
                <div className={`inspiration-message-utility-bar ${message.role}`}>
                  {message.role === "user" && revisionCount > 1 ? (
                    <div className="inspiration-revision-nav" aria-label="提示词版本">
                      <button
                        type="button"
                        aria-label="查看上一版提示词"
                        disabled={isSending || isRevisionSubmitting || revisionIndex <= 1}
                        onClick={() => void onActivateRevision?.(revisionIds[revisionIndex - 2])}
                      >
                        <ChevronLeft size={14} aria-hidden="true" />
                      </button>
                      <span>{revisionIndex} / {revisionCount}</span>
                      <button
                        type="button"
                        aria-label="查看下一版提示词"
                        disabled={
                          isSending
                          || isRevisionSubmitting
                          || revisionIndex >= revisionCount
                        }
                        onClick={() => void onActivateRevision?.(revisionIds[revisionIndex])}
                      >
                        <ChevronRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  ) : null}
                  {message.role === "user" || message.status === "success" ? (
                    <button
                      className="inspiration-message-tool"
                      type="button"
                      aria-label={message.role === "user" ? "复制你的消息" : `复制 ${assistantName} 的消息`}
                      title="复制"
                      onClick={() => void copyMessage(message)}
                    >
                      {copiedMessageId === message.id ? <Check size={14} /> : <Copy size={14} />}
                      {copiedMessageId === message.id ? <span>已复制</span> : null}
                    </button>
                  ) : null}
                  {message.role === "user" && onQuoteMessage ? (
                    <button
                      className="inspiration-message-tool"
                      type="button"
                      aria-label="引用这条提示词"
                      title="引用到当前输入框"
                      disabled={isSending || isRevisionSubmitting}
                      onClick={() => onQuoteMessage(message)}
                    >
                      <Quote size={14} aria-hidden="true" />
                    </button>
                  ) : null}
                  {message.role === "user"
                    && session?.status === "active"
                    && onReviseMessage ? (
                    <button
                      className="inspiration-message-tool"
                      type="button"
                      aria-label="编辑这条历史提示词"
                      title="编辑并创建新分支"
                      disabled={isSending || isRevisionSubmitting}
                      onClick={() => startRevision(message)}
                    >
                      <Pencil size={14} aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
              ) : null}
              {message.status === "failed" ? <span className="message-error">本次生成未完成，请重新提问。</span> : null}
              {message.role === "assistant" && message.status === "success" ? (
                <div className="inspiration-message-actions">
                  <button className="table-action compact" type="button" disabled={(message.content_collection_id ?? 0) > 0} onClick={() => onSaveDraft(message.id)}>
                    <BookmarkPlus size={15} aria-hidden="true" />
                    {(message.content_collection_id ?? 0) > 0 ? "已保存到内容收藏" : "保存到内容收藏"}
                  </button>
                  {!isNormalMode && onSendToVideoCreation ? (
                    <button
                      className="table-action compact"
                      type="button"
                      onClick={() => onSendToVideoCreation(message)}
                    >
                      <Clapperboard size={15} aria-hidden="true" />
                      用于视频创作
                    </button>
                  ) : null}
                </div>
              ) : null}
              {message.role === "assistant" && (message.content_collection_id ?? 0) > 0 ? <span className="message-draft-id">收藏稿 ID：{message.content_collection_id}</span> : null}
            </div>
          </article>
          );
        })}
      </div>

      {session ? (
        <div className="inspiration-composer">
          {pendingAttachments.length ? (
            <div className="inspiration-pending-attachments" aria-label="待发送图片">
              {pendingAttachments.map((attachment) => (
                <div key={attachment.id}>
                  <AttachmentPreview attachment={attachment} />
                  <button
                    type="button"
                    aria-label={`移除 ${attachment.file_name}`}
                    onClick={() => onRemoveAttachment?.(attachment.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          {quotedMessage ? (
            <div className="inspiration-quote-preview" role="status">
              <Quote size={16} aria-hidden="true" />
              <div>
                <strong>引用你的提示词</strong>
                <p>{quotedMessage.content}</p>
              </div>
              <button
                type="button"
                aria-label="取消引用"
                title="取消引用"
                onClick={onClearQuote}
              >
                <X size={15} aria-hidden="true" />
              </button>
            </div>
          ) : null}
          {isAttachmentMenuOpen ? (
            <div className="inspiration-attachment-popover" role="menu" aria-label="添加内容">
              <button
                type="button"
                role="menuitem"
                aria-label="上传图片"
                onClick={() => {
                  setIsAttachmentMenuOpen(false);
                  imageInputRef.current?.click();
                }}
              >
                <ImagePlus size={17} aria-hidden="true" />
                <span>
                  <strong>上传图片</strong>
                  <small>支持 JPG、PNG、WEBP，最多 4 张</small>
                </span>
              </button>
            </div>
          ) : null}
          <label className="sr-only" htmlFor="inspiration-message-input">输入运营问题</label>
          <textarea
            ref={messageInputRef}
            id="inspiration-message-input"
            aria-label="输入消息"
            value={draftMessage}
            disabled={!canSend}
            onChange={(event) => onDraftMessageChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && canSend && draftMessage.trim()) {
                event.preventDefault();
                onSend();
              }
            }}
            placeholder={session.status === "archived" ? "此会话已归档" : "输入消息，Enter 发送，Shift + Enter 换行"}
            rows={2}
          />
          <div className="inspiration-composer-footer">
            <div className="inspiration-composer-options">
              <input
                ref={imageInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                hidden
                onChange={(event) => {
                  const files = Array.from(event.target.files || []);
                  if (files.length) onSelectImages?.(files);
                  event.target.value = "";
                }}
              />
              <div className="inspiration-attachment-menu">
                <button
                  className="inspiration-image-button inspiration-attachment-trigger"
                  type="button"
                  aria-label="添加内容"
                  aria-expanded={isAttachmentMenuOpen}
                  disabled={!onSelectImages || isUploadingImages || pendingAttachments.length >= 4}
                  onClick={() => setIsAttachmentMenuOpen((current) => !current)}
                >
                  {isUploadingImages
                    ? <Loader2 size={15} className="spin" />
                    : <Plus size={16} aria-hidden="true" />}
                  {isUploadingImages ? "上传中" : "添加"}
                </button>
              </div>
              <div className="inspiration-mode-controls" data-testid="inspiration-mode-controls">
                {modelModeControl}
                {conversationSpaceControl}
              </div>
              {onOpenContext && !isNormalMode ? (
                <button className="inspiration-context-trigger" type="button" onClick={onOpenContext}>
                  查看创作上下文
                </button>
              ) : null}
            </div>
            <span>{isNormalMode ? "通用对话不会自动加入创作上下文" : "回答可保存到内容收藏，继续复制或编辑"}</span>
            <button className="primary-button inspiration-send-button" type="button" aria-label="发送" disabled={!canSend || !draftMessage.trim()} onClick={onSend}>
              {isSending ? <Loader2 size={17} className="spin" aria-hidden="true" /> : <Send size={17} aria-hidden="true" />}
              <span>{isSending ? "生成中" : "发送"}</span>
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
