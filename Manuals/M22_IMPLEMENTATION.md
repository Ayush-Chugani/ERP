# M22 conferences, publications and presentations

Status: explicitly advanced by the user and implemented as a staged module: shared prerequisites, source-faithful models/migrations, validation, scoped transactional services/APIs, indexing verification, React/PWA screens, scoped admin inspection and reporting/CSV. Operational activation and staging/production acceptance remain separate. See M22_HANDOFF.md for current behavior, tests and limitations. Earlier discovery statements below are historical.

Source: `Prompts/M22-Conferences_Publications_Presentations_Prompt_Pack.docx`.
Extracted text: `M22_prompt_pack_extracted.txt`.
Original DOCX and consolidated SQL are unchanged. The document's final end-to-end master prompt does not override the user's requested sequence or authorize production deployment.

## Dependency findings — 2026-09-25

The pack contains 18 ordered prompts and inline definitions for `conference_event`, `conference_activity` and `conference_activity_indexing`. All three have source definitions in the consolidated SQL; none currently has an installed Django owner or local database table.

`scripts/m22_discovery.py` records source DDL, dependencies, model owners and table presence in `M22_SCHEMA_INVENTORY.json`. It reads schema metadata only and should be rerun after predecessors finish. This preliminary inventory does not complete Prompt 1's full architecture, field, permission or query planning.

Reuse `staff_activities.StaffActivity` as the shared activity parent. Existing owners also cover external organization, publisher, participation level, publication type, indexing agency, activity/status taxonomies, employee, organizational hierarchy, academic year, geography and custom user. Three prerequisites remain absent: `organizer`, `event_mode`, `conference_contribution_type`. They are among the M19/M20 shared-master requirements and should be implemented in the canonical `staff_profile` app, not duplicated within the conference app.

M21's shared schema exists, but its authorized activity services, specialization invariants and operational workflows remain unfinished. Coordinate M21/M22 service ownership so the same StaffActivity cannot acquire incompatible publication and conference specializations.

## Source contracts and review points

- ConferenceEvent is reusable master data. ConferenceActivity has a one-to-one `staff_activity_id` PK/FK and does not repeat generic employee, organization or activity fields.
- ConferenceActivityIndexing has a physical composite primary key on activity and agency. Reuse Django 5.2 composite-key conventions established in M21. The pack also asks for a composite UniqueConstraint; document that the primary key already supplies this uniqueness rather than adding a redundant database index.
- Preserve native types, lengths, nullability, timestamp behavior, DOI uniqueness and the database event-date check. Add application date validation in the model/service stages.
- The inline SQL omits several constraint names and table engine/collation clauses present in the consolidated schema. Complete a semantic comparison in Prompt 1; retain the consolidated named constraints and target MySQL engine/collation unless a substantive contract conflict is found.
- Contribution-dependent requirements use approved stable lookup codes. Do not invent official master values or use numeric IDs in rules.
- DOI normalization must align with M21. DOI alone cannot establish indexing verification. Separate claimant and verifier authority and retain audit provenance.
- Keep event-master APIs separate from employee activity APIs. Scope querysets, writes, autocomplete, reports and exports on the server.
- Reuse the existing evidence/storage boundary and export infrastructure. Do not introduce public evidence URLs or offline mutation replay without the corresponding security and conflict handling.

## Ordered prompts remaining

1. Dependency analysis, field mapping, permissions and implementation plan.
2. Models and MySQL migrations after the shared masters exist.
3. Scholarly metadata, date, geography and conditional validation.
4. Authorized transactional activity services.
5. List/detail/write serializers and service-backed nested writes.
6. Scoped APIs, filtering, pagination and query optimization.
7. Conference event React/PWA UI.
8. Staff conference activity UI.
9. Indexing claim and verification workflow.
10. Permission-aware Django admin; account for composite-key admin limitations.
11. Measured query/index performance review.
12. Scoped reporting and export.
13. Security, authorization and audit review.
14. Automated backend/frontend integration suite.
15. Offline and interrupted-submit reliability.
16. API documentation and developer handoff.
17. Deployment and migration checklist protecting existing activity data.
18. Final integration and acceptance audit; no completion with unresolved critical/high issues.

Discovery validation confirms 18 prompt numbers, three source tables, an existing canonical StaffActivity owner and the three missing masters above. No runtime test, migration, performance, UI or deployment result is claimed for M22. The broader queue still has unfinished work beginning at M16 Prompt 6; see `MODULE_EXECUTION_QUEUE.md`.


## Current implementation update

All three missing masters and three conference tables are installed locally; M22_SCHEMA_INVENTORY.json now has no missing schema dependencies. The module remains disabled by default and no users/roles were granted access. M22_HANDOFF.md is the current architecture, API, policy, verification and rollout record. M22_QUERY_PLANS.json contains local EXPLAIN-only evidence, not a production benchmark. Earlier queued modules are not marked complete by this explicit M22 follow-up.
