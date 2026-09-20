import { useCallback, useEffect, useRef, useState } from "react";
import { Bookmark, ChevronLeft, ChevronRight, RefreshCw, Search } from "lucide-react";

import { api } from "../api/client";
import { ContentCollectionDetail } from "../components/collection/ContentCollectionDetail";
import type { ContentCollection, ContentCollectionUpdate } from "../types";


const pageSize = 20;

type CollectionMessage = {
  text: string;
  tone: "success" | "info" | "error";
};

function explainError(error: unknown) {
  return error instanceof Error ? error.message : "请求未完成，请稍后重试。";
}

async function writeClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

export function ContentCollectionPage() {
  const [items, setItems] = useState<ContentCollection[]>([]);
  const [detail, setDetail] = useState<ContentCollection | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [message, setMessage] = useState<CollectionMessage | null>(null);
  const selectedId = useRef<number | null>(null);

  const loadDetail = useCallback(async (collectionId: number) => {
    selectedId.current = collectionId;
    setIsDetailLoading(true);
    setMessage(null);
    try {
      const next = await api.getContentCollection(collectionId);
      if (selectedId.current === collectionId) setDetail(next);
    } catch (error) {
      if (selectedId.current === collectionId) {
        setMessage({ text: explainError(error), tone: "error" });
      }
    } finally {
      if (selectedId.current === collectionId) setIsDetailLoading(false);
    }
  }, []);

  const loadItems = useCallback(async () => {
    setIsLoading(true);
    setMessage(null);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (keyword) params.set("keyword", keyword);
      const result = await api.listContentCollections(params);
      setItems(result.items);
      setTotal(result.total);
      if (!result.items.length) {
        selectedId.current = null;
        setDetail(null);
        return;
      }
      const nextId = result.items.some((item) => item.id === selectedId.current)
        ? selectedId.current as number
        : result.items[0].id;
      await loadDetail(nextId);
    } catch (error) {
      setMessage({ text: explainError(error), tone: "error" });
    } finally {
      setIsLoading(false);
    }
  }, [keyword, loadDetail, page]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  async function updateCollection(payload: ContentCollectionUpdate) {
    if (!detail || isSaving) return false;
    setIsSaving(true);
    setMessage(null);
    try {
      const updated = await api.updateContentCollection(detail.id, payload);
      setDetail(updated);
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage({ text: "收藏稿已更新，不会产生算力消耗。", tone: "success" });
      return true;
    } catch (error) {
      setMessage({ text: explainError(error), tone: "error" });
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function copyContent(text: string, label: string) {
    if (!text.trim()) {
      setMessage({ text: `${label}暂无可复制内容。`, tone: "info" });
      return;
    }
    try {
      await writeClipboard(text);
      setMessage({ text: `${label}已复制。`, tone: "success" });
    } catch {
      setMessage({ text: "复制失败，请手动选择内容复制。", tone: "error" });
    }
  }

  async function deleteCollection() {
    if (!detail || isDeleting) return;
    const confirmed = window.confirm(`确定删除收藏稿“${detail.title}”吗？\n\n只会删除收藏记录，不会删除原始 AI 对话、爆款解析任务或产品知识库素材。`);
    if (!confirmed) return;
    setIsDeleting(true);
    setMessage(null);
    try {
      await api.deleteContentCollection(detail.id);
      selectedId.current = null;
      setDetail(null);
      await loadItems();
      setMessage({
        text: "收藏稿已删除，原始业务记录和素材均未受影响。",
        tone: "success"
      });
    } catch (error) {
      setMessage({ text: explainError(error), tone: "error" });
    } finally {
      setIsDeleting(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="publish-workspace collection-workspace">
      <header className="publish-compact-heading collection-page-heading">
        <div className="publish-title-line">
          <h1>内容收藏</h1>
          <span>集中保存爆款解析与 Karries AI 内容，随时复制、编辑和复用。</span>
        </div>
        <button className="secondary-button" type="button" disabled={isLoading} onClick={() => void loadItems()}>
          <RefreshCw size={16} aria-hidden="true" />刷新
        </button>
      </header>
      {message ? (
        <div
          className={`app-alert collection-message ${message.tone}${message.tone === "success" ? " collection-message-success" : ""}`}
          role={message.tone === "error" ? "alert" : "status"}
        >
          {message.text}
        </div>
      ) : null}

      <div className="panel collection-shell">
        <aside className="collection-sidebar">
          <form
            className="collection-search"
            onSubmit={(event) => {
              event.preventDefault();
              setPage(1);
              setKeyword(keywordInput.trim());
            }}
          >
            <Search size={17} aria-hidden="true" />
            <input aria-label="搜索收藏内容" placeholder="搜索标题、脚本或标签" value={keywordInput} onChange={(event) => setKeywordInput(event.target.value)} />
            <button type="submit">搜索</button>
          </form>
          <div className="collection-list-heading">
            <strong>收藏草稿</strong>
            <span>{total} 项</span>
          </div>
          <div className="collection-list" aria-busy={isLoading}>
            {isLoading && !items.length ? <div className="collection-list-state">正在加载收藏...</div> : null}
            {!isLoading && !items.length ? (
              <div className="collection-list-state">
                <Bookmark size={26} aria-hidden="true" />
                <strong>{keyword ? "没有匹配的收藏" : "暂未收藏内容"}</strong>
                <span>{keyword ? "请更换关键词后重试" : "可从爆款解析或 Karries AI 将内容保存到这里"}</span>
              </div>
            ) : null}
            {items.map((item) => (
              <button
                className={item.id === detail?.id ? "collection-list-item active" : "collection-list-item"}
                type="button"
                key={item.id}
                onClick={() => void loadDetail(item.id)}
              >
                <Bookmark size={17} aria-hidden="true" />
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.source_type === "inspiration" ? "来自 Karries AI" : "来自爆款解析"} · #{item.source_id}</small>
                </span>
              </button>
            ))}
          </div>
          <footer className="collection-pagination">
            <button type="button" aria-label="上一页收藏" disabled={page <= 1 || isLoading} onClick={() => setPage((current) => current - 1)}><ChevronLeft size={16} /></button>
            <span>{page} / {totalPages}</span>
            <button type="button" aria-label="下一页收藏" disabled={page >= totalPages || isLoading} onClick={() => setPage((current) => current + 1)}><ChevronRight size={16} /></button>
          </footer>
        </aside>

        <main className="collection-main">
          {isDetailLoading ? <div className="collection-detail-state">正在加载收藏详情...</div> : null}
          {!isDetailLoading && detail ? (
            <ContentCollectionDetail
              item={detail}
              isSaving={isSaving || isDeleting}
              onSave={updateCollection}
              onCopy={copyContent}
              onDelete={deleteCollection}
            />
          ) : null}
          {!isDetailLoading && !detail && items.length === 0 ? (
            <div className="collection-detail-state"><Bookmark size={32} aria-hidden="true" /><strong>选择收藏稿后查看完整内容</strong></div>
          ) : null}
        </main>
      </div>
    </section>
  );
}
