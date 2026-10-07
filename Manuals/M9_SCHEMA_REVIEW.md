# M9 schema review — stages 1 and 2

Source: M9-Attendance_and_Lesson_Plan_Module_Prompt_Pack.docx. The extracted text is in M9_prompt_pack_extracted.txt. Read-only preflight found none of the four supplied M9 tables in the configured local development database. M7 and M8 remain disabled globally.

## Issue matrix

| Severity | Source object | Evidence | Required correction |
| --- | --- | --- | --- |
| Critical | class_session | Separate faculty/timetable FKs do not enforce section identity | Composite candidate keys and FKs, plus dated published-occurrence validation |
| Critical | student_attendance | Mutable counts_as_present affects historical totals | Explicit immutable policy interpretation and stored contributions |
| Critical | attendance_correction_request | No requester/resolver/version; concurrent decisions can overwrite | Actor FKs, expected attendance version/status, serialized review and immutable history |
| High | attendance_correction_request | No pending uniqueness | Generated nullable pending key with unique constraint |
| High | student_attendance | marked_by_user_id has no FK | FK to the configured platform user PK; do not assume its SQL type |
| High | class_session | RESCHEDULED has no lineage | Explicit source/replacement links; retain old register and plan evidence |
| High | student_attendance | Current roster can change after marking | Freeze exact eligible roster IDs when opening; reconcile explicit differences before finalization; finalized snapshots stay stable |
| High | attendance_status | Renaming/reweighting has no historical provenance | Immutable code identity; weights belong to versioned attendance policy, not mutable labels |
| High | class_session | Concurrent class-number allocation and regeneration | Transactional allocation, unique section/class number and occurrence identity |
| Medium | planned_topic/topic_covered | No ordered plan or partial coverage history | Ordered immutable topic revisions plus dated coverage |
| Medium | all source tables | No optimistic versions, request receipts or bounded bulk contract | Session aggregate version, actor-bound digest receipts and atomic bulk commands |

## Architecture constraints

New app: apps.attendance_lesson_plan. API namespace: /api/v1/attendance/. Frontend route: /#/attendance. Global and per-institution feature switches default off.

Reuse existing M7 course-offering sections and dated roster episodes and M8 published occurrences/dated exceptions. A class session snapshots the committed schedule it was created from. Later timetable changes are reconciliation findings, not silent historical rewrites. Additional and replacement sessions require explicit exceptional-session authority and complete dated assignment/room/term validation.

The shared organization governance lock is acquired before actor reauthorization and session/register/correction locks. Every writer uses the same path. Session version serializes bulk marking and lifecycle changes; row version protects correction approval. No API accepts a client-owned section for an attendance row.

No implicit absence: unmarked entries remain explicit, and finalization must resolve them. Cancelled/rescheduled source sessions do not contribute to attendance totals. Pure calculation primitives consume explicit stored contributions; they never consult current status flags or invent a shortage threshold.

M4 curriculum and M3 academic calendar are reused. No holiday model was found in the current academic-calendar app; holiday validation needs an explicit adapter or dated scheduling evidence, rather than a fabricated calendar.

## Accepted decisions

The user accepted all three recommended choices: immutable section policy revisions frozen per session, a different authorized correction reviewer, and ordered lesson revisions with dated coverage. Thresholds, weights and edit windows remain explicit institution configuration; no numeric policy was invented.

The original reference schema stays unchanged. M9_reviewed_migration.sql records generated migration DDL; run Django migrations to include status seeding.

## Verified prerequisite details

The metadata-only preflight is captured in M9_UPSTREAM_SCHEMA.md and can be rerun with scripts/m9_preflight.py through manage.py shell.

- The actual user_account.user_id is signed BIGINT. The source M9 marked_by_user_id declaration is unsigned and must change to match the configured User FK.
- FacultyAssignment already exposes the (faculty_assignment_id, course_offering_section_id) candidate key.
- M7 exposes exact roster/section and mapping/session-type candidate keys.
- M8 timetable sessions and published occurrences need additional candidate keys for composite section ownership.
- Reuse the existing published occurrence's actual PK type instead of assuming every new platform identifier is unsigned.

## Implementation

Models, migrations, services, APIs, UI, import/health tools and automated tests are now implemented. See M9_IMPLEMENTATION.md for release status and remaining operational acceptance gates. The immutable calculation interpretation is connected to finalization and reviewed correction services.
