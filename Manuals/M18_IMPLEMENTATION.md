# M18 Performance Indexes implementation record

Status: queued after M16 and M17, as requested. Source extraction and read-only discovery are complete; M18 index implementation has not begun. No indexes have been added, renamed or removed for M18, and no query/business/authorization behavior has been changed for M18.

## Sequence and governing source

Source: `Manuals/Prompts/M18-Performance_Indexes_Django_Prompt_Pack.docx`. The original document and consolidated SQL remain unchanged. Extracted text: `M18_prompt_pack_extracted.txt`.

The pack contains Prompt 0 discovery, then Prompts 1-11 for manifest, owning-model metadata, migrations, compatibility, query alignment, tests, benchmarks, privacy review, verification, deployment and observation. Prompt 0 explicitly requires stopping on structural mismatches. The user separately requires completion of preceding modules first. M16 has completed Prompts 1?5 and the models/migrations portion of Prompt 6; M17 has discovery only. Those prerequisites remain implementation work, not an unanswered approval question.

## Current discovery evidence

`scripts/m18_discovery.py` inspects registered model metadata, migration heads and database index metadata. It never reads business row values and never executes index DDL. `M18_DISCOVERY.json` records all 65 uniquely named source entries, physical and Django column mappings where available, existing indexes, exact duplicates, wider leftmost candidates, sensitivity flags and dispositions.

Tested environment: Django 5.2.17, MySQL 8.4.11, existing `accounts.User` custom user model. No M18 runtime app is created. Candidate indexes remain owned by their existing domain apps.

| Preliminary disposition | Count | Meaning |
| --- | ---: | --- |
| ADD | 28 | Mapping exists and no exact duplicate was found; still requires workload/compatibility review. |
| NEEDS_REVIEW | 12 | Existing equivalent columns under another name, or a Django portable name-length issue. |
| BLOCKED | 25 | Required HR/Fees models/tables are not yet implemented. |
| Total | 65 | All requested source entries accounted for. |

This is a discovery inventory, not the completed Prompt 1 manifest or approval to add the 28 candidates. Index purpose, real query traces, measured benefit and deployment risk must still be added after prerequisite modules stabilize. Wider composites are recorded as leftmost candidates rather than automatically declared exact equivalents.

## Review items

| Requested name | Finding |
| --- | --- |
| `idx_term_registration_section` | Exact columns already indexed under another name; decide duplicate versus documented waiver |
| `idx_course_registration_status` | Exact columns already indexed under another name; decide duplicate versus documented waiver |
| `idx_employee_institution_source` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_employee_assignment_location` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_external_agency_institution` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_education_institution_lookup` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_employee_qualification_employee` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_employee_qualification_passing` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_previous_organization_lookup` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_employee_previous_employment_employee` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |
| `idx_file_object_confidentiality` | Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class |

Nine review entries exceed Django's portable 30-character index-name convention while remaining within the target database's 64-character limit. Preserve source names; evaluate a narrowly scoped backend-specific Index subclass when M18 implementation begins. Do not shorten the names silently. Two entries already have exact column coverage under other names; document the duplicate/waiver decision rather than automatically creating another access path.

## Next work in order

1. Finish M16 from Prompt 6: restricted identifier models/services, evidence ownership, file lifecycle, access rules, dual audit, APIs/workflows, seeds, admin and final security tests.
2. Implement M17 Prompts 02-25 after its existing discovery, with transaction/payment/financial safety tests.
3. Refresh this inventory against those completed migrations. Resolve every missing owner/column before M18 model changes.
4. Complete M18 Prompt 1's manifest, then run Prompts 2-9 sequentially. Keep index-only migrations in owning apps and test reversal only in a disposable database; do not reverse the retention-protected M15/HR history migrations.
5. Prepare Prompt 10's deployment plan with actual table sizes/traffic/replication information. Prompt 11 observation requires an actual approved deployment and observation interval; it cannot be represented as already done in local development.

No EXPLAIN benchmark, production deployment or performance improvement is claimed. No production information, passwords, banking identifiers, PAN/Aadhaar values or document keys were collected.

## Reproduce discovery

```powershell
backend/.venv/Scripts/python.exe backend/manage.py shell -c "exec(open('scripts/m18_discovery.py').read())"
```

Inventory refreshed after M16 migrations 0004/0005 on 2026-09-25: bank/PAN/Aadhaar ownership now resolves. The bank employee/status index adds one portable-name review item; no M18 index DDL was executed. Current detailed dispositions are authoritative in M18_DISCOVERY.json.
