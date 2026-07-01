import time


class AccountRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, account_name: str, cookie_path: str) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into account (
                    account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
                )
                values (%s, 'xiaohongshu', %s, 1, 0, %s, %s)
                """,
                (account_name, cookie_path, now, now),
            )
            account_id = int(cursor.lastrowid)
        self.conn.commit()
        return account_id

    def get(self, account_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
                from account
                where id = %s
                """,
                (account_id,),
            )
            return cursor.fetchone()

    def list_all(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
                from account
                order by id desc
                """
            )
            return list(cursor.fetchall())

    def update_status(self, account_id: int, status: int) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update account
                set status = %s, last_checked_time = %s, update_time = %s
                where id = %s
                """,
                (status, now, now, account_id),
            )
        self.conn.commit()
