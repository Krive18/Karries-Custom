import time

import pymysql

from app.repositories.material_library_repository import (
    MaterialLibraryNotFoundError,
    MaterialLibraryRepository,
)
from app.repositories.wallet_repository import WalletRepository
from app.services.credit_charge_service import CreditChargeService
from app.services.upload_storage_service import StoredUpload


STATUS_PENDING = "pending"
STATUS_CLAIMED = "claimed"
STATUS_IN_PROGRESS = "in_progress"
STATUS_AWAITING_CUSTOMER = "awaiting_customer"
STATUS_REVISION_REQUESTED = "revision_requested"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
STATUS_FAILED = "failed"

STATUS_TEXT = {
    STATUS_PENDING: "待接取",
    STATUS_CLAIMED: "已接取",
    STATUS_IN_PROGRESS: "翻译制作中",
    STATUS_AWAITING_CUSTOMER: "待客户确认",
    STATUS_REVISION_REQUESTED: "客户要求修改",
    STATUS_COMPLETED: "已完成",
    STATUS_CANCELLED: "已取消",
    STATUS_FAILED: "处理失败",
}

DELIVERY_RESOURCE_TYPES = {"video", "voiceover", "subtitle"}


class AiTranslationRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create_from_upload(
        self,
        tenant_id: int,
        user_id: int,
        client_request_id: str,
        stored: StoredUpload,
        source_language: str,
        target_language: str,
    ) -> tuple[dict, bool]:
        return self._create_task(
            tenant_id=tenant_id,
            user_id=user_id,
            client_request_id=client_request_id,
            source_type="local_upload",
            material_file_id=0,
            file_name=stored.file_name,
            file_path=stored.storage_path,
            mime_type=stored.mime_type,
            file_size=stored.file_size,
            source_language=source_language,
            target_language=target_language,
        )

    def create_from_material(
        self,
        tenant_id: int,
        user_id: int,
        client_request_id: str,
        material_file_id: int,
        source_language: str,
        target_language: str,
    ) -> tuple[dict, bool]:
        asset = MaterialLibraryRepository(self.conn).get_asset(
            tenant_id,
            material_file_id,
        )
        if asset is None or asset["file_type"] != "video":
            raise MaterialLibraryNotFoundError("video material asset not found")
        return self._create_task(
            tenant_id=tenant_id,
            user_id=user_id,
            client_request_id=client_request_id,
            source_type="material_library",
            material_file_id=material_file_id,
            file_name=str(asset["file_name"]),
            file_path=str(asset["file_path"]),
            mime_type=str(asset["mime_type"]),
            file_size=int(asset["file_size"]),
            source_language=source_language,
            target_language=target_language,
        )

    def _create_task(self, **values) -> tuple[dict, bool]:
        now = int(time.time())
        created = False
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into ai_translation_task (
                        tenant_id, user_id, client_request_id, source_type,
                        material_file_id, source_file_name, source_file_path,
                        source_mime_type, source_file_size, source_language,
                        target_language, status, operator_user_id,
                        developer_note, revision_feedback, revision_count,
                        delivery_count, charged_credit_cost, credit_ledger_id,
                        delivered_time, completed_time, create_time, update_time
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'pending', 0, '', '', 0, 0, 0, 0, 0, 0, %s, %s
                    )
                    """,
                    (
                        values["tenant_id"],
                        values["user_id"],
                        values["client_request_id"],
                        values["source_type"],
                        values["material_file_id"],
                        values["file_name"],
                        values["file_path"],
                        values["mime_type"],
                        values["file_size"],
                        values["source_language"],
                        values["target_language"],
                        now,
                        now,
                    ),
                )
                task_id = int(cursor.lastrowid)
            self.conn.commit()
            created = True
        except pymysql.err.IntegrityError:
            self.conn.rollback()
            existing = self._get_by_client_request(
                int(values["user_id"]),
                str(values["client_request_id"]),
            )
            if existing is None:
                raise
            return existing, False
        except Exception:
            self.conn.rollback()
            raise
        task = self.get_for_user(
            int(values["tenant_id"]),
            int(values["user_id"]),
            task_id,
        )
        if task is None:
            raise RuntimeError("created AI translation task is not readable")
        return task, created

    def list_for_user(
        self,
        tenant_id: int,
        user_id: int,
        status: str = "",
    ) -> list[dict]:
        where = "where task.tenant_id = %s and task.user_id = %s"
        params: list[object] = [tenant_id, user_id]
        if status:
            where += " and task.status = %s"
            params.append(status)
        return self._list(self._select_sql() + where + " order by task.id desc", params)

    def list_for_developer(self, status: str = "", keyword: str = "") -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("task.status = %s")
            params.append(status)
        clean_keyword = keyword.strip()
        if clean_keyword:
            clauses.append(
                "(task.source_file_name like %s or owner.login_name like %s "
                "or owner.nickname like %s or tenant.tenant_name like %s)"
            )
            keyword_like = f"%{clean_keyword}%"
            params.extend([keyword_like] * 4)
        where = " where " + " and ".join(clauses) if clauses else ""
        return self._list(self._select_sql() + where + " order by task.id desc", params)

    def get_for_user(
        self,
        tenant_id: int,
        user_id: int,
        task_id: int,
    ) -> dict | None:
        return self._get(
            self._select_sql()
            + " where task.tenant_id = %s and task.user_id = %s and task.id = %s",
            (tenant_id, user_id, task_id),
        )

    def get_for_developer(self, task_id: int) -> dict | None:
        return self._get(self._select_sql() + " where task.id = %s", (task_id,))

    def cancel(self, tenant_id: int, user_id: int, task_id: int) -> dict | None:
        return self._customer_transition(
            tenant_id,
            user_id,
            task_id,
            allowed={STATUS_PENDING},
            next_status=STATUS_CANCELLED,
        )

    def accept(self, tenant_id: int, user_id: int, task_id: int) -> dict | None:
        return self._customer_transition(
            tenant_id,
            user_id,
            task_id,
            allowed={STATUS_AWAITING_CUSTOMER},
            next_status=STATUS_COMPLETED,
            completed=True,
        )

    def request_revision(
        self,
        tenant_id: int,
        user_id: int,
        task_id: int,
        feedback: str,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select status from ai_translation_task
                    where tenant_id = %s and user_id = %s and id = %s
                    for update
                    """,
                    (tenant_id, user_id, task_id),
                )
                row = cursor.fetchone()
                if row is None:
                    self.conn.rollback()
                    return None
                if row["status"] != STATUS_AWAITING_CUSTOMER:
                    self.conn.rollback()
                    return {"error": "translation task cannot request revision in current state"}
                cursor.execute(
                    """
                    update ai_translation_task
                    set status = %s, revision_feedback = %s,
                        revision_count = revision_count + 1, update_time = %s
                    where id = %s
                    """,
                    (STATUS_REVISION_REQUESTED, feedback, now, task_id),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_user(tenant_id, user_id, task_id)

    def claim(self, task_id: int, developer_user_id: int, note: str) -> dict | None:
        return self._developer_transition(
            task_id,
            developer_user_id,
            allowed={STATUS_PENDING},
            next_status=STATUS_CLAIMED,
            note=note,
            assign=True,
        )

    def start(self, task_id: int, developer_user_id: int, note: str) -> dict | None:
        return self._developer_transition(
            task_id,
            developer_user_id,
            allowed={STATUS_CLAIMED, STATUS_REVISION_REQUESTED},
            next_status=STATUS_IN_PROGRESS,
            note=note,
        )

    def fail(self, task_id: int, developer_user_id: int, note: str) -> dict | None:
        return self._developer_transition(
            task_id,
            developer_user_id,
            allowed={STATUS_CLAIMED, STATUS_IN_PROGRESS, STATUS_REVISION_REQUESTED},
            next_status=STATUS_FAILED,
            note=note,
        )

    def deliver(
        self,
        task_id: int,
        developer_user_id: int,
        client_request_id: str,
        uploads: list[StoredUpload],
        note: str,
        *,
        resource_type: str = "video",
        complete_delivery: bool = False,
    ) -> tuple[dict | None, bool]:
        if resource_type not in DELIVERY_RESOURCE_TYPES:
            raise ValueError("unsupported translation delivery resource type")
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, tenant_id, user_id, status, operator_user_id,
                           delivery_count, charged_credit_cost
                    from ai_translation_task
                    where id = %s
                    for update
                    """,
                    (task_id,),
                )
                task = cursor.fetchone()
                if task is None:
                    self.conn.rollback()
                    return None, False
                cursor.execute(
                    """
                    select id from ai_translation_delivery
                    where task_id = %s and client_request_id = %s
                    limit 1
                    """,
                    (task_id, client_request_id),
                )
                if cursor.fetchone() is not None:
                    self.conn.rollback()
                    existing = self.get_for_developer(task_id)
                    return existing, False
                if task["status"] not in {
                    STATUS_CLAIMED,
                    STATUS_IN_PROGRESS,
                    STATUS_REVISION_REQUESTED,
                }:
                    self.conn.rollback()
                    return {"error": "translation task cannot be delivered in current state"}, False
                if int(task["operator_user_id"]) != developer_user_id:
                    self.conn.rollback()
                    return {"error": "translation task belongs to another developer"}, False

                delivery_no = int(task["delivery_count"]) + 1
                for asset_no, upload in enumerate(uploads, start=1):
                    cursor.execute(
                        """
                        insert into ai_translation_delivery (
                            task_id, delivery_no, asset_no, client_request_id,
                            developer_user_id, resource_type,
                            file_name, file_path, mime_type,
                            file_size, note, create_time
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            task_id,
                            delivery_no,
                            asset_no,
                            client_request_id,
                            developer_user_id,
                            resource_type,
                            upload.file_name,
                            upload.storage_path,
                            upload.mime_type,
                            upload.file_size,
                            note,
                            now,
                        ),
                    )

                charged_cost = int(task["charged_credit_cost"])
                ledger_id = 0
                if complete_delivery and charged_cost == 0:
                    cost = CreditChargeService().estimate("ai_translation_delivery")
                    ledger_id = WalletRepository(self.conn).adjust_credits(
                        int(task["user_id"]),
                        -cost,
                        "ai_translation_delivery",
                        task_id,
                        "AI翻译成片首次成功交付",
                        commit=False,
                    )
                    charged_cost = cost

                if complete_delivery:
                    cursor.execute(
                        """
                        update ai_translation_task
                        set status = %s, developer_note = %s,
                            delivery_count = %s, charged_credit_cost = %s,
                            credit_ledger_id = case
                                when credit_ledger_id = 0 then %s else credit_ledger_id end,
                            delivered_time = %s, update_time = %s
                        where id = %s
                        """,
                        (
                            STATUS_AWAITING_CUSTOMER,
                            note,
                            delivery_no,
                            charged_cost,
                            ledger_id,
                            now,
                            now,
                            task_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        update ai_translation_task
                        set developer_note = %s, delivery_count = %s,
                            update_time = %s
                        where id = %s
                        """,
                        (note, delivery_no, now, task_id),
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        delivered = self.get_for_developer(task_id)
        if delivered is None:
            raise RuntimeError("delivered AI translation task is not readable")
        return delivered, True

    def complete_delivery(
        self,
        task_id: int,
        developer_user_id: int,
        note: str,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, user_id, status, operator_user_id,
                           delivery_count, charged_credit_cost
                    from ai_translation_task
                    where id = %s
                    for update
                    """,
                    (task_id,),
                )
                task = cursor.fetchone()
                if task is None:
                    self.conn.rollback()
                    return None
                if task["status"] in {STATUS_AWAITING_CUSTOMER, STATUS_COMPLETED}:
                    self.conn.rollback()
                    return self.get_for_developer(task_id)
                if task["status"] not in {
                    STATUS_CLAIMED,
                    STATUS_IN_PROGRESS,
                    STATUS_REVISION_REQUESTED,
                }:
                    self.conn.rollback()
                    return {"error": "translation task cannot be completed in current state"}
                if int(task["operator_user_id"]) != developer_user_id:
                    self.conn.rollback()
                    return {"error": "translation task belongs to another developer"}
                if int(task["delivery_count"]) < 1:
                    self.conn.rollback()
                    return {"error": "upload at least one delivery resource before completion"}

                charged_cost = int(task["charged_credit_cost"])
                ledger_id = 0
                if charged_cost == 0:
                    cost = CreditChargeService().estimate("ai_translation_delivery")
                    ledger_id = WalletRepository(self.conn).adjust_credits(
                        int(task["user_id"]),
                        -cost,
                        "ai_translation_delivery",
                        task_id,
                        "AI翻译成片首次成功交付",
                        commit=False,
                    )
                    charged_cost = cost
                cursor.execute(
                    """
                    update ai_translation_task
                    set status = %s, developer_note = %s,
                        charged_credit_cost = %s,
                        credit_ledger_id = case
                            when credit_ledger_id = 0 then %s else credit_ledger_id end,
                        delivered_time = %s, update_time = %s
                    where id = %s
                    """,
                    (
                        STATUS_AWAITING_CUSTOMER,
                        note,
                        charged_cost,
                        ledger_id,
                        now,
                        now,
                        task_id,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_developer(task_id)

    def get_delivery(self, task_id: int, delivery_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, task_id, delivery_no, asset_no, client_request_id,
                       developer_user_id, resource_type,
                       file_name, file_path, mime_type,
                       file_size, note, create_time
                from ai_translation_delivery
                where task_id = %s and id = %s
                """,
                (task_id, delivery_id),
            )
            row = cursor.fetchone()
        return self._delivery_from_row(row) if row else None

    def _customer_transition(
        self,
        tenant_id: int,
        user_id: int,
        task_id: int,
        *,
        allowed: set[str],
        next_status: str,
        completed: bool = False,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select status from ai_translation_task
                    where tenant_id = %s and user_id = %s and id = %s
                    for update
                    """,
                    (tenant_id, user_id, task_id),
                )
                row = cursor.fetchone()
                if row is None:
                    self.conn.rollback()
                    return None
                if row["status"] not in allowed:
                    self.conn.rollback()
                    return {"error": "translation task cannot change in current state"}
                cursor.execute(
                    """
                    update ai_translation_task
                    set status = %s, completed_time = %s, update_time = %s
                    where id = %s
                    """,
                    (next_status, now if completed else 0, now, task_id),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_user(tenant_id, user_id, task_id)

    def _developer_transition(
        self,
        task_id: int,
        developer_user_id: int,
        *,
        allowed: set[str],
        next_status: str,
        note: str,
        assign: bool = False,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select status, operator_user_id from ai_translation_task
                    where id = %s for update
                    """,
                    (task_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    self.conn.rollback()
                    return None
                if row["status"] not in allowed:
                    self.conn.rollback()
                    return {"error": "translation task cannot change in current state"}
                operator_user_id = int(row["operator_user_id"])
                if not assign and operator_user_id != developer_user_id:
                    self.conn.rollback()
                    return {"error": "translation task belongs to another developer"}
                cursor.execute(
                    """
                    update ai_translation_task
                    set status = %s, operator_user_id = %s,
                        developer_note = %s, update_time = %s
                    where id = %s
                    """,
                    (next_status, developer_user_id, note, now, task_id),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_developer(task_id)

    def _get_by_client_request(self, user_id: int, client_request_id: str) -> dict | None:
        return self._get(
            self._select_sql()
            + " where task.user_id = %s and task.client_request_id = %s",
            (user_id, client_request_id),
        )

    def _list(self, sql: str, params) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
        return [self._row_to_task(row) for row in rows]

    def _get(self, sql: str, params) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
        return self._row_to_task(row) if row else None

    def _row_to_task(self, row) -> dict:
        result = dict(row)
        for key in (
            "id",
            "tenant_id",
            "user_id",
            "material_file_id",
            "source_file_size",
            "operator_user_id",
            "revision_count",
            "delivery_count",
            "charged_credit_cost",
            "credit_ledger_id",
            "delivered_time",
            "completed_time",
            "create_time",
            "update_time",
        ):
            result[key] = int(result[key])
        result["status_text"] = STATUS_TEXT.get(result["status"], result["status"])
        result["source_content_url"] = (
            f"/api/ai-translations/tasks/{result['id']}/source/content"
        )
        result["internal_source_content_url"] = (
            f"/api/internal/ai-translations/tasks/{result['id']}/source/content"
        )
        result["deliveries"] = self._list_deliveries(result["id"])
        result["delivery_resource_counts"] = {
            resource_type: sum(
                1
                for delivery in result["deliveries"]
                if delivery["resource_type"] == resource_type
            )
            for resource_type in ("video", "voiceover", "subtitle")
        }
        return result

    def _list_deliveries(self, task_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, task_id, delivery_no, asset_no, client_request_id,
                       developer_user_id, resource_type,
                       file_name, file_path, mime_type,
                       file_size, note, create_time
                from ai_translation_delivery
                where task_id = %s
                order by delivery_no desc, asset_no asc, id asc
                """,
                (task_id,),
            )
            return [self._delivery_from_row(row) for row in cursor.fetchall()]

    @staticmethod
    def _delivery_from_row(row) -> dict:
        item = dict(row)
        for key in (
            "id",
            "task_id",
            "delivery_no",
            "asset_no",
            "developer_user_id",
            "file_size",
            "create_time",
        ):
            item[key] = int(item[key])
        resource_type = str(item.get("resource_type") or "").strip().lower()
        if resource_type not in DELIVERY_RESOURCE_TYPES:
            mime_type = str(item.get("mime_type") or "").lower()
            resource_type = (
                "voiceover"
                if mime_type.startswith("audio/")
                else "subtitle"
                if mime_type in {"application/x-subrip", "text/plain"}
                else "video"
            )
        item["resource_type"] = resource_type
        item["content_url"] = (
            f"/api/ai-translations/tasks/{item['task_id']}"
            f"/deliveries/{item['id']}/content"
        )
        item["internal_content_url"] = (
            f"/api/internal/ai-translations/tasks/{item['task_id']}"
            f"/deliveries/{item['id']}/content"
        )
        return item

    @staticmethod
    def _select_sql() -> str:
        return """
            select task.id, task.tenant_id, task.user_id,
                   task.client_request_id, task.source_type,
                   task.material_file_id, task.source_file_name,
                   task.source_file_path, task.source_mime_type,
                   task.source_file_size, task.source_language,
                   task.target_language, task.status, task.operator_user_id,
                   task.developer_note, task.revision_feedback,
                   task.revision_count, task.delivery_count,
                   task.charged_credit_cost, task.credit_ledger_id,
                   task.delivered_time, task.completed_time,
                   task.create_time, task.update_time,
                   coalesce(tenant.tenant_name, '') tenant_name,
                   owner.login_name user_login_name,
                   owner.nickname user_nickname,
                   coalesce(nullif(operator.nickname, ''), operator.login_name, '') operator_name
            from ai_translation_task task
            join app_user owner on owner.id = task.user_id
            left join tenant on tenant.id = task.tenant_id
            left join app_user operator on operator.id = task.operator_user_id
        """
