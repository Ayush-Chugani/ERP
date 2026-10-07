# M25 implementation

Prompt 1: canonical ResearchProposal subtype in research_proposals; new FundingAgency/FundingType/ResearchStatus in shared staff_profile ownership. PI and department remain source columns, validated equal to the canonical StaffActivity employee/department derived from a dated assignment. No duplicate authentication or file subsystem. M15 scopes/audit and M13 managed private files are reused.

Prompt 4: optional co-investigators are outside this initial scope; no speculative table. Reference numbers remain nonunique until institution/funder uniqueness policy is confirmed. Shared M15 audit lacks retained workflow rationale, so a protected append-only proposal status timeline is added. Research statuses and shared parent approval codes are kept synchronized; missing/inactive configuration fails closed.

Application implementation and local verification completed. Source SQL/DOCX unchanged. See M25_HANDOFF.md and M25_VERIFICATION.json for operational acceptance limits and exact test outcomes.

Prompt traceability: 1 owner map; 2 canonical native DDL/model; 3 transactional service; 4 optional investigators decision; 5 retained history and native protection; 6 typed serializers/exact money; 7 scoped API; 8 M15 grants; 9 remote masters/assignment/domain choices; 10 responsive table/cards/filter drawer; 11 proposal form/field errors; 12 canonical detail/timeline; 13 M13 private evidence; 14 configurable after-commit adapter; 15 currency-separated reports/CSV; 16 six query plans and constant list-query test; 17 backend tests; 18 frontend/PWA tests; 19 denial/tampering/upload/precision checks; 20 scoped read-only admin; 21 idempotent catalogue seed; 22 validated OpenAPI; 23 rollout/retention plan; 24 full-suite and focused verification; 25 shared subtype invariant and final review fixes.

No production flags, role assignments, external notification delivery or secrets were configured by this implementation.
