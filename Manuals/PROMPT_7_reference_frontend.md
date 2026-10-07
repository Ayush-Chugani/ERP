# Prompt 7 - Login and Common Reference frontend

## Implementation

The existing React/TypeScript/Material UI frontend now provides login, logout, session restoration, protected hash routes, and screens for all ten reference resources. Routes are `/#/reference/<resource-path>`, for example `/#/reference/countries` and `/#/reference/sub-castes`. An unknown or unauthorized route displays an access message. Accounts with no model view grants see a clear empty-access state.

The application shell includes responsive reference navigation and the signed-in username. Reference screens are loaded separately from the login shell to reduce initial JavaScript size.

Each resource provides server-side search, pagination, ordering, list/detail access, create and edit forms, and explicitly confirmed deactivate/reactivate controls. There are no hard-delete controls. The field definitions and permissions are centralized in `frontend/src/features/common-reference/resources.ts`; request payloads include only allowlisted fields. Active-state changes use their own explicit PATCH action. IDs, generated values, labels, and effective_active never enter ordinary form payloads.

## Authentication and permissions

The UI reuses the existing `features/auth/session.ts` client, including shared refresh coordination and one bounded authentication retry. It fetches `/auth/me/` to restore the session and after login. Password inputs are cleared after sign-in attempts. Tokens remain in module memory; refresh cookies retain the existing server policy.

Navigation requires each model's view permission. Create/edit/lifecycle controls require the corresponding model add/change permission plus global maintenance permission, or superuser authority. Inactive/all catalogue filters require maintenance authority. Permissions are loaded for the session; the backend checks current permissions on every request and remains authoritative if permissions change while a screen is open. Sign in again to reload changed navigation grants.

An unrecoverable 401 returns the user to login with an expired-session message. A failed server logout clears the local screen and offers a server sign-out retry: it does not falsely claim that the cookie was revoked. Network failures expose a retry message; write failures explicitly warn that the server may already have committed the change, so reload before attempting another write. The UI does not add automatic mutation retries beyond the existing bounded authentication retry.

## Lists, selectors, and forms

- Search is debounced and bounded to 150 characters. Ordering choices use known resource fields and IDs. Pagination supports 10/25/50/100 rows.
- Default lists contain records available for selection. Maintainers can select deactivated or all records. An active record under an inactive ancestor is shown as `Parent unavailable` in the all-records view.
- States filter by country, castes by social category, and sub-castes by caste. Castes also have an explicit uncategorized filter, mutually exclusive with category filtering.
- Parent selectors search available parents in server-paginated batches; Load more exposes further matches. Clearing an optional caste category selects uncategorized.
- The editor fetches the record's current detail before opening. Parent selectors independently fetch the saved parent by ID and retain its label even if excluded from active lists. Unavailable saved parents are marked accordingly. Missing parent read permission or a failed lookup is shown as an error instead of silently changing the stored value.
- Existing historical parents can remain unchanged. New/changed parent selection is validated again by the server. Deactivation never rewrites child references; reactivating a child does not override ancestor availability.
- Optional blank fields become null, parent IDs become numbers, and verification flags remain JSON booleans. Server field errors appear next to text/parent fields; conflicts and other failures appear in alerts.
- Forms use labeled controls, required-field indicators, dialog titles, keyboard-capable Material UI selectors, and horizontally scrollable tables on small screens. Read-only users can open details without editing. Save controls prevent duplicate submissions.
- Closing a dirty form or following a navigation/sign-out control asks before discarding; browser unloading also warns. Browser back/forward hash navigation and session expiration can still discard in-memory edits. Drafts are not persisted.

No service worker, API caching, offline write queue, credential persistence, or new backend endpoints were added.

## Run locally

Use the existing configured backend environment and authorized account. Apply the Prompt 6 migration before reference writes if not already applied.

```powershell
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
```

In a second terminal from the workspace root:

```powershell
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173/`. Use the same hostname throughout; Vite proxies `/api` to Django. Sign in with an existing account and the appropriate reference permissions. No test account, password reset, or demonstration records were created in the working database for this step.

## Verification

- `npm --prefix frontend test`: **8 tests passed**. Covers all ten resource permission/payload contracts, optional/null values, boolean flags, session-expiration signaling, field errors, network uncertainty, and the existing refresh coordination/bounded retry tests.
- `npm --prefix frontend run build`: TypeScript and production build passed. The final build splits reference screens into a separate chunk and emits no oversized-chunk warning.
- The Browser skill was initialized, but browser discovery returned no connected browser. Interactive login, keyboard navigation, mobile layout, and integrated save flows could not be verified in a real browser. The tests above are contract/client tests, not browser component tests.

Recommended browser acceptance run when connected: sign in as a reader and maintainer; inspect all ten routes; create/edit a reference; search and page through parent choices; deactivate a parent and retain its historical selection; verify duplicate and validation errors; reload to restore a session; sign out; repeat on a narrow viewport.
