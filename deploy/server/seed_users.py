import os
import time
from dataclasses import dataclass

from app.core.config import default_config
from app.core.security import hash_password
from app.db.connection import connect
from app.db.migrations import migrate


@dataclass(frozen=True)
class SeedAccount:
    login_name: str
    nickname: str
    role: str
    password: str
    initial_credits: int = 0


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value


def seed_accounts() -> tuple[SeedAccount, ...]:
    return (
        SeedAccount(
            login_name=required_env("KARRIES_MANAGER_USERNAME"),
            nickname="禾一斯负责人",
            role="client_owner",
            password=required_env("KARRIES_MANAGER_PASSWORD"),
        ),
        SeedAccount(
            login_name=required_env("KARRIES_DEVELOPER_USERNAME"),
            nickname="平台开发者",
            role="developer_admin",
            password=required_env("KARRIES_DEVELOPER_PASSWORD"),
        ),
    )


def main() -> None:
    config = default_config()
    conn = connect(config.mysql)
    now = int(time.time())
    accounts = seed_accounts()
    try:
        migrate(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                insert into tenant (
                    id, tenant_code, tenant_name, status, create_time, update_time
                )
                values (1, 'karries', '禾一斯', 1, %s, %s)
                on duplicate key update
                    tenant_name = values(tenant_name),
                    status = 1,
                    update_time = values(update_time)
                """,
                (now, now),
            )
            # Preserve historical records while disabling every privileged or
            # demo login created by older delivery packages.
            active_logins = {account.login_name for account in accounts}
            for legacy_login in (
                "karries_owner",
                "karries_developer",
                "karries_local_test",
            ):
                if legacy_login in active_logins:
                    continue
                cursor.execute(
                    """
                    update app_user
                    set status = 0,
                        auth_version = auth_version + 1,
                        update_time = %s
                    where login_name = %s
                      and status <> 0
                    """,
                    (now, legacy_login),
                )
            for account in accounts:
                initial_password_hash = hash_password(account.password)
                cursor.execute(
                    """
                    insert into app_user (
                        tenant_id, login_name, nickname, password_hash, user_role,
                        status, auth_version, invite_code, last_login_time,
                        create_time, update_time
                    )
                    values (1, %s, %s, %s, %s, 1, 1, '', 0, %s, %s)
                    on duplicate key update
                        nickname = values(nickname),
                        password_hash = values(password_hash),
                        user_role = values(user_role),
                        status = 1,
                        auth_version = auth_version + 1,
                        update_time = values(update_time)
                    """,
                    (
                        account.login_name,
                        account.nickname,
                        initial_password_hash,
                        account.role,
                        now,
                        now,
                    ),
                )
                cursor.execute(
                    "select id from app_user where login_name = %s",
                    (account.login_name,),
                )
                user_id = int(cursor.fetchone()["id"])
                cursor.execute(
                    """
                    insert into credit_wallet (
                        user_id, balance, total_recharged, total_consumed,
                        create_time, update_time
                    )
                    values (%s, %s, %s, 0, %s, %s)
                    on duplicate key update update_time = values(update_time)
                    """,
                    (
                        user_id,
                        account.initial_credits,
                        account.initial_credits,
                        now,
                        now,
                    ),
                )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
