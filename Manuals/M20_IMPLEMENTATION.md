# M20 staff profile master data

Status: queued after M19-18, following the user's requested sequence. No M20 application changes or migrations have been applied.

Source: `Prompts/M20-SIMS_Staff_Profile_Master_Data_Prompt_Pack.docx`.
Extracted text: `M20_prompt_pack_extracted.txt`.

The extracted paragraph text exactly matches `M19_prompt_pack_extracted.txt`, including ten prompts, 28 source tables and the internal module-19 heading. M19's preliminary source inventory is recorded in `M19_SCHEMA_INVENTORY.json`; ownership and database state must be refreshed when M20 begins.

Execute all ten prompts in order as a further implementation and verification pass over the existing master-data app. Reuse the M19 models, migrations, services, APIs and UI wherever they already satisfy the requirements; implement and test remaining gaps without duplicating tables or resetting edited reference data. Record each prompt's evidence and outcome at that time.

See `MODULE_EXECUTION_QUEUE.md` for the accepted order and current predecessor status.
