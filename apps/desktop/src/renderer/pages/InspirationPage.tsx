import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Pencil,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  PinOff,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  X
} from "lucide-react";

import { ApiRequestError, api } from "../api/client";

function generateRequestId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = (Math.random() * 16) | 0;
    return (char === "x" ? value : (value & 0x3) | 0x8).toString(16);
  });
}

import {
  InspirationContextPanel,
  type InspirationSessionDraft
} from "../components/inspiration/InspirationContextPanel";
import { InspirationMessages } from "../components/inspiration/InspirationMessages";
import { composeInspirationPrompt } from "../components/inspiration/inspirationQuote";
import {
  InspirationSpaceSelector,
  type InspirationConversationSpace,
  conversationSpaceValue
} from "../components/inspiration/InspirationSpaceSelector";
import { InspirationTemplateManager } from "../components/inspiration/InspirationTemplateManager";
import type {
  AgentVideoCreationHandoff,
  InspirationAttachment,
  InspirationMessage,
  InspirationModelMode,
  InspirationPersonalizationTemplate,
  InspirationPersonalizationTemplateUpdate,
  InspirationSession,
  InspirationSessionDetail,
  MaterialFolder,
  ViralAnalysisAgentHandoff
} from "../types";

const pageSize = 20;
const MODEL_MODE_STORAGE_KEY = "inspiration:model-mode";
const defaultConversationSpace: InspirationConversationSpace = {
  interaction_mode: "normal",
  personalization_template_id: 0
};
const initialDraft: InspirationSessionDraft = {
  title: "",
  linked_product_id: 0,
  linked_xhs_account_id: 0,
  goal_type: "general",
  interaction_mode: "normal",
  personalization_template_id: 0,
  tone: "自然真诚",
  extra_requirement: ""
};

type SessionAction =
  | { mode: "rename"; session: InspirationSession }
  | { mode: "delete"; session: InspirationSession }
  | null;

function readModelMode(): InspirationModelMode {
  try {
    return window.localStorage.getItem(MODEL_MODE_STORAGE_KEY) === "pro"
      ? "pro"
      : "standard";
  } catch {
    return "standard";
  }
}

function explainError(error: unknown, modelMode: InspirationModelMode = "standard") {
  if (error instanceof ApiRequestError) {
    if (error.code === "SESSION_GENERATING") return "上一条建议正在生成，请稍后再试。";
    if (error.code === "SESSION_ARCHIVED") return "会话已经归档，不能继续发送消息。";
    if (error.code === "AI_PROVIDER_ERROR") {
      return modelMode === "pro"
        ? "Pro 服务暂时不可用，请稍后重试。"
        : "灵感服务暂时无法响应，请稍后重试。";
    }
  }
  return error instanceof Error ? error.message : "操作未完成，请稍后重试。";
}

function feedbackTone(value: string): "success" | "error" | "info" {
  if (/失败|错误|异常|未完成|不可用|不能|无效|最多|仅支持|请输入|稍后/.test(value)) {
    return "error";
  }
  if (/成功|完成|已保存|已创建|已更新|已归档|已置顶|已取消|已切换|已上传/.test(value)) {
    return "success";
  }
  return "info";
}

type InspirationPageProps = {
  initialHandoff?: ViralAnalysisAgentHandoff | null;
  onInitialHandoffConsumed?: (key: string) => void;
  onSendToVideoCreation?: (handoff: AgentVideoCreationHandoff) => void;
};

export function InspirationPage({
  initialHandoff = null,
  onInitialHandoffConsumed,
  onSendToVideoCreation
}: InspirationPageProps) {
  const [sessions, setSessions] = useState<InspirationSession[]>([]);
  const [detail, setDetail] = useState<InspirationSessionDetail | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isListLoading, setIsListLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [sendingSessionId, setSendingSessionId] = useState<number | null>(null);
  const [isNewSessionOpen, setIsNewSessionOpen] = useState(false);
  const [isContextOpen, setIsContextOpen] = useState(false);
  const [sessionDraft, setSessionDraft] = useState(initialDraft);
  const [sessionKeyword, setSessionKeyword] = useState("");
  const [messageDraft, setMessageDraft] = useState("");
  const [quotedMessage, setQuotedMessage] = useState<InspirationMessage | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<InspirationAttachment[]>([]);
  const [isUploadingImages, setIsUploadingImages] = useState(false);
  const [message, setMessage] = useState("");
  const [sessionAction, setSessionAction] = useState<SessionAction>(null);
  const [sessionTitleDraft, setSessionTitleDraft] = useState("");
  const [isSessionActionPending, setIsSessionActionPending] = useState(false);
  const [templates, setTemplates] = useState<InspirationPersonalizationTemplate[]>([]);
  const [conversationSpace, setConversationSpace] = useState(defaultConversationSpace);
  const [modelMode, setModelMode] = useState<InspirationModelMode>(readModelMode);
  const [isConversationSpaceReady, setIsConversationSpaceReady] = useState(false);
  const [isPersonalizationOpen, setIsPersonalizationOpen] = useState(false);
  const [isSessionPanelOpen, setIsSessionPanelOpen] = useState(true);
  const [isPersonalizationSaving, setIsPersonalizationSaving] = useState(false);
  const [productFolders, setProductFolders] = useState<MaterialFolder[]>([]);
  const listRequestRef = useRef(0);
  const detailRequestRef = useRef(0);
  const sendRequestRef = useRef(0);
  const pendingMessageRequestRef = useRef<{
    sessionId: number;
    content: string;
    clientRequestId: string;
    attachmentIds: number[];
    modelMode: InspirationModelMode;
  } | null>(null);
  const selectedSessionIdRef = useRef<number | null>(null);
  const selectSessionRef = useRef<(sessionId: number) => Promise<void>>(
    async () => undefined
  );
  const conversationSpaceRef = useRef<InspirationConversationSpace>(defaultConversationSpace);
  const openedHandoffKeyRef = useRef("");
  const newSessionIntentRef = useRef(Boolean(initialHandoff));
  const viralSourceBySessionRef = useRef<Record<number, number>>({});
  const [pendingHandoff, setPendingHandoff] =
    useState<ViralAnalysisAgentHandoff | null>(null);

  const clearPendingAttachments = useCallback(() => {
    setPendingAttachments((current) => {
      current.forEach((item) => {
        if (item.preview_url) URL.revokeObjectURL(item.preview_url);
      });
      return [];
    });
  }, []);

  useEffect(() => clearPendingAttachments, [clearPendingAttachments]);

  const loadSessions = useCallback(async (
    requestedPage = 1,
    requestedSpace = conversationSpaceRef.current
  ) => {
    const requestId = ++listRequestRef.current;
    setIsListLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(requestedPage),
        page_size: String(pageSize),
        interaction_mode: requestedSpace.interaction_mode
      });
      if (requestedSpace.interaction_mode === "personalized") {
        params.set(
          "personalization_template_id",
          String(requestedSpace.personalization_template_id)
        );
      }
      const result = await api.listInspirationSessions(params);
      if (requestId !== listRequestRef.current) return;
      if (result.items.length === 0 && result.total > 0 && requestedPage > 1) {
        void loadSessions(requestedPage - 1, requestedSpace);
        return;
      }
      setSessions(result.items);
      setPage(result.page);
      setTotal(result.total);
      setMessage("");
      const rememberedSessionId = Number(
        window.localStorage.getItem(
          `inspiration:last-session:${conversationSpaceValue(requestedSpace)}`
        ) || 0
      );
      if (
        rememberedSessionId > 0
        && result.items.some((session) => session.id === rememberedSessionId)
        && selectedSessionIdRef.current === null
        && !newSessionIntentRef.current
      ) {
        void selectSessionRef.current(rememberedSessionId);
      }
    } catch (error) {
      if (requestId === listRequestRef.current) setMessage(explainError(error));
    } finally {
      if (requestId === listRequestRef.current) setIsListLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void api.listMaterialProjectGroups()
      .then((groups) => Promise.all(groups.map(async (group) => {
        try {
          const listing = await api.listMaterialLibraryItems(
            0,
            "",
            "",
            false,
            group.id
          );
          return listing.folders.map((folder) => ({
            ...folder,
            folder_name: `${group.group_name} / ${folder.folder_name}`
          }));
        } catch {
          return [];
        }
      })))
      .then((foldersByGroup) => {
        if (active) setProductFolders(foldersByGroup.flat());
      })
      .catch(() => {
        if (active) setProductFolders([]);
      });
    void Promise.all([
      api.listInspirationPersonalizationTemplates(),
      api.getInspirationPersonalizationPreference()
    ]).then(([savedTemplates, preference]) => {
      setTemplates(savedTemplates);
      const selectedTemplate = savedTemplates.find(
        (template) => template.id === preference.personalization_template_id
          && template.status === "active"
      );
      const nextSpace: InspirationConversationSpace =
        preference.interaction_mode === "personalized" && selectedTemplate
          ? {
              interaction_mode: "personalized",
              personalization_template_id: selectedTemplate.id
            }
          : defaultConversationSpace;
      conversationSpaceRef.current = nextSpace;
      setConversationSpace(nextSpace);
      setIsConversationSpaceReady(true);
      setSessionDraft((current) => ({ ...current, ...nextSpace }));
      void loadSessions(1, nextSpace);
    }).catch(() => {
      conversationSpaceRef.current = defaultConversationSpace;
      setConversationSpace(defaultConversationSpace);
      setIsConversationSpaceReady(true);
      void loadSessions(1, defaultConversationSpace);
    });
    return () => {
      active = false;
    };
  }, [loadSessions]);

  async function refreshTemplates() {
    const nextTemplates = await api.listInspirationPersonalizationTemplates();
    setTemplates(nextTemplates);
    return nextTemplates;
  }

  async function createTemplate(payload: InspirationPersonalizationTemplateUpdate) {
    setIsPersonalizationSaving(true);
    try {
      const created = await api.createInspirationPersonalizationTemplate(payload);
      setTemplates((current) => [created, ...current]);
      await changeConversationSpace({
        interaction_mode: "personalized",
        personalization_template_id: created.id
      });
      setIsPersonalizationOpen(false);
      setMessage("个性化模板已创建并设为当前对话模式。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsPersonalizationSaving(false);
    }
  }

  async function updateTemplate(
    templateId: number,
    payload: InspirationPersonalizationTemplateUpdate
  ) {
    setIsPersonalizationSaving(true);
    try {
      const updated = await api.updateInspirationPersonalizationTemplate(templateId, payload);
      setTemplates((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage("个性化模板已保存。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsPersonalizationSaving(false);
    }
  }

  async function duplicateTemplate(templateId: number) {
    setIsPersonalizationSaving(true);
    try {
      const created = await api.duplicateInspirationPersonalizationTemplate(templateId);
      setTemplates((current) => [created, ...current]);
      setMessage("模板副本已创建。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsPersonalizationSaving(false);
    }
  }

  async function archiveTemplate(templateId: number) {
    setIsPersonalizationSaving(true);
    try {
      await api.archiveInspirationPersonalizationTemplate(templateId);
      const nextTemplates = await refreshTemplates();
      if (
        conversationSpaceRef.current.interaction_mode === "personalized"
        && conversationSpaceRef.current.personalization_template_id === templateId
      ) {
        await changeConversationSpace(defaultConversationSpace);
      }
      setTemplates(nextTemplates);
      setMessage("模板已归档，原有历史会话仍会保留。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsPersonalizationSaving(false);
    }
  }

  async function changeConversationSpace(nextSpace: InspirationConversationSpace) {
    conversationSpaceRef.current = nextSpace;
    setConversationSpace(nextSpace);
    setIsConversationSpaceReady(true);
    selectedSessionIdRef.current = null;
    setDetail(null);
    setMessageDraft("");
    setQuotedMessage(null);
    clearPendingAttachments();
    setPage(1);
    setSessionDraft((current) => ({
      ...current,
      ...nextSpace,
      linked_product_id: nextSpace.interaction_mode === "normal" ? 0 : current.linked_product_id,
      linked_xhs_account_id: nextSpace.interaction_mode === "normal" ? 0 : current.linked_xhs_account_id,
      goal_type: nextSpace.interaction_mode === "normal" ? "general" : current.goal_type,
      extra_requirement: nextSpace.interaction_mode === "normal" ? "" : current.extra_requirement
    }));
    try {
      await api.updateInspirationPersonalizationPreference(nextSpace);
    } catch (error) {
      setMessage(`当前模式已切换，但默认选择保存失败：${explainError(error)}`);
    }
    await loadSessions(1, nextSpace);
  }

  const selectSession = useCallback(async (sessionId: number) => {
    const requestId = ++detailRequestRef.current;
    newSessionIntentRef.current = false;
    selectedSessionIdRef.current = sessionId;
    setIsDetailLoading(true);
    setIsNewSessionOpen(false);
    setIsContextOpen(false);
    setMessageDraft("");
    setQuotedMessage(null);
    clearPendingAttachments();
    try {
      const nextDetail = await api.getInspirationSession(sessionId);
      if (requestId !== detailRequestRef.current || selectedSessionIdRef.current !== sessionId) return;
      setDetail(nextDetail);
      window.localStorage.setItem(
        `inspiration:last-session:${conversationSpaceValue(conversationSpaceRef.current)}`,
        String(sessionId)
      );
      setMessage("");
    } catch (error) {
      if (requestId === detailRequestRef.current && selectedSessionIdRef.current === sessionId) {
        setMessage(explainError(error));
      }
    } finally {
      if (requestId === detailRequestRef.current) setIsDetailLoading(false);
    }
  }, [clearPendingAttachments]);
  selectSessionRef.current = selectSession;

  useEffect(() => {
    if (!initialHandoff || openedHandoffKeyRef.current === initialHandoff.key) return;
    openedHandoffKeyRef.current = initialHandoff.key;
    newSessionIntentRef.current = true;
    detailRequestRef.current += 1;
    selectedSessionIdRef.current = null;
    setDetail(null);
    setPendingHandoff(initialHandoff);
    setSessionDraft(initialHandoff.session_draft);
    setMessageDraft(initialHandoff.initial_message);
    setIsNewSessionOpen(true);
    setMessage("爆款解析结果已带入，请选择产品资料并创建会话。");
  }, [initialHandoff]);

  async function createSession() {
    if (!sessionDraft.title.trim()) {
      setMessage("请先填写会话标题。");
      return;
    }
    setIsCreating(true);
    const handoffToSend = pendingHandoff;
    try {
      const currentSpace = conversationSpaceRef.current;
      const activeSpace: InspirationConversationSpace = handoffToSend
        ? {
            interaction_mode: "personalized",
            personalization_template_id:
              currentSpace.interaction_mode === "personalized"
                ? currentSpace.personalization_template_id
                : templates.find((template) => template.status === "active")?.id ?? 0
          }
        : currentSpace;
      if (handoffToSend) {
        conversationSpaceRef.current = activeSpace;
        setConversationSpace(activeSpace);
        if (activeSpace.personalization_template_id > 0) {
          void api.updateInspirationPersonalizationPreference(activeSpace).catch(() => undefined);
        }
      }
      const created = await api.createInspirationSession({
        ...sessionDraft,
        ...activeSpace,
        title: sessionDraft.title.trim(),
        ...(activeSpace.interaction_mode === "normal" ? {
          linked_product_id: 0,
          linked_xhs_account_id: 0,
          goal_type: "general" as const,
          extra_requirement: ""
        } : {})
      });
      const nextSession: InspirationSession = created;
      const nextMessages: InspirationMessage[] = [];
      newSessionIntentRef.current = false;
      selectedSessionIdRef.current = created.id;
      window.localStorage.setItem(
        `inspiration:last-session:${conversationSpaceValue(activeSpace)}`,
        String(created.id)
      );
      if (handoffToSend) {
        viralSourceBySessionRef.current[created.id] = handoffToSend.source_job_id;
        setMessage("爆款解析结果已放入输入框，可修改确认后再发送。");
        setPendingHandoff(null);
        onInitialHandoffConsumed?.(handoffToSend.key);
      } else {
        setMessage("会话已创建，可以开始提问。");
      }
      setSessions((current) => [nextSession, ...current.filter((item) => item.id !== created.id)].slice(0, pageSize));
      setDetail({ session: nextSession, messages: nextMessages });
      setPage(1);
      setTotal((current) => current + 1);
      setIsNewSessionOpen(false);
      setSessionDraft({ ...initialDraft, ...activeSpace });
      setMessageDraft(handoffToSend ? handoffToSend.initial_message : "");
      void loadSessions(1);
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsCreating(false);
    }
  }

  async function uploadImages(files: File[]) {
    if (!detail || isUploadingImages) return;
    const remaining = Math.max(0, 4 - pendingAttachments.length);
    const selected = files.slice(0, remaining);
    if (!selected.length) {
      setMessage("每条消息最多添加 4 张图片。");
      return;
    }
    const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
    const invalid = selected.find((file) => !allowedTypes.has(file.type) || file.size > 10 * 1024 * 1024);
    if (invalid) {
      setMessage("仅支持 JPG、PNG、WEBP，且单张图片不能超过 10 MB。");
      return;
    }
    setIsUploadingImages(true);
    try {
      for (const file of selected) {
        const uploaded = await api.uploadInspirationAttachment(detail.session.id, file);
        const previewUrl = URL.createObjectURL(file);
        setPendingAttachments((current) => [
          ...current,
          { ...uploaded, preview_url: previewUrl }
        ]);
      }
      setMessage("");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsUploadingImages(false);
    }
  }

  function removePendingAttachment(attachmentId: number) {
    setPendingAttachments((current) => {
      const removed = current.find((item) => item.id === attachmentId);
      if (removed?.preview_url) URL.revokeObjectURL(removed.preview_url);
      return current.filter((item) => item.id !== attachmentId);
    });
  }

  async function sendMessage() {
    if (!detail || !messageDraft.trim()) return;
    const session = detail.session;
    const requestId = ++sendRequestRef.current;
    const content = composeInspirationPrompt(messageDraft, quotedMessage?.content);
    const attachmentIds = pendingAttachments.map((item) => item.id);
    const pendingRequest = pendingMessageRequestRef.current;
    const clientRequestId = pendingRequest?.sessionId === session.id
      && pendingRequest.content === content
      && pendingRequest.attachmentIds.join(",") === attachmentIds.join(",")
      && pendingRequest.modelMode === modelMode
      ? pendingRequest.clientRequestId
      : generateRequestId();
    pendingMessageRequestRef.current = {
      sessionId: session.id,
      content,
      clientRequestId,
      attachmentIds,
      modelMode
    };
    setSendingSessionId(session.id);
    try {
      const response = await api.sendInspirationMessage(session.id, {
        content,
        client_request_id: clientRequestId,
        attachment_ids: attachmentIds,
        model_mode: modelMode
      });
      const nextSession = {
        ...session,
        status: "active" as const,
        message_count: session.message_count + 2,
        total_credit_cost: session.total_credit_cost + response.credit_cost
      };
      setSessions((current) => current.map((item) => item.id === session.id ? nextSession : item));
      if (requestId !== sendRequestRef.current || selectedSessionIdRef.current !== session.id) return;
      setDetail((current) => {
        if (!current || current.session.id !== session.id) return current;
        const responseMessages = [response.user_message, response.assistant_message];
        const responseIds = new Set(responseMessages.map((item) => item.id));
        const nextMessages: InspirationMessage[] = [
          ...current.messages.filter((item) => !responseIds.has(item.id)),
          ...responseMessages
        ];
        return { session: nextSession, messages: nextMessages };
      });
      setMessageDraft("");
      setQuotedMessage(null);
      clearPendingAttachments();
      pendingMessageRequestRef.current = null;
      setMessage("");
    } catch (error) {
      if (requestId === sendRequestRef.current && selectedSessionIdRef.current === session.id) {
        setMessage(explainError(error, modelMode));
      }
    } finally {
      if (requestId === sendRequestRef.current) setSendingSessionId(null);
    }
  }

  async function reviseMessage(
    messageId: number,
    content: string,
    retainedAttachmentIds: number[],
    files: File[]
  ) {
    if (!detail || sendingSessionId !== null) return;
    const session = detail.session;
    const requestId = ++sendRequestRef.current;
    setSendingSessionId(session.id);
    try {
      const attachmentIds: number[] = [];
      for (const file of files) {
        const uploaded = await api.uploadInspirationAttachment(session.id, file);
        attachmentIds.push(uploaded.id);
      }
      await api.reviseInspirationMessage(session.id, messageId, {
        content,
        client_request_id: generateRequestId(),
        attachment_ids: attachmentIds,
        model_mode: modelMode,
        retained_attachment_ids: retainedAttachmentIds
      });
      const refreshed = await api.getInspirationSession(session.id);
      if (
        requestId !== sendRequestRef.current
        || selectedSessionIdRef.current !== session.id
      ) return;
      setDetail(refreshed);
      setSessions((current) => current.map((item) => (
        item.id === refreshed.session.id ? refreshed.session : item
      )));
      setMessage("");
    } catch (error) {
      if (
        requestId === sendRequestRef.current
        && selectedSessionIdRef.current === session.id
      ) {
        setMessage(explainError(error, modelMode));
      }
      throw error;
    } finally {
      if (requestId === sendRequestRef.current) setSendingSessionId(null);
    }
  }

  async function activateRevision(messageId: number) {
    if (!detail || sendingSessionId !== null) return;
    const sessionId = detail.session.id;
    try {
      const activated = await api.activateInspirationMessageRevision(sessionId, messageId);
      if (selectedSessionIdRef.current !== sessionId) return;
      setDetail(activated);
      setSessions((current) => current.map((item) => (
        item.id === activated.session.id ? activated.session : item
      )));
      setMessage("");
    } catch (error) {
      if (selectedSessionIdRef.current === sessionId) setMessage(explainError(error));
    }
  }

  async function archiveSession() {
    if (!detail || sendingSessionId === detail.session.id) return;
    const sessionId = detail.session.id;
    try {
      const archived = await api.archiveInspirationSession(sessionId);
      if (selectedSessionIdRef.current !== sessionId) return;
      setDetail((current) => current?.session.id === sessionId ? { ...current, session: archived } : current);
      setSessions((current) => current.map((item) => item.id === archived.id ? archived : item));
      setMessage("会话已归档。");
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  async function togglePinned(session: InspirationSession) {
    try {
      const updated = await api.setInspirationSessionPinned(
        session.id,
        !session.is_pinned
      );
      setSessions((current) => current.map((item) =>
        item.id === updated.id ? updated : item
      ));
      setDetail((current) => current?.session.id === updated.id
        ? { ...current, session: updated }
        : current
      );
      setMessage(updated.is_pinned ? "会话已置顶，将长期保留在列表顶部。" : "已取消置顶。");
      await loadSessions(1);
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  async function renameSession() {
    if (sessionAction?.mode !== "rename") return;
    const title = sessionTitleDraft.trim();
    if (!title) {
      setMessage("请输入会话名称。");
      return;
    }
    setIsSessionActionPending(true);
    try {
      const updated = await api.renameInspirationSession(
        sessionAction.session.id,
        title
      );
      setSessions((current) => current.map((item) =>
        item.id === updated.id ? updated : item
      ));
      setDetail((current) => current?.session.id === updated.id
        ? { ...current, session: updated }
        : current
      );
      setSessionAction(null);
      setMessage("会话名称已更新。");
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsSessionActionPending(false);
    }
  }

  async function deleteSession() {
    if (sessionAction?.mode !== "delete") return;
    const sessionId = sessionAction.session.id;
    setIsSessionActionPending(true);
    try {
      await api.deleteInspirationSession(sessionId);
      if (selectedSessionIdRef.current === sessionId) {
        selectedSessionIdRef.current = null;
        setDetail(null);
        setMessageDraft("");
      }
      setSessions((current) => current.filter((item) => item.id !== sessionId));
      setTotal((current) => Math.max(0, current - 1));
      setSessionAction(null);
      setMessage("会话已删除。");
      await loadSessions(page);
    } catch (error) {
      setMessage(explainError(error));
    } finally {
      setIsSessionActionPending(false);
    }
  }

  async function saveDraft(messageId: number) {
    try {
      const result = await api.saveInspirationMessageDraft(messageId);
      setDetail((current) => current ? {
        ...current,
        messages: current.messages.map((item) => item.id === messageId
          ? { ...item, content_collection_id: result.collection_id }
          : item)
      } : current);
      setMessage("已保存到内容收藏。");
    } catch (error) {
      setMessage(explainError(error));
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const selectedSession = detail?.session ?? null;
  const selectedTemplateId = selectedSession?.personalization_template_id
    ?? conversationSpace.personalization_template_id;
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId);
  const configuredAssistantName = selectedTemplate?.assistant_name.trim();
  const assistantName = !configuredAssistantName || configuredAssistantName === "AI Agent"
    ? "Karries AI"
    : configuredAssistantName;
  const conversationSpaceLabel = conversationSpace.interaction_mode === "normal"
    ? "普通对话"
    : selectedTemplate?.template_name ?? "个性化模板";
  const spaceSelector = isConversationSpaceReady ? (
    <InspirationSpaceSelector
      space={conversationSpace}
      templates={templates}
      onChange={(space) => void changeConversationSpace(space)}
      onManage={() => setIsPersonalizationOpen(true)}
    />
  ) : null;
  const modelModeSelector = (
    <div className="inspiration-model-control">
      <label className="inspiration-model-selector">
        <Sparkles size={15} aria-hidden="true" />
        <span className="sr-only">模型模式</span>
        <select
          aria-label="模型模式"
          value={modelMode}
          onChange={(event) => {
            const nextMode = event.target.value as InspirationModelMode;
            setModelMode(nextMode);
            try {
              window.localStorage.setItem(MODEL_MODE_STORAGE_KEY, nextMode);
            } catch {
              // The selected mode still applies to this session when storage is unavailable.
            }
          }}
        >
          <option value="standard">标准模式</option>
          <option value="pro">Pro</option>
        </select>
      </label>
      {modelMode === "pro" ? (
        <span className="inspiration-model-cost">Pro 每次成功生成扣除 5 算力</span>
      ) : null}
    </div>
  );
  const filteredSessions = sessions.filter((session) =>
    session.title.toLocaleLowerCase().includes(sessionKeyword.trim().toLocaleLowerCase())
  );
  return (
    <section className="page-stack inspiration-page">
      <div className="page-heading horizontal-heading inspiration-page-heading">
        <div>
          <h1>Karries AI</h1>
          {!selectedSession ? spaceSelector : null}
        </div>
        <div className="heading-actions inspiration-heading-actions">
          <button
            className="secondary-button compact inspiration-session-toggle"
            type="button"
            aria-label={isSessionPanelOpen ? "收起历史对话" : "展开历史对话"}
            aria-expanded={isSessionPanelOpen}
            onClick={() => setIsSessionPanelOpen((current) => !current)}
          >
            {isSessionPanelOpen
              ? <PanelLeftClose size={16} aria-hidden="true" />
              : <PanelLeftOpen size={16} aria-hidden="true" />}
            {isSessionPanelOpen ? "收起历史" : "展开历史"}
          </button>
          <button
            className="secondary-button compact"
            type="button"
            onClick={() => setIsPersonalizationOpen(true)}
          >
            <Settings2 size={16} aria-hidden="true" />
            个性化
          </button>
          <button className="icon-button inspiration-refresh" type="button" aria-label="刷新" onClick={() => void loadSessions(page)}>
            <RefreshCw size={17} aria-hidden="true" />
          </button>
        </div>
      </div>
      {message ? (
        <div className={`form-message ${feedbackTone(message)}`} role="status">
          {message}
        </div>
      ) : null}
      <div className={isSessionPanelOpen
        ? "inspiration-workspace"
        : "inspiration-workspace session-panel-collapsed"}
      >
        {isSessionPanelOpen ? <aside className="inspiration-session-panel" aria-label="会话列表">
          <button className="primary-button inspiration-new-session" type="button" onClick={() => {
            newSessionIntentRef.current = true;
            setSessionDraft((current) => ({ ...current, ...conversationSpaceRef.current }));
            setIsNewSessionOpen(true);
          }}>
            <Plus size={17} aria-hidden="true" />
            新建会话
          </button>
          <label className="inspiration-session-search">
            <Search size={15} aria-hidden="true" />
            <input
              aria-label="搜索会话"
              value={sessionKeyword}
              onChange={(event) => setSessionKeyword(event.target.value)}
              placeholder="搜索历史会话"
            />
          </label>
          <div className="panel-title inspiration-session-title">
            <h2>历史对话</h2>
            <span>{total} 条</span>
          </div>
          {isListLoading ? <div className="inspiration-session-skeleton" aria-label="正在加载会话"><span /><span /><span /></div> : null}
          {!isListLoading && sessions.length === 0 ? <div className="empty-list-state">暂无会话，点击“新建会话”开始。</div> : null}
          {!isListLoading && sessions.length > 0 && filteredSessions.length === 0 ? <div className="empty-list-state compact-empty">没有匹配的会话</div> : null}
          {!isListLoading ? (
            <div className="inspiration-session-list">
              {filteredSessions.map((session, index) => (
                <div
                  key={session.id}
                  className={selectedSession?.id === session.id ? "inspiration-session-item active" : "inspiration-session-item"}
                >
                  <button
                    className="inspiration-session-open"
                    type="button"
                    onClick={() => void selectSession(session.id)}
                  >
                    <strong title={session.title}>{session.title}</strong>
                  </button>
                  <div className="inspiration-session-actions">
                    <button
                      className={session.is_pinned ? "inspiration-session-action active" : "inspiration-session-action"}
                      type="button"
                      title={session.is_pinned ? `取消置顶：${session.title}` : `置顶：${session.title}`}
                      aria-label={session.is_pinned ? `取消置顶第 ${index + 1} 个会话` : `置顶第 ${index + 1} 个会话`}
                      onClick={() => void togglePinned(session)}
                    >
                      {session.is_pinned ? <PinOff size={14} aria-hidden="true" /> : <Pin size={14} aria-hidden="true" />}
                    </button>
                    <button
                      className="inspiration-session-action"
                      type="button"
                      title={`重命名：${session.title}`}
                      aria-label={`重命名第 ${index + 1} 个会话`}
                      onClick={() => {
                        setSessionTitleDraft(session.title);
                        setSessionAction({ mode: "rename", session });
                      }}
                    >
                      <Pencil size={14} aria-hidden="true" />
                    </button>
                    <button
                      className="inspiration-session-action danger"
                      type="button"
                      title={`删除：${session.title}`}
                      aria-label={`删除第 ${index + 1} 个会话`}
                      onClick={() => setSessionAction({ mode: "delete", session })}
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {total > pageSize ? (
            <div className="inspiration-pagination" aria-label="会话分页"><button className="table-action compact" type="button" disabled={page <= 1 || isListLoading} onClick={() => void loadSessions(page - 1)}><ChevronLeft size={15} aria-hidden="true" />上一页</button><span>第 {page} 页 / 共 {total} 条</span><button className="table-action compact" type="button" disabled={page >= pageCount || isListLoading} onClick={() => void loadSessions(page + 1)}>下一页<ChevronRight size={15} aria-hidden="true" /></button></div>
          ) : null}
        </aside> : null}
        <InspirationMessages
          session={selectedSession}
          messages={detail?.messages ?? []}
          draftMessage={messageDraft}
          isLoading={isDetailLoading}
          isSending={sendingSessionId === selectedSession?.id}
          assistantName={assistantName}
          modelModeControl={modelModeSelector}
          conversationSpaceControl={spaceSelector}
          onOpenContext={selectedSession?.interaction_mode === "personalized" ? () => setIsContextOpen(true) : undefined}
          onDraftMessageChange={setMessageDraft}
          onSend={() => void sendMessage()}
          pendingAttachments={pendingAttachments}
          isUploadingImages={isUploadingImages}
          onSelectImages={(files) => void uploadImages(files)}
          onRemoveAttachment={removePendingAttachment}
          quotedMessage={quotedMessage}
          onQuoteMessage={(nextMessage) => setQuotedMessage(nextMessage)}
          onClearQuote={() => setQuotedMessage(null)}
          onReviseMessage={reviseMessage}
          onActivateRevision={(messageId) => void activateRevision(messageId)}
          onSaveDraft={(messageId) => void saveDraft(messageId)}
          onSendToVideoCreation={(assistantMessage) => {
            const session = detail?.session;
            if (!session || !onSendToVideoCreation) return;
            const sourceJobId = viralSourceBySessionRef.current[session.id] ?? 0;
            onSendToVideoCreation({
              key: `agent-video-${session.id}-${assistantMessage.id}-${Date.now()}`,
              source_session_id: session.id,
              source_message_id: assistantMessage.id,
              source_viral_job_id: sourceJobId,
              job_title: session.title || "爆款融合视频创作",
              script_text: assistantMessage.content,
              requirement_text: sourceJobId > 0
                ? "基于爆款解析结果与所选产品资料形成的原创视频脚本，请保持结构参考但避免直接照搬。"
                : "已由 Karries AI 整理的视频脚本，请按脚本完成制作。",
              linked_product_id: session.linked_product_id
            });
          }}
        />
      </div>
      {isNewSessionOpen ? (
        <div className="material-picker-backdrop" role="presentation">
          <section className="inspiration-context-dialog" role="dialog" aria-modal="true" aria-label="新建会话">
            <InspirationContextPanel
              draft={sessionDraft}
              session={selectedSession}
              isCreating={isCreating}
              isArchiveDisabled={false}
              isOpen
              productFolders={productFolders}
              conversationSpaceLabel={conversationSpaceLabel}
              onDraftChange={setSessionDraft}
              onCreate={() => void createSession()}
              onClose={() => {
                newSessionIntentRef.current = false;
                setIsNewSessionOpen(false);
              }}
              onArchive={() => undefined}
            />
          </section>
        </div>
      ) : null}
      {isContextOpen && selectedSession ? (
        <div className="material-picker-backdrop" role="presentation">
          <section className="inspiration-context-dialog" role="dialog" aria-modal="true" aria-label="创作上下文">
            <InspirationContextPanel
              draft={sessionDraft}
              session={selectedSession}
              isCreating={false}
              isArchiveDisabled={sendingSessionId === selectedSession.id}
              isOpen={false}
              productFolders={productFolders}
              conversationSpaceLabel={conversationSpaceLabel}
              onDraftChange={setSessionDraft}
              onCreate={() => undefined}
              onClose={() => setIsContextOpen(false)}
              onArchive={() => void archiveSession()}
            />
          </section>
        </div>
      ) : null}
      {sessionAction ? (
        <div className="material-picker-backdrop" role="presentation">
          <section
            className="inspiration-session-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="inspiration-session-dialog-title"
          >
            <header>
              <h2 id="inspiration-session-dialog-title">
                {sessionAction.mode === "rename" ? "重命名会话" : "删除会话"}
              </h2>
              <button
                className="icon-button compact-icon"
                type="button"
                aria-label="关闭"
                disabled={isSessionActionPending}
                onClick={() => setSessionAction(null)}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>
            {sessionAction.mode === "rename" ? (
              <label>
                会话名称
                <input
                  autoFocus
                  maxLength={100}
                  value={sessionTitleDraft}
                  onChange={(event) => setSessionTitleDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void renameSession();
                  }}
                />
              </label>
            ) : (
              <p>删除“{sessionAction.session.title}”后，对话记录将无法恢复。</p>
            )}
            <footer>
              <button
                className="secondary-button"
                type="button"
                disabled={isSessionActionPending}
                onClick={() => setSessionAction(null)}
              >
                取消
              </button>
              <button
                className={sessionAction.mode === "delete" ? "quiet-danger" : "primary-button"}
                type="button"
                disabled={isSessionActionPending}
                onClick={() => void (sessionAction.mode === "rename" ? renameSession() : deleteSession())}
              >
                {isSessionActionPending ? "处理中" : sessionAction.mode === "rename" ? "保存" : "确认删除"}
              </button>
            </footer>
          </section>
        </div>
      ) : null}
      {isPersonalizationOpen ? (
        <div className="material-picker-backdrop" role="presentation">
          <InspirationTemplateManager
            templates={templates}
            isSaving={isPersonalizationSaving}
            onClose={() => setIsPersonalizationOpen(false)}
            onCreate={createTemplate}
            onUpdate={updateTemplate}
            onDuplicate={duplicateTemplate}
            onArchive={archiveTemplate}
          />
        </div>
      ) : null}
    </section>
  );
}
