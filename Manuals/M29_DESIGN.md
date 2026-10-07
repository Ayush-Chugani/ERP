# M29 integration and rules (prompts 1-2)

Owner: apps.extracurricular owns extracurricular_activity; apps.staff_profile owns the new canonical ExtraCurricularCategory. Country/State, Organizer and ExternalOrganization remain shared masters. StaffActivity supplies employee assignment, institution/campus/department/year, dates, verification, approval and soft deletion. M15 supplies scoped permissions and audit; M13 supplies private scanned versioned evidence; existing React authentication and NetworkOnly PWA policy remain authoritative.

Source SQL and prompt DOCX remain unchanged. Source table fields and native DDL are preserved. The sole extension is retained status history for timeline and after-commit notification reconciliation, following M25. There is no new approval engine, file store or notification sender.

Required: active category and nonblank event name. All other source fields remain optional. A supplied state requires its active country and must belong to it. All supplied master references must be active at write/submission time; historical inactive labels remain readable. Event date, if supplied, must equal the immutable parent context date selected against the employee assignment; leave it null for an undated draft. Correct context by withdrawing/archiving and recreating. UTF-8 TEXT is bounded to 65,535 bytes. Duplicate event names are allowed (repeated events are legitimate); idempotency prevents retry duplicates. Lists support scoped duplicate review via name/date/employee filters.

DRF rejects unknown/protected fields and malformed scalar values; services enforce scope, dates, active references, exclusivity, workflow and row locking; database enforces canonical lengths, nullability, PK/FKs and retained history. DRAFT/RETURNED permit metadata and evidence edits. Shared independent-review workflow applies. Archive is soft and limited to draft/returned/withdrawn/rejected. Ownership/type/status are never client writable. Reports intersect READ and EXPORT; files additionally require M13 confidentiality permissions.

Permission catalogue has seven ACTIVITY actions and separate MASTER UPDATE for category maintenance; no role grants. Global category maintenance requires explicit global permission. Other masters stay with their existing owners. Notifications use disabled-by-default after-commit adapter with immutable event identifiers and reconciliation history; adapter must deduplicate, resolve authorized recipients and enqueue through shared communications.

Migrations refuse automatic adoption of existing source tables, and refuse populated rollback. Rehearse on a disposable MySQL database; review existing schema before any explicit adoption. Runtime remains disabled pending institutional role grants, file scanner and notification adapter configuration, and device QA.


Validation mapping:

| Data | Enforcement |
| --- | --- |
| Parent PK/type/employee/context | Service-only assignment derivation, M15 scope, exclusive subtype and immutable context; native PK/FKs |
| Category/event name | Serializer required/type/length; service active master and trim/full_clean; native NOT NULL/FK/length |
| Organizer/organization | Serializer optional IDs; service active master and organizer organization; native nullable FKs |
| Event date | Serializer date parsing; service optional equality to immutable parent date; native DATE |
| Venue/city/achievement | Serializer length and null handling; service trim/full_clean; native VARCHAR bounds |
| Country/state | Active paginated lookup and UI dependency/reset; serializer optional IDs; service matching country; native nullable FKs |
| Contribution | Serializer optional text; service trim and UTF-8 byte bound; native TEXT |
| Ownership/status/review | Strict serializer allowlist; service role, version, independent reviewer and shared workflow; row locks |
| History/attachments | Shared services and M15/M13 authorization; immutable history model plus native guards, retained replacement FKs |


M29 discovery additions: source schema is in section 29; ExtraCurricularCategory is absent and belongs to staff_profile. M28 remains unchanged. Add award-presence filter (true/false), free-text search over event/venue/city/award/details, and employee-profile navigation into an employee-filtered activity list. Organizer and institution/organization are independent optional references (organizer versus host); they need not identify the same organization. Trim surrounding whitespace, retain meaningful multiline details. Staff ownership derives from a permitted assignment, never an arbitrary employee ID. Employee deep links remain subject to the same server row scope.

Implementation sequence follows prompts 1-3 discovery/model, 4-8 services/API/security, 9-13 UI/profile/PWA/evidence/reports, 14-15 verification/performance/deployment, 16 final traceability. Prompt 17 consolidates these stages. Local verification budgets: at most 100 list rows/page, no list query growth with row count, 10,000 export rows maximum, 100 summary groups/dimension. Production latency budgets require representative data and infrastructure; no unsupported latency guarantee is asserted.
