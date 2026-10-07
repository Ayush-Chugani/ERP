# Prompt 3 ? models and migration handover

## Model mapping

| SQL table | Django model | Explicit PK | Storage |
|---|---|---|---|
| country | Country | country_id | SMALLINT UNSIGNED AUTO_INCREMENT |
| state | State | state_id | SMALLINT UNSIGNED AUTO_INCREMENT |
| gender | Gender | gender_id | TINYINT UNSIGNED AUTO_INCREMENT |
| blood_group | BloodGroup | blood_group_id | TINYINT UNSIGNED AUTO_INCREMENT |
| religion | Religion | religion_id | SMALLINT UNSIGNED AUTO_INCREMENT |
| social_category | SocialCategory | social_category_id | SMALLINT UNSIGNED AUTO_INCREMENT |
| caste | Caste | caste_id | INT UNSIGNED AUTO_INCREMENT |
| sub_caste | SubCaste | sub_caste_id | INT UNSIGNED AUTO_INCREMENT |
| admission_category | AdmissionCategory | admission_category_id | SMALLINT UNSIGNED AUTO_INCREMENT |
| document_type | DocumentType | document_type_id | SMALLINT UNSIGNED AUTO_INCREMENT |

Models: `backend/apps/common_reference/models.py`. Historical field implementations: `backend/apps/core/fields.py`. Migration authority: `backend/apps/common_reference/migrations/0001_initial.py`. Full generated MySQL SQL: `Manuals/common_reference_0001_mysql.sql` (review artifact, not a second installation script). Tests: `backend/apps/common_reference/tests.py`.

## Preserved schema and deliberate differences

All singular names, explicit keys, field lengths, optional NULLs, unique scopes, flags and flag defaults are preserved. `db_default=True` retains flag defaults for direct SQL, as well as Django's Python defaults. Country ISO code remains CHAR(2). ForeignKey attributes country/social_category/caste use explicit country_id/social_category_id/caste_id columns and matching unsigned widths. All three relations use PROTECT; MySQL FKs also reject raw deletes/orphans.

Named unique constraints are retained: uq_state_country_code, uq_state_country_name, uq_caste_name_category, uq_sub_caste. MySQL's unnamed inline unique indexes normally use the column name. Django does not expose a supported FK constraint-name option, so the initial migration uses these generated names:

| Supplied FK name | Generated migration FK name |
|---|---|
| fk_state_country | state_country_id_6b36f831_fk_country_country_id |
| fk_caste_social_category | caste_social_category_id_378dd6e2_fk_social_ca |
| fk_sub_caste_caste | sub_caste_caste_id_bc95f10f_fk_caste_caste_id |

These name changes do not change referential behavior. Future Django schema alterations may regenerate names; adoption must inventory actual constraint metadata. Column physical order differs because an abstract base supplies is_active and Django orders relation fields during creation. Named column access is required; do not use position-dependent INSERTs. No unique constraint was invented for sub_caste_code. No timestamps, institution keys or inactive-only uniqueness were added.

Foreign keys have db_index=False because each is already the leftmost column of an explicit unique index. The migration adds unique indexes before its deferred FKs. Actual SHOW INDEX confirmed no redundant standalone state-country index; tests check all ten tables for unexpected standalone indexes.

## Unsigned field implementation

UnsignedAutoField subclasses AutoField, serializes its bits argument, supplies unsigned db_type and rel_db_type, and explicitly supplies AUTO_INCREMENT. Backend lookup range detection uses PositiveIntegerField semantics so valid keys above 2**31-1 are not incorrectly optimized to empty results. Explicit validation uses 1..2**bits-1, including the full unsigned INT range. MySQL UNSIGNED supplies storage bounds; no redundant CHECK is added. Zero is not used as a sentinel, so raw zero-insertion SQL modes cannot cause a generated-key collision. Keep the custom field import path and behavior available for historical migrations.

ReferenceTextField serializes kind/fixed options, uses CHAR for ISO codes and explicit utf8mb4_0900_ai_ci for text. Inputs are NFC-normalized and trimmed; name whitespace is collapsed, codes uppercased, blank optional codes/descriptions become NULL. Code syntax and lengths are validated after normalization. ReferenceMaster.full_clean normalizes before Django can skip blank fields during validation; save calls it. Preparation also normalizes ordinary literal bulk writes, but QuerySet expressions/raw SQL bypass application validation. External SQL writers must follow the same canonical-value rules. No database trigger is claimed to enforce normalization.

## Nullable caste uniqueness

Keep the original (social_category_id, caste_name) unique index. Add a nullable stored generated VARCHAR(150) column uncategorized_caste_name:

```sql
CASE WHEN social_category_id IS NULL THEN caste_name ELSE NULL END
```

A unique index uq_caste_uncategorized_name covers that column, using the same accent/case-insensitive collation. Categorized rows generate NULL and retain their original per-category scope. Uncategorized rows generate their name and cannot duplicate it, including concurrent direct SQL. Category changes and inactive rows remain constrained. This avoids COALESCE(...,0) and a new positive-ID database CHECK, preserving the category schema more closely. No partial unique index or nulls_distinct flag is used.

Generated columns are read-only. `save()` excludes generated attributes from pre-save validation to avoid stale cached generated values; database constraints enforce final validity. Refresh from the database after writes when the generated value is needed. Future serializers must exclude this internal field from writes.

## Fresh installation and current local instance

Use migrations only. Do not run the full raw schema or the generated SQL artifact alongside migrations. Initial migration preflight rejects MariaDB/SQLite and databases whose default engine/collation differ. Individual text fields declare collation, and the table inherits the verified utf8mb4_0900_ai_ci database default. This is a MySQL-authoritative schema, not an SQLite-portable approximation.

Docker Desktop was started and MySQL 8.4.11 was provisioned on localhost:3307, database sims_reference_dev. Its generated local root password is stored only in ignored `.tmp/mysql-check.env`. Existing XAMPP on 3306 and its sims_v6 database were not modified. This new instance uses a separate generated password, not the XAMPP root password.

From repository root in PowerShell, reuse the already-provisioned instance:

```powershell
docker compose --env-file .tmp/mysql-check.env up -d --wait
$env:SIMS_DB_PASSWORD = (Get-Content .tmp/mysql-check.env -Raw).Trim().Substring(17)
$env:SIMS_DB_NAME = 'sims_reference_dev'
$env:SIMS_DB_HOST = '127.0.0.1'
$env:SIMS_DB_PORT = '3307'
$env:SIMS_DB_USER = 'root'
# Set DJANGO_SECRET_KEY to your own generated secret or configure backend/.env.
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py check --database default
backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
backend/.venv/Scripts/python.exe backend/manage.py test apps.common_reference apps.core --settings=config.settings.test --noinput
backend/.venv/Scripts/python.exe backend/manage.py sqlmigrate common_reference 0001
```

For a different fresh environment, follow README setup and use backend/.env instead. Do not change the initialized Docker volume's password just by changing an env file. Full foundation SQLite migration tests no longer apply once these MySQL-only migrations are present; only the database-free FieldTests can run without MySQL.

## Existing-database adoption ? separate procedure

1. Determine actual server/version, SQL modes, schema encoding/defaults and application writers. Inventory SHOW CREATE TABLE for each table, information_schema.COLUMNS (COLUMN_TYPE, length, NULL/default, EXTRA, collation/generation expression), STATISTICS (column sequence/uniqueness), KEY_COLUMN_USAGE and REFERENTIAL_CONSTRAINTS (all incoming and outgoing FKs). Include incoming links from modules outside this review without claiming to validate their business rules.
2. Take a logical backup including routines/triggers as appropriate and prove restoration to a staging clone. Compare actual DDL against this migration, including unsigned widths, AUTO_INCREMENT, generated fields, unique scopes, default values, engine/collation, and Django migration history. A table-name match is insufficient. Profile null/blank values, oversize codes after uppercase normalization, ID ranges and orphan relations.
3. Check duplicate uncategorized names before adding the index on a MySQL staging copy:

```sql
SELECT caste_name COLLATE utf8mb4_0900_ai_ci AS name_key, COUNT(*)
FROM caste WHERE social_category_id IS NULL
GROUP BY name_key HAVING COUNT(*) > 1;
SELECT social_category_id, caste_name, COUNT(*)
FROM caste WHERE social_category_id IS NOT NULL
GROUP BY social_category_id, caste_name HAVING COUNT(*) > 1;
```

Also run equivalent duplicate checks for every unique name/code scope under the destination collation. Profile the proposed canonical values with the same Python normalization; SQL TRIM alone does not reproduce Unicode NFC and internal-whitespace normalization. Resolve conflicts by an explicitly documented survivor/rename plan, remap every incoming FK, and record audit history. Do not silently delete duplicates, convert collations or normalize production records during initial migration.

4. Reconcile drift on the clone using deployment-specific reviewed migrations, then verify row counts, IDs, references and constraints. Converting MariaDB requires a logical migration into MySQL; utf8mb4_unicode_ci is not equivalent to utf8mb4_0900_ai_ci. Existing auth/platform tables require separate adoption planning.
5. Baseline migration state only after equivalence with the FINAL initial migration, including the generated column/index, is established. A reviewed state-only adoption branch or tightly controlled fake initial can then register existing tables. Django --fake-initial mostly checks table/column existence, not complete types, constraints or data; it may also skip initial RunPython preflight. Never use it as verification. Do not fake the migration and forget its AddConstraint operations.
6. Schedule controlled writes/maintenance during DDL and reconciliation. MySQL DDL cannot be rolled back as one transaction. The migration sets atomic=False. If creation fails midway, inspect actual partial objects before retrying; either reconcile them or restore/recreate an explicitly disposable empty database. Never blanket-drop an existing deployment. Reverse migration drops these tables and their data; it is not a data-preserving production rollback. Restore-tested backups or a reviewed forward fix are required.

## Results and limitations

MySQL 8.4.11: initial migrations applied. Thirteen tests passed: unsigned field serialization/ranges, canonical codes, schema types/collations/defaults/generated storage, concurrent/direct-SQL nullable uniqueness, categorized uniqueness, category-change conflicts, inactive uniqueness, unsigned 3,000,000,000 FK lookup, orphan rejection and protected history, plus foundation regression checks. The provisional empty reference tables from the first implementation attempt were verified empty, reversed and recreated using the corrected initial migration. No deployed migration history was rewritten.

Migration drift: no changes. Django database checks: no issues. Generated SQL was produced by sqlmigrate against the real MySQL connection. These checks do not prove existing-deployment adoption, full domain authorization or frontend behavior. APIs/admin registration, active-parent selection policies, audit writes and seed data belong to later prompts; PROTECT and uniqueness are implemented now.

Sources: [custom fields](https://docs.djangoproject.com/en/5.2/howto/custom-model-fields/), [GeneratedField](https://docs.djangoproject.com/en/5.2/ref/models/fields/#generatedfield), [MySQL generated indexes](https://dev.mysql.com/doc/refman/8.4/en/create-table-secondary-indexes.html), [Django migrations and MySQL limits](https://docs.djangoproject.com/en/5.2/topics/migrations/).

Continuation: Prompt 4 can add authentication and authorization using the custom user, Groups/Permissions, and common_reference.maintain_reference. No institution-scoped role model or future SIMS module has been added.
