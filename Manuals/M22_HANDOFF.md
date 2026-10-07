# M22 implementation and rollout handoff

## Implemented locally

The user's explicit request to implement M22 advanced this module ahead of the remaining queue. The original SQL/DOCX were not changed. Two new migrations installed three shared masters and three conference tables:

- `staff_profile.Organizer`, `EventMode`, `ConferenceContributionType` reuse the existing shared master app.
- `conferences.ConferenceEvent`, `ConferenceActivity`, `ConferenceActivityIndexing` preserve source column names, types, lengths, nullable fields, named constraints, defaults, timestamps and keys.
- ConferenceActivity shares StaffActivity's primary key. Indexing uses Django's composite primary key; no redundant unique index was added.

Migrations pair frozen source SQL with Django state. Existing tables cause an adoption-review failure before creation. Reversal refuses populated tables; MySQL foreign keys remain enabled. Do not use `--fake` to bypass a collision or disable foreign keys for rollback.

The API is under `/api/v1/conferences/`; the PWA is at `#/conferences`. `SIMS_CONFERENCES_ENABLED` defaults to `0`. M15's identity and security flags must also be enabled for operational access. Development implementation is not authorization to enable global security or deploy to production.

## Endpoints and permissions

| Endpoint | Methods | Required business permission |
| --- | --- | --- |
| `events/`, `events/{id}/` | GET | CONFERENCES.EVENT.READ at GLOBAL scope |
| `events/` | POST | CONFERENCES.EVENT.CREATE at GLOBAL scope |
| `events/{id}/` | PATCH | CONFERENCES.EVENT.UPDATE at GLOBAL scope |
| `activities/`, `activities/{id}/` | GET | CONFERENCES.ACTIVITY.READ in the row's scope |
| `activities/` | POST | CONFERENCES.ACTIVITY.CREATE in the derived employee/assignment scope |
| `activities/{id}/` | PATCH | READ and UPDATE, with current version token |
| `activities/{id}/` | DELETE | READ and DELETE, with current version token; soft archive only |
| `activities/{id}/verify/` | POST | READ and VERIFY; independent verifier required |
| `activities/summary/`, `activities/export/` | GET | Intersection of READ and EXPORT row scopes |
| `lookups/`, `lookups/{resource}/` | GET | EVENT.READ for shared masters; ACTIVITY.CREATE for assignment choices |

Run `backend/.venv/Scripts/python.exe backend/manage.py seed_conference_permissions` to install the nine catalogue permissions idempotently. This command preserves existing definitions and grants no roles or user assignments. It was run locally. Assign permissions to appropriate existing roles through the established M15 process, at the intended scopes. A Django superuser flag alone grants no M22 business access.

Event records have no institution column in the source contract, so they are shared masters managed by global permissions. Staff activities use employee institution, a dated employee assignment and its campus/department. SELF resolves through the explicit employee-account link. M15 DENY rules override grants, including ancestor denials. List scoping compiles permission evidence into database filters; it does not authorize each result with an N+1 query loop.

API identifiers are decimal strings on reads, preserving unsigned BIGINT precision in JavaScript. Writes accept validated integer strings. Use backend-provided lookup IDs rather than hard-coded master identifiers. All responses are private/no-store. The existing PWA service worker routes APIs through NetworkOnly.

## Validation and lifecycle

- Event dates are checked in Django and MySQL. State/country mismatches are rejected. Date changes on events with recorded activities require a coordinated correction outside ordinary editing.
- A new activity requires an employee assignment covering the event's full date range and an active CONFERENCE activity type. Parent organization/employee fields are derived, never accepted as arbitrary nested fields.
- Configure active nonterminal `PENDING` rows in VerificationStatus and ApprovalStatus using institution-approved data. The implementation does not invent official catalogue values. Missing configuration fails closed with a validation error.
- The service creates parent, child, claims and audit in one transaction. Edits lock the parent and compare a SHA-256 content version covering parent, child and claims. This avoids relying on second-resolution TIMESTAMP for concurrency. No caller-supplied version means no update/archive.
- Parent title is paper title, else presentation title, else event title. Employee ownership, parent identity and selected event cannot be replaced through update. Journal-publication specialization conflicts are rejected. Terminal parent approvals block ordinary edits. Content edits reset parent verification.
- Optional strings normalize to NULL. DOI input accepts bare identifiers, `doi:` prefixes and doi.org URLs; storage is a lowercase identifier. URL fields allow HTTP/HTTPS and reject embedded credentials. No external URLs are fetched by the server.
- ISBN/ISSN validation is deliberately format-only for legacy compatibility, not registration/checksum verification. Numeric page ranges must be ordered. Award dates require an award name; post-event award dates remain allowed.
- `SIMS_CONFERENCES_CONTRIBUTION_REQUIREMENTS` can configure stable contribution-code requirements as JSON, e.g. `{"APPROVED_LOCAL_CODE":["paper_title"]}`. Allowed requirement fields are paper_title, presentation_title, proceedings_title and publication_type_id. No unapproved contribution-code vocabulary is assumed.
- Data-entry claims are always CLAIMED. Dedicated verification supports CLAIMED → VERIFIED/NOT_INDEXED, VERIFIED → DISCONTINUED, DISCONTINUED/NOT_INDEXED → CLAIMED. Source URL and remarks are required. Neither the activity creator nor the employee's linked user may verify it. Verification records actor/time and status change through M15 audit.
- Verified claim sets cannot be overwritten by ordinary nested edits. Explicit version checks protect edits after concurrent verification.

DOI URL policy references [Crossref display guidance](https://www.crossref.org/display-guidelines); ISSN formatting references the [ISSN International Centre](https://www.issn.org/understanding-the-issn/what-is-an-issn/). Local normalization does not assert publisher registration, indexing or academic validity.

## Example flow

Get an authorized assignment from `lookups/assignments/`, a conference from `lookups/events/` and active activity/contribution types from their lookups. IDs below are placeholders, not seed IDs.

```json
{
  "context": {
    "employee_id": "123",
    "employee_assignment_id": "456",
    "activity_type_id": "7"
  },
  "activity": {
    "conference_event_id": "89",
    "conference_contribution_type_id": "10",
    "paper_title": "Example paper"
  },
  "indexing": []
}
```

POST to `activities/`. GET the returned activity for a version token. PATCH with `{"version":"<current-token>","activity":{"paper_title":"Revised title"}}`. Stale versions and database uniqueness conflicts return 409 without disclosing another employee's record. Protected/unknown fields return 400. Out-of-scope details return 404. Disabled module routes return 404.

## UI, admin, reports and evidence

The PWA includes separate event/activity lists and forms, remote searchable/paginated choices, event dates/geography, all conference-specific content fields, indexing claims, verification controls, soft archive confirmation, search/date/active/indexing filters, pagination and scoped summaries/CSV. Filter state is retained in the route. Draft records are held in component memory only. Offline writes are disabled, unsaved changes prompt before dismissal, and interrupted requests direct users to reload before retrying. Errors display server field details; the server remains authoritative.

Django admin supplies scoped read-only inspection. Mutations use service-backed PWA/API actions so admin cannot bypass ownership, verification or composite-key rules. Django composite-key indexing rows are managed in the module UI/API rather than unsafe admin inline editing.

Summary counts cover contributions, employees, departments, institutions, academic years, publication types, papers, presentations, awards and indexing status. Groups are capped at 100 with truncation indicators. CSV is capped at 10,000 rows, uses the existing spreadsheet-formula escaping helper and audits exports. No XLSX exporter is added. Source/evidence URLs are retained as metadata; this module adds no upload endpoint, storage backend or new access path to private M13 files. A future staff-activity attachment adapter must reuse existing storage and authorization rather than exposing public file links.

## Verification and limits

Backend coverage includes all six new table schemas and FK names; date checks; shared parent identity; DOI uniqueness/rollback; content versions; mass-assignment rejection; ancestor denial and SELF scope; claim duplication/verification; archive audit; API CRUD/filtering; permission revocation; constant list query count; and scoped/formula-safe CSV.

The related suite passed **59 tests and 9 subtests**. Four React tests cover permission-aware creation, safe text rendering, offline persistence/write prevention, form rendering and event submission. The frontend production build and PWA generation passed. Lint, migration-drift and Django checks are recorded in the final verification run. An existing unrelated FileObject unique-key length warning remains in MySQL checks.

`M22_QUERY_PLANS.json` contains three EXPLAIN-only local plans. These are not production-like load benchmarks. No speculative index was added. Real browser viewport QA, institution policy acceptance and representative staging/load evidence remain rollout checks; do not claim them from jsdom or an empty/local database. The module is staged, not production deployed or operationally enabled.

## Rollout checklist

1. Confirm master data, nonterminal PENDING statuses and configured contribution-code policy with the institution.
2. Rehearse migrations and backups on staging; inspect existing-table collisions before adoption. Confirm MySQL supports source CHECK/ENUM/unsigned/composite-key contracts.
3. Install the permission catalogue and explicitly assign existing roles at intended scopes, including global shared-event READ where needed. Rehearse denied/expired/SELF access.
4. Run backend/UI tests, lint, `makemigrations --check --dry-run`, `migrate --check`, schema generation and frontend build.
5. Review realistic EXPLAIN/load results and mobile/keyboard behavior. Verify private no-store responses and interrupted-submit handling.
6. Enable M22 only after the coordinated M15 security rollout is ready. Deploy static assets through the existing PWA cache update process; do not change production flags as part of documentation work.
7. Smoke-test event creation, employee-scoped activity entry, independent verification, export and archive; review audits and errors.
8. Roll back application activation by disabling M22 and restoring compatible assets. Preserve populated tables/history. Do not force reverse populated migrations or restore a database backup without a separately reviewed data-recovery plan.

Final verification: OpenAPI generated without warnings/errors; Django checks, lint and migration-drift checks passed. See M22_VERIFICATION.json for counts and remaining rollout acceptance. Verification actions also require the current content-version token to reject decisions based on stale activity content. Event and assignment rows are locked during creation to prevent concurrent date corrections from invalidating ownership checks.
