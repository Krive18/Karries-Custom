import json
import time
from typing import Any


class AdminAuditRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create(
        self,
        admin_user_id: int,
        action: str,
        target_type: str,
        target_id: int,
        detail: dict[str, Any],
        commit: bool = True,
    ) -> int:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into admin_audit_log (
                    admin_user_id, action, target_type, target_id, detail_json, create_time
                )
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    admin_user_id,
                    action,
                    target_type,
                    target_id,
                    json.dumps(detail, ensure_ascii=False),
                    int(time.time()),
                ),
            )
            audit_id = int(cursor.lastrowid)
        if commit:
            self.conn.commit()
        return audit_id
