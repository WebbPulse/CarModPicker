# Phase 6 — Human UAT Checklist

Manual verifications required for Phase 6 completion. Each item is gated by a human; no CI substitute is available per VALIDATION.md Manual-Only Verifications.

## 1. Chrome extension smoke test against FastAPI 0.136 (QUAL-06 / D-12b)

**Scope:** Prove the extension still works end-to-end after the FastAPI 0.128 -> 0.136.1 upgrade. FastAPI 0.132 introduced strict Content-Type checking; the vitest grep guard (Plan 06-01) proves extension source already sets `Content-Type: application/json` in the shared `apiRequest` helper, but this manual step confirms real runtime behavior.

**Prerequisites:**
- Local backend running against FastAPI 0.136.1 (`cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`)
- Local docker-compose Postgres up (`cd backend && docker-compose up -d`)
- Chrome extension built: `cd chrome-extension && npm run build`
- Chrome extension loaded unpacked from `chrome-extension/dist` at `chrome://extensions/`

**Steps:**
1. Open the extension popup. Verify it loads without a console error (F12 → Console; inspect the popup).
2. Click "Log in" in the popup. Complete the login flow against the local backend.
3. After login, visit a supported retailer product page (e.g., any page handled by a tier0_http adapter).
4. Trigger the extension's scrape + POST to the backend.
5. Open the extension's background console (chrome://extensions → service worker "Inspect"). Confirm NO 400/415 "Content-Type" errors from the backend.
6. Verify the new part appears in the local backend DB (`psql` or via the frontend `/my-parts` page).

**Expected result:** Login + scrape-and-save flow round-trips successfully. No HTTP 400 or 415 errors in extension logs. No 400 "Content-Type" errors in backend logs (`uvicorn` terminal).

**Sign-off:** _____________________ (date: ____________)

***

## 2. Sentry route-group tag verification in staging (FE-03 / OBS-05)

**Scope:** Confirm that an exception thrown in each of the 4 route groups (admin, authentication, builder, public) produces a Sentry event tagged with the correct `route_group`. Automated test (`App.coverage.test.tsx`) verifies the wrapper structure; this item verifies the downstream Sentry integration under real conditions.

**Prerequisites:**
- Phase 6 deployed to staging (App Runner staging environment).
- Sentry project access for staging.
- A way to trigger a component throw per group (one option: add a temporary `?crash=1` query-param debug toggle to one page per group for the test, then revert; document in PR if used).

**Steps:**
1. Visit staging URL for each group's flagship page:
   - public: `/`
   - authentication: `/login`
   - builder: `/profile` (requires logged-in test user)
   - admin: `/admin` (requires admin test user)
2. Trigger a render-time throw in each (temporary toggle or known broken page).
3. Verify the RouteGroupBoundary fallback UI renders: "Something went wrong in the <group> section" heading + Event ID + Retry / Go Home buttons.
4. Open the Sentry staging project. Confirm 4 distinct events arrived, each tagged `route_group=<name>` matching the group where the throw occurred.
5. Click "Retry" on one fallback; confirm the UI recovers once the trigger is removed.
6. Click "Go Home" on another fallback; confirm navigation to `/`.

**Expected result:** 4 Sentry events with correct `route_group` tag; Retry resets the boundary; Go Home navigates to root.

**Sign-off:** _____________________ (date: ____________)

***

## 3. Terraform QUAL-08 apply confirmation (inherited from Plan 06-01)

**Scope:** Operator confirms the Glacier Deep Archive lifecycle rule landed in AWS state and takes effect on the correct bucket.

**Prerequisites:**
- Plan 06-01 merged (terraform/s3.tf contains `aws_s3_bucket_lifecycle_configuration.crawl_data`).
- AWS SSO credentials for the prod account.

**Steps:**
1. `cd terraform && terraform plan -target=aws_s3_bucket_lifecycle_configuration.crawl_data -no-color`
2. Confirm the plan shows "1 resource to add" (on first apply) or "No changes" (after apply).
3. `terraform apply -target=aws_s3_bucket_lifecycle_configuration.crawl_data`
4. Verify in AWS console: S3 → `carmodpicker-production-crawl-data` → Management → Lifecycle rules → rule `archive-old-snapshots` is Enabled, transitioning to Deep Archive at 90 days.
5. Confirm `carmodpicker-prod-user-images` has NO lifecycle rule (D-19).

**Expected result:** Exactly one lifecycle rule on `carmodpicker-production-crawl-data`; user-images bucket untouched.

**Sign-off:** _____________________ (date: ____________)

***

## 4. Parts-catalog polish visual acceptance (FE-07 — forward reference to Plan 06-06)

Placeholder — will be populated by Plan 06-06. Parts-catalog polish checklist (Card variants, spacing, typography, responsive grid) drafted by the planner, approved here by the operator.

**Sign-off:** _____________________ (date: ____________)

***

## Summary sign-off

All four items signed -> Phase 6 manual gates closed. Record the date of final sign-off in the phase SUMMARY.

Phase 6 manual verification complete: _____________________ (date: ____________)
