# M8 teaching allocation and timetable — schema review

Update, 23 September 2026: the initial audit below predates the user's policy decisions and implementation. Those decisions are now resolved in M8_ARCHITECTURE.md. The complete accepted schema is represented by the Django migrations and M8_REVISED_SCHEMA.sql; local migration and current verification results are in M8_RELEASE_AUDIT.md. References below to pending choices, absent M8 tables and ten tests describe the original audit only.

## Scope and status

Source: `M8-Teaching_Allocation_and_Timetable_Module_Prompt_Pack.docx`, extracted in `M8_prompt_pack_extracted.txt`. Work is on Prompt 1 and independent scheduling primitives. The full publication schema, migrations and later stages depend on the three scheduling-policy answers requested from the user.

`M8_UPSTREAM_SCHEMA.md` contains read-only live definitions. MySQL 8.4.11 is available; both M8 source tables are absent. M7's course-offering/section tables exist, but its full allocation/API/roster workflow remains unfinished. Do not silently treat M7 as production-ready or enable it as an M8 side effect.

## Issue matrix

| Severity | Evidence | Impact | Correction |
|---|---|---|---|
| Critical | `uq_timetable_room(day_of_week,time_slot_id,room_id,effective_from)` | Different effective starts or different overlapping slot IDs evade room conflict detection | Interval queries and serialized command/publication checks; replace misleading uniqueness with search index |
| Critical | Assignment FK references faculty_assignment_id alone | Session can use an assignment for another course section | Required candidate key `(faculty_assignment_id,course_offering_section_id)` and composite session FK |
| Critical | No lifecycle or revision identity | Draft edits can change the operational timetable | Separate approved publication design; awaiting user's revision/publication choice |
| High | Assignment unique key has no dates | Valid historical reappointment is forbidden | Include start_date in episode uniqueness; service rejects overlapping incompatible roles |
| High | No assignment/session end-date check | Reversed date ranges can be stored | CHECK end is NULL or at least start |
| High | Nullable workload has no magnitude constraint | Negative or zero workload can corrupt summaries | CHECK NULL or positive; interpretation and employee limit policy awaiting answer |
| High | Nullable room and assignment | FK/uniqueness cannot decide publication readiness | Explicit publication policy awaiting answer; never infer availability from NULL |
| High | Employee/course/room/time-slot references independently valid | Cross-institution or campus allocation is possible | Derive scope from course offering; validate every referenced parent and employee assignment |
| High | No faculty/class/batch temporal occupancy constraint | Double teaching or conflicting student sessions are possible | Compare dates, actual clock intervals and intersecting cohorts under consistent locks |
| High | No exceptions/history model | A holiday or substitute requires destructive editing | Approved, dated cancellation/move/substitution records tied to immutable publication identity |
| Medium | Source SQL user IDs differ from live Django user IDs | Actor FKs would fail | Signed BIGINT actor references matching the custom user table |
| Medium | Existing room has capacity/type but no facilities/accessibility catalogue | Required facilities cannot be verified | Explicit upstream contract; unavailable required evidence blocks acceptance instead of inventing master fields |

No syntactic defect was found in the two baseline CREATE statements. The existing room unique key is inadequate rather than syntactically invalid. MySQL nullable unique behavior does not substitute for a policy on roomless sessions.

## Core corrected DDL

`M8_CORE_SCHEMA_PROPOSAL.sql` preserves both source tables and identifiers, revises assignment episode uniqueness, adds date/workload checks and actor/version metadata, introduces the faculty/section candidate key and matching composite FK, and replaces room uniqueness with interval lookup indexes.

This is explicitly **core-table corrections**, not the complete deployment schema: revision/publication/exception/support records still require the pending policy decisions. No M8 migration has been applied to the application database.

Dependency order for these core tables: existing M7 course_offering_section and M5 employee → faculty_course_assignment → timetable_session, also referencing existing time_slot, room and signed Django user IDs. The candidate key is declared in the same DDL before the child FK. No invented upstream candidate key is assumed.

## Interval semantics

Clock intervals are half-open: 09:00–10:00 and 10:00–11:00 do not collide. Effective DATE bounds are inclusive, preserving source-style date semantics. Bound an open end by the relevant academic term before comparing occurrences. Weekdays use ISO Monday=1 through Sunday=7. Overnight time slots remain unsupported, matching the existing time-slot constraint.

Date-range overlap alone is not enough: find the first matching weekday inside the intersection. A Tuesday–Wednesday intersection contains no shared Monday meeting. Compare actual start/end times even when slot identifiers differ.

Whole-section teaching conflicts with every batch in that section. Two distinct batches can share a clock interval only when their rooms and instructors do not conflict; shared student membership across other sections still requires roster-based cohort validation in the full scheduling service. Pure primitives are not authorization or a concurrency barrier.

Faculty assignment validity must cover every generated teaching occurrence, not merely intersect the recurring effective range. The service must also validate active employee status, dated employment assignment, course-section ownership and configured competency rules. Leave/holiday and timetable exceptions need explicit precedence and cannot be guessed from absent data.

## Database and service responsibilities

Database: valid keys, non-reversed dates, positive specified workload, declared assignment/section identity and episode uniqueness. All references retain RESTRICT/NO ACTION.

Services: authorization, active/scoped parents, faculty eligibility, workload units/limits, room suitability/capacity, recurrence expansion, exceptions, room/faculty/cohort overlap, revision lifecycle, immutable publication, overrides and audit/outbox atomicity. MySQL has no simple ordinary unique key enforcing these arbitrary temporal exclusions.

Publication must revalidate against current published occupancy under the same locking protocol used by manual edits and solver acceptance. A preview or solver result is never authoritative after its inputs change.

## Verification performed

- `scripts/m8_preflight.py`: inspected table definitions only; no personal rows read.
- `scripts/m8_verify_schema.py`: cloned upstream table definitions into a uniquely named disposable database, executed both core CREATE statements, verified five added foreign keys, then removed that database in finally. Application schema/data unchanged.
- `backend/apps/teaching_timetable/intervals.py`: pure overlap primitives with ten passing tests covering touching clock boundaries, distinct effective starts, shared weekdays, inclusive date boundaries, whole-section/batch relationships, NULL rooms and invalid intervals.

Run: `backend/.venv/Scripts/python.exe -m pytest backend/apps/teaching_timetable/tests -q`.

These tests do not prove scheduling concurrency, API authorization, publication, solver quality or frontend behavior. Those remain later implementation/acceptance stages.

## Rollout and rollback

Complete the accepted publication/exception schema before model migrations. For legacy imports, quarantine reversed dates, cross-owner assignments, unknown slots, overlapping allocations and unsupported room/facility data. Do not silently deduplicate historical rows or rewrite attendance-linked identifiers.

Deploy schema and code with M8 disabled, reconcile historical data, validate constraints, then pilot publication. Once attendance consumes published occurrences, prefer forward corrections and withdrawal/version supersession over destructive rollback. A tested database backup and downstream replay plan are required for recovery; MySQL DDL is not undone by a Django atomic block.
