# Local validation — 2026-11-15

All requested outstanding module checks passed. No application changes were needed.

| Check | Result |
| --- | --- |
| Predictive-maintenance backend | 13 passed, 0 skipped |
| Digital-twin backend, application retention | 23 passed, 0 skipped |
| Digital-twin backend, TimescaleDB policy retention | 22 passed; application-only retention test skipped as designed |
| Digital-twin database integration tests, application retention | 2 passed, 0 skipped |
| Predictive-maintenance frontend | TypeScript check and production build passed |
| Digital-twin frontend | 5 tests passed; TypeScript check and production build passed |

Runtime: CPython 3.12.16 in `/private/tmp/sias-validation-py312`, Node.js 24.21.0,
npm 11.19.0. Backend dependencies were installed from both modules' requirements;
frontend dependencies were installed using `npm ci` and the existing lockfiles.
Both frontends built with Next.js 16.4.3.

## Commands

From `modules/predictive-maintenance/backend`:

```sh
/private/tmp/sias-validation-py312/bin/python -m pytest tests -q
```

From each module's `frontend` directory:

```sh
npm ci --no-audit --no-fund
npm run typecheck
npm run build
```

Digital twin also ran `npm test`.

## Isolated database checks

Used a temporary Docker container bound to `127.0.0.1:55432`, with PostgreSQL
17.11 and TimescaleDB 2.31.0. Image:
`timescale/timescaledb@sha256:b56a3f51991df1f79d0c1a0841cad5c5fa8058fdd6a3ee6886394a6d4c174538`.
No existing database or persistent volume was used.

Applied `modules/digital-twin/database/001_telemetry.sql` to `sias_twin`.
Applied `modules/digital-twin/database/neon/001_telemetry.sql` to the separate
`sias_application_validation` database. From `modules/digital-twin/backend`, ran:

```sh
TEST_DATABASE_URL=postgresql://sias:sias_test_only@127.0.0.1:55432/sias_twin \
TEST_RETENTION_MODE=timescaledb \
/private/tmp/sias-validation-py312/bin/python -m pytest tests -q

TEST_DATABASE_URL=postgresql://sias:sias_test_only@127.0.0.1:55432/sias_application_validation \
TEST_RETENTION_MODE=application \
/private/tmp/sias-validation-py312/bin/python -m pytest tests -q
```

The application mode also passed a separate run of `tests/test_storage_integration.py`.
Checks cover persistence across store restarts, source isolation, hypertable
provisioning, retention-policy presence, and removal of old chunks while retaining
recent data. Predictive-maintenance tests cover SQLite migration and work-order
persistence across Python process restarts.

## Limits

Backend suites emitted a Starlette deprecation warning about using `httpx` with
`TestClient`; no failures resulted. The first predictive-maintenance run took
120.49 seconds while macOS loaded native PyTorch libraries; a concurrent follow-up
also passed (24.89 seconds).

Application retention was checked on full-edition TimescaleDB using the alternative
migration, not on hosted Neon. Builds and unit/integration tests do not verify
interactive browser workflows, hosted deployment, or provider volume persistence.
The temporary database container was removed after validation.
