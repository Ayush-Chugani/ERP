# M27 consultancy / industry-sponsored projects

Implemented in `backend/apps/consultancy` and `frontend/src/features/consultancy`, at `#/consultancy`. Original SQL and DOCX remain unchanged. Runtime defaults off. Local implementation does not imply production deployment or completion of earlier queued modules.

## Confirmed decisions
The user approved the team, milestone, receipt-ledger and status-history extensions described in M27_DESIGN.md. Over-receipts are allowed. Faculty incentive share is a monetary amount, with no assumed cap against receipts or consultancy value. Completion requires a completion date. Closure requires completed status plus authorized confirmation, with no full-payment gate.

Business reference numbers in the core table remain nonunique. No GST, tax, overhead, departmental share, incentive distribution or automatic mandatory-document matrix was invented. Advance receipts are allowed. Administrative closure does not freeze receipts or retained evidence; authorized late payments/corrections remain possible until archival. Closed/cancelled core metadata, team and milestones are read-only.

## Architecture and relationships
ConsultancyProject uses the StaffActivity primary key as its own protected OneToOne key. Parent employee/institution/campus/department come from an active EmployeeAssignment valid on context_date. Principal consultant matches parent employee. ExternalOrganization is the existing global client catalogue; only active clients are accepted. Historical ownership context is immutable.

The core project owns ProjectTeam, ProjectMilestone, ProjectReceipt and ProjectStatusHistory rows. ReceiptVoid has a protected OneToOne relationship to a receipt. Receipt document links reference the existing ActivityAttachment; files remain in M13 storage. No client/employee/file master is duplicated.

Creation and mutation services authorize fresh principals, lock parent rows and commit parent/child/audit/receipt updates atomically. Mutation versions include the latest module audit identifier, parent, child and attachment state; a change-and-revert still invalidates stale versions. Create, status and extension commands accept stable Idempotency-Key values and reauthorize retries. Integrity conflicts/deadlocks become safe 409 responses.

## Core field dictionary
| Column | Native model type | Write policy |
| --- | --- | --- |
| staff_activity_id | bigint unsigned | Service-managed |
| client_organization_id | bigint unsigned | Scoped write |
| principal_consultant_employee_id | bigint unsigned | Service-managed |
| consultancy_title | varchar(500) | Scoped write |
| consultancy_type | enum('CONSULTANCY','INDUSTRY_SPONSORED_PROJECT','TESTING_SERVICE','TRAINING_SERVICE','OTHER') | Scoped write |
| work_order_number | varchar(150) | Scoped write |
| agreement_number | varchar(150) | Scoped write |
| purchase_order_number | varchar(150) | Scoped write |
| project_start_date | date | Scoped write |
| completion_date | date | Scoped write |
| consultancy_amount | numeric(16, 2) | Scoped write |
| amount_received | numeric(16, 2) | Service-managed |
| faculty_incentive_share | numeric(16, 2) | Scoped write |
| currency_code | char(3) | Scoped write |
| deliverables | text | Scoped write |
| status | enum('PROPOSED','APPROVED','ONGOING','COMPLETED','CANCELLED','CLOSED') | Service-managed |
| client_feedback | text | Scoped write |

Core dates and nonnegative monetary rules exist in both the source-native database constraints and service validation. Native enums, DECIMAL(16,2), CHAR(3), unsigned shared PK/FKs, TEXT, nullability and string lengths are retained. Canonical TEXT fields reject values above 65,535 UTF-8 bytes before database writes. Monetary JSON must use exact decimal strings; input exceeding two decimal places is rejected, not silently rounded. Currency uses uppercase three-letter codes and receipt currency must match its project; the implementation does not infer exchange rates.

## Workflow and financial calculations
PROPOSED ? APPROVED ? ONGOING ? COMPLETED ? CLOSED. PROPOSED/APPROVED/ONGOING may become CANCELLED. All transitions require STATUS.UPDATE and a nonblank reason. Source project status describes execution; the parent starts DRAFT and records APPROVED actor/time when approved. No institution-specific approval authority is hardcoded: roles receive reviewed scoped grants.

The receipt ledger is authoritative. Under a parent lock, every receipt/void recomputes amount_received as the sum of nonvoid receipts. Receipts are immutable; void and replace with a new reference for corrections. Reference uniqueness is per project, including voided receipts. Zero receipts are allowed by the approved nonnegative schema; aggregate overflow above core DECIMAL(16,2) capacity is rejected atomically.

`balance_receivable = consultancy_amount - amount_received`, including negative balances for over-collection. `collection_percentage = received / consultancy_amount * 100`, rounded to two decimal places for display only; zero project value returns null, not division-by-zero or an invented percentage. No incentive distribution/payment is performed by storing faculty_incentive_share.

Team membership is unique per project/employee, including inactive rows; reactivate the retained membership. Employee identity is immutable after creation. Co-consultants must belong to the project institution and active members must be active employees. Principal remains authoritative in the core project and is excluded from co-consultants. Membership dates fit known project boundaries.

Milestone sequence is unique per project. Dates fit known project boundaries; completion/acceptance require their dates and acceptance cannot precede completion. Cancel milestones instead of deleting evidence. Progress counts completed/accepted among noncancelled milestones; overdue means a planned milestone with due_date before today. Counts cover all scoped milestones, not just the current page.

## Permission matrix
All permissions have the `CONSULTANCY.` prefix and use existing M15 institution/campus/department/SELF/global scopes with DENY precedence.

| Resource | Actions | Purpose |
| --- | --- | --- |
| ACTIVITY | READ, CREATE, UPDATE, DELETE, EXPORT | Scoped metadata, creation, archive and reports |
| STATUS | UPDATE | Controlled lifecycle transitions |
| FINANCE | READ, UPDATE, DELETE, EXPORT | Monetary fields, receipts, voiding and financial reports |
| TEAM | READ, UPDATE | View/change co-consultants |
| MILESTONE | READ, UPDATE | View/change milestone planning and acceptance |
| DOCUMENT | READ, UPDATE | Private evidence metadata/download and retained uploads |

Creation requires ACTIVITY.CREATE/READ and FINANCE.UPDATE/READ. Financial core edits additionally require FINANCE.UPDATE/READ. Receipt voiding requires FINANCE.DELETE/READ. Team/milestone mutations require their READ and UPDATE permissions. Archive requires ACTIVITY.DELETE/READ and CLOSED/CANCELLED status. Financial report scope is the intersection of ACTIVITY.READ/EXPORT and FINANCE.READ/EXPORT. Financial audit history additionally requires FINANCE.READ.

Nonfinance readers do not receive monetary fields or invoice metadata/downloads. Invoice evidence needs FINANCE.READ in addition to DOCUMENT permissions. M13 confidentiality, institution membership, file-level grants, scanning and content/size rules always apply. No user or role grants were changed by installation.

## API and examples
Versioned base: `/api/v1/consultancy/`. All responses are private/no-store; IDs are strings in read projections. Existing auth/error envelope, throttling and bounded pagination are reused.

- `activities/`: GET list, POST create.
- `activities/{id}/`: GET detail, PATCH metadata, DELETE soft archive.
- `activities/{id}/workflow/`: POST action/remarks/version.
- `activities/{id}/timeline/`: GET paginated status history.
- `activities/{id}/extensions/team|milestones|receipts/`: GET paginated list; POST values/reason/version plus optional item_id and void.
- `activities/{id}/evidence/`: multipart POST; `evidence/{attachment_id}/download/`: private GET.
- `activities/{id}/financial-history/`: paginated actor/time/before/after/reason/correlation audit.
- `activities/summary/` and `activities/export/`: scoped currency-separated summaries and safe CSV.
- `lookups/`: allowed actions and source enums; paginated assignments/clients/years; employees requires project_id and TEAM.UPDATE within parent scope.

Create example (use actual authorized IDs):
```json
{"context":{"employee_assignment_id":"123","context_date":"2026-09-01"},"activity":{"consultancy_title":"Equipment testing","client_organization_id":"45","consultancy_type":"TESTING_SERVICE","project_start_date":"2026-09-01","consultancy_amount":"10000.00","faculty_incentive_share":"1500.00","currency_code":"INR"}}
```
Send `Idempotency-Key: <stable command key>`. Successful detail includes staff_activity, version, readable client/consultant/department labels, allowed actions and permission-dependent financial fields.

Receipt example:
```json
{"values":{"receipt_date":"2026-08-25","amount":"12500.00","currency_code":"INR","reference_number":"BANK-2026-001","invoice_number":"INV-001"},"version":"<current version>","reason":"Payment received"}
```
Void example: `{"item_id":"<receipt ID>","void":true,"values":{},"version":"<current version>","reason":"Duplicate bank entry"}`. Both require their own stable retry key. Metadata PATCH requires activity, version and reason. State transition example: `{"action":"complete","remarks":"Deliverables completed","version":"<current version>"}` after setting completion_date. A stale version returns 409; refresh and review before issuing a new command. Do not change keys blindly after an uncertain network outcome.

Filter by status, consultancy_type, client, principal, institution/campus/department, academic_year, date_from/date_to and mine=1. Search covers title, work order, agreement, PO, client and consultant names. Ordering is allowlisted and deterministic. Reports use project aggregates without receipt joins, so totals are not multiplied. CSV uses the existing formula-injection protection and caps export at 10,000 projects. Grouped summaries are capped at 101 groups per dimension; narrow filters for larger distributions. No unsupported PDF/XLSX export stack was added.

## UI, PWA and documents
Responsive project lists/cards, filter drawer with URL persistence, sectioned forms, status timeline, financial summary, co-consultants, milestones/progress, receipt history/voiding, evidence versions and client feedback use shared React/MUI and authenticated transport. Amounts stay strings. Errors include field/domain messages. Unsaved changes warn on navigation. Offline writes/downloads are disabled; drafts remain only in page memory. Financial/status/destructive requests are not blindly queued. The existing NetworkOnly API/admin worker and shell-update/install behavior are reused.

Evidence categories: proposal, work order, agreement, PO, invoice, completion certificate, client feedback and other. Replacements retain prior links and file objects. Common M13 private storage/content checks handle safe names and traversal defenses. No physical evidence deletion endpoint or unreviewed purge job is introduced; retained historical evidence is protected alongside financial records.

## Migration, performance and rollout
Three migrations install the exact source table, five explicitly approved extension tables and native UPDATE/DELETE rejection triggers for receipt/void/status history. Empty reversal/reinstallation is tested; populated reversal refuses data loss. Inspect M27_SCHEMA_INVENTORY.json for native column/constraint fidelity and M27_QUERY_PLANS.json for seven local EXPLAIN plans. Existing PK/FK/unique indexes are reused. Query-count tests prove list queries do not grow with row count. Production date/status/type index tuning needs real distribution/slow-query evidence; local plans are not a load benchmark.

Back up and verify restore before production DDL. MySQL DDL is nontransactional; inspect partial failures before retry. The source installer refuses collisions with canonical/extension tables. Existing SQL-created deployments require reviewed type/default/collation/FK/check/index comparison and explicit state-adoption migrations, not blind --fake-initial. If imported projects have received totals, reconcile them against actual historical receipts before enabling ledger writes; never fabricate receipt references to force a balance.

Local commands: `backend/.venv/Scripts/python.exe backend/manage.py migrate`; then `... manage.py seed_consultancy`. The seed installs sixteen permissions and activity/workflow configuration only, not grants or client records. Runtime remains `SIMS_CONSULTANCY_ENABLED=0`; the default rate is `SIMS_CONSULTANCY_RATE=120/min`.

Release checklist: staging backup/restore; native migration/adoption review; scoped role grants and independent institutional approval authorities; HTTPS/secure cookies/CSRF/CORS using existing deployment config; private storage and malware scanner; M13 membership/confidentiality setup; database connection health and existing health endpoints; frontend API base URL and static build; real mobile/browser/install/update checks; representative report/load tests; audit retention and operational monitoring. Enable M27 and both M15 security flags only after acceptance. Roll back operationally by disabling M27, retaining financial evidence.

Monitor 400/403/409 rates, lock/deadlock retries, report latency, receipt-total discrepancies, upload scanning/storage failures and audit-write failures. Use correlation IDs; do not log private payloads/files. Archived records retain relational and audit evidence. The institution must set retention schedules, optional mandatory document/approval matrices and any future tax/overhead/distribution policies before those capabilities are added. These optional policies are not guessed by this implementation.

Verification commands/results are recorded in M27_VERIFICATION.json. The existing unrelated M13 storage-key mysql.W003 warning remains. Production restore drills, representative load tests and actual device QA are rollout checks, not claims of completed local testing.
