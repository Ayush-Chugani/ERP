# Prompt 5 - Common Reference APIs

Base URL: `/api/v1/reference/`. Routes use trailing slashes and explicit model ID names. Send `Authorization: Bearer <access token>` and JSON for writes. Authentication uses the existing Prompt 4 session flow.

## Endpoint-permission matrix

All permission names below have the `common_reference.` prefix. `M` means `maintain_reference`. Each cell states the complete required permission combination. Active authenticated users are required; superusers pass the permission gates. Staff status and starter group names alone do not grant mutations.

| Resource path | GET collection and /{id}/ | POST collection | PUT/PATCH /{id}/, including is_active | DELETE |
| --- | --- | --- | --- | --- |
| countries | view_country | M + add_country | M + change_country | Disabled |
| states | view_state | M + add_state | M + change_state | Disabled |
| genders | view_gender | M + add_gender | M + change_gender | Disabled |
| blood-groups | view_bloodgroup | M + add_bloodgroup | M + change_bloodgroup | Disabled |
| religions | view_religion | M + add_religion | M + change_religion | Disabled |
| social-categories | view_socialcategory | M + add_socialcategory | M + change_socialcategory | Disabled |
| castes | view_caste | M + add_caste | M + change_caste | Disabled |
| sub-castes | view_subcaste | M + add_subcaste | M + change_subcaste | Disabled |
| admission-categories | view_admissioncategory | M + add_admissioncategory | M + change_admissioncategory | Disabled |
| document-types | view_documenttype | M + add_documenttype | M + change_documenttype | Disabled |

HEAD and OPTIONS require the corresponding view permission. DELETE has no handler and returns 405 for an authorized platform administrator; authentication/permission rejection can precede 405 for other callers. No delete permission enables hard deletion. PUT requires mandatory fields; optional omitted fields retain their values. PATCH updates only supplied fields. Reactivation/deactivation requires an actual JSON boolean (`true`/`false`), not a string, number, or null.

## List visibility and filters

These are global catalogues, with no institution/tenant filtering. `ReferencePermissions` checks action permissions and repeats them on objects. `get_queryset()` independently filters list visibility before search, ordering, pagination, and counts. Object permission checks do not filter a collection.

| Query parameter | Meaning |
| --- | --- |
| search | Substring search across writable text fields; maximum 150 characters; database collation determines case/accent equality |
| ordering | Comma-separated writable fields or primary key; prefix one `-` for descending. No relation traversal. Primary key is appended as a stable tie breaker |
| is_active=true | Default: row and all required ancestors must be active |
| is_active=false | Own flag is false; requires model view permission plus M |
| is_active=all | Any own/ancestor active status; requires model view permission plus M |
| page | Positive integer, default 1; at most ten digits; nonexistent page returns 404 |
| page_size | Positive integer, default 25, capped at 100; at most ten digits |
| country_id | States only: positive ID within unsigned SMALLINT range |
| social_category_id | Castes only: positive ID within unsigned SMALLINT range |
| caste_id | Sub-castes only: positive ID within unsigned INT range |
| uncategorized | Castes only: `true` selects NULL category; `false` selects non-NULL category; cannot combine with social_category_id |

Unknown/repeated parameters and invalid filter/ordering values return 400. Missing parent filter matches return an empty list. A parent's inactive status does not change the child's own flag, so an active child under an inactive parent is omitted by `true`, omitted by `false`, and included by `all`.

## Fields and writable allowlists

Every response includes the resource's explicit primary key, its writable fields, and read-only `effective_active`. Every resource accepts `is_active` in addition to the fields below. No other input fields are accepted, including IDs, generated columns, labels, or effective_active.

| Resource | Writable fields besides is_active | Primary key |
| --- | --- | --- |
| countries | iso_code, country_name | country_id |
| states | country_id, state_code, state_name | state_id |
| genders | gender_code, gender_name | gender_id |
| blood-groups | blood_group_code | blood_group_id |
| religions | religion_code, religion_name | religion_id |
| social-categories | category_code, category_name | social_category_id |
| castes | social_category_id, caste_code, caste_name | caste_id |
| sub-castes | caste_id, sub_caste_code, sub_caste_name | sub_caste_id |
| admission-categories | category_code, category_name, description | admission_category_id |
| document-types | document_code, document_name, requires_verification | document_type_id |

States also return country_label/country_is_active; castes return social_category_label/social_category_is_active (null for uncategorized); sub-castes return caste_label/caste_is_active. `effective_active` includes all ancestors, even when a direct parent's own flag remains true. Related ancestors use select_related to avoid per-row lookups. Parent write IDs must be positive JSON integers in the parent's storage range; only social_category_id permits null.

## Lifecycle and historical selections

Parent deactivation changes only that parent's flag. Existing child FKs and child flags remain unchanged. Dropdowns use the default list and omit unavailable descendants. An authorized GET detail still resolves historical selections, including inactive rows; edit forms should fetch the stored ID separately, retain its label, and mark it unavailable when effective_active is false. This API supports that behavior; frontend screens are outside this step.

New or changed parent assignments must have active ancestors. An unchanged historical FK can be explicitly resubmitted or omitted while editing another field. Explicitly reactivating a child under an inactive ancestor is allowed, but effective_active remains false until its ancestors are active. No cascade or automatic relationship replacement occurs.

## Validation, transactions, and errors

Text is NFC-normalized and trimmed; names collapse whitespace; codes uppercase. Optional blank codes/descriptions become null. Country codes require two ASCII letters. Codes otherwise allow ASCII letters, digits, underscore, hyphen and plus. Lengths retain the model/schema limits. requires_verification also requires a JSON boolean.

Database-backed model validation uses actual MySQL utf8mb4_0900_ai_ci comparisons, rather than Python case folding. Case/accent equivalents conflict within their unique scope, including inactive rows. Database unique constraints remain the final authority; the generated uncategorized caste key enforces NULL-category name uniqueness. Sub-caste codes intentionally are not unique.

API writes execute through write_reference in an atomic block. A shared locked Country content-type row serializes API catalogue writes, including parent deactivation versus child assignment; parent rows are reloaded after acquiring that lock. Direct SQL, bulk ORM, and future alternate writers must adopt the same lifecycle protocol to guarantee inactive-parent rules. Database FK/unique constraints remain effective for those writers, but active-parent rules are application policy.

Expected IntegrityError handling runs outside the rolled-back atomic block: MySQL 1062 maps to 409 duplicate_reference; 1451/1452 and ORM ProtectedError map to 409 protected_reference. Ordinary validation maps to 400 invalid. Unexpected database failures use the existing generic 500 envelope; vendor SQL is never returned. Prompt 6 adds transactional audit recording and shared admin/seed workflows; see PROMPT_6_admin_seed_audit.md for the current write contract.

## Request/response examples

IDs below are illustrative; use IDs returned by your instance.

POST `/api/v1/reference/countries/`:
```json
{"iso_code":" in ","country_name":"India"}
```
201:
```json
{"country_id":1,"iso_code":"IN","country_name":"India","is_active":true,"effective_active":true}
```

POST `/api/v1/reference/states/`:
```json
{"country_id":1,"state_code":"MH","state_name":"Maharashtra"}
```
201:
```json
{"state_id":1,"country_id":1,"state_code":"MH","state_name":"Maharashtra","is_active":true,"effective_active":true,"country_label":"India","country_is_active":true}
```

GET `/api/v1/reference/states/?country_id=1&search=maha&ordering=state_name&page_size=25`:
```json
{"count":1,"next":null,"previous":null,"results":[{"state_id":1,"country_id":1,"state_code":"MH","state_name":"Maharashtra","is_active":true,"effective_active":true,"country_label":"India","country_is_active":true}]}
```

PATCH `/api/v1/reference/countries/1/`:
```json
{"is_active":false}
```
200:
```json
{"country_id":1,"iso_code":"IN","country_name":"India","is_active":false,"effective_active":false}
```
The states dropdown is now empty for that country. GET `/api/v1/reference/states/1/` still returns the state with is_active=true, country_is_active=false and effective_active=false. Reactivate with PATCH `{"is_active":true}`.

GET `/api/v1/reference/castes/?uncategorized=true&ordering=caste_name` selects available uncategorized castes. POST with `{"caste_name":"Example","social_category_id":null}` creates one; parent label/active fields return null.

Duplicate write, 409:
```json
{"error":{"code":"duplicate_reference","message":"A reference with these values already exists.","details":{"detail":"A reference with these values already exists."}}}
```
Invalid is_active, 400:
```json
{"error":{"code":"invalid","message":"Request validation failed.","details":{"is_active":["Use a JSON boolean."]}}}
```

## Verification

28 backend tests passed against the isolated MySQL test database, covering all ten API lifecycles, read/write permission combinations, filters, strict inputs, ancestor visibility, historical edits, collation duplicates and rollback-safe error translation, plus the existing schema/concurrency/authentication tests. OpenAPI generation and validation passed with --validate --fail-on-warn; makemigrations --check --dry-run reported no changes. Tests do not exercise browser edit forms or deployment. No full-schema import or legacy XAMPP mutation was performed.

OpenAPI: `backend/openapi.yaml`; schema endpoint `/api/v1/schema/`, interactive documentation `/api/v1/docs/` (existing admin access policy).

Next step: integrate login and Common Reference frontend screens with historical selection handling and server-returned permissions.

