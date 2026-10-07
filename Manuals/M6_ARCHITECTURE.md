# M6 architecture (Prompt 2)

Schema and repeat-admission policy approved by the user; fee policy A: authorized manual clearance reference. Clearance is an attestation, not a payment integration.

`apps.admission_enrolment` owns applicant/application/enrolment/history models, validation, policies, selectors, transactional commands, API, admin and tests. `support.py` contains platform audit, command receipts, manual clearance evidence and durable outbox records. These are separate from the source's four academic entities.

Dependencies: accounts authenticates actors; tenancy owns membership, module enablement and scope; organization supplies programme/campus/department ownership; calendar supplies shared years and semesters; curriculum supplies schemes; reference supplies demographic/category masters; people owns student creation and activation. M6 must use the public people write adapter rather than write student tables directly. Finance, documents and notification delivery are optional integrations, not implicit side effects.

Writes acquire the existing organization governance lock, reload actor authorization, then lock target rows. The lock order matches upstream modules and serializes policy changes with admissions. This conservative design favors correctness over parallel admission throughput; measure before replacing it. API callers provide version preconditions. Expected database errors are translated only after the atomic savepoint has rolled back.

Admission receipt keys are scoped to actor and application. The receipt stores a request digest and resulting enrolment, not a raw applicant payload. Reauthorize retries before returning the prior result; reject key reuse with changed input.

```mermaid
sequenceDiagram
  participant API
  participant Command
  participant DB
  participant People
  API->>Command: admit(application, version, key, payload)
  Command->>DB: begin; governance lock; reload actor; lock application
  Command->>DB: check receipt, selected/eligible, manual clearance
  Command->>People: create or verify student through governed adapter
  Command->>DB: application + enrolment + initial history
  Command->>DB: receipt + audit + outbox
  Command->>DB: commit
  Command-->>API: stable enrolment ID
```

Events use versioned names and identifier-only payloads: `admission.application.transition.v1`, `admission.enrolment.created.v1`, `admission.enrolment.transition.v1`. Consumers deduplicate by event UUID. Dispatch occurs only after commit; a callback can wake a worker but cannot replace durable polling. No email is sent merely by admitting a student.

Frontend uses typed requests and string IDs, memory-only personal-data caches, server capabilities and versions. No offline admission writes. Security and release gates remain pending until their tests and implementation are complete.
