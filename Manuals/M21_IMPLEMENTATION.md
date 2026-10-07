# M21 journals and journal publications

Status: M21 publication models and their shared schema prerequisites are implemented and migrated locally in response to the latest request to resolve the models. Services, APIs, UI, seeds and the remaining module prompts are not implemented. Earlier discovery findings below are historical.

Source: `Prompts/M21-Journals_Journal_Publications_Django_Prompt_Pack.docx`.
Extracted requirements: `M21_prompt_pack_extracted.txt`.
The original DOCX and consolidated SQL remain unchanged.

## Preliminary findings — 2026-09-25

The pack contains 16 ordered prompts. Its four tables are `journal`, `journal_publication`, `journal_publication_indexing` and `journal_metric`. Each has exactly one definition in the consolidated SQL, beginning at lines 4000, 4022, 4054 and 4068 respectively. None exists in the current local database or has an installed model owner.

`scripts/m21_discovery.py` records source definitions, references, local schema presence and registered owners in `M21_SCHEMA_INVENTORY.json`. It reads schema metadata only. Refresh the inventory after the queued predecessors complete.

Reuse existing owners for `accounts.User`, `people_master.Employee`, organizational institution/campus/department, `academic_calendar.AcademicYear` and `common_reference.Country`. M19/M20 are expected to supply journal/publication types, publisher, indexing agency, metric type and the activity/status taxonomies; do not create parallel masters in the journal app.

`staff_activity` is absent from both registered models and the local database. It is not one of the 28 M19/M20 reference tables. M21 requires it as the publication's one-to-one PK/FK parent and as the atomic service's organization, employee and workflow owner. Prompt 1 must explicitly resolve its canonical shared ownership and migration prerequisite before Prompt 2, using the existing source definition at line 3903. Do not substitute employee or create an unrelated journal-only parent identity. This discovery does not complete the full Prompt 1 architecture review.

## Contracts to retain during implementation

- Publication identity is `staff_activity_id`; creation/update must be atomic with its parent, with activity-type and organizational-scope validation.
- Indexing has the composite primary key `(staff_activity_id, indexing_agency_id)`. Evaluate the project's existing Django 5.2 composite-key conventions before proposing any workaround.
- Journal ISSN/eISSN and publication DOI uniqueness preserve SQL NULL behavior. Normalize identifiers at the service boundary and translate concurrent uniqueness failures safely.
- Source SQL explicitly checks nonnegative metric values. Publication-date/year agreement and positive supplied author position are additional prompt-required service validation; do not claim they are existing source CHECK constraints.
- Journal defaults can prefill new publication attributes; subsequent journal edits must not rewrite historical publication values.
- Indexing includes CLAIMED, VERIFIED, DISCONTINUED and NOT_INDEXED. Verification requires separate permissions and audit. Metric `verified_at` must be server-controlled, with actor provenance supplied by the shared audit framework.
- Derive row scope from trusted employee/activity relationships. Enforce the same scope in lists, autocomplete, reports and exports.
- Coordinate performance work with earlier index packs; preserve existing useful indexes and require query-plan evidence for additions.

## Ordered prompt checklist

1. Complete repository/dependency analysis and file/migration plan.
2. Implement models and migrations after upstream ownership is resolved.
3. Implement normalization and domain validators.
4. Implement atomic activity/publication services.
5. Implement journal master management and autocomplete.
6. Implement scoped publication REST APIs.
7. Implement indexing verification workflow.
8. Implement metric history and verification.
9. Implement React/TypeScript PWA screens.
10. Integrate and test RBAC/audit across all actions.
11. Measure MySQL query plans and query counts.
12. Implement authorized reporting and export.
13. Run and fix the automated quality gate.
14. Review security and add regression tests for confirmed issues.
15. Prepare deployment readiness evidence and checklist; do not infer production deployment authorization from the document.
16. Complete SQL/API/UI/test traceability and final documentation.

The original broader queue remains incomplete at M16 Prompt 6. The latest request explicitly advanced M21 model dependency resolution; it does not mark any earlier module complete. See the implementation update below and `MODULE_EXECUTION_QUEUE.md`.


## Publication model dependency resolution ? 2026-09-25

The user requested resolution of M21 publication models. Implemented and registered three canonical owners:

- `apps.staff_profile`: eleven required shared masters (`publication_type`, `journal_type`, `indexing_agency`, `metric_type`, `external_organization`, `publisher`, `activity_type`, `participation_level`, `role_type`, `verification_status`, `approval_status`). M19/M20 must reuse these rather than recreate them; their remaining 17 reference tables and application workflows remain pending.
- `apps.staff_activities`: `StaffActivity`, preserving all source actor, organization, employee, workflow, lifecycle and timestamp columns. No parallel employee/user identity.
- `apps.research_publications`: `Journal`, `JournalPublication`, `JournalPublicationIndexing`, `JournalMetric`. Publication identity is a OneToOneField primary key to StaffActivity. Indexing uses Django's native composite primary key; no surrogate ID is added.

### Schema and migration decisions

Frozen source DDL is paired with complete Django migration state using SeparateDatabaseAndState. This preserves exact source FK/unique/check names, ENUM, YEAR, unsigned keys, TEXT, DATETIME, TIMESTAMP defaults/ON UPDATE, collation and nullability. Existing-table collisions abort before creation and require a reviewed adoption; they are not silently accepted. Reverse migration refuses populated tables. Empty-table reversal drops only the owning app's tables, in dependency order, and retains database FK protection. MySQL DDL is nontransactional: a partially failed install requires inspection before retry. No production migration or deployment occurred.

The existing `user_account.user_id` is signed, so the shared parent's actor columns use matching signed BIGINT. This follows the established identity integration rather than altering the user table. Source activity_group has **12** enum values, including OTHER; all are preserved despite the M19 prose saying eleven.

Initial raw DDL already installed native TEXT/DATETIME. Follow-up state-only migrations align Django fields with those physical types, avoiding later LONGTEXT or fractional-DATETIME drift. Operational endpoints and admin interfaces are not exposed by this model-only change. No institutional seed values or user grants were created.

### Verification

Applied five local migrations across the three new apps. The MySQL tests cover all 16 new tables' column names/types, source named FKs and unique constraints, server update timestamps, shared publication identity, orphan/duplicate rejection, composite-key ORM lookup, DOI/ISSN nullable uniqueness, metric precision/nonnegative checks, protected references, parent dates, transactional rollback, independent historical publication flags and migration refusal on existing/populated tables.

Combined publication, HR and M15 foundation tests: **46 passed, 9 subtests passed**. Django checks and migration drift checks passed. The previously existing FileObject unique storage-key length warning remains when running MySQL migration checks. New-app lint/format checks are also run as part of this change.

### Remaining boundaries

The missing schema prerequisite is resolved. Prompt 3 domain normalization/date-year/author-position validation and Prompt 4 authorized atomic services are next for M21. Direct ORM save does not enforce one specialized child across all future activity types, title synchronization, scoped authorization, soft-deletion workflow or verification authority; these must be implemented in the later service/API stages before operational use. No full-module, UI, export, performance, production-readiness or deployment completion is claimed.
