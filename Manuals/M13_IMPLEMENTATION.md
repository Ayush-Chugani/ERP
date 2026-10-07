# M13 implementation contract

## Prompts 1-2: repository impact and boundaries

A cohesive documents_exit app owns exactly file_object, student_document, certificate_type, certificate_request and student_exit. It reuses People Student/AccountLink/Employee, Common Reference DocumentType, Admission StudentProgrammeEnrolment, existing custom User/Membership/ScopeGrant and core ReferenceAuditEvent. No master, authentication, clearance or file-version table is duplicated. API namespace /api/v1/documents/, UI /documents. Interface -> services/selectors -> models/adapters; external writes go through admission_enrolment.services.finalize_exit_enrolment.

Files: models/fields map canonical SQL; permissions defines identity/scope; storage defines private backend and content validation; integrations provides approved renderer/scanner/clearance hooks; services owns transactions/cleanup/state machines; selectors presents redacted summaries; api defines strict typed commands and protected streams; admin is read-only; management commands handle explicit expiry/health; tests cover schema/security/storage/races; migrations freeze and verify canonical DDL.

Confirmed conflicts and handling before model generation:

- file_object.uploaded_by_user_id is an unsigned numeric column without a FK. Store authenticated actor ID; do not invent a FK against the custom-user table.
- file_object.updated_at is a native TIMESTAMP with ON UPDATE CURRENT_TIMESTAMP. Preserve this in frozen DDL and a native field, not an invented auto_now timestamp.
- No approved PDF renderer or malware scanner exists. Add configurable provider contracts; fail closed when absent. Tests use isolated fake providers, not operational certificate templates or a pretend virus scanner.
- No exit no-dues/final-result clearance provider exists. Finalization calls a configurable clearance/result policy and fails closed until configured. Do not treat admission fee clearance as exit clearance.
- M6 has TRANSFERRED in its model vocabulary but omits it from the owning transition service. Add a dedicated owning-service integration for final exits, allowing TRANSFERRED from ACTIVE/ON_BREAK while retaining permission, version, history and date checks. Keep the generic M6 transition API unchanged so transfer finalization is not exposed there. No M6 schema changes. OTHER requires an explicit provider-selected terminal status.
- Issued certificates are immutable; no correction/reissue or public-verification endpoint without further policy/schema approval.
- File replacement retains the prior file object and audit linkage. There is no invented document-version table. Physical purge is deferred; soft deletion is only file_object.deleted_at.

Default policy decisions are explicit: private local storage outside public MEDIA, PDF/PNG/JPEG only initially, 10 MiB upload limit, required malware provider, RESTRICTED uploads, no duplicate active certificate request by default, student cancellation before approval only, no future exits, mandatory transfer destination and privileged termination confirmation/reason. Prefixes, upload limits/profiles, duplicate policy, approved renderer and exit rules are configurable. M13 remains globally disabled and institution allowlist empty after implementation.

Migration dependencies point to Common Reference, People and Admission owners; raw table DDL preserves names/types/defaults/nullability/unique/FKs/checks. Native schema field primitives are reused from the prior schema-first implementation without importing its domain services or permissions. Existing M12 pilot configuration remains separate.

## Sequential delivery record (prompts 3-25)

| Prompts | Delivered implementation |
| --- | --- |
| 3-4 | Exact five-table models, frozen native DDL, existing-table adoption checks and non-destructive reverse migration. |
| 5-6 | Private storage adapter, random exclusive keys, size/content/MIME validation, required malware scan, SHA-256 and rollback cleanup. |
| 7-9 | Scoped upload/replacement, verification transitions, authenticated attachment streaming and integrity checks. Browser inline preview is deliberately not exposed for untrusted uploads. |
| 10-14 | Certificate master, student request, review/approval/cancellation, provider-backed PDF issuance, idempotent retrieval. Issued artifacts are immutable; public verification and reissue remain unavailable pending an approved policy. |
| 15-17 | Finalized exit records with clearance hook, transfer/termination safeguards and atomic admission owner-service transition/history. |
| 18-21 | Custom-user permissions and row scope, strict command APIs, protected central audit, read-only admin. |
| 22 | MySQL schema, service, authorization, storage failure, expiry, API and concurrency tests. |
| 23 | Explicit expiry, storage reconciliation and stale workflow commands. No automatic physical purge or invented retention duration. |
| 24 | Automated document/certificate/exit journeys and React component checks. Interactive browser acceptance remains outstanding: no browser was available in this session. |
| 25 | Local readiness checks and release gates below. |

## API and UI

The UI route is `/#/documents`. Commands live under `/api/v1/documents/`:

- `documents/upload/`, `documents/{id}/replace/`, `documents/{id}/verify/`, `documents/{id}/delete-file/`.
- `types/create/`, `types/{id}/edit/`, `certificates/submit/`.
- `certificates/{id}/review/`, `approve/`, `reject/`, `cancel/`, `issue/`.
- `exits/finalize/`.
- Scoped lists/details for documents, certificates and exits; supporting type/student/enrolment lookups; owner-checked `download/` and separately authorized `audit/` subroutes.

Uploads use multipart form data. Other commands use JSON objects; unknown/protected fields and non-object payloads are rejected. State changes require expected status where applicable. Exit finalization requires explicit confirmation and reason. There is no generic status patch or raw storage-key endpoint. UI drafts remain in memory, require an online connection, and warn before leaving; confidential data is not added to offline queues.

Student identity comes from AccountLink and active membership. Staff authorization combines capability and existing institution/campus/department scope. Unsupported record limits fail closed. File confidentiality is an additional check after ownership/scope. Self-review, self-approval, self-issuance and self-exit are denied. Historical records remain readable according to scope after student inactivity. Downloads use attachment disposition, no-store, nosniff and sandbox headers. No public file URLs are returned.

## Provider contracts and activation gates

M13 is disabled by default. Operational activation requires all applicable providers, institution allowlisting, scoped role assignments and acceptance testing. Test providers must never be configured for operational use.

| Setting / environment name | Contract |
| --- | --- |
| `DOCUMENTS_MALWARE_SCANNER` / `SIMS_DOCUMENTS_MALWARE_SCANNER` | Dotted callable accepting `data` bytes; must return exactly `True` after an approved scan. Missing/unavailable providers deny the operation. |
| `DOCUMENTS_CERTIFICATE_RENDERER` / `SIMS_DOCUMENTS_CERTIFICATE_RENDERER` | Dotted callable accepting `request` and `certificate_number`, returning approved PDF bytes. Institution must supply template, signatory and numbering requirements. Generated files pass the upload security checks. |
| `DOCUMENTS_EXIT_CLEARANCE` / `SIMS_DOCUMENTS_EXIT_CLEARANCE` | Dotted callable accepting `actor`, `enrolment`, `exit_type`, `exit_date`; returns `{'allowed': True}` only after required clearance/result checks. OTHER also requires an explicit terminal `enrolment_status`. |
| `DOCUMENTS_STORAGE_FACTORY` / `SIMS_DOCUMENTS_STORAGE_FACTORY` | Private storage adapter; default local private directory. Production adapters must preserve exclusive writes, protected reads and cleanup semantics. |

Use `SIMS_DOCUMENTS_EXIT_ENABLED` and `SIMS_DOCUMENTS_EXIT_INSTITUTIONS` only after these gates. See `.env.example` for limits, allowlists and policy settings. The role seeder creates groups only; it does not assign memberships, institutional scope or users. Termination permission needs explicit assignment. Global certificate-master maintenance also requires platform authority.

Local storage defaults to `backend/private_documents`, outside public MEDIA. Configure operating-system ACLs (especially on Windows), encrypted storage/backups and a shared production throttle cache. PDF/PNG/JPEG are the only initial supported formats; adding Office/ZIP extensions requires an approved content parser, not merely an allowlist change. Parser/provider errors are sanitized. Existing nullable-checksum records get size validation; new uploads always receive SHA-256 checks.

## Migration, recovery and operations

The migration creates missing canonical tables and adopts matching existing tables only after verifying column types, nullability, defaults, enum values, keys, full-length indexes, foreign keys/actions and checks. Any mismatch stops adoption. No fabricated rows or certificate types are seeded. Reverse migration retains tables and data; it is not a data rollback.

Before applying to a populated environment, back up the database and private objects together, inspect the canonical DDL, and investigate duplicate document identity triples, certificate numbers, enrolment exit rows and storage keys. Do not resolve duplicates by deleting evidence. Example preflight queries:

```sql
SELECT student_id, document_type_id, document_number, COUNT(*)
FROM student_document WHERE document_number IS NOT NULL
GROUP BY student_id, document_type_id, document_number HAVING COUNT(*) > 1;
SELECT certificate_number, COUNT(*) FROM certificate_request
WHERE certificate_number IS NOT NULL GROUP BY certificate_number HAVING COUNT(*) > 1;
SELECT storage_key, COUNT(*) FROM file_object
GROUP BY storage_key HAVING COUNT(*) > 1;
```

Run `python backend/manage.py migrate`, then the schema report script using the project environment. `Manuals/M13_SCHEMA_AND_QUERY_PLANS.md` records local DDL and EXPLAIN output; empty-table plans are not production load evidence. Django emits W003 for the canonical unique VARCHAR(500) storage key. Local InnoDB supports and verifies the full index; the field was not shortened to suppress the generic warning. Verify target engine/index limits before migration elsewhere.

Commands (use the project's Python environment):

- `documents_expire --actor ID` previews; add `--apply` to expire eligible documents. Supports bounded batches and reruns without deleting bytes.
- `documents_storage_check --actor ID --scan-orphans` reports bounded reconciliation counts without exposing keys or removing objects. A truncated sample does not prove absence of orphans.
- `documents_workflow_check --actor ID --older-than-days N` reports aging certificate workflows; N is an operator choice, not an institutional SLA.
- `seed_document_roles` creates permission groups without assigning people or generating master data.

Service commands use a durable transaction boundary, database locks and compensating storage cleanup. Do not wrap them in another application transaction. A process crash between object storage and commit can still leave an orphan; reconciliation and an approved retention process are required. Replaced objects and soft-deleted objects remain retained. Restore database and object storage from a coordinated backup, verify checksums and relationships, and test restoration in staging before release. No physical purge command is supplied.

## Verification and readiness

The combined verification run passed 236 backend tests across M6-M13/core and 45 frontend tests. OpenAPI validation and the TypeScript/Vite build passed. A subsequent focused M13/M6 run passed 41 tests after integration refinements; the native timestamp regression also passed. Final focused suite results are recorded below. Run `scripts/verify-module13.ps1` to repeat the broader checks against the isolated test database.

Local migration was applied successfully. Implementation is available for review, but operational release still requires: approved scanner/template/clearance providers; institutional confidentiality/retention and numbering decisions; scoped pilot users; interactive browser acceptance; populated load checks; production storage and logging review; and a demonstrated staging restore. No real document, certificate or exit was created during implementation, and M13 activation was not performed.

Final local verification: all 35 M13 tests passed, including multipart API upload, malformed JSON rejection, native timestamp behavior and concurrent commands. Ruff checks/formatting passed and migration drift check reported no changes. Runtime inspection confirmed zero pending migrations, zero rows in all five M13 tables, M13 disabled with an empty institution allowlist, and all three required provider settings unset. M12 remained enabled for institution 1.
