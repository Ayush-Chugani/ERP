# M15 Identity, RBAC and Audit implementation contract

Status: the three recommended decisions were approved on 2026-09-25. The staged M15 implementation is now installed locally, with both activation flags disabled and no business-role assignments. The original preflight findings below are historical; see the current implementation and validation record at the end.

## Requested sequence and prerequisites

User requested implementation of `Manuals/Prompts/m15-RBAC_Audit_Structured_Prompt_Pack.docx` after M12. M12 is already implemented and locally enabled for institution 1. M13 and M14 are implemented but remain disabled. No rollback of those modules is required by this request.

Follow prompts 3.1-3.7 (identity/schema), 4.1-4.5 (authorization), 5.1-5.4 (authentication), 6.1-6.5 (administration), 7.1-7.3 (audit), 8.1-8.4 (seeds), 9.1-9.3 (integrations), 10.1-10.2 (API/UI), and 11.1-11.5 (tests), with the master prompt and acceptance criteria applying throughout. Source documents are requirements input; they do not authorize sending messages or silently replacing existing identity data.

## Verified repository and database findings

- AUTH_USER_MODEL is `accounts.User`, derived from AbstractUser, using the existing `user_account` table. Keep the model label and existing user IDs; do not introduce a second login identity.
- Current columns include signed BIGINT user_id, password VARCHAR(128), username VARCHAR(150), email, is_active/is_staff/is_superuser, date_joined, names and last_login. Source SQL instead specifies unsigned BIGINT, password_hash VARCHAR(255), username VARCHAR(100), security-state fields and native timestamps. An exact replacement is not an additive migration.
- Database preflight found 2 users, no usernames over 100 characters, no negative user IDs, no existing People AccountLink rows, no memberships or scope grants, 2 central reference-audit records and no M15 domain tables. These are local counts only; deployments elsewhere require their own preflight.
- 90 foreign keys reference the current user table. Their types and constraints are enumerated in `Manuals/M15_PREFLIGHT.json`. Unsigned conversion requires coordinated FK changes and recovery planning; disabling FK checks and assuming compatibility is not acceptable.
- Existing identity consumers use People AccountLink and its invitation/unlink workflow. Canonical student_user_account and employee_user_account must have a single authoritative owner plus a compatibility strategy; independently writable parallel links would create security inconsistencies.
- Existing modules use Django Permission/Group together with active Membership/ScopeGrant and explicit superuser branches. Adding a new evaluator alone would not make it authoritative for those modules.
- Existing login uses CSRF/origin-checked refresh cookies, JWT access tokens, single-consumer refresh rotation, blacklisting and inactive-user checks. Preserve these controls while adding account status, lockout, password history, MFA and actor context. Refresh/access authentication must recheck security state, not only the login endpoint.
- Attendance already stores a FK to AUTH_USER_MODEL and an authenticated marking actor. FileObject currently stores an unsigned nullable uploader number without a FK; there are no orphan uploader values locally. M15's uploader FK requires alignment with the actual user key type and updating M13's frozen-schema verifier contract deliberately.
- Audit evidence already exists in Core ReferenceAuditEvent and module-specific logs. Preserve old evidence; do not copy it into new tables and imply stronger provenance than recorded originally.

## Decisions presented to the user

1. **Rollout:** staged M15 behind a feature flag with current access preserved until verified cutover (recommended), or replacement of authorization across all existing modules in this implementation. This determines whether every existing module needs simultaneous permission/scope adapters and changes to superuser handling.
2. **SELF DENY correction:** direct/delegated SELF role grants use the effective principal's user ID, but SELF overrides in v_effective_user_permission use 0. As supplied, these form different groups, so a SELF override cannot deny a SELF role grant. Recommended correction: map SELF overrides to their user ID in the effective view, preserving the override table's per-user normalized uniqueness key. Alternative: preserve literal SQL and disable SELF overrides.
3. **Ancestor scopes:** retain the exact-scope evaluator and use explicit business-object adapters that apply ancestor grants with DENY winning across applicable scopes (recommended), or permit exact-scope matches only. Scope inheritance must not be silently mixed into the exact-scope SQL aggregation.

Approved: staged feature-flag rollout; SELF overrides resolve to the principal user ID; explicit ancestor adapters with DENY precedence. No further approval is required for these decisions.

## Implementation defaults independent of those choices

- Role parent is hierarchy metadata only; no inherited role grants unless separately specified.
- Time windows are start-inclusive/end-exclusive. Inactive module/resource/action/permission/role and unusable accounts fail closed at the service boundary, even where the supplied SQL views check only a subset.
- Delegation must originate from the delegator's active assignment, remain within its scope and time window, and never be delegated onward as a new source assignment. Preserve the source view's SELF behavior: delegate SELF resolves to the delegate's identity. Require approval authority and reason; no self-approval of privilege escalation.
- Security administrators must not assign permissions they are not authorized to grant. Bootstrap/emergency access must be explicit, audited and revocable; existing is_superuser must not silently defeat a business DENY in authoritative mode.
- Passwords remain Django encoded hashes; column mapping must preserve existing hashes byte-for-byte. Never audit password/hash, reset token, MFA seed/recovery code, JWT or refresh-cookie values. User IDs/session audit identifiers are distinct from bearer credentials.
- MFA and sensitive-action proofs need a fail-closed provider contract. multi_factor_enabled cannot be only a display flag. Password reset must use verified expiring one-time tokens; no unauthenticated user-ID reset endpoint.
- Impersonation needs explicit permission, step-up, original actor retention and effective permissions restricted to the intersection of permitted support actions and target authority. Prevent nested sessions, target privilege escalation and credential/security-policy changes. Never implement it by replacing request.user without original actor context.
- Audit updates/deletes are denied in ordinary flows. Login logout_at completion, if implemented as an update, must use a narrowly authorized service and retain evidence. Physical purge stays unavailable without a retention/legal-hold policy.
- Catalogue seeds must be idempotent and preserve the supplied business matrix. Django groups may remain framework compatibility state but must not replace M15 business roles.
- Security UI/exports remain authorization-checked, bounded, no-store and network-only; no security mutations queued offline.

## Source catalogue evidence

`Manuals/M15_SOURCE_CATALOGUE.json` contains the extracted source actions/modules/roles and expanded role-permission matrix. `scripts/m15_source_catalogue.py` regenerates it without executing SQL or writing to a database.

Verified source totals: 11 actions, 20 modules, 220 MODULE.ALL.ACTION permissions, 32 roles, 1,732 role-permission pairs and 30 sensitive permissions. SUPER_ADMIN has 220 grants; SYSTEM_ADMIN has 60 and no IMPERSONATE grants. DATABASE_ADMIN, FINANCE_OFFICER and GRIEVANCE_OFFICER have no role-permission INSERT rule in the supplied source and therefore receive no invented grants. Any later rules for them require an explicit policy choice.

Resource ALL semantics and MODULE.RESOURCE.ACTION mapping must be explicit in the registry. Wildcard resource matching must not silently broaden a resource-specific denial. Exact permission-code evaluation remains separately testable against the SQL view.

## Proposed module boundaries and migration plan

Keep `accounts.User` and authentication integration in the owning Accounts app. Put the business RBAC catalogue, assignments, overrides, delegation, effective resolvers and audit API in a new `apps.identity_access` bounded app. Use lazy public scope adapters/registry contracts to avoid circular imports with business modules. Preserve M12 confidentiality and assignment restrictions as additional domain gates, never replace them with a broad module-level grant.

Migration increments must be reviewable: account compatibility/security fields; canonical IAM catalogue; scoped assignments/overrides/delegation; identity-link ownership and backfill; password/login/activity audit; SQL views; actor-FK integration; idempotent source catalogue. No table replacement or live authorization cutover has yet been executed. A signed/unsigned user-key conversion and password-column rename need a coordinated all-FK plan if selected; an additive compatibility schema must clearly document deviations from source DDL instead of claiming exact mapping.

Existing audit rows and access assignments must be reconciled before cutover. Prepare a dry-run mapping report from Django grants and existing scopes to M15 business assignments; do not infer equivalent roles merely from similar names. Compare old/new decisions for actual endpoints, identify broadening/denial changes, establish an explicitly assigned recovery administrator, and test rollback before enabling authoritative evaluation.

## Verification requirements

- Real MySQL column/default/ENUM/generated-key/FK/view checks; exact-scope uniqueness and every invalid scope shape.
- Seed matrix comparison for all 32 roles and sensitivity rules, idempotency and no unintended assignments.
- Direct/delegated ALLOW/DENY, SELF correction, parent-scope adapter precedence, inactive catalogue nodes, validity boundaries, revoked sources and no delegated scope expansion.
- Missing permission metadata fails closed; scope filtering before object lookup; cross-institution/campus/department/programme/user denials; protected explanations and exports.
- Login enumeration resistance, lockout concurrency, refresh/access security-state revocation, forced password change, reuse prevention, MFA failure paths, impersonation intersection/original actor, and audit redaction.
- M12/M13/M14 and other impacted authorization regressions, existing JWT/CSRF/rotation tests, UI confirmations/offline behavior and MySQL concurrency.

## Work completed this step

Read the complete prompt structure and SQL appendix, inspected current account/auth/link/RBAC/audit integrations, ran the read-only preflight, and extracted/validated source seed totals. Added only this guide, the extracted prompt text, aggregate preflight report, source catalogue and the two reproducible scripts. Original SQL/DOCX unchanged. No module implementation, migrations or production-readiness claim yet.

Commands:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py shell -c "exec(open('scripts/m15_preflight.py').read())"
backend/.venv/Scripts/python.exe scripts/m15_source_catalogue.py
```


## Current implementation ? 2026-09-25

All three approved decisions are implemented: staged activation, SELF override correction in both SQL and ORM, and exact-scope evaluation plus explicit ancestor-scope evaluation with DENY precedence. The new owner is `backend/apps/identity_access`; APIs are under `/api/v1/security/`, UI at `#/security`.

Implemented components:

- Additive Accounts security state and security_version; custom JWT/session backend integration; audited login failures/success, lockout, password history/reuse checks, verified one-time password reset consumption, MFA/step-up provider contracts and password-change UI. Login, refresh and access tokens recheck security state when security activation is enabled. Existing CSRF/origin checks, refresh rotation, cookie protections and inactive-user behavior remain.
- Business catalogue, generated scope keys, SQL checks and uniqueness, role grants, scoped assignments, overrides, delegation and audit models; exact source views with SELF DENY corrected. `revoked_at` is an explicit additive override extension so future access can be cancelled without rewriting its dates.
- Exact permission evaluation, wildcard-resource matching only in the explicit object evaluator, DENY across supplied ancestors, inactive catalogue/account rejection, source validity and delegation restrictions, missing-metadata denial and protected explanations. Business owners must supply authoritative scope adapters; request-supplied ancestry is never trusted.
- Step-up-protected transactional administration services/APIs for roles, matrix, accounts, assignments, overrides and delegations. Self-assignment and self-overrides are rejected; grants cannot exceed the operator's effective authority. Delegation approval must be independent. Administration lists currently require explicit GLOBAL IAM/AUDIT authority; no institution administrator is silently granted access to every identity.
- Read-only support sessions retain original actor, expire after 15 minutes, prevent nested starts and restrict supported reads to the actor/target intersection. Credential changes and IAM/AUDIT access are excluded. Support identity never replaces request.user in legacy modules. A persistent banner identifies active support sessions.
- Append-oriented audit APIs, bounded CSV export with step-up and spreadsheet-formula protection, recursive sensitive-key redaction, expiry command, explicit first-administrator bootstrap command and a read-only cutover inventory. Physical audit purge is unavailable; final migration prevents reversing the schema into evidence deletion. Rollback is via flags/code, not dropping security tables.
- File uploader is now a signed FK matching the existing custom user. Orphans abort migration. Attendance already uses the correct authenticated actor FK. M13 schema verification recognizes the explicitly recorded M15 uploader upgrade.
- Source-exact catalogue installer: 11 actions, 20 modules, 220 permissions, 32 roles, 1,732 role grants and 30 sensitive permissions. Re-runs preserve existing edits and assign no users.

### Explicit compatibility deviations

The existing `accounts.User(AbstractUser)`, signed user IDs, username length 150, Django `password` column and framework fields are retained. `date_joined` remains the creation timestamp; password hashes are not renamed or copied. This avoids rewriting 90 inbound FKs. New FK columns follow the actual owner types. Source TIMESTAMP/DATETIME native types are used for new IAM models; most created/default/update times are supplied by Django rather than raw-SQL server-default clauses.

Canonical student_user_account and employee_user_account are **non-updatable DISTINCT SQL views** over the existing uniquely constrained People account links. Managed=False projection models prohibit writes. People invitation/link services remain the single writer. They are intentionally not independently writable replacement tables during staged rollout.

The raw permission views preserve source aggregation plus the approved SELF correction and override revocation exclusion. The service evaluator adds account/catalogue/validity guards; callers must not bypass it by treating raw view rows as final business authorization.

### Local installation evidence

`M15_INSTALL_REPORT.json` records the local schema/catalogue state. All migrations applied; zero pending migrations. Both `IDENTITY_ACCESS_ENABLED` and `IDENTITY_ACCESS_SECURITY_ENABLED` are false. Assignments, overrides and delegations are all zero. No user was automatically promoted and no live authorization cutover occurred.

Commands:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py migrate --noinput
backend/.venv/Scripts/python.exe backend/manage.py seed_identity_access
backend/.venv/Scripts/python.exe backend/manage.py identity_access_cutover_report
```

The bootstrap command defaults to dry-run and requires explicit target/operator IDs and reason. It does not toggle activation flags. Configure the tested MFA provider before requiring MFA. Reset token delivery must use a verified external delivery owner; this implementation consumes validated tokens and sends no messages.

### Validation and remaining rollout work

- Real MySQL foundation/accounts pass: 16 tests initially; expanded catalogue/security run: 22; expanded Accounts/IAM run: 27.
- Broader regression pass: **122 tests**, covering IAM, Accounts, People, Documents, Communication and Student Support. One existing People URLField deprecation warning remains. An initial reused-database People seed fixture failure was resolved by recreating the isolated test database.
- Latest IAM-only pass: **22 tests**, including lockout concurrency, support intersection and future-override revocation. These runs overlap; do not sum their counts.
- UI tests: **9 passed** across security, Documents and Communication. Production frontend build passes. OpenAPI validation passes with zero warnings after registering the custom JWT authentication extension. Django checks and migration drift checks pass. M13's existing MySQL long unique storage-key warning remains on migrate.

Remaining before authoritative rollout: endpoint-by-endpoint legacy grant/scope mapping and decision comparison; explicit recovery-user assignment; institution/object-specific integration of support reads; real MFA enrollment/recovery provider and verified reset delivery configuration; deployment backup/restore and cutover rehearsal. Browser-interactive QA has not been performed. `identity_access_cutover_report` intentionally reports cutover_ready=False until that review is implemented and completed; it is an inventory, not a simulated equivalence report.

M16 and M17 are still queued after completion of the preceding module prompts. Their discovery artifacts exist; their application implementations have not been completed. The three M15 design decisions are resolved and must not be requested again.


Final verification update: the expanded Accounts/IAM run passed 30 tests; subsequent focused runs passed 13 authorization/API/support tests and 7 account-security tests, including the new source-principal delegation denial and HTTP login/access/refresh state checks. The latest security UI run passed 3 tests (included in the earlier 9-test UI group). A reused MySQL test run exhausted the source TINYINT action auto-increment because TestCase rollback does not roll back sequences; test-only catalogue fixtures now use stable IDs. No production key width or seed behavior was changed to accommodate tests.

Framework password changes also invalidate issued access tokens through Django's keyed session-auth stamp. Django account-admin writes are disabled when M15 account security is active so password/history policy cannot be bypassed through that UI. Enabling M15 administration without account security produces a Django system-check error. Delegated service decisions additionally honor direct/global source-principal DENY evidence; raw SQL view output is not the authorization API.

Reproducible staged checks: `scripts/verify-module15.ps1`. Run the broader suite with a fresh isolated test database when migration-seeded People fixtures are required. Test runs overlap and their counts must not be added together.
