# Prompt 8 - PWA shell, installation, offline state, and updates

Implemented an installable application manifest, 192/512px PNG icons and a maskable icon, production service-worker registration, an offline screen, and an explicit update prompt. Icons are a simple code-generated S mark. No image generation service was used.

## Cache and security boundary

The generated Workbox worker precaches only public build assets (HTML, hashed JavaScript/CSS, icons and manifest). API and admin navigation are excluded from shell fallback. Matching runtime GET requests use NetworkOnly; other methods and unmatched external requests follow the browser network without a caching handler. There is no background sync, queued mutation, API response cache, credential cache, or offline reference snapshot. No user data needs cache deletion at logout because none is stored by the worker.

The offline dialog blocks interaction and keyboard focus with the online screen while leaving mounted forms in memory. It does not persist drafts: closing/reloading the tab can lose them. Browser online/offline detection indicates connectivity, not backend health; ordinary API errors still handle an unreachable server while the browser reports online.

## Installation and updates

Installation is available over HTTPS or loopback development origins. Supporting browsers expose the Install action via beforeinstallprompt; otherwise use the browser's own installation/Add to Home Screen menu. The app does not promise that every platform shows an automatic install prompt.

New workers wait for activation. The update banner does not reload automatically. Update asks the user to save work in every SIMS tab before activating the new worker and reloading the current tab. Existing editor beforeunload protection also remains. Other open tabs are not forcibly reloaded, so refresh them after saving to use the new build. This is explicit user-coordinated updating, not cross-tab draft storage or automatic draft recovery.

## Run and verify

Service workers are deliberately disabled for `npm run dev`. To test the production PWA with the existing Django backend running on 127.0.0.1:8000:

```powershell
npm --prefix frontend run build
npm --prefix frontend run preview
```

Open `http://127.0.0.1:4173/`. The preview proxy forwards /api to Django. Add `http://127.0.0.1:4173` to the development CSRF trusted origins before testing login there (the implementation includes this origin). Keep hostname usage consistent. Production requires HTTPS and same-origin API routing; deploy the complete dist directory, serve sw.js without long-lived HTTP caching, and use immutable caching only for hashed assets. Hosting configuration/deployment is not performed in this step.

Manual acceptance checklist:

1. Open the production preview online, wait for worker installation, and install using the browser menu or offered button.
2. Open offline after the shell was cached: confirm the offline screen appears and reference/API data are unavailable.
3. Inspect Cache Storage: only public build assets should exist; no /api or /admin responses.
4. Reconnect, log in, edit a reference and go offline. Confirm the form remains in memory and saving is blocked by the offline screen.
5. Build a changed version and reopen/check updates. Confirm a waiting update appears without reloading a dirty form. Save work before accepting the update.
6. Verify logout and API errors with the worker controlling the tab.

## Verification and limits

Ten frontend tests pass, including PWA route exclusions, NetworkOnly policy, prompt registration, actual PNG dimensions, and existing authentication/reference contracts. TypeScript and production worker generation pass. The generated precache has 11 public asset entries. No browser is connected in this session (discovery was empty during Prompt 7), so installation, offline reload, mobile appearance, and multi-tab updates still require the manual browser checks above. No claim of completed interactive PWA acceptance or production deployment is made.
