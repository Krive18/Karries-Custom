#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

APP_ROOT="/opt/karries"
WEB_ROOT="/var/www/karries"
BACKUP_ROOT="/var/backups/karries"
ROLLBACK_ROOT="${1:-}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
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
  fail "karries-api did not become ready within 30 seconds after rollback"
}

[[ "${EUID}" -eq 0 ]] || fail "run this script with sudo"
command -v curl >/dev/null 2>&1 || fail "missing required command: curl"
if [[ -z "${ROLLBACK_ROOT}" ]]; then
  [[ -L "${BACKUP_ROOT}/last-upgrade" ]] || fail "no last-upgrade rollback point"
  ROLLBACK_ROOT="$(readlink -f "${BACKUP_ROOT}/last-upgrade")"
else
  ROLLBACK_ROOT="$(readlink -f "${ROLLBACK_ROOT}")"
fi
case "${ROLLBACK_ROOT}" in
  "${BACKUP_ROOT}"/upgrade-*) ;;
  *) fail "refusing unexpected rollback directory: ${ROLLBACK_ROOT}" ;;
esac

for required_file in app-code.tar.gz web-static.tar.gz SHA256SUMS; do
  [[ -f "${ROLLBACK_ROOT}/${required_file}" ]] || \
    fail "rollback file is missing: ${required_file}"
done
(cd "${ROLLBACK_ROOT}" && sha256sum --check SHA256SUMS --quiet)

systemctl stop karries-publish-worker karries-api

for target in \
  "${APP_ROOT}/backend/app" \
  "${APP_ROOT}/external" \
  "${APP_ROOT}/deploy" \
  "${APP_ROOT}/web"; do
  case "${target}" in
    "${APP_ROOT}/backend/app"|"${APP_ROOT}/external"|"${APP_ROOT}/deploy"|"${APP_ROOT}/web")
      rm -rf -- "${target}"
      ;;
    *) fail "refusing unexpected application path: ${target}" ;;
  esac
done
rm -f -- \
  "${APP_ROOT}/backend/pyproject.toml" \
  "${APP_ROOT}/DEPLOY.txt" \
  "${APP_ROOT}/UPGRADE-PRESERVE-DATA.txt" \
  "${APP_ROOT}/RELEASE-MANIFEST.json" \
  "${APP_ROOT}/SHA256SUMS"
tar -C "${APP_ROOT}" -xzf "${ROLLBACK_ROOT}/app-code.tar.gz"

failed_venv=""
if [[ -d "${ROLLBACK_ROOT}/previous-venv" ]]; then
  if [[ -d "${APP_ROOT}/backend/.venv" ]]; then
    failed_venv="${ROLLBACK_ROOT}/failed-venv-$(date -u +%Y%m%dT%H%M%SZ)"
    mv "${APP_ROOT}/backend/.venv" "${failed_venv}"
  fi
  mv "${ROLLBACK_ROOT}/previous-venv" "${APP_ROOT}/backend/.venv"
else
  [[ -x "${APP_ROOT}/backend/.venv/bin/python" ]] || \
    fail "neither the previous nor current virtualenv is usable"
fi

for portal in customer manager developer; do
  portal_root="${WEB_ROOT}/${portal}"
  install -d -m 0755 "${portal_root}"
  find "${portal_root}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
done
tar -C "${WEB_ROOT}" -xzf "${ROLLBACK_ROOT}/web-static.tar.gz"

for unit in \
  karries-api.service \
  karries-publish-worker.service \
  karries-backup.service \
  karries-backup.timer; do
  [[ -f "${ROLLBACK_ROOT}/system/${unit}" ]] && \
    install -m 0644 "${ROLLBACK_ROOT}/system/${unit}" \
      "/etc/systemd/system/${unit}"
done

systemctl daemon-reload
nginx -t
systemctl restart nginx karries-api karries-publish-worker
wait_for_api_ready
"${APP_ROOT}/deploy/server/smoke-test.sh" "${SMOKE_BASE_URL:-http://127.0.0.1}"

cat <<EOF
Previous KARRIES application code and static files were restored.
The production database and writable data directories were not restored or replaced.
Failed new virtualenv retained at: ${failed_venv:-not applicable}
EOF
