# M32: academic and professional contributions

Implementation follows the 32 prompts in the supplied pack. The source DOCX and consolidated SQL remain unchanged. See M32_DESIGN.md for the data dictionary and integration decisions, M32_TRACEABILITY.json for prompt-to-file coverage, and M32_VERIFICATION.json for check results. This is a local implementation handoff, not production activation or real-device acceptance.

## Delivered

The professional_contributions app provides the exact 17-column source subtype and eight foreign keys, a source-faithful five-column contribution-type master, and append-only platform workflow history. It reuses dated employee ownership, independent approval/verification, M15 scopes and audit, actor-bound idempotency, optimistic versions, M13 private evidence, and soft archive. No generic parent-write or admin-write bypass exists. Optional context links can coexist; optional dates and counts remain null unless recorded. Counts accept 0?65535 and reject fractions/negative values. The type master is configurable, with no hardcoded numeric IDs or mandatory illustrative type rules.

The React/MUI PWA adds `#/professional-contributions` and a staff-profile link. It includes remote paginated reference search, list/filter/sort, responsive cards/table, add/edit, policy hints, duplicate preview, workflow, evidence and history, report aggregates and CSV. All context fields remain available rather than hiding SQL-valid combinations; type metadata highlights requirements. Entered values stay in memory after errors, error focus is restored, and offline writes/downloads are disabled. Current API IDs are strings in read responses and the UI. Authenticated data uses existing NetworkOnly/no-store policy; no private drafts or student data enter persistent browser storage.

## API contract

Base: `/api/v1/professional-contributions/`.

- `activities/`: GET scoped bounded list; POST aggregate create with Idempotency-Key.
- `activities/{id}/`: GET detail; PATCH partial child edit; PUT full child replacement; DELETE eligible soft archive. Writes require current `version` except creation.
- `activities/{id}/workflow/`: POST `{action, remarks, version}` with Idempotency-Key. Existing submit/review/return/verify/approve/reject/withdraw transitions apply.
- `activities/{id}/evidence/`: multipart POST file/title/category/version, optional replaces. M13 scanner and confidentiality rules apply. GET `evidence/{attachment_id}/download/` reauthorizes access.
- `activities/{id}/timeline/` and `audit_history/`: scoped paginated history; direct changes to native status-history rows are rejected by database triggers.
- `activities/duplicate-preview/`: read-only POST with the create body. Returns up to five readable candidate IDs; no parent, audit, receipt or event is written. Whitespace is normalized in topic/reference; repeated assignments remain valid.
- `activities/summary/`: READ intersect EXPORT aggregates. Missing count sums stay null. `reviews_recorded`/`candidates_recorded` distinguish missing values from zero. Recent means contribution_date in the inclusive server-local-date window today minus 29 days through today, additionally restricted by selected filters.
- `activities/export/`: formula-safe UTF-8 CSV, up to 10,000 matches, canonical PK order, 100-row keyset pages with live permission rechecks. Audit records export initiation and matching count; a network interruption is not asserted as completed delivery. Snapshot upper ID prevents new records extending an export; this is not a transactional reporting snapshot.
- `lookups/`: capability metadata; `lookups/{assignments,years,types,statuses,organizations,journals,conferences,programmes,courses,students}/`: bounded choices. Large context searches require two characters. Type options include required_fields.
- `type-admin/`: global MASTER.UPDATE controlled GET/POST and PATCH by numeric ID, with audit. No delete endpoint. Type master fields are contribution_code(60), contribution_name(180), description(500, optional), is_active.

Example POST body (replace illustrative IDs with authorized lookup choices):

```json
{
  "context": {"employee_assignment_id": "17", "context_date": "2026-09-28"},
  "activity": {
    "professional_contribution_type_id": "3",
    "title_topic": "Session chair",
    "conference_event_id": "8",
    "contribution_date": "2026-09-28",
    "number_of_reviews": 0
  }
}
```

The assignment context date may differ from optional contribution dates. If omitted, contribution_date or start_date supplies it; if all are absent, explicitly supply context_date. Ownership cannot be reassigned after creation. Parent title mirrors topic or falls back to type name. Submission revalidates active references and policy. Partial edits validate the complete locked record. API/model/form/service date and count rules agree; Django ModelForm persistence is disabled so callers must use the transactional service.

Filters: search, employee, institution, campus, department, academic_year, type, organization, journal, conference_event, programme, course, student, appointment_reference_number, status, verification_status, date_from/date_to, mine. Date filters explicitly use contribution_date; undated records are included only when no date bound excludes them. Deterministic ordering permits staff_activity_id, title_topic, contribution_date and professional_contribution_type__contribution_name, optionally descending. Pagination is capped at 100.

## Permissions and confidential references

Module code: PROFESSIONAL_CONTRIBUTIONS. ACTIVITY actions: READ, CREATE, UPDATE, DELETE, VERIFY, APPROVE, EXPORT. MASTER.UPDATE is global for the shared type catalogue. M15 GLOBAL/INSTITUTION/CAMPUS/DEPARTMENT/SELF scopes and DENY precedence apply; stale actor/grant state is re-evaluated. Creator/subject cannot independently verify or approve their own record. Parent workflow, not a second child status, governs editability.

Programme/course contexts must match the parent institution and authorized academic scope. Shared organizations, journals and conferences have no institution field; authorized users receive only active minimal catalogue labels. Student lookup additionally requires existing People Master read access and M32 row scope. Selecting a student must match the parent institution. If People Master access is later removed, student-linked contributions disappear from API/export/admin and service mutations reject them; their underlying history is retained. Institutions must provision these permissions deliberately. Global superuser status alone does not bypass M32 M15 grants.

## Type policy extension

Use the governed master API/admin to add a stable code and label; no model migration is needed. `seed_professional_contributions --example-types` can install four optional source catalogue examples without overwriting existing rows. Ordinary seed installs only workflow/permission configuration and grants nobody access.

`PROFESSIONAL_CONTRIBUTIONS_TYPE_RULES` in deployment Django settings defaults to `{}`. Example only, enable after institutional acceptance:

```python
PROFESSIONAL_CONTRIBUTIONS_TYPE_RULES = {
    "JOURNAL_REVIEWER": ["journal_id", "number_of_reviews"],
    "SESSION_CHAIR": ["conference_event_id"],
}
```

The policy is keyed by code, never IDs. Unknown configured fields fail validation, prompting administrator review. Zero counts satisfy required-value policies. Restart workers after a settings change; review existing drafts before introducing stricter rules. No institutional policy is enabled merely because it appears as an example in the prompt pack.

## Deployment and rollback

1. Back up and rehearse on a production-like MySQL 8/MariaDB environment with CHECK enforcement. Check version, InnoDB, utf8mb4 collation, referenced PK signedness, orphan references and existing table names. Verify prerequisites and planned migration order with `manage.py migrate --plan`.
2. If source tables already exist, stop: frozen installers intentionally reject silent adoption. Compare SHOW CREATE TABLE with M32_SCHEMA_INVENTORY.json and the source; approve a database-specific state/adoption migration. Do not broadly fake migrations or drop populated tables.
3. Keep `SIMS_PROFESSIONAL_CONTRIBUTIONS_ENABLED=0`. Apply staff_profile.0009, professional_contributions.0001 and .0002. Do not reverse populated source/history tables: guards deliberately reject data loss. Validate history triggers and source CHECK/FKs.
4. Run `manage.py seed_professional_contributions`. Configure active types and explicitly grant least-privilege M15 scopes; grant People Master student access only where required. Review type policies and document institutional acceptance. Keep event adapter blank unless an approved shared delivery integration is configured; no outbound messages were sent by implementation.
5. Build the frontend (`npm run build`), deploy its versioned PWA assets and run backend collectstatic using existing deployment process. Restart workers. The build changes precache asset hashes automatically; authenticated APIs remain NetworkOnly. Existing service-worker update UX governs activation.
6. Enable IAM flags and M32 runtime only after scoped-role acceptance. Smoke-test own/department/institution reads, unauthorized ID, student denial, create/retry, edit conflict, independent workflow, evidence access, aggregate/null counts, export and archive. Check the existing system health path and database connectivity.
7. Review phone/tablet/desktop keyboard and screen-reader use, date inputs, remote choices, focus/error recovery, service-worker update, offline reconnect and sign-out on supported browsers. Vitest/MSW component tests are automated; real-device/browser-installability acceptance remains an operational release gate.
8. Monitor errors/latency and SQL slow-query plans under representative load. Roll back application exposure by disabling M32 and restoring prior assets/code while retaining populated schema/audit. Restore from a verified backup only under an approved incident plan; migrations never silently delete production data.

## Diagnostics and performance

Every M32 API response carries X-Request-ID. Standard Python logger `sims.professional_contributions` emits an allowlisted event with correlation ID, actor/record ID, operation, HTTP status and duration_ms; contribution narratives, search terms and student PII are excluded. M15 audits share correlation IDs. Configure the existing logging sink to retain structured extras and derive API latency/error-rate dashboards. Alert on sustained 5xx, unusual 409 conflict spikes and slow SQL; investigate with the correlation ID and audit. 409 can be a normal stale edit; refresh or retry the original idempotent request. 404 can reflect disabled runtime or revoked object/student scope. Invalid type policy requires configuration review, not client workarounds.

M32_QUERY_PLANS.json records eight actual ORM EXPLAIN plans on the local database. This is not a production-volume benchmark. List/detail eager-load context relations and constant-query tests include all six contexts. FK indexes are retained; the source's optional type/date composite should be evaluated against measured workloads before a separate migration. Leading-wildcard text searches may scan; require realistic-volume acceptance. No speculative composite indexes or shared permission-sensitive caches were introduced.

## Release review

Resolved during review: strict unsigned count boundaries, invalid policy errors, complete-record PATCH validation, scoped context selection, student-access revocation in API/service/admin, append-only history, bounded streaming exports, private correlated diagnostics and non-blocking duplicate warnings. High-risk regressions are covered by module tests plus the full-suite results in M32_VERIFICATION.json. Production activation, reference-policy acceptance, real-device UAT and representative-volume benchmarks remain explicit operational gates. No production-ready approval is implied by local test success.
