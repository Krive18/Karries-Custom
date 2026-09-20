import time


ACTIVE_LOGIN_STATUSES = ("starting", "awaiting_scan")


class XHSAccountLoginRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(
        self,
        *,
        tenant_id: int,
        user_id: int,
        account_id: int,
        operation_token: str,
        login_state_path: str,
        expires_time: int,
    ) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update xhs_account_login_session
                    set status = 'cancelled',
                        message = '已创建新的扫码登录会话',
                        completed_time = %s,
                        update_time = %s
                    where user_id = %s
                      and xhs_account_id = %s
                      and status in ('starting', 'awaiting_scan')
                    """,
                    (now, now, user_id, account_id),
                )
                cursor.execute(
                    """
                    insert into xhs_account_login_session (
                        tenant_id, user_id, xhs_account_id, operation_token,
                        status, message, qrcode_image_data, login_state_path,
                        started_time, expires_time, completed_time,
                        create_time, update_time
                    )
                    values (
                        %s, %s, %s, %s,
                        'starting', '正在准备小红书登录二维码', '', %s,
                        %s, %s, 0,
                        %s, %s
                    )
                    """,
                    (
                        tenant_id,
                        user_id,
                        account_id,
                        operation_token,
                        login_state_path,
                        now,
                        expires_time,
                        now,
                        now,
                    ),
                )
                session_id = int(cursor.lastrowid)
            self.conn.commit()
            return session_id
        except Exception:
            self.conn.rollback()
            raise

    def get_for_user(self, user_id: int, account_id: int, session_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, xhs_account_id, operation_token,
                       status, message, qrcode_image_data, login_state_path,
                       started_time, expires_time, completed_time,
                       create_time, update_time
                from xhs_account_login_session
                where id = %s and user_id = %s and xhs_account_id = %s
                """,
                (session_id, user_id, account_id),
            )
            return cursor.fetchone()

    def get_latest_for_user(self, user_id: int, account_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, user_id, xhs_account_id, operation_token,
                       status, message, qrcode_image_data, login_state_path,
                       started_time, expires_time, completed_time,
                       create_time, update_time
                from xhs_account_login_session
                where user_id = %s and xhs_account_id = %s
                order by id desc
                limit 1
                """,
                (user_id, account_id),
            )
            return cursor.fetchone()

    def mark_qrcode_ready(
        self,
        session_id: int,
        operation_token: str,
        qrcode_image_data: str,
    ) -> bool:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update xhs_account_login_session
                set status = 'awaiting_scan',
                    message = '请使用小红书 App 扫描二维码',
                    qrcode_image_data = %s,
                    update_time = %s
                where id = %s
                  and operation_token = %s
                  and status = 'starting'
                """,
                (qrcode_image_data, now, session_id, operation_token),
            )
            updated = cursor.rowcount > 0
        self.conn.commit()
        return updated

    def complete(
        self,
        session_id: int,
        operation_token: str,
        *,
        status: str,
        message: str,
    ) -> bool:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update xhs_account_login_session
                set status = %s,
                    message = %s,
                    qrcode_image_data = '',
                    completed_time = %s,
                    update_time = %s
                where id = %s
                  and operation_token = %s
                  and status in ('starting', 'awaiting_scan')
                """,
                (status, message[:500], now, now, session_id, operation_token),
            )
            updated = cursor.rowcount > 0
        self.conn.commit()
        return updated
