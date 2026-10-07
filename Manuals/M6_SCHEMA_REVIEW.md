# M6 admission and enrolment: schema approval review

Status: schema approved by user reply “1 yes 2 A”; manual fee-clearance policy selected. Implementation is in progress. The review SQL itself has not been executed.

Source: `M6-Admission_and_Enrolment_Transaction_Module_Prompt_Pack.docx`, extracted in `M6_prompt_pack_extracted.txt`. The pack says: **“Run Prompt 1 first and approve the corrected data model before generating migrations.”**

## Review artifacts and evidence

- `M6_REVISED_SCHEMA_PROPOSAL.sql`: complete proposed definitions for the four source tables, plus one supporting unique key on the existing curriculum table.
- `M6_UPSTREAM_SCHEMA.md`: read-only MySQL 8.4.11 inspection of actual parent definitions. All four M6 tables are absent. No personal records were inspected.
- `scripts/m6_schema_proposal.py`: reproducible generation from the source SQL. Does not connect to a database.

This proposal deliberately separates database guarantees from rules requiring transactional services. It is not a deployment script. No M6 migration or admission workflow has been installed.

## Decisions proposed for approval

1. Applicants belong to one institution. Application scope follows the chosen programme's department and campus; it must resolve to the applicant's institution. Applicant listings require institution-wide admissions authority; narrower users see only applicants associated with their authorized programmes, and cannot use deduplication to enumerate other applicants.
2. Permit repeat admission of an existing student into a different programme or academic year. Preserve the existing unique `(student, programme, admission_academic_year)` rule, so a second enrolment in the same programme and year remains prohibited. Each application converts once and produces exactly one enrolment through the admission service.
3. Admission creates an ACTIVE enrolment only after student activation prerequisites pass, including the previously approved primary-address requirement. Existing students are explicitly selected and verified in the same institution. Matching contact details never automatically merge people.
4. Accept applications for planned or active years; perform admission only into an active year with an admission date inside that year. Require an active, date-valid scheme with an exact programme and nullable-specialization match. Semester number must fit the programme duration.
5. Finance integration is not present. Before admission is enabled, choose either a separately authorized manual fee-clearance reference or an explicit no-fee pilot policy. Recording a reference is an administrative attestation, not payment verification.

## Findings and corrections

| Severity | Source evidence | Impact | Proposed correction |
|---|---|---|---|
| Critical | Applicant has no ownership column | Unscoped list, search and duplicate warnings can disclose personal records | Required institution FK; scope queries before lookup; narrower application-driven applicant visibility |
| High | `admitted_student_id UNIQUE` | One student can never have a second admitted application | Remove global uniqueness; retain a single nullable student pointer per application |
| Critical | Enrolment has no source application | Retried conversion can create unrelated or duplicate enrolments | Required unique application FK; composite application/student FK; locked idempotent conversion |
| High | Scheme FK references its ID alone | Scheme may belong to another programme | Unconditional `(scheme_id, programme_id)` FK with supporting unique key |
| High | Nullable specialization composite FK | NULL skips the composite check | Keep independent programme FK and unconditional scheme/programme FK; explicitly compare both nullable specialization values in the service |
| High | Separate caste and sub-caste FKs | Individually valid IDs can form an invalid hierarchy | Validate the entire chain in governed writes, including uncategorized castes; reject changed inactive parents, preserve unchanged historical references |
| High | No version or conversion lock | Stale review and simultaneous admission races | Integer version, If-Match on mutations, row locks, unique conversion key |
| High | History only has status/date/reason | No attributable ordering, corrections or concurrency protection | Required actor, recorded timestamp, effective date, source, request ID, per-enrolment sequence and optional correction link |
| High | Free-form history statuses and nullable reason | Impossible statuses and unexplained changes | Same status enum as enrolment, mandatory nonblank reason |
| High | Source user IDs are unsigned; actual Django IDs are signed | FK creation failure | Actor/reviewer IDs use signed BIGINT matching inspected `user_account` |
| Medium | No expected-completion date constraint | Completion may precede admission | Database CHECK plus service validation |
| Medium | No queue/contact lookup indexes | Unbounded scans | Institution/contact/name indexes; programme/year/status queue indexes; history effective-date index |
| Medium | No transfer lineage | Transfer can overwrite historical programme identity | Unique nullable predecessor FK; atomic predecessor transition and successor creation |

## Column and constraint disposition

**Applicant:** retain unsigned auto primary key; required first/display names and their existing lengths; nullable middle/last names, birth date, gender, contact and demographic FKs. Blank optional strings normalize to NULL. Names are not identifiers. Email/phone remain non-unique because families can share contact details. Normalize email consistently with the existing people module and normalize phone only when sufficient country context exists. Candidate matching is scoped, explainable and manually confirmed. Retain creation/update timestamps; add actors, optimistic version, institution and optional canonical student reference. Canonical student assignment requires a governed identity decision and cannot be casually reassigned.

**Application:** retain unsigned ID, globally unique application number, required applicant/programme/year/date, nullable specialization/category/remarks, all existing workflow/eligibility enum values and defaults, and timestamps. Application numbers are server-generated; clients cannot select student pointers or states through general PATCH. Add reviewer, actors, version and a supporting application/student unique key. A CHECK requires a student pointer exactly when status is ADMITTED; another requires eligible status for ELIGIBLE/SELECTED/ADMITTED. Other transition consistency is a service responsibility. Database collation remains `utf8mb4_unicode_ci`; uniqueness preflight uses database comparisons, not Python case folding.

**Enrolment:** retain required student/programme/scheme/year/date/semester, nullable specialization/category/expected completion, source status enum/default and natural unique key. Add unique source application, optional unique transfer predecessor, timestamps, actors and version. The unconditional composite scheme FK validates programme ownership even when specialization is NULL. Exact specialization equality, application programme/year/category agreement, student institution, active parents, admission-date/year bounds and semester limits remain transactionally validated service rules. Do not allow general PATCH of historical ownership. Scheme or date corrections need dedicated commands and append-only evidence.

**History:** retain unsigned key, required enrolment and effective date. Old status remains nullable only for the first event; new status is required. Replace VARCHAR statuses with the enrolment enum. Require nonblank reason and add actor/time/source/request/sequence/correction metadata. Service locks the enrolment, derives old status from the database, checks permitted transitions and writes state plus history atomically. Clients cannot supply arbitrary old status, sequence or actor. Correction links must refer to the same enrolment; no in-place history editing. As-of queries use effective date and sequence, preserving recorded-time evidence.

All relationships retain RESTRICT/NO ACTION in SQL and PROTECT in Django. No cascading deletion or public hard-delete endpoints. Retention durations require institutional policy; no invented legal retention period. Archive or anonymization is a separate reviewed operation, preserving required academic and audit links. Application-level append-only history is not protection against a database administrator.

## Guarantee boundaries

The database guarantees at most one enrolment per application and matching admitted student when an enrolment exists. It does **not** enforce that every ADMITTED application has an enrolment: the admission transaction and reconciliation check enforce that reverse relationship. It also does not validate nullable specialization equality or cross-table date windows; services must do so under the existing shared governance lock and relevant row locks. Tests must exercise direct constraint violations and simultaneous command execution separately.

## Required support records at implementation

These are platform-support records, not additional academic entities. Their Django definitions and migrations follow approval:

- Command receipt: institution, actor, command, idempotency key, request digest and resulting record IDs; unique scoped key; no raw applicant payload. Same key/different digest returns conflict. Reauthorize every retry.
- Workflow audit: actor/action/resource/record/time/request, reason and allowlisted bounded changes. Avoid duplicating sensitive demographic/contact payloads; never store credentials or tokens. Writes share the business transaction.
- Outbox: event UUID, event type, minimal record identifiers, occurred/delivered timestamps, retry metadata. Commit with the command; dispatch after commit with consumer deduplication. An on-commit callback only wakes dispatch; it is not the durable event store.
- Clearance evidence if manual fee clearance is selected: authorized actor, time, reference and application link, protected from ordinary application edits.

## Migration and verification plan

For this inspected database, create new tables after adding the supporting M4 unique key through an M4-owned migration. Match Django migration state and database state; never apply this proposal as ad hoc production SQL. Reverse in dependency order and only before real admissions exist.

For legacy installations, stage source rows with batch/source keys and hashes. Report missing ownership, duplicate student/programme/year enrolments, ambiguous application links, invalid hierarchies, scheme mismatches and broken histories. Do not invent application links, dates, actors or identities. Resolve or quarantine exceptions with signed decisions before backfilling required fields and enforcing constraints. Compare counts and relationships; release requires zero unexplained discrepancies.

Next: after schema/policy approval, execute Prompts 2–8 in order, then security, real-MySQL concurrency tests, migration rehearsal and deployment gates in Prompts 9–12. Browser verification and production deployment must be reported separately from unit tests and local builds.
