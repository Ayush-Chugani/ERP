# M4 Prompt 1 — domain and schema gap analysis

Status: source/database review complete; three business decisions requested from the user remain pending. This document does not approve an ownership or elective-credit change. M4 Prompts 2–14 remain the authorized objective, with dependent migrations gated on those answers.

Sources: the five-table DDL in the M4 pack and Section 4 of sims_v6_5_1_mariadb_full_schema.sql; the complete SQL's downstream FK references; actual Django 5.2.17 code; M4_UPSTREAM_SCHEMA.md read-only MySQL evidence. No ALTER TABLE additions for these five tables were found in the full SQL. The configured database currently contains none of the five target tables.

## Field mapping

| Table | All supplied fields | Mapping and review |
| --- | --- | --- |
| course_category | course_category_id | SMALLINT UNSIGNED auto ID: existing UnsignedAutoField(16) |
| course_category | category_code(30), category_name(100) | Explicit utf8mb4_unicode_ci, independently globally unique unless ADR-01 changes ownership |
| course_category | is_graded, contributes_to_gpa, is_active | BooleanField with application/database defaults true |
| course_catalog | course_id | INT UNSIGNED auto ID: UnsignedAutoField(32) |
| course_catalog | owning_department_id, course_category_id | SMALLINT UNSIGNED protected FKs; department derives institution |
| course_catalog | course_code(30), course_title(200), short_title(80) nullable | Normalized text, preserve lengths and nullability; code globally unique pending ADR-01 |
| course_catalog | course_type | THEORY/LAB/THEORY_LAB/PROJECT/SEMINAR/INTERNSHIP/OTHER; TextChoices + DB CHECK |
| course_catalog | lecture_hours, tutorial_hours, practical_hours, self_study_hours, credits | Decimal(4,1), default zero, exact Decimal arithmetic and nonnegative CHECK |
| course_catalog | effective_from, effective_to | Both optional dates; either null means an open boundary; supplied ordered-date CHECK retained |
| course_catalog | is_active | Boolean default true; explicit service lifecycle writes |
| curriculum_scheme | curriculum_scheme_id | INT UNSIGNED auto ID |
| curriculum_scheme | programme_id, specialization_id nullable | SMALLINT UNSIGNED protected relations plus exact composite specialization/programme FK |
| curriculum_scheme | scheme_code(30), scheme_name(150) | Code globally unique pending ADR-01, normalized names |
| curriculum_scheme | regulation_year | MySQL YEAR requires a migration-stable custom integer field; proposed policy 1901–2155, reject YEAR zero for academic validity |
| curriculum_scheme | total_credits | Nullable Decimal(6,1); proposed nonnegative declared activation target, not sum of all elective alternatives |
| curriculum_scheme | effective_from required, effective_to nullable | Add date-order validation/CHECK; null end is unbounded |
| curriculum_scheme | status | DRAFT/ACTIVE/RETIRED, default DRAFT; readonly ordinary payload; state machine in service |
| curriculum_course | curriculum_course_id | BIGINT UNSIGNED auto ID requires new custom BigAutoField, NOT existing 32-bit field |
| curriculum_course | curriculum_scheme_id, course_id | INT UNSIGNED protected FKs |
| curriculum_course | semester_id | TINYINT UNSIGNED protected FK to shared Semester; programme duration is separate service validation |
| curriculum_course | course_category_id | SMALLINT UNSIGNED FK; consistency with course default requires policy |
| curriculum_course | is_mandatory | Boolean default true |
| curriculum_course | elective_group_code(30) nullable | Normalized code; mandatory/elective contradiction requires validation |
| curriculum_course | display_order, exam_duration_minutes | Nullable SMALLINT UNSIGNED (0–65535 storage); semantic positivity/order policy distinct |
| curriculum_course | internal_max_marks, external_max_marks | Decimal(6,2), default zero; add nonnegative validation/CHECK |
| curriculum_course | passing_marks | Nullable Decimal(6,2); if present, zero <= passing <= internal+external |
| course_prerequisite | course_id, prerequisite_course_id | Two INT UNSIGNED FKs forming composite primary key; preserve pair identity |
| course_prerequisite | minimum_grade(5) nullable | Trim/normalize; validate against an explicitly configured grading allowlist, never invent grades |

BIGINT identifiers must round-trip through JSON/TypeScript as decimal strings; converting them through JavaScript Number would lose precision above 2^53-1. The prerequisite pair uses bounded 32-bit component IDs but retains a composite identifier, not a silently invented surrogate.

## Constraint inventory and enforcement

| Supplied constraint | Database | Application/service |
| --- | --- | --- |
| category_code/category_name uniqueness | Separate UNIQUE constraints using actual collation | Same-collation lookup, stable conflict, raw DB final defense |
| course_code uniqueness | UNIQUE pending ownership ADR | Normalize and validate without revealing another tenant's record |
| chk_course_nonnegative_values | Preserve named five-value CHECK | Field errors before write |
| chk_course_effective_dates | Preserve null-aware CHECK | Validate before mapping/activation |
| fk_course_department, fk_course_category | Compatible numeric protected FKs | Trusted department scope and active parents for new assignment |
| scheme_code uniqueness | UNIQUE pending ADR | Stable conflict and immutable identity/versioning |
| fk_scheme_programme | Protected FK | Programme context derived and scope-checked |
| fk_scheme_specialization_programme | Composite FK (specialization_id,programme_id) -> verified composite key | Validate owned specialization before DB save; null specialization still means general programme scheme |
| uq_curriculum_course | UNIQUE(scheme,semester,course) | Draft-only composition and duplicate rejection |
| four curriculum_course FKs | Protected FKs to scheme, semester, course, category | Scope, programme semester range, course validity and category consistency |
| prerequisite pair PK | Native composite primary key | Pair-addressed commands and API |
| chk_prerequisite_not_self | Preserve named CHECK | Stable self-link error before graph scan |
| both prerequisite FKs | Protected course relations | Check both endpoints, institution policy, active state/validity |

Proposed extra row-local CHECKs: scheme date order and nonnegative target; nonnegative marks and bounded passing marks; mandatory/elective field consistency; enumerated status/type sets. Cross-table/category/semester and cross-row effective-range/graph/credit rules are service invariants, not fake CHECK constraints. A shared lock must coordinate all sanctioned writers.

## Risk-ranked gaps and resolutions

| Severity | Gap / affected consumers | Resolution proposal |
| --- | --- | --- |
| High | Global codes conflict with multi-client code reuse; changes affect all FK consumers and data imports | ADR-01 awaits choice: preserve global baseline or add explicit institution ownership/scoped uniqueness with backfill |
| High | Course sharing/category drift across programme mappings could invalidate assessment and GPA | ADR-02 proposes same-institution cross-department reuse, exact category match; disallow override endpoints unless separately approved |
| High | Active scheme date overlap makes offering/enrolment selection ambiguous | Serialize programme/specialization activation; reject inclusive interval overlap, treating null as unbounded; only drafts editable |
| High | Elective credits cannot be summed naively; no selection-count field | ADR-03 awaits one equal-credit selection per semester/group versus deferring elective activation |
| High | Concurrent prerequisite edges can jointly create a cycle | Lock graph mutations at common institution/global scope; O(V+E) traversal, explicit cycle path with authorized IDs only |
| High | Django admin rejects composite-primary-key models in installed sites.py | Preserve prerequisite schema and provide service-backed custom admin views/link to governed frontend; do not register it with ordinary ModelAdmin |
| High | Existing UnsignedAutoField cannot represent BIGINT | Add a separate migration-safe field and string ID serializer; preserve old field imports |
| Medium | YEAR differs from SMALLINT; baseline accepts zero | Custom MySQL YEAR field and explicit policy; document stricter academic zero rejection |
| Medium | Scheme/course history can be mutated after registrations/results exist | Active/retired structure immutable, clone to a new code/version; protect downstream references; no automatic historical rewrite |
| Medium | Semester reference is global rather than programme-owned | Verify 1 <= semester_number <= programme.duration_semesters; no fabricated semester ownership FK |
| Medium | Zero-total marks/pass-fail behavior unspecified | Proposed zero total allowed only for ungraded category, passing_marks null/zero; graded mappings require positive total at activation |
| Medium | Elective ordering/group and validity gaps | Group keyed by scheme+semester+normalized code; unique nonnull display order per semester; activation validates course validity covers scheme interval |
| Medium | Minimum-grade policy absent | Only null accepted until deployment config supplies approved grade codes; do not depend on nonimplemented results models |
| Medium | General workflow/confidentiality machinery assumed but absent | Use explicit scoped Django lifecycle permissions; draft reads require edit/design authority; no invented approval state; document limited support and fail closed beyond it |
| Medium | Lost updates in editor workflows | Proposed ETag derived from canonical bounded snapshot; require expected version on update/action; compare after lock |
| Medium | Durable events not available | Transactional support event records with stable IDs and documented pull/ack contract only if required; never claim external delivery from an audit insertion |

## Ownership and lifecycle rules awaiting confirmation

The existing department -> campus -> institution and programme -> department chains are authoritative. Membership, role, Django permission, module activation and record limits must all agree. No payload creates institution authority. Shared categories (if approved) remain platform-maintained. Cross-institution mappings and prerequisites are denied. Existing ScopeGrant capabilities can express editor/designer/approver via scoped assignment plus explicit Django permissions; no new password or parallel role store.

Proposed scheme transitions: DRAFT -> ACTIVE -> RETIRED; DRAFT -> RETIRED for cancellation; RETIRED is terminal, use clone. Draft-to-active validates every mapping and returns all readiness defects. No implicit activation by ordinary PATCH. Course active/deactivated states preserve historical mappings; referenced semantic fields freeze. Removing a draft-only mapping or prerequisite is an explicit audited command, with impact confirmation, not a generic DELETE endpoint.

No approval is inferred from M3 calendar choices. The async questions sent in this turn cover ADR-01 (global codes), ADR-02 (composition/lifecycle/sharing) and ADR-03 (elective credit selection). These must be resolved before dependent domain migrations and services.

## Downstream compatibility

The full SQL references courses from employee_competency, course_offering and professional contributions; schemes from student_programme_enrolment, programme_term_offering and curriculum_framework_node; mappings from course_offering. Later assessment/results consume offerings and their historical scheme context. Preserve all IDs and composite ownership relations, avoid cascades and expose versioned read DTOs. These consumers are not currently installed Django apps, so they cannot be declared integration-tested. Future modules must supply eligibility/grade policy through public contracts, not import curriculum managers.

## Migration and profiling gate

Current environment: target tables absent, upstream numeric types/composite key verified on MySQL 8.4.11. Legacy adoption still needs preflight read-only checks; never fake initial migrations over imported tables. Use M4_DATA_PROFILING.sql only on an existing legacy schema after confirming table presence. Review orphan counts, case/accent duplicate codes, specialization ownership, bad date/mark ranges and self-links; then run graph and interval validation in staging. Retain row counts and canonical hashes for reconciliation. Any ownership change requires an explicit reviewed mapping and restartable backfill before nonnull/UNIQUE changes.

Prompt 1 is review-only: no domain migration or business feature has been introduced. The next independent work may verify framework field/adapter capabilities; dependent implementation waits for the recorded decisions.

## Approved decisions — user confirmation

The user confirmed global codes/shared platform categories, proposed draft-only editing and activation overlap/category/sharing rules, and one equal-credit course per semester/elective group. ADR-01/02/03 are resolved accordingly. Subsequent implementation may proceed. No institution-specific ownership columns or elective selection-count columns are introduced.

## Final implementation note

The pending language above records the original review stage and is superseded by the approved decisions and M4_IMPLEMENTATION.md. Concurrency uses a platform revision counter/If-Match, not a snapshot-derived ETag. Events provide durable polling with consumer-owned cursors; no acknowledgement API or delivery worker is claimed. See M4_RELEASE_AUDIT.md for verification and remaining release gates.
