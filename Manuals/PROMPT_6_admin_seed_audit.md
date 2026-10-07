# Prompt 6 - Administration, seed data, and audit history

## Delivered scope

All ten Common Reference models are registered in Django admin. API, admin, and seed writes now use `write_reference`, which checks the actor's current active status, global `common_reference.maintain_reference` capability, and the model's add/change permission. The service validates and normalizes model values, rejects new inactive-parent assignments, retains unchanged historical references, and commits the record with its audit event in one transaction.

The new `core.ReferenceAuditEvent` model is platform-support infrastructure, not a table imported from the legacy SIMS schema. Its migration is `backend/apps/core/migrations/0001_initial.py`, with a swappable dependency on the existing user model. Table: `platform_reference_audit`. The migration was applied successfully to the isolated `sims_reference_dev` database at 127.0.0.1:3307.

## Django administration

Visit `/admin/` with an active staff account. Platform superusers have access; other staff need explicit permissions:

| Operation | Required permissions in addition to active staff status |
| --- | --- |
| View a reference catalogue, including inactive rows | common_reference.maintain_reference + model view permission |
| Add a reference | common_reference.maintain_reference + model add permission |
| Edit/deactivate/reactivate | common_reference.maintain_reference + model change permission |
| View audit history | core.view_referenceauditevent |
| Delete references or add/edit/delete audits | Disabled, including for superusers |

API read permissions retain the Prompt 5 policy: ordinary authorized readers can list active references and resolve historical details. The admin catalogue includes inactive entries and therefore requires the maintenance capability to view it. Grant model view permissions alongside add/change permissions for useful admin navigation. Being staff or belonging to the starter Admin group is insufficient for writes. Grant permissions through existing superuser account administration; the seed command never grants them.

Lists display IDs, names/codes, parent IDs, and flags; provide text search, active/parent filters, and deterministic ordering. Reference text is normalized before form length validation. Parent choices show meaningful labels and IDs. New choices include only active parents with active ancestors. Edit forms also retain their stored historical parent, marked `(unavailable)` when necessary. The service independently rechecks parent validity under the shared catalogue lock.

Use each record's `is_active` checkbox to deactivate/reactivate. Parent deactivation never cascades flags or rewrites child FKs. Bulk actions and list editing are disabled: there is no delete-selected or queryset-update shortcut. Expected service conflicts appear as safe admin messages after rollback; the user must reopen/retry the form. Standard form validation errors remain inline.

## Seed baseline and demonstration data

`seed_reference_data` loads this deliberately minimal application baseline:

| Resource | Natural key | Baseline values |
| --- | --- | --- |
| Country | iso_code=IN | India |
| State | country resolved by IN, state_code=MH | Maharashtra |
| Blood groups | blood_group_code | A+, A-, B+, B-, AB+, AB-, O+, O- |

This is a small starting catalogue, not a complete official country/state dataset or a clinical validation system. Country/state IDs are resolved at runtime; no ID is assumed. No caste, sub-caste, religion, admission-category, gender, or social-category classifications are invented or seeded.

Synthetic demonstration data is separately defined as `DEMONSTRATION` in seed_data.py and included only with `--demo`: document code DEMO_DOCUMENT, name Demonstration document, requires_verification=false. Keep `--demo` out of production baseline commands. Running baseline later does not remove previously loaded demo data.

An existing active user must be named with `--actor`. That user needs global maintenance and the relevant model add/change permissions. For repeatable provisioning, grant both add and change for country, state and bloodgroup; demo mode additionally needs documenttype permissions. A dedicated non-login service account may be used if provisioned through the platform's account policy. No actor or user is silently created.

Default behavior preserves every existing natural-key match, including administrator-edited labels and inactive flags. `--update` updates only the explicitly provided non-key defaults. It does not overwrite fields absent from the seed data and never reactivates records. Identical reruns create no audit events. Editing a natural key changes seed identity: a later run may attempt a new row and will stop if another unique value conflicts. Reconcile such key changes deliberately rather than assuming the command can infer renamed identities.

An existing inactive parent may remain on an unchanged historical child. A missing child cannot be created against an inactive parent: seeding stops and rolls back. Parent lookup and uniqueness use the actual database's collation. Invalid data, a missing parent, or insufficient permission aborts the entire batch, including earlier changes and audit entries. The command reports created/updated/unchanged counts and never silently deletes conflicting data.

### Usage (PowerShell, workspace root)

Use the existing isolated MySQL development configuration in backend/.env. Replace `platform-maintainer` with an existing authorized username.

```powershell
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py seed_reference_data --actor platform-maintainer
# Explicitly apply baseline labels to existing natural-key matches:
backend/.venv/Scripts/python.exe backend/manage.py seed_reference_data --actor platform-maintainer --update
# Development/demo use only:
backend/.venv/Scripts/python.exe backend/manage.py seed_reference_data --actor platform-maintainer --demo
```

No baseline has been inserted into the working database on behalf of an arbitrary user. Command execution and repeatability were verified in the isolated test database. No changes were made to the legacy XAMPP database or full-schema SQL files.

## Audit contract

| Field | Meaning and bound |
| --- | --- |
| actor | Required protected FK to the existing user; deletion of an actor with events is blocked |
| action | create, update, deactivate, reactivate; at most 12 characters |
| resource | Singular reference table name, at most 40 characters |
| record_id | Unsigned positive bigint representation of the domain PK |
| timestamp | Automatically recorded timezone-aware creation time; application UTC configuration |
| source | api, admin, seed; at most 8 characters |
| before / after | Only the resource's explicitly allowlisted writable scalar fields plus primary key; strings capped at 500 characters |

Snapshots contain no nested objects, credentials, tokens, request bodies, usernames, or contact details. The only user link is the necessary actor FK. Before is `{}` for create; after contains the normalized persisted values. IDs and flags remain numbers/booleans. Generated columns are excluded. With the fixed ten-resource field allowlists, snapshot size is bounded by their finite field counts and the 500-character string cap.

An update that changes the active flag is classified as deactivate/reactivate even if labels also change; before/after retain all simultaneous changes. No-op writes create no event. Failed writes create no event. If audit insertion fails, the reference change rolls back; errors are not swallowed to allow unaudited success. API, admin and seed writes share the same catalogue lock to serialize parent-state changes and assignments. Django's normal admin log remains in addition to this dedicated history.

Example event (illustrative IDs):

```json
{
  "actor_id": 7,
  "action": "deactivate",
  "resource": "country",
  "record_id": 42,
  "source": "admin",
  "before": {"country_id":42,"iso_code":"IN","country_name":"India","is_active":true},
  "after": {"country_id":42,"iso_code":"IN","country_name":"India","is_active":false}
}
```

Read history at `/admin/core/referenceauditevent/` with `core.view_referenceauditevent`. Search by resource, record ID, or actor ID, and filter by action/resource/source. There is no public audit API and no ordinary audit update/delete interface. Audit model instance update/delete, queryset update/delete/bulk_update, and bulk_create are rejected. New events use insert-only saving to prevent accidental replacement by a reused PK.

**Protection boundary:** this is application-level append-only behavior, not database-administrator-proof tamper protection. Raw SQL, privileged database access, low-level ORM internals, and alternate writers can bypass application safeguards. Direct model/SQL reference writes are not automatically audited; integrations must call the shared service with an authorized actor. This release does not implement database triggers, cryptographic chaining, immutable external storage, retention deletion, or DBA-resistant auditing. Use restricted database credentials and independently governed backups/log storage if stronger protection is required.

## Focused verification

37 backend tests passed against isolated MySQL, including existing authentication, schema, collation and concurrency checks plus:

- Registration of all ten models; admin create/deactivate/reactivate, no hard deletion or delete-selected bypass.
- Admin normalization, inactive-parent rejection, historical parent retention, maintenance gating, and audit read permission.
- API audit actions, actor/source, bounded snapshot allowlists, and no-op suppression.
- Data rollback on failed audit recording from both API service and admin.
- Natural-key parent resolution with a non-default numeric ID, baseline/demo separation, repeat execution, edit preservation and explicit updates without reactivation.
- Seed rejection for unauthorized actors, inactive parents, duplicate values, and late batch validation failures with complete rollback.
- Conventional audit instance/queryset mutation rejection.

`makemigrations --check --dry-run` reported no changes. OpenAPI regeneration with `--validate --fail-on-warn` passed. Django system checks passed. Admin HTML was exercised through Django's test client; no interactive browser or production deployment verification is claimed.

```powershell
backend/.venv/Scripts/python.exe backend/manage.py test apps.common_reference apps.accounts apps.core --settings=config.settings.test --noinput
backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
backend/.venv/Scripts/python.exe backend/manage.py spectacular --file backend/openapi.yaml --validate --fail-on-warn
```

## Reverification after repeated Prompt 6 request

Reviewed all ten admin registrations, the shared permission-checked transactional write service, natural-key baseline/demo seeding, and restricted append-only audit history against the requested requirements. Existing implementation was retained. All 38 backend tests now pass against MySQL, including the authenticated release workflow. Corrected that later workflow test to expect the existing logout contract (204 No Content). Migration drift check reports no changes; core.0001_initial is already applied. No seed data was added to the working database. Browser acceptance remains separate.
