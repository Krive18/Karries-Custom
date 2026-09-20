import time


class NotificationRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create_for_employees(
        self,
        *,
        tenant_id: int,
        sender_user_id: int,
        recipient_user_ids: list[int],
        notification_type: str,
        title: str,
        content: str,
        priority: int,
        action_path: str,
        business_type: str,
        business_id: int,
        deadline_time: int,
        commit: bool = True,
    ) -> list[int]:
        now = int(time.time())
        ids: list[int] = []
        try:
            with self.conn.cursor() as cursor:
                for recipient_user_id in recipient_user_ids:
                    cursor.execute(
                        """
                        insert into user_notification (
                            tenant_id, recipient_user_id, sender_user_id,
                            notification_type, title, content, priority,
                            action_path, business_type, business_id,
                            deadline_time, read_time, status, create_time, update_time
                        )
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 1, %s, %s)
                        """,
                        (
                            tenant_id,
                            recipient_user_id,
                            sender_user_id,
                            notification_type,
                            title,
                            content,
                            priority,
                            action_path,
                            business_type,
                            business_id,
                            deadline_time,
                            now,
                            now,
                        ),
                    )
                    ids.append(int(cursor.lastrowid))
            if commit:
                self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return ids

    def active_employee_ids(self, tenant_id: int) -> list[int]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id
                from app_user
                where tenant_id = %s and user_role = 'customer' and status = 1
                order by id
                """,
                (tenant_id,),
            )
            return [int(row["id"]) for row in cursor.fetchall()]

    def validate_employee_ids(self, tenant_id: int, user_ids: list[int]) -> bool:
        if not user_ids:
            return True
        placeholders = ", ".join(["%s"] * len(user_ids))
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from app_user
                where tenant_id = %s and user_role = 'customer' and status = 1
                  and id in ({placeholders})
                """,
                (tenant_id, *user_ids),
            )
            return int(cursor.fetchone()["total"]) == len(user_ids)

    def ensure_publish_reminders(
        self,
        tenant_id: int,
        user_id: int,
        now_time: int | None = None,
    ) -> int:
        now = now_time if now_time is not None else int(time.time())
        reminder_end = now + 3 * 60 * 60
        created = 0
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select i.id, i.title, i.scheduled_time,
                           coalesce(a.display_name, '小红书账号') as account_name
                    from matrix_publish_item i
                    join matrix_publish_plan p on p.id = i.plan_id
                    left join xhs_account a on a.id = i.xhs_account_id
                    where p.user_id = %s
                      and i.user_id = %s
                      and i.status = 2
                      and i.scheduled_time > %s
                      and i.scheduled_time <= %s
                      and not exists (
                          select 1
                          from user_notification n
                          where n.tenant_id = %s
                            and n.recipient_user_id = %s
                            and n.business_type = 'matrix_publish_item_reminder'
                            and n.business_id = i.id
                            and n.status = 1
                      )
                    order by i.scheduled_time asc, i.id asc
                    """,
                    (
                        user_id,
                        user_id,
                        now,
                        reminder_end,
                        tenant_id,
                        user_id,
                    ),
                )
                rows = list(cursor.fetchall())
                for row in rows:
                    publish_time = time.strftime(
                        "%Y-%m-%d %H:%M",
                        time.localtime(int(row["scheduled_time"])),
                    )
                    cursor.execute(
                        """
                        insert into user_notification (
                            tenant_id, recipient_user_id, sender_user_id,
                            notification_type, title, content, priority,
                            action_path, business_type, business_id,
                            deadline_time, read_time, status, create_time,
                            update_time
                        )
                        values (
                            %s, %s, 0, 'task', %s, %s, 2,
                            'schedule', 'matrix_publish_item_reminder', %s,
                            %s, 0, 1, %s, %s
                        )
                        """,
                        (
                            tenant_id,
                            user_id,
                            "发布计划即将执行",
                            (
                                f"《{row['title']}》将在 {publish_time} "
                                f"发布到 {row['account_name']}，请及时检查账号登录状态。"
                            ),
                            row["id"],
                            row["scheduled_time"],
                            now,
                            now,
                        ),
                    )
                    created += 1
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return created

    def list_for_user(self, tenant_id: int, user_id: int, page: int, page_size: int) -> dict:
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select count(*) as total
                from user_notification
                where tenant_id = %s and recipient_user_id = %s and status = 1
                """,
                (tenant_id, user_id),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                """
                select id, notification_type, title, content, priority,
                       action_path, business_type, business_id, deadline_time,
                       read_time, create_time, update_time
                from user_notification
                where tenant_id = %s and recipient_user_id = %s and status = 1
                order by read_time = 0 desc, create_time desc, id desc
                limit %s offset %s
                """,
                (tenant_id, user_id, page_size, offset),
            )
            items = [self._serialize(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def unread_count(self, tenant_id: int, user_id: int) -> int:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select count(*) as total
                from user_notification
                where tenant_id = %s and recipient_user_id = %s
                  and status = 1 and read_time = 0
                """,
                (tenant_id, user_id),
            )
            return int(cursor.fetchone()["total"])

    def mark_read(self, tenant_id: int, user_id: int, notification_id: int) -> bool:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update user_notification
                set read_time = if(read_time = 0, %s, read_time), update_time = %s
                where id = %s and tenant_id = %s and recipient_user_id = %s and status = 1
                """,
                (now, now, notification_id, tenant_id, user_id),
            )
            updated = cursor.rowcount > 0
        self.conn.commit()
        return updated

    def mark_all_read(self, tenant_id: int, user_id: int) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update user_notification
                set read_time = %s, update_time = %s
                where tenant_id = %s and recipient_user_id = %s
                  and status = 1 and read_time = 0
                """,
                (now, now, tenant_id, user_id),
            )
            updated = cursor.rowcount
        self.conn.commit()
        return int(updated)

    def list_sent(self, tenant_id: int, sender_user_id: int, page: int, page_size: int) -> dict:
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select count(distinct title, content, create_time) as total
                from user_notification
                where tenant_id = %s and sender_user_id = %s and status = 1
                """,
                (tenant_id, sender_user_id),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                """
                select min(n.id) as id, n.notification_type, n.title, n.content,
                       n.priority, n.action_path, n.deadline_time, n.create_time,
                       count(*) as recipient_count,
                       sum(case when n.read_time > 0 then 1 else 0 end) as read_count
                from user_notification n
                where n.tenant_id = %s and n.sender_user_id = %s and n.status = 1
                group by n.notification_type, n.title, n.content, n.priority,
                         n.action_path, n.deadline_time, n.create_time
                order by n.create_time desc, id desc
                limit %s offset %s
                """,
                (tenant_id, sender_user_id, page_size, offset),
            )
            items = [self._serialize(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    @staticmethod
    def _serialize(row: dict) -> dict:
        result = dict(row)
        if "read_time" in result:
            result["is_read"] = int(result["read_time"] or 0) > 0
        for key in ("id", "priority", "deadline_time", "read_time", "create_time", "update_time",
                    "recipient_count", "read_count"):
            if key in result:
                result[key] = int(result[key] or 0)
        return result
