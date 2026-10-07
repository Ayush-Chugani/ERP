# M31 Professional Memberships and Academic Bodies

Implemented from all 18 prompts in the supplied pack, using the established React/MUI frontend and shared staff-activity architecture. Source DOCX and consolidated SQL are unchanged. Earlier queued modules remain separate work.

## Source schema and shared dependencies

StaffProfessionalMembership maps exactly eleven canonical columns: staff_activity_id (the sole PK/FK identity), organization_id, membership_type_id, membership_number, membership_start_date, membership_expiry_date, is_lifetime_membership, role_type_id, participation_level_id, renewal_required, membership_status. The source five foreign keys, date CHECK, nullable organization-scoped unique number and native five-value ENUM remain intact. Identifiers preserve unsigned BIGINT/SMALLINT/TINYINT types. Frozen native DDL retains InnoDB/utf8mb4/collation/defaults.

The missing membership_type master is added under staff_profile using source type_code/type_name/is_active columns. ExternalOrganization, RoleType and ParticipationLevel are reused. StaffActivity owns employee, institution, department, audit metadata, verification and approval. A separate platform_professional_memberships_status_history follows the existing approval-history extension with native append-only guards. No identity, employee, document, or approval columns are added to the canonical child.

## Behavior and authorization

- Blank/whitespace membership numbers become NULL. Multiple NULL numbers are allowed. A nonempty number must be unique within its organization using the database's case/accent-insensitive collation; the same number in another organization is allowed. Archived records retain their number reservation; archiving does not make that organization/number reusable. Parent ownership corrections require an audited administrative process rather than recreating a conflicting number. Friendly preflight validation is backed by the database unique constraint and transactional rollback.
- Dates are optional, but expiry cannot precede start when both exist. Assignment ownership is derived from a dated, scoped EmployeeAssignment. Creation derives context_date from membership_start_date when context_date is omitted; an explicit context_date is required when start is unknown. Parent context is immutable after creation; membership dates can be corrected on eligible drafts without reassigning ownership.
- A lifetime flag normalizes ACTIVE/EXPIRED initial state to LIFETIME. Lifetime with expiry or renewal_required=True is rejected. Status LIFETIME without the flag is rejected. Incompatible SUSPENDED/CANCELLED combinations are rejected, not overwritten. Lifetime conversion on an existing record uses the authorized mark-lifetime action.
- Staff edits use UPDATE in DRAFT/RETURNED approval states. PATCH cannot change membership_status or lifetime identity; lifecycle endpoints prevent bypass. Read-only Django admin prevents transactional records from bypassing services. Master administration is separately authorized and audited, with deletion disabled.
- Approval workflow (DRAFT, SUBMITTED, UNDER_REVIEW, RETURNED, VERIFIED, APPROVED, REJECTED, WITHDRAWN) is separate from membership status (ACTIVE, EXPIRED, SUSPENDED, CANCELLED, LIFETIME). Existing independent verification/approval rules apply to approval workflow.
- Membership actions require VERIFY plus READ, a DRAFT/RETURNED/APPROVED parent, current version, idempotency key and reason. suspend: ACTIVE/EXPIRED to SUSPENDED. cancel: ACTIVE/EXPIRED/SUSPENDED to CANCELLED. reactivate: SUSPENDED/EXPIRED to ACTIVE if expiry is not past. renew: ACTIVE/EXPIRED to ACTIVE with an explicit future expiry later than the current expiry. mark-lifetime: ACTIVE/EXPIRED to LIFETIME, clearing expiry and renewal. CANCELLED and LIFETIME have no outgoing membership transitions under the selected default policy. Imported initial administrative states require VERIFY too.
- Renewal_due is a derived indicator: ACTIVE, non-lifetime, renewal_required=True, expiry between the effective date and configurable window end. It is not persisted or allowed to overwrite manual states. Days-to-expiry and tenure are query-free derived values. Past ACTIVE dates are not silently rewritten on reads; explicit automation applies policy.

Permissions: PROFESSIONAL_MEMBERSHIPS.ACTIVITY.{READ,CREATE,UPDATE,DELETE,VERIFY,APPROVE,EXPORT}; PROFESSIONAL_MEMBERSHIPS.MASTER.UPDATE. M15 SELF/department/campus/institution/global scope, live assignments/delegations and DENY precedence are reused. CREATE also requires READ; reports intersect READ and EXPORT; shared masters require global MASTER.UPDATE. No automatic grants.

## API and UI

UI: #/professional-memberships, optionally ?employee=<string ID>. Staff profiles link to this scoped route. Forms provide searchable, paginated masters, required organization/type, optional number/dates/role/level, lifetime clearing of expiry/renewal, inline errors, unsaved-change protection, and stable retry keys. Tables/mobile cards, detail, approval timeline, read-only change history, renewal reports and a dry-run-first CSV dialog are included.

Base /api/v1/professional-memberships/ supports GET/POST collection, GET/PATCH/PUT/DELETE <id>/, and custom actions. Native IDs are returned as strings. Foreign keys use *_id on writes and relationship names plus display labels on reads.

Create example (Idempotency-Key required):

```json
{
  "context": {"employee_assignment_id": "123", "academic_year_id": null},
  "activity": {
    "organization_id": "45",
    "membership_type_id": "2",
    "membership_number": "MEM-2026-001",
    "membership_start_date": "2026-01-01",
    "membership_expiry_date": "2027-12-31",
    "is_lifetime_membership": false,
    "role_type_id": null,
    "participation_level_id": null,
    "renewal_required": true
  }
}
```

For unknown start dates, use null and supply context.context_date to select the dated employee assignment. For historical memberships that predate the current employee assignment, supply that assignment context date explicitly; the form supports this separately from membership_start_date. Do not send staff_activity_id, employee_id or approval fields.

PATCH/PUT body: {"activity":{...},"version":"..."}. PATCH preserves omitted fields. PUT requires organization/type, clears omitted nullable fields, and uses ACTIVE/false boolean defaults; it cannot implicitly change protected status/lifetime fields on an existing record. DELETE body {"version":"..."} archives only eligible parent states and retains child/evidence/history.

POST <id>/workflow/ uses action/remarks/version and Idempotency-Key for the shared approval workflow. POST <id>/lifecycle/ uses action/remarks/version and Idempotency-Key for membership actions; renew additionally requires new_expiry_date. Invalid state/date combinations return field errors (400), permission failure is 403, out-of-scope detail is 404, stale version or incompatible retry is 409. Database race conflicts roll back atomically.

Filters: employee, institution, campus, department, academic_year, organization, membership_type, role_type, participation_level, membership_status, status (approval), is_lifetime_membership, renewal_required, renewal_due, start_from/start_to, expiry_from/expiry_to, mine=1 and search (membership number/organization). Safe ordering accepts staff_activity_id, membership_number, membership_start_date, membership_expiry_date, membership_status and organization__organization_name with optional '-'. Default -staff_activity_id, bounded page/page_size. Report output groups are capped at 100 values with explicit truncation metadata and UI notice.

GET summary/: status counts, 30/60/90-day expiry counts, renewal-required/due counts and groups by organization/type/role/level/department/employee. GET export/: authorized CSV, 10,000-row cap and shared formula-escaping. The collection itself is the paginated report endpoint. GET <id>/timeline/ and <id>/audit_history/ are separately paginated, authorization-checked histories. Change history returns actor ID/time/action and sanitized details; raw membership numbers and file contents are not copied into audit detail snapshots.

GET lookups/ and lookups/{assignments,types,organizations,roles,levels,statuses,years}/ provide capabilities and scoped/searchable choices. type-admin/ GET/POST and type-admin/<id>/ PATCH plus governed Django admin manage MembershipType. Existing organization/role/level masters are selected, not silently created.

Private evidence uses existing M13 storage/scanner/content/size checks: POST <id>/evidence/ with multipart file/title/category/version/optional replaces; GET <id>/evidence/<attachment_id>/download/. Replacement retains old links/files. Downloads recheck membership scope and M13 confidentiality. Current accepted formats are the shared PDF/PNG/JPEG pipeline.

## Controlled imports

GET import-template/ downloads headers. POST import/ accepts {"csv":"...","dry_run":true} and a stable Idempotency-Key of 1-80 safe characters. The UI validates first, then offers commit. Defaults are dry-run; limit is 200 rows and 256KiB UTF-8 per request. Headers are assignment/context IDs plus canonical writable child fields. Rows use existing approved master IDs; no fuzzy organization creation or client-provided activity identity.

Each row goes through the same serializer/service inside a savepoint. All invalid row numbers/field errors are reported. The bounded batch commits only if every row is valid; dry-run or any row error rolls back parents, children, status history and command receipts. Stable batch key plus row number makes successful batch retries idempotent. A changed row with an already-used key conflicts; a duplicate number with a new key is rejected. Imports never implicitly update existing records. Batch audit records actor, counts, dry-run/commit result, not uploaded content. Partial success is achieved by correcting/splitting bounded batches, not silently dropping invalid rows.

The existing shared import/export convention is CSV. For XLSX source spreadsheets, explicitly export the approved sheet to UTF-8 CSV with identifiers and membership numbers kept as text and dates as ISO YYYY-MM-DD, then use dry-run. No new XLSX upload parser or untrusted workbook execution is introduced.

## Expiry automation and notification boundary

The command is scoped to an explicit service actor and is not scheduled automatically:

```
python manage.py expire_professional_memberships --actor-id 123 --dry-run --as-of 2026-09-28 --batch-size 100
python manage.py expire_professional_memberships --actor-id 123 --batch-size 100
```

Dry-run reports eligible records and renewal_due without mutating memberships. Applied runs require SIMS_MEMBERSHIPS_AUTO_EXPIRY_ENABLED=1. Candidates are non-archived ACTIVE non-lifetime rows with expiry before as-of. Each row is locked, reauthorized and checked again. SUBMITTED/review-frozen parents and manual membership states are not changed. Each eligible row is an atomic transaction; batches use PK keyset iteration, size 1-1000. Repeated runs do not duplicate state transitions; aggregate batch audit and counts remain. Failures are counted and cause a nonzero command result without exposing raw membership content.

SIMS_MEMBERSHIPS_RENEWAL_WINDOW_DAYS defaults to 30. Configure cron/Task Scheduler only after the runtime and service actor's scoped grants are accepted; the example applied command can be scheduled daily using the application's configured timezone. A separate existing communication adapter can consume authorized renewal_due results and deduplicate reminders by activity/expiry/window while resolving approved recipients. This delivery does not send reminders or install a schedule. PROFESSIONAL_MEMBERSHIPS_EVENT_HANDLER remains empty; the existing after-commit approval adapter boundary can be configured later, with event-ID deduplication and immutable-history reconciliation.

## PWA and security review

Established React/API forms are used instead of parallel Django templates, as allowed by the pack. Shared JWT/session transport is retained; Django admin retains its CSRF middleware. M31 does not introduce authentication exemptions. Server scope applies before records, reports, lifecycle actions, imports or downloads. Strict field allowlists reject ownership/status mass assignment. The service is authoritative for every write path; admin transactional records remain read-only.

Private APIs stay NetworkOnly/no-store under existing PWA policy. Static shell/install assets are precached; membership records, CSV content and tokens are not persisted in browser storage. Offline editing/commits are disabled, drafts remain in component memory, ambiguous command retries reuse keys, and stale writes require refresh. Organization text and audit strings render as text; CSV uses shared formula protection. Lookups use scoped availability, pagination and module throttle (default 120/min).

## Deployment and rollback

1. Back up and rehearse against the target MySQL/MariaDB version. Local verification uses MySQL 8.4. Compare M31_SCHEMA_INVENTORY.json. Pre-existing tables are never silently adopted; use an explicit schema review before any adoption.
2. Run manage.py migrate --plan, then migrate. New migrations: staff_profile.0008_membershiptype and professional_memberships.0001_initial/0002_retain_status_history. Populated source/master/history reversal is refused; empty reverse/reinstall is tested in isolation.
3. Run manage.py seed_professional_memberships after M15 action setup. It installs compatible type/workflow/permission configuration without grants and rejects incompatible active configuration.
4. Assign approved scoped permissions and configure shared M13 storage/scanning. Enable required IAM switches and SIMS_PROFESSIONAL_MEMBERSHIPS_ENABLED=1 after acceptance. Automation remains separately controlled by SIMS_MEMBERSHIPS_AUTO_EXPIRY_ENABLED=0. Set the renewal window and optional adapter explicitly.
5. Deploy the production frontend bundle. Smoke-test own versus departmental scope, creation with nullable dates/numbers, independent approval, administrative actions, renewal/lifetime, evidence downloads, import dry-run/commit, report scope and mobile/offline/update behavior.
6. Operational rollback: disable M31 runtime/automation and preserve data. Do not drop populated tables, fake migrations, or remove retention guards. Shared masters and evidence stay intact.

## Performance and acceptance

M31_QUERY_PLANS.json contains eight actual ORM EXPLAIN plans. Native FK indexes and unique organization/number index are retained; list query-count tests ensure constant query counts. Evaluate a status/lifetime/expiry/PK composite index only against measured target workloads, and consider renewal_required selectivity separately. Local empty/small development plans are not a production load benchmark. Large master selectors are search-driven and paginated.

M31_TRACEABILITY.json maps all prompts; M31_VERIFICATION.json records final automated checks and remaining operational acceptance. Production volume/device acceptance, deployment backup rehearsal, role grants, scheduler setup, storage/scanner configuration and notification delivery remain operator steps. No production-ready claim is made before those checks are accepted.


## Final local verification

Passed: 681 full-backend tests and 139 subtests; 27 final M31 backend tests and 18 subtests; 113 full-UI tests across 23 suites; 12 final focused M31/profile UI tests (including the additional historical-date case); 12 shared transport/PWA tests. Final TypeScript/Vite/PWA build, Django system checks, migration drift checks, OpenAPI validation, lint, schema inspection and eight ORM query plans passed. The pre-existing M13 storage-key warning remains unrelated to M31. Runtime, automated expiry and outbound adapter remain disabled.
