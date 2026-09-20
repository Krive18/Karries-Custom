import datetime
import time


class AdminOperationsRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def overview(self, tenant_id: int, days: int) -> dict:
        now = int(time.time())
        today_start = int(
            time.mktime(
                (time.localtime(now).tm_year, time.localtime(now).tm_mon, time.localtime(now).tm_mday,
                 0, 0, 0, 0, 0, -1)
            )
        )
        tomorrow_start = today_start + 86400

        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select
                    count(*) as total_employees,
                    sum(case when status = 1 then 1 else 0 end) as active_employees
                from app_user
                where tenant_id = %s and user_role = 'customer'
                """,
                (tenant_id,),
            )
            employee = cursor.fetchone()

            cursor.execute(
                """
                select
                    count(*) as total_accounts,
                    sum(case when a.status = 1 then 1 else 0 end) as normal_accounts,
                    sum(case when a.status = 2 then 1 else 0 end) as expired_accounts,
                    sum(case when a.status = 4 then 1 else 0 end) as risk_accounts
                from xhs_account a
                join app_user u on u.id = a.user_id
                where u.tenant_id = %s and u.user_role = 'customer'
                """,
                (tenant_id,),
            )
            account = cursor.fetchone()

            cursor.execute(
                """
                select
                    sum(case when i.scheduled_time between %s and %s then 1 else 0 end)
                        as today_scheduled,
                    sum(
                        case
                            when i.scheduled_time between %s and %s and i.status = 4
                            then 1
                            else 0
                        end
                    ) as today_submitted,
                    sum(
                        case
                            when i.scheduled_time between %s and %s and i.status in (5, 6)
                            then 1
                            else 0
                        end
                    ) as today_failed,
                    sum(case when i.status in (1, 2, 3) then 1 else 0 end) as pending_items,
                    sum(case when i.status = 4 then 1 else 0 end) as submitted_total,
                    sum(case when i.status in (4, 5, 6) then 1 else 0 end) as finished_total
                from matrix_publish_item i
                join app_user u on u.id = i.user_id
                where u.tenant_id = %s
                """,
                (
                    today_start,
                    tomorrow_start - 1,
                    today_start,
                    tomorrow_start - 1,
                    today_start,
                    tomorrow_start - 1,
                    tenant_id,
                ),
            )
            publish = cursor.fetchone()

            cursor.execute(
                """
                select coalesce(sum(w.balance), 0) as team_credit_balance
                from credit_wallet w
                join app_user u on u.id = w.user_id
                where u.tenant_id = %s and u.user_role = 'customer'
                """,
                (tenant_id,),
            )
            wallet = cursor.fetchone()

            start_date = datetime.date.today() - datetime.timedelta(days=days - 1)
            start_time = int(time.mktime(start_date.timetuple()))
            cursor.execute(
                """
                select
                    date_format(from_unixtime(i.scheduled_time), '%%Y-%%m-%%d') as day_key,
                    count(*) as scheduled,
                    sum(case when i.status = 4 then 1 else 0 end) as submitted,
                    sum(case when i.status in (5, 6) then 1 else 0 end) as failed
                from matrix_publish_item i
                join app_user u on u.id = i.user_id
                where u.tenant_id = %s and i.scheduled_time >= %s
                group by day_key
                order by day_key
                """,
                (tenant_id, start_time),
            )
            trend_rows = {str(row["day_key"]): row for row in cursor.fetchall()}

            cursor.execute(
                """
                select i.status, count(*) as total
                from matrix_publish_item i
                join app_user u on u.id = i.user_id
                where u.tenant_id = %s
                group by i.status
                order by i.status
                """,
                (tenant_id,),
            )
            distribution_rows = cursor.fetchall()

            cursor.execute(
                """
                select
                    u.id as user_id,
                    u.nickname,
                    coalesce(a.account_count, 0) as account_count,
                    coalesce(p.publish_count, 0) as publish_count,
                    coalesce(p.failed_count, 0) as failed_count,
                    coalesce(c.credit_consumed, 0) as credit_consumed
                from app_user u
                left join (
                    select user_id, count(*) as account_count
                    from xhs_account
                    group by user_id
                ) a on a.user_id = u.id
                left join (
                    select user_id,
                           sum(case when status = 4 then 1 else 0 end) as publish_count,
                           sum(case when status in (5, 6) then 1 else 0 end) as failed_count
                    from matrix_publish_item
                    where scheduled_time >= %s
                    group by user_id
                ) p on p.user_id = u.id
                left join (
                    select user_id, sum(abs(change_amount)) as credit_consumed
                    from credit_ledger
                    where change_amount < 0 and create_time >= %s
                    group by user_id
                ) c on c.user_id = u.id
                where u.tenant_id = %s and u.user_role = 'customer'
                order by publish_count desc, account_count desc, u.id asc
                limit 8
                """,
                (start_time, start_time, tenant_id),
            )
            ranking = [self._int_fields(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                select
                    sum(case when a.status = 2 then 1 else 0 end) as expired_accounts,
                    sum(case when a.status = 4 then 1 else 0 end) as risk_accounts
                from xhs_account a
                join app_user u on u.id = a.user_id
                where u.tenant_id = %s
                """,
                (tenant_id,),
            )
            account_alerts = cursor.fetchone()
            cursor.execute(
                """
                select
                    sum(case when i.status = 2 and i.scheduled_time < %s then 1 else 0 end) as overdue_items,
                    sum(case when i.status in (5, 6) then 1 else 0 end) as failed_items
                from matrix_publish_item i
                join app_user u on u.id = i.user_id
                where u.tenant_id = %s
                """,
                (now, tenant_id),
            )
            publish_alerts = cursor.fetchone()

        finished_total = int(publish["finished_total"] or 0)
        submitted_total = int(publish["submitted_total"] or 0)
        summary = {
            "total_employees": int(employee["total_employees"] or 0),
            "active_employees": int(employee["active_employees"] or 0),
            "total_accounts": int(account["total_accounts"] or 0),
            "normal_accounts": int(account["normal_accounts"] or 0),
            "expired_accounts": int(account["expired_accounts"] or 0),
            "risk_accounts": int(account["risk_accounts"] or 0),
            "today_scheduled": int(publish["today_scheduled"] or 0),
            "today_submitted": int(publish["today_submitted"] or 0),
            "today_failed": int(publish["today_failed"] or 0),
            "pending_items": int(publish["pending_items"] or 0),
            "success_rate": round(submitted_total * 100 / finished_total, 1) if finished_total else 0,
            "team_credit_balance": int(wallet["team_credit_balance"] or 0),
        }
        trend = []
        for offset in range(days):
            day = start_date + datetime.timedelta(days=offset)
            day_key = day.strftime("%Y-%m-%d")
            row = trend_rows.get(day_key, {})
            trend.append(
                {
                    "date": day_key,
                    "label": day.strftime("%m/%d"),
                    "scheduled": int(row.get("scheduled", 0) or 0),
                    "submitted": int(row.get("submitted", 0) or 0),
                    "failed": int(row.get("failed", 0) or 0),
                }
            )

        status_names = {
            1: "待确认",
            2: "待发布",
            3: "提交中",
            4: "已提交",
            5: "发布失败",
            6: "人工接管",
            7: "已取消",
        }
        distribution = [
            {
                "status": int(row["status"]),
                "name": status_names.get(int(row["status"]), "未知"),
                "value": int(row["total"]),
            }
            for row in distribution_rows
        ]
        alerts = [
            {"type": "login_expired", "title": "登录已过期账号", "count": int(account_alerts["expired_accounts"] or 0)},
            {"type": "risk", "title": "账号风险提醒", "count": int(account_alerts["risk_accounts"] or 0)},
            {"type": "overdue", "title": "已到期未提交", "count": int(publish_alerts["overdue_items"] or 0)},
            {"type": "failed", "title": "发布失败或需接管", "count": int(publish_alerts["failed_items"] or 0)},
        ]
        return {
            "summary": summary,
            "publish_trend": trend,
            "status_distribution": distribution,
            "employee_ranking": ranking,
            "alerts": alerts,
        }

    def list_accounts(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        employee_id: int | None,
        status: int | None,
        keyword: str,
    ) -> dict:
        conditions = ["u.tenant_id = %s", "u.user_role = 'customer'"]
        params: list[object] = [tenant_id]
        if employee_id is not None:
            conditions.append("a.user_id = %s")
            params.append(employee_id)
        if status is not None:
            conditions.append("a.status = %s")
            params.append(status)
        if keyword:
            conditions.append("(a.display_name like %s or a.account_group like %s or u.nickname like %s)")
            like = f"%{keyword}%"
            params.extend((like, like, like))
        where_sql = " and ".join(conditions)
        offset = (page - 1) * page_size

        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from xhs_account a
                join app_user u on u.id = a.user_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                select
                    a.id, a.user_id, a.display_name, a.account_group, a.status,
                    a.daily_limit, a.min_interval_minutes, a.last_publish_time,
                    a.today_publish_count, a.create_time, a.update_time,
                    u.nickname as employee_name, u.login_name as employee_login,
                    case when a.login_state_path <> '' then 1 else 0 end as login_state_ready,
                    coalesce(s.status, '') as latest_login_status,
                    coalesce(p.pending_count, 0) as pending_count,
                    coalesce(p.submitted_count, 0) as submitted_count,
                    coalesce(p.failed_count, 0) as failed_count
                from xhs_account a
                join app_user u on u.id = a.user_id
                left join xhs_account_login_session s on s.id = (
                    select max(ls.id)
                    from xhs_account_login_session ls
                    where ls.xhs_account_id = a.id and ls.user_id = a.user_id
                )
                left join (
                    select xhs_account_id,
                           sum(case when status in (1, 2, 3) then 1 else 0 end) as pending_count,
                           sum(case when status = 4 then 1 else 0 end) as submitted_count,
                           sum(case when status in (5, 6) then 1 else 0 end) as failed_count
                    from matrix_publish_item
                    group by xhs_account_id
                ) p on p.xhs_account_id = a.id
                where {where_sql}
                order by a.status <> 1 desc, a.update_time desc, a.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._int_fields(row) for row in cursor.fetchall()]
        for item in items:
            item["login_state_ready"] = bool(item["login_state_ready"])
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def list_plans(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        employee_id: int | None,
        status: int | None,
        keyword: str,
    ) -> dict:
        conditions = ["u.tenant_id = %s", "u.user_role = 'customer'"]
        params: list[object] = [tenant_id]
        if employee_id is not None:
            conditions.append("p.user_id = %s")
            params.append(employee_id)
        if status is not None:
            conditions.append("p.status = %s")
            params.append(status)
        if keyword:
            conditions.append("(p.plan_name like %s or u.nickname like %s)")
            like = f"%{keyword}%"
            params.extend((like, like))
        where_sql = " and ".join(conditions)
        offset = (page - 1) * page_size

        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from matrix_publish_plan p
                join app_user u on u.id = p.user_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                select
                    p.id, p.user_id, p.plan_name, p.source_type, p.content_type,
                    p.product_id, p.status, p.schedule_start_time, p.schedule_end_time,
                    p.create_time, p.update_time,
                    u.nickname as employee_name, u.login_name as employee_login,
                    count(i.id) as item_count,
                    sum(case when i.status in (1, 2, 3) then 1 else 0 end) as pending_count,
                    sum(case when i.status = 4 then 1 else 0 end) as submitted_count,
                    sum(case when i.status in (5, 6) then 1 else 0 end) as failed_count,
                    sum(case when i.status = 7 then 1 else 0 end) as cancelled_count
                from matrix_publish_plan p
                join app_user u on u.id = p.user_id
                left join matrix_publish_item i on i.plan_id = p.id and i.user_id = p.user_id
                where {where_sql}
                group by p.id, p.user_id, p.plan_name, p.source_type, p.content_type,
                         p.product_id, p.status, p.schedule_start_time, p.schedule_end_time,
                         p.create_time, p.update_time, u.nickname, u.login_name
                order by p.update_time desc, p.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._int_fields(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_plan(self, tenant_id: int, plan_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select p.id, p.user_id, p.plan_name, p.source_type, p.content_type,
                       p.product_id, p.status, p.schedule_start_time, p.schedule_end_time,
                       p.create_time, p.update_time,
                       u.nickname as employee_name, u.login_name as employee_login
                from matrix_publish_plan p
                join app_user u on u.id = p.user_id
                where p.id = %s and u.tenant_id = %s and u.user_role = 'customer'
                """,
                (plan_id, tenant_id),
            )
            plan = cursor.fetchone()
            if plan is None:
                return None
            cursor.execute(
                """
                select i.id, i.plan_id, i.xhs_account_id, i.content_type, i.title,
                       i.scheduled_time, i.status, i.last_error,
                       i.attempt_count, i.max_attempts, i.next_retry_time,
                       i.submitted_time, i.publish_result_json,
                       i.create_time, i.update_time,
                       a.display_name as account_name, a.status as account_status
                from matrix_publish_item i
                join xhs_account a on a.id = i.xhs_account_id and a.user_id = i.user_id
                where i.plan_id = %s and i.user_id = %s
                order by i.scheduled_time, i.id
                """,
                (plan_id, plan["user_id"]),
            )
            items = [self._int_fields(row) for row in cursor.fetchall()]
        result = self._int_fields(plan)
        result["items"] = items
        return result

    def get_plan_owner(self, tenant_id: int, plan_id: int) -> int | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select p.user_id
                from matrix_publish_plan p
                join app_user u on u.id = p.user_id
                where p.id = %s and u.tenant_id = %s and u.user_role = 'customer'
                """,
                (plan_id, tenant_id),
            )
            row = cursor.fetchone()
        return None if row is None else int(row["user_id"])

    @staticmethod
    def _int_fields(row: dict) -> dict:
        result = dict(row)
        for key, value in list(result.items()):
            if key in {
                "id", "user_id", "product_id", "status", "daily_limit",
                "min_interval_minutes", "last_publish_time", "today_publish_count",
                "create_time", "update_time", "login_state_ready", "pending_count",
                "submitted_count", "failed_count", "cancelled_count", "item_count",
                "schedule_start_time", "schedule_end_time", "xhs_account_id",
                "scheduled_time", "account_status", "account_count", "publish_count",
                "credit_consumed",
                "attempt_count", "max_attempts", "next_retry_time", "submitted_time",
            }:
                result[key] = int(value or 0)
        return result
