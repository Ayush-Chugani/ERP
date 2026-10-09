# Operations runbook

## Release checklist
1. CI green (lint, tests and coverage gate, frontend build, image builds, dependency audit, secret scan).
2. Tag `vX.Y.Z`; the CD workflow builds the images and pushes them to GHCR.
3. Take a database backup (below). Run `python -m app.cli migrate`. Roll out `api`, `worker`, `web`.
4. Smoke test: `/api/v1/health/ready` returns `ok`, sign in, open the dashboard.
5. Rollback: redeploy the previous image tag. Migrations are kept backward compatible within a release; otherwise restore the backup.

## Backups and restore
- Supabase: enable daily backups / PITR in the project settings; additionally `pg_dump --format=custom` weekly to separate storage.
- Restore drill (quarterly): restore into a scratch project, run `app.cli migrate`, check `/health/ready`, sign in.
- Uploaded files live in the configured storage bucket; back it up on the same cadence.

## Monitoring and SLOs
- Probes: `/api/v1/health/live` (process), `/api/v1/health/ready` (database and schema revision).
- Every response carries `X-Request-ID`; logs are one line per request with that id.
- Alert on: 5xx rate > 1 % for 5 min, p95 > 800 ms, ready failing, dead jobs > 0 (`/ops/jobs?status=dead`).
- Targets: availability 99.5 %, p95 < 500 ms for list/read endpoints.

## Incident response
1. Triage using the request id from the user's error message; search logs.
2. Suspected credential exposure: rotate `SIMS_SECRET_KEY` (signs everyone out), the database password and the AI key; revoke sessions of affected users.
3. Review `/security/audit` (append-only) for the affected window.
4. Write a post-incident note: timeline, impact, fix, follow-ups.

## Routine
- The worker must run (`python -m app.cli worker`): housekeeping, notifications, evidence-expiry reminders.
- Review dead jobs weekly and retry them from the admin Jobs page.
- Update dependencies monthly (`uv lock --upgrade`, `npm update`); CI audits them on every push.
