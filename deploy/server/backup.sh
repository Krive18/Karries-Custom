#!/usr/bin/env bash
set -euo pipefail
umask 077

APP_ROOT="/opt/karries"
ENV_FILE="/etc/karries-api.env"
BACKUP_ROOT="/var/backups/karries"
RETENTION_DAYS="${KARRIES_BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DESTINATION="${BACKUP_ROOT}/${TIMESTAMP}"
MYSQL_OPTION_FILE="$(mktemp)"

cleanup() {
  rm -f "${MYSQL_OPTION_FILE}"
}
trap cleanup EXIT

set -a
source "${ENV_FILE}"
set +a

install -d -m 0700 "${DESTINATION}"
cat > "${MYSQL_OPTION_FILE}" <<EOF
[client]
host=${MYSQL_HOST}
port=${MYSQL_PORT}
user=${MYSQL_USER}
password=${MYSQL_PASSWORD}
default-character-set=${MYSQL_CHARSET:-utf8mb4}
EOF

mysqldump \
  --defaults-extra-file="${MYSQL_OPTION_FILE}" \
  --single-transaction \
  --routines \
  --triggers \
  --events \
  --set-gtid-purged=OFF \
  "${MYSQL_DATABASE}" | gzip -9 > "${DESTINATION}/database.sql.gz"

if [[ -d "${APP_ROOT}/data" ]]; then
  tar -C "${APP_ROOT}" -czf "${DESTINATION}/data.tar.gz" data
fi

sha256sum "${DESTINATION}"/* > "${DESTINATION}/SHA256SUMS"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d \
  -mtime "+${RETENTION_DAYS}" -exec rm -rf -- {} +
