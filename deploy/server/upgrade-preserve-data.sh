#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

APP_ROOT="/opt/karries"
WEB_ROOT="/var/www/karries"
ENV_FILE="/etc/karries-api.env"
BACKUP_ROOT="/var/backups/karries"
LOCK_FILE="/run/lock/karries-upgrade.lock"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROLLBACK_ROOT="${BACKUP_ROOT}/upgrade-${TIMESTAMP}"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
NEXT_VENV="${APP_ROOT}/backend/.venv.next-${TIMESTAMP}"
PROTECTED_APP_PATHS=("data" "runtime" "logs")
DEPLOYMENT_STARTED=0

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

require_file() {
  [[ -f "$1" ]] || fail "required file is missing: $1"
}

ensure_env_value() {
  local key="$1"
  local value="$2"
  if ! grep -q "^${key}=" "${ENV_FILE}"; then
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

wait_for_api_ready() {
  local attempt
  for ((attempt = 1; attempt <= 30; attempt += 1)); do
    if curl --fail --silent --show-error --max-time 5 \
      http://127.0.0.1:8765/api/ready >/dev/null; then
      return 0
    fi
    sleep 1
  done
  journalctl -u karries-api -n 100 --no-pager >&2 || true
  fail "karries-api did not become ready within 30 seconds"
}

safe_remove_tree() {
  local target="$1"
  case "${target}" in
    "${APP_ROOT}/backend/app"|"${APP_ROOT}/external"|"${APP_ROOT}/deploy"|"${APP_ROOT}/web")
      rm -rf -- "${target}"
      ;;
    *)
      fail "refusing to remove unexpected path: ${target}"
      ;;
  esac
}

restore_on_error() {
  local status=$?
  trap - ERR
  if [[ "${DEPLOYMENT_STARTED}" -eq 1 && -d "${ROLLBACK_ROOT}" ]]; then
    echo "Upgrade failed; restoring the previous application version." >&2
    bash "${SOURCE_ROOT}/deploy/server/rollback-preserve-data.sh" \
      "${ROLLBACK_ROOT}" || true
  fi
  exit "${status}"
}
trap restore_on_error ERR

[[ "${EUID}" -eq 0 ]] || fail "run this script with sudo"
for command_name in curl flock sha256sum tar gzip python3 systemctl find stat; do
  require_command "${command_name}"
done

exec 9>"${LOCK_FILE}"
flock -n 9 || fail "another KARRIES upgrade is already running"

[[ "${SOURCE_ROOT}" != "${APP_ROOT}" ]] || \
  fail "extract the new release under /home/ubuntu; do not overwrite /opt/karries first"
require_file "${SOURCE_ROOT}/SHA256SUMS"
require_file "${SOURCE_ROOT}/backend/app/server_main.py"
require_file "${SOURCE_ROOT}/backend/pyproject.toml"
require_file "${SOURCE_ROOT}/web/customer/index.html"
require_file "${SOURCE_ROOT}/web/manager/manager.html"
require_file "${SOURCE_ROOT}/web/developer/developer.html"
require_file "${SOURCE_ROOT}/deploy/server/karries-api.service"
require_file "${SOURCE_ROOT}/deploy/server/karries-publish-worker.service"
require_file "${SOURCE_ROOT}/deploy/server/rollback-preserve-data.sh"

require_file "${APP_ROOT}/backend/app/server_main.py"
require_file "${APP_ROOT}/backend/.venv/bin/python"
require_file "${APP_ROOT}/deploy/server/backup.sh"
require_file "${ENV_FILE}"
[[ -d "${WEB_ROOT}" ]] || fail "production web root is missing: ${WEB_ROOT}"

echo "Verifying uploaded release files..."
(cd "${SOURCE_ROOT}" && sha256sum --check SHA256SUMS --quiet)

protected_inode=()
for relative_path in "${PROTECTED_APP_PATHS[@]}"; do
  install -d -o www-data -g www-data -m 0750 "${APP_ROOT}/${relative_path}"
  protected_inode+=("$(stat -c '%d:%i' "${APP_ROOT}/${relative_path}")")
done

echo "Creating a fresh production database and upload backup..."
systemctl reset-failed karries-backup.service >/dev/null 2>&1 || true
systemctl start karries-backup.service
if systemctl is-failed --quiet karries-backup.service; then
  journalctl -u karries-backup.service -n 100 --no-pager >&2
  fail "production backup failed; upgrade was not started"
fi

DATABASE_BACKUP="$({
  find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d \
    ! -name 'upgrade-*' -printf '%T@ %p\n'
} | sort -nr | head -n 1 | cut -d' ' -f2-)"
[[ -n "${DATABASE_BACKUP}" ]] || fail "no database backup directory was created"
require_file "${DATABASE_BACKUP}/database.sql.gz"
gzip -t "${DATABASE_BACKUP}/database.sql.gz"
if [[ ! -f "${DATABASE_BACKUP}/SHA256SUMS" ]]; then
  echo "Legacy backup detected; creating a checksum manifest..."
  (
    cd "${DATABASE_BACKUP}"
    backup_payloads=(database.sql.gz)
    [[ -f data.tar.gz ]] && backup_payloads+=(data.tar.gz)
    sha256sum "${backup_payloads[@]}" > SHA256SUMS
  )
fi
require_file "${DATABASE_BACKUP}/SHA256SUMS"
(cd "${DATABASE_BACKUP}" && sha256sum --check SHA256SUMS --quiet)

install -d -o root -g root -m 0700 "${ROLLBACK_ROOT}"
printf '%s\n' "${DATABASE_BACKUP}" > "${ROLLBACK_ROOT}/database-backup-path"

echo "Saving the currently deployed code and static files for rollback..."
app_backup_paths=(backend/app backend/pyproject.toml external deploy web)
for optional_path in DEPLOY.txt RELEASE-MANIFEST.json SHA256SUMS; do
  [[ -e "${APP_ROOT}/${optional_path}" ]] && app_backup_paths+=("${optional_path}")
done
tar -C "${APP_ROOT}" -czf "${ROLLBACK_ROOT}/app-code.tar.gz" \
  "${app_backup_paths[@]}"
tar -C "${WEB_ROOT}" -czf "${ROLLBACK_ROOT}/web-static.tar.gz" .
install -d -m 0700 "${ROLLBACK_ROOT}/system"
for system_file in \
  /etc/systemd/system/karries-api.service \
  /etc/systemd/system/karries-publish-worker.service \
  /etc/systemd/system/karries-backup.service \
  /etc/systemd/system/karries-backup.timer; do
  [[ -f "${system_file}" ]] && cp -a "${system_file}" "${ROLLBACK_ROOT}/system/"
done
(cd "${ROLLBACK_ROOT}" && \
  sha256sum app-code.tar.gz web-static.tar.gz system/* > SHA256SUMS)
ln -sfn "${ROLLBACK_ROOT}" "${BACKUP_ROOT}/last-upgrade"

echo "Preparing the new Python runtime while the existing service stays online..."
python3 -m venv "${NEXT_VENV}"
"${NEXT_VENV}/bin/python" -m pip install --upgrade pip
"${NEXT_VENV}/bin/python" -m pip install "${SOURCE_ROOT}/backend"
PLAYWRIGHT_BROWSERS_PATH="${APP_ROOT}/runtime/browsers" \
  "${NEXT_VENV}/bin/python" -m patchright install chromium

NEXT_PATCHRIGHT_DRIVER="$(find "${NEXT_VENV}/lib" \
  -path '*/site-packages/patchright/driver/node' -type f -print -quit)"
[[ -n "${NEXT_PATCHRIGHT_DRIVER}" ]] || fail "Patchright driver was not installed"
chmod 0755 "${NEXT_PATCHRIGHT_DRIVER}"

echo "Stopping API and worker for the short code switch..."
DEPLOYMENT_STARTED=1
systemctl stop karries-publish-worker karries-api

safe_remove_tree "${APP_ROOT}/backend/app"
safe_remove_tree "${APP_ROOT}/external"
safe_remove_tree "${APP_ROOT}/deploy"
safe_remove_tree "${APP_ROOT}/web"
cp -a "${SOURCE_ROOT}/backend/app" "${APP_ROOT}/backend/app"
install -m 0644 "${SOURCE_ROOT}/backend/pyproject.toml" \
  "${APP_ROOT}/backend/pyproject.toml"
cp -a "${SOURCE_ROOT}/external" "${APP_ROOT}/external"
cp -a "${SOURCE_ROOT}/deploy" "${APP_ROOT}/deploy"
cp -a "${SOURCE_ROOT}/web" "${APP_ROOT}/web"
for release_file in DEPLOY.txt UPGRADE-PRESERVE-DATA.txt RELEASE-MANIFEST.json SHA256SUMS; do
  [[ -f "${SOURCE_ROOT}/${release_file}" ]] && \
    install -m 0644 "${SOURCE_ROOT}/${release_file}" "${APP_ROOT}/${release_file}"
done

mv "${APP_ROOT}/backend/.venv" "${ROLLBACK_ROOT}/previous-venv"
mv "${NEXT_VENV}" "${APP_ROOT}/backend/.venv"
chmod -R u=rwX,go=rX "${APP_ROOT}/backend/.venv"

for portal in customer manager developer; do
  portal_root="${WEB_ROOT}/${portal}"
  install -d -m 0755 "${portal_root}"
  find "${portal_root}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  cp -a "${SOURCE_ROOT}/web/${portal}/." "${portal_root}/"
done
install -m 0644 "${WEB_ROOT}/manager/manager.html" \
  "${WEB_ROOT}/manager/index.html"
install -m 0644 "${WEB_ROOT}/developer/developer.html" \
  "${WEB_ROOT}/developer/index.html"

install -m 0644 "${APP_ROOT}/deploy/server/karries-api.service" \
  /etc/systemd/system/karries-api.service
install -m 0644 "${APP_ROOT}/deploy/server/karries-publish-worker.service" \
  /etc/systemd/system/karries-publish-worker.service
install -m 0644 "${APP_ROOT}/deploy/server/karries-backup.service" \
  /etc/systemd/system/karries-backup.service
install -m 0644 "${APP_ROOT}/deploy/server/karries-backup.timer" \
  /etc/systemd/system/karries-backup.timer

ensure_env_value "MYSQL_POOL_SIZE" "10"
ensure_env_value "MYSQL_POOL_TIMEOUT" "10"
ensure_env_value "MYSQL_POOL_RECYCLE" "1800"
ensure_env_value "MYSQL_POOL_PRE_PING" "1"
ensure_env_value "MYSQL_RECONNECT_RETRY_SECONDS" "5"
ensure_env_value "SAU_LOG_DIR" "/opt/karries/logs/social"
chmod 0600 "${ENV_FILE}"

chown -R root:root \
  "${APP_ROOT}/backend/app" \
  "${APP_ROOT}/backend/pyproject.toml" \
  "${APP_ROOT}/external" \
  "${APP_ROOT}/deploy" \
  "${APP_ROOT}/web" \
  "${WEB_ROOT}"
find "${APP_ROOT}/backend/app" "${APP_ROOT}/external" "${APP_ROOT}/deploy" \
  -type d -exec chmod 0755 {} +
find "${APP_ROOT}/backend/app" "${APP_ROOT}/external" "${APP_ROOT}/deploy" \
  -type f -exec chmod 0644 {} +
chmod 0755 \
  "${APP_ROOT}/deploy/server/backup.sh" \
  "${APP_ROOT}/deploy/server/restore.sh" \
  "${APP_ROOT}/deploy/server/smoke-test.sh" \
  "${APP_ROOT}/deploy/server/enable-https.sh" \
  "${APP_ROOT}/deploy/server/upgrade-preserve-data.sh" \
  "${APP_ROOT}/deploy/server/rollback-preserve-data.sh"
find "${WEB_ROOT}" -type d -exec chmod 0755 {} +
find "${WEB_ROOT}" -type f -exec chmod 0644 {} +
find "${APP_ROOT}/backend/.venv/bin" -type f -exec chmod 0755 {} +
PATCHRIGHT_DRIVER="$(find "${APP_ROOT}/backend/.venv/lib" \
  -path '*/site-packages/patchright/driver/node' -type f -print -quit)"
[[ -n "${PATCHRIGHT_DRIVER}" ]] || fail "Patchright driver is missing after switch"
chmod 0755 "${PATCHRIGHT_DRIVER}"
chown -R www-data:www-data "${APP_ROOT}/runtime/browsers"
chmod -R u+rwX,g+rX,o-rwx "${APP_ROOT}/runtime/browsers"

for protected_index in "${!PROTECTED_APP_PATHS[@]}"; do
  relative_path="${PROTECTED_APP_PATHS[${protected_index}]}"
  [[ "$(stat -c '%d:%i' "${APP_ROOT}/${relative_path}")" == \
    "${protected_inode[${protected_index}]}" ]] || \
    fail "protected directory was replaced unexpectedly: ${relative_path}"
done

nginx -t
systemctl daemon-reload
systemctl enable karries-api karries-publish-worker karries-backup.timer >/dev/null
systemctl restart nginx karries-api karries-publish-worker
wait_for_api_ready
"${APP_ROOT}/deploy/server/smoke-test.sh" "${SMOKE_BASE_URL:-http://127.0.0.1}"

DEPLOYMENT_STARTED=0
trap - ERR
cat <<EOF
KARRIES production upgrade completed.
Production database backup: ${DATABASE_BACKUP}
Code rollback point: ${ROLLBACK_ROOT}
The existing MySQL database, application environment, uploads, runtime and logs were preserved.
EOF
