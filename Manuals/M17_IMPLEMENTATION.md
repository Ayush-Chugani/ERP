# M17 Student Fees implementation record

Status: Prompt 01 source discovery completed. Prompts 02-25 are pending completion of M15 and M16, in the user's requested sequence. No fees app, financial records, migrations, gateway configuration or outbound notifications were created.

## Source and schema inventory

Source: `Manuals/Prompts/M17-Student_Fees_GPT_Prompt_Pack.docx`. Extracted text is in `M17_prompt_pack_extracted.txt`; `M17_SCHEMA_INVENTORY.json` records all 31 table definitions and their external references. All 31 table definitions match the consolidated SQL after whitespace/comment normalization. This comparison does not assert equality of seeds, views or separate index statements. Original DOCX and SQL are unchanged.

## Prompt 01 dependency map

| SQL table | Existing Django model / app | Primary-key mapping |
| --- | --- | --- |
| academic_term | `academic_calendar.AcademicTerm` | `academic_term_id` / UnsignedAutoField |
| academic_year | `academic_calendar.AcademicYear` | `academic_year_id` / UnsignedAutoField |
| admission_application | `admission_enrolment.AdmissionApplication` | `application_id` / UnsignedBigAutoField |
| admission_category | `common_reference.AdmissionCategory` | `admission_category_id` / UnsignedAutoField |
| campus | `organization.Campus` | `campus_id` / UnsignedAutoField |
| certificate_request | `documents_exit.CertificateRequest` | `certificate_request_id` / UnsignedBigAutoField |
| institution | `organization.Institution` | `institution_id` / UnsignedAutoField |
| programme | `organization.Programme` | `programme_id` / UnsignedAutoField |
| programme_specialization | `organization.ProgrammeSpecialization` | `specialization_id` / UnsignedAutoField |
| semester | `academic_calendar.Semester` | `semester_id` / UnsignedAutoField |
| student | `people_master.Student` | `student_id` / UnsignedBigAutoField |
| student_programme_enrolment | `admission_enrolment.StudentProgrammeEnrolment` | `enrolment_id` / UnsignedBigAutoField |
| student_term_registration | `term_registration.StudentTermRegistration` | `term_registration_id` / UnsignedBigAutoField |
| user_account | `accounts.User` | `user_id` / BigAutoField |

All 14 external FK table names resolve to registered Django models. The existing user key is signed BigAutoField while the source contract expects unsigned user references: resolve this through the M15 compatibility strategy before fee migrations. Other keys use existing unsigned field primitives; compare actual database column widths and composite referenced indexes before migration. Database presence/adoption and FK compatibility remain unverified because the local database refused connection on 2026-09-25.

## Existing conventions and integration findings

The backend uses `apps.*`, custom `accounts.User`, services/selectors, thin DRF APIs, bounded pagination, a shared error handler and drf-spectacular. Register fees using these conventions and keep financial business rules out of serializers and model save hooks. Use the existing frontend API/authentication conventions and server-authoritative commands; payment/refund actions must not be replayed automatically by an offline queue.

M6 `FeeClearance` is an append-only manual attestation tied to application version, with `record_clearance` as its owner service. It is not a payment ledger. Keep existing admission behavior until an explicit fee-clearance adapter is integrated and tested. M6 also provides examples of command receipts and a transactional outbox; these are patterns, not shared fee persistence tables.

No payment provider implementation was found in the inspected backend. Define a provider interface, deterministic fake for tests and disabled production adapter until configured. Browser redirects cannot mark payments successful. Verified callbacks must match amount, currency, merchant and internal transaction, with durable deduplication. No real payment, refund or notification is authorized by development testing.

M15 business roles, effective scope evaluator and central audit remain prerequisites; do not substitute Django Group permissions for the required financial RBAC. M13 owns certificate requests and private artifacts. M14 announcements do not supply a general notification delivery provider. ReferenceAuditEvent and module-specific audits exist; fees requires its own immutable activity log and an integration with M15's audit writer.

## Proposed package and public interfaces

Create `backend/apps/fees/` with `apps.py`, `models/`, `domain/`, `services/`, `selectors.py`, `permissions.py`, `api/`, `admin/`, `integrations/`, `tasks/`, `management/commands/`, `migrations/` and `tests/`. Use Decimal money helpers with explicit currency precision and rounding; never float conversions.

Public command boundaries: assess_student_fees, apply_benefit, schedule_installments, assess_penalty, request_service_fee, assert_action_allowed(student, action, context), initiate_payment, accept_verified_callback, allocate_payment, issue_receipt, approve_refund and execute_refund. Every command receives actor/context, validates institution and ownership, and uses an idempotency key where retried. Query boundaries: account_statement, outstanding_balance and fee_clearance. Other modules consume these contracts rather than updating fee balances directly.

Dependency direction: identity/organisation/calendar/People -> M6/M7 enrolment -> fees; M15 -> fees authorization/audit; M13 -> fee-linked certificate references. M16 completes first because the user requested that sequence, although the fee tables have no direct HR FK. Avoid reverse imports: certificate/admission consumers call configured adapters into fees. Publish committed domain events through an outbox.

## Migration sequence and risks

1. Finish M15 and M16; repeat live database and migration graph preflight. Verify signedness, collations, generated columns, all external FKs and pre-existing table ownership. Fail on incompatible existing tables instead of silently adopting them.
2. Add the app skeleton, then reference/ledger tables and fee structure/late-fee configuration. Create referenced tables before dependent tables even when prompt presentation order differs.
3. Add accounts, assessments/items/source links; benefits and installment tables; payment modes, transactions, admission bridge and allocations; receipts, adjustments/refunds, penalties, service requests, holds and audit. Preserve every named SQL constraint, including composite owner FKs and nullable generated uniqueness; represent unsupported Django constraints with explicit database/state operations.
4. Seed exact source reference/RBAC rows idempotently. Reconcile existing FINANCE_OFFICER without overwriting institutional edits. Verify whether M15 administrators receive new FEES permissions; do not assume initial M15 grants include future resources.
5. Add views/indexes and explicitly documented platform extensions for command deduplication, reference sequences and reliable outbox delivery. Test fresh and existing-schema migration paths on the supported MySQL/MariaDB server.

| Risk | Required control / verification |
| --- | --- |
| Cross-institution references | Resolve ownership through authoritative related records; enforce scope on queries, commands, exports and callbacks. |
| Concurrent allocation/refund/receipt issuance | Atomic transactions, consistent lock order, database uniqueness and real-database race tests. |
| Duplicate callbacks or scheduled penalties | Durable provider event/command identity; verify payload consistency and reject conflicting replays. |
| Incorrect totals | Decimal-only arithmetic, conservation properties and explicit currency checks. The source collection summary does not group by currency: never use it to silently combine different currencies. |
| Financial history alteration | Posted facts immutable; corrections through audited adjustments/reversals. Document which source rows may transition status without changing posted amounts. |
| Approval abuse | M15 permissions plus requester/approver separation and configurable thresholds; student access restricted to own authorized records. |
| Gateway or refund uncertainty | Explicit pending/reconciliation states; trusted provider verification, no browser-authoritative success and no blind external retries. |
| Audit leakage | Redact credentials, bank details and raw provider secrets; restrict exports and preserve failed-access audit where applicable. |
| External integration outage | Fail closed for required checks; transactional outbox with retry/dedup and independently configured delivery adapters. |

## Remaining prompt order

2. Fees app scaffold and domain boundaries
3. Master-data and ledger models
4. Fee structure versioning and approval
5. Seed data and database-driven permissions
6. Student financial accounts and assessment engine
7. Concessions, scholarships, sponsorships, and benefits
8. Installment scheduling and overdue processing
9. Penalties and late-fee assessment
10. Service-fee requests and cross-module integration
11. Financial holds and release rules
12. Payment transaction intake and gateway safety
13. Atomic payment allocation and balance updates
14. Receipt issuance, cancellation, and replacement
15. Adjustments and refund processing
16. DRF API design and OpenAPI contract
17. Custom-user RBAC and separation of duties
18. Finance UI and PWA workflows
19. Reports, statements, and reconciliation
20. Notifications and event-driven integration
21. Audit trail and financial observability
22. Comprehensive automated test suite
23. Data integrity, reconciliation, and repair commands
24. Performance, indexing, retention, and security hardening
25. Final integration review and production handover

Run and verify each implementation prompt before the next. Final validation must cover unit/API tests, real database constraints and concurrency, authorization denial paths, fresh/upgrade migrations, frontend build and workflows, reconciliation, backup/restore and rollout documentation. Do not mark these checks complete based on source discovery.

## Verification in this turn

`backend/.venv/Scripts/python.exe backend/manage.py check` passed with no issues. Registered-model introspection resolved all 14 external tables. All 31 CREATE TABLE definitions matched consolidated SQL after normalization. Live database introspection failed with connection refused; no database tests or migration checks are claimed. Application code and runtime settings were not changed.

## Pending upstream decisions

M15 still awaits the previously requested choices: staged feature-flag rollout; correcting SELF override scope to user ID; and explicit ancestor-scope adaptation with DENY precedence. Those decisions must be settled before completing M15, then M16, then M17 Prompt 02 onward.


Update 2026-09-25: all three M15 design decisions were approved. M15 staged code/schema/catalogue is now installed locally with activation disabled. The previous decision questions are resolved; remaining sequence work is implementation/integration and validation, not renewed approval. See M15_IMPLEMENTATION.md for current status.
