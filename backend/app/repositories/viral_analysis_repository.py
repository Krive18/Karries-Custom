import json
import time
import uuid
from typing import Any

from app.schemas.viral_analysis import ViralAnalysisJobCreate, ViralAnalysisStructuredResult


class ViralAnalysisNotFoundError(LookupError):
    pass


class ViralAnalysisStateError(ValueError):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"viral analysis job is {status}")


class ViralAnalysisRepository:
    LEASE_SECONDS = 10 * 60

    def __init__(self, conn) -> None:
        self.conn = conn

    def create_job(self, tenant_id: int, user_id: int, payload: ViralAnalysisJobCreate) -> dict:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into viral_analysis_job (
                    tenant_id, user_id, title, source_type, source_url, material_file_id,
                    analysis_goal, supplement_text, status, ai_provider, ai_model,
                    credit_cost, error_message, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, 0, %s, %s, 'pending', '', '', 0, '', %s, %s)
                """,
                (
                    tenant_id,
                    user_id,
                    payload.title,
                    payload.source_type,
                    payload.source_url,
                    json.dumps(payload.analysis_goal, ensure_ascii=False),
                    payload.supplement_text,
                    now,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)
        self.conn.commit()
        job = self.get_for_user(tenant_id, user_id, job_id)
        if job is None:
            raise ViralAnalysisNotFoundError
        return job

    def add_material(self, tenant_id: int, user_id: int, job_id: int, material: dict) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                self._require_for_user(cursor, tenant_id, user_id, job_id)
                cursor.execute(
                    """
                    insert into viral_analysis_material (
                        tenant_id, job_id, file_name, file_type, mime_type,
                        file_size, storage_path, create_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        job_id,
                        material["file_name"],
                        material["file_type"],
                        material["mime_type"],
                        material["file_size"],
                        material["storage_path"],
                        now,
                    ),
                )
                material_id = int(cursor.lastrowid)
                cursor.execute(
                    """
                    update viral_analysis_job
                    set material_file_id = %s, update_time = %s
                    where tenant_id = %s and user_id = %s and id = %s and status = 'pending'
                    """,
                    (material_id, now, tenant_id, user_id, job_id),
                )
                if cursor.rowcount != 1:
                    raise ViralAnalysisStateError("not_pending")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return {
            "id": material_id,
            "job_id": job_id,
            "file_name": material["file_name"],
            "file_type": material["file_type"],
            "mime_type": material["mime_type"],
            "file_size": material["file_size"],
            "create_time": now,
        }

    def list_for_user(self, tenant_id: int, user_id: int, page: int, page_size: int) -> dict:
        return self._list(
            "where tenant_id = %s and user_id = %s", (tenant_id, user_id), page, page_size
        )

    def list_for_admin(
        self,
        tenant_id: int,
        page: int,
        page_size: int,
        user_id: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        where_sql, params = self._admin_filters(
            tenant_id, user_id, start_time, end_time, status, keyword
        )
        return self._list(where_sql, params, page, page_size)

    def list_for_developer(
        self,
        page: int,
        page_size: int,
        tenant_id: int | None = None,
        status: str | None = None,
    ) -> dict:
        clauses: list[str] = []
        params: list[Any] = []
        if tenant_id is not None:
            clauses.append("tenant_id = %s")
            params.append(tenant_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        where_sql = "where " + " and ".join(clauses) if clauses else ""
        return self._list(where_sql, tuple(params), page, page_size)

    def get_for_user(self, tenant_id: int, user_id: int, job_id: int) -> dict | None:
        return self._get_job("where tenant_id = %s and user_id = %s and id = %s", (tenant_id, user_id, job_id))

    def get_for_admin(self, tenant_id: int, job_id: int) -> dict | None:
        return self._get_job("where tenant_id = %s and id = %s", (tenant_id, job_id))

    def get_for_developer(self, job_id: int) -> dict | None:
        return self._get_job("where id = %s", (job_id,))

    def claim_for_run(self, tenant_id: int, user_id: int, job_id: int) -> tuple[dict, str]:
        now = int(time.time())
        token = uuid.uuid4().hex
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update viral_analysis_job
                    set status = 'failed', processing_token = '', processing_started_time = 0,
                        error_message = 'analysis lease expired', update_time = %s
                    where tenant_id = %s and user_id = %s and id = %s
                      and status = 'processing' and processing_started_time <= %s
                    """,
                    (now, tenant_id, user_id, job_id, now - self.LEASE_SECONDS),
                )
                cursor.execute(
                    """
                    update viral_analysis_job
                    set status = 'processing', processing_token = %s,
                        processing_started_time = %s, error_message = '', update_time = %s
                    where tenant_id = %s and user_id = %s and id = %s
                      and status in ('pending', 'failed')
                    """,
                    (token, now, now, tenant_id, user_id, job_id),
                )
                if cursor.rowcount != 1:
                    self._raise_state_for_user(cursor, tenant_id, user_id, job_id)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        job = self.get_for_user(tenant_id, user_id, job_id)
        if job is None:
            raise ViralAnalysisNotFoundError
        return job, token

    def finalize_success(
        self,
        tenant_id: int,
        user_id: int,
        job_id: int,
        processing_token: str,
        result: ViralAnalysisStructuredResult,
        provider: str,
        model_name: str,
        credit_cost: int,
    ) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update viral_analysis_job
                set status = 'completed', ai_provider = %s, ai_model = %s,
                    credit_cost = %s, error_message = '', processing_token = '',
                    processing_started_time = 0, update_time = %s
                where id = %s and tenant_id = %s and user_id = %s
                  and status = 'processing' and processing_token = %s
                """,
                (provider, model_name, credit_cost, now, job_id, tenant_id, user_id, processing_token),
            )
            if cursor.rowcount != 1:
                self._raise_state_for_user(cursor, tenant_id, user_id, job_id)
            cursor.execute(
                """
                insert into viral_analysis_result (
                    tenant_id, job_id, hook_summary, structure_summary, shot_rhythm,
                    script_breakdown, selling_points, reuse_suggestions, rewritten_script,
                    tags, raw_result_json, create_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    job_id,
                    result.hook_summary,
                    result.structure_summary,
                    result.shot_rhythm,
                    result.script_breakdown,
                    result.selling_points,
                    result.reuse_suggestions,
                    result.rewritten_script,
                    json.dumps(result.tags, ensure_ascii=False),
                    json.dumps(result.model_dump(), ensure_ascii=False),
                    now,
                ),
            )

    def finalize_failure(
        self,
        tenant_id: int,
        user_id: int,
        job_id: int,
        processing_token: str,
        provider: str,
        model_name: str,
        error_message: str,
    ) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update viral_analysis_job
                set status = 'failed', ai_provider = %s, ai_model = %s, credit_cost = 0,
                    error_message = %s, processing_token = '', processing_started_time = 0,
                    update_time = %s
                where id = %s and tenant_id = %s and user_id = %s
                  and status = 'processing' and processing_token = %s
                """,
                (provider, model_name, error_message[:1000], now, job_id, tenant_id, user_id, processing_token),
            )
            if cursor.rowcount != 1:
                self._raise_state_for_user(cursor, tenant_id, user_id, job_id)

    def cancel_for_user(self, tenant_id: int, user_id: int, job_id: int) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update viral_analysis_job
                    set status = 'cancelled', update_time = %s
                    where tenant_id = %s and user_id = %s and id = %s and status = 'pending'
                    """,
                    (now, tenant_id, user_id, job_id),
                )
                if cursor.rowcount != 1:
                    self._raise_state_for_user(cursor, tenant_id, user_id, job_id)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        job = self.get_for_user(tenant_id, user_id, job_id)
        if job is None:
            raise ViralAnalysisNotFoundError
        return job

    def _list(self, where_sql: str, params: tuple, page: int, page_size: int) -> dict:
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute("select count(*) as total from viral_analysis_job " + where_sql, params)
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                self._job_select_sql() + where_sql + " order by create_time desc, id desc limit %s offset %s",
                (*params, page_size, offset),
            )
            items = [self._row_to_job(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def _admin_filters(
        self,
        tenant_id: int,
        user_id: int | None,
        start_time: int | None,
        end_time: int | None,
        status: str | None,
        keyword: str | None,
    ) -> tuple[str, tuple]:
        clauses = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if user_id is not None:
            clauses.append("user_id = %s")
            params.append(user_id)
        if start_time is not None:
            clauses.append("create_time >= %s")
            params.append(start_time)
        if end_time is not None:
            clauses.append("create_time <= %s")
            params.append(end_time)
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        if keyword is not None:
            match = f"%{keyword}%"
            clauses.append(
                """
                (
                    title like %s
                    or supplement_text like %s
                    or exists (
                        select 1
                        from viral_analysis_result
                        where viral_analysis_result.tenant_id = viral_analysis_job.tenant_id
                          and viral_analysis_result.job_id = viral_analysis_job.id
                          and (
                              viral_analysis_result.hook_summary like %s
                              or viral_analysis_result.structure_summary like %s
                              or viral_analysis_result.script_breakdown like %s
                              or viral_analysis_result.selling_points like %s
                              or viral_analysis_result.reuse_suggestions like %s
                              or viral_analysis_result.rewritten_script like %s
                          )
                    )
                )
                """
            )
            params.extend([match] * 8)
        return "where " + " and ".join(clauses), tuple(params)

    def _get_job(self, where_sql: str, params: tuple) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(self._job_select_sql() + where_sql, params)
            row = cursor.fetchone()
        if row is None:
            return None
        job = self._row_to_job(row)
        job["materials"] = self._list_materials(job["id"])
        job["result"] = self._get_result(job["tenant_id"], job["id"])
        return job

    def _require_for_user(self, cursor, tenant_id: int, user_id: int, job_id: int) -> None:
        cursor.execute(
            "select id from viral_analysis_job where tenant_id = %s and user_id = %s and id = %s",
            (tenant_id, user_id, job_id),
        )
        if cursor.fetchone() is None:
            raise ViralAnalysisNotFoundError

    def _raise_state_for_user(self, cursor, tenant_id: int, user_id: int, job_id: int) -> None:
        cursor.execute(
            "select status from viral_analysis_job where tenant_id = %s and user_id = %s and id = %s",
            (tenant_id, user_id, job_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ViralAnalysisNotFoundError
        raise ViralAnalysisStateError(str(row["status"]))

    def _list_materials(self, job_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, job_id, file_name, file_type, mime_type, file_size, create_time
                from viral_analysis_material
                where job_id = %s
                order by id asc
                """,
                (job_id,),
            )
            return list(cursor.fetchall())

    def _get_result(self, tenant_id: int, job_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select hook_summary, structure_summary, shot_rhythm, script_breakdown,
                       selling_points, reuse_suggestions, rewritten_script, tags, create_time
                from viral_analysis_result
                where tenant_id = %s and job_id = %s
                """,
                (tenant_id, job_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        row["tags"] = self._load_json_list(row["tags"])
        return row

    def _job_select_sql(self) -> str:
        return """
            select id, tenant_id, user_id, title, source_type, source_url, material_file_id,
                   analysis_goal, supplement_text, status, ai_provider, ai_model, credit_cost,
                   error_message, create_time, update_time
            from viral_analysis_job
            """

    def _row_to_job(self, row: dict) -> dict:
        return {
            "id": row["id"], "tenant_id": row["tenant_id"], "user_id": row["user_id"],
            "title": row["title"], "source_type": row["source_type"],
            "source_url": row["source_url"], "material_file_id": row["material_file_id"],
            "analysis_goal": self._load_json_list(row["analysis_goal"]),
            "supplement_text": row["supplement_text"], "status": row["status"],
            "ai_provider": row["ai_provider"], "ai_model": row["ai_model"],
            "credit_cost": row["credit_cost"], "error_message": row["error_message"],
            "create_time": row["create_time"], "update_time": row["update_time"],
        }

    def _load_json_list(self, raw: str) -> list:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []
