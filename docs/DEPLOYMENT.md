# Deployment

The system is three small processes plus PostgreSQL and a static web bundle:

```
browser ──HTTPS──> [web: nginx, static UI + /api proxy] ──> [api: uvicorn x N] ──> PostgreSQL (Supabase)
                                                          [worker: jobs / schedules] ──┘
```

Everything is stateless except the database and (optionally) the local file store, so scale horizontally by running
more `api` and `worker` containers. Use `SIMS_STORAGE_BACKEND=s3` as soon as you run more than one machine.

## Environment
Copy `backend/.env.example` to `backend/.env` (or inject the same variables through your platform). Required in production:

| Variable | Purpose |
| --- | --- |
| `SIMS_ENV=production` | enables strict start-up checks, HSTS, secure cookies |
| `SIMS_DATABASE_URL` | Supabase **session pooler** URL (`…pooler.supabase.com:5432`, `?sslmode=require`) |
| `SIMS_SECRET_KEY` | ≥ 32 random characters (signs tokens) |
| `SIMS_ALLOWED_HOSTS` | exact host names, e.g. `sims.example.org` |
| `SIMS_FIELD_ENCRYPTION_KEYS`, `SIMS_FINGERPRINT_KEY` | encryption of staff identifiers |
| `SIMS_DOCS_ENABLED=false` | hide the OpenAPI UI |
| `SIMS_STORAGE_*` | S3-compatible bucket for uploads (Supabase Storage S3 endpoint works) |

Rotating the encryption key: add a new version to `SIMS_FIELD_ENCRYPTION_KEYS`, set `SIMS_FIELD_ENCRYPTION_ACTIVE` to it;
old ciphertext stays readable because each blob records its key version.

## Option A — Docker Compose on one host
```bash
cp backend/.env.example backend/.env && $EDITOR backend/.env
docker compose --profile app up -d --build migrate api worker web   # Supabase database
# or include the bundled PostgreSQL: docker compose --profile app up -d --build
```
`migrate` applies migrations and syncs the permission catalogue, then exits; `api`/`worker` start after it succeeds.
Put a TLS-terminating proxy or load balancer (Caddy, Traefik, Cloudflare, a cloud LB) in front of the `web` container
(port 8080) and forward `X-Forwarded-Proto`. The API container runs as an unprivileged user with a read-only filesystem.

## Option B — Managed container platforms (Render, Fly.io, Railway, Cloud Run, ECS…)
Deploy two services from `backend/Dockerfile` (command `uvicorn …` for the API, `python -m app.cli worker` for the
worker) and one from `frontend/Dockerfile`. Run `python -m app.cli migrate && python -m app.cli bootstrap` as the
release/pre-deploy command. The web image proxies `/api` to a host named `api` on port 8000 — edit `frontend/nginx.conf`
(`set $upstream …`) if your platform names or ports differ. If you host the UI on a different registrable domain than
the API, set `SIMS_CORS_ORIGINS` and `SIMS_COOKIE_SAMESITE=none` (HTTPS required); same-site subdomains work with the
defaults except cookies must share `SIMS_COOKIE_DOMAIN`.

## First release
```bash
python -m app.cli migrate
python -m app.cli bootstrap                      # roles, permissions, reference lookups (idempotent)
SIMS_BOOTSTRAP_ADMIN_PASSWORD=… python -m app.cli create-admin --username admin --email you@example.org
```

## Operations
* **Health**: `GET /api/v1/health/live` (process) and `/api/v1/health/ready` (database + schema version).
* **Logs**: one access line per request with a request id (`X-Request-ID` is echoed to the client).
* **Jobs**: *Administration → Background jobs* shows queued/running/dead jobs and can retry dead ones.
* **Backups**: enable Supabase PITR; back up the object bucket separately.
* **Upgrades**: deploy a new image, run `migrate`, roll the API; migrations are forward-only and tested from an empty
  database and downgraded to base in CI.
* **Scaling knobs**: `WEB_CONCURRENCY` (uvicorn workers), `SIMS_DB_POOL_SIZE`/`SIMS_DB_MAX_OVERFLOW`; with Supabase's
  transaction pooler (port 6543) set `SIMS_DB_POOLER=transaction`.
