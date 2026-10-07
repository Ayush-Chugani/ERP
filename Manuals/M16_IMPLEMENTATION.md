# M16 Employee HR implementation record

Status: Prompts 1-5 implemented. Prompt 6 models and database constraints are implemented; secure create/update services and masked DTOs remain unfinished. Thirteen model tables and five migrations are installed locally. HR remains disabled; no operational cryptographic keys or HR user grants were created. Earlier preflight notes below are historical; see the current progress record at the end.

## Sequence and source

The user requested execution of `Manuals/Prompts/M16-Employee_HR_Structured_Prompt_Pack.docx` after previous modules. M12 is implemented. M13 and M14 are implemented but disabled. M15 remains at preflight pending rollout, SELF-denial and ancestor-scope decisions. M16 depends directly on that business RBAC and central activity audit, so application/schema implementation must follow M15 rather than inventing substitute authorization.

The prompt pack contains 19 sequential prompts and refers to the supplied SQL contract. M16 DDL is present in `Manuals/sims_v6_5_1_mariadb_full_schema.sql`, starting at line 2045. `Manuals/M16_SCHEMA_INVENTORY.json` captures all 17 CREATE TABLE definitions, source locations, references and 84 named constraints. The original SQL and DOCX remain unchanged. `Manuals/M16_prompt_pack_extracted.txt` preserves the extracted prompt text for traceability.

## Prompt 1: exact reuse/dependency map

| Required dependency | Existing owner and interface | Finding |
| --- | --- | --- |
| Employee identity | `apps.people_master.models.Employee`, `EmployeeAssignment`; `people_master.permissions` and `integrations.upstream` | Reuse employee primary key and institutional ownership. Staff department/campus affiliation comes from dated assignments, not a department column on Employee. |
| Custom login identity | `apps.accounts.models.User`, `AUTH_USER_MODEL=accounts.User`; existing JWT/CSRF/refresh services | Reuse current identity; await M15 security/account compatibility migrations. |
| Employee account link | `apps.people_master.models.AccountLink`; `people_master.identity` | Current identity consumer. Await M15's canonical-link compatibility strategy rather than duplicating links. |
| Country/state/document type | `apps.common_reference.models.Country`, `State`, `DocumentType` | Existing canonical tables; use FKs and validate state/country consistency. Idempotent HR document-type seeds must preserve unrelated data. |
| Institutional hierarchy | `apps.organization`; existing Membership/ScopeGrant in `apps.tenancy` | Available for authoritative organisational context. HR permissions must ultimately use M15 and preserve additional domain restrictions. |
| Business role, permission, assignment, overrides/delegation | Required M15 business RBAC | `role`, `permission` and `user_role_assignment` absent locally. Django Group/Permission is not a replacement for employee_document_access_rule.role_id. |
| Managed files | `apps.documents_exit.models.FileObject`, `storage`, `services`, `sharing` | Existing validation/scanner/private storage and compensating cleanup are reusable. Current sharing API is for explicitly institution-shared files, not an employee evidence ACL. Add an owner-aware private evidence contract in M13; never publish HR evidence through the announcement sharing path. |
| Central activity audit | Existing `apps.core.models.ReferenceAuditEvent`; M15 requires canonical ActivityAudit | Core audit exists; canonical `activity_audit` absent. M16 needs its own sensitive-access audit plus the M15 writer for restricted operations; do not silently substitute only one log. |
| Cryptography | No existing employee identifier crypto boundary found in inspected app code/requirements | Introduce a narrowly scoped provider using a vetted authenticated-encryption library plus separate keyed HMAC fingerprinting. Operational secret material must come from environment/secret manager; test keys only in tests. |
| Native schema primitives | Core/People unsigned fields; Student Support native ENUM/DATETIME/TEXT; Documents timestamp fields | Reuse stateless field primitives where suitable. Native VARBINARY, CHAR, YEAR and composite owner FKs need explicit mapping/DDL verification. |
| API/UI conventions | Existing module services/selectors, thin DRF command views, bounded pagination and core error envelopes | Follow these conventions, with stricter redacted serializers and no-store responses for sensitive HR. |

Read-only database inventory confirmed all six base prerequisites (`employee`, `user_account`, `country`, `state`, `document_type`, `file_object`) exist; none of the 17 M16 tables exist. No schema changes were applied during reconnaissance.

## Proposed file placement

Use a bounded `apps.employee_hr` package with models/field primitives, services, selectors, permissions, crypto boundary, audit integration, API serializers/views/URLs, read-only/service-driven admin, migrations, management commands and tests. Register it only after M15 contracts are settled. Reuse public M15 evaluator/audit APIs and M13 private file APIs; avoid reverse domain imports from those owners into HR.

Reference masters: qualification_level, study_mode, education_institution_type, awarding_body_type, education_institution, awarding_body, previous_organization_type and previous_organization.

Employee history: employee_qualification and employee_previous_employment. Preserve native generated uniqueness for the highest non-deleted qualification and optional experience_days override.

Restricted HR: employee_bank_account, employee_pan and employee_aadhaar. Preserve native ciphertext/fingerprint/masked columns, global fingerprint uniqueness, one PAN/Aadhaar per employee and generated primary-bank uniqueness.

Evidence: employee_document_category, employee_document and employee_document_access_rule. Preserve exact scope XOR checks and the five composite child/employee owner FKs; a service-only owner check cannot replace these database constraints. Supersession must also validate same employee and compatible scope and prevent branching/version races.

Audit: employee_sensitive_access_audit plus M15 ActivityAudit on restricted operations. Retain failed-access evidence without allowing an exception rollback to silently erase the only denial audit.

## Gaps and implementation decisions to carry forward

1. **M15 ordering:** resolve the three pending M15 choices and complete its selected implementation/cutover contract before M16 Prompt 2. User has been offered one consolidated choice to accept the three recommendations or specify alternatives.
2. **User FK type:** supplied M16 actor columns are unsigned; current custom user key is signed and has 90 inbound FKs. Follow the reviewed M15 migration/compatibility decision, not an isolated HR conversion.
3. **Cryptographic envelope:** use authenticated encryption, random nonce and embedded key-version metadata within VARBINARY(1024). Bind ciphertext to record kind and employee identity using authenticated context. Derive deterministic HMAC-SHA256 fingerprints from canonical plaintext with a separate secret and field-domain separation. Do not add an institution prefix that would defeat the supplied global uniqueness rule.
4. **Key rotation:** encryption-key rotation and fingerprint-key rotation have different effects. Preserve old encryption key versions until re-encryption/restoration is verified. Fingerprint-key rotation needs a coordinated reindex/duplicate-detection plan; mixing unversioned fingerprints from different keys can defeat uniqueness. No operational keys will be generated or committed implicitly.
5. **Output redaction:** ordinary API/admin/export DTOs expose only permitted metadata and masked/last-four values. Ciphertext/fingerprint are also excluded. Never echo submitted identifiers or include them in validation errors, audit payloads, traces or free-form logs. Dedicated decrypt flows need explicit M15 policy, purpose and dual audit; no general raw-field read endpoint.
6. **ACL combination:** per-document flags and validity windows must not override a business RBAC DENY or permit out-of-scope employee access. Source ACL rows are permission flags, not an explicit ALLOW/DENY enum. Treat them as an additional required grant where policy applies; do not invent implicit broad access from missing/expired rows.
7. **Storage:** current M13 local adapter is private but reports `encrypted=False`; confidential storage encryption/ACLs and a real malware provider remain deployment gates. Evidence must never expose durable public URLs. Link only files created/authorized through the employee evidence owner contract, not arbitrary FileObject IDs.
8. **Experience semantics:** the SQL view uses stored experience_days when present, otherwise inclusive date difference. Completed years and remaining months derive independently from calendar dates using TIMESTAMPDIFF; do not derive them from the override or divide by 365/30.
9. **Primary/highest semantics:** generated unique keys count rows with the flag true and deleted_at null. They do not implicitly filter verification status or effective dates. Services may add eligibility checks but must retain the precise DB uniqueness behavior.
10. **Soft-delete uniqueness:** PAN/Aadhaar employee uniqueness and fingerprints remain reserved after soft deletion. Restore/update records through controlled services; do not create a new row pretending soft deletion removed the unique constraint.
11. **Seed behavior:** add DOWNLOAD, six explicit EMPLOYEE resources and the specified permissions and HR roles through M15's business catalogue. SUPER_ADMIN must receive later EMPLOYEE additions. Preserve supplied HR_ADMIN/HR_OFFICER/PAYROLL_OFFICER rules, stable codes and existing master edits; no seed operation assigns users automatically.

## Planned verification

Each numbered implementation prompt gets relevant MySQL checks/tests before proceeding. Verify native column types/defaults, all 84 named constraints, generated uniqueness, composite owner FKs and seed matrix. Add crypto tests with test-only keys, tampered-ciphertext/context failures, masking, deterministic duplicate detection and no plaintext persistence. Test cross-employee IDOR, expired grants, RBAC denial precedence, sensitive dual auditing, denied-access audit durability, forged workflow actors, concurrent primary/highest/version operations and database/storage rollback cleanup. Preserve existing employee/M12 confidentiality and M13/M14 regressions.

## Reconnaissance changes and checks

Changed only this record, extracted prompt text and the schema-inventory JSON. No application or migration changes. Django check reports only the existing M13 MySQL W003 unique-storage-key warning; migration drift check reports no changes. The first prerequisite test run against a reused test database lacked seeded reference data. Rebuilding only the isolated test database restored migration seed state: all 23 People/M12 policy prerequisite tests passed in 62.45 seconds. One existing People-admin Django 6.0 URLField-default deprecation remains. Application database and runtime flags were unchanged.


Update 2026-09-25: all three M15 design decisions were approved. M15 staged code/schema/catalogue is now installed locally with activation disabled. The previous decision questions are resolved; remaining sequence work is implementation/integration and validation, not renewed approval. See M15_IMPLEMENTATION.md for current status.


## Implementation progress ? 2026-09-25

The M18 request extends the queue without replacing M16/M17. The three M15 decisions are already approved, and its installed evaluator/audit infrastructure is reused.

- Prompt 2: registered `apps.employee_hr`, bounded package layout, disabled runtime flag, existing M15 permission/audit and M13 file-owner imports. No unrestricted HR admin or API writer is exposed by the scaffold.
- Prompt 3: eight native reference/master models and a frozen-schema create/verify/adopt migration. SQL enums, lengths, nullability, unsigned key widths, unique keys, state/country FKs, defaults, table collations and server-maintained timestamps are retained. Existing incompatible tables cause migration failure rather than silent adoption. The migration preserves data on reverse.
- Prompt 4: qualification and previous-employment models, full source column coverage, generated highest-qualification uniqueness (including PURSUING rows; excluding only soft-deleted rows), all score/date/salary checks, experience_days override, composite owner uniqueness and exact named foreign keys. Actor FKs remain signed to match the approved M15 custom-user compatibility model. Explicit SQL maintains native timestamp ON UPDATE behavior; schema reversal that would erase history is unavailable.
- Prompt 5: internal AES-256-GCM boundary using pinned cryptography 50.0.1; random 12-byte nonces, authenticated employee/kind/version context, versioned ciphertext envelope, separate HMAC-SHA256 fingerprint key, masking and rotation support. Fingerprints omit employee/institution identity to preserve the source's global uniqueness semantics. No plaintext is stored by this boundary, and errors do not echo inputs. Aadhaar normalization here is a format check, not checksum or issuer verification; stricter identifier/workflow validation belongs to Prompt 6.

The crypto primitive is not a decrypt API. Future HR use cases must authorize and dual-audit persisted-data reads/decrypts before invoking it. Operational secrets must come from `SIMS_EMPLOYEE_HR_ENCRYPTION_KEYS` (JSON version-to-base64 32-byte key map), `SIMS_EMPLOYEE_HR_ACTIVE_KEY_VERSION` and `SIMS_EMPLOYEE_HR_FINGERPRINT_KEY` (separate base64 32-byte key). Defaults contain no usable keys and fail closed. Retain old encryption keys for historical ciphertext and backup recovery; do not rotate the unversioned fingerprint key independently of a coordinated duplicate-check/reindex plan.

Validation: a fresh MySQL database run passed the reference/history suite; after crypto, 32 related tests plus 6 constraint subtests passed across HR, IAM foundation/security and the M13 schema contract. The final HR-only run passed 15 tests plus 6 subtests, including exact foreign-key names and signed actor compatibility. An early migration-verifier numeric-default omission and two missing generated history relations were corrected before local installation. One test fixture used the wrong upstream employment choice and was corrected to REGULAR. All three HR migrations are applied locally; Django checks, migration consistency and pending-migration checks pass. The existing M13 MySQL W003 warning remains unrelated.

`cryptography`, `cffi` and `pycparser` are pinned in the lock; only the project virtual environment was updated. No production keys, employee records, sensitive identifier records or role assignments were created. Reference seeds are intentionally deferred to the pack's Prompt 15. No M18 index changes have been made.

Remaining: M16 Prompts 6-19, then M17 implementation, then M18 index work. Those remaining modules are not complete.


## Prompt 6 partial implementation (2026-09-25)

Added `models/restricted.py` and migrations 0004/0005 for employee bank accounts, PAN and Aadhaar. `VarBinaryField` preserves VARBINARY(1024); fingerprints/last-four values use native CHAR. Native ENUMs, nullable metadata, actor links, owner composite keys, named source foreign keys, source date/format checks and server update timestamps are retained. Actor foreign keys use the existing signed user key, consistent with the previously documented M15 compatibility choice. Primary-bank uniqueness follows the exact generated expression; one-per-employee PAN/Aadhaar and global fingerprints remain reserved after soft deletion.

Initial local application exposed Django deferred foreign-key creation: name alignment cannot execute inside the same migration before deferred keys exist. It is now a separate following migration. Only the three newly created, verified-empty tables from that failed application were removed for retry. Both migrations subsequently applied successfully; no existing business records were changed. The follow-up migration deliberately has no destructive reverse operation.

Synthetic MySQL tests cover ciphertext roundtrip, source column coverage, native binary/CHAR types, exact FK names, database format/date rejection and primary/identifier uniqueness including soft deletion. Permission entry now denies absent/anonymous principals explicitly.

Prompt 6 is not complete: authorized transactional create/update services, masked DTOs and their negative authorization tests remain next. No restricted API, plaintext read interface or admin registration was added. Later prompts must provide sensitive dual-audit, evidence lifecycle and verification workflows before rollout. M17, M18 and M19 remain queued in order.

Validation: 21 HR tests and 9 subtests passed on MySQL; `makemigrations --check --dry-run` reported no changes and `migrate --check` succeeded. The existing unrelated FileObject storage-key length warning remains.


## Prompt 6 authorization groundwork (2026-09-25)

Added `require_employee_permission` in `permissions.py`. It reloads employee ownership and derives GLOBAL/institution/current campus/current department scopes from persisted rows. SELF comes from the explicit employee-to-user account link. It denies inconsistent institutional ancestry, absent owners and unauthorized callers, delegates policy decisions to M15 and refreshes forced-password-reset state. Dates include the assignment's end date. No caller-provided institution or person identifier is treated as a SELF principal. This is an internal authorization boundary, not a read/decrypt/download endpoint; document rules and dual-audit remain later dependencies.

Tests exercise current/future/expired assignments, SELF linkage and other-employee denial, ancestor DENY precedence, cross-institution corruption, unrelated department grants, composite FK protection, stale disabled/reset actors and superusers without grants. Combined HR and M15 foundation tests: 38 passed, 9 subtests passed. Prompt 6 transactional writes and masked DTOs remain unfinished. See MODULE_EXECUTION_QUEUE.md for newly added M19-18 and M20.
