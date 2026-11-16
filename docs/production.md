# Production operations deployment

The root `render.yaml` deploys the Flask operations application as one Docker web
service in Oregon, with a 1 GB persistent disk at `/app/instance`. The Vercel
deployment remains a separate stateless public simulator. The standalone module
services in `modules/` have their own deployment configurations and lifecycles.

## Release

1. Install Python 3.12 and `pip install -r requirements-dev.txt`.
   Runtime pins live in `requirements.txt`; regenerate `requirements.lock` with
   `uv pip compile requirements.txt --python-version 3.12 --universal -o requirements.lock`
   after intentional dependency updates. The image installs the lock.
2. Run `python -m pytest -q` and build the image with `docker build -t sias .`.
   CI also boots the actual image, checks authenticated HTTP and WebSocket flows,
   restarts it, and checks that the administrator account persisted.
3. Validate `render.yaml` against Render's published JSON Schema and, when the
   Render CLI is installed, run `render blueprints validate render.yaml`.
4. Commit and push, wait for CI, and review the Render Blueprint plan before
   applying it. The Blueprint creates `sias-operations`; it does not adopt the
   existing machine-simulator or digital-twin services.
5. Wait until the deploy is live and `/ready` returns 200 over HTTPS.
6. In the service's Render Shell, run `python scripts/manage_users.py` to create
   your administrator. Choose your own password at the prompt; there is no
   default login. Do not put passwords in the Blueprint or Git.
   For an installation without shell access, operators can supply
   `SIAS_INITIAL_ADMIN_USERNAME` and `SIAS_INITIAL_ADMIN_PASSWORD_HASH` at startup.
   The hash must use Werkzeug's `pbkdf2:sha256:1000000` format. This creates an
   administrator only in an empty account store, atomically records completion,
   and never resets existing accounts. Clear both variables after verifying login.
7. Log in over HTTPS and verify customer/site/asset creation, a work order and its
   completion history, account role restrictions, and live dashboard updates.
   Run `python scripts/production_smoke.py https://YOUR-SERVICE.onrender.com`
   from a validation environment with `SIAS_ADMIN_USERNAME` and
   `SIAS_ADMIN_PASSWORD` set securely. This check reads operations data and logs
   its test session out; it does not create or alter customer records.
8. Restart the service, then confirm the same account, asset, and work order
   remain. Record the deployed commit and verification results.

The initial plan uses the smallest paid web compute plan (`0.5c-512mb`). As of
2026-11-16, the listed compute and disk total is approximately $7.25/month,
excluding workspace subscription, bandwidth overages, and taxes. Confirm the
[current pricing](https://render.com/pricing) in the reviewed plan. Monitor memory
and request latency under realistic load before admitting more users.

## Runtime constraints

Keep one Gunicorn worker and one instance. Simulator state, operator sockets, and
metrics are process-local, and SQLite is stored on a single attached disk. This
deployment does not provide high availability; disk-backed releases interrupt
service briefly. Horizontal scaling requires shared state, a Socket.IO message
queue, and a server database before increasing instance counts.

The image runs as UID 10001. The mounted directory must be writable by this user.
`SIAS_COOKIE_SECURE=1` requires HTTPS for login. Render terminates TLS; keep the
application port behind its ingress. Do not enable wildcard forwarded-header
trust for an app port reachable directly from the internet.

`PLC_MODE=sim` is intentional. Real equipment connections require a separately
validated network and engineering setup. A healthy web release does not certify
industrial control safety.

`/health` checks the HTTP process. `/ready` additionally exercises a database
transaction and rejects a stale telemetry loop. It can return 503 on a disk
failure or stalled simulation. Review application logs when this happens.

Optional SMTP delivery remains opt-in. Configure the documented `SIAS_SMTP_*`
variables in Render and invoke `scripts/process_notifications.py --send` from
the same service environment. A separate Render worker cannot share this disk;
move the notification store to a shared database before adding such a worker.

## Backups and restore

From Render Shell, create a consistent database backup:

```sh
python scripts/backup_database.py /app/instance/sias-backup-YYYYMMDD.sqlite3
```

The command refuses to overwrite a file, uses SQLite's live backup API, checks
database integrity, and restricts file permissions. Copy backups to separate
protected storage using Render SSH/SCP. A backup kept only on the application's
disk does not protect against loss of that disk. Schedule and test this procedure
according to the acceptable data-loss window; restrict access because backups
contain customer data, password hashes, sessions, and device credential hashes.

Test restores in an isolated environment first: copy a backup to a new writable
directory, set `SIAS_DATABASE_PATH` to that copy, start the app, and verify account
login, registry data, and work-order history. For production recovery, stop writes
before replacing the database; do not replace a live SQLite file. Preserve a
backup of the failed database and keep the current Render `SECRET_KEY`.

## Rollback

Keep a database backup before each release. Use Render's rollback action for a
known compatible application build, then recheck readiness, login, telemetry,
and persisted operations records. A code rollback does not undo database changes.
Restore a database only when necessary, after checking the backup and explicitly
accounting for records written since it was taken.
