from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_ROOT = PROJECT_ROOT / "deploy" / "server"


def read_asset(name: str) -> str:
    return (DEPLOY_ROOT / name).read_text(encoding="utf-8")


def test_installer_configures_privileged_accounts_and_publish_worker() -> None:
    installer = read_asset("install.sh")
    seed_users = read_asset("seed_users.py")

    assert "secrets.token_hex(32)" in installer
    assert "resolve_secret" in installer
    assert "KARRIES_MYSQL_PASSWORD:-123456" not in installer
    assert "KARRIES_MANAGER_PASSWORD:-Karries@2026" not in installer
    assert "KARRIES_DEVELOPER_PASSWORD:-123456" not in installer
    assert "MYSQL_POOL_PRE_PING=1" in installer
    assert "MYSQL_RECONNECT_RETRY_SECONDS=5" in installer
    assert "SAU_LOG_DIR=/opt/karries/logs/social" in installer
    assert "KARRIES_MANAGER_USERNAME" in installer
    assert "KARRIES_MANAGER_PASSWORD" in installer
    assert "KARRIES_DEVELOPER_USERNAME" in installer
    assert "KARRIES_DEVELOPER_PASSWORD" in installer
    assert "Employee accounts are not pre-created" in installer
    assert '"karries_owner"' in seed_users
    assert '"karries_developer"' in seed_users
    assert '"karries_local_test"' in seed_users
    assert "set status = 0" in seed_users
    assert "password_hash = values(password_hash)" in seed_users
    assert "auth_version = auth_version + 1" in seed_users
    assert '"${WEB_ROOT}/manager/index.html"' in installer
    assert '"${WEB_ROOT}/developer/index.html"' in installer
    assert "patchright install --with-deps chromium" in installer
    assert "karries-publish-worker.service" in installer
    assert "karries-backup.timer" in installer
    assert "/api/ready" in installer


def test_installer_preserves_patchright_driver_execute_permission() -> None:
    installer = read_asset("install.sh")

    assert (
        'find "${APP_ROOT}/backend" "${WEB_ROOT}" -type f -exec chmod 0644 {} +'
        not in installer
    )
    assert '-path "${APP_ROOT}/backend/.venv" -prune -o' in installer
    assert '*/site-packages/patchright/driver/node' in installer
    assert 'chmod 0755 "${PATCHRIGHT_DRIVER}"' in installer
    assert installer.index('chmod 0644 {} +') < installer.index(
        'chmod 0755 "${PATCHRIGHT_DRIVER}"'
    )


def test_api_service_is_private_and_hardened() -> None:
    service = read_asset("karries-api.service")

    assert "--host 127.0.0.1" in service
    assert "EnvironmentFile=/etc/karries-api.env" in service
    assert "PLAYWRIGHT_BROWSERS_PATH=/opt/karries/runtime/browsers" in service
    assert "NoNewPrivileges=true" in service
    assert "ProtectSystem=strict" in service
    assert "CapabilityBoundingSet=" in service
    assert "MemoryMax=" in service


def test_publish_worker_is_managed_and_uses_private_api() -> None:
    service = read_asset("karries-publish-worker.service")

    assert "User=www-data" in service
    assert "Requires=karries-api.service" in service
    assert "EnvironmentFile=/etc/karries-api.env" in service
    assert "BACKEND_API_URL=http://127.0.0.1:8765" in service
    assert "PLAYWRIGHT_BROWSERS_PATH=/opt/karries/runtime/browsers" in service
    assert "app.workers.matrix_publish_worker" in service
    assert "Restart=always" in service


def test_api_service_uses_movable_virtualenv_python_entrypoint() -> None:
    service = read_asset("karries-api.service")

    assert "backend/.venv/bin/python -m uvicorn" in service
    assert "backend/.venv/bin/uvicorn" not in service


def test_upgrade_preserves_production_database_and_runtime_state() -> None:
    upgrade = read_asset("upgrade-preserve-data.sh")

    assert 'APP_ROOT="/opt/karries"' in upgrade
    assert 'ENV_FILE="/etc/karries-api.env"' in upgrade
    assert "systemctl start karries-backup.service" in upgrade
    assert "sha256sum --check SHA256SUMS" in upgrade
    assert 'PROTECTED_APP_PATHS=("data" "runtime" "logs")' in upgrade
    assert "seed_users.py" not in upgrade
    assert "install.sh" not in upgrade
    assert "CREATE DATABASE" not in upgrade
    assert "DROP DATABASE" not in upgrade
    assert "DROP USER" not in upgrade
    assert "MYSQL_PASSWORD=" not in upgrade
    assert 'systemctl stop karries-publish-worker karries-api' in upgrade
    assert 'smoke-test.sh" http://127.0.0.1' in upgrade


def test_upgrade_accepts_legacy_backup_without_checksum_manifest() -> None:
    upgrade = read_asset("upgrade-preserve-data.sh")

    database_backup_required = (
        'require_file "${DATABASE_BACKUP}/database.sql.gz"'
    )
    database_backup_gzip_check = (
        'gzip -t "${DATABASE_BACKUP}/database.sql.gz"'
    )
    legacy_manifest_fallback = (
        'if [[ ! -f "${DATABASE_BACKUP}/SHA256SUMS" ]]; then'
    )
    generated_manifest = (
        'sha256sum "${backup_payloads[@]}" > SHA256SUMS'
    )
    verified_manifest = (
        'sha256sum --check SHA256SUMS --quiet'
    )

    for expected in (
        database_backup_required,
        database_backup_gzip_check,
        legacy_manifest_fallback,
        generated_manifest,
        verified_manifest,
    ):
        assert expected in upgrade

    assert upgrade.index(database_backup_required) < upgrade.index(
        database_backup_gzip_check
    )
    assert upgrade.index(database_backup_gzip_check) < upgrade.index(
        legacy_manifest_fallback
    )
    assert upgrade.index(legacy_manifest_fallback) < upgrade.index(
        generated_manifest
    )
    assert upgrade.index(generated_manifest) < upgrade.index(
        verified_manifest,
        upgrade.index(legacy_manifest_fallback),
    )
    assert upgrade.index(verified_manifest, upgrade.index(legacy_manifest_fallback)) < (
        upgrade.index("DEPLOYMENT_STARTED=1")
    )


def test_upgrade_keeps_fresh_virtualenv_executable_by_service_user() -> None:
    upgrade = read_asset("upgrade-preserve-data.sh")

    assert 'chmod -R u=rwX,go=rX "${APP_ROOT}/backend/.venv"' in upgrade


def test_upgrade_and_rollback_wait_for_api_readiness_before_smoke_test() -> None:
    upgrade = read_asset("upgrade-preserve-data.sh")
    rollback = read_asset("rollback-preserve-data.sh")

    for script in (upgrade, rollback):
        assert "wait_for_api_ready" in script
        assert "http://127.0.0.1:8765/api/ready" in script


def test_upgrade_has_code_only_rollback_without_implicit_database_restore() -> None:
    rollback = read_asset("rollback-preserve-data.sh")

    assert 'BACKUP_ROOT="/var/backups/karries"' in rollback
    assert "previous-venv" in rollback
    assert "app-code.tar.gz" in rollback
    assert "web-static.tar.gz" in rollback
    assert "mysql" not in rollback.lower()
    assert "database.sql" not in rollback.lower()
    assert 'if [[ -d "${ROLLBACK_ROOT}/previous-venv" ]]' in rollback
    assert '[[ -d "${ROLLBACK_ROOT}/previous-venv" ]] || fail' not in rollback
    assert 'systemctl stop karries-publish-worker karries-api' in rollback
    assert 'smoke-test.sh" http://127.0.0.1' in rollback


def test_nginx_has_security_headers_and_rate_limits() -> None:
    nginx = read_asset("nginx-ip.conf")

    assert "server_tokens off" in nginx
    assert "limit_req_zone" in nginx
    assert "X-Content-Type-Options" in nginx
    assert "X-Frame-Options" in nginx
    assert "Referrer-Policy" in nginx
    assert "Content-Security-Policy" in nginx
    assert "https://d8j0ntlcm91z4.cloudfront.net" in nginx
    assert "https://fonts.googleapis.com" in nginx
    assert "https://fonts.gstatic.com" in nginx
    assert "Strict-Transport-Security" in nginx
    assert "X-Request-ID" in nginx
    assert "location ~ ^/api/auth/(customer|manager|developer)/login$" in nginx
    assert "proxy_pass http://127.0.0.1:8765" in nginx


def test_backup_is_scheduled_and_uses_consistent_dump() -> None:
    backup = read_asset("backup.sh")
    service = read_asset("karries-backup.service")
    timer = read_asset("karries-backup.timer")

    assert "--single-transaction" in backup
    assert "sha256sum" in backup
    assert "RETENTION_DAYS" in backup
    assert "ReadOnlyPaths=/opt/karries /etc/karries-api.env" in service
    assert "ReadWritePaths=/var/backups/karries" in service
    assert "Persistent=true" in timer


def test_restore_verifies_backup_before_mutating_services() -> None:
    restore = read_asset("restore.sh")

    assert "sha256sum --check SHA256SUMS" in restore
    assert "systemctl stop karries-publish-worker karries-api" in restore
    assert "data.previous" in restore
    assert "/api/ready" in restore


def test_smoke_test_checks_all_three_frontends_and_readiness() -> None:
    smoke = read_asset("smoke-test.sh")

    assert 'check_page "/" "customer"' in smoke
    assert 'check_page "/manager/" "manager"' in smoke
    assert 'check_page "/developer/" "developer"' in smoke
    assert 'check_api "/api/health" "health"' in smoke
    assert 'check_api "/api/ready" "readiness"' in smoke
    assert 'check_service "karries-api"' in smoke
    assert 'check_service "karries-publish-worker"' in smoke


def test_https_script_validates_domain_and_uses_certbot_redirect() -> None:
    https = read_asset("enable-https.sh")

    assert "Invalid domain" in https
    assert "python3-certbot-nginx" in https
    assert "certbot --nginx" in https
    assert "--redirect" in https
    assert "nginx -t" in https


def test_upload_instructions_do_not_publish_weak_credentials_or_fixed_host() -> None:
    readme = read_asset("UPLOAD-README.txt")

    assert "122.152.235.76" not in readme
    assert "Karries@2026" not in readme
    assert "应用密码：123456" not in readme
    assert "/root/karries-initial-credentials" in readme
    assert "external/social-auto-upload-xiaohongshu" in readme
