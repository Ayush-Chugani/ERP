# M5 Prompt 4: disabled foundation

Implemented apps.people_master with AppConfig, baseline lifecycle enums, API limits, conflict/version exceptions, feature permission gate, reserved public/integration boundaries, URL namespace, settings and module registry entry. Selectors/services/filters/admin are explicitly reserved modules, not implemented business features. There are no domain models or personal-data endpoints yet.

The global switch SIMS_PEOPLE_MASTER_ENABLED defaults to 0. The feature gate checks active authenticated users only and is not a substitute for the institution/role/record authorization that must accompany every future endpoint. No UI navigation is advertised until the feature is usable.

Verification: Django checks passed; three foundation tests passed; makemigrations --check --dry-run reported no changes. Source SQL and existing domain migrations were not modified. Read-only live preflight confirmed all fifteen target tables absent.

Continue with Prompt 5 after resolving the ownership and primary-record cardinality questions in M5_PROMPTS_1_3_review.md. Prompts 5–20 remain outstanding; this scaffold is not a completed Student/Staff module.

## Superseded scaffold status

The disabled foundation described above is the historical Prompt4 checkpoint. Subsequent M5 implementation has added domain models/services/APIs/admin/frontend and applied migrations. The global flag now defaults on, with independent institution grants still required. See M5_IMPLEMENTATION.md and M5_RELEASE_AUDIT.md for current status.
