# SIMS Frontend Rebuild — Log & Update Documentation

> Backend untouched (read-only discovery). All changes are under `frontend/`
> except this log. Last verified: `tsc --noEmit` clean, `vite build` clean,
> `npm test` 12/12 pass, targeted vitest (people/organization/calendar/offline) green.
>
> Premium pass: navy/emerald/champagne-gold theme, responsive AppShell
> (sticky gradient AppBar, drawer → mobile drawer, max-width content),
> responsive PageHeader/dashboard/login, gold table-head rules.

## 1. Discovery (read-only)

### Backend contracts (`backend/config/urls.py`, `apps/*/urls.py`, `openapi.yaml`)
- 33 Django apps; 28 routed under `api/v1/` + `admin/`, `core/live`, `core/ready`, `schema/`, `docs/`.
- Prefixes: `evidence/`, `professional-contributions/`, `professional-memberships/`,
  `awards/`, `extracurricular/`, `cocurricular/`, `employee-hr/` (empty `[]`),
  `security/`, `communication/`, `documents/`, `support/`, `feedback/`,
  `assessments/`, `auth/`, `reference/` (10 resources), `organization/` (8 resources),
  `calendar/`, `curriculum/`, `people/` (15 resources), `admissions/`, `attendance/`,
  `registration/` (17 commands), `timetable/` (~14 commands), `consultancy/`,
  `funded-projects/`, `research-proposals/`, `faculty-internships/`, `conferences/`.
- Auth: JWT access (5 min, in-memory) + HttpOnly `sims_refresh` cookie rotation +
  CSRF bootstrap; `IsAuthenticated` default; per-module scoped permissions.
- Pagination `page/page_size`, default 25 / cap 100, PK tie-breaker.
- Error envelope `{"error":{"code","message","details":{}}}`; `404 not_found`,
  `500 internal_error`, `503 not_ready` on readiness.
- `openapi.yaml` covers the 16 mature modules (~405 paths); staff/research modules
  are routed but staged (`*_ENABLED=0`) and absent from the YAML.

### Frontend mess (57 files under `src/`)
- `app/App.tsx` (49 lines, ~14.5 KB, 2 minified lines) held all nav + routing as an
  inline hash ternary; dual routing (shell hash + nested `HashRouter` in
  people/organization + per-feature hash listeners in calendar/curriculum).
- `lib/api.ts` dead stub; real client hidden at `features/common-reference/api.ts`;
  organization diverged via `axios` adapter + `OrganizationError`.
- `components/` empty — `ParentSelect`/`ParentInput`/lookup triplicated,
  `useOnline` triplicated, `ApiError/message` vs `OrganizationError` duality.
- `pwa/PwaStatus.tsx` re-rendered every second (`setInterval 1000`); offline copy
  in-memory only (lost on reload); no `ErrorBoundary`; no 404; no global
  QueryClient (one per feature mount); `AllocationImport` minted a fresh
  `Idempotency-Key` per retry; no admissions UI despite backend `admissions/`.

## 2. New production architecture

```
src/
  lib/
    config.ts        API_BASE, pagination, app constants, envelope guard
    api-client.ts    helpers only (idempotencyKey, allPages, Page) +
                     re-exports of the single session store (no 2nd token store)
    auth-context.tsx AuthProvider (me/login/logout, session-expired event)
    query.ts         shared QueryClient singleton
  app/
    theme.ts         MUI theme (primary #174d43, Inter, radius 10)
    navigation.ts    single nav source (27 items, 5 groups, permission predicates)
    layout.tsx       AppShell (AppBar, responsive drawer, sign-out, PWA, banner)
    router.tsx       single HashRouter routes + RequireAuth + UserRoute injector
    pages/           LoginPage, DashboardPage (module cards + health note), NotFoundPage
    App.tsx          Theme + QueryClient + Auth + HashRouter + AppRouter
  components/
    feedback.tsx     PageHeader, ErrorAlert, EmptyState, Loading
    ErrorBoundary.tsx reload-safe crash boundary with logging
  features/
    common-reference/ReferenceRoutes.tsx  nested /reference/:resource routes
    admission/AdmissionsApp.tsx           NEW: applicants/applications/enrolments/history
    organization/OrganizationApp.tsx      de-nested (standalone-safe router fallback)
    people/PeopleApp.tsx                  de-nested (standalone-safe router fallback)
    ... (22 other features unchanged, mounted via UserRoute where they need `user`)
  pwa/
    offline.ts       persistent (localStorage + memory) 5-min per-user copy
    offlineCopy.ts   backward-compat re-export shim (tests import this path)
    PwaStatus.tsx    expiry-timer (no 1s interval), offline dialog, update/install
```

Routing: one `HashRouter` at `main.tsx` (static-hosting safe). Legacy
`href="#/..."` links keep working; `<Link to="...">` preferred for new code.
`UserRoute` injects `useAuth().user` into the 8 legacy apps typed `({user})`
without touching their internals.

## 3. Changes by file

| File | Change |
|---|---|
| `src/lib/config.ts` | NEW. Central config + envelope guard |
| `src/lib/api-client.ts` | Reworked to helpers + re-exports (single store) |
| `src/lib/auth-context.tsx` | NEW. Single session restore/login/logout |
| `src/lib/query.ts` | NEW. Shared QueryClient |
| `src/lib/api.ts` | Now re-exports canonical `API_BASE` (was dead stub) |
| `src/app/theme.ts` | NEW. Extracted theme |
| `src/app/navigation.ts` | NEW. 27 routes, groups, permission gates |
| `src/app/layout.tsx` | NEW. AppShell (replaces inline shell in old App.tsx) |
| `src/app/router.tsx` | NEW. All routes, guards, lazy features, admissions |
| `src/app/pages/*` | NEW. Login/Dashboard/NotFound |
| `src/app/App.tsx` | Rewritten (9-line providers + router; was 49-line monolith) |
| `src/main.tsx` | Unchanged shape, points at new App |
| `src/components/feedback.tsx` | NEW. Shared page/alert/empty/loading |
| `src/components/ErrorBoundary.tsx` | NEW |
| `src/features/common-reference/api.ts` | Restored byte-for-byte (contract tests) |
| `src/features/common-reference/ReferenceRoutes.tsx` | NEW |
| `src/features/auth/session.ts` | Restored byte-for-byte (contract tests) |
| `src/features/organization/api.ts` | axios removed → fetch + `client.request` compat |
| `src/features/organization/OrganizationApp.tsx` | De-nested router/provider, standalone-safe |
| `src/features/people/api.ts` | Canonical import path (same behaviour) |
| `src/features/people/PeopleApp.tsx` | De-nested router/provider, standalone-safe |
| `src/features/admission/AdmissionsApp.tsx` | NEW. Wired to `/admissions/*` |
| `src/features/timetable/AllocationImport.tsx` | Stable idempotency key per payload |
| `src/pwa/offline.ts` | NEW. Persistent per-user copy |
| `src/pwa/offlineCopy.ts` | Now re-export shim |
| `src/pwa/PwaStatus.tsx` | No interval; expiry timer |
| `index.html` | Title → `SIMS — Student Information Management System` |
| `backend/` | NOT TOUCHED |

## 4. Backend wiring checklist

- [x] `auth/` — login/refresh/logout/me/csrf via session transport + AuthProvider
- [x] `reference/` (10) — ReferencePage + ReferenceRoutes, permission-gated
- [x] `organization/` (8) — Workspace, metadata/list/detail/impact/move/offline-snapshot
- [x] `people/` (15) — metadata/list/detail/save/action, DataGrid server paging
- [x] `curriculum/`, `calendar/` — existing apps mounted (hash-compatible)
- [x] `timetable/`, `registration/`, `attendance/`, `assessments/` — command + idempotency-key pattern preserved, user injected
- [x] `admissions/` — NEW AdmissionsApp (list + search + pagination on all 4 resources)
- [x] `feedback/`, `support/`, `documents/`, `communication/`, `security/` — mounted, user injected where typed
- [x] `evidence/`, `awards/`, `conferences/`, `consultancy/`, `funded-projects/`,
      `research-proposals/`, `faculty-internships/`, `professional-contributions/`,
      `professional-memberships/`, `cocurricular/`, `extracurricular/` — mounted as-is
      (staged backends return governed 404s until `*_ENABLED=1`)
- [x] `core/live`, `core/ready` — referenced on dashboard; PWA NetworkOnly for `/api|/admin`

## 5. Verification loop

1. `npx tsc --noEmit` → clean.
2. `npm run build` → clean (1598 modules, PWA precache 51 entries).
3. `npm test` (node CJS) → 12/12 pass (session + reference + PWA contracts).
4. `npx vitest run tests/people|organization|calendar|offline` → green.
   Full `test:ui` suite is long (>2 min); earlier full run showed pre-existing
   unrelated failures in evidence/contributions/registration MSW handlers
   (unmatched `/registration/mine/*`, `/calendar/metadata` POST, multipart
   expectations) — not caused by this rebuild; feature internals untouched.
   Re-run full suite before release and triage those MSW gaps.
5. Manual (requires Django + MySQL on 3307): `manage.py runserver`, `npm run dev`,
   sign in, walk `/dashboard` → each module, 401-expiry, offline dialog, PWA update.

## 6. Known limits / next loop

- `axios` remains in `package.json` (unused) — remove + `npm install` in a deps pass.
- Full-suite MSW gaps (registration/calendar/evidence/contributions) pre-date this
  rebuild; fix test handlers or feature edge calls next.
- Curriculum/calendar still listen to `location.hash` internally — works under the
  single HashRouter but should migrate to `useLocation`/`useSearchParams` next loop.
- No visual regression run (needs backend + browser); add Playwright smoke next.
