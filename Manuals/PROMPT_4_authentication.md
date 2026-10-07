# Prompt 4 ? browser authentication and permissions

## Files

Added accounts/views.py, urls.py, permissions.py, tests.py; frontend/src/features/auth/session.ts and frontend/tests/session.test.cjs; deploy/sims-token-cleanup.cron and auth-rate-limit.conf.example. Updated split settings, URL root, seed_role_groups, OpenAPI, frontend package scripts and this handover. No user schema change or new migration is required.

## Endpoints and cookies

All paths start `/api/v1/auth/`:

| Endpoint | Behavior |
|---|---|
| GET csrf/ | Public bootstrap returns masked csrfToken and sets CSRF cookie |
| POST login/ | username/password only; returns access and new csrfToken, sets refresh cookie |
| POST refresh/ | Reads refresh from cookie, returns access, rotates cookie and blacklists consumed token |
| POST logout/ | Blacklists current refresh when valid, deletes refresh cookie; idempotent for absent/expired tokens |
| GET me/ | Bearer authentication; current ID, username, groups, permissions and superuser state |

Access lasts five minutes and lives only in module memory. Refresh lifetime is one day, cookie `sims_refresh`, HttpOnly, SameSite=Strict, path `/api/v1/auth/`, host-only. Secure is enabled by default/production and disabled explicitly for localhost development. Cookie deletion repeats path/security flags. Auth responses use Cache-Control: no-store. No credential is stored in localStorage, IndexedDB or worker caches; no service worker is registered at this stage.

Unsafe auth requests require both a valid X-CSRFToken and an Origin matching the current origin or an explicitly configured trusted development origin. Missing Origin is deliberately rejected, including command-line POST clients unless they supply it. CSRF checks are explicit because APIView's normal dispatch is exempt. Login rotates CSRF; use its returned token afterward. Bootstrap allows JavaScript to obtain a masked token even though the CSRF cookie itself is HttpOnly. Use the same hostname consistently in development (localhost or 127.0.0.1) and the Vite proxy.

Refresh validates the JWT, locks its OutstandingToken row, rechecks the blacklist, checks current active user, then consumes it and creates the replacement in one transaction. Tested concurrent consumption yields one 200 and one 401. A failed refresh clears the cookie. This is consumed-token replay protection, not token-family revocation across all devices. Network failures can require signing in again if rotation committed but its response was lost.

Logout clears frontend access immediately, waits for an in-flight refresh, and blacklists the cookie on the server. Existing access JWTs are not blacklisted; they expire within five minutes. Server-side JWTAuthentication still rejects inactive users and permission checks load current database permissions. No client role claim is used to authorize a request.

## Frontend client

Import login, logout, refreshSession and authenticatedFetch from `features/auth/session.ts`. Login takes credentials; resource paths are relative, e.g. authenticatedFetch('/auth/me/'). A shared promise coordinates refreshes within a tab. Web Locks serializes refresh/login/logout between supporting tabs, bootstrapping current CSRF inside the lock. Browsers without Web Locks have only per-tab coordination; the server still rejects replay, so a cross-tab race may require reauthentication. A protected request retries at most once after 401, with no refresh loop. Callers must use replayable bodies (JSON strings/FormData rather than consumed streams) and must not implement an additional retry layer. Other HTTP failures do not trigger refresh. The screen integration remains for the frontend prompt.

## Permission policy

ReferencePermissions requires an explicit `permission_model` on the view. It maps list/retrieve to view, create to add, update/partial_update/activate/deactivate to change, and destroy to delete. Unknown actions fail closed. APIView method equivalents are supported. All writes additionally require common_reference.maintain_reference. Object checks repeat this gate; future queryset visibility rules remain mandatory in Prompt 5.

Anonymous users have no reference access. The global Admin, Teacher and Student starter groups receive all ten Django view_model permissions via seed_role_groups. They gain no write or global-maintenance permissions. Admin is not an institution membership and implies no global write authority. A future institution-scoped Admin must separately receive a read bundle or equivalent explicit view permissions; no missing tenancy schema is invented.

Platform maintainers must be explicitly granted both the global maintain_reference permission and each required add/change/delete model permission. The superuser is a platform administrator. User/group management remains superuser-only in Django admin. Login rejects extra fields; me is read-only. No grant or membership mutation endpoint exists. IsAdminOrTeacher is provided only for later domain workflows and must be combined with future scope checks; it is not used for reference writes.

## Commands (repository root, PowerShell)

Reuse the isolated MySQL database from Prompt 3 and your secret environment:

```powershell
$env:SIMS_DB_PASSWORD=(Get-Content .tmp/mysql-check.env -Raw).Trim().Substring(17)
# Set DJANGO_SECRET_KEY securely, or use backend/.env as described in README.
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py seed_role_groups
backend/.venv/Scripts/python.exe backend/manage.py createsuperuser
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
```

Assign users to the read groups through superuser administration. To grant maintenance, assign the global gate and chosen model permissions explicitly in that same interface. Seeding adds only reference reads and preserves any existing grants; it does not silently repair preexisting overprivileged group assignments.

Verification:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py test apps.accounts apps.core apps.common_reference --settings=config.settings.test --noinput
backend/.venv/Scripts/python.exe backend/manage.py spectacular --settings=config.settings.test --file backend/openapi.yaml --validate --fail-on-warn
npm --prefix frontend test
npm --prefix frontend run build
```

## Cleanup and throttling operations

`deploy/sims-token-cleanup.cron` schedules flushexpiredtokens daily at 03:17 in the server timezone. On Linux set the service-user environment first, then install the entry into that user's crontab using `crontab -e`; preserve other jobs. It is supplied but not installed on this Windows development machine or a production server. To run manually: `backend/.venv/Scripts/python.exe backend/manage.py flushexpiredtokens`.

Login is limited to five requests/minute per client identity using DRF's cache throttle; responses for nonexistent, incorrect-password and inactive users are generic. Default local-memory caching is process-local and DRF throttles are approximate, not brute-force/DDoS protection. Apply the supplied Nginx login rate-limit example for a shared edge limit across Gunicorn workers, and configure trusted proxy addressing/shared cache when deploying multiple servers. Nginx-generated throttling errors are edge responses, not the DRF error envelope. Neither Nginx configuration nor cleanup cron has been deployed here.

## Actual verification and continuation

Twenty backend tests passed against MySQL 8.4.11, including the prior foundation/reference suite and authentication cookie flags, unauthorized access, origin/CSRF checks, credential throttling, refresh rotation/replay/race, logout, inactive users, read/write separation and rejected privilege escalation. Three frontend runtime tests passed for shared refresh and bounded retry behavior. TypeScript/build and OpenAPI validation passed; no migration drift. No real-browser cookie/HTTPS visual test or production deployment was performed.

Prompt 5 must attach ReferencePermissions plus visibility-filtered querysets to each real reference endpoint. This step tests that policy with a minimal API probe; the CRUD endpoints are not yet implemented. Login screens, scoped institution roles and immediate access-token session revocation remain outside this step.

References: [Django CSRF](https://docs.djangoproject.com/en/5.2/ref/csrf/), [Simple JWT blacklist and cleanup](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/blacklist_app.html), [DRF throttle limitations](https://www.django-rest-framework.org/api-guide/throttling/).
