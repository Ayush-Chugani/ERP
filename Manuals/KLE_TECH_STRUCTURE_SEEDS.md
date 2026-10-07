# KLE Technological University structure seed

Website reviewed on 21 September 2026. The seed is embedded at the end of Section 2 in `sims_v6_5_1_mariadb_full_schema.sql` and supplied separately as `kle_tech_structure_seed.sql`.

## Coverage

- One university record, classified as PRIVATE.
- One institution record for the university's own operations, with three campus records: Hubballi (B. V. Bhoomaraddi), Belagavi (Dr. M. S. Sheshgiri), and Bengaluru (KLE Law).
- Twelve Hubballi schools/departments and ten Belagavi departments from the respective campus catalogues.
- Nine Hubballi B.E. programmes whose eight-semester durations are explicitly published on the 2026 admissions page.

This is a sourced baseline, not a complete course or premises inventory. Other degrees, Bengaluru department ownership, programme specializations, maximum completion durations, buildings and rooms are not seeded without verified details. Unpublished optional values remain NULL. Campus-specific phone/email values are not copied from the university-wide help desk.

## Mapping decisions

The website describes a university and three campuses. The schema requires an intermediate institution, so the single KLETECH institution is an application representation of university operations; it does not assert that a separate legal entity exists. KLE Society is not inserted as a university.

All identifiers such as KLETECH, HUBBALLI, CSE and KLE_HBL_BE_CSE are local SIMS codes. They are not university-issued department codes or CET/COMEDK identifiers. Schools occupy the department table with type SCHOOL; departments use DEPARTMENT. B.E. CSE (Artificial Intelligence) and B.E. Electronics Engineering (VLSI Design & Technology) are programme rows, matching their presentation as degrees. Their ownership is mapped to the corresponding CSE/ECE school as an application mapping, not a quoted governance rule.

## Sources

- [University overview](https://www.kletech.ac.in/overview): university identity, private-university context and three campuses.
- [University contact page](https://www.kletech.ac.in/contact-us): campus names, addresses and central contact details.
- [Placement contact details](https://www.kletech.ac.in/placements/about-placements): Hubballi PIN 580031.
- [Hubballi campus department catalogue](https://www.kletech.ac.in/hubballi/academic/schools-departemts): twelve school/department names and campus programme listings.
- [Belagavi campus department catalogue](https://www.kletech.ac.in/belagavi/academic/department): ten department names.
- [2026 admissions](https://www.kletech.ac.in/admission2026): nine listed B.E. degrees and their eight-semester durations.

## Use

For a fresh installation, Section 2 seeds run after its tables and the Section 1 India/Karnataka seeds exist.

For an existing raw-SQL installation, select the intended database in your SQL client and run only `kle_tech_structure_seed.sql`, inside a transaction. Do not execute the full schema again. Confirm India (`IN`), Karnataka (`KA`) and the Section 2 tables exist first. This SQL does not pass through Django permissions or audit services and has not been applied to the live application database.

The insert statements resolve IDs through parent codes and preserve existing records, active flags and administrator edits. Repeated serial execution adds no duplicates. If the same name exists under a different code, its insertion is skipped; review the mapping before importing children. Missing parents can also skip descendants. This script does not reconcile an existing institution tree or rename its identifiers. Use one importer at a time.
