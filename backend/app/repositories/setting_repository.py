import time


class SettingRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, key: str, default: str = "") -> str:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select setting_value from app_setting where setting_key = %s",
                (key,),
            )
            row = cursor.fetchone()
        if row is None:
            return default
        return str(row["setting_value"])

    def set(self, key: str, value: str) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into app_setting (setting_key, setting_value, create_time, update_time)
                values (%s, %s, %s, %s)
                on duplicate key update
                    setting_value = values(setting_value),
                    update_time = values(update_time)
                """,
                (key, value, now, now),
            )
        self.conn.commit()

    def delete(self, key: str) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute("delete from app_setting where setting_key = %s", (key,))
        self.conn.commit()
