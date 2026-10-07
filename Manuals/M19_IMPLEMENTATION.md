# M19 staff profile master data — queued implementation

The authorized order is to finish earlier module prompts, then M19 Prompts 1–10 in order. Current unfinished predecessor: M16 Prompt 6. M17 and M18 implementation must follow M16 before M19 model generation.

## Preliminary discovery (2026-09-25)

Read the supplied `Prompts/M19-SIMS_Staff_Profile_Master_Data_Prompt_Pack.docx` and extracted its text to `M19_prompt_pack_extracted.txt`. Source documents and consolidated SQL were not modified.

`scripts/m19_discovery.py` performs metadata-only discovery. It found exactly one definition for each of the 28 requested tables in `sims_v6_5_1_mariadb_full_schema.sql`. None currently exists in the local database or has an installed Django model owner. The full source definitions, line locations, references and ownership findings are in `M19_SCHEMA_INVENTORY.json`. Re-run discovery after predecessors complete; these findings are not permission to overwrite any subsequently created tables.

The intended app will own these 28 tables. Reuse `common_reference.State`, `common_reference.Country`, `accounts.User`, the established employee model, and M15 permission/audit infrastructure. `role_type` is an activity taxonomy, not a replacement for M15's authorization roles. Verification and approval taxonomies likewise do not replace existing domain workflow state fields.

## Ordered work remaining

1. Complete the repository/column mapping, dependency and migration plan after predecessors are complete. Review existing-table adoption if discovery changes.
2. Implement the 23 reference/taxonomy models against exact source types and constraints.
3. Implement external organizations and the four organization relationship/role tables. Preserve the composite organization-type primary key and nullable unique-key semantics.
4. Implement and verify dependency-ordered migrations, including adoption preflight and reversal behavior.
5. Implement idempotent, dry-run/import-capable seeds using approved data; illustrative values must not become official institutional data.
6. Implement transactional services, normalization, geography validation and lifecycle audit.
7. Implement protected, paginated APIs and contact-data permissions.
8. Implement admin and React/mobile screens and read-only caching.
9. Verify authorization, audit and applicable existing rate limits.
10. Run MySQL constraint/concurrency tests and UI validation; produce the handoff.

Initial discovery implemented no runtime objects. The M21 follow-up below now supplies eleven shared model tables; M19 is still not complete.

## M21 prerequisite follow-up (2026-09-25)

The user subsequently requested resolution of M21 publication models. Eleven required masters are now implemented in staff_profile, and M19_SCHEMA_INVENTORY.json has been refreshed. Reuse those owners; 17 M19 tables and the remaining master-data services/API/UI/seeding prompts remain unimplemented. Earlier absence findings in this document are historical. See M21_IMPLEMENTATION.md for migration and validation evidence.
