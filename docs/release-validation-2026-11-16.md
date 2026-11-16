# Operations release validation — 2026-11-16

Scope: the root Flask operations application. These checks do not verify the
separate module deployments, hosted browser workflows, production load capacity,
or industrial equipment safety.

## Local results

- CPython 3.12.16: `python -m pytest -q` — 115 passed, 64 subtests passed.
- After the final checkpoint cleanup change: `python -m pytest tests/test_core.py -q`
  — 50 passed.
- `python -m pip check` — no broken requirements.
- `python -m pip_audit -r requirements-dev.txt` — no known vulnerabilities in
  the locked production dependencies or the declared validation dependencies.
- `render.yaml` validated against the current public Render JSON Schema.
- Gunicorn on a non-default port passed `scripts/production_smoke.py`, including
  account login, protected pages/APIs, actual WebSocket connection and telemetry,
  CSRF rejection, logout, and authentication rejection after logout.
- Restarted Gunicorn against the same isolated SQLite database and repeated the
  smoke check successfully, confirming account persistence across processes.

All server checks used a temporary database and a randomly generated validation
administrator; no customer records or existing production services were changed.

## Release gates

Review the actual Render Blueprint plan before applying it. After deployment,
verify the Render disk permissions, HTTPS login, asset and work-order browser
flows, data survival after a service restart, off-service backup/restore, and
resource usage under expected traffic. See [the runbook](production.md).
