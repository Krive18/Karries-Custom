import time


class AIUsageRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create(
        self,
        tenant_id: int,
        user_id: int,
        business_type: str,
        business_id: int,
        provider: str,
        model_name: str,
        status: str,
        credit_cost: int,
        latency_ms: int,
        input_chars: int,
        output_chars: int,
        error_message: str,
        request_id: str = "",
        commit: bool = True,
    ) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into ai_usage_log (
                        tenant_id, user_id, business_type, business_id, provider, model_name,
                        request_id, status, credit_cost, latency_ms, input_chars, output_chars, error_message,
                        create_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        user_id,
                        business_type,
                        business_id,
                        provider,
                        model_name,
                        request_id[:128],
                        status,
                        credit_cost,
                        latency_ms,
                        input_chars,
                        output_chars,
                        error_message,
                        now,
                    ),
                )
                usage_id = int(cursor.lastrowid)
            if commit:
                self.conn.commit()
            return usage_id
        except Exception:
            if commit:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            raise

    def get_latest_for_business(
        self,
        tenant_id: int,
        business_type: str,
        business_id: int,
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, status, provider, model_name, request_id, latency_ms, input_chars,
                       output_chars, credit_cost, error_message, create_time
                from ai_usage_log
                where tenant_id = %s and business_type = %s and business_id = %s
                order by id desc
                limit 1
                """,
                (tenant_id, business_type, business_id),
            )
            return cursor.fetchone()
