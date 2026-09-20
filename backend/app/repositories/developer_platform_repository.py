import math
import time


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def aggregate_ai_usage(rows: list[dict]) -> dict:
    hourly: dict[int, list[dict]] = {}
    providers: dict[str, list[dict]] = {}
    for row in rows:
        timestamp = int(row["create_time"] or 0)
        hour = timestamp - (timestamp % 3600)
        hourly.setdefault(hour, []).append(row)
        provider = str(row["provider"] or "unknown").strip().lower() or "unknown"
        providers.setdefault(provider, []).append(row)

    def metrics(items: list[dict]) -> dict:
        calls = len(items)
        failures = sum(1 for item in items if str(item["status"]) == "failed")
        latencies = [int(item["latency_ms"] or 0) for item in items]
        return {
            "calls": calls,
            "failures": failures,
            "failure_rate": round(failures * 100 / calls, 1) if calls else 0.0,
            "p95_latency_ms": _p95(latencies),
        }

    overall = metrics(rows)
    return {
        "calls_24h": overall["calls"],
        "failures_24h": overall["failures"],
        "failure_rate": overall["failure_rate"],
        "p95_latency_ms": overall["p95_latency_ms"],
        "trend": [
            {
                "timestamp": timestamp,
                **{
                    "calls": bucket_metrics["calls"],
                    "failures": bucket_metrics["failures"],
                    "success_rate": round(100 - bucket_metrics["failure_rate"], 1),
                    "p95_latency_ms": bucket_metrics["p95_latency_ms"],
                },
            }
            for timestamp, bucket_metrics in (
                (hour, metrics(hourly[hour])) for hour in sorted(hourly)
            )
        ],
        "providers": {
            provider: metrics(items)
            for provider, items in sorted(providers.items())
        },
    }


class DeveloperPlatformRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def overview_counts(self) -> dict:
        now = int(time.time())
        since = now - 86400
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select status, count(*) total
                from viral_analysis_job
                group by status
                """
            )
            viral_rows = cursor.fetchall()
            cursor.execute(
                """
                select
                    case
                        when review_status = 'rejected' or status = 4 then 5
                        else status
                    end status,
                    count(*) total
                from video_edit_job
                group by case
                    when review_status = 'rejected' or status = 4 then 5
                    else status
                end
                """
            )
            video_rows = cursor.fetchall()
            cursor.execute(
                """
                select status, count(*) total
                from matrix_publish_plan
                group by status
                """
            )
            matrix_rows = cursor.fetchall()
            cursor.execute(
                """
                select create_time, status, latency_ms, provider
                from ai_usage_log
                where create_time >= %s
                order by create_time, id
                limit 10000
                """,
                (since,),
            )
            ai_rows = list(cursor.fetchall())
            cursor.execute(
                """
                select count(*) total
                from app_user
                where user_role in ('platform_admin', 'developer_admin')
                  and status = 1
                """
            )
            active_developers = int(cursor.fetchone()["total"] or 0)
            cursor.execute(
                """
                select
                    count(*) open_alerts,
                    sum(case when severity = 'page' then 1 else 0 end) page_alerts
                from developer_alert_event
                where status in ('open', 'acknowledged')
                """
            )
            alert_row = cursor.fetchone()

        return {
            "tasks": {
                "viral_analysis": self._string_status_counts(viral_rows),
                "video_edit": self._video_status_counts(video_rows),
                "matrix_publish": self._matrix_status_counts(matrix_rows),
            },
            "ai": aggregate_ai_usage(ai_rows),
            "open_alerts": int(alert_row["open_alerts"] or 0),
            "page_alerts": int(alert_row["page_alerts"] or 0),
            "active_developers": active_developers,
            "updated_at": now,
        }

    def list_tasks(
        self,
        *,
        page: int,
        page_size: int,
        kind: str | None,
        status: str | None,
        keyword: str,
    ) -> dict:
        union_sql = """
            select
                job.id,
                'viral_analysis' kind,
                job.title,
                job.tenant_id,
                coalesce(tenant.tenant_name, concat('Tenant ', job.tenant_id)) tenant_name,
                job.user_id,
                user.login_name,
                coalesce(nullif(user.nickname, ''), user.login_name) user_name,
                job.status,
                job.status raw_status,
                job.error_message error_summary,
                job.create_time,
                job.update_time
            from viral_analysis_job job
            join app_user user on user.id = job.user_id
            left join tenant on tenant.id = job.tenant_id
            union all
            select
                job.id,
                'video_edit' kind,
                job.job_title title,
                user.tenant_id,
                coalesce(tenant.tenant_name, concat('Tenant ', user.tenant_id)) tenant_name,
                job.user_id,
                user.login_name,
                coalesce(nullif(user.nickname, ''), user.login_name) user_name,
                case
                    when job.review_status = 'rejected' or job.status = 4 then 'cancelled'
                    when job.status = 1 then 'pending'
                    when job.status = 2 then 'running'
                    when job.status = 3 then 'completed'
                    when job.status = 5 then 'cancelled'
                    else 'unknown'
                end status,
                cast(job.status as char) raw_status,
                '' error_summary,
                job.create_time,
                job.update_time
            from video_edit_job job
            join app_user user on user.id = job.user_id
            left join tenant on tenant.id = user.tenant_id
            union all
            select
                plan.id,
                'matrix_publish' kind,
                plan.plan_name title,
                user.tenant_id,
                coalesce(tenant.tenant_name, concat('Tenant ', user.tenant_id)) tenant_name,
                plan.user_id,
                user.login_name,
                coalesce(nullif(user.nickname, ''), user.login_name) user_name,
                case plan.status
                    when 1 then 'pending'
                    when 2 then 'pending'
                    when 3 then 'pending'
                    when 4 then 'running'
                    when 5 then 'completed'
                    when 6 then 'failed'
                    when 7 then 'cancelled'
                    else 'unknown'
                end status,
                cast(plan.status as char) raw_status,
                coalesce((
                    select item.last_error
                    from matrix_publish_item item
                    where item.plan_id = plan.id and item.last_error <> ''
                    order by item.update_time desc, item.id desc
                    limit 1
                ), '') error_summary,
                plan.create_time,
                plan.update_time
            from matrix_publish_plan plan
            join app_user user on user.id = plan.user_id
            left join tenant on tenant.id = user.tenant_id
        """
        clauses: list[str] = []
        params: list[object] = []
        if kind:
            clauses.append("task.kind = %s")
            params.append(kind)
        if status:
            clauses.append("task.status = %s")
            params.append(status)
        if keyword:
            clauses.append(
                "(task.title like %s or task.login_name like %s or task.user_name like %s)"
            )
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern, pattern])
        where_sql = f"where {' and '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"select count(*) total from ({union_sql}) task {where_sql}",
                tuple(params),
            )
            total = int(cursor.fetchone()["total"] or 0)
            cursor.execute(
                f"""
                select * from ({union_sql}) task
                {where_sql}
                order by task.update_time desc, task.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            rows = list(cursor.fetchall())

        items = []
        for row in rows:
            raw_status = str(row["raw_status"])
            actions: list[str] = []
            if row["kind"] == "matrix_publish":
                if raw_status in {"1", "2", "3"}:
                    actions.append("cancel")
                if raw_status == "6":
                    actions.append("retry")
            items.append(
                {
                    "id": int(row["id"]),
                    "kind": str(row["kind"]),
                    "title": str(row["title"]),
                    "tenant_id": int(row["tenant_id"]),
                    "tenant_name": str(row["tenant_name"]),
                    "user_id": int(row["user_id"]),
                    "user_name": str(row["user_name"]),
                    "login_name": str(row["login_name"]),
                    "status": str(row["status"]),
                    "raw_status": raw_status,
                    "error_summary": str(row["error_summary"] or "")[:500],
                    "available_actions": actions,
                    "created_at": int(row["create_time"]),
                    "updated_at": int(row["update_time"]),
                }
            )
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def list_customer_accounts(
        self,
        *,
        page: int,
        page_size: int,
        keyword: str,
        role: str | None,
        status: int | None,
    ) -> dict:
        where = ["user.user_role in ('client_owner', 'customer')"]
        params: list[object] = []
        if keyword:
            where.append(
                "(user.login_name like %s or user.nickname like %s "
                "or tenant.tenant_name like %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like])
        if role:
            where.append("user.user_role = %s")
            params.append(role)
        if status is not None:
            where.append("user.status = %s")
            params.append(status)
        where_sql = " and ".join(where)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from app_user user
                left join tenant on tenant.id = user.tenant_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"] or 0)
            cursor.execute(
                f"""
                select user.id, user.tenant_id, user.login_name,
                       user.nickname, user.user_role, user.status,
                       user.last_login_time, user.create_time, user.update_time,
                       coalesce(tenant.tenant_name, '') as tenant_name,
                       coalesce(wallet.balance, 0) as balance,
                       coalesce(plan.plan_code, '') as membership_plan_code,
                       coalesce(plan.plan_name, '') as membership_plan_name
                from app_user user
                left join tenant on tenant.id = user.tenant_id
                left join credit_wallet wallet on wallet.user_id = user.id
                left join user_membership membership on membership.user_id = user.id
                left join membership_plan plan on plan.id = membership.plan_id
                where {where_sql}
                order by tenant.tenant_name asc,
                         case when user.user_role = 'client_owner' then 0 else 1 end,
                         user.id asc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            rows = cursor.fetchall()
        items = []
        for row in rows:
            item = dict(row)
            for key in (
                "id",
                "tenant_id",
                "status",
                "last_login_time",
                "create_time",
                "update_time",
                "balance",
            ):
                item[key] = int(item[key] or 0)
            items.append(item)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def get_matrix_plan_owner(self, plan_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select plan.user_id, user.tenant_id, plan.status
                from matrix_publish_plan plan
                join app_user user on user.id = plan.user_id
                where plan.id = %s
                """,
                (plan_id,),
            )
            return cursor.fetchone()

    @staticmethod
    def _blank_counts() -> dict[str, int]:
        return {
            "total": 0,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }

    @classmethod
    def _string_status_counts(cls, rows: list[dict]) -> dict[str, int]:
        result = cls._blank_counts()
        mapping = {
            "pending": "pending",
            "processing": "running",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }
        for row in rows:
            total = int(row["total"] or 0)
            result["total"] += total
            target = mapping.get(str(row["status"]))
            if target:
                result[target] += total
        return result

    @classmethod
    def _video_status_counts(cls, rows: list[dict]) -> dict[str, int]:
        result = cls._blank_counts()
        mapping = {1: "pending", 2: "running", 3: "completed", 4: "running", 5: "cancelled"}
        for row in rows:
            total = int(row["total"] or 0)
            result["total"] += total
            target = mapping.get(int(row["status"]))
            if target:
                result[target] += total
        return result

    @classmethod
    def _matrix_status_counts(cls, rows: list[dict]) -> dict[str, int]:
        result = cls._blank_counts()
        mapping = {
            1: "pending",
            2: "pending",
            3: "pending",
            4: "running",
            5: "completed",
            6: "failed",
            7: "cancelled",
        }
        for row in rows:
            total = int(row["total"] or 0)
            result["total"] += total
            target = mapping.get(int(row["status"]))
            if target:
                result[target] += total
        return result
