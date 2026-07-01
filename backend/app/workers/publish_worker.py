import json
import time

from app.integrations.xiaohongshu import build_note_payload, submit_note
from app.repositories.account_repository import AccountRepository
from app.repositories.log_repository import LogRepository
from app.repositories.task_repository import TaskRepository


class PublishResourceNotFoundError(ValueError):
    pass


class PublishWorker:
    def __init__(self, conn):
        self.conn = conn
        self.accounts = AccountRepository(conn)
        self.tasks = TaskRepository(conn)
        self.logs = LogRepository(conn)

    async def submit(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            raise PublishResourceNotFoundError(f"任务不存在: {task_id}")

        account = self.accounts.get(int(task["account_id"]))
        if account is None:
            raise PublishResourceNotFoundError(f"账号不存在: {task['account_id']}")

        self.tasks.set_status(task_id, 4)
        self.logs.append(task_id, "INFO", "开始提交到小红书平台定时发布")
        try:
            payload = build_note_payload(
                account_file=str(account["cookie_path"]),
                title=str(task["task_title"]),
                body=str(task["task_body"]),
                tags=json.loads(str(task["tag_text"])),
                image_paths=json.loads(str(task["image_path_text"])),
                schedule_time=int(task["schedule_time"]),
            )
            await submit_note(payload)
            now = int(time.time())
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update publish_task
                    set status = 5, submitted_time = %s, update_time = %s
                    where id = %s
                    """,
                    (now, now, task_id),
                )
            self.conn.commit()
            self.logs.append(task_id, "INFO", "提交成功，已进入小红书平台定时发布")
        except Exception as exc:
            self.tasks.set_status(task_id, 6, str(exc))
            self.logs.append(task_id, "ERROR", f"提交失败: {exc}")
            raise
