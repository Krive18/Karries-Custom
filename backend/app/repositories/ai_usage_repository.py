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
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into ai_usage_log (
                    tenant_id, user_id, business_type, business_id, provider, model_name,
                    status, credit_cost, latency_ms, input_chars, output_chars, error_message,
                    create_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    user_id,
                    business_type,
                    business_id,
                    provider,
                    model_name,
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
        self.conn.commit()
        return usage_id
