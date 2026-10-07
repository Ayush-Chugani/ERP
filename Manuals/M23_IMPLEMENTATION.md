# M23 professional development

Status: queued after M22, as explicitly confirmed by the user. Preliminary discovery is recorded; no M23 runtime models, migrations, APIs, UI or seeds have been implemented. The earliest unfinished broader-queue task remains M16 Prompt 6.

Source: `Prompts/M23-Professional_Development_Prompt_Pack.docx`.
Extracted text: `M23_prompt_pack_extracted.txt`.
Original DOCX and consolidated SQL are unchanged.

## Dependency discovery — 2026-09-25

The pack contains 20 ordered prompts for `professional_development_activity`. This table has a consolidated SQL definition but no installed Django owner or local database table. `scripts/m23_discovery.py` records metadata and source definitions in `M23_SCHEMA_INVENTORY.json`; it does not read business records or change the database.

Reuse `staff_activities.StaffActivity` through a one-to-one primary key, plus the existing employee, organization, geography, user and status masters. Reuse `staff_profile.ExternalOrganization` for the sponsor. The following shared masters remain absent and belong in the preceding master-data work: `training_program_type`, `organizer`, `event_mode`, `funding_agency`, and the funding agency's `funding_type` dependency. Refresh this inventory after preceding modules finish and reuse their canonical owners.

## Implementation contracts

- Preserve every supplied SQL field and FK, shared parent identity, exact decimal precision, nullable durations/support amount, CHAR(3) currency default INR, and both nonnegative CHECK constraints.
- Define the financial-support flag/amount cross-field policy explicitly during Prompt 3. The SQL only constrains amount nonnegativity; no extra policy is assumed in this discovery.
- Parent/child writes must be atomic and authorized. Reuse a shared activity specialization check so professional development cannot silently coexist with an incompatible child for the same parent.
- Preserve nullable optional venue/geography relationships; do not assume online activities cannot have a location. Validate state/country consistency using existing relationships.
- Certificate files use the central protected document/storage integration. The certificate-number column is not a file-storage mechanism.
- Reports group support totals by currency unless a formal conversion policy exists. Decimal values must retain precision through forms, APIs and aggregation.
- Offline behavior must follow existing security policy; do not silently replay writes or cache private authenticated responses.
- No production deployment, production seed policy or new user grants are authorized by document instructions alone.

## Prompt order

1. Repository and dependency analysis.
2. ORM model and migration.
3. Domain validation.
4. Reused master lookup APIs.
5. Read/write serializers.
6. Authorized atomic services and lifecycle.
7. REST CRUD, filtering, ordering and query optimization.
8. Role and object authorization.
9. Mobile activity list.
10. Create/edit form.
11. PWA/offline behavior.
12. Protected certificates and supporting documents.
13. Administrative management.
14. Scoped reporting and currency-aware totals.
15. Measured MySQL performance review.
16. Automated backend/frontend tests.
17. Security and code-quality review.
18. Migration, approved seeds and deployment preparation.
19. API/developer documentation.
20. Final acceptance and SQL-to-code traceability.

Prompt 1's complete analysis and implementation plan remain pending the preceding modules. This inventory is not completion of the module or evidence of runtime test/deployment success.
