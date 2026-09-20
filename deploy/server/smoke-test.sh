#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"
BASE_URL="${BASE_URL%/}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

check_page() {
  local path="$1"
  local name="$2"
  local output="${TMP_DIR}/${name}.html"

  curl --fail --silent --show-error \
    --connect-timeout 5 \
    --max-time 20 \
    "${BASE_URL}${path}" > "${output}"
  if [[ ! -s "${output}" ]]; then
    echo "${name} returned an empty response." >&2
    exit 1
  fi
  echo "PASS ${name}: ${BASE_URL}${path}"
}

check_api() {
  local path="$1"
  local name="$2"
  local output="${TMP_DIR}/${name}.json"

  curl --fail --silent --show-error \
    --connect-timeout 5 \
    --max-time 20 \
    "${BASE_URL}${path}" > "${output}"
  python3 - "${output}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    payload = json.load(source)
if payload.get("success") is not True:
    raise SystemExit(f"API check failed: {payload!r}")
PY
  echo "PASS ${name}: ${BASE_URL}${path}"
}

check_service() {
  local name="$1"

  if ! systemctl is-active --quiet "${name}"; then
    systemctl status "${name}" --no-pager >&2 || true
    echo "${name} is not active." >&2
    exit 1
  fi
  echo "PASS service: ${name}"
}

check_service "karries-api"
check_service "karries-publish-worker"
check_page "/" "customer"
check_page "/manager/" "manager"
check_page "/developer/" "developer"
check_api "/api/health" "health"
check_api "/api/ready" "readiness"

echo "All production smoke checks passed."
