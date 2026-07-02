import pytest

from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 0
        self.rowcount = 0
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.lower().split())
        self.conn.queries.append(normalized)
        self.conn.params.append(params)
        self.rowcount = 0
        self._result = None

        if normalized.startswith("insert into credit_wallet"):
            self.lastrowid = self.conn.next_wallet_id
            self.conn.next_wallet_id += 1
            user_id = params[0]
            self.conn.wallet = {
                "id": self.lastrowid,
                "user_id": user_id,
                "balance": 0,
                "total_recharged": 0,
                "total_consumed": 0,
            }
            self.rowcount = 1
        elif normalized.startswith("select") and "from credit_wallet" in normalized:
            self._result = self.conn.wallet
        elif normalized.startswith("update credit_wallet"):
            if len(params) == 4:
                balance, recharged_delta, _now, _user_id = params
                consumed_delta = 0
            else:
                balance, recharged_delta, consumed_delta, _now, _user_id = params
            self.conn.wallet["balance"] = balance
            self.conn.wallet["total_recharged"] += recharged_delta
            self.conn.wallet["total_consumed"] += consumed_delta
            self.rowcount = 1
        elif normalized.startswith("insert into credit_ledger"):
            self.lastrowid = self.conn.next_ledger_id
            self.conn.next_ledger_id += 1
            self.conn.ledger.append(
                {
                    "id": self.lastrowid,
                    "user_id": params[0],
                    "business_type": params[1],
                    "business_id": params[2],
                    "before_balance": params[3],
                    "change_amount": params[4],
                    "after_balance": params[5],
                    "reason": params[6],
                }
            )
            self.rowcount = 1

    def fetchone(self):
        return self._result

    def fetchall(self):
        return list(self.conn.ledger)


class FakeWalletConnection:
    def __init__(self, wallet=None):
        self.wallet = wallet
        self.ledger = []
        self.queries = []
        self.params = []
        self.commits = 0
        self.rollbacks = 0
        self.next_wallet_id = 10
        self.next_ledger_id = 100

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_invite_code_create_and_consume(mysql_conn):
    users = UserRepository(mysql_conn)
    invite_id = users.create_invite_code(
        code="INVITE-A",
        initial_credits=88,
        max_uses=1,
        expires_time=0,
        remark="first batch",
    )

    invite = users.get_invite_code("INVITE-A")

    assert invite["id"] == invite_id
    assert invite["initial_credits"] == 88
    assert users.consume_invite_code("INVITE-A") is True
    assert users.consume_invite_code("INVITE-A") is False


def test_expired_invite_code_cannot_be_consumed(mysql_conn):
    users = UserRepository(mysql_conn)
    users.create_invite_code(
        code="EXPIRED-A",
        initial_credits=88,
        max_uses=1,
        expires_time=1,
        remark="expired",
    )

    assert users.consume_invite_code("EXPIRED-A") is False
    invite = users.get_invite_code("EXPIRED-A")
    assert invite["used_count"] == 0


def test_user_repository_creates_and_reads_user(mysql_conn):
    users = UserRepository(mysql_conn)
    user_id = users.create_user(
        login_name="operator_a",
        nickname="operator A",
        password_hash="hash-value",
        user_role="customer",
        invite_code="INVITE-A",
    )

    row = users.get_by_login_name("operator_a")

    assert row["id"] == user_id
    assert row["nickname"] == "operator A"
    assert row["user_role"] == "customer"


def test_wallet_repository_initializes_and_adjusts_credits(mysql_conn):
    users = UserRepository(mysql_conn)
    wallets = WalletRepository(mysql_conn)
    user_id = users.create_user("operator_a", "operator A", "hash-value", "customer", "INVITE-A")

    wallets.create_wallet(user_id, initial_credits=100, reason="invite bonus")
    wallet = wallets.get_wallet(user_id)
    assert wallet["balance"] == 100
    assert wallet["total_recharged"] == 100
    assert wallet["total_consumed"] == 0

    ledger_id = wallets.adjust_credits(
        user_id=user_id,
        change_amount=-25,
        business_type="ai_copy",
        business_id=123,
        reason="AI copy",
    )

    wallet = wallets.get_wallet(user_id)
    ledger = wallets.list_ledger(user_id)
    assert ledger_id
    assert wallet["balance"] == 75
    assert wallet["total_recharged"] == 100
    assert wallet["total_consumed"] == 25
    assert len(ledger) == 2
    assert ledger[0]["business_type"] == "ai_copy"
    assert ledger[0]["before_balance"] == 100
    assert ledger[0]["change_amount"] == -25
    assert ledger[0]["after_balance"] == 75
    assert ledger[1]["business_type"] == "invite_bonus"
    assert ledger[1]["before_balance"] == 0
    assert ledger[1]["change_amount"] == 100
    assert ledger[1]["after_balance"] == 100


def test_wallet_repository_rejects_insufficient_credits(mysql_conn):
    users = UserRepository(mysql_conn)
    wallets = WalletRepository(mysql_conn)
    user_id = users.create_user("operator_a", "operator A", "hash-value", "customer", "INVITE-A")
    wallets.create_wallet(user_id, initial_credits=10, reason="invite bonus")
    before_wallet = wallets.get_wallet(user_id)
    before_ledger = wallets.list_ledger(user_id)

    with pytest.raises(ValueError, match="insufficient credits"):
        wallets.adjust_credits(user_id, -11, "ai_video", 1, "video generation")

    after_wallet = wallets.get_wallet(user_id)
    after_ledger = wallets.list_ledger(user_id)
    assert after_wallet["balance"] == before_wallet["balance"]
    assert after_wallet["total_recharged"] == before_wallet["total_recharged"]
    assert after_wallet["total_consumed"] == before_wallet["total_consumed"]
    assert len(after_ledger) == len(before_ledger)


def test_wallet_adjustment_locks_wallet_row_for_update():
    conn = FakeWalletConnection(
        wallet={
            "id": 1,
            "user_id": 7,
            "balance": 50,
            "total_recharged": 50,
            "total_consumed": 0,
        }
    )
    wallets = WalletRepository(conn)

    wallets.adjust_credits(7, -20, "ai_copy", 123, "AI copy")

    assert any("for update" in query for query in conn.queries)


def test_wallet_adjustment_rolls_back_when_wallet_missing():
    conn = FakeWalletConnection(wallet=None)
    wallets = WalletRepository(conn)

    with pytest.raises(ValueError, match="wallet does not exist"):
        wallets.adjust_credits(7, -20, "ai_copy", 123, "AI copy")

    assert conn.rollbacks == 1
    assert conn.commits == 0
    assert conn.ledger == []


def test_wallet_adjustment_rolls_back_without_side_effects_when_insufficient():
    wallet = {
        "id": 1,
        "user_id": 7,
        "balance": 5,
        "total_recharged": 5,
        "total_consumed": 0,
    }
    conn = FakeWalletConnection(wallet=wallet)
    wallets = WalletRepository(conn)

    with pytest.raises(ValueError, match="insufficient credits"):
        wallets.adjust_credits(7, -6, "ai_copy", 123, "AI copy")

    assert conn.rollbacks == 1
    assert conn.commits == 0
    assert conn.wallet["balance"] == 5
    assert conn.wallet["total_recharged"] == 5
    assert conn.wallet["total_consumed"] == 0
    assert conn.ledger == []


def test_wallet_create_records_initial_bonus_in_one_transaction():
    conn = FakeWalletConnection()
    wallets = WalletRepository(conn)

    wallet_id = wallets.create_wallet(7, initial_credits=30, reason="invite bonus")

    assert wallet_id == 10
    assert conn.commits == 1
    assert conn.wallet["balance"] == 30
    assert conn.wallet["total_recharged"] == 30
    assert conn.ledger == [
        {
            "id": 100,
            "user_id": 7,
            "business_type": "invite_bonus",
            "business_id": 10,
            "before_balance": 0,
            "change_amount": 30,
            "after_balance": 30,
            "reason": "invite bonus",
        }
    ]
