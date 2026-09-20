import json
import time
import uuid
from typing import Any

from app.schemas.inspiration import InspirationSessionCreate


class InspirationSessionNotFoundError(LookupError):
    pass


class InspirationRequestConflictError(ValueError):
    pass


class InspirationSessionStateError(ValueError):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"inspiration session is {status}")


class InspirationRepository:
    GENERATION_LEASE_SECONDS = 5 * 60

    def __init__(self, conn) -> None:
        self.conn = conn

    def create_session(
        self, tenant_id: int, user_id: int, payload: InspirationSessionCreate
    ) -> dict:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into inspiration_session (
                    tenant_id, user_id, title, linked_product_id,
                    linked_xhs_account_id, interaction_mode,
                    personalization_template_id, goal_type, tone, extra_requirement,
                    create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    user_id,
                    payload.title,
                    payload.linked_product_id,
                    payload.linked_xhs_account_id,
                    payload.interaction_mode,
                    payload.personalization_template_id,
                    payload.goal_type,
                    payload.tone,
                    payload.extra_requirement,
                    now,
                    now,
                ),
            )
            session_id = int(cursor.lastrowid)
        self.conn.commit()
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise RuntimeError("created inspiration session was not found")
        return session

    def list_sessions_for_user(
        self,
        tenant_id: int,
        user_id: int,
        page: int,
        page_size: int,
        interaction_mode: str | None = None,
        personalization_template_id: int | None = None,
    ) -> dict:
        offset = (page - 1) * page_size
        filters = ["tenant_id = %s", "user_id = %s"]
        params: list[Any] = [tenant_id, user_id]
        if interaction_mode is not None:
            filters.append("interaction_mode = %s")
            params.append(interaction_mode)
        if personalization_template_id is not None:
            filters.append("personalization_template_id = %s")
            params.append(personalization_template_id)
        where_sql = "where " + " and ".join(filters)
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select count(*) as total from inspiration_session " + where_sql,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                self._session_select_sql()
                + where_sql
                + """
                order by is_pinned desc, pinned_time desc, update_time desc, id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._session_from_row(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def list_sessions_for_admin(
        self,
        tenant_id: int,
        page: int,
        page_size: int,
        user_id: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        product_id: int | None = None,
        keyword: str | None = None,
    ) -> dict:
        offset = (page - 1) * page_size
        where_sql, filter_params = self._admin_filter_sql(
            tenant_id,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            product_id=product_id,
            keyword=keyword,
        )
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select count(*) as total from inspiration_session " + where_sql,
                filter_params,
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                self._session_select_sql()
                + where_sql
                + """
                order by update_time desc, id desc
                limit %s offset %s
                """,
                (*filter_params, page_size, offset),
            )
            items = [self._session_from_row(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_session_for_user(
        self, tenant_id: int, user_id: int, session_id: int
    ) -> dict | None:
        return self._get_session_for_user(tenant_id, user_id, session_id)

    def _get_session_for_user(
        self, tenant_id: int, user_id: int, session_id: int, lock: bool = False
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._session_select_sql()
                + "where tenant_id = %s and user_id = %s and id = %s"
                + (" for update" if lock else ""),
                (tenant_id, user_id, session_id),
            )
            row = cursor.fetchone()
        return self._session_from_row(row) if row is not None else None

    def get_session_for_admin(self, tenant_id: int, session_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._session_select_sql() + "where tenant_id = %s and id = %s",
                (tenant_id, session_id),
            )
            row = cursor.fetchone()
        return self._session_from_row(row) if row is not None else None

    def create_attachment(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        *,
        file_name: str,
        mime_type: str,
        file_size: int,
        storage_path: str,
    ) -> dict:
        if self.get_session_for_user(tenant_id, user_id, session_id) is None:
            raise InspirationSessionNotFoundError
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into inspiration_attachment (
                    tenant_id, user_id, session_id, message_id, file_name,
                    mime_type, file_size, storage_path, status,
                    create_time, update_time
                ) values (%s, %s, %s, 0, %s, %s, %s, %s, 'pending', %s, %s)
                """,
                (
                    tenant_id,
                    user_id,
                    session_id,
                    file_name,
                    mime_type,
                    file_size,
                    storage_path,
                    now,
                    now,
                ),
            )
            attachment_id = int(cursor.lastrowid)
        self.conn.commit()
        attachment = self.get_attachment_for_user(tenant_id, user_id, attachment_id)
        if attachment is None:
            raise RuntimeError("created inspiration attachment was not found")
        return attachment

    def get_attachment_for_user(
        self, tenant_id: int, user_id: int, attachment_id: int
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, session_id, message_id, file_name,
                       mime_type, file_size, storage_path, status,
                       create_time, update_time
                from inspiration_attachment
                where tenant_id = %s and user_id = %s and id = %s
                """,
                (tenant_id, user_id, attachment_id),
            )
            row = cursor.fetchone()
        return self._attachment_from_row(row) if row is not None else None

    def claim_and_store_user_message(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        content: str,
        context: dict,
        client_request_id: str,
        attachment_ids: list[int] | None = None,
        revision_source_message_id: int = 0,
        retained_attachment_ids: list[int] | None = None,
    ) -> tuple[dict, dict, str, dict | None]:
        now = int(time.time())
        generation_token = uuid.uuid4().hex
        created_message_id = 0
        user_message: dict | None = None
        assistant_message: dict | None = None
        normalized_attachment_ids = sorted(set(attachment_ids or []))
        normalized_retained_ids = sorted(set(retained_attachment_ids or []))
        parent_message_id = 0
        revision_root_message_id = 0
        with self.conn.cursor() as cursor:
            self._recover_expired_generation(
                cursor, tenant_id, user_id, session_id, now
            )
            current = self._get_session_for_user(
                tenant_id, user_id, session_id, lock=True
            )
            if current is None:
                raise InspirationSessionNotFoundError
            branch_messages = self._list_messages_with_cursor(
                cursor,
                "where tenant_id = %s and user_id = %s and session_id = %s",
                (tenant_id, user_id, session_id),
            )
            effective_parents = self._effective_parent_ids(branch_messages)
            if revision_source_message_id > 0:
                source_message = next(
                    (
                        message
                        for message in branch_messages
                        if int(message["id"]) == revision_source_message_id
                        and message["role"] == "user"
                    ),
                    None,
                )
                if source_message is None:
                    raise InspirationSessionNotFoundError
                parent_message_id = effective_parents.get(
                    revision_source_message_id, 0
                )
                revision_root_message_id = int(
                    source_message.get("revision_root_message_id", 0)
                    or source_message["id"]
                )
            else:
                active_leaf_message_id = int(
                    current.get("active_leaf_message_id", 0) or 0
                )
                if active_leaf_message_id not in {
                    int(message["id"]) for message in branch_messages
                }:
                    active_leaf_message_id = max(
                        (int(message["id"]) for message in branch_messages),
                        default=0,
                    )
                parent_message_id = active_leaf_message_id
            request_messages = self._get_request_messages(
                cursor,
                tenant_id,
                user_id,
                session_id,
                client_request_id,
            )
            user_message = next(
                (message for message in request_messages if message["role"] == "user"),
                None,
            )
            assistant_message = next(
                (
                    message
                    for message in request_messages
                    if message["role"] == "assistant"
                ),
                None,
            )
            if user_message is not None and user_message["content"] != content:
                raise InspirationRequestConflictError
            if (
                user_message is not None
                and int(user_message.get("revision_source_message_id", 0) or 0)
                != int(revision_source_message_id or 0)
            ):
                raise InspirationRequestConflictError
            if user_message is not None and revision_source_message_id <= 0:
                stored_attachment_ids = self._message_attachment_ids(
                    cursor, tenant_id, user_id, user_message["id"]
                )
                if stored_attachment_ids != normalized_attachment_ids:
                    raise InspirationRequestConflictError
            if user_message is not None and assistant_message is not None:
                for message in (user_message, assistant_message):
                    message["attachments"] = self._list_attachments_for_message(
                        tenant_id, int(message["id"])
                    )
                self._apply_revision_metadata(
                    [user_message, assistant_message], branch_messages
                )
                return current, user_message, "", assistant_message
            if current["status"] != "active":
                raise InspirationSessionStateError(current["status"])
            cursor.execute(
                """
                update inspiration_session
                set status = 'generating', generation_token = %s,
                    generation_started_time = %s, update_time = %s
                where tenant_id = %s and user_id = %s and id = %s and status = 'active'
                """,
                (generation_token, now, now, tenant_id, user_id, session_id),
            )
            if cursor.rowcount != 1:
                latest = self._get_session_for_user(
                    tenant_id, user_id, session_id, lock=True
                )
                raise InspirationSessionStateError(
                    latest["status"] if latest is not None else "archived"
                )
            if user_message is None:
                if normalized_retained_ids:
                    if revision_source_message_id <= 0:
                        raise InspirationRequestConflictError
                    placeholders = ",".join(["%s"] * len(normalized_retained_ids))
                    cursor.execute(
                        f"""
                        select id
                        from inspiration_attachment
                        where tenant_id = %s and user_id = %s and session_id = %s
                          and message_id = %s and status = 'attached'
                          and id in ({placeholders})
                        for update
                        """,
                        (
                            tenant_id,
                            user_id,
                            session_id,
                            revision_source_message_id,
                            *normalized_retained_ids,
                        ),
                    )
                    owned_retained_ids = {
                        int(row["id"]) for row in cursor.fetchall()
                    }
                    if owned_retained_ids != set(normalized_retained_ids):
                        raise InspirationRequestConflictError
                if normalized_attachment_ids:
                    placeholders = ",".join(["%s"] * len(normalized_attachment_ids))
                    cursor.execute(
                        f"""
                        select id
                        from inspiration_attachment
                        where tenant_id = %s and user_id = %s and session_id = %s
                          and status = 'pending' and message_id = 0
                          and id in ({placeholders})
                        for update
                        """,
                        (tenant_id, user_id, session_id, *normalized_attachment_ids),
                    )
                    owned_ids = {int(row["id"]) for row in cursor.fetchall()}
                    if owned_ids != set(normalized_attachment_ids):
                        raise InspirationRequestConflictError
                cursor.execute(
                    """
                    insert into inspiration_message (
                        tenant_id, session_id, user_id, client_request_id,
                        parent_message_id, revision_root_message_id,
                        revision_source_message_id, role,
                        content, context_json, ai_provider, ai_model, credit_cost,
                        latency_ms, status, error_message, create_time
                    )
                    values (
                        %s, %s, %s, %s, %s, %s, %s, 'user', %s, %s, '', '', 0, 0,
                        'success', '', %s
                    )
                    """,
                    (
                        tenant_id,
                        session_id,
                        user_id,
                        client_request_id,
                        parent_message_id,
                        revision_root_message_id,
                        revision_source_message_id,
                        content,
                        self._dump_json(context),
                        now,
                    ),
                )
                created_message_id = int(cursor.lastrowid)
                if normalized_retained_ids:
                    placeholders = ",".join(["%s"] * len(normalized_retained_ids))
                    cursor.execute(
                        f"""
                        insert into inspiration_attachment (
                            tenant_id, user_id, session_id, message_id, file_name,
                            mime_type, file_size, storage_path, status,
                            create_time, update_time
                        )
                        select tenant_id, user_id, session_id, %s, file_name,
                               mime_type, file_size, storage_path, 'attached', %s, %s
                        from inspiration_attachment
                        where tenant_id = %s and user_id = %s and session_id = %s
                          and message_id = %s and status = 'attached'
                          and id in ({placeholders})
                        """,
                        (
                            created_message_id,
                            now,
                            now,
                            tenant_id,
                            user_id,
                            session_id,
                            revision_source_message_id,
                            *normalized_retained_ids,
                        ),
                    )
                    if cursor.rowcount != len(normalized_retained_ids):
                        raise InspirationRequestConflictError
                if normalized_attachment_ids:
                    placeholders = ",".join(["%s"] * len(normalized_attachment_ids))
                    cursor.execute(
                        f"""
                        update inspiration_attachment
                        set message_id = %s, status = 'attached', update_time = %s
                        where tenant_id = %s and user_id = %s and session_id = %s
                          and status = 'pending' and message_id = 0
                          and id in ({placeholders})
                        """,
                        (
                            created_message_id,
                            now,
                            tenant_id,
                            user_id,
                            session_id,
                            *normalized_attachment_ids,
                        ),
                    )
                    if cursor.rowcount != len(normalized_attachment_ids):
                        raise InspirationRequestConflictError
                cursor.execute(
                    """
                    update inspiration_session
                    set message_count = message_count + 1
                    where tenant_id = %s and user_id = %s and id = %s
                      and status = 'generating' and generation_token = %s
                    """,
                    (tenant_id, user_id, session_id, generation_token),
                )
        if user_message is None and created_message_id > 0:
            user_message = self.get_message_for_user(
                tenant_id, user_id, created_message_id
            )
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise InspirationSessionNotFoundError
        if user_message is None:
            raise RuntimeError("claimed inspiration user message was not found")
        return session, user_message, generation_token, None

    def finalize_generation(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        content: str,
        context: dict,
        ai_provider: str,
        ai_model: str,
        generation_token: str,
        credit_cost: int,
        latency_ms: int,
        status: str,
        error_message: str = "",
        client_request_id: str = "",
        parent_message_id: int = 0,
        activate_branch: bool = True,
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into inspiration_message (
                    tenant_id, session_id, user_id, client_request_id,
                    parent_message_id, role,
                    content, context_json, ai_provider, ai_model, credit_cost,
                    latency_ms, status, error_message, create_time
                )
                values (
                    %s, %s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    tenant_id,
                    session_id,
                    user_id,
                    client_request_id,
                    parent_message_id,
                    content,
                    self._dump_json(context),
                    ai_provider,
                    ai_model,
                    credit_cost,
                    latency_ms,
                    status,
                    error_message,
                    now,
                ),
            )
            message_id = int(cursor.lastrowid)
            cursor.execute(
                """
                update inspiration_session
                set status = 'active',
                    generation_token = '',
                    generation_started_time = 0,
                    active_leaf_message_id = case
                        when %s = 1 then %s else active_leaf_message_id
                    end,
                    message_count = message_count + 1,
                    total_credit_cost = total_credit_cost + %s,
                    update_time = %s
                where tenant_id = %s and user_id = %s and id = %s
                  and status = 'generating' and generation_token = %s
                """,
                (
                    1 if activate_branch else 0,
                    message_id,
                    credit_cost,
                    now,
                    tenant_id,
                    user_id,
                    session_id,
                    generation_token,
                ),
            )
            if cursor.rowcount != 1:
                current = self._get_session_for_user(
                    tenant_id, user_id, session_id, lock=True
                )
                raise InspirationSessionStateError(
                    current["status"] if current is not None else "archived"
                )
        return message_id

    def archive_active_session(
        self, tenant_id: int, user_id: int, session_id: int
    ) -> dict:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            self._recover_expired_generation(
                cursor, tenant_id, user_id, session_id, now
            )
            session = self._get_session_for_user(
                tenant_id, user_id, session_id, lock=True
            )
            if session is None:
                raise InspirationSessionNotFoundError
            if session["status"] != "active":
                raise InspirationSessionStateError(session["status"])
            cursor.execute(
                """
                update inspiration_session
                set status = 'archived', generation_token = '',
                    generation_started_time = 0, update_time = %s
                where tenant_id = %s and user_id = %s and id = %s and status = 'active'
                """,
                (now, tenant_id, user_id, session_id),
            )
            if cursor.rowcount != 1:
                raise InspirationSessionStateError("generating")
        self.conn.commit()
        session["status"] = "archived"
        session["update_time"] = now
        return session

    def set_session_pinned(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        is_pinned: bool,
    ) -> dict:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update inspiration_session
                set is_pinned = %s, pinned_time = %s
                where tenant_id = %s and user_id = %s and id = %s
                """,
                (
                    1 if is_pinned else 0,
                    now if is_pinned else 0,
                    tenant_id,
                    user_id,
                    session_id,
                ),
            )
            if cursor.rowcount != 1:
                cursor.execute(
                    """
                    select id
                    from inspiration_session
                    where tenant_id = %s and user_id = %s and id = %s
                    """,
                    (tenant_id, user_id, session_id),
                )
                if cursor.fetchone() is None:
                    self.conn.rollback()
                    raise InspirationSessionNotFoundError
        self.conn.commit()
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise InspirationSessionNotFoundError
        return session

    def rename_session(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        title: str,
    ) -> dict:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update inspiration_session
                set title = %s, update_time = %s
                where tenant_id = %s and user_id = %s and id = %s
                """,
                (title, now, tenant_id, user_id, session_id),
            )
            if cursor.rowcount != 1:
                cursor.execute(
                    """
                    select id
                    from inspiration_session
                    where tenant_id = %s and user_id = %s and id = %s
                    """,
                    (tenant_id, user_id, session_id),
                )
                if cursor.fetchone() is None:
                    self.conn.rollback()
                    raise InspirationSessionNotFoundError
        self.conn.commit()
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise InspirationSessionNotFoundError
        return session

    def delete_session(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
    ) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            self._recover_expired_generation(
                cursor, tenant_id, user_id, session_id, now
            )
            session = self._get_session_for_user(
                tenant_id, user_id, session_id, lock=True
            )
            if session is None:
                raise InspirationSessionNotFoundError
            if session["status"] == "generating":
                raise InspirationSessionStateError("generating")
            cursor.execute(
                """
                delete from content_draft_source
                where tenant_id = %s and user_id = %s
                  and source_type = 'inspiration'
                  and source_id in (
                      select id
                      from inspiration_message
                      where tenant_id = %s and user_id = %s and session_id = %s
                  )
                """,
                (tenant_id, user_id, tenant_id, user_id, session_id),
            )
            cursor.execute(
                """
                delete from inspiration_message
                where tenant_id = %s and user_id = %s and session_id = %s
                """,
                (tenant_id, user_id, session_id),
            )
            cursor.execute(
                """
                delete from inspiration_session
                where tenant_id = %s and user_id = %s and id = %s
                """,
                (tenant_id, user_id, session_id),
            )
            if cursor.rowcount != 1:
                self.conn.rollback()
                raise InspirationSessionNotFoundError
        self.conn.commit()

    def list_messages_for_user(
        self, tenant_id: int, user_id: int, session_id: int
    ) -> list[dict]:
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            return []
        messages = self._list_messages(
            "where tenant_id = %s and user_id = %s and session_id = %s",
            (tenant_id, user_id, session_id),
        )
        return self._active_branch_with_metadata(
            messages, int(session.get("active_leaf_message_id", 0) or 0)
        )

    def list_messages_for_admin(self, tenant_id: int, session_id: int) -> list[dict]:
        session = self.get_session_for_admin(tenant_id, session_id)
        if session is None:
            return []
        messages = self._list_messages(
            "where tenant_id = %s and session_id = %s", (tenant_id, session_id)
        )
        return self._active_branch_with_metadata(
            messages, int(session.get("active_leaf_message_id", 0) or 0)
        )

    def list_successful_history(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        excluded_message_id: int,
    ) -> list[tuple[str, str]]:
        with self.conn.cursor() as cursor:
            messages = self._list_messages_with_cursor(
                cursor,
                "where tenant_id = %s and user_id = %s and session_id = %s",
                (tenant_id, user_id, session_id),
            )
        active_messages = self._active_branch(messages, excluded_message_id)
        history = [
            (message["role"], message["content"])
            for message in active_messages
            if int(message["id"]) != excluded_message_id
            and message["status"] == "success"
        ]
        return history[-20:]

    def activate_message_branch(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        message_id: int,
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            self._recover_expired_generation(
                cursor, tenant_id, user_id, session_id, now
            )
            session = self._get_session_for_user(
                tenant_id, user_id, session_id, lock=True
            )
            if session is None:
                raise InspirationSessionNotFoundError
            if session["status"] == "generating":
                raise InspirationSessionStateError("generating")
            messages = self._list_messages_with_cursor(
                cursor,
                "where tenant_id = %s and user_id = %s and session_id = %s",
                (tenant_id, user_id, session_id),
            )
            target = next(
                (
                    message
                    for message in messages
                    if int(message["id"]) == message_id and message["role"] == "user"
                ),
                None,
            )
            if target is None:
                raise InspirationSessionNotFoundError
            effective_parents = self._effective_parent_ids(messages)
            children: dict[int, list[int]] = {}
            for child_id, parent_id in effective_parents.items():
                children.setdefault(parent_id, []).append(child_id)
            descendants = {message_id}
            pending = [message_id]
            while pending:
                parent_id = pending.pop()
                for child_id in children.get(parent_id, []):
                    if child_id not in descendants:
                        descendants.add(child_id)
                        pending.append(child_id)
            active_leaf_message_id = max(descendants)
            cursor.execute(
                """
                update inspiration_session
                set active_leaf_message_id = %s, update_time = %s
                where tenant_id = %s and user_id = %s and id = %s
                """,
                (
                    active_leaf_message_id,
                    now,
                    tenant_id,
                    user_id,
                    session_id,
                ),
            )
            if cursor.rowcount != 1:
                raise InspirationSessionNotFoundError
        self.conn.commit()
        return active_leaf_message_id

    def get_message_for_user(
        self, tenant_id: int, user_id: int, message_id: int
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._message_select_sql()
                + "where tenant_id = %s and user_id = %s and id = %s",
                (tenant_id, user_id, message_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        message = self._message_from_row(row)
        message["attachments"] = self._list_attachments_for_message(
            tenant_id, message_id
        )
        with self.conn.cursor() as cursor:
            session_messages = self._list_messages_with_cursor(
                cursor,
                "where tenant_id = %s and user_id = %s and session_id = %s",
                (tenant_id, user_id, int(message["session_id"])),
            )
        self._apply_revision_metadata([message], session_messages)
        return message

    def _list_messages(self, where_sql: str, params: tuple) -> list[dict]:
        with self.conn.cursor() as cursor:
            messages = self._list_messages_with_cursor(cursor, where_sql, params)
        for message in messages:
            message["attachments"] = self._list_attachments_for_message(
                int(message["tenant_id"]), int(message["id"])
            )
        return messages

    def _list_messages_with_cursor(
        self, cursor, where_sql: str, params: tuple
    ) -> list[dict]:
        cursor.execute(
            self._message_select_sql() + where_sql + " order by id asc", params
        )
        return [self._message_from_row(row) for row in cursor.fetchall()]

    @staticmethod
    def _effective_parent_ids(messages: list[dict]) -> dict[int, int]:
        effective_parents: dict[int, int] = {}
        last_legacy_message_id = 0
        for message in sorted(messages, key=lambda item: int(item["id"])):
            message_id = int(message["id"])
            parent_message_id = int(message.get("parent_message_id", 0) or 0)
            revision_root_message_id = int(
                message.get("revision_root_message_id", 0) or 0
            )
            if parent_message_id <= 0 and revision_root_message_id <= 0:
                parent_message_id = last_legacy_message_id
                last_legacy_message_id = message_id
            effective_parents[message_id] = parent_message_id
        return effective_parents

    @classmethod
    def _active_branch(
        cls, messages: list[dict], active_leaf_message_id: int
    ) -> list[dict]:
        if not messages:
            return []
        by_id = {int(message["id"]): message for message in messages}
        if active_leaf_message_id not in by_id:
            active_leaf_message_id = max(by_id)
        effective_parents = cls._effective_parent_ids(messages)
        active_messages: list[dict] = []
        seen: set[int] = set()
        current_id = active_leaf_message_id
        while current_id > 0 and current_id in by_id and current_id not in seen:
            seen.add(current_id)
            active_messages.append(by_id[current_id])
            current_id = effective_parents.get(current_id, 0)
        active_messages.reverse()
        return active_messages

    @classmethod
    def _active_branch_with_metadata(
        cls, messages: list[dict], active_leaf_message_id: int
    ) -> list[dict]:
        active_messages = cls._active_branch(messages, active_leaf_message_id)
        cls._apply_revision_metadata(active_messages, messages)
        return active_messages

    @staticmethod
    def _apply_revision_metadata(
        target_messages: list[dict], all_messages: list[dict]
    ) -> None:
        revision_groups: dict[int, list[int]] = {}
        for message in all_messages:
            if message["role"] != "user":
                continue
            message_id = int(message["id"])
            revision_root_message_id = int(
                message.get("revision_root_message_id", 0) or message_id
            )
            revision_groups.setdefault(revision_root_message_id, []).append(message_id)
        for group in revision_groups.values():
            group.sort()
        for message in target_messages:
            message["revision_index"] = 1
            message["revision_count"] = 1
            if message["role"] != "user":
                continue
            message_id = int(message["id"])
            revision_root_message_id = int(
                message.get("revision_root_message_id", 0) or message_id
            )
            variants = revision_groups.get(revision_root_message_id, [message_id])
            message["revision_root_message_id"] = revision_root_message_id
            message["revision_index"] = variants.index(message_id) + 1
            message["revision_count"] = len(variants)
            message["revision_message_ids"] = list(variants)

    def _list_attachments_for_message(
        self, tenant_id: int, message_id: int
    ) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, session_id, message_id, file_name,
                       mime_type, file_size, storage_path, status,
                       create_time, update_time
                from inspiration_attachment
                where tenant_id = %s and message_id = %s and status = 'attached'
                order by id asc
                """,
                (tenant_id, message_id),
            )
            return [self._attachment_from_row(row) for row in cursor.fetchall()]

    def _message_attachment_ids(
        self, cursor, tenant_id: int, user_id: int, message_id: int
    ) -> list[int]:
        cursor.execute(
            """
            select id
            from inspiration_attachment
            where tenant_id = %s and user_id = %s and message_id = %s
              and status = 'attached'
            order by id asc
            """,
            (tenant_id, user_id, message_id),
        )
        return [int(row["id"]) for row in cursor.fetchall()]

    @staticmethod
    def _attachment_from_row(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "tenant_id": int(row["tenant_id"]),
            "user_id": int(row["user_id"]),
            "session_id": int(row["session_id"]),
            "message_id": int(row["message_id"]),
            "file_name": row["file_name"],
            "mime_type": row["mime_type"],
            "file_size": int(row["file_size"]),
            "storage_path": row["storage_path"],
            "status": row["status"],
            "create_time": int(row["create_time"]),
            "update_time": int(row["update_time"]),
        }

    def _session_select_sql(self) -> str:
        return """
            select id, tenant_id, user_id, title, linked_product_id,
                   linked_xhs_account_id, interaction_mode,
                   personalization_template_id, goal_type, tone, extra_requirement,
                   generation_token, generation_started_time,
                   active_leaf_message_id, status, message_count,
                   is_pinned, pinned_time, total_credit_cost, create_time, update_time
            from inspiration_session
            """

    def _message_select_sql(self) -> str:
        return """
            select id, tenant_id, session_id, user_id, client_request_id, role,
                   parent_message_id, revision_root_message_id,
                   revision_source_message_id, content, context_json,
                   ai_provider, ai_model, credit_cost,
                   latency_ms, status, error_message, create_time,
                   coalesce((
                       select source.content_draft_id
                       from content_draft_source as source
                       where source.tenant_id = inspiration_message.tenant_id
                         and source.user_id = inspiration_message.user_id
                         and source.source_type = 'inspiration'
                         and source.source_id = inspiration_message.id
                       limit 1
                   ), 0) as content_draft_id,
                   coalesce((
                       select collection.id
                       from content_collection as collection
                       where collection.tenant_id = inspiration_message.tenant_id
                         and collection.user_id = inspiration_message.user_id
                         and collection.source_type = 'inspiration'
                         and collection.source_id = inspiration_message.id
                       limit 1
                   ), 0) as content_collection_id
            from inspiration_message
            """

    def _session_from_row(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "linked_product_id": row["linked_product_id"],
            "linked_xhs_account_id": row["linked_xhs_account_id"],
            "interaction_mode": row.get("interaction_mode", "personalized"),
            "personalization_template_id": int(
                row.get("personalization_template_id", 0) or 0
            ),
            "goal_type": row["goal_type"],
            "tone": row["tone"],
            "extra_requirement": row["extra_requirement"],
            "generation_token": row["generation_token"],
            "generation_started_time": row["generation_started_time"],
            "active_leaf_message_id": int(row.get("active_leaf_message_id", 0) or 0),
            "status": row["status"],
            "is_pinned": bool(row["is_pinned"]),
            "pinned_time": row["pinned_time"],
            "message_count": row["message_count"],
            "total_credit_cost": row["total_credit_cost"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _message_from_row(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "client_request_id": row["client_request_id"],
            "parent_message_id": int(row.get("parent_message_id", 0) or 0),
            "revision_root_message_id": int(
                row.get("revision_root_message_id", 0) or 0
            ),
            "revision_source_message_id": int(
                row.get("revision_source_message_id", 0) or 0
            ),
            "role": row["role"],
            "content": row["content"],
            "context": self._load_json(row["context_json"]),
            "ai_provider": row["ai_provider"],
            "ai_model": row["ai_model"],
            "credit_cost": row["credit_cost"],
            "latency_ms": row["latency_ms"],
            "status": row["status"],
            "error_message": row["error_message"],
            "content_draft_id": int(row["content_draft_id"] or 0),
            "content_collection_id": int(row.get("content_collection_id", 0) or 0),
            "create_time": row["create_time"],
            "attachments": [],
        }

    def _admin_filter_sql(
        self,
        tenant_id: int,
        user_id: int | None,
        start_time: int | None,
        end_time: int | None,
        product_id: int | None,
        keyword: str | None,
    ) -> tuple[str, tuple[Any, ...]]:
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
        if product_id is not None:
            clauses.append("linked_product_id = %s")
            params.append(product_id)
        if keyword:
            keyword_like = f"%{keyword}%"
            clauses.append(
                """(
                    title like %s
                    or extra_requirement like %s
                    or exists (
                        select 1
                        from inspiration_message
                        where inspiration_message.tenant_id = %s
                          and inspiration_message.session_id = inspiration_session.id
                          and inspiration_message.content like %s
                    )
                )"""
            )
            params.extend((keyword_like, keyword_like, tenant_id, keyword_like))
        return " where " + " and ".join(clauses), tuple(params)

    def _dump_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _get_request_messages(
        self,
        cursor,
        tenant_id: int,
        user_id: int,
        session_id: int,
        client_request_id: str,
    ) -> list[dict]:
        cursor.execute(
            self._message_select_sql()
            + """
            where tenant_id = %s and user_id = %s and session_id = %s
              and client_request_id = %s
            order by id asc
            """,
            (tenant_id, user_id, session_id, client_request_id),
        )
        return [self._message_from_row(row) for row in cursor.fetchall()]

    def _recover_expired_generation(
        self, cursor, tenant_id: int, user_id: int, session_id: int, now: int
    ) -> None:
        cursor.execute(
            """
            update inspiration_session
            set status = 'active', generation_token = '', generation_started_time = 0,
                update_time = %s
            where tenant_id = %s and user_id = %s and id = %s
              and status = 'generating'
              and (generation_started_time = 0 or generation_started_time <= %s)
            """,
            (now, tenant_id, user_id, session_id, now - self.GENERATION_LEASE_SECONDS),
        )

    def _load_json(self, raw_value: str) -> dict:
        try:
            value = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}
