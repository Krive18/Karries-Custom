import pytest

from app.core.config import default_config


def clear_mysql_env(monkeypatch):
    for key in (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_CHARSET",
        "MYSQL_CONNECT_TIMEOUT",
        "XHS_ENV",
        "APP_ENV",
        "XHS_AUTH_TOKEN_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)


def test_default_config_uses_mysql_defaults(monkeypatch):
    clear_mysql_env(monkeypatch)

    config = default_config()

    assert not hasattr(config, "database_path")
    assert config.mysql.host == "127.0.0.1"
    assert config.mysql.port == 3306
    assert config.mysql.database == "xhs_publisher"
    assert config.mysql.user == "xhs_publisher"
    assert config.mysql.password == ""
    assert config.mysql.charset == "utf8mb4"
    assert config.mysql.connect_timeout == 5
    assert config.environment == "development"


def test_default_config_reads_mysql_environment(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "db.local")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setenv("MYSQL_DATABASE", "xhs_test")
    monkeypatch.setenv("MYSQL_USER", "tester")
    monkeypatch.setenv("MYSQL_PASSWORD", "secret")
    monkeypatch.setenv("MYSQL_CHARSET", "utf8mb4")
    monkeypatch.setenv("MYSQL_CONNECT_TIMEOUT", "9")

    config = default_config()

    assert config.mysql.host == "db.local"
    assert config.mysql.port == 3307
    assert config.mysql.database == "xhs_test"
    assert config.mysql.user == "tester"
    assert config.mysql.password == "secret"
    assert config.mysql.charset == "utf8mb4"
    assert config.mysql.connect_timeout == 9


def test_default_config_requires_auth_secret_outside_development(monkeypatch):
    clear_mysql_env(monkeypatch)
    monkeypatch.setenv("XHS_ENV", "production")

    with pytest.raises(ValueError, match="XHS_AUTH_TOKEN_SECRET"):
        default_config()


def test_default_config_allows_custom_auth_secret_in_production(monkeypatch):
    clear_mysql_env(monkeypatch)
    monkeypatch.setenv("XHS_ENV", "production")
    monkeypatch.setenv("XHS_AUTH_TOKEN_SECRET", "production-secret")

    config = default_config()

    assert config.environment == "production"
    assert config.auth.token_secret == "production-secret"
