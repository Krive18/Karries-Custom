import time


class WalletRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_wallet(self, user_id: int, initial_credits: int, reason: str) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into credit_wallet (
                        user_id, balance, total_recharged, total_consumed, create_time, update_time
                    )
                    values (%s, 0, 0, 0, %s, %s)
                    """,
                    (user_id, now, now),
                )
                wallet_id = int(cursor.lastrowid)

                if initial_credits > 0:
                    cursor.execute(
                        """
                        update credit_wallet
                        set balance = %s,
                            total_recharged = total_recharged + %s,
                            update_time = %s
                        where user_id = %s
                        """,
                        (initial_credits, initial_credits, now, user_id),
                    )
                    cursor.execute(
                        """
                        insert into credit_ledger (
                            user_id, business_type, business_id, before_balance,
                            change_amount, after_balance, reason, create_time
                        )
                        values (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            "invite_bonus",
                            wallet_id,
                            0,
                            initial_credits,
                            initial_credits,
                            reason,
                            now,
                        ),
                    )
            self.conn.commit()
            return wallet_id
        except Exception:
            self.conn.rollback()
            raise

    def get_wallet(self, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, balance, total_recharged, total_consumed, create_time, update_time
                from credit_wallet
                where user_id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()

    def adjust_credits(
        self,
        user_id: int,
        change_amount: int,
        business_type: str,
        business_id: int,
        reason: str,
    ) -> int:
        try:
            now = int(time.time())
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, user_id, balance, total_recharged, total_consumed, create_time, update_time
                    from credit_wallet
                    where user_id = %s
                    for update
                    """,
                    (user_id,),
                )
                wallet = cursor.fetchone()
                if wallet is None:
                    raise ValueError(f"wallet does not exist: {user_id}")

                before = int(wallet["balance"])
                after = before + change_amount
                if after < 0:
                    raise ValueError("insufficient credits")

                total_recharged_delta = change_amount if change_amount > 0 else 0
                total_consumed_delta = -change_amount if change_amount < 0 else 0
                cursor.execute(
                    """
                    update credit_wallet
                    set balance = %s,
                        total_recharged = total_recharged + %s,
                        total_consumed = total_consumed + %s,
                        update_time = %s
                    where user_id = %s
                    """,
                    (after, total_recharged_delta, total_consumed_delta, now, user_id),
                )
                cursor.execute(
                    """
                    insert into credit_ledger (
                        user_id, business_type, business_id, before_balance,
                        change_amount, after_balance, reason, create_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, business_type, business_id, before, change_amount, after, reason, now),
                )
                ledger_id = int(cursor.lastrowid)
            self.conn.commit()
            return ledger_id
        except Exception:
            self.conn.rollback()
            raise

    def list_ledger(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, business_type, business_id, before_balance,
                       change_amount, after_balance, reason, create_time
                from credit_ledger
                where user_id = %s
                order by id desc
                """,
                (user_id,),
            )
            return list(cursor.fetchall())
