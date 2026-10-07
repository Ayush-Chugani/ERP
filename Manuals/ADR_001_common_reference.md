# ADR 001 — Common Reference Module, SIMS 6.5.1

Date: 2026-09-14. Status: architecture selected; implementation and MySQL integration tests pending.

## Scope and evidence

Reviewed only the ten Common Reference CREATE TABLE statements in `sims_v6_5_1_reviewed_full_schema.sql`, lines 32–135, and searched for later caste uniqueness corrections (none found). The university/institution selection in the IDE is outside scope. No claim is made about other SIMS modules or their integrity rules.

Earlier session work imported the full schema into local XAMPP MariaDB 10.4.32 using a separate compatibility copy. That is known local state, not evidence of any deployment elsewhere. Production deployment state remains unknown. Do not import the full schema as the foundation of this module. This step changes no database, application settings, or dependency installations.

## Compatibility and deployment decision

Use Python 3.11 and Django 5.2.17, the supported 5.2 LTS patch currently listed by the [Django download page](https://www.djangoproject.com/download/); security support extends to April 2028. Recheck patches when locking and deploying. DRF 3.16.x explicitly supports Django 5.2 ([announcement](https://www.django-rest-framework.org/community/3.16-announcement/)). Keep mysqlclient 2.2.8, already installed; Django requires at least 2.2.1.

The SQL baseline is MySQL 8.0.16+ because that is the enforcement floor for CHECK constraints. Django 5.2's engine floor is independently MySQL 8.0.11+ or MariaDB 10.5+, through `django.db.backends.mysql` ([database documentation](https://docs.djangoproject.com/en/5.2/ref/databases/)). Neither minimum is a production lifecycle recommendation. Target MySQL 8.4 LTS, current supported patch pinned at foundation build time, InnoDB, utf8mb4, explicit utf8mb4_0900_ai_ci. MySQL 8.0 entered Sustaining Support in April 2026 ([vendor lifecycle notice](https://www.mysql.com/support/eol-notice.html)). Do not select 8.0 for a new production deployment.

Local MariaDB 10.4.32 is incompatible with Django 5.2 and lacks the required collation. The earlier utf8mb4_unicode_ci substitution is not semantically identical. Preserve the local database; provision a separate MySQL instance and fresh `sims_reference_dev` database for Prompt 2. Keep the user's root-account preference for local development with an environment-supplied password. Production should use separate migration and application credentials. Do not bypass Django's version checks or silently upgrade/replace XAMPP.

Simple JWT 5.5.1 is a provisional candidate, not a verified compatible pin: its [stable requirements](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/getting_started.html) list Django through 5.1 and DRF through 3.15. Prompt 2 must reconcile tagged release metadata/test matrices with those older docs and run authentication tests against Django 5.2/DRF 3.16 before finalizing the lock. Do not describe this combination as officially verified based on installation success alone.

Frontend candidates: React/React DOM 19, Material UI with Emotion, TypeScript, Vite, and vite-plugin-pwa imported as `VitePWA`. [MUI's installation guide](https://mui.com/material-ui/getting-started/installation/) lists React 19 support. [Vite](https://vite.dev/guide/) requires Node 20.19+ or 22.12+; select maintained Node 22 with at least 22.12. [PWA documentation](https://vite-pwa-org.netlify.app/guide/) documents the integration; [upstream package metadata](https://raw.githubusercontent.com/vite-pwa/vite-plugin-pwa/main/package.json) currently includes Vite 8 peers. This is branch metadata, not a release lock. Resolve exact mutually compatible released frontend patches, TypeScript and React plugin peer ranges, then commit a lockfile and pass build/type checks in Prompt 2. No unverified exact frontend or Gunicorn/Nginx versions are selected here.

Production is Linux: Nginx serves built static assets and proxies same-origin `/api/` to Gunicorn WSGI. Windows development uses Django's development server; production must not use it. Verify maintained Gunicorn/Nginx releases and image digests before deployment. Use HTTPS, environment secrets, UTC Django/database sessions and aware timestamps; render a configurable IANA display timezone, default UTC. No timezone columns are needed in these ten masters.

## SQL review

All tables have an explicit auto-increment primary key, NOT NULL `is_active` default TRUE, InnoDB and the requested collation. All three parent relations have matching unsigned widths. Omitted ON DELETE actions restrict referenced-row deletion; no cascading deletion is present. InnoDB supplies supporting foreign-key indexes where needed; avoid duplicating composite-index left prefixes.

| Table | Key and fields | Uniqueness / relationship assessment |
| --- | --- | --- |
| country | unsigned SMALLINT PK; CHAR(2) iso_code; required VARCHAR(100) name | Global code and name uniqueness. Add application validation for exactly two ASCII letters; SQL alone permits shorter/non-letter values. |
| state | unsigned SMALLINT PK and required country_id; required code(10), name(100) | Unique code and name within country. Both composite indexes support country filtering. |
| gender | unsigned TINYINT PK; required code(20), name(50) | Both globally unique. Capacity 255 nonzero generated IDs; retain width. |
| blood_group | unsigned TINYINT PK; required code(5) | Globally unique code, no separate name. Preserve this shape. |
| religion | unsigned SMALLINT PK; nullable unique code(20); required unique name(100) | Multiple NULL codes intentionally allowed. |
| social_category | unsigned SMALLINT PK; required code(20), name(100) | Both globally unique. |
| caste | unsigned INT PK; nullable unsigned SMALLINT category FK; nullable unique code(30); required name(150) | Categorized names unique within category; uncategorized names currently NOT reliably unique. |
| sub_caste | unsigned INT PK; required unsigned INT caste FK; nullable code(30); required name(150) | Name unique within caste. Code has NO uniqueness requirement in baseline. |
| admission_category | unsigned SMALLINT PK; required unique code(30), name(100); nullable description(500) | Both global uniqueness constraints valid; description absence remains NULL. |
| document_type | unsigned SMALLINT PK; required unique code(30), name(100); requires_verification default TRUE | Both global uniqueness constraints valid. Verification flag is reference metadata only. |

Actual defect: nullable caste category defeats the intended name uniqueness for uncategorized rows. NOT NULL does not reject empty/whitespace-only names, codes have no normalization, and MySQL BOOLEAN is an integer alias: these are validation gaps relative to this module's new policy, not malformed SQL. Add strict API/service validation rather than claiming current SQL enforces them. SQL consumers remain responsible for normalization; unique indexes remain the race-safe final authority.

Optional improvements, not accepted schema changes: unique sub_caste codes, broader key widths, boolean CHECKs for direct SQL writers, master timestamps, and query-driven active/name indexes. Do not infer requirements from names, add institution IDs, or create standalone is_active indexes without query evidence.

## Required caste correction

Keep `uq_caste_name_category` for categorized rows. Add a stored generated name that is populated only for uncategorized rows; its unique index enforces exactly that missing rule. No reserved category ID, synthetic parent row, trigger, or application-only lock is needed.

```sql
ALTER TABLE caste
  ADD COLUMN uncategorized_caste_name VARCHAR(150)
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci
    GENERATED ALWAYS AS
      (CASE WHEN social_category_id IS NULL THEN caste_name ELSE NULL END) STORED,
  ADD CONSTRAINT uq_caste_uncategorized_name UNIQUE (uncategorized_caste_name);
```

Multiple generated NULLs for categorized rows are intentional. Updating names or moving a caste between categories recomputes the key. MySQL supports unique indexes on generated columns ([reference](https://dev.mysql.com/doc/refman/8.4/en/create-table-secondary-indexes.html)). Map this as a persisted Django GeneratedField with a nullable character output, excluded from write serializers/forms. Preserve the original FK column and constraint. Do not use `nulls_distinct=False` or a conditional UniqueConstraint as a MySQL fix. The SQL above is a proposed migration operation, not executed in this step.

Before adoption, detect conflicts under the destination collation:

```sql
SELECT caste_name COLLATE utf8mb4_0900_ai_ci AS name_key, COUNT(*) AS n
FROM caste WHERE social_category_id IS NULL
GROUP BY name_key HAVING COUNT(*) > 1;
```

Also check normalized names/codes and categorized groups before changing data. Resolve duplicates with an explicit survivor/reference-remapping plan and audit trail; never silently delete them. Run this query on MySQL staging, not the current incompatible MariaDB collation.

## Canonical values and equality

For every entry path (API, admin, imports, seed commands), normalize strings to Unicode NFC; strip leading/trailing Unicode whitespace. Collapse internal whitespace runs to one space in names, preserving spelling/case/accents. For codes, uppercase and reject internal whitespace; country ISO codes must be `[A-Z]{2}`. Other codes allow ASCII letters, digits, underscore, hyphen and plus (blood groups need plus/minus), within original lengths; do not invent a clinical list in this step. Empty optional codes become NULL: religion_code, caste_code, sub_caste_code. Empty description becomes NULL, with internal prose formatting preserved. Required empty strings are rejected. Recheck length after normalization and uppercase conversion. Reject unknown fields and non-boolean flag input.

The supplied collation compares case and accents insensitively, so names such as `Cafe`, `CAFÉ` collide within the same unique scope; values retain their original display spelling. It is NO PAD, so do not assume trailing spaces compare equal. CHAR storage behavior differs from VARCHAR, reinforcing explicit code normalization. See [MySQL Unicode collations](https://dev.mysql.com/doc/refman/8.0/en/charset-unicode-sets.html). Python casefold/accent removal is not a substitute for database equality. Prevalidation improves errors, but catch named unique-constraint violations after concurrent writes and return a stable conflict response.

## Ownership, access and lifecycle

All ten masters are global. Authenticated active users may read active references. A platform-granted `common_reference.maintain_reference` capability gates every mutation, including Django admin and bulk commands. Django model add/change permissions alone, `is_staff`, an institution Admin role, tenant membership, or a caller-supplied institution ID never grants it. Platform superusers are explicitly global authorities. Only platform account administrators can grant this capability; self-service account updates cannot change it.

Maintainers may list inactive rows with an explicit filter. Ordinary selectors return only active rows with active ancestors: state/country, caste/optional category, sub_caste/caste/category. NULL caste category is valid. Deactivation does not cascade flags or alter old relationships. Existing records display their historical reference labels (marked inactive) through authorized detail/label resolution. New selections must be active, including ancestors; edits may retain an unchanged historical FK. Parent deactivation prevents new choices without rewriting children. Reactivation is explicit and uniqueness still includes inactive records.

No hard-delete API in normal workflows; return 405. Default administration offers deactivate/reactivate. Any future platform-only purge must check references and use ORM PROTECT plus restrictive database FKs, handle concurrent reference creation, and emit audit history. Future modules must adopt this reference contract; their implementations are not reviewed here.

DRF list querysets must apply visibility rules before pagination/counts; detail lookup also checks visibility. Object checks alone do not filter lists ([DRF permissions](https://www.django-rest-framework.org/api-guide/permissions/)). Shared transactional services enforce normalization, permission checks, parent validity and atomic audit writes across API/admin/seed paths. Serialize competing parent-state changes and selection writes with a consistent parent-lock ordering. Seeds use a trusted service identity, natural keys and idempotent updates, never fixed PK assumptions or silent reactivation.

## Application and frontend boundaries

`accounts`: custom AbstractUser-based user from the first migration, authentication, platform capability grants, account lifecycle. No institution models yet. Fresh installations use an explicitly named `user_account` table and `user_id`; this is a new accounts design, not a declaration of compatibility with the old full-schema user table. Adoption needs a separate auth comparison and migration plan.

`core`: shared validation/error contracts, unsigned field classes, UTC/audit infrastructure, static registry and health checks. No imports of domain models. `accounts` depends on core; core audit actor relation uses a lazy swappable user reference in a later migration to avoid a dependency cycle.

`common_reference`: owns exactly the ten models, selectors, transactional services, serializers, versioned routes, admin, seeds and tests. Preserve singular db_table names and explicit db_column names. Use foreign-key attributes such as `country` with `db_column='country_id'` to avoid country_id_id. Explicit custom unsigned TINYINT/SMALLINT/INT auto fields must preserve db_type, rel_db_type, migration deconstruction and range validation; SmallAutoField alone is signed and does not preserve the baseline. Preserve CHAR(2) with a migration-safe custom field. Do not turn these into unmanaged models for the default fresh install.

Frontend: `app/` owns shell/router/providers; `features/auth/` owns session flows; `features/common-reference/` owns typed schemas, API queries, tables and forms; `shared/` owns HTTP/errors/UI primitives; `pwa/` owns worker/update/offline policy. Future features consume exported typed selectors and APIs, never write another module's tables. Browser permission-based navigation is usability, not authorization.

## Static trusted module registry contract

Store frozen descriptors in source code; validate duplicate codes/namespaces, unknown dependencies and cycles at startup. Only explicitly installed, trusted Django apps appear. There is no package upload, runtime pip install, dynamic import from database strings, or arbitrary plugin execution.

| Code | App | Dependencies | API namespace / prefix | Navigation | Permission codes |
| --- | --- | --- | --- | --- | --- |
| CORE | core | none | core / `/api/v1/core/` | none | core.view_audit (platform only) |
| ACCOUNTS | accounts | CORE | accounts / `/api/v1/auth/` | account/profile | accounts.manage_platform_access |
| COMMON_REFERENCE | common_reference | CORE, ACCOUNTS | common_reference / `/api/v1/common-reference/` | Reference data, order 100, child route for each table | common_reference.view_reference, common_reference.maintain_reference |

Navigation descriptors contain route, label, order and required capability. Per-resource add/change/view permissions may refine access but cannot replace the global maintain gate. Read capability is part of the active-user baseline. Registry dependencies do not replace Django migration dependencies. Existing full-schema PLATFORM ownership catalog entries are not used for runtime registration; reconcile them explicitly only during adoption. Future module names are roadmap boundaries, not installed registry entries.

## Required platform foundation

API resources preserve explicit ID field names, use bounded pagination, allowlisted search/order/filter fields, predictable validation errors and protected-delete errors. Use atomic writes and append-only audit events containing actor, action, table, PK, timestamp, request ID and before/after values. Do not audit passwords/tokens. Reads of audit history require a separate platform capability.

Use short-lived JWT access tokens in memory and rotating refresh tokens in Secure HttpOnly SameSite cookies under same-origin deployment. Cookie refresh/logout require CSRF protection and Origin checks; do not store credentials in localStorage. Enable both ROTATE_REFRESH_TOKENS and BLACKLIST_AFTER_ROTATION plus `rest_framework_simplejwt.token_blacklist` and its migrations ([settings](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/settings.html)). Logout blacklists refresh tokens; access tokens remain valid until expiry unless server-side account/session revocation is checked. Check active user/current permissions on protected requests; JWT role claims alone cannot authorize writes. Test refresh replay and concurrent tabs; single-flight refresh coordinates tabs, and stronger token-family replay protection is separate work, not a Simple JWT default claim.

PWA first caches only versioned public shell/assets and provides a clear offline screen. Authentication, admin and API responses are NetworkOnly; no offline mutation queue or automatic write replay. A later explicitly approved reference snapshot cache must be bounded, labeled stale, exclude sensitive/auth data and be cleared on logout/user change. Installability requires HTTPS (localhost exception), manifest, icons, service worker and tested update handling. Platform-specific install prompts differ.

## Installation and adoption

Fresh default: create empty MySQL `sims_reference_dev` with the required collation; set root credentials through environment for local use; configure custom user before any migration; apply accounts/core/reference migrations only. Declare exact unsigned fields and generated column in migration state. Seed after schema verification. Do not execute the 265-table full SQL file, reuse existing auth tables, or run migrations against local sims_v6 by default.

Existing deployment: first inventory version, engine/collation, SHOW CREATE TABLE, row counts, all incoming FKs, auth schema, migration history and actual application writers. Take and restore-test backups; work on a staging clone. Profile normalization/collation conflicts and orphan references; stop on incompatibilities. MySQL migration from MariaDB requires a logical export/import and destination validation, not copying its data directory. Preserve IDs and all references during reconciliation. Change collation only after collision analysis.

If existing DDL exactly matches the initial baseline, carefully reviewed SeparateDatabaseAndState or fake-initial adoption may register state; fake-initial's existence check is not proof of schema equivalence. Apply caste correction as a subsequent migration after cleanup. Never blanket fake migrations. Schedule write quiescence for normalization/DDL; MySQL schema DDL is not one rollbackable transaction. Rollback is restore-and-replay or an explicitly tested forward fix. Full-schema adoption and legacy authentication mapping are separate deliverables.

Accepted deviations: one internal generated caste column/unique index; canonical input rules; application-level inactive-parent rules; deactivation-only ordinary API; additional accounts/core/audit tables required by the platform; static COMMON_REFERENCE ownership rather than using the old PLATFORM catalog. Retained: all ten singular names, explicit keys, unsigned widths, nullability, original unique scopes, collation and defaults. No original SQL file changes in Prompt 1.

## Implementation acceptance criteria

1. Fresh MySQL 8.4 migration succeeds; schema introspection verifies all ten table names, PK/FK widths and signedness, CHAR(2), defaults, collation, indexes and generated column. No unrequested domain tables. Migration state has no drift.
2. NULL-category duplicate caste names fail at the database level, including concurrent requests and direct SQL; categorized duplicates fail in the same category and succeed across categories. Moving between NULL/non-NULL categories cannot bypass uniqueness. Inactive names remain reserved.
3. Normalization is identical in API/admin/seed flows; optional blanks become NULL; multiple missing optional codes succeed; required blanks and oversize values fail. Verify case/accent collisions and whitespace behavior on real MySQL, not SQLite.
4. An institution Admin, ordinary staff member and forged JWT claim cannot mutate global masters or grant the capability. Maintainer can. Anonymous requests fail. List, detail, search/count and inactive-reference policies agree.
5. Deactivation preserves historical FKs; inactive-parent choices fail for new assignments. Retaining an unchanged historical FK succeeds. Referenced hard deletion fails at ORM and database layers, including concurrent operations.
6. Auth login/refresh/logout, blacklist migrations, replay rejection, CSRF, inactive users and permission revocation pass against the locked Django/DRF/JWT combination. No secret in source or frontend artifacts.
7. Audit writes commit/rollback with business changes; idempotent seeds preserve IDs and inactive state. Audit API has platform-only access.
8. React build/type checks and accessible keyboard/form/error flows pass. Registry cycles and unknown dependencies fail startup; disabling navigation does not weaken API checks.
9. PWA installs on supported test browsers, opens its shell offline, never caches tokens/API data, never replays writes, and updates without losing unsaved edits.
10. Existing-database adoption is separately rehearsed on a restored clone, with duplicate resolution, FK checks, row-count reconciliation and rollback evidence. Production includes Linux Gunicorn/Nginx, HTTPS, UTC, health checks, backups and exact maintained dependency locks.

Verification for Prompt 1: the ten source definitions were read and their key/nullable/index structure reviewed; no later caste fix was found by search. Official compatibility sources were consulted. No MySQL 8.4 execution, migration generation, UI build or security test is claimed. The MariaDB mismatch and Simple JWT documentation gap are explicit foundation gates for Prompt 2.
