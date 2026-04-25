---
status: complete
phase: 05-structural-router-splits
document: HUMAN-UAT
total_items: 5
completed: 2026-04-23
---

# Phase 05 — Post-Deploy Human UAT Checklist

**Scope:** AUTH-05 — Chrome extension end-to-end auth flow validation post-refactor.
**When:** After Plan 05-04 (auth split) merges to main + staging deploy completes.
**Owner:** Developer with staging credentials + loaded Chrome extension build.
**Environment:** staging.carmodpicker.com (or current staging URL) + Chrome extension loaded from `dist/` via `chrome://extensions` developer mode.

## Checklist

- [x] **Step 1 — Log in on staging web app.** Navigate to the staging URL, log in with a known staging test account. Verify JWT token is stored in localStorage (DevTools → Application → Local Storage → `authToken` present with a non-empty value starting with `ey`).
- [x] **Step 2 — Verify extension popup.** Click the extension icon. Popup shows "Connected as <username>" — the username matches the logged-in staging account. If popup shows "Not connected", step 1 did not propagate; open DevTools on the extension popup and inspect `chrome.storage.local.get('authToken')`.
- [x] **Step 3 — Navigate to a Phase 1 characterized retailer product page.** Pick one of: briantooleyracing.com, amsperformance.com, subispeed.com, texasspeed.com, cobbtuning.com. Navigate to any single-product page.
- [x] **Step 4 — Trigger scrape + verify part creation.** Click the extension's scrape button. Verify: (a) no visible error toast, (b) navigate to your build-list view on the web app — the scraped part appears in the user's build-list workflow, (c) DevTools → Network shows a POST to `/api/parts/` with status 2xx.
- [x] **Step 5 — Log out on web app + verify extension state.** Click Logout on the web app. Open the extension popup again — it should show a disconnected state OR still show cached state. Acceptable per current design: the extension holds a cached token until the next API call hits a 401. Click scrape once more on a product page; the extension should detect the 401 and show a reconnect prompt.

## Pass criteria

All 5 checkbox items pass in one session. If any fails, record the failure mode in this file and halt the phase gate.

## Fail handling

- If step 1 fails → JWT issuance is broken; investigate `/api/auth/token` regression first.
- If step 2 fails → extension popup → web-app message channel broken; investigate `externally_connectable.matches` in `manifest.json`.
- If step 4 fails with 401/403 → per-route auth dependency missing (AUTH-03 regression); rerun `test_auth_auth_coverage.py`.
- If step 4 fails with 500 → backend scrape pipeline broken; check Sentry for stack trace.

## Sign-off

- **Passed by:** Tyler Webb (manual approval)
- **Date:** 2026-04-23
- **Commit on main:** (see git log for 05-* plans)
- **Staging URL:** staging.carmodpicker.com




user manually fully signs off