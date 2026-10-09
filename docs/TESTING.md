# Testing

| Layer | Command | What it proves |
|---|---|---|
| Backend unit + API + journeys | `make test-api` | ~1,090 tests against a throw-away PostgreSQL DB (`*_test` only; the suite refuses any other name) |
| Coverage gate | `cd backend && uv run pytest --cov=app` | `fail_under = 98` (currently ≈98 %; demo-data seeders are the least covered code); remaining lines are defensive branches |
| RBAC matrix | `tests/test_resources.py`, `test_admin.py`, `test_journeys.py` | every persona sees only its scope; DENY beats ALLOW; self-service whitelists |
| Schema quality | `tests/test_schema_quality.py` | naming, FKs, indexes, audit columns, RLS on every table |
| API contract | `tests/test_api_contract.py` | OpenAPI operation IDs unique, errors use one envelope |
| Fuzz | `tests/test_fuzz.py` (Hypothesis) | no endpoint returns 5xx for junk paths, params or bodies, as admin / HOD / student |
| Migrations | `tests/test_migrations.py` | upgrade/downgrade round-trip, no model/DB drift |
| Frontend | `make test-web` | component and routing tests (role-based navigation, forms, errors) |
| Load | `make loadtest` | Locust mix of student / admin traffic (`backend/loadtest/locustfile.py`) |

## Load test result (local laptop, 2 uvicorn workers, PostgreSQL in Docker)
12 concurrent users, 60 s: **p50 25 ms, p95 89 ms, ~8 req/s sustained, no server errors**. The only failures were
HTTP 429 from the login rate limiter (working as designed: repeated logins from one IP). Re-run against staging
before launch with realistic user counts and record the numbers here.

Never run two pytest sessions at once; they share the same test database.
