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
        "MYSQL_READ_TIMEOUT",
        "MYSQL_WRITE_TIMEOUT",
        "MYSQL_POOL_SIZE",
        "MYSQL_POOL_TIMEOUT",
        "MYSQL_POOL_RECYCLE",
        "MYSQL_POOL_PRE_PING",
        "MYSQL_RECONNECT_RETRY_SECONDS",
        "XHS_ENV",
        "APP_ENV",
        "XHS_AUTH_TOKEN_SECRET",
        "AI_SETTINGS_ENCRYPTION_KEY",
        "XHS_CORS_ALLOWED_ORIGINS",
        "XHS_EXPOSE_API_DOCS",
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
    assert config.mysql.read_timeout == 15
    assert config.mysql.write_timeout == 15
    assert config.mysql.pool_size == 10
    assert config.mysql.pool_timeout == 10
    assert config.mysql.pool_recycle == 1800
    assert config.mysql.pool_pre_ping is True
    assert config.mysql.reconnect_retry_seconds == 5
    assert config.environment == "development"
    assert config.expose_api_docs is True
    assert config.cors_allowed_origins


def test_default_config_reads_mysql_environment(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "db.local")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setenv("MYSQL_DATABASE", "xhs_test")
    monkeypatch.setenv("MYSQL_USER", "tester")
    monkeypatch.setenv("MYSQL_PASSWORD", "secret")
    monkeypatch.setenv("MYSQL_CHARSET", "utf8mb4")
    monkeypatch.setenv("MYSQL_CONNECT_TIMEOUT", "9")
    monkeypatch.setenv("MYSQL_READ_TIMEOUT", "21")
    monkeypatch.setenv("MYSQL_WRITE_TIMEOUT", "22")
    monkeypatch.setenv("MYSQL_POOL_SIZE", "12")
    monkeypatch.setenv("MYSQL_POOL_TIMEOUT", "7")
    monkeypatch.setenv("MYSQL_POOL_RECYCLE", "900")
    monkeypatch.setenv("MYSQL_POOL_PRE_PING", "false")
    monkeypatch.setenv("MYSQL_RECONNECT_RETRY_SECONDS", "3")

    config = default_config()

    assert config.mysql.host == "db.local"
    assert config.mysql.port == 3307
    assert config.mysql.database == "xhs_test"
    assert config.mysql.user == "tester"
    assert config.mysql.password == "secret"
    assert config.mysql.charset == "utf8mb4"
    assert config.mysql.connect_timeout == 9
    assert config.mysql.read_timeout == 21
    assert config.mysql.write_timeout == 22
    assert config.mysql.pool_size == 12
    assert config.mysql.pool_timeout == 7
    assert config.mysql.pool_recycle == 900
    assert config.mysql.pool_pre_ping is False
    assert config.mysql.reconnect_retry_seconds == 3


def test_default_config_requires_auth_secret_outside_development(monkeypatch):
    clear_mysql_env(monkeypatch)
    monkeypatch.setenv("XHS_ENV", "production")

    with pytest.raises(ValueError, match="XHS_AUTH_TOKEN_SECRET"):
        default_config()


def test_default_config_allows_custom_auth_secret_in_production(monkeypatch):
    clear_mysql_env(monkeypatch)
    monkeypatch.setenv("XHS_ENV", "production")
    monkeypatch.setenv("XHS_AUTH_TOKEN_SECRET", "production-secret")
    monkeypatch.setenv("AI_SETTINGS_ENCRYPTION_KEY", "production-encryption-secret")

    config = default_config()

    assert config.environment == "production"
    assert config.auth.token_secret == "production-secret"
    assert config.expose_api_docs is False
    assert config.cors_allowed_origins == []


def test_default_config_requires_ai_encryption_key_in_production(monkeypatch):
    clear_mysql_env(monkeypatch)
    monkeypatch.setenv("XHS_ENV", "production")
    monkeypatch.setenv("XHS_AUTH_TOKEN_SECRET", "production-secret")

    with pytest.raises(ValueError, match="AI_SETTINGS_ENCRYPTION_KEY"):
        default_config()


def test_default_config_reads_worker_api_token(monkeypatch):
    monkeypatch.setenv("WORKER_API_TOKEN", "worker-secret")

    from app.core.config import default_config

    config = default_config()

    assert config.worker_api_token == "worker-secret"
