# M26 funded research projects

M26 is implemented as `backend/apps/funded_projects` and the `#/funded-projects` React feature. Runtime activation remains off. The original SQL and DOCX were not modified. This explicit module request does not complete earlier queued modules.

## Delivered workflow
Direct award creation and approved-proposal conversion create a new shared staff activity. Conversion preserves the source and permits one project per proposal, including archived projects. Scoped assignment selection derives PI, institution, campus and department. Sanction metadata remains separate from proposal data.

Lifecycle: SANCTIONED ? ONGOING ? COMPLETED ? CLOSED; SANCTIONED/ONGOING may become CANCELLED. Completion requires a completion date and outcomes. Project status uses the shared ResearchStatus catalogue independently of parent approval. Recorded awards have APPROVED parent status; this does not fabricate an internal proposal approval. Parent context remains immutable. Metadata edits require a reason and current version.

Utilization records are authoritative. Active periods must not overlap, opening balances form a continuous sequence beginning at zero, and closing = opening + receipts ? expenditure. Received cannot exceed sanctioned, expenditure cannot exceed receipts. Editing or voiding earlier reports must preserve later continuity. Voiding retains the original record and a protected reason. Project totals synchronize within the same parent-row-locked transaction. Financial corrections retain before/after values in M15 audit history. No financial delete endpoint removes records.

Financial year uses adjacent YYYY-YYYY years containing the reporting period, without assuming an institutional fiscal start date. Planned duration must be positive but is not forced to equal a rounded calendar-month calculation. Supported currency defaults to INR; configure additional institutional ISO codes explicitly with `SIMS_FUNDED_PROJECTS_CURRENCIES=INR,USD,...`. Monetary input and output use exact decimal strings.

## Access and endpoints
All endpoints are under `/api/v1/funded-projects/` and return private/no-store responses. Existing authenticated transport, CSRF/session handling, M15 scope and deny rules apply.

- `activities/`: paginated GET, POST direct/create-from-source (`source_id`). POST requires `Idempotency-Key`.
- `activities/{id}/`: detail GET, PATCH with version/reason, DELETE soft archive of closed/cancelled projects.
- `activities/{id}/workflow/`: POST action/remarks/version plus retry key.
- `activities/{id}/utilization/`: paginated GET; POST create/edit/void command with values, optional utilization_id, void, version, reason and retry key.
- `activities/{id}/timeline/`: paginated retained status history.
- `activities/{id}/financial-history/`: paginated M15 before/after audit, actors, reasons and correlation identifiers, requiring finance read access.
- `activities/{id}/evidence/` and `evidence/{attachment}/download/`: shared M13 upload/download with version retention and private file authorization.
- `activities/summary/`, `activities/export/`: currency-separated, scoped reports and formula-safe CSV. No ledger joins inflate project totals.
- `lookups/` and paginated assignments/funding_agencies/funding_types/statuses/years/proposals/domains; `lookups/proposal-prefill/?source_id=...` requires proposal read and M26 create/finance permissions.

Ten permissions: ACTIVITY READ/CREATE/UPDATE/DELETE/EXPORT, STATUS UPDATE, FINANCE READ/UPDATE/DELETE/EXPORT. All use prefix FUNDED_PROJECTS. Money fields, amount-based filters, financial documents, ledger and audit require FINANCE.READ. Metadata editing does not imply financial editing; status changes use a separate resource. Reporting intersects ACTIVITY.READ/EXPORT and FINANCE.READ/EXPORT. Create requires ACTIVITY.CREATE/READ and FINANCE.UPDATE/READ. Shared evidence upload additionally requires ACTIVITY.UPDATE and FINANCE.UPDATE plus M13 permissions. No roles or users were granted permissions.

The UI includes responsive list/cards, scoped filters, grouped reports, editable outputs/completion, source prefill, timeline, evidence, ledger forms, retained void controls and financial history. Private drafts stay in memory. Offline writes/downloads are disabled; the existing service worker treats APIs as NetworkOnly. Retry keys persist for an unchanged command body within the open page. Version conflicts require refresh and review.

## Migration and staged rollout
Three migrations install the two canonical tables, two explicit platform retention tables, source-proposal uniqueness, date indexes and native append-only triggers. Source FK indexes cover PI, department, funder, type, status and project references. Local development migrations and seed were applied. Every canonical column was compared with the installed database; see M26_SCHEMA_INVENTORY.json. M26_QUERY_PLANS.json records six local EXPLAIN plans, not production performance claims.

Before rollout: back up and verify restore; inventory existing tables, duplicate source conversions, ledger arithmetic and opening-balance continuity; confirm clean migration state and MySQL/MariaDB compatibility on a staging clone. MySQL DDL is nontransactional: investigate any partial failure before retrying. The installer refuses table collisions, including extension tables. Never use blind `--fake-initial`. Existing SQL-installed tables require an explicit source/column/type/default/FK/check/index/collation comparison and reviewed state-adoption migration; imported totals must be reconciled with real period reports before enabling writes. Reverse migrations refuse populated records. Disable runtime for rollback rather than dropping financial evidence.

Run `backend/.venv/Scripts/python.exe backend/manage.py migrate`, then `... manage.py seed_funded_projects`. The seed creates configuration only, preserving existing labels and refusing incompatible status/type configuration. Configure required active organizations/funders/types through their existing owners; no business funders were invented.

Enable only after institutional acceptance: both M15 security flags, `SIMS_FUNDED_PROJECTS_ENABLED=1`, reviewed scope-specific permission grants, and M25 activation for proposal conversion. M13 activation, institution membership, confidentiality grants, private storage and malware scanning are prerequisites for evidence. Production restore drills, browser/device QA, storage/scanner configuration and representative load testing remain release checks, not completed local verification.

Smoke checks: create an award; repeat its key; convert an approved proposal and reject duplicate conversion; verify cross-department denial; read as project-only user and confirm amounts/evidence are absent; submit exact-decimal periods; reject overlap/stale edits; test authorized void/continuity; verify status completion requirements; export by currency; inspect retained audit; disconnect and confirm writes remain disabled.

Monitor validation/conflict/deadlock rates, failed authorization, report latency, upload scanning/storage errors and aggregate reconciliation. Never log private payloads or files. Retain projects, utilization, void records, status history, command receipts and evidence according to institutional research/finance retention policy; no automated hard-delete or purge job was introduced.

## Verification
Exact final commands/results are in M26_VERIFICATION.json. Tests cover Decimal precision, transactions, idempotency, competing finance users, permission separation, disclosure prevention, conversion, native constraints, workflow, retained history, evidence and frontend retry/offline behavior. The existing unrelated M13 storage-key mysql.W003 warning remains.
