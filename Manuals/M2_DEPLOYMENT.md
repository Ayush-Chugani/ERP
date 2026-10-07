# Module 2 deployment and operations

Status: deployment templates prepared; Linux staging deployment and recovery rehearsal remain outstanding. See [implementation](M2_IMPLEMENTATION.md) and [release audit](M2_RELEASE_AUDIT.md).

## Release preparation

Run `scripts/verify-module2.ps1` against a disposable local/test MySQL instance. Tests create and destroy `test_sims_reference`; never grant a test runner access to production. The verified database is MySQL, not MariaDB. The schema reference filename does not establish MariaDB compatibility; test its collations, generated constraints and migrations separately before adopting it.

Use immutable release directories under `/srv/sims/releases/` with `/srv/sims/current` pointing to the selected release. Provision Python 3.11, Node 22.12 or newer, MySQL, nginx and a dedicated unprivileged `sims` service account. Build with `npm --prefix frontend ci` and `npm --prefix frontend run build`. Resolve and review a pinned Linux production dependency lock from `backend/requirements-production.in`, audit it, and install into the release environment. The Windows verification does not validate Gunicorn or Linux dependency resolution. Retain the matching environment for rollback.

Copy `deploy/.env.example` to `/etc/sims/runtime.env`, replace every placeholder and restrict it to root and the service group (0640). Use a new secret and production database credentials. Do not copy development `.env` into releases. Keep database traffic private. Use a separate migration identity with DDL rights; runtime needs only application DML rights. Application audit append-only rules do not protect against database administrators.

## Deployment sequence

1. Take an encrypted backup and verify it can be restored into an isolated database. Record the release identifier, dependency lock and migration state.
2. Put the application into maintenance mode and stop writes during migration. Inspect `manage.py migrate --plan` using production settings and migration credentials. Existing legacy tables require an explicit adoption review; never blindly fake initial migrations or import the full reference SQL over Django tables.
3. Apply `manage.py migrate`, then `manage.py collectstatic --noinput` with `DJANGO_SETTINGS_MODULE=config.settings.production` and the production environment loaded securely. The deployment account needs write access to the release staticfiles directory; the runtime service can remain read-only.
4. Run `manage.py check --deploy --database default`. HSTS subdomain and preload warnings W005/W021 are expected with the supplied opt-in defaults. Enable them only after all affected domains support HTTPS and preload consequences have been reviewed.
5. Adapt `deploy/sims-api.service.example` and create its `/var/lib/sims` and `/var/log/sims` directories with service-account permissions. Match the virtual-environment path to the selected release. Validate with `systemd-analyze verify`, reload systemd and start the service.
6. Adapt `deploy/module2-nginx.conf.example`, supply the actual domain and certificate, run `nginx -t`, and reload nginx. Gunicorn must be reachable only through the trusted proxy: Django trusts its overwritten `X-Forwarded-Proto` header.
7. Complete the smoke tests below before enabling ordinary access. Provision memberships, module enablement and scope grants through the platform administrator as described in the implementation guide.

The nginx example assumes nginx is the public edge. Review real-client-IP handling before adding another load balancer. Its SPA CSP permits inline styles for MUI; API/admin are excluded because their renderer requirements differ. Test CSP on the deployed application and establish a separate admin policy. API/admin/static/media paths must never fall through to SPA HTML. API responses are not service-worker cached; offline copies exist only briefly in tab memory. Validate service-worker update behavior after deployment.

## Staging smoke tests

- Check HTTPS redirect, certificate, secure refresh cookie, CSRF/origin enforcement and login/logout/refresh.
- With separate institution users, verify lists, detail IDs, parent searches, exports, metadata and impact counts never expose the other institution.
- Exercise create, edit, deactivate/reactivate, rejected parent moves and one permitted move. Check each committed write has an audit event; rejected writes have none.
- Dry-run a CSV, then import a small reviewed fixture. Check row errors and batch rollback. Remove fixtures using an isolated staging database restore, not a newly enabled public delete endpoint.
- Test desktop/mobile keyboard navigation, validation, saved inactive parents, child navigation and pagination.
- Install/update the PWA. Test offline-copy expiration, logout/account change/reconnect and cross-tab clearing. Reloading offline cannot restore a saved copy or establish authentication.
- Verify unknown API routes return API errors, asset misses return 404, and API responses are not stored in Cache Storage.

## Backups, recovery and monitoring

Schedule encrypted MySQL backups using a least-privileged backup account. For InnoDB, use a consistent transactional snapshot; coordinate schema changes so they cannot race backups. Store credentials outside command history and logs. Keep copies off-host, define retention and recovery objectives with operations, and test restores regularly. Include schema, data, audit history and the release/dependency metadata. Audit retention must be a separately authorized operational policy, not a public deletion endpoint.

Monitor service restarts, database connectivity, error rate, request latency, storage, certificate expiry and backup/restore success. Gunicorn's example access log excludes query strings; configure nginx and upstream logs similarly if query strings can contain user-entered searches. Never log authorization headers, cookies or credentials. DRF process-local throttling is approximate; retain edge rate limiting and size/time bounds.

For rollback, stop writes and determine migration compatibility first. Restore the prior release and its dependencies only when it can read the migrated schema. Otherwise restore the verified pre-release database backup into a separate database, validate it, switch connections and then resume traffic. Do not blindly reverse migrations on live data. Document the recovery point and any writes that would be lost; reconcile them before reopening. No production rollback or restore has been rehearsed by this implementation run.
