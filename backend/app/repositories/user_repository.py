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
        self.conn.commit()
        return user_id

    def get_by_login_name(self, login_name: str) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, login_name, nickname, password_hash, user_role, status,
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
