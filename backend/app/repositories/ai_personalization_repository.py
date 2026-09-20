import time


class AIPersonalizationRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get_for_user(self, tenant_id: int, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, assistant_name, assistant_traits,
                       preferred_address, occupation, user_details,
                       response_preferences, create_time, update_time
                from ai_personalization_profile
                where tenant_id = %s and user_id = %s
                """,
                (tenant_id, user_id),
            )
            return cursor.fetchone()

    def upsert_for_user(
        self,
        tenant_id: int,
        user_id: int,
        values: dict[str, str],
    ) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into ai_personalization_profile (
                        tenant_id, user_id, assistant_name, assistant_traits,
                        preferred_address, occupation, user_details,
                        response_preferences, create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on duplicate key update
                        assistant_name = values(assistant_name),
                        assistant_traits = values(assistant_traits),
                        preferred_address = values(preferred_address),
                        occupation = values(occupation),
                        user_details = values(user_details),
                        response_preferences = values(response_preferences),
                        update_time = values(update_time)
                    """,
                    (
                        tenant_id,
                        user_id,
                        values["assistant_name"],
                        values["assistant_traits"],
                        values["preferred_address"],
                        values["occupation"],
                        values["user_details"],
                        values["response_preferences"],
                        now,
                        now,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        profile = self.get_for_user(tenant_id, user_id)
        if profile is None:
            raise RuntimeError("saved AI personalization profile was not found")
        return profile

    def list_templates_for_user(
        self, tenant_id: int, user_id: int, include_archived: bool = False
    ) -> list[dict]:
        status_sql = "" if include_archived else " and status = 1"
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, template_name, assistant_name,
                       assistant_traits, preferred_address, occupation,
                       user_details, response_preferences, status,
                       create_time, update_time
                from ai_personalization_template
                where tenant_id = %s and user_id = %s
                """
                + status_sql
                + " order by status asc, update_time desc, id desc",
                (tenant_id, user_id),
            )
            return [self._template_from_row(row) for row in cursor.fetchall()]

    def get_template_for_user(
        self,
        tenant_id: int,
        user_id: int,
        template_id: int,
        *,
        include_archived: bool = False,
    ) -> dict | None:
        status_sql = "" if include_archived else " and status = 1"
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, template_name, assistant_name,
                       assistant_traits, preferred_address, occupation,
                       user_details, response_preferences, status,
                       create_time, update_time
                from ai_personalization_template
                where tenant_id = %s and user_id = %s and id = %s
                """
                + status_sql,
                (tenant_id, user_id, template_id),
            )
            row = cursor.fetchone()
        return self._template_from_row(row) if row is not None else None

    def create_template(
        self, tenant_id: int, user_id: int, values: dict[str, str]
    ) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into ai_personalization_template (
                        tenant_id, user_id, template_name, assistant_name,
                        assistant_traits, preferred_address, occupation,
                        user_details, response_preferences, status,
                        create_time, update_time
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
                    """,
                    (
                        tenant_id,
                        user_id,
                        values["template_name"],
                        values["assistant_name"],
                        values["assistant_traits"],
                        values["preferred_address"],
                        values["occupation"],
                        values["user_details"],
                        values["response_preferences"],
                        now,
                        now,
                    ),
                )
                template_id = int(cursor.lastrowid)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        template = self.get_template_for_user(tenant_id, user_id, template_id)
        if template is None:
            raise RuntimeError("created AI personalization template was not found")
        return template

    def update_template(
        self,
        tenant_id: int,
        user_id: int,
        template_id: int,
        values: dict[str, str],
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update ai_personalization_template
                    set template_name = %s, assistant_name = %s,
                        assistant_traits = %s, preferred_address = %s,
                        occupation = %s, user_details = %s,
                        response_preferences = %s, update_time = %s
                    where tenant_id = %s and user_id = %s and id = %s and status = 1
                    """,
                    (
                        values["template_name"],
                        values["assistant_name"],
                        values["assistant_traits"],
                        values["preferred_address"],
                        values["occupation"],
                        values["user_details"],
                        values["response_preferences"],
                        now,
                        tenant_id,
                        user_id,
                        template_id,
                    ),
                )
                updated = cursor.rowcount > 0
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return (
            self.get_template_for_user(tenant_id, user_id, template_id)
            if updated
            else None
        )

    def archive_template(
        self, tenant_id: int, user_id: int, template_id: int
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update ai_personalization_template
                    set status = 2, update_time = %s
                    where tenant_id = %s and user_id = %s and id = %s and status = 1
                    """,
                    (now, tenant_id, user_id, template_id),
                )
                updated = cursor.rowcount > 0
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return (
            self.get_template_for_user(
                tenant_id, user_id, template_id, include_archived=True
            )
            if updated
            else None
        )

    def get_preference_for_user(self, tenant_id: int, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, interaction_mode,
                       personalization_template_id, create_time, update_time
                from ai_chat_preference
                where tenant_id = %s and user_id = %s
                """,
                (tenant_id, user_id),
            )
            return cursor.fetchone()

    def upsert_preference(
        self,
        tenant_id: int,
        user_id: int,
        interaction_mode: str,
        personalization_template_id: int,
    ) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into ai_chat_preference (
                        tenant_id, user_id, interaction_mode,
                        personalization_template_id, create_time, update_time
                    ) values (%s, %s, %s, %s, %s, %s)
                    on duplicate key update
                        interaction_mode = values(interaction_mode),
                        personalization_template_id = values(personalization_template_id),
                        update_time = values(update_time)
                    """,
                    (
                        tenant_id,
                        user_id,
                        interaction_mode,
                        personalization_template_id,
                        now,
                        now,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        preference = self.get_preference_for_user(tenant_id, user_id)
        if preference is None:
            raise RuntimeError("saved AI chat preference was not found")
        return preference

    def migrate_legacy_profile(self, tenant_id: int, user_id: int) -> dict | None:
        templates = self.list_templates_for_user(tenant_id, user_id)
        if templates:
            return templates[0]
        profile = self.get_for_user(tenant_id, user_id)
        if profile is None:
            return None
        return self.create_template(
            tenant_id,
            user_id,
            {
                "template_name": "默认个性化模板",
                "assistant_name": profile["assistant_name"],
                "assistant_traits": profile["assistant_traits"],
                "preferred_address": profile["preferred_address"],
                "occupation": profile["occupation"],
                "user_details": profile["user_details"],
                "response_preferences": profile["response_preferences"],
            },
        )

    def _template_from_row(self, row: dict) -> dict:
        return {**row, "status": "active" if int(row["status"]) == 1 else "archived"}
