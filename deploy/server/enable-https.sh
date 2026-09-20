#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

DOMAIN="${1:-}"
EMAIL="${2:-}"
NGINX_SITE="/etc/nginx/sites-available/karries"

if [[ -z "${DOMAIN}" || -z "${EMAIL}" ]]; then
  echo "Usage: sudo $0 <domain> <email>" >&2
  exit 1
fi

if [[ ! "${DOMAIN}" =~ ^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$ ]]; then
  echo "Invalid domain: ${DOMAIN}" >&2
  exit 1
fi

if [[ ! "${EMAIL}" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
  echo "Invalid email address." >&2
  exit 1
fi

if [[ ! -f "${NGINX_SITE}" ]]; then
  echo "Nginx site was not found at ${NGINX_SITE}." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx

cp "${NGINX_SITE}" "${NGINX_SITE}.before-https"
sed -i -E "s/^[[:space:]]*server_name[[:space:]]+[^;]+;/    server_name ${DOMAIN};/" \
  "${NGINX_SITE}"

nginx -t
systemctl reload nginx

certbot --nginx \
  --non-interactive \
  --agree-tos \
  --redirect \
  --email "${EMAIL}" \
  --domain "${DOMAIN}"

nginx -t
systemctl reload nginx
curl -fsS "https://${DOMAIN}/api/ready"
echo
echo "HTTPS enabled: https://${DOMAIN}/"
