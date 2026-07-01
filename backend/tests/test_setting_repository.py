from app.repositories.setting_repository import SettingRepository


def test_setting_repository_upserts_and_reads_value(mysql_conn):
    repo = SettingRepository(mysql_conn)

    repo.set("ai.vision.provider", "doubao")
    repo.set("ai.vision.provider", "gemini")

    assert repo.get("ai.vision.provider") == "gemini"


def test_setting_repository_returns_default_for_missing_key(mysql_conn):
    repo = SettingRepository(mysql_conn)

    assert repo.get("missing", "fallback") == "fallback"


def test_setting_repository_deletes_value(mysql_conn):
    repo = SettingRepository(mysql_conn)

    repo.set("ai.copywriting.api_key", "sk-secret")
    repo.delete("ai.copywriting.api_key")

    assert repo.get("ai.copywriting.api_key") == ""
