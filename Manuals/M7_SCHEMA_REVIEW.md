# M7 schema audit — Prompt 1

Source: `M7-Term_Registration_Section_and_Course_Registration_Module_Prompt_Pack.docx`; extracted text is `M7_prompt_pack_extracted.txt`. The active editor's fees SQL is context, not the requested module.

## Evidence and current decisions

`M7_UPSTREAM_SCHEMA.md` records read-only inspection of MySQL 8.4.11. All eight M7 tables are absent. M1–M5 parent tables and the M6 enrolment table exist. M6 remains incomplete and disabled by default; consuming it must not silently enable admissions.

The user confirmed: **only REGISTERED and APPROVED term registrations reserve seats**. DRAFT has no reservation guarantee. Approval or registration from draft must acquire locks and recheck capacity.

Progression policy approved: authorized registrar approval with a recorded reason. No result or timetable app was found. Missing result/attempt/prerequisite/clash evidence must never become implicit eligibility. Course credit limits must be explicitly configured before registration, not inferred from a guessed institutional policy.

## Issue matrix

| Severity | Table | Evidence / impact | Correction |
|---|---|---|---|
| Critical | student_term_registration | Enrolment and offering separately valid but may belong to different programmes | Required server-derived programme_id; composite FKs to enrolment and offering candidate keys |
| Critical | student_course_registration | Independent term-registration/offering FKs permit cross-term registration | Required server-derived programme_term_offering_id with two unconditional composite ownership FKs |
| High | programme_term_offering | Scheme ID FK does not establish programme ownership | Composite scheme/programme FK using existing M6-added candidate key; exact nullable specialization checked in service |
| High | course_offering | curriculum_course_id and course_id can disagree | Composite curriculum-course/course FK with explicitly declared upstream unique key |
| High | sections, batches, course offerings | Unsigned capacity permits zero and no concurrent occupancy rule | CHECK positive-or-NULL; locked occupancy checks on allocation and capacity changes |
| High | roster | Unique mapping/registration pair permits simultaneous conflicting session assignments across mappings | Denormalized session_type validated by composite FK; generated active registration key unique per session type |
| High | roster | Unique mapping/registration pair prevents returning to a previous section without overwriting history | Episode uniqueness includes effective_from; retain old row/ID for attendance references |
| High | all mutable records | No revision or write provenance | Required version, actor IDs and timestamps; transactional immutable audit support |
| High | all scoped operations | Programme/term IDs alone do not authorize ownership | Derive institution/campus/department from programme; scope list query and every referenced record |
| Medium | roll_number | Nullable uniqueness intentionally permits multiple NULLs but also blank strings | Normalize blank to NULL and CHECK nonblank; preserve database collation comparisons |
| Medium | roster dates | Open intervals and status changes lack overlap enforcement | Half-open interval policy; ACTIVE requires open end; overlaps checked under shared command lock |
| Medium | source actor schema | Source IAM uses unsigned IDs; live Django user uses signed BIGINT | Use signed actor IDs to match the actual parent table |

No SQL syntax defect was found in the supplied eight-table baseline. Existing unique owner keys are necessary for its composite foreign keys. Explicit FK-supporting indexes need not be duplicated because InnoDB creates them. Foreign keys retain RESTRICT/NO ACTION; no cascading deletion is introduced.

## Complete revised DDL and dependency order

`M7_REVISED_SCHEMA_PROPOSAL.sql` contains all eight tables and the two new upstream prerequisite keys. `scripts/m7_schema_proposal.py` reproducibly builds this review artifact without database access.

1. M4: unique curriculum_course(curriculum_course_id, course_id).
2. M6: unique student_programme_enrolment(enrolment_id, programme_id).
3. Existing M6 prerequisite: unique curriculum_scheme(curriculum_scheme_id, programme_id).
4. programme_term_offering → class_section → class_batch → student_term_registration.
5. course_offering → course_offering_section → student_course_registration → course_offering_section_student.

Identifiers and existing valid composite keys are retained. The only revised original uniqueness rule is roster episode uniqueness, explicitly needed to preserve return-transfer history. Django migrations must place upstream model-state changes in their owning apps; review SQL must not be executed ad hoc against production.

## Database versus service guarantees

MySQL: identity, existence, declared composite owners, duplicate code/roll/registration prevention, nullable generated-key uniqueness, positive capacities, roster dates and one open active roster per registration/session type.

Services: active enrolment; exact programme/specialization/scheme compatibility; applicable semester and curriculum composition; registration windows; progression and eligibility evidence; credit/attempt limits; room campus consistency; capacity counts; status transitions; historical overlap; approved course registration before roster activation; same section/batch as allocated term registration; actor scope and parent scope; controlled correction and transfer.

NULL in a composite FK skips checking that FK. Therefore scheme/programme enforcement uses two required values; optional specialization identity is a separate check. Optional curriculum_course still permits declared exceptional offerings; that exception needs a separate capability, reason and eligibility policy, never a silent fallback.

Whole-section and batch mappings can coexist as setup records, but the active roster uniqueness prevents a student simultaneously joining two mappings for the same session type. Cross-programme shared electives require a future explicit design; do not weaken same-offering constraints to support them.

## Index rationale

- Programme + term + status serves scoped offering queues.
- Section/batch + registration status serves seat counts under allocation locks.
- Course offering + registration status serves course occupancy.
- Offering + status serves course setup and availability.
- Mapping + roster status + interval dates serves current rosters and attendance-date lookup.
- Existing natural uniqueness indexes serve duplicates and exact lookups. Prefix code/roll search should use indexes; broad personal-data searches and unbounded exports are excluded.

## Rollout and rollback

For the inspected empty M7 deployment, add prerequisite unique keys, create tables, validate constraints, deploy disabled code, then enable an institution after acceptance. For legacy installations, stage and quarantine cross-owner rows, roll collisions, overcapacity and overlapping episodes. Do not infer missing ownership, silently drop duplicates or rewrite attendance-linked IDs.

Rollback before use can remove M7 tables in reverse dependency order and then the new upstream keys. After live registrations exist, prefer disabling writes and a forward fix; destructive rollback requires a tested backup/restore and downstream dependency review. MySQL DDL is not transactionally rolled back merely because a migration is atomic.

## Verification status

Preflight and DDL generation ran successfully. `scripts/m7_verify_schema.py` executed all 10 proposal statements in a uniquely named disposable MySQL database containing copies of upstream table definitions only. All eight tables and 23 additional foreign keys were created successfully; the disposable database was removed in finally. No application data or schema was changed. This proves DDL compatibility, not runtime ownership/capacity correctness. Model migrations, transactional tests, API, frontend and deployment acceptance remain implementation stages; they are not claimed complete by this audit.

## Approved progression policy

User selected option 1: authorized registrar approval with a recorded reason. Only REGISTERED and APPROVED term registrations reserve seats. No further confirmation of these policies is required.
