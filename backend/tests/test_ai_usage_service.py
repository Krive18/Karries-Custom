import json

import pytest

from app.integrations.deepseek import TextGenerationResult
from app.repositories.ai_usage_repository import AIUsageRepository
from app.services.ai_usage_service import AIUsageService
from app.services.credit_charge_service import CreditChargeService


class FakeUsageCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params):
        if self.conn.fail_execute:
            raise RuntimeError("database execute failed")
        self.conn.queries.append(" ".join(sql.lower().split()))
        self.lastrowid = self.conn.next_id
        self.conn.next_id += 1
        self.conn.rows.append(
            dict(
                zip(
                    (
                        "tenant_id",
                        "user_id",
                        "business_type",
                        "business_id",
                        "provider",
                        "model_name",
                        "status",
                        "credit_cost",
                        "latency_ms",
                        "input_chars",
                        "output_chars",
                        "error_message",
                        "create_time",
                    ),
                    params,
                )
            )
        )


class FakeUsageConnection:
    def __init__(self, fail_execute=False, fail_commit=False):
        self.rows = []
        self.queries = []
        self.commits = 0
        self.rollbacks = 0
        self.next_id = 1
        self.fail_execute = fail_execute
        self.fail_commit = fail_commit

    def cursor(self):
        return FakeUsageCursor(self)

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("database commit failed")

    def rollback(self):
        self.rollbacks += 1


def test_usage_service_records_success_with_generation_metrics():
    conn = FakeUsageConnection()
    usage = AIUsageService(AIUsageRepository(conn))
    result = TextGenerationResult(
        content="reply",
        provider="deepseek",
        model_name="deepseek-chat",
        latency_ms=123,
        input_chars=18,
        output_chars=5,
    )

    usage.record_success(
        tenant_id=2,
        user_id=7,
        business_type="viral_analysis",
        business_id=19,
        result=result,
        credit_cost=3,
    )

    assert conn.commits == 1
    assert conn.rows == [
        {
            "tenant_id": 2,
            "user_id": 7,
            "business_type": "viral_analysis",
            "business_id": 19,
            "provider": "deepseek",
            "model_name": "deepseek-chat",
            "status": "success",
            "credit_cost": 3,
            "latency_ms": 123,
            "input_chars": 18,
            "output_chars": 5,
            "error_message": "",
            "create_time": conn.rows[0]["create_time"],
        }
    ]
    assert "insert into ai_usage_log" in conn.queries[0]


def test_usage_service_records_failed_call_without_key_or_prompt():
    conn = FakeUsageConnection()
    usage = AIUsageService(AIUsageRepository(conn))

    usage.record_failure(
        tenant_id=2,
        user_id=7,
        business_type="inspiration_chat",
        business_id=0,
        provider="deepseek",
        model_name="deepseek-chat",
        error_message="provider timeout for sk-private-secret",
        latency_ms=50,
        input_chars=12,
    )

    row = conn.rows[0]
    assert row["status"] == "failed"
    assert row["credit_cost"] == 0
    assert row["output_chars"] == 0
    assert "sk-" not in json.dumps(row)
    assert set(row) == {
        "tenant_id",
        "user_id",
        "business_type",
        "business_id",
        "provider",
        "model_name",
        "status",
        "credit_cost",
        "latency_ms",
        "input_chars",
        "output_chars",
        "error_message",
        "create_time",
    }


@pytest.mark.parametrize(
    "error_message",
    [
        "request failed for account private-account-id",
        "Authorization: Bearer custom-sensitive-token",
        "Prompt: " + "private prompt text " * 100,
        "Provider response: " + "private response text " * 100,
    ],
)
def test_usage_service_uses_safe_summary_for_untrusted_failure_message(error_message):
    conn = FakeUsageConnection()
    usage = AIUsageService(AIUsageRepository(conn))

    usage.record_failure(
        tenant_id=2,
        user_id=7,
        business_type="inspiration_chat",
        business_id=0,
        provider="deepseek",
        model_name="deepseek-chat",
        error_message=error_message,
    )

    assert conn.rows[0]["error_message"] == "AI provider request failed"
    assert "private" not in conn.rows[0]["error_message"]
    assert "Bearer" not in conn.rows[0]["error_message"]


def test_usage_repository_rolls_back_when_execute_fails():
    conn = FakeUsageConnection(fail_execute=True)
    repository = AIUsageRepository(conn)

    with pytest.raises(RuntimeError, match="database execute failed"):
        repository.create(
            tenant_id=2,
            user_id=7,
            business_type="inspiration_chat",
            business_id=0,
            provider="deepseek",
            model_name="deepseek-chat",
            status="failed",
            credit_cost=0,
            latency_ms=0,
            input_chars=0,
            output_chars=0,
            error_message="AI provider request failed",
        )

    assert conn.rollbacks == 1


def test_usage_repository_rolls_back_when_commit_fails():
    conn = FakeUsageConnection(fail_commit=True)
    repository = AIUsageRepository(conn)

    with pytest.raises(RuntimeError, match="database commit failed"):
        repository.create(
            tenant_id=2,
            user_id=7,
            business_type="inspiration_chat",
            business_id=0,
            provider="deepseek",
            model_name="deepseek-chat",
            status="failed",
            credit_cost=0,
            latency_ms=0,
            input_chars=0,
            output_chars=0,
            error_message="AI provider request failed",
        )

    assert conn.rollbacks == 1


def test_credit_charge_service_estimates_supported_business_types():
    service = CreditChargeService()

    assert service.estimate("inspiration_chat") == 1
    assert service.estimate("viral_analysis") == 3


def test_credit_charge_service_rejects_unknown_business_type():
    with pytest.raises(ValueError, match="unsupported business type"):
        CreditChargeService().estimate("image_copy")
