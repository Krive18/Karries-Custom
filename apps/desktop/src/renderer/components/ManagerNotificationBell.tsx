import { useEffect, useRef, useState } from "react";
import { Bell, Clock3 } from "lucide-react";


export function ManagerNotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div className="notification-center" ref={ref}>
      <button
        className="icon-button notification-trigger"
        type="button"
        aria-label="查看任务提醒说明"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <Bell size={20} />
      </button>
      {open ? (
        <section className="notification-popover manager-notifications">
          <header>
            <div>
              <strong>任务提醒</strong>
              <span>由系统自动触发</span>
            </div>
          </header>
          <div className="notification-empty manager-reminder-note">
            <Clock3 size={22} aria-hidden="true" />
            <strong>发布前三小时自动提醒</strong>
            <span>
              系统会根据员工的发布计划自动生成提醒，无需管理端人工发布任务。
            </span>
          </div>
        </section>
      ) : null}
    </div>
  );
}
