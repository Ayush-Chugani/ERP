# M26 funded research projects ? integration and decisions

## Discovery (prompt 1)
Reuse staff_activities.StaffActivity and its attachment/receipt tables; research_proposals.ResearchProposal; staff_profile FundingAgency/FundingType/ResearchStatus; people_master EmployeeAssignment; organization Department; M15 scoped permissions/audit; M13 private file sharing. React uses the existing authenticated request client and MUI. API traffic is NetworkOnly in the existing PWA worker.

Dependencies: M15 security, M20 staff masters, M25 proposal/master migrations, shared activity migrations and M13 file permissions for evidence. Previous module production activation is not implied.

Files: backend/apps/funded_projects/{models,services,permissions,api,urls,admin}.py; migrations/; management/commands/seed_funded_projects.py; tests/; frontend/src/features/funded-projects/; frontend/tests/projects.test.tsx. Wire settings, versioned URLs and hash navigation.

Schema mismatches: canonical tables have no void flag or explicit status history. Add a platform utilization-void record (one-to-one, retained) and project status history, without editing source SQL. Optional proposal FK is nonunique in source: an explicit unique constraint adopts one project per proposal, including archived projects. Source allows null financial periods; application requires complete reporting periods and financial year. Source requested/sanctioned/received/utilized amounts have identical DECIMAL(16,2) precision.

## Rules (prompt 2)
PI and department derive from an active employee assignment valid on the context date. Context is immutable. Funding agency, organization and type must be active; agency/type must agree. Approved source proposals must match PI/department. Conversion creates a separate activity and copies identity/funding/objectives; sanction order, sanction date, sanctioned amount and project start are separately required. Copying requested amount never implies sanction approval.

Project lifecycle: SANCTIONED -> ONGOING -> COMPLETED -> CLOSED; SANCTIONED or ONGOING -> CANCELLED. Status changes require STATUS.UPDATE; reasons required. Completed/closed require completion date >= start and nonblank outcomes. Parent approval remains APPROVED (recorded funded award); project lifecycle lives in ResearchStatus and retained history, independently of proposal approval. Closed/cancelled projects cannot mutate. No hard deletion: archive only closed/cancelled records.

Dates: end >= start, completion >= start; sanction date <= start; positive duration months when provided (advisory planned duration, not an inferred exact day count). ISO currency code required. All money exact two-decimal strings; nonnegative values. Received <= sanctioned and utilized <= received. Currency cannot change after ledger entries exist.

Finance: nonvoid utilization entries are authoritative; synchronized project totals updated while holding the parent row lock. Periods cannot overlap; financial year uses YYYY-YYYY adjacent years, period contained in those calendar years (institution-specific fiscal start is not assumed). Equation closing = opening + received - expenditure is mandatory. Chronological continuity starts at zero; modifying/voiding an earlier period must preserve all later opening balances or fails atomically. Void retains original record and reason. Closed/cancelled projects reject ledger changes. All adjustments need reason and optimistic version. Separate FINANCE.READ/UPDATE/DELETE and FINANCE.EXPORT permissions; ACTIVITY.READ alone never exposes monetary fields, ledger or financial evidence. Reports intersect READ, EXPORT and finance permissions for monetary output.

Implementation sequence: native models/migrations; atomic project/conversion/lifecycle/ledger services; scoped API and seed configuration; responsive UI; security/concurrency/Decimal tests; migration/query-plan verification and staged rollout documentation. All runtime flags remain off until institutional rollout.

## Currency deployment policy
The default supported ISO currency is INR, inherited from the source schema. Additional institution-approved ISO codes are explicitly configured in SIMS_FUNDED_PROJECTS_CURRENCIES. Three-letter format is validated as well as allowlist membership; the implementation does not add a currency-master dependency.

## Prompt traceability
| Prompt | Implementation evidence |
| --- | --- |
| 1 | This integration/discovery artifact, written before production code |
| 2 | Lifecycle, validation and finance authority decisions above |
| 3 | funded_projects/models.py; canonical column inventory |
| 4 | migrations/0001?0003; refusal/adoption/rollback instructions in handoff |
| 5 | services.save_activity source_id path; unique source constraint and locked conversion tests |
| 6 | services.normalize/apply/save_activity; strict serializers and protected-field tests |
| 7 | services.utilization/reconcile; void retention; exact Decimal/concurrency tests |
| 8 | api.py, urls.py and generated .tmp/m26-openapi.yaml |
| 9 | permissions.py; ten seeded permissions; M15 audit; finance redaction and scope tests |
| 10 | funded-projects/FundedProjectsApp.tsx and FinancePanel.tsx using shared transport/MUI |
| 11 | paginated responsive list, filter drawer, server totals and grouped reports |
| 12 | sectioned create/edit, approved source prefill, outputs and completion fields |
| 13 | detail, ledger controls, reconciliation balances, timeline and financial audit |
| 14 | existing NetworkOnly worker; memory drafts; offline, XSS, IDOR, permission and CSV tests |
| 15 | backend/UI regressions, native/query-plan evidence, handoff and release checks |
