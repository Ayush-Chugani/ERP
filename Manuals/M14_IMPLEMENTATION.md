# M14 Communication: implementation contract and schema decisions

Status: ownership option 1 and normalized programme/user target tables explicitly approved by the user; implemented and locally verified. The baseline and approved extension are implemented; activation and outbound delivery remain off.

## Source and repository findings

Source: `Manuals/Prompts/M14-Communication_Module_Prompt_Pack.docx`, prompts 0-13. The three baseline tables also appear in `Manuals/sims_v6_5_1_mariadb_full_schema.sql` at line 1515. Repository conventions use `apps.<domain>`, not the document's illustrative `sims.platform` path. Proposed app: `apps.communication`; API `/api/v1/communication/`; frontend `/#/communication`.

Installed Django is 5.2.17 and exposes CompositePrimaryKey, so announcement_attachment can retain its real two-column primary key without a surrogate ID. Existing native field primitives support unsigned keys, native ENUM, DATETIME and TIMESTAMP. Department -> Campus -> Institution provides authoritative ownership derivation. Programme belongs to Department. Existing AccountLink distinguishes student and employee identities; active institution Membership and ScopeGrant supply authorization. Core ReferenceAuditEvent is append-only through its ORM API and can record workflow provenance in the same transaction.

M13 owns FileObject, validation, private storage and download integrity. Its current access_file service resolves student-document and certificate owners. Communication must add an explicit owner-service sharing contract; raw file IDs or uploader IDs alone cannot establish permission to publish a file. A broad announcement must never turn a student's document into a public attachment.

## Approved schema decisions

1. Recommended ownership: add non-null announcement.institution_id in a separately named extension migration; department_id identifies the optional publishing department. Reject publisher/owner mismatches. Null department means institution-level publication, requiring elevated institutional authority; it does not mean global publication. Existing ambiguous rows must be quarantined/backfilled before enforcing the new owner column. Alternative: require department ownership operationally and disable rows with null departments, without changing baseline DDL.
2. Recommended audiences: add normalized announcement_programme_target and announcement_user_target relationships, each unique by announcement and target. Targets must belong to the owner's institution. Alternative: reject PROGRAMME/CUSTOM on create, edit, submit, approve and recipient resolution until mappings are implemented. No target IDs hidden in description, JSON or audit payloads.

The user approved recommendation 1 in both questions. The alternative designs were not selected. See the approved ADR below.

DEPARTMENT requires a separate semantic decision within the selected model: proposed meaning is recipients affiliated with the publishing department, explicitly documented as a derived audience rule, with no ability to choose a different target department. If independently targeted departments are needed, add a normalized department-target relationship rather than giving department_id two independent meanings.

## Proposed domain defaults

- Authenticated recipients only; active user, active institution membership and enabled module required. ALL means active members of the owning institution. STUDENTS/STAFF additionally require active linked student/employee identities in that institution. Inactive, suspended or unlinked identities do not qualify by role labels alone.
- PROGRAMME, if approved, resolves active student programme enrolments; staff membership in a programme is not inferred. CUSTOM resolves explicit user targets and rechecks current institution membership. Multi-role qualification is a union within the same institution, never across institutions.
- Plain text description, rendered as text; no HTML interpretation.
- UTC at the application/database boundary. Visibility uses APPROVED and publish_from <= now and (publish_to is null or now < publish_to). Equality is rejected by service validation; no implicit schema CHECK addition without approval.
- DRAFT -> PENDING; PENDING -> APPROVED or REJECTED; REJECTED -> DRAFT; draft/rejected/approved records may be archived with authority. ARCHIVED is terminal. Approved content and attachment links are immutable; changes require a new draft. No scheduler is needed for feed correctness.
- Separate author and approver; reject approval by creator or submitting actor. Missing legacy provenance denies approval until reconciled. Reasons required for rejection/archive. Optimistic change checks plus row locks prevent stale edits and competing transitions.
- Central audit records event, actor, timestamp, old/new state, changed field names, protected reason and request correlation. Avoid announcement bodies, private target lists and storage credentials in routine logs. Core audit is application append-only, not a guarantee against privileged database tampering.
- Stable attachment order by display_order null-last then file ID; duplicate order values allowed with this deterministic tie-break. At most 10 attachments initially, each subject to M13 limits and validation. Detachment removes only relationships; no shared file deletion.
- Archive instead of hard-delete. No physical retention purge without a retention policy.
- No email/SMS/push delivery in this increment. No messages will be sent by the agent. Delivery integrations require an existing approved outbox contract and separate operational configuration.
- Sensitive feeds, drafts and downloads remain network-only; no offline mutation queue or browser persistence.

## Baseline column traceability

| Table / columns | Django representation | Enforcement |
| --- | --- | --- |
| announcement_type.announcement_type_id | Unsigned 16-bit auto primary key | Native DB type / PK |
| type_code VARCHAR(30), type_name VARCHAR(100) | CharField with exact lengths and unique flags | DB uniqueness; normalized/validated service inputs |
| is_active BOOLEAN DEFAULT TRUE | BooleanField with DB default | DB shape; inactive types denied for new submissions/approvals |
| announcement.announcement_id | Unsigned 64-bit auto primary key | Native DB type / PK |
| announcement_type_id | Protected FK to classification | DB FK; service active-type check |
| department_id nullable unsigned SMALLINT | Protected nullable FK to Department | DB FK; ownership and author scope policy |
| title VARCHAR(250), description TEXT | CharField / canonical TextField | Required nonblank service input; safe text rendering |
| publish_from DATETIME, publish_to nullable DATETIME | Canonical DateTimeField | UTC conversion; strict interval validation; selectors enforce exact boundaries |
| approval_status | Native ENUM DRAFT/PENDING/APPROVED/REJECTED/ARCHIVED, DB default DRAFT | DB enum; transactional state machine |
| audience_type | Native ENUM ALL/STUDENTS/STAFF/PROGRAMME/DEPARTMENT/CUSTOM, DB default ALL | DB enum; representability and recipient policies |
| created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP | Native timestamp with DB default | DB timestamp; not client editable |
| announcement_attachment.announcement_id | Protected unsigned BIGINT FK | Composite PK and DB FK |
| file_object_id | Protected unsigned BIGINT FK to M13 | Composite PK, DB FK and independent file policy |
| display_order nullable unsigned SMALLINT | Nullable positive-small integer field preserving zero compatibility | Native range; deterministic selector ordering |

Both association FKs preserve baseline restrictive deletion; lifecycle services explicitly detach relationships when allowed. No FK cascade may remove FileObject. Engine InnoDB, charset utf8mb4, collation utf8mb4_unicode_ci and all baseline constraint names must be verified against MySQL. Add no performance indexes before measuring representative feed/management EXPLAIN results.

## Package and dependency contract

`apps/communication/{models,fields,permissions,services,selectors,admin,apps}.py`, `api/`, `migrations/`, `tests/`, `management/commands/`, and a frontend communication feature. Public selectors accept authenticated principal and evaluation time; management services accept trusted actor and validated command inputs. Views remain thin. Other modules use public selectors/services rather than private models.

Dependencies point from Communication to Organization, People, Admission (if programme recipients enabled), Accounts/Tenancy, Core audit and Documents. No reverse domain dependency from Documents to Communication: Documents supplies an explicit share authorization API accepting a trusted owner-context contract, not arbitrary client-supplied scope. Module activation remains off until tested and intentionally configured.

Capabilities distinguish type maintenance, draft creation/edit, submission, review/approval/rejection, archive, attachment management and audit access. Recipient feed qualification is separate from management permissions. Scope filtering happens before object lookup; nonexistent and unauthorized objects share the same outward response. Null scope and incomplete target data fail closed.

## Verification plan and remaining sequence

Prompt 2: scaffold after ownership/audience decisions. Prompt 3: frozen baseline plus explicitly approved extension migrations, real MySQL schema checks and reversible/forward-fix plan. Prompts 4-9: lifecycle, audiences, file-sharing contract, permissions, API, selectors/admin/audit. Prompt 10: accessible feed and management UI. Prompt 11: full tests. Prompt 12: seed/import/reconciliation/recovery runbook. Prompt 13: evidence-based final review.

Required tests: every column/key/native type; publication boundary equality; inactive types/memberships; every enabled recipient mode and multi-role account; forged target IDs/cross-institution records; four-eyes workflow and MySQL races; missing audit provenance; stale writes; attachment link uniqueness, ordering, sharing authority, confidentiality, rollback and shared-file preservation; safe text rendering; bounded pagination/query counts; network-only frontend behavior. Use existing pytest-django isolated MySQL and frontend test commands.

Verification performed during the initial preparatory step: source DOCX read; canonical SQL locations checked; repository dependency/identity/audit/file APIs inspected; installed Django version and composite-key support checked. No application changes were made during that preparatory step; subsequent implementation evidence is below.

## Approved ADR 2026-09-23

User selected institution ownership and separate programme/user target tables. Migration 0001 preserves baseline; 0002 adds institution ownership and targets. Empty installations migrate directly. Populated legacy announcement tables stop before extension: ownership and audience must be reconciled in a reviewed backfill, never guessed from ambiguous rows. The source SQL and DOCX remain unchanged.


## Implemented delivery: prompts 2-12

| Prompt | Implementation / evidence |
| --- | --- |
| 2 | `apps.communication`, core registry, disabled settings, versioned API and frontend feature. Existing custom User and tenancy grants reused. |
| 3 | `0001_baseline` freezes/verifies exact baseline DDL; `0002_institution_and_audience_targets` contains the approved ownership and normalized targets. Django native composite keys retain attachment/programme/user relationship identities. |
| 4 | Durable service transactions, shared governance lock and announcement row locks; central-audit revision tokens reject stale writes. Explicit workflow, four-eyes approval, rejected revision and terminal archival. |
| 5 | All six audiences implemented. Programme uses ACTIVE enrolments; staff department affiliation uses dated EmployeeAssignment rows. Current membership/status is re-evaluated on each feed read. |
| 6 | M13 public `sharing` interface owns upload validation, malware scan, private bytes, hash checks and file-level permissions. Only explicitly shared uploads can be linked. Association changes are draft/rejected only; detachment preserves files. |
| 7 | Scope-filtered management and separate recipient queries, institutional publishing authority, inactive membership denial, unsupported record-limit denial and protected audit. |
| 8 | Strict JSON/multipart commands, bounded lists, deterministic sorting, status/type/department/audience/search/publication-date filters, protected streaming download and OpenAPI. |
| 9 | Public selectors/services, read-only admin, central append-only audit, sanitized event/error logs and scoped operational count report. No delivery worker/outbox is invented. |
| 10 | React/MUI feed, details, management filters, editor, all audience choices, type maintenance, workflow confirmations, attachments and audit viewer. Descriptions render as text. Sensitive API traffic remains network-only in the existing service worker. |
| 11 | Real MySQL schema, recipient, authorization, time boundary, stale-write, workflow-race, rollback, attachment, API, query-count and React tests. Existing MySQL CI discovers the new backend suite; frontend suite includes M14. |
| 12 | Explicit role/type seed commands, scoped reconciliation command, migration/legacy/recovery runbook below. No operational data or membership assignments seeded. |

### Public contracts and permission boundaries

`selectors.feed(actor, at=None)` and `can_view(actor, pk, at=None)` apply current membership and recipient relationships plus the requested evaluation time. They do not reconstruct historical authorization. `type_by_code` resolves active classification. `permissions.management(actor, capability)` is the management queryset contract. Call `services.write`, `workflow`, `write_type`, `attachment` and `upload_attachment` for mutations.

An institution-wide grant and `publish_institution` capability are required to publish beyond DEPARTMENT recipients, even when a publishing department is set. Department-scoped authors can publish DEPARTMENT announcements only. Global type maintenance additionally requires platform administration. Superusers may manage enabled institutions but do not automatically become recipient-feed members; four-eyes approval still applies.

Post-approval editing is rejected. Create a new draft and archive the old notice where needed. There is no implied revision linkage table. A classification made inactive blocks new submissions/approvals; already approved notices remain visible until their window closes or they are archived.

M13 sharing stores explicit file-sharing provenance with institution in protected central audit. Existing student documents and certificates cannot be attached by guessing a file ID. Shared uploads currently require an institution-wide M13 scope plus `documents_exit.share_file`. CONFIDENTIAL adds `access_confidential_shared_file`; RESTRICTED and HIGHLY_RESTRICTED retain their existing M13 permissions. PUBLIC still requires announcement visibility and active institutional access. Approvers must be able to inspect all attachment confidentiality levels before approving. Upload and association commit atomically, with M13 compensating storage cleanup on failure; crash-orphan reconciliation remains necessary.

### API reference

All paths below are relative to `/api/v1/communication/`:

- `GET feed/`, `GET feed/{id}/`: approved, currently visible content; no management target lists or audit tokens.
- `GET manage/`, `GET manage/{id}/`: scoped management view with status, publication state, audience, targets and revision token.
- `POST drafts/create/`, `POST drafts/{id}/edit/`: complete editor payload with approved owner, type, text, UTC-aware publication window and matching target list. Edits require `expected_version`.
- `POST drafts/{id}/{submit|approve|reject|revise|archive}/`: `expected_version` and reason; workflow authority checked again in the service.
- `POST drafts/{id}/upload/`: multipart `upload`, `expected_version`, confidentiality `level`, optional `display_order`.
- `POST drafts/{id}/{attach|detach|reorder}/`: `file_id`, `expected_version`, optional `display_order`.
- `GET {feed|manage}/{id}/attachments/{file_id}/download/`: membership/announcement/file checks at request time; attachment stream with no-store, nosniff and sandbox headers. No signed or durable storage URL is exposed.
- `GET audit/{id}/`: separately scoped audit capability, bounded pagination.
- `GET lookups/{types|type-admin|institutions|departments|programmes|users}/`: scoped form options; organisational/recipient lookups take `institution`.
- `POST types/create/`, `POST types/{id}/edit/`: platform-authorized classification commands.

Publication states in management responses are derived: draft, pending, rejected, scheduled, published, expired or archived. They do not add database ENUM values. The window is start-inclusive/end-exclusive. API accepts ISO timestamps with timezone; the UI requests an explicit timezone and displays local time. Description limit is 50,000 characters and 65,535 UTF-8 bytes to match native TEXT capacity.

Form lookups intentionally stop with a visible error above 100 choices; the API remains paginated. Large recipient populations need a searched picker enhancement before broad UI rollout. List serialization prefetches target relations and obtains audit revision tokens in one subquery rather than one lookup per row. Tests measure query counts; real populated load remains a release check.

### Migration and rollback runbook

1. Back up database and M13 private object storage together. Verify Department, Programme, custom User and FileObject prerequisites. Preserve the source DOCX and consolidated SQL baseline.
2. Inspect migration plan. For a fresh installation, run `python backend/manage.py migrate`. Baseline adoption verifies engine, collation, exact native columns/defaults, unique/composite keys, FK actions and checks before creating missing tables.
3. The extension stops on a populated legacy announcement table before assigning ownership. Do not delete legacy records to bypass this gate. Reconcile source ownership, audience, approval provenance, timezone and attachment-sharing authority in a separately reviewed backfill. Quarantine unresolved records outside live feeds. Import as drafts and obtain current approval; never send historical notifications.
4. Legacy reconciliation must report source total versus accepted/quarantined counts, status/audience distribution, unique announcement/file associations, unresolved programmes/users, invalid intervals, missing sharing provenance and checksum mismatches. Backfills should use stable source keys, bounded batches and checkpoints. No automatic legacy importer is supplied because no source dataset or mapping was provided.
5. Apply the additive M13 `0002_shared_file_permissions` migration. It changes permissions metadata, not file tables or existing authorization assignments.
6. Generate DDL/EXPLAIN evidence using `python backend/manage.py shell -c "exec(open('scripts/m14_schema_report.py').read())"`. The generated report covers all five M14 tables and representative local queries. No optional indexes were added without populated evidence.
7. Repeat `scripts/verify-module14.ps1`. Test database recreation is isolated and guarded. The existing MySQL W003 warning refers to M13's canonical storage-key length; it is not an M14 schema defect.
8. Keep `SIMS_COMMUNICATION_ENABLED=0` until pilot scope and acceptance are approved. Enable selected institutions using `SIMS_COMMUNICATION_INSTITUTIONS`. Attachments additionally need M13 enabled for those institutions, private storage and a real malware provider. No certificate renderer or exit-clearance provider is needed for announcement text or attachment sharing.

Rollback is feature disable plus a reviewed forward fix or coordinated backup restore. `0002` explicitly rejects reverse migration so it cannot drop institutional ownership or recipient mappings. This also blocks graph reversal of upstream M13 while M14 is installed. M13's own retain/adopt callbacks remain verified independently. Do not fake migration history or run reverse SQL to evade this protection.

### Operations

- `python backend/manage.py seed_communication_roles` reconciles four capability groups without users, memberships or scope grants. Institutional publishing, type/platform administration and file sharing must be assigned deliberately. A group alone never supplies row scope.
- `python backend/manage.py seed_announcement_type --actor ID --code CODE --name NAME` idempotently reconciles an explicitly chosen classification using the service. No unapproved hard-coded type IDs or default master records.
- `python backend/manage.py communication_check --actor ID` reports only authorized counts, status/audience totals, invalid intervals, scheduled/expired rows, attachment totals and missing target mappings. No status mutation, delivery or purge.
- M13 storage reconciliation covers bytes/orphans. Retention and legal-hold decisions precede any physical purge. Detaching shared evidence does not remove its bytes.
- Collect sanitized `m14_<event>` and `m14_request_failed status=<code>` counters plus command reports in the deployment's existing logging/monitoring system. There is no claim that an external dashboard or alert sink has been deployed.

No email/SMS/push is sent or queued. Future delivery must use a transactional shared outbox with an announcement/event idempotency key and recheck audience/time at send time. Feed visibility remains independent of delivery success.

## Final review and verification evidence

Results and remaining release conditions are recorded after the final automated run. Interactive browser discovery returned ?No browser is available?; component tests are not a substitute for browser acceptance. No production-readiness claim is made before verification and the rollout gates are satisfied.


### Final local results (2026-09-23)

- 109 backend tests passed across Communication, Documents/Exit, People, Admission and Core. This includes all 38 M14 tests and the M13 sharing regression coverage. Two focused API tests passed after audit correlation was added; two focused schema/rollback tests passed after collation alignment.
- 48 frontend tests passed, including the three M14 checks for safe text rendering, recipient-only controls, offline behavior and confirmation. TypeScript/Vite/PWA build passed after final UI changes.
- OpenAPI validation passed with fail-on-warning enabled. Ruff checks/formatting passed. Django migration drift check reported no changes.
- Local migrations 0001, 0002 and 0003 applied, along with M13's permissions-only migration. 0003 aligns the two numeric target tables' default collation with utf8mb4_unicode_ci; it changes no target IDs or recipient policy.
- Local schema and EXPLAIN evidence is in `Manuals/M14_SCHEMA_AND_QUERY_PLANS.md`. No announcements, targets, attachments or announcement types were created in the application database. No roles/users were assigned. M14 remains disabled with an empty institution allowlist; M13 remains disabled; M12 remains enabled for institution 1.
- Interactive browser acceptance was unavailable, not passed. Existing checks report M13's generic MySQL W003 unique-storage-key warning; the broader test run also reports an existing Django 6.0 URLField-default deprecation in People admin.

### Prompt 13 release recommendation

**Conditional go for a controlled pilot after the following gates; no production go yet.** The reviewed/tested paths show no unresolved critical or high-severity authorization, workflow, XSS or confidentiality bypass. This is evidence from local tests and code/schema review, not a claim of independent security certification or production load testing.

| Severity / scope | Remaining condition | Measurable exit criterion |
| --- | --- | --- |
| Release gate | No interactive browser acceptance | Complete student/staff/author/approver journeys in a connected browser, including keyboard navigation, denied attachment access and offline handling. |
| Release gate | No pilot assignments or active M14 configuration | Select institution(s), assign membership/scope and distinct author/approver accounts, verify each least-privilege role before enabling. |
| Release gate for attachments | Real scanner and production private storage not configured | Configure an approved scanner/storage adapter, verify clean/rejected uploads and private download revocation, and retain M13 confidentiality checks. Text-only pilot does not require attachment activation. |
| Release gate for populated deployments | Legacy ownership, audit provenance and file-sharing authority not reconciled | Supply source mappings, review restartable backfill, reconcile accepted/quarantined totals and test recovery before overriding the legacy gate. |
| Medium operational | Local query plans use empty tables; governance lock serializes mutations | Load-test representative recipient/management workloads and concurrent writes; approve any needed indexes from measured plans. |
| Medium operational | Form option lists capped at 100; targets capped at 500 | Keep pilot within limits or implement searched recipient/programme pickers before larger rollout. API pagination remains available. |
| Medium operational | Backup restore, retention, legal hold, monitoring and multi-worker throttling unverified | Demonstrate coordinated database/object restore in staging and configure deployment retention, alerts and shared throttle cache. |
| Out of scope | Email/SMS/push and historical imports | Remain disabled; separately implement approved outbox/source integration with idempotency and audience rechecks when requested. |

Files changed: new `backend/apps/communication` app; M13 `sharing.py`, permission metadata and retention callback test; core module registry, config settings/URLs and `.env.example`; React communication feature, app navigation, frontend tests/config; OpenAPI artifact; existing MySQL CI lint coverage; verification/schema-report scripts; this guide and schema report. Original prompt DOCX and consolidated SQL were preserved.
