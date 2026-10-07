# Prompt 9 - Release verification

Date: 2026-09-17. Status: backend verification subsequently passed during Prompt 6 reverification; browser acceptance remains pending.

**Latest result:** MySQL is available; all 38 backend tests pass, including the new authenticated workflow. Corrected its logout assertion to the existing 204 response contract. Migration drift check passes and core.0001_initial is applied. The initial blocked results below are retained as session history, not the current database status.

## Changes

- Fixed test settings loading: backend/.env is now loaded before test-only defaults. Previously the placeholder SIMS_DB_PASSWORD shadowed the configured local password, making the documented test command fail even when MySQL was available. Explicit shell environment variables still take precedence.
- Added test_release.py: a workflow through real CSRF/login/JWT endpoints, country/state creation, parent deactivation, historical editing, actor-linked audit events, refresh, permission revocation, logout, and anonymous rejection. It does not use force_authenticate.
- Added scripts/verify-release.ps1: a repeatable, fail-fast gate for backend tests, migration drift, OpenAPI, frontend tests, and production build. It never starts migrations or seeds records. Backend test execution uses the disposable test_sims_reference database.

## Results this session

| Check | Result |
| --- | --- |
| Frontend client/permission/PWA tests | PASS: 10 tests |
| TypeScript and production build | PASS |
| PWA generation | PASS: 11 public precache entries |
| OpenAPI generation and validation with fail-on-warn | PASS |
| Django system checks | PASS |
| Backend MySQL tests | BLOCKED: MySQL connection refused; no tests executed |
| New authenticated workflow test | Added; not executed against MySQL |
| Database-backed migration verification | Pending database availability |
| Browser login/forms/permissions | BLOCKED: browser discovery returned no connected browsers |
| PWA installation/offline/update acceptance | Pending browser connection |
| Mobile layout and keyboard accessibility | Pending browser connection |

The prior 37-test backend pass belongs to Prompt 6; it is not a result from this session. The new test increases the intended suite to 38. Django system checks and schema generation do not prove a working database connection.

## Environment blockers

Attempted to launch Docker Desktop and run the project's compose service, including an execution outside the sandbox. Docker reported that the dockerDesktopLinuxEngine named pipe does not exist. The Linux engine must finish starting before backend verification can proceed. No container volume was deleted, no database was reset, and no working reference records were altered.

Browser discovery returned an empty list. No interactive browser checks were performed, and this document is not release approval.

## Resume automated checks

Start Docker Desktop with its Linux engine, then run from the workspace root:

```powershell
docker compose --env-file backend/.env up -d --wait
powershell -NoProfile -File scripts/verify-release.ps1
```

The verification script stops at the first failure. It regenerates backend/openapi.yaml and frontend/dist. Keep credentials in backend/.env; do not substitute SQLite for the MySQL schema/collation/concurrency checks.

## Browser acceptance checklist

Run Django on 127.0.0.1:8000 and the production frontend preview on 127.0.0.1:4173. Use dedicated test accounts and clearly identified disposable reference data; do not alter official classifications to test the UI.

1. Login, invalid credentials, page reload/session restoration, logout, and expired session.
2. Reader sees permitted resources and no write controls. Maintainer can write only with the required model grants. Revoke a permission and verify server denial.
3. Create, edit, search, order, and paginate all ten resources; test duplicate and invalid values.
4. Filter states/castes/sub-castes by parents; test uncategorized castes. Deactivate a parent and confirm historical choices remain visible while new choices are excluded.
5. Confirm create/update/deactivate/reactivate audit events and actor identity. Verify audit read restrictions and disabled deletion.
6. Install the PWA; inspect cached public asset URLs; confirm no API/admin responses are cached. Load the shell offline and reconnect.
7. Build an update with a dirty form open. Confirm no automatic reload and that the save-before-update confirmation works. Repeat with multiple open tabs.
8. At narrow viewport widths, check navigation, table scrolling, dialogs, labels, tab order, keyboard parent selection, focus trapping, and readable error messages.

Record actual outcomes and defects here once these checks can run. Production deployment and Institution/Campus implementation remain outside this verification step.
