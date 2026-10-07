# M25 Research Proposals

## Delivery scope

The implementation follows the supplied pack in sequence. The original SQL and DOCX are unchanged. Runtime activation, role grants, production delivery adapters and deployment are separate operational steps. Earlier queued modules are not implicitly declared complete.

## Data ownership and decisions

`research_proposals.ResearchProposal` owns the canonical `research_proposal` table and all 16 source columns. Its protected one-to-one primary key is the existing `StaffActivity` identifier. The source PI and department fields are retained and must equal the parent employee and department. The API derives them from a scoped, active PI's dated employee assignment; it never accepts organization ownership from the client. `context_date` selects the historical assignment and becomes the parent start date; proposal_submission_date remains the independent nullable source field. Context cannot be reassigned through ordinary editing.

New shared masters `FundingType`, `FundingAgency` and `ResearchStatus` belong to `staff_profile`. Funding agencies reuse ExternalOrganization. Funding type is derived from the selected agency if absent and must match it if supplied. Agency, underlying organization and funding type must be active. External funding requires an agency before submission; drafts may leave funding metadata incomplete. Requested amount is optional nonnegative DECIMAL(16,2); currency is an uppercase three-letter CHAR(3), default INR. Monetary inputs remain decimal strings. Sanctioned/released/utilized funds are outside the proposal table.

No co-investigator extension is added: the pack marks it optional and supplies no requirement or approved external-person policy. Reference numbers remain nonunique; no global/funder/institution uniqueness policy was invented. Research domain stays free text, with scoped suggestions rather than a duplicate taxonomy.

`platform_research_proposal_status_history` is an explicit platform extension. It retains from/to status, actor, timestamp and remarks. The existing M15 audit remains authoritative for general mutation metadata; it did not retain all historical rationale. History is protected against ORM and native SQL update/delete. Shared `ActivityCommandReceipt` and `ActivityAttachment` are reused from M24; no second binary-storage or retry subsystem is introduced.

## Workflow and authorization

Permissions: `RESEARCH_PROPOSALS.ACTIVITY.READ`, CREATE, UPDATE, DELETE, VERIFY, APPROVE and EXPORT. Effective M15 grants support GLOBAL, INSTITUTION, CAMPUS, DEPARTMENT and SELF; deny overrides win. SELF resolves through AccountLink to the login principal. Django staff/superuser status alone does not bypass these business grants. Both IAM runtime/security flags must be active.

DRAFT/RETURNED -> SUBMITTED; SUBMITTED -> UNDER_REVIEW; SUBMITTED/UNDER_REVIEW -> VERIFIED; VERIFIED -> APPROVED. Reviewers may return submitted/under-review/verified proposals. Approvers may reject those states. Draft/returned/submitted records may be withdrawn. Only draft/returned records are editable; archive is a soft delete limited to draft/returned/rejected/withdrawn records. ResearchStatus and parent approval codes are synchronized atomically. Statuses are resolved by active stable codes; absent/inactive configuration is rejected.

An independent actor with VERIFY or APPROVE is required for review decisions: neither the creator nor the linked PI may self-review. Review comments are written only by workflow roles through the dedicated transition endpoint, never through the form/update payload. Scoped proposal readers may read review feedback and the timeline. Return/reject/verify/approve require remarks. Current statuses and timeline changes commit together with audit; failures roll back all affected rows.

Create and status commands require an actor-scoped Idempotency-Key. Concurrent retries use the same receipt/parent; different payloads under an existing key return 409. Retries recheck current permissions. Updates, transitions, uploads and archive require the current version; content plus latest audit identifier prevents stale or rapid change/revert edits from silently overwriting data.

## API

Base `/api/v1/research-proposals/`.

| Method/path | Purpose |
| --- | --- |
| GET/POST `activities/` | Scoped list / create draft |
| GET/PATCH/DELETE `activities/{id}/` | Detail / eligible edit / soft archive |
| POST `activities/{id}/workflow/` | Controlled action with remarks, version, Idempotency-Key |
| GET `activities/{id}/timeline/` | Chronological, paginated status history |
| POST `activities/{id}/evidence/` | Validated multipart evidence; optional retained replacement |
| GET `activities/{id}/evidence/{attachment_id}/download/` | Reauthorized private managed-file download |
| GET `activities/summary/` | Scoped counts and requested totals separated by currency and report dimension |
| GET `activities/export/` | Same READ ? EXPORT scope; formula-safe CSV, maximum 10,000 rows |
| GET `lookups/` | Effective creation/report capabilities and evidence categories |
| GET `lookups/{assignments,funding_agencies,funding_types,statuses,years,domains}/` | Lightweight searched/paginated choices and scoped domain suggestions |

PI and department selection is combined in the assignment selector to prevent inconsistent combinations. List filters include search, PI/employee, institution, campus, department, academic_year, funding_agency, funding_type, status, domain, submission date_from/date_to, currency, amount_min/amount_max and mine=1. Ordering is a whitelist, pagination defaults to 25 and caps at 100. Identifiers are string-safe in responses; monetary values use Decimal. All proposal API responses are private/no-store.

Synthetic creation example (replace identifiers with real authorized choices):

```json
{"context":{"employee_assignment_id":"42","context_date":"2026-09-25","academic_year_id":null},"activity":{"proposal_title":"Synthetic research proposal","proposal_submission_date":"2026-10-01","funding_agency_id":"7","requested_amount":"125000.50","currency_code":"INR"}}
```

POST with a new random Idempotency-Key; keep the same body/key for a network retry. PATCH supplies activity fields and version. Workflow supplies action (`submit`, `review`, `return`, `verify`, `approve`, `reject`, `withdraw`), remarks and version, with a new key for each distinct action. Unknown/protected input fields are rejected. Ordinary edits cannot supply PI, department, status, reviewer comments or audit actors.

## Documents, notifications and PWA

Evidence uses the M13 sharing boundary, random private storage keys, content validation, scanner, size/name checks, confidentiality checks, integrity verification and rollback cleanup. Supported shared types are PDF/PNG/JPEG. Proposal evidence is RESTRICTED and additionally requires M13 institution membership and shared-file/restricted-file permissions. Categories cover proposal, budget, forwarding letter, ethics approval, acknowledgement, review communication, revision and decision letter. Replacements preserve old links/files and cannot cross proposals. The larger `evidence_document` catalogue is not duplicated here.

Notification integration is an optional after-commit adapter (`SIMS_RESEARCH_PROPOSALS_EVENT_HANDLER`, dotted Python callable). The adapter receives only event_id, proposal_id, status and actor_id, resolves institution-configured recipients, and queues through approved shared delivery infrastructure. It must deduplicate event_id. Delivery errors do not roll back committed proposals; immutable history supports reconciliation. No adapter, recipients, credentials or external transport are configured by this implementation, and no real messages were sent. No delivery guarantee is claimed without the institution's queue/retry adapter.

The PWA route is `#/research-proposals`. It provides responsive cards/table, a mobile filter drawer, server-side filtering, form sections, remote choices, details, status timeline, workflow confirmations, documents and reports. Faculty linked to an employee default to their own records. Drafts stay in page memory; there is no private browser-storage draft or offline write queue. Offline writes/downloads are disabled. The existing service worker keeps APIs NetworkOnly. Unsaved-navigation warnings and field-level validation errors preserve recoverable edits.

Research-office Django admin is scoped read-only; it cannot bypass the service workflow. All business mutations use the PWA/API. Canonical funding masters remain owned by staff-profile administration; seeds do not invent funders.

## Deployment and rollback

Migrations install frozen native DDL for three masters and the proposal table, plus the explicit history extension and retention triggers. Existing native table collisions fail for adoption review. Source unsigned keys, ENUM-independent status FKs, DECIMAL(16,2), CHAR(3), TEXT, checks, FK names and utf8mb4 are preserved. ORM relations use PROTECT. Refer to M25_SCHEMA_INVENTORY.json for source/installed mapping.

1. Back up the target database and private document metadata/files using the deployment's existing procedure.
2. Deploy compatible backend code and run `backend/.venv/Scripts/python.exe backend/manage.py migrate --noinput`.
3. Run `backend/.venv/Scripts/python.exe backend/manage.py seed_research_proposals` after the M15 action catalogue exists. The seed uses stable codes, preserves labels, rejects incompatible existing configuration and grants no users access.
4. Install approved funding master rows and explicit scoped role grants. Configure M13 institutions, private storage and scanner. Configure a notification adapter only when its recipient/retry policy is approved.
5. Build the frontend with `npm run build` from frontend; deploy backend/frontend/service-worker changes together.
6. Enable `SIMS_RESEARCH_PROPOSALS_ENABLED=1` with coordinated IAM flags and perform scoped draft/edit/submit/review/document/export smoke tests.

Default rate limit is 120 requests/minute per authenticated principal (`SIMS_RESEARCH_PROPOSALS_RATE`). Use the project's production shared cache/edge limits. The flag stays off in the current environment. No production migration, flag change, user grants or external notification delivery is implied by local implementation.

Rollback: disable the module flag first and retain data/files. Reverse migrations refuse populated proposal/history tables. Canonical master reversal also refuses populated tables. Do not bypass retention guards or foreign-key checks. A populated deployment requires an explicit preservation/data-migration plan rather than dropping tables.

## User guides

PI: select New proposal, choose your dated assignment and context date, add title and optional submission/funding metadata, then save. Attach proposal/budget evidence. Supply submission date and external funder when applicable, then Submit. Returned records can be corrected and resubmitted. To change PI/department/context, withdraw and create a corrected draft.

Reviewer: open a proposal in your granted scope, inspect metadata, evidence and timeline, then review/return/verify with remarks. Approvers may approve verified proposals or reject eligible proposals. The UI hides unavailable actions, and the server repeats every authorization/state check.

Administrator: run catalogue seeds, maintain shared masters and scoped role assignments, configure document providers and notification adapter, and review operational acceptance before activation. API schema examples contain only synthetic data.

## Acceptance

Final command outcomes, remaining defects and operational checks are recorded in M25_VERIFICATION.json. Local EXPLAIN evidence is in M25_QUERY_PLANS.json; no speculative indexes were added. Local empty/small data is not a production load benchmark. Real-browser viewport/keyboard acceptance, institution role sign-off, configured storage/scanner/notification delivery, representative-volume staging checks and production smoke tests remain deployment work.

Changed files: new research_proposals app, staff_profile models/native master migration helpers, settings/routes, shared integration helpers where documented, frontend feature/navigation/tests, M25 manuals and scripts. Input documents and consolidated SQL remain unchanged.


Verification fixes also made the existing suite independent of module order and wall-clock date: the shared action-catalogue fixture is available to all backend tests; the People seed test initializes its baseline before testing repeatability; the timetable integration test fixes its historical clock. M25 concurrent tests clean only the isolated test database with TRUNCATE, while production history triggers stay active during assertions. Shared subtype exclusivity is now checked centrally for M22/M24/M25, including future installed primary-key child models.
