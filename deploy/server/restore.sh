#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

BACKUP_DIR="${1:-}"
APP_ROOT="/opt/karries"
ENV_FILE="/etc/karries-api.env"
MYSQL_OPTION_FILE="$(mktemp)"

cleanup() {
  rm -f "${MYSQL_OPTION_FILE}"
}
trap cleanup EXIT

if [[ -z "${BACKUP_DIR}" || ! -d "${BACKUP_DIR}" ]]; then
  echo "Usage: sudo $0 /var/backups/karries/<timestamp>" >&2
  exit 1
fi

if [[ ! -f "${BACKUP_DIR}/SHA256SUMS" || ! -f "${BACKUP_DIR}/database.sql.gz" ]]; then
  echo "Backup is incomplete: ${BACKUP_DIR}" >&2
  exit 1
fi

(
  cd "${BACKUP_DIR}"
  sha256sum --check SHA256SUMS
)

set -a
source "${ENV_FILE}"
set +a

cat > "${MYSQL_OPTION_FILE}" <<EOF
[client]
host=${MYSQL_HOST}
port=${MYSQL_PORT}
user=${MYSQL_USER}
password=${MYSQL_PASSWORD}
default-character-set=${MYSQL_CHARSET:-utf8mb4}
EOF

systemctl stop karries-publish-worker karries-api
trap 'systemctl start karries-api karries-publish-worker || true; cleanup' EXIT

gzip -dc "${BACKUP_DIR}/database.sql.gz" | mysql \
  --defaults-extra-file="${MYSQL_OPTION_FILE}" \
  "${MYSQL_DATABASE}"

if [[ -f "${BACKUP_DIR}/data.tar.gz" ]]; then
  rm -rf "${APP_ROOT}/data.restore"
  install -d -o www-data -g www-data -m 0750 "${APP_ROOT}/data.restore"
  tar -C "${APP_ROOT}/data.restore" --strip-components=1 \
    -xzf "${BACKUP_DIR}/data.tar.gz"
  rm -rf "${APP_ROOT}/data.previous"
  if [[ -d "${APP_ROOT}/data" ]]; then
    mv "${APP_ROOT}/data" "${APP_ROOT}/data.previous"
  fi
  mv "${APP_ROOT}/data.restore" "${APP_ROOT}/data"
  chown -R www-data:www-data "${APP_ROOT}/data"
fi

systemctl start karries-api karries-publish-worker
curl --retry 12 --retry-delay 2 --retry-connrefused \
  --fail --silent --show-error \
  http://127.0.0.1:8765/api/ready
echo
echo "Restore completed from ${BACKUP_DIR}."
trap cleanup EXIT
