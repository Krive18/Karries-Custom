# KARRIES Production Operations

## Service checks

```bash
sudo systemctl status karries-api karries-publish-worker nginx mysql
curl -fsS http://127.0.0.1:8765/api/health
curl -fsS http://127.0.0.1:8765/api/ready
```

`/api/health` confirms that the API process is alive. `/api/ready` also
checks the database and must be used by monitoring and deployment checks.

## Logs and request tracing

```bash
sudo journalctl -u karries-api -n 200 --no-pager
sudo journalctl -u karries-publish-worker -n 200 --no-pager
sudo tail -n 200 /var/log/nginx/karries-access.log
sudo tail -n 200 /var/log/nginx/karries-error.log
```

Every API response includes `X-Request-ID`. Search that value in the API
journal and Nginx access log when tracing a failed request.

## Xiaohongshu publishing worker

The API creates and leases due publish tasks. `karries-publish-worker` owns
the browser automation process that claims those tasks and reports success,
retry, or manual takeover.

```bash
sudo systemctl restart karries-publish-worker
sudo systemctl is-active karries-publish-worker
sudo -u www-data env \
  PLAYWRIGHT_BROWSERS_PATH=/opt/karries/runtime/browsers \
  /opt/karries/backend/.venv/bin/python -m patchright install --list
```

If Chromium is missing after an operating-system upgrade:

```bash
sudo PLAYWRIGHT_BROWSERS_PATH=/opt/karries/runtime/browsers \
  /opt/karries/backend/.venv/bin/python -m patchright install --with-deps chromium
sudo chown -R www-data:www-data /opt/karries/runtime/browsers
sudo chmod -R u+rwX,g+rX,o-rwx /opt/karries/runtime/browsers
sudo systemctl restart karries-publish-worker
```

An expired Xiaohongshu login state or a platform security challenge is not
retried indefinitely. The task moves to manual takeover and the account must
be logged in again.

## Backup and restore

`karries-backup.timer` creates a daily MySQL dump and archives local uploads.
Backups are stored under `/var/backups/karries` and must also be copied to
encrypted off-host storage.

```bash
sudo systemctl list-timers karries-backup.timer
sudo systemctl start karries-backup.service
sudo journalctl -u karries-backup.service -n 100 --no-pager
```

Restore must be rehearsed before launch. The restore script verifies every
backup file before stopping application services:

```bash
sudo /opt/karries/deploy/server/restore.sh \
  /var/backups/karries/<backup>
```

## HTTPS and deployment smoke test

After DNS points to this server, enable a Let's Encrypt certificate:

```bash
sudo /opt/karries/deploy/server/enable-https.sh \
  hys-karries.com ops@example.com
```

After every deployment, check the customer, manager, and developer
applications plus both API health endpoints:

```bash
sudo /opt/karries/deploy/server/smoke-test.sh https://hys-karries.com
```

## First-login credentials

Initial credentials are written once to
`/root/karries-initial-credentials`. Change all three passwords immediately,
then remove that file. Never copy credentials into tickets or chat messages.

## Alerts

Create alerts for:

- `/api/ready` failing twice in succession
- API 5xx rate above 2% for five minutes
- P95 API latency above two seconds for five minutes
- CPU above 80% for ten minutes
- memory above 85%
- disk above 80%
- publish worker inactive or restarting repeatedly
- backup failure or no new backup for 26 hours

## Release and rollback

Keep each uploaded release in a versioned directory and make
`/opt/karries` a symlink to the active version. Run the installer, readiness
check, and a login smoke test before switching traffic. To roll back, point
the symlink to the previous release and restart the API and worker. Database
schema changes require a forward repair migration or a verified backup
restore; never roll back only the application when the schema is incompatible.
