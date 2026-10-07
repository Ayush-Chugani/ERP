# M7 developer and operator reference

## Entry points and files

API: /api/v1/registration/. React route: /#/registration.
Backend app: backend/apps/term_registration. workflows.py owns setup/allocation/course/roster commands; services.py retains progression and basic term commands. selectors.py applies scopes and effective-date reads. commands.py declares exact serializers and dispatch. execution.py supplies idempotency and atomic batches. integrations.py supplies course eligibility, M8 clash checks and event delivery.

RegistrationPolicy, CommandReceipt, RegistrationEvent and EventDelivery are additive platform tables. Existing identifiers and composite constraints are unchanged. ScopeGrant.record_limits accepts registration-offerings, registration-sections, registration-batches, registration-terms, registration-courses, registration-mappings, registration-registrations, registration-rosters, registration-policies, and registration-audit, alongside upstream programme/student/course/scheme/room limits. Malformed limits never broaden access. Narrow grants cannot read whole-programme audit payloads.

## Commands

Every POST to commands/<operation>/ requires an Idempotency-Key (1–100 characters). Keys belong to an actor, cover the validated payload and return the same result only after reauthorization. Reusing a key for changed input returns 409. Existing records require expected_version. Material actions require a nonblank reason. No generic model write endpoint is exposed.

| Command | Purpose |
| --- | --- |
| configure-policy | Explicit programme minimum/maximum credits, versioned after creation |
| create-offering / transition-offering | Build programme-term offering and advance its lifecycle |
| save-section / save-batch | Create or amend capacity, names, room and activation; ownership/codes stay stable |
| approve-progression | Registrar evidence against current enrolment/offering versions |
| create-draft / transition-term | Draft, reserve, approve, complete or cancel term registration |
| allocate | Explicit class/batch allocation, balanced unallocated assignment, or dated transfer of active rosters |
| correct-roll | Versioned unique roll-number correction |
| create-course / transition-course | Curriculum or explicitly authorized special offerings and lifecycle |
| amend-course-capacity | Change capacity without displacing reservations |
| create-mapping | Map one course to its exact class/batch/session type |
| register-course | Validate course eligibility, window, credits, capacity and published schedule |
| transition-registration | Approve, drop, withdraw or complete course registration; close episodes atomically |
| assign-roster | Start or transfer an approved registration's session membership |

OpenAPI at /api/v1/schema/ describes complete payloads. Use string IDs in TypeScript/CSV to avoid JavaScript precision loss. Server serializers accept positive integer strings.

Offering lifecycle: PLANNED → REGISTRATION_OPEN → ACTIVE → COMPLETED; planned/open offerings can cancel only after unfinished dependencies are resolved.
Course lifecycle: PLANNED → OPEN → ACTIVE → COMPLETED, with guarded cancellation.
Term lifecycle: DRAFT → REGISTERED → APPROVED → COMPLETED; unfinished registrations may cancel after resolving active courses.
Course registration: REGISTERED → APPROVED; registered/approved rows may drop or withdraw; approved rows may complete.

## Reads and import

Paginated resources: offerings, sections, batches, terms, courses, mappings, registrations, rosters, policies, audit. Detail: <resource>/<id>/.
Filters: programme_id, applicable offering_id, and as_of=YYYY-MM-DD for rosters. Intervals are [effective_from, effective_to); closed episodes remain visible historically.

lookups/programmes/ loads scope. Other upstream lookups require programme_id and contain only matching records. mine/ and mine/offerings/ use verified People AccountLink plus active institution membership and module status, never client-supplied student IDs. No applicant contact, address or demographic data is included.

export/<resource>/ requires export permission and caps results at 10,000 rows. Formula-like CSV cells are escaped. reconciliation/ reports over-capacity groups/courses and missing/invalid active rosters.

bulk/ accepts {rows: [{operation, data}], dry_run: true}, at most 100 rows and an 80-character batch key. The complete batch rolls back on failure. Dry-run rolls back receipts, audit and events too. Preview IDs are provisional and must not become dependencies in another row. Apply revalidates current state.

import/parse/ parses a maximum 1 MB CSV with exactly operation,data columns; data is a quoted JSON object using mapped existing IDs. Parsing performs no writes; preview uses bulk/. Import parents in earlier batches, then children using committed IDs. Duplicate/collision rows are rejected for correction, never silently overwritten.

## Authority

| Permission | Scope |
| --- | --- |
| view_registration | Read authorized workspace |
| manage_registration | Setup, allocations and ordinary transitions |
| approve_progression | Registrar progression evidence |
| approve_registration | Approve term/course registrations |
| configure_registration | Programme credit policy |
| authorize_special_course | Noncurriculum course creation, plus manage permission |
| export_registration | Scoped CSV exports |

Non-superusers require active institutional membership, enabled institutional M7, and an institution/campus/department administrator grant. Django permission alone never supplies scope. The established superuser path bypasses institution grants while the global module switch still applies. Admin is inspection-only.

## Eligibility and timetable integration

SIMS_REGISTRATION_ELIGIBILITY_ADAPTER is a trusted dotted Python callable supplied by the result/attempt/prerequisite owner. Signature:

    provider(term_registration=..., course_offering=..., registration_type=...)

It returns {status: "ELIGIBLE", reference: "<durable evidence identifier>"} only after checking applicable prerequisites/grades, previous attempts and the requested registration-type rules. Any other response or an unconfigured provider blocks the command. Audit captures the reference. Never configure the test provider in a deployed environment.

M8 must be enabled for the institution and have a published revision with sessions for candidate mappings. M7 checks actual occurrence times, personal episodes and room capacity. A first timetable can be published for the class cohort before students acquire course memberships; registering a student then checks it. All M7/M8 commands share the governance lock.

M8 stores original student/cohort snapshots immutably. Operational resolution overlays M7 dated membership, so later adds/transfers/drops affect personal schedules and collision checks on their effective dates. Explicit revision-history reads retain original publication membership. M7 does not silently publish or edit schedule revisions.

## Events and reliability

Every audit atomically creates registration.offering.changed.v1, registration.term.changed.v1, registration.course.changed.v1, or registration.roster.changed.v1. Payload contains scoped identifiers, actor and before/after evidence, not contact data. Command logs include actor, operation, request key and dry-run state.

integrations.deliver(consumer, callback, limit=100) records success after callback completion. Local transactional consumers share the transaction; external consumers must deduplicate the event ID because an external side effect cannot roll back. No external callback is configured or invoked here.

Locks serialize capacity, duplicates and transfers. Deadlock/lock-timeout returns 409. Clients refresh stale records and reuse original keys only for unchanged uncertain-outcome retries. No offline mutation queue or API cache is introduced. All M7 responses use private, no-store.

Audit/receipts are application-immutable, not tamper-proof against database administrators. Configure retention, restricted backups and monitoring according to institutional policy; no automatic purge is installed.

Course status changes and class/roster transfers execute on the effective day. Future-dated state changes are rejected so they cannot release reserved seats early. New roster episodes may start later, while their course registration already reserves capacity. Scheduled transition jobs are not supplied.

Credit accounting includes REGISTERED, APPROVED and COMPLETED non-audit courses in the term; completing a course does not create additional credit headroom. Seat occupancy uses only the reserving registration statuses.
