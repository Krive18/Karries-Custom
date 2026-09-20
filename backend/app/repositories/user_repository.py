import time


class UserRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_invite_code(
        self,
        code: str,
        initial_credits: int,
        max_uses: int,
        expires_time: int,
        remark: str,
        tenant_id: int = 1,
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into invite_code (
                    tenant_id, code, initial_credits, max_uses, used_count,
                    expires_time, status, remark, create_time, update_time
                )
                values (%s, %s, %s, %s, 0, %s, 1, %s, %s, %s)
                """,
                (tenant_id, code, initial_credits, max_uses, expires_time, remark, now, now),
            )
            invite_id = int(cursor.lastrowid)
        self.conn.commit()
        return invite_id

    def get_invite_code(self, code: str) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, code, initial_credits, max_uses, used_count,
                       expires_time, status, remark, create_time, update_time
                from invite_code
                where code = %s
                """,
                (code,),
            )
            return cursor.fetchone()

    def consume_invite_code(self, code: str) -> bool:
        now = int(time.time())
        invite = self.get_invite_code(code)
        if invite is None:
            return False
        if invite["status"] != 1:
            return False
        if invite["used_count"] >= invite["max_uses"]:
            return False
        if invite["expires_time"] and invite["expires_time"] < now:
            return False

        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update invite_code
                set used_count = used_count + 1, update_time = %s
                where code = %s
                  and used_count < max_uses
                  and status = 1
                  and (expires_time = 0 or expires_time >= %s)
                """,
                (now, code, now),
            )
            changed = cursor.rowcount == 1
        self.conn.commit()
        return changed

    def create_user(
        self,
        login_name: str,
        nickname: str,
        password_hash: str,
        user_role: str,
        invite_code: str,
        tenant_id: int = 1,
        *,
        commit: bool = True,
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into app_user (
                    tenant_id, login_name, nickname, password_hash, user_role, status,
                    invite_code, last_login_time, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, 1, %s, 0, %s, %s)
                """,
                (tenant_id, login_name, nickname, password_hash, user_role, invite_code, now, now),
            )
            user_id = int(cursor.lastrowid)
        if commit:
            self.conn.commit()
        return user_id

    def get_by_login_name(self, login_name: str) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, login_name, nickname, password_hash, user_role, status,
                       auth_version,
                       invite_code, last_login_time, create_time, update_time
                from app_user
                where login_name = %s
                """,
                (login_name,),
            )
            return cursor.fetchone()

    def get_by_id(self, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, login_name, nickname, password_hash, user_role, status,
                       auth_version,
                       invite_code, last_login_time, create_time, update_time
                from app_user
                where id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()

    def update_last_login(self, user_id: int) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                "update app_user set last_login_time = %s, update_time = %s where id = %s",
                (now, now, user_id),
            )
        self.conn.commit()

    @staticmethod
    def _employee_filters(
        tenant_id: int,
        keyword: str,
        status: int | None,
        *,
        table_alias: str = "u",
    ) -> tuple[str, tuple]:
        prefix = f"{table_alias}." if table_alias else ""
        clauses = [
            f"{prefix}tenant_id = %s",
            f"{prefix}user_role = 'customer'",
        ]
        params: list[object] = [tenant_id]
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            clauses.append(
                f"({prefix}login_name like %s or {prefix}nickname like %s)"
            )
            pattern = f"%{normalized_keyword}%"
            params.extend([pattern, pattern])
        if status is not None:
            clauses.append(f"{prefix}status = %s")
            params.append(status)
        return " and ".join(clauses), tuple(params)

    def list_employees(
        self,
        tenant_id: int,
        keyword: str,
        status: int | None,
        offset: int,
        limit: int,
    ) -> list[dict]:
        where_sql, params = self._employee_filters(
            tenant_id,
            keyword,
            status,
        )
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select u.id, u.tenant_id, u.login_name, u.nickname,
                       u.user_role, u.status,
                       coalesce(w.balance, 0) as wallet_balance,
                       (
                           select count(*)
                           from xhs_account xa
                           where xa.user_id = u.id
                       ) as xhs_account_count,
                       (
                           select count(*)
                           from matrix_publish_plan mp
                           where mp.user_id = u.id
                       ) as publish_plan_count,
                       u.last_login_time, u.create_time, u.update_time
                from app_user u
                left join credit_wallet w on w.user_id = u.id
                where {where_sql}
                order by u.id desc
                limit %s offset %s
                """,
                (*params, limit, offset),
            )
            return list(cursor.fetchall())

    def count_employees(
        self,
        tenant_id: int,
        keyword: str,
        status: int | None,
    ) -> int:
        where_sql, params = self._employee_filters(
            tenant_id,
            keyword,
            status,
            table_alias="",
        )
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"select count(*) as total from app_user where {where_sql}",
                params,
            )
            return int(cursor.fetchone()["total"])

    def get_employee_for_tenant(
        self,
        tenant_id: int,
        user_id: int,
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select u.id, u.tenant_id, u.login_name, u.nickname,
                       u.user_role, u.status,
                       coalesce(w.balance, 0) as wallet_balance,
                       (
                           select count(*)
                           from xhs_account xa
                           where xa.user_id = u.id
                       ) as xhs_account_count,
                       (
                           select count(*)
                           from matrix_publish_plan mp
                           where mp.user_id = u.id
                       ) as publish_plan_count,
                       (
                           select count(*)
                           from inspiration_session ins
                           where ins.user_id = u.id
                             and ins.tenant_id = u.tenant_id
                       ) as inspiration_session_count,
                       (
                           select count(*)
                           from viral_analysis_job vaj
                           where vaj.user_id = u.id
                             and vaj.tenant_id = u.tenant_id
                       ) as viral_analysis_count,
                       u.last_login_time, u.create_time, u.update_time
                from app_user u
                left join credit_wallet w on w.user_id = u.id
                where u.id = %s
                  and u.tenant_id = %s
                  and u.user_role = 'customer'
                """,
                (user_id, tenant_id),
            )
            return cursor.fetchone()

    def get_employee_summary(self, tenant_id: int) -> dict:
        seven_days_ago = int(time.time()) - 7 * 24 * 60 * 60
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select count(*) as total,
                       coalesce(sum(status = 1), 0) as active,
                       coalesce(sum(status = 2), 0) as disabled,
                       coalesce(sum(last_login_time >= %s), 0) as recent_login
                from app_user
                where tenant_id = %s
                  and user_role = 'customer'
                """,
                (seven_days_ago, tenant_id),
            )
            return cursor.fetchone()

    def update_employee_profile_for_tenant(
        self,
        tenant_id: int,
        user_id: int,
        login_name: str,
        nickname: str,
        *,
        commit: bool = True,
    ) -> bool:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update app_user
                set login_name = %s, nickname = %s, update_time = %s
                where id = %s
                  and tenant_id = %s
                  and user_role = 'customer'
                """,
                (
                    login_name,
                    nickname,
                    int(time.time()),
                    user_id,
                    tenant_id,
                ),
            )
            changed = cursor.rowcount == 1
        if commit:
            self.conn.commit()
        return changed

    def update_status_for_tenant(
        self,
        tenant_id: int,
        user_id: int,
        status: int,
        *,
        commit: bool = True,
    ) -> bool:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update app_user
                set status = %s,
                    auth_version = auth_version + 1,
                    update_time = %s
                where id = %s
                  and tenant_id = %s
                  and user_role = 'customer'
                """,
                (status, int(time.time()), user_id, tenant_id),
            )
            changed = cursor.rowcount == 1
        if commit:
            self.conn.commit()
        return changed

    def update_password_for_tenant(
        self,
        tenant_id: int,
        user_id: int,
        password_hash: str,
        *,
        commit: bool = True,
    ) -> bool:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update app_user
                set password_hash = %s,
                    auth_version = auth_version + 1,
                    update_time = %s
                where id = %s
                  and tenant_id = %s
                  and user_role = 'customer'
                """,
                (password_hash, int(time.time()), user_id, tenant_id),
            )
            changed = cursor.rowcount == 1
        if commit:
            self.conn.commit()
        return changed
