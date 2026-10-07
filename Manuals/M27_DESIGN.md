# M27 discovery and proposed extensions

Reuse StaffActivity, EmployeeAssignment, ExternalOrganization, M15 scope/audit, M13 private files, ActivityCommandReceipt, the M26 private-response/optimistic-version patterns and React/MUI authenticated transport. New owner: backend/apps/consultancy; frontend/src/features/consultancy. Core consultancy_project stays exactly as supplied (17 columns, native enums, DECIMAL(16,2), unsigned shared PK).

Sequence: core model/native migration; atomic create/update and lifecycle; scoped APIs; optional approved extensions; private documents; responsive PWA; reports; validation/concurrency/security/full regression; deployment and field/API documentation.

Migration risks: MySQL DDL is nontransactional; refuse existing-table collisions and populated reversal. Explicit extension migrations only. Existing SQL installations require schema comparison and reviewed adoption. No runtime activation, grants, business-master seeding or production deployment is implied.

## Proposed normalized extensions (for review)
All tables use protected project/user/employee FKs, explicit migrations and retained audit history.

- platform_consultancy_team: id BIGINT PK; project FK; employee FK; project_role VARCHAR(80); contribution_description TEXT nullable; start_date DATE; end_date DATE nullable; is_active BOOLEAN default true. One retained membership per (project, employee), reactivated/edited with audit; no incentive allocation. Principal remains authoritative in the core table. Employee must belong to the project institution; membership dates cannot precede project start or exceed completion.
- platform_consultancy_milestone: id BIGINT PK; project FK; sequence positive integer; title VARCHAR(200); description TEXT nullable; due_date DATE; completion_date/acceptance_date DATE nullable; status PLANNED/COMPLETED/ACCEPTED/CANCELLED; client_remarks TEXT nullable. Unique (project, sequence). Acceptance requires completion. Dates must fit known project boundaries. Retain cancelled milestones.
- platform_consultancy_receipt: id BIGINT PK; project FK; receipt_date DATE; amount DECIMAL(16,2) nonnegative; currency CHAR(3); reference_number VARCHAR(150); invoice_number VARCHAR(150) nullable; payment_mode VARCHAR(80) nullable; remarks TEXT nullable; document_attachment FK to existing ActivityAttachment nullable; actor FK; created_at timestamp. Unique (project, reference_number), including voided receipts; currency matches project. Receipt records are immutable; corrections void and replace with a new reference.
- platform_consultancy_receipt_void: receipt OneToOne FK, actor FK, timestamp, reason TEXT. Retained append-only. Core amount_received becomes a transactionally synchronized sum of nonvoid receipts under the project parent lock. No taxes, overhead or revenue allocation assumed.
- platform_consultancy_status_history: project FK, from/to source status codes, actor FK, timestamp and remarks. Retained append-only.

All extension commands require parent scope, separate TEAM/MILESTONE/FINANCE permissions, a current version and retry key. No extension duplicates staff/client masters or file storage. M13 attachments are shared links, never BLOBs or public paths.

## Source-preserving policy defaults
Preserve the source allowance for over-receipts; expose negative receivable balances without policy conclusions. Work order/agreement/PO remain nonunique as supplied. No automatic taxes, deductions, overhead, mandatory-document matrix or incentive distribution. Proposed lifecycle PROPOSED -> APPROVED -> ONGOING -> COMPLETED -> CLOSED, with cancellation before closure; completion requires a date, closure requires completed status and explicit authorized confirmation, not inferred full payment. Institutional approval authorities are supplied through scoped permission grants.

## User decisions confirmed
All proposed extensions approved. Over-receipts allowed; incentive is a monetary amount. Completion needs a date; closure requires authorized confirmation without a payment gate. No tax/overhead/incentive-distribution policy introduced.

Receipt dates are independently validated: advance payments are allowed. Administrative closure does not freeze the ledger or retained evidence; authorized financial/document corrections remain possible until archival. Core metadata, team and milestones are frozen in closed/cancelled states.
