import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, CheckCheck, Clock3 } from "lucide-react";

import { customerApi } from "../api/client";
import type { PageKey, UserNotification } from "../types";


const navigablePages = new Set<PageKey>([
  "create", "productLibrary", "viralAnalysis", "inspiration",
  "publishReview", "schedule", "settings", "recharge", "profile", "feedback"
]);

function formatTime(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false
  }).format(new Date(timestamp * 1000));
}


export function CustomerNotificationBell({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<UserNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [message, setMessage] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const [list, unread] = await Promise.all([
        customerApi.listNotifications(new URLSearchParams({ page_size: "20" })),
        customerApi.getUnreadNotificationCount()
      ]);
      setItems(list.items);
      setUnreadCount(unread.count);
      setMessage("");
    } catch {
      setMessage("通知暂时无法加载");
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const openItem = async (item: UserNotification) => {
    if (!item.is_read) {
      await customerApi.markNotificationRead(item.id);
      setItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, is_read: true, read_time: Math.floor(Date.now() / 1000) } : entry));
      setUnreadCount((current) => Math.max(0, current - 1));
    }
    if (navigablePages.has(item.action_path as PageKey)) {
      onNavigate(item.action_path as PageKey);
      setOpen(false);
    }
  };

  const readAll = async () => {
    await customerApi.markAllNotificationsRead();
    setItems((current) => current.map((item) => ({ ...item, is_read: true })));
    setUnreadCount(0);
  };

  return (
    <div className="notification-center" ref={ref}>
      <button className="icon-button notification-trigger" type="button" aria-label="通知" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
        <Bell size={20} />
        {unreadCount ? <span>{unreadCount > 99 ? "99+" : unreadCount}</span> : null}
      </button>
      {open ? (
        <section className="notification-popover customer-notifications">
          <header><div><strong>任务提醒</strong><span>{unreadCount} 条未读</span></div><button type="button" onClick={() => void readAll()}><CheckCheck size={15} />全部已读</button></header>
          {message ? <div className="notification-message">{message}</div> : null}
          <div className="notification-list">
            {items.map((item) => (
              <button key={item.id} type="button" className={item.is_read ? "notification-item" : `notification-item unread priority-${item.priority}`} onClick={() => void openItem(item)}>
                <div><strong>{item.title}</strong><time>{formatTime(item.create_time)}</time></div>
                <p>{item.content}</p>
                {item.deadline_time ? <small><Clock3 size={13} />截止 {formatTime(item.deadline_time)}</small> : null}
              </button>
            ))}
            {!items.length && !message ? <div className="notification-empty">暂无通知</div> : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
