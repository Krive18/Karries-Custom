import time

from app.schemas.xhs_account import XHSAccountCreate, XHSAccountProfile


PROFILE_FIELDS = (
    "domain_name",
    "persona",
    "target_audience",
    "content_style",
    "tone",
    "common_phrases",
    "forbidden_phrases",
    "tag_preferences",
    "word_count_preference",
    "topic_preferences",
)


class XHSAccountRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, user_id: int, payload: XHSAccountCreate) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into xhs_account (
                        user_id, display_name, account_group, status, daily_limit,
                        min_interval_minutes, last_publish_time, today_publish_count,
                        login_state_path, create_time, update_time
                    )
                    values (%s, %s, %s, 2, %s, %s, 0, 0, '', %s, %s)
                    """,
                    (
                        user_id,
                        payload.display_name,
                        payload.account_group,
                        payload.daily_limit,
                        payload.min_interval_minutes,
                        now,
                        now,
                    ),
                )
                account_id = int(cursor.lastrowid)
                self._insert_profile(cursor, account_id, payload.profile, now)
            self.conn.commit()
            return account_id
        except Exception:
            self.conn.rollback()
            raise

    def list_by_user(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + """
                where a.user_id = %s and a.status <> 5
                order by a.id desc
                """,
                (user_id,),
            )
            return [self._row_to_account(row) for row in cursor.fetchall()]

    def get_for_user(self, user_id: int, account_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + """
                where a.user_id = %s and a.id = %s and a.status <> 5
                """,
                (user_id, account_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_account(row)

    def update(self, user_id: int, account_id: int, payload: XHSAccountCreate) -> bool:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update xhs_account
                    set display_name = %s,
                        account_group = %s,
                        daily_limit = %s,
                        min_interval_minutes = %s,
                        update_time = %s
                    where id = %s and user_id = %s and status <> 5
                    """,
                    (
                        payload.display_name,
                        payload.account_group,
                        payload.daily_limit,
                        payload.min_interval_minutes,
                        now,
                        account_id,
                        user_id,
                    ),
                )

                cursor.execute(
                    "select id from xhs_account_profile where xhs_account_id = %s",
                    (account_id,),
                )
                if cursor.fetchone() is None:
                    self._insert_profile(cursor, account_id, payload.profile, now)
                else:
                    values = payload.profile.model_dump()
                    cursor.execute(
                        """
                        update xhs_account_profile
                        set domain_name = %s,
                            persona = %s,
                            target_audience = %s,
                            content_style = %s,
                            tone = %s,
                            common_phrases = %s,
                            forbidden_phrases = %s,
                            tag_preferences = %s,
                            word_count_preference = %s,
                            topic_preferences = %s,
                            update_time = %s
                        where xhs_account_id = %s
                        """,
                        tuple(values[field] for field in PROFILE_FIELDS) + (now, account_id),
                    )
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def delete(self, user_id: int, account_id: int) -> str:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id
                    from xhs_account
                    where id = %s and user_id = %s and status <> 5
                    """,
                    (account_id, user_id),
                )
                if cursor.fetchone() is None:
                    return "not_found"

                cursor.execute(
                    """
                    select count(*) as active_count
                    from matrix_publish_item
                    where xhs_account_id = %s and user_id = %s
                      and status in (1, 2, 3, 6)
                    """,
                    (account_id, user_id),
                )
                matrix_count = int(cursor.fetchone()["active_count"])
                cursor.execute(
                    """
                    select count(*) as active_count
                    from video_edit_job
                    where xhs_account_id = %s and user_id = %s
                      and status in (1, 2, 3, 4)
                    """,
                    (account_id, user_id),
                )
                video_count = int(cursor.fetchone()["active_count"])
                if matrix_count + video_count > 0:
                    return "in_use"

                cursor.execute(
                    """
                    update xhs_account
                    set status = 5,
                        login_state_path = '',
                        update_time = %s
                    where id = %s and user_id = %s and status <> 5
                    """,
                    (now, account_id, user_id),
                )
                cursor.execute(
                    """
                    update xhs_account_login_session
                    set status = 'cancelled',
                        message = '账号已删除',
                        update_time = %s
                    where xhs_account_id = %s and user_id = %s
                      and status in ('starting', 'awaiting_scan')
                    """,
                    (now, account_id, user_id),
                )
            self.conn.commit()
            return "deleted"
        except Exception:
            self.conn.rollback()
            raise

    def update_profile(self, user_id: int, account_id: int, profile: XHSAccountProfile) -> bool:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select id from xhs_account where id = %s and user_id = %s and status <> 5",
                    (account_id, user_id),
                )
                if cursor.fetchone() is None:
                    return False

                cursor.execute(
                    "select id from xhs_account_profile where xhs_account_id = %s",
                    (account_id,),
                )
                existing_profile = cursor.fetchone()
                if existing_profile is None:
                    self._insert_profile(cursor, account_id, profile, now)
                else:
                    values = profile.model_dump()
                    cursor.execute(
                        """
                        update xhs_account_profile
                        set domain_name = %s,
                            persona = %s,
                            target_audience = %s,
                            content_style = %s,
                            tone = %s,
                            common_phrases = %s,
                            forbidden_phrases = %s,
                            tag_preferences = %s,
                            word_count_preference = %s,
                            topic_preferences = %s,
                            update_time = %s
                        where xhs_account_id = %s
                        """,
                        tuple(values[field] for field in PROFILE_FIELDS) + (now, account_id),
                    )
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def update_login_state(
        self,
        user_id: int,
        account_id: int,
        *,
        status: int,
        login_state_path: str | None = None,
    ) -> bool:
        now = int(time.time())
        assignments = ["status = %s", "update_time = %s"]
        values: list[object] = [status, now]
        if login_state_path is not None:
            assignments.append("login_state_path = %s")
            values.append(login_state_path)
        values.extend((account_id, user_id))
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                update xhs_account
                set {", ".join(assignments)}
                where id = %s and user_id = %s
                """,
                tuple(values),
            )
            updated = cursor.rowcount > 0
        self.conn.commit()
        return updated

    def _insert_profile(self, cursor, account_id: int, profile: XHSAccountProfile, now: int) -> None:
        values = profile.model_dump()
        cursor.execute(
            """
            insert into xhs_account_profile (
                xhs_account_id, domain_name, persona, target_audience,
                content_style, tone, common_phrases, forbidden_phrases,
                tag_preferences, word_count_preference, topic_preferences,
                create_time, update_time
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (account_id,) + tuple(values[field] for field in PROFILE_FIELDS) + (now, now),
        )

    def _select_sql(self) -> str:
        return """
            select
                a.id,
                a.user_id,
                a.display_name,
                a.account_group,
                a.status,
                a.daily_limit,
                a.min_interval_minutes,
                a.last_publish_time,
                a.today_publish_count,
                a.login_state_path,
                a.create_time,
                a.update_time,
                p.id as profile_id,
                p.domain_name,
                p.persona,
                p.target_audience,
                p.content_style,
                p.tone,
                p.common_phrases,
                p.forbidden_phrases,
                p.tag_preferences,
                p.word_count_preference,
                p.topic_preferences,
                p.create_time as profile_create_time,
                p.update_time as profile_update_time
            from xhs_account a
            left join xhs_account_profile p on p.xhs_account_id = a.id
            """

    def _row_to_account(self, row: dict) -> dict:
        profile = XHSAccountProfile().model_dump()
        if row["profile_id"] is not None:
            profile.update({field: row[field] for field in PROFILE_FIELDS})
            profile["id"] = row["profile_id"]
            profile["create_time"] = row["profile_create_time"]
            profile["update_time"] = row["profile_update_time"]

        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "display_name": row["display_name"],
            "account_group": row["account_group"],
            "status": row["status"],
            "daily_limit": row["daily_limit"],
            "min_interval_minutes": row["min_interval_minutes"],
            "last_publish_time": row["last_publish_time"],
            "today_publish_count": row["today_publish_count"],
            "login_state_path": row["login_state_path"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
            "profile": profile,
        }
