# Module 2 final integration audit

## Scope and decision

The organization module implementation covers eight organization resources, scoped tenancy, transactional write auditing, bulk APIs, OpenAPI and the React interface. See [implementation and prompt ledger](M2_IMPLEMENTATION.md). Deployment examples and the [operations guide](M2_DEPLOYMENT.md) are supplied. This is not production release approval.

## Findings and release gates

| Severity | Finding | Status / required evidence |
| --- | --- | --- |
| High | Production infrastructure and recovery have not been exercised | Stage the Linux deployment, resolve/audit its production lock, validate proxy/service configuration and rehearse backup restore before release. |
| High | Interactive browser acceptance outstanding | No browser was connected. Complete role-separated login, forms, mobile/keyboard navigation, PWA install/update and multi-tab scenarios. Component tests do not replace these checks. |
| Medium | MariaDB compatibility unverified | Tests use MySQL. Independently verify any MariaDB target before deployment. |
| Medium | Offline scope narrower than requested persistent read access | Implemented opt-in user-bound tab memory with five-minute lifetime. Offline reload cannot restore a copy; accept this limit or commission separately reviewed persistent storage. |
| Medium | CSV onboarding has API coverage but no dedicated UI | Use documented import-template/dry-run/import/export APIs; dedicated screens remain future work. |
| Medium | Existing legacy database adoption requires review | Initial migrations target the new Django database; no automatic adoption of an imported full schema. |
| Low | HSTS subdomains/preload intentionally opt-in | Production checks report W005/W021 until those deployment-wide policies are explicitly enabled. |

## Verification evidence

Final automated results are recorded below after running `scripts/verify-module2.ps1`. That script checks Django/database configuration, focused runtime-error lint, backend tests and organization/tenancy statement coverage, migration drift, OpenAPI validation, frontend tests and production build. Coverage excludes migrations and tests and has a 75% floor. It does not establish complete branch coverage.

Earlier dependency checks: backend pinned runtime requirements audit found no known vulnerabilities after upgrading DRF to 3.17.2; `pip check` passed; frontend production dependency audit reported zero vulnerabilities. Audit results are time-specific and exclude a separately resolved Linux/Gunicorn production lock. DRF change reference: https://www.django-rest-framework.org/community/release-notes/ .

## Security and integrity boundaries

Queryset filtering enforces authorization before list/count/detail selection; object checks alone are insufficient. Parent selection, bulk operations and snapshots use the same scope. Database constraints remain the concurrent-write defense. Data and audit events commit together. Ordinary APIs expose no hard deletion. Parent deactivation does not cascade; active dropdowns hide ineffective parents while unchanged historical selections remain visible.

Platform audit access is restricted and ordinary mutation is disabled. Application append-only behavior is not DBA-proof tamper protection. The organization tenancy foundation does not automatically authorize future student, staff, curriculum or registration modules. Those modules require their own scoped data and permission design.

## Final automated run — 2026-09-20

`scripts/verify-module2.ps1` completed successfully against running MySQL:

| Check | Result |
| --- | --- |
| Django/database system checks | No issues |
| Organization/tenancy runtime-error lint | Passed |
| Backend pytest suite | 80 passed |
| Organization/tenancy statement coverage | 96.40% (722 statements, 26 missed) |
| Migration drift | No changes detected |
| OpenAPI validation with fail-on-warning | Passed |
| Frontend Node tests | 10 passed |
| Frontend Vitest component/offline tests | 6 passed |
| TypeScript and Vite/PWA production build | Passed |

This run does not close the browser, staging, Linux dependency or recovery gates above. The verification script can be used as a Windows CI job with a disposable MySQL database and installed development dependencies; no hosted CI run is claimed.
