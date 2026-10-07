# Karnataka reference seeds

Source review: 21 September 2026. Requested scope: Karnataka postal directory and Karnataka education/admission classifications.

## Implemented coverage

Section 1 of `sims_v6_5_1_mariadb_full_schema.sql` and the Django opt-in seed contain India/Karnataka, seven religion labels, seven broad Karnataka social-category labels, and eleven admission-category labels (including General Merit and SC internal A/B/C).

`KA_*` and religion codes are local application identifiers, not government certificate or seat-matrix codes. General Merit belongs only to the admission catalogue. These rows do not assign eligibility, percentages, income limits, caste membership, or religion-to-category relationships. Internal SC labels do not replace the need to record and verify certificate details. The broad SC label does not express internal reservation by itself.

## Run on an existing Django database

From the project root, replace USERNAME with an existing active platform maintainer:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py seed_reference_data --actor USERNAME --karnataka
```

The existing baseline (India, Maharashtra and eight blood groups) also runs. The Karnataka option adds 26 rows on an otherwise unseeded catalogue. Writes use existing permissions and reference audit logging, resolve parent IDs by natural keys, and preserve existing rows and inactive flags. Validation conflicts roll back the batch. `--update` explicitly updates non-key seed fields and does not reactivate rows.

The SQL section is for fresh schema installation; do not rerun the entire CREATE TABLE script against an existing installation. Its insert statements preserve matching codes/names but bypass Django audit logging. No live database seed has been applied as part of this change.

## Official sources

- [KEA UGCET-2026 Bulletin 1, dated 16 January 2026](https://cetonline.karnataka.gov.in/keawebentry456/ugcet2026/information_bulletin_1_ugcet_2026_17012026english.pdf): printed pages 6, 8, 49 and 51 support education category labels, SC internal A/B/C, and certificate requirements. The bulletin refers to the 30 March 2002 and 6 February 2012 orders as amended. This is a dated reference, not a claim that every later amendment has been consolidated.
- [Census C-01 Karnataka, 2011](https://www.censusindia.gov.in/nada/index.php/catalog/11378): principal religious-community labels.
- [Karnataka Directorate of Minorities annual report 2016–17](https://dom.karnataka.gov.in/storage/pdf-files/Reports/AnnualReport2016-17English.pdf): minority-community names including Parsi. Used for names only, not present-day scheme eligibility.
- [Karnataka Backward Classes Welfare caste list](https://bcw.karnataka.gov.in/storage/pdf-files/caste%20list.new.pdf): downloaded and inspected; contains the 30 March 2002 order. Extracted text has spelling/OCR corruption. No individual caste or sub-caste rows were imported from this unverified extraction.
- [India Post circle PIN directories](https://www.indiapost.gov.in/rti/pincodelist): Karnataka is listed, but its linked public download returned HTTP 410 Gone during retrieval. The older `KA_Pincode_12Nov2020.pdf` URL returned HTTP 404. The OGD directory page did not provide a usable data download in this session.

## Remaining work — not yet seeded

Individual caste/sub-caste mappings and the Karnataka postal directory remain incomplete. A verified consolidated caste list (including applicable amendments) and a downloadable official Karnataka postal CSV/XLSX/PDF are required. Do not treat this seed as a complete Karnataka policy or postal database.

The existing reference schema has no postal-directory tables. Once the official dataset is available, add a postal-office model and migration reflecting its actual columns; multiple offices can share a PIN. Preserve source spelling, snapshot date and checksum, validate six-digit PINs, and distinguish postal divisions from civil districts. No postal tables or postal rows have been introduced yet.
