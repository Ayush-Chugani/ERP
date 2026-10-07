# M30 awards, honours and recognitions

Implemented from the supplied M30 pack, in its prompt sequence. The original DOCX and consolidated SQL remain unchanged. Source schema and integration decisions are in M30_DESIGN.md. Earlier queued modules are not marked complete by this delivery.

## Delivered

- Canonical ten-column staff_award and AwardCategory master, exact unsigned FK types, nullable category/organization, required name/date, DECIMAL(14,2) values, CHAR(3) currency default INR, and database nonnegative checks.
- Transactional parent/child creation, scoped CRUD, full/partial update, soft archive, independently reviewed workflow, optimistic concurrency, idempotent creation/workflow, retained immutable status history and M15 audit.
- Private scanned evidence and replacement history through M13; no file/ownership/status columns added to the award child.
- Responsive MUI forms, tables/mobile cards, detail/timeline, financial validation, reports, filters/reset, staff-profile navigation, memory-only drafts, offline write prevention and stable retry keys.
- Read-only scoped StaffAward admin; AwardCategory API and Django admin require AWARDS.MASTER.UPDATE. Shared categories cannot be deleted through these interfaces. Organization selection reuses existing masters.
- Scoped CSV and category/department/date summaries. Cash prizes and incentives are summed separately per currency. Null is not zero; no exchange conversion or mixed-currency grand total.

## API contract

Base: /api/v1/awards/. UI: #/awards, optionally ?employee=<string ID>.

POST activities/ requires an Idempotency-Key header; example:

```json
{
  "context": {"employee_assignment_id": "123", "academic_year_id": null},
  "activity": {
    "award_name": "Research excellence award",
    "award_date": "2026-09-01",
    "award_category_id": null,
    "awarding_organization_id": null,
    "citation_details": "Recognition for published research",
    "award_reference_number": "CERT-2026-01",
    "cash_prize_amount": "12500.00",
    "incentive_amount": "0.00",
    "currency_code": "INR"
  }
}
```

award_date supplies the dated assignment context. If context_date is explicitly supplied it must match. Context/ownership cannot be reassigned after creation. For a date/context correction, recreate an eligible draft and archive the superseded record.

Read responses use string IDs, source relationship names (award_category, awarding_organization), category_name and awarding_organization_name labels, exact amount strings, and parent context/status metadata. Detail adds version, permitted actions, evidence and history. Zero is "0.00"; unspecified money is null. Send foreign keys with the _id suffix on writes.

PATCH activities/<id>/ sends {"activity":{...},"version":"..."}; omitted fields remain unchanged. PUT requires name/date, resets omitted nullable fields to null and omitted currency to INR. DELETE accepts {"version":"..."} and archives eligible records. Writes to stale versions return 409; refresh before applying another edit. Workflow POST activities/<id>/workflow/ sends action, remarks, version and stable Idempotency-Key. Independently reviewed verification/approval and required reasons follow shared workflow policy.

List/report filters: search (award name/reference/organization), employee, institution, campus, department, academic_year, category, awarding_organization, currency, status, date_from/date_to, mine=1, cash_prize_present/incentive_present, cash_prize_min/max, incentive_min/max. Amount filter values are decimal strings. Presence includes zero. Sort fields: staff_activity_id, award_name, award_date, award_category__category_name, with optional '-' prefix. Default: -award_date, then -PK. page/page_size use shared bounded pagination.

GET activities/summary/ returns count, bounded category/context/date/status groups, truncated_groups and totals_by_currency. Each currency entry has cash_prize_amount and incentive_amount as exact strings or null, including aggregates larger than DECIMAL(14,2). GET activities/export/ returns safe CSV (10,000-row cap). Reports intersect READ and EXPORT scopes; no permitted rows yields empty reporting data.

GET lookups/ describes creation/report capability; lookups/{assignments,categories,organizations,statuses,years}/ supports search/page. Category administration: category-admin/ GET/POST and category-admin/<id>/ PATCH. Django admin also supports governed category creation and activation/deactivation. Private evidence: POST activities/<id>/evidence/ (multipart file, title, category, version, optional replaces), GET activities/<id>/evidence/<attachment_id>/download/. Timeline is separately paginated.

## Permission and operation notes

AWARDS.ACTIVITY.{READ,CREATE,UPDATE,DELETE,VERIFY,APPROVE,EXPORT}; AWARDS.MASTER.UPDATE. All are evaluated by existing M15 assignment/delegation/override rules. DENY takes precedence. Staff SELF, departmental reviewers, institutional administrators and reporting roles receive only institution-approved scopes. No automatic user/role grants. Evidence additionally requires M13 confidentiality permissions.

Supported evidence categories: CERTIFICATE, AWARD, AWARD_LETTER, APPROVED_EVIDENCE, CITATION, APPROVED_PHOTO. Supported uploads use M13's currently configured PDF/PNG/JPEG pipeline, content checks, size limit, malware scanner, private storage and audited download. Archive retains evidence and command/history records.

## Deployment and rollback

1. Back up and rehearse on an isolated copy of the target MySQL/MariaDB schema. Native SQL refuses silent adoption of existing award tables: compare the saved source/installed inventory before any explicit adoption procedure. MySQL 8.4 was used locally; a different target engine/version needs its own acceptance run.
2. Run `python manage.py migrate --plan`, then `python manage.py migrate`. New migrations: staff_profile.0007_awardcategory, awards.0001_initial and awards.0002_retain_status_history. Frozen source DDL avoids Django-generated signed-ID/type differences. The only additional table is platform_awards_status_history, the established shared workflow-history extension.
3. Run `python manage.py seed_awards` after the M15 action catalogue. The idempotent command installs compatible type/status/permission configuration and refuses conflicting existing configuration; it never grants access.
4. Assign approved M15 scoped permissions, govern category/organization masters, and configure M13 private storage/scanning. Enable SIMS_IDENTITY_ACCESS_ENABLED and SIMS_IDENTITY_ACCESS_SECURITY_ENABLED as required by the platform, then SIMS_AWARDS_ENABLED=1. Current application default is 0. SIMS_AWARDS_RATE defaults to 120/min.
5. Deploy the frontend production bundle and verify sign-in, own versus department scope, independent review, private uploads/downloads, reporting, mobile layout, installation/reconnect and service-worker update behavior using target-environment accounts.
6. SIMS_AWARDS_EVENT_HANDLER remains empty. If later configured, its adapter must resolve recipients, queue through existing infrastructure, deduplicate immutable event_id and reconcile immutable history. No notification was sent as part of implementation.
7. Operational rollback: set SIMS_AWARDS_ENABLED=0; preserve data. Empty-schema migration reverse/reapply is tested on an isolated test database. Populated award/history/master reversal is refused. Do not remove guards, fake migrations, drop populated tables, overwrite evidence, or reverse shared masters to roll back application code.

## Verification and acceptance

Local verification passed: 652 full-backend tests and 121 subtests; final M30 run 25 tests and 35 subtests; full frontend run 106 tests across 22 suites; 12 shared PWA/transport tests. Django checks, migration drift, OpenAPI validation, lint, native schema inspection and final TypeScript/Vite/PWA build passed. The first full frontend run exposed an edited test-file encoding error; it was fixed and a clean full rerun passed. The existing M13 storage-key warning remains unrelated to M30.

See M30_VERIFICATION.json for final checks, M30_SCHEMA_INVENTORY.json for installed source/ORM fidelity, M30_QUERY_PLANS.json for eight actual ORM EXPLAIN plans, and M30_TRACEABILITY.json for prompt-to-file mapping. Local EXPLAIN is not a production volume benchmark; date sorting and leading-wildcard search should be measured on representative data before adding indexes. Canonical FK indexes are retained without speculative additions.

Production enablement, target-environment identity grants, storage/scanner credentials, notification adapter delivery, representative-volume benchmarking, and real device acceptance remain operational release steps.
