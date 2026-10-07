# M3 Prompts 0–1: implementation contract and schema review

Source: M3-Academic_Calendar_Module_Prompt_Pack.docx, Prompts 0–13. The user requested sequential execution. The supplied Section 3 SQL remains the baseline; document instructions proposing schema changes are review questions, not automatic approval to change ownership.

## Contract

Academic Calendar is one internal Django app: apps.academic_calendar. Reuse the custom User, Django permissions, Membership/ScopeGrant and InstitutionModule, shared error envelope, pagination, authenticated frontend transport and static-only PWA. Dependencies point from calendar to platform support and organization; downstream modules consume calendar/public.py. No auth store, microservice, import-time database access or workflow signals.

Layout: apps.py, models.py, enums.py, policies.py, selectors.py, services.py, scheduling.py, public.py, api.py, urls.py, admin.py, migrations/, tests/. Frontend feature: features/academic-calendar. API prefix: /api/v1/calendar/.

## Field mapping (all baseline fields)

| Table | SQL field(s) | Django representation |
| --- | --- | --- |
| academic_year | academic_year_id SMALLINT UNSIGNED AUTO_INCREMENT | existing UnsignedAutoField(bits=16), primary key |
| academic_year | year_code VARCHAR(9) unique | normalized CharField, max_length=9, unique, explicit collation |
| academic_year | start_date, end_date DATE required | DateField |
| academic_year | status ENUM PLANNED/ACTIVE/CLOSED, default PLANNED | CharField/TextChoices with DB CHECK and default |
| academic_term | academic_term_id INT UNSIGNED AUTO_INCREMENT | UnsignedAutoField(bits=32), primary key |
| academic_term | academic_year_id SMALLINT UNSIGNED | ForeignKey AcademicYear, explicit column, PROTECT |
| academic_term | term_code VARCHAR(20), term_name VARCHAR(100) | normalized character fields, explicit lengths |
| academic_term | term_type ODD/EVEN/SUMMER/ANNUAL/OTHER | TextChoices plus DB CHECK |
| academic_term | start_date, end_date | DateField required |
| academic_term | registration_start_date, registration_end_date | nullable/blank DateField |
| academic_term | status PLANNED/REGISTRATION_OPEN/ACTIVE/CLOSED | TextChoices plus DB CHECK, default PLANNED |
| semester | semester_id TINYINT UNSIGNED AUTO_INCREMENT | UnsignedAutoField(bits=8) |
| semester | semester_number TINYINT UNSIGNED unique | existing UnsignedTinyIntegerField, unique, positive validator/check |
| semester | semester_name VARCHAR(50) unique | normalized CharField, explicit collation |
| time_slot | time_slot_id SMALLINT UNSIGNED AUTO_INCREMENT | UnsignedAutoField(bits=16) |
| time_slot | campus_id SMALLINT UNSIGNED | ForeignKey Campus, explicit column, PROTECT |
| time_slot | slot_code VARCHAR(20) | normalized uppercase character field |
| time_slot | start_time, end_time TIME | TimeField, wall-clock only, no overnight intervals |
| time_slot | is_break default false; is_active default true | BooleanField plus database defaults |

Unsigned identifiers are MySQL-specific; SQLite is not an acceptance substitute. Text comparison should use baseline utf8mb4_unicode_ci explicitly, including duplicate validation queries. Existing organization uses a different MySQL collation; foreign keys here are numeric, so that difference does not require unrelated table conversion. ENUM values are represented using CHECK constraints as in the existing app.

## Constraint and invariant matrix

| Rule | Enforcement |
| --- | --- |
| unique year_code | database unique; full_clean collation-aware query; IntegrityError conflict mapping |
| chk_academic_year_dates: end > start | named database CHECK + model clean |
| uq_term_code: year + code | named UniqueConstraint + validation |
| chk_term_dates: end >= start | named CHECK + model validation |
| chk_term_registration_dates: either NULL or end >= start | named CHECK + model validation; keep independently nullable endpoints |
| fk_term_academic_year | database FK, PROTECT; service authorization/parent validation |
| unique semester_number and semester_name | unique database fields and validation |
| chk_semester_number > 0 | named CHECK and validator; storage upper bound 255 |
| uq_time_slot: campus + slot_code | named UniqueConstraint and validation |
| chk_time_slot: end > start | named CHECK and model validation |
| fk_time_slot_campus | database FK + PROTECT; trusted scoped parent validation |
| term/registration endpoints within year | service/model cross-table check; lock year during changes |
| single active year, if selected | serialized service lock; not a cross-row CHECK |
| slot overlap, if selected | half-open interval intersection under shared write lock; adjacent boundaries allowed |
| lifecycle and closed immutability | transition services and permissions; readonly ordinary API status |
| audit together with writes | same transaction, bounded allowlisted snapshots |
| list visibility and object authority | scoped selectors plus policy; never object checks alone |
| disabling a module | deny calendar reads/writes for affected non-platform principals; do not unload app tables |

## Decision log / proposals

1. Ownership (high impact): retain global academic years/terms/semesters and global baseline uniqueness unless user selects institution ownership. Global maintenance is platform-superuser-only; institutional readers need active membership/grant, module enablement and Django view permissions. Time slots are campus-owned. Institution-owned years require a separately approved backfill and uniqueness migration; never infer an institution from existing records.
2. Lifecycle (medium): propose year PLANNED -> ACTIVE -> CLOSED; CLOSED -> PLANNED with reason. Term PLANNED -> REGISTRATION_OPEN -> ACTIVE -> CLOSED (direct PLANNED -> ACTIVE permitted); CLOSED -> PLANNED with reason and nonclosed year. Repeated target state is idempotent. Closing a year requires all its terms closed. No delete endpoint or admin delete.
3. Cardinality (medium): propose one active shared year; overlapping terms allowed because distinct term types/programmes may run concurrently. This is not one active year per institution under global ownership.
4. Containment (medium): propose term dates and each nonnull registration endpoint within the year; registration may precede term start. Updating year bounds must preserve all child ranges. Neither optional registration endpoint is silently made required.
5. Slots (medium): propose no overlapping active non-break slots per campus. Break slots may overlap. Inactive slots do not conflict; activation rechecks. No stored ordering field: order by start_time/end_time/PK.
6. Timezone (high): Campus has no timezone column. Do not invent a campus timezone from an address. Use an explicitly configured campus-ID -> IANA timezone mapping for conversion; missing zone fails closed. Display wall-clock values with a timezone-unconfigured label until mapped. Reject ambiguous or nonexistent local datetimes instead of silently choosing a DST offset.
7. Audit (medium): separate platform support CalendarAudit table, actor, nullable trusted institution for global records, action/resource/ID, bounded before/after, timestamp, correlation and transition reason. No ordinary audit mutation. Application append-only is not DBA-proof protection.

## Risk-ranked gaps

High: ownership decision changes data visibility and migrations; no existing campus timezone; existing tenancy has organization-only activation and needs additive calendar flag; no general workflow engine exists, so explicit Django lifecycle permissions must express authority. Medium: cross-row cardinality/overlap need common locking; future registration dependencies are not yet Django models; use fail-closed integration policy before those modules are enabled. Medium: no connected browser or Linux staging evidence. Low: PostgreSQL/SQLite portability is not claimed.

Prompt 1 made no application code changes. Subsequent prompts must record final decisions, exact verification and any remaining limitations in M3_IMPLEMENTATION.md.

## Decision resolution

The user explicitly approved shared calendars with platform-only maintenance and all proposed initial policies in decisions 1–5 (one active year, containment, non-break overlap prevention and reasoned reopening). The implementation retains those choices. The timezone decision uses explicit campus mapping without a domain-schema change. See M3_IMPLEMENTATION.md and the final evidence in M3_RELEASE_AUDIT.md.
