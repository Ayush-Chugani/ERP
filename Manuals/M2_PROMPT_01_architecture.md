# M2 Prompt 1 - Architecture and schema review

## Execution status and authority

Source: M2_SIMS_University_Institution_Structure_ChatGPT_Prompt_Pack.docx, Appendix A. The user requested its prompts in sequence. The pack contains 19 prompts and requires checkpointing and resolving blockers before moving on. This file records the first review, not approval of a nonexistent implementation.

Repository mismatch: the document assumes an implemented authorization extension. accounts.User currently extends AbstractUser without institution memberships, campus/department scopes, module activation or record-access grants. The full reviewed SQL contains IAM designs, but SQL definitions are not an installed Django authorization service. The user has been asked whether to implement that prerequisite here or integrate another existing extension. No schema migration or runtime change is made while that dependency is unresolved.

## Relationships

University 1:N Institution 1:N Campus. Campus 1:N Department 1:N Programme 1:N ProgrammeSpecialization. Campus 1:N Building 1:N Room. University and Campus optionally reference one existing State; State may be referenced by many of either. Institution is the tenant boundary. University is a shared parent, not a tenant membership grant.

## Canonical field specification

Notation: ? means nullable/blank; all other supplied fields are required unless a default is specified. Preserve the Appendix A lengths, table names and key names. Numeric IDs below are auto-increment and unsigned. No replacement State table is created.

| Table | Fields and mapping |
| --- | --- |
| university | university_id SMALLINT -> existing UnsignedAutoField(bits=16); university_code varchar(30), globally unique; university_name varchar(200); legal_name varchar(250)?; university_type choices CENTRAL/STATE/PRIVATE/DEEMED/OTHER default OTHER; website_url varchar(255)?; email varchar(254)?; phone varchar(25)?; address_line_1/address_line_2 varchar(200)?; city varchar(100)?; state_id nullable protected State FK; postal_code varchar(12)?; is_active boolean default true; created_at and updated_at aware timestamps |
| institution | institution_id unsigned SMALLINT; university_id required protected FK; institution_code varchar(20), globally unique; institution_name varchar(200); legal_name varchar(250)?; website_url varchar(255)?; email varchar(254)?; phone varchar(25)?; is_active default true; created_at and updated_at timestamps |
| campus | campus_id unsigned SMALLINT; institution_id required protected FK; campus_code varchar(20); campus_name varchar(150); address_line_1/address_line_2 varchar(200)?; city varchar(100)?; state_id nullable protected State FK; postal_code varchar(12)?; phone varchar(25)?; email varchar(254)?; is_active default true |
| department | department_id unsigned SMALLINT; campus_id required protected FK; department_code varchar(20); department_name varchar(150); department_type varchar(30)?; is_active default true |
| programme | programme_id unsigned SMALLINT; department_id required protected FK; programme_code varchar(30), globally unique; programme_name varchar(150); award_name varchar(150)?; programme_level UG/PG/DIPLOMA/CERTIFICATE/DOCTORAL/OTHER, required; duration_semesters unsigned TINYINT, required; maximum_duration_semesters unsigned TINYINT?; is_active default true |
| programme_specialization | specialization_id unsigned SMALLINT; programme_id required protected FK; specialization_code varchar(30); specialization_name varchar(150); is_active default true |
| building | building_id unsigned SMALLINT; campus_id required protected FK; building_code varchar(20); building_name varchar(100); is_active default true |
| room | room_id unsigned INT -> existing UnsignedAutoField(bits=32); building_id required protected FK; room_code varchar(20); room_name varchar(100)?; room_type CLASSROOM/LAB/SEMINAR_HALL/AUDITORIUM/OFFICE/OTHER, required; capacity unsigned SMALLINT?; is_active default true |

FK Python attributes use university/institution/campus/etc. with explicit db_column ending _id; avoid _id_id. Reuse migration-safe custom unsigned PK field and preserve corresponding FK types. Duration requires a migration-safe unsigned 8-bit scalar field (not the auto-increment class), with storage bounds 0..255 plus a positive-duration constraint. Capacity uses unsigned 16-bit storage and nullable 1..65535 policy.

TextChoices alone is not a database enum constraint: use explicit CHECK membership constraints with varchar storage as a documented Django-managed deviation from native SQL ENUM. Preserve original literals. Native ENUM adoption would require separate verified state/DDL mapping; do not claim an existing ENUM table equals a newly generated varchar table.

Django's standard timestamp storage and service-managed updated_at differ from TIMESTAMP ... ON UPDATE CURRENT_TIMESTAMP in Appendix A. Proposed fresh-install contract uses aware DateTimeFields, creation defaults, and service-managed updates. Every alternate writer must call the service. Existing schema adoption must explicitly reconcile physical types and server defaults; do not fake equivalence.

## Uniqueness decisions

Retain globally unique university_code, institution_code and programme_code. This is the supplied contract and avoids silently changing integration identifiers. Institution-scoped or department-scoped codes may be more flexible for imported institutions but would make code-only lookup ambiguous. Such changes are optional and require a separate data/integration decision.

Retain uq_campus_code(institution_id,campus_code), uq_department_code(campus_id,department_code), uq_specialization_code(programme_id,specialization_code), uq_building_code(campus_id,building_code), and uq_room_code(building_id,room_code). Preserve uq_department_id_campus and uq_specialization_programme: although their leading PK is already unique, downstream composite FKs may depend on these keys. Do not add name uniqueness where the supplied schema has none. Inactive records continue to reserve codes.

Use the existing project's MySQL utf8mb4_0900_ai_ci collation for fresh tables. Names retain spelling and accents; database comparisons, not Python casefold, determine collisions. Canonical code normalization precedes validation, while database constraints remain final defense against concurrency.

## Validation contract

Normalize Unicode to NFC. Trim all text. Uppercase codes, reject internal whitespace, and use the project's ASCII code character allowlist. Do not uppercase names, legal names or address text; preserve meaningful internal whitespace in addresses. Required trimmed-empty strings fail. Optional empty text becomes NULL. Check lengths after normalization.

Email: Django EmailValidator plus 254-character bound, no verification/deliverability claim. URL: http/https only, maximum 255; links are stored, never fetched by the server. Phone: at most 25 characters, optional leading + and digits with spaces/parentheses/hyphens; require a digit, do not assume one nation's numbering plan. Postal code: 12 characters maximum, Unicode letters/digits/spaces/hyphens; no India-only numeric constraint because University/State can be international.

Capacity is null or integer 1..65535; reject booleans and fractional input. Duration is integer 1..255; maximum is null or integer >= duration and <=255. Add corresponding database CHECKs. Strict booleans for API is_active; reject client audit fields and unknown write fields.

## Lifecycle, history and services

All hierarchy and State FKs use PROTECT in the ORM with restrictive database FKs. No public hard-delete endpoint. Deactivation changes only the row's flag; children and historical references remain intact. Selectable descendants require active ancestors. Unchanged historical parents may remain on edits; new assignments require active parents. Reactivation remains explicit.

Generic updates cannot move ownership parents. A separate transactional impact-preview/move flow must inspect dependent records, preserve tenant ownership and hold deterministic locks. Default deny structural moves with historical references, including unknown reverse dependencies. Impact counts must obey the same scope as reads and avoid revealing hidden tenants.

The current ReferenceAuditEvent is intentionally limited to Common Reference resources. Do not pass organization models through its fixed resource allowlist. Add organization audit support as explicit platform infrastructure with actor/action/resource/id/time/bounded changes, and atomic commits with domain writes. Add created_at/updated_at consistently to the six entities missing them; this is an additive fresh-schema correction for list/detail audit metadata, not a silent alteration of legacy tables.

## Index contract

PKs and existing unique keys already support identity/code and most direct-parent filters. A standalone FK index is unnecessary when an existing composite index has that FK as its left prefix. University state, institution university, campus state and programme department require usable FK-leading indexes if not otherwise supplied. Preserve both composite historical keys noted above. Avoid standalone is_active indexes and indexing every text field. Substring search ordinarily cannot use a B-tree efficiently; set page/search limits and measure before adding search infrastructure. Query-count tests must bound hierarchy and list prefetching.

## Migration strategy

Target the existing isolated MySQL development database, not XAMPP or production. Use Django-managed migrations for fresh organization tables. Before Prompt 4 inspect server version/engine/collation and whether any of the eight tables already exist. A preexisting table is a stop-and-compare condition, not evidence permitting --fake-initial.

For adoption: inspectdb/SHOW CREATE TABLE comparison, row/duplicate/orphan checks, backup restore rehearsal and staging migration first. Reconcile enum types, unsigned widths, datetime defaults, indexes and CHECKs explicitly. Preserve existing identifiers. Do not combine full-schema import and Django creation migrations. Reverse RunSQL operations need explicit reverse_sql; destructive initial-migration reversal is for disposable test databases only, not a production rollback strategy. Production rollback requires the documented backup/forward-fix plan.

## Mandatory corrections versus optional changes

Mandatory: existing authorization prerequisite reconciliation; bounded inputs and strict types; explicit enum/duration/capacity CHECKs; protected history; transactional scoped services; scoped list queries before counts/lookups; module activation; complete write auditing; explicit timestamp mapping; reviewed migration/adoption strategy.

Optional and not selected: parent-scoped institution/programme codes, UUIDs, wider IDs, name uniqueness, full-text indexes, cascading deactivation, automatic ownership moves. New membership/scope/activation tables remain a proposed prerequisite pending the user's answer.

## Proposed authorization prerequisite

If the user chooses implementation here: add an explicit platform-support authorization app integrating the reviewed SQL IAM concepts with the current custom User. Institution memberships, scoped role assignments and activation must fail closed. Platform superuser authority is separate from the existing global Admin group. Campus and department roles must be tied to validated parents inside the member's institution; read ancestor breadcrumbs without exposing siblings. Record-level grants must narrow baseline tenant visibility, never bypass membership or activation. Workflow/confidentiality features need a defined organization policy rather than fictitious fields on all eight entities. Do not install the complete legacy IAM SQL or an unrelated full-schema import.

If an external implementation already exists: inspect its code and migrations, expose adapters to its authoritative scope/query interfaces, and avoid duplicate security models.

## Acceptance checklist for Prompt 1

- [x] All eight entities/fields and relationships reviewed against Appendix A.
- [x] Uniqueness choices, lifecycle, validation, indexes and migration alternatives recorded.
- [x] Mandatory versus optional changes separated.
- [x] Repository authorization mismatch identified, not silently assumed solved.
- [ ] Authorization prerequisite chosen by user; implementation contract finalized.
- [ ] Proceed to Prompt 2 only after that prerequisite is resolved, per pack sequencing.

Files changed: this review and the text extraction of the supplied DOCX. Commands: read-only extraction and repository inspection; no migration commands run. Tests added: none (architecture-only step). Manual verification: review the field/authorization contract. Unresolved assumption: source/ownership of the required authorization extension. Status: Prompt 1 review drafted; Prompts 2-19 not executed.

## User decision

The user approved building the missing authorization foundation in this project. The implementation contract above is adopted; membership, activation and scoped role support will be explicit platform infrastructure. Prompts proceed using the existing global authentication client and MySQL conventions.
