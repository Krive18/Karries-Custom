#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/server/install.sh"
  exit 1
fi

APP_ROOT="/opt/karries"
WEB_ROOT="/var/www/karries"
ENV_FILE="/etc/karries-api.env"
BOOTSTRAP_FILE="/etc/karries-bootstrap.env"
CREDENTIALS_FILE="/root/karries-initial-credentials"

generate_hex_secret() {
  python3 -c 'import secrets; print(secrets.token_hex(32))'
}

read_env_value() {
  local file="$1"
  local key="$2"
  [[ -f "${file}" ]] || return 0
  awk -F= -v key="${key}" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "${file}"
}

resolve_secret() {
  local override="$1"
  local file="$2"
  local key="$3"
  local existing=""
  if [[ -n "${override}" ]]; then
    printf '%s' "${override}"
    return
  fi
  existing="$(read_env_value "${file}" "${key}")"
  if [[ -n "${existing}" ]]; then
    printf '%s' "${existing}"
    return
  fi
  generate_hex_secret
}

require_safe_secret() {
  local label="$1"
  local value="$2"
  if [[ ! "${value}" =~ ^[A-Za-z0-9._@%+=:,/-]{16,128}$ ]]; then
    echo "${label} must be 16-128 characters and contain only safe password characters." >&2
    exit 1
  fi
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local escaped_value="${value//\\/\\\\}"
  escaped_value="${escaped_value//&/\\&}"
  escaped_value="${escaped_value//|/\\|}"
  if grep -q "^${key}=" "${file}" 2>/dev/null; then
    sed -i "s|^${key}=.*$|${key}=${escaped_value}|" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

ensure_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  if ! grep -q "^${key}=" "${file}" 2>/dev/null; then
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  nginx mysql-server python3 python3-venv python3-pip

install -d -o www-data -g www-data -m 0750 \
  "${APP_ROOT}/data" \
  "${APP_ROOT}/logs" \
  "${APP_ROOT}/runtime" \
  "${APP_ROOT}/runtime/browsers"

install -d -m 0755 \
  "${WEB_ROOT}/customer" \
  "${WEB_ROOT}/manager" \
  "${WEB_ROOT}/developer"
rm -rf \
  "${WEB_ROOT}/customer/"* \
  "${WEB_ROOT}/manager/"* \
  "${WEB_ROOT}/developer/"*
cp -a "${APP_ROOT}/web/customer/." "${WEB_ROOT}/customer/"
cp -a "${APP_ROOT}/web/manager/." "${WEB_ROOT}/manager/"
cp -a "${APP_ROOT}/web/developer/." "${WEB_ROOT}/developer/"
if [[ -f "${WEB_ROOT}/manager/manager.html" ]]; then
  install -m 0644 \
    "${WEB_ROOT}/manager/manager.html" \
    "${WEB_ROOT}/manager/index.html"
fi
if [[ -f "${WEB_ROOT}/developer/developer.html" ]]; then
  install -m 0644 \
    "${WEB_ROOT}/developer/developer.html" \
    "${WEB_ROOT}/developer/index.html"
fi

python3 -m venv "${APP_ROOT}/backend/.venv"
"${APP_ROOT}/backend/.venv/bin/pip" install --upgrade pip
"${APP_ROOT}/backend/.venv/bin/pip" install -e "${APP_ROOT}/backend"
PLAYWRIGHT_BROWSERS_PATH="${APP_ROOT}/runtime/browsers" \
  "${APP_ROOT}/backend/.venv/bin/python" -m patchright install --with-deps chromium

if [[ ! -f "${ENV_FILE}" ]]; then
  AUTH_SECRET="$(generate_hex_secret)"
  ENCRYPTION_KEY="$(generate_hex_secret)"
  WORKER_TOKEN="$(generate_hex_secret)"
  cat > "${ENV_FILE}" <<EOF
XHS_ENV=production
XHS_AUTH_TOKEN_SECRET=${AUTH_SECRET}
AI_SETTINGS_ENCRYPTION_KEY=${ENCRYPTION_KEY}
WORKER_API_TOKEN=${WORKER_TOKEN}
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=xhs_publisher
MYSQL_USER=xhs_publisher
MYSQL_CHARSET=utf8mb4
MYSQL_CONNECT_TIMEOUT=5
MYSQL_READ_TIMEOUT=15
MYSQL_WRITE_TIMEOUT=15
MYSQL_POOL_SIZE=10
MYSQL_POOL_TIMEOUT=10
MYSQL_POOL_RECYCLE=1800
MYSQL_POOL_PRE_PING=1
MYSQL_RECONNECT_RETRY_SECONDS=5
SAU_LOG_DIR=/opt/karries/logs/social
XHS_CORS_ALLOWED_ORIGINS=
XHS_EXPOSE_API_DOCS=0
XHS_EMBEDDED_PUBLISH_WORKER=0
EOF
fi

ensure_env_value "${ENV_FILE}" "MYSQL_POOL_SIZE" "10"
ensure_env_value "${ENV_FILE}" "MYSQL_POOL_TIMEOUT" "10"
ensure_env_value "${ENV_FILE}" "MYSQL_POOL_RECYCLE" "1800"
ensure_env_value "${ENV_FILE}" "MYSQL_POOL_PRE_PING" "1"
ensure_env_value "${ENV_FILE}" "MYSQL_RECONNECT_RETRY_SECONDS" "5"
ensure_env_value "${ENV_FILE}" "SAU_LOG_DIR" "/opt/karries/logs/social"

MYSQL_PASSWORD="$(resolve_secret "${KARRIES_MYSQL_PASSWORD:-}" "${ENV_FILE}" "MYSQL_PASSWORD")"
require_safe_secret "MySQL password" "${MYSQL_PASSWORD}"
set_env_value "${ENV_FILE}" "MYSQL_PASSWORD" "${MYSQL_PASSWORD}"
chmod 600 "${ENV_FILE}"

touch "${BOOTSTRAP_FILE}"
chmod 600 "${BOOTSTRAP_FILE}"
MANAGER_PASSWORD="$(resolve_secret "${KARRIES_MANAGER_PASSWORD:-}" "${BOOTSTRAP_FILE}" "KARRIES_MANAGER_PASSWORD")"
DEVELOPER_PASSWORD="$(resolve_secret "${KARRIES_DEVELOPER_PASSWORD:-}" "${BOOTSTRAP_FILE}" "KARRIES_DEVELOPER_PASSWORD")"
require_safe_secret "Manager password" "${MANAGER_PASSWORD}"
require_safe_secret "Developer password" "${DEVELOPER_PASSWORD}"
set_env_value "${BOOTSTRAP_FILE}" \
  "KARRIES_MANAGER_USERNAME" "${KARRIES_MANAGER_USERNAME:-Karries_admin}"
set_env_value "${BOOTSTRAP_FILE}" \
  "KARRIES_MANAGER_PASSWORD" "${MANAGER_PASSWORD}"
set_env_value "${BOOTSTRAP_FILE}" \
  "KARRIES_DEVELOPER_USERNAME" "${KARRIES_DEVELOPER_USERNAME:-admin}"
set_env_value "${BOOTSTRAP_FILE}" \
  "KARRIES_DEVELOPER_PASSWORD" "${DEVELOPER_PASSWORD}"

cat > "${CREDENTIALS_FILE}" <<EOF
Initial KARRIES privileged accounts
Manager:   ${KARRIES_MANAGER_USERNAME:-Karries_admin}   Password: ${MANAGER_PASSWORD}
Developer: ${KARRIES_DEVELOPER_USERNAME:-admin}         Password: ${DEVELOPER_PASSWORD}

Employee accounts are not pre-created. Create them from the manager portal.
EOF
chmod 600 "${CREDENTIALS_FILE}"

mysql <<SQL
CREATE DATABASE IF NOT EXISTS xhs_publisher
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'xhs_publisher'@'127.0.0.1' IDENTIFIED BY '${MYSQL_PASSWORD}';
ALTER USER 'xhs_publisher'@'127.0.0.1' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON xhs_publisher.* TO 'xhs_publisher'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

set -a
source "${ENV_FILE}"
source "${BOOTSTRAP_FILE}"
set +a
PYTHONPATH="${APP_ROOT}/backend" \
  "${APP_ROOT}/backend/.venv/bin/python" "${APP_ROOT}/deploy/server/seed_users.py"
unset \
  KARRIES_MANAGER_USERNAME \
  KARRIES_MANAGER_PASSWORD \
  KARRIES_DEVELOPER_USERNAME \
  KARRIES_DEVELOPER_PASSWORD

cp "${APP_ROOT}/deploy/server/nginx-ip.conf" /etc/nginx/sites-available/karries
ln -sfn /etc/nginx/sites-available/karries /etc/nginx/sites-enabled/karries
rm -f /etc/nginx/sites-enabled/default
cp "${APP_ROOT}/deploy/server/karries-api.service" /etc/systemd/system/karries-api.service
cp "${APP_ROOT}/deploy/server/karries-publish-worker.service" \
  /etc/systemd/system/karries-publish-worker.service
cp "${APP_ROOT}/deploy/server/karries-backup.service" /etc/systemd/system/karries-backup.service
cp "${APP_ROOT}/deploy/server/karries-backup.timer" /etc/systemd/system/karries-backup.timer
chmod 0755 \
  "${APP_ROOT}/deploy/server/backup.sh" \
  "${APP_ROOT}/deploy/server/restore.sh" \
  "${APP_ROOT}/deploy/server/smoke-test.sh" \
  "${APP_ROOT}/deploy/server/enable-https.sh"

chown -R root:root "${APP_ROOT}/backend" "${WEB_ROOT}"
find "${APP_ROOT}/backend" \
  -path "${APP_ROOT}/backend/.venv" -prune -o \
  -type d -exec chmod 0755 {} +
find "${APP_ROOT}/backend" \
  -path "${APP_ROOT}/backend/.venv" -prune -o \
  -type f -exec chmod 0644 {} +
find "${WEB_ROOT}" -type d -exec chmod 0755 {} +
find "${WEB_ROOT}" -type f -exec chmod 0644 {} +
find "${APP_ROOT}/backend/.venv/bin" -type f -exec chmod 0755 {} +
PATCHRIGHT_DRIVER="$(find "${APP_ROOT}/backend/.venv/lib" \
  -path "*/site-packages/patchright/driver/node" -type f -print -quit)"
if [[ -z "${PATCHRIGHT_DRIVER}" ]]; then
  echo "Patchright driver was not installed." >&2
  exit 1
fi
chmod 0755 "${PATCHRIGHT_DRIVER}"
chown -R www-data:www-data "${APP_ROOT}/runtime/browsers"
chmod -R u+rwX,g+rX,o-rwx "${APP_ROOT}/runtime/browsers"
install -d -o root -g root -m 0700 /var/backups/karries

nginx -t
systemctl daemon-reload
systemctl enable --now \
  mysql nginx karries-api karries-publish-worker karries-backup.timer
systemctl restart nginx karries-api karries-publish-worker

"${APP_ROOT}/deploy/server/smoke-test.sh" http://127.0.0.1

KARRIES_PUBLIC_HOST="${1:-${KARRIES_PUBLIC_HOST:-$(curl -4s https://api.ipify.org 2>/dev/null || true)}}"
if [[ -z "${KARRIES_PUBLIC_HOST}" ]]; then
  KARRIES_PUBLIC_HOST="YOUR_SERVER_IP"
fi

echo "Customer:  http://${KARRIES_PUBLIC_HOST}/"
echo "Manager:   http://${KARRIES_PUBLIC_HOST}/manager/"
echo "Developer: http://${KARRIES_PUBLIC_HOST}/developer/"
echo "Health:    http://${KARRIES_PUBLIC_HOST}/api/health"
echo "Readiness: http://${KARRIES_PUBLIC_HOST}/api/ready"
echo "Initial credentials: ${CREDENTIALS_FILE} (root-only)"
