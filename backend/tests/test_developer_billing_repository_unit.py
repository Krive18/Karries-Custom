from app.repositories.developer_billing_repository import DeveloperBillingRepository


class PaymentRecordCursor:
    def __init__(self) -> None:
        self.execute_count = 0
        self.list_params = None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        return None

    def execute(self, _query: str, params=None) -> None:
        self.execute_count += 1
        if params is not None:
            self.list_params = params

    def fetchone(self) -> dict:
        return {"total": 2}

    def fetchall(self) -> list[dict]:
        return [
            {
                "record_key": "membership_purchase:8",
                "record_type": "membership_purchase",
                "record_type_text": "会员购买",
                "order_id": 8,
                "order_no": "MU-8",
                "tenant_id": 2,
                "tenant_name": "测试团队",
                "user_id": 12,
                "customer_name": "管理员",
                "customer_login": "manager",
                "description": "Max会员版 · 1 个月",
                "amount_cent": 29_900,
                "credits": 0,
                "payment_channel": "wechat",
                "status": 3,
                "status_text": "已开通",
                "paid_time": 1_800_000_000,
                "create_time": 1_799_999_900,
                "update_time": 1_800_000_000,
                "sort_time": 1_800_000_000,
            }
        ]


class PaymentRecordConnection:
    def __init__(self) -> None:
        self.payment_cursor = PaymentRecordCursor()

    def cursor(self) -> PaymentRecordCursor:
        return self.payment_cursor


def test_list_payment_records_normalizes_rows_and_applies_pagination():
    connection = PaymentRecordConnection()

    result = DeveloperBillingRepository(connection).list_payment_records(
        page=2,
        page_size=25,
    )

    assert result == {
        "items": [
            {
                "record_key": "membership_purchase:8",
                "record_type": "membership_purchase",
                "record_type_text": "会员购买",
                "order_id": 8,
                "order_no": "MU-8",
                "tenant_id": 2,
                "tenant_name": "测试团队",
                "user_id": 12,
                "customer_name": "管理员",
                "customer_login": "manager",
                "description": "Max会员版 · 1 个月",
                "amount_cent": 29_900,
                "credits": 0,
                "payment_channel": "wechat",
                "status": 3,
                "status_text": "已开通",
                "paid_time": 1_800_000_000,
                "create_time": 1_799_999_900,
                "update_time": 1_800_000_000,
            }
        ],
        "page": 2,
        "page_size": 25,
        "total": 2,
    }
    assert connection.payment_cursor.execute_count == 2
    assert connection.payment_cursor.list_params == (25, 25)
