# Security model

## Authentication and sessions
* **Passwords** are hashed with Argon2id. Legacy Django PBKDF2 hashes are still accepted and silently upgraded at the
  next sign-in. Policy: 12+ characters, three character classes, no common or username-derived passwords, no reuse of the
  last five. Changing a password signs every other device out.
* **Sign-in** is rate-limited per IP *and* per username (shared across replicas through PostgreSQL), locks the account
  for 15 minutes after five failures, performs a dummy hash for unknown users (no timing oracle) and gives one generic
  error for every failure. Every attempt is recorded in `login_audit`.
* **Access tokens** are 10-minute JWTs (HS256, `iss`/`exp`/`sid` required) kept only in browser memory. Each token is
  bound to a server-side session row, so logout, password change, deactivation and "sign out everywhere" take effect
  immediately.
* **Refresh tokens** are opaque, stored only as SHA-256 digests, delivered in an `HttpOnly; Secure; SameSite=Strict`
  cookie scoped to `/api/v1/auth`, and **rotated on every use**. Presenting an already-rotated token is treated as theft
  and revokes the whole session. Sessions have absolute (7 d) and idle (2 d) limits.
* **CSRF**: credential endpoints require a signed double-submit token and a same-origin `Origin` header; every other
  endpoint uses bearer tokens, which browsers never attach automatically.
* **MFA**: optional TOTP (RFC 6238) per user.
* Users created by administrators get a one-time temporary password and **must change it** before using the system.

## Authorisation
* Permissions are `MODULE.RESOURCE.ACTION` codes granted to **roles**, assigned to users with a **scope**
  (global, institution, campus, department, programme, or self). `DENY` always beats `ALLOW`.
* Every list, read, create, update, delete and workflow action is filtered by the caller's scope **in SQL**, following
  foreign keys to the owning institution/department/student/employee — a row outside your scope is simply a 404.
* Self-service writers (students, staff) may only touch fields on an explicit allow-list; workflow status, ownership and
  organisation columns can never be set directly. Results are visible to students only once published.
* Reviewers cannot review or approve their own records.
* Aadhaar, PAN and bank numbers need the *specific* `EMPLOYEE_*` permission — a module-wide grant is not enough — are
  encrypted with AES-256-GCM (versioned keys), never returned (only masked forms) and deduplicated by keyed fingerprint.
* Administrators cannot grant permissions they do not hold themselves, cannot assign privileged roles unless they are
  super administrators, and cannot remove their own super-admin role or deactivate themselves.

### Access control (least privilege)
* Built-in roles are defined in `backend/app/rbac/matrix.py` and `python -m app.cli bootstrap` reconciles the database to
  it (missing grants added, extra grants removed); customise by creating a new role, not by editing a built-in one.
* Segregation of duties: entering, verifying/approving and publishing results are held by different roles; students see
  results only after publication; submitted records are locked.
* Teaching roles (faculty, lab instructor, evaluator, course coordinator) are row-limited to assigned classes/papers and
  mentors/advisors to their mentees, unless the person also holds a wider role such as head of department.
* Each audience signs in through its own portal (`backend/app/rbac/portals.py`); an account cannot use another entrance.
* Known gaps: no fees/library/hostel/transport/placement modules, lab instructors are not limited to lab sections, and
  there is no field-level restriction for the document verifier. See `docs/ROLES.md`.

## Data integrity and audit
* Optimistic concurrency (`version`) on editable records, idempotency keys on creates and workflow actions.
* Every mutation writes an immutable `audit_log` entry (before/after, actor, request id, IP); workflow changes also write
  `status_history`. Both tables are append-only at the database level (triggers).
* Anonymous feedback stores answers with **no link to the student**; a keyed fingerprint in a separate ledger only
  prevents double submission. Small cohorts are suppressed in results.

## Transport and HTTP hardening
* Security headers on every response (CSP, `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, HSTS in production),
  `Cache-Control: no-store` for the API, request ids, host-header validation, body-size limits, CORS only for
  configured origins (none by default), CSV export formula-injection neutralisation.
* Uploads accept PDF/PNG/JPEG only, validated by content (not just extension), size-limited, stored privately under
  random names, checksummed, served only through authorised, `attachment`/`nosniff`/`sandbox` downloads.
* Production refuses to start with a weak secret, wildcard hosts/CORS, insecure cookies or missing encryption keys.

## Database (Supabase)
* Migrations enable **row level security** on every table and revoke all privileges from `anon` and `authenticated`, so
  Supabase's public REST/GraphQL surface exposes nothing. The API connects as the table owner (`postgres`), which is the
  only identity that can read or write data. A test asserts RLS is on for every table.
* Keep the database password and `SIMS_SECRET_KEY` in your platform's secret store, never in git.
* **New tables** added in future migrations must run `ALTER TABLE … ENABLE ROW LEVEL SECURITY` (the RLS test fails otherwise).

## Operational checklist before go-live
1. `SIMS_ENV=production`, strong `SIMS_SECRET_KEY`, `SIMS_FIELD_ENCRYPTION_KEYS`, `SIMS_FINGERPRINT_KEY`.
2. `SIMS_ALLOWED_HOSTS` = real host names; serve over HTTPS only; `SIMS_DOCS_ENABLED=false`.
3. Change or remove every demo account; create real administrators with `create-admin`.
4. Run the worker; enable Supabase point-in-time backups; store uploads in a private bucket (`SIMS_STORAGE_BACKEND=s3`).
5. Review `docs/ROLES.md` and tailor roles to your institution through **Administration → Roles and permissions**.
