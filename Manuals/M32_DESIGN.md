# M32 design and integration (prompts 1?2)

M32 implements academic/professional contributions as an exclusive staff_activity subtype. The source DOCX and consolidated SQL are unchanged. All 17 columns and eight foreign keys are mapped below. Null means unknown/not recorded, including counts; reports retain null sums when no counts were recorded.

## Source data dictionary

| Column | Meaning / constraint |
|---|---|
| staff_activity_id | Required unsigned BIGINT; parent FK and one-to-one primary key |
| professional_contribution_type_id | Required unsigned SMALLINT FK to configurable shared type master |
| organization_id | Optional unsigned BIGINT external organization context |
| journal_id | Optional unsigned BIGINT journal context |
| conference_event_id | Optional unsigned BIGINT conference context |
| programme_id | Optional unsigned SMALLINT programme context |
| course_id | Optional unsigned INT course context |
| student_id | Optional unsigned BIGINT student context |
| title_topic | Optional VARCHAR(500) topic |
| appointment_reference_number | Optional VARCHAR(150) appointment reference |
| contribution_date | Optional DATE for a single contribution |
| start_date, end_date | Optional DATE range; end >= start only when both exist |
| number_of_reviews, number_of_candidates | Optional unsigned SMALLINT counts, 0?65535 |
| contribution_details, outcome_details | Optional native TEXT, at most 65,535 UTF-8 bytes each |

No context exclusivity, duplicate uniqueness, future-date rejection, or mandatory context/type-specific fields are added to source rules. Type policies default to empty; deployment can configure required fields by stable contribution code. The master exactly maps contribution_code(60), contribution_name(180), optional description(500), is_active, and unsigned SMALLINT PK. No hardcoded numeric type IDs.

## Integration and application rules

App: professional_contributions. Shared owners: staff_profile (type/organization), research_publications (journal), conferences (event), organization (programme), curriculum_catalog (course), people_master (student/dated employee assignment), staff_activities (parent/workflow/evidence/idempotency), identity_access (M15 permissions/audit), documents_exit (M13 private files).

Dated employee assignment is mandatory creation context; use explicit context_date or contribution_date/start_date as fallback. Parent date records the authorization context; optional contribution dates remain editable and separate. Ownership/context cannot be reassigned through update. Parent title mirrors topic, falling back to contribution type name. Inactive references are rejected on mutation. Programme/course must belong to the parent institution; lookups use effective M32 institutional/campus/department scopes. Student selection additionally intersects existing People Master read scope, so contribution permission alone cannot enumerate students. Shared organization/journal/conference catalogues have no institution field and expose only active minimal labels to authorized M32 users.

Read/create/update/delete/export/verify/approve follow M15 scope and deny precedence. Parent approval workflow is reused; independent reviewers, optimistic versions, actor-bound idempotency keys, append-only history and M15 audit match preceding modules. Soft archive only, no hard-delete API/admin. Admin contributions are read-only; shared type edits need global MASTER.UPDATE. No roles are automatically granted.

Create: principal -> actor receipt lock -> authorized assignment lock -> type/contexts/policy validation -> parent + subtype + history + audit + receipt in one transaction. Update/workflow: parent lock -> current authorization/version -> normalized child + synchronized parent -> history/audit. Validation/audit failures roll back all changes. Evidence uses existing durable M13 upload transaction. Notifications remain disabled by default and use after-commit adapters only.

## Components and delivery sequence

models/fields + frozen native migrations; policy validator and scoped selectors; services and forms; strict serializers/viewsets/URLs; bounded autocomplete; React/MUI contribution form/list/detail/history/report; tests; schema/query-plan evidence; rollout documentation and release review. React is the established PWA architecture; reusable Django ModelForm supports server-side integrations without introducing a second application UI. Authenticated responses are no-store/NetworkOnly; drafts stay in memory and offline writes are blocked.

Search/list/export are scoped before filtering and use deterministic ordering and select_related. CSV is formula-safe and capped at 10,000 records. Aggregates use SQL SUM/COUNT, explicitly scoped date windows, and no shared user-data cache. Duplicate detection is bounded, scoped, advisory, and never prevents repeated legitimate contributions. No speculative indexes; evaluate existing FK indexes first.

## Acceptance and operational assumptions

Verify exact native schema, nullable combinations, count boundaries/date checks, multi-context writes, foreign institution/student denial, no orphan after rollback, stale edit conflict, retry reauthorization, private evidence, workflow/audit immutability, list query count, report/export safety, migration reversal guards, responsive form/offline behavior, and build/OpenAPI. Runtime remains disabled pending institutional grants, accepted type policy, backup/preflight, and real-device UAT. Production deployment is not performed by this implementation task.
