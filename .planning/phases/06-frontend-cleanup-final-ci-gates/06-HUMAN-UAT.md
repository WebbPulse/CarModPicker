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

**Sign-off:** Tyler Webb (date: 2026-04-23)

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

**Sign-off:** Tyler Webb (date: 2026-04-23)

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

**Sign-off:** Tyler Webb (date: 2026-04-23)

***

## 4. Parts-catalog polish visual acceptance (FE-07 / D-17)

**Scope:** Plan 06-06 applied a bounded visual polish pass to `frontend/src/pages/parts/*` + `frontend/src/components/parts/*`. This item verifies the polish reads correctly in a real browser and no regression occurred.

**Prerequisites:**
- Phase 6 Plans 06-01 through 06-06 merged to staging OR running locally via `npm run dev`.
- Logged-in test user with at least 3 parts saved.

**Steps:**
1. Visit `/parts` (public catalog). Verify:
   - [x] Page title uses `text-3xl` size (matches Home.tsx landing scale; rendered by `PageHeader.tsx`).
   - [x] Responsive layout: filter sidebar collapses to top-of-list on mobile, side-by-side on desktop (`flex-col lg:flex-row`).
   - [x] Part list rows (when card layout active) use rounded-xl corners + shadow-md (matches `Card.tsx` vocabulary).
   - [x] Spacing between list rows is consistent (`space-y-2` outer, `p-4` inner — was `p-3` pre-polish).
   - [x] No visual regression vs. pre-Phase-6 baseline (spot-check 5 random rows).
2. Click into any part -> `/parts/:partId`. Verify:
   - [x] Part detail page renders without layout shift on mobile viewport (DevTools -> Responsive Mode -> iPhone 14 Pro).
   - [x] Body/metadata text is readable (text-sm text-gray-400 for metadata, text-base for description).
   - [x] Image gallery thumbnails maintain consistent rounded-lg corners and 24x24 sizing.
3. Visit `/my-parts`. Verify:
   - [x] User's parts render with the same list pattern as PartsCatalog.
   - [x] Create / Edit / Delete affordances are clearly identifiable on each row.
   - [x] "Browse All Parts" outline button (top-right) renders with consistent btn-outline styling.
4. Click "Edit" on one part -> `/parts/:partId/edit`. Verify:
   - [x] Form fields use consistent spacing (`space-y-4` between fields; no visual squeeze).
   - [x] Primary submit button is `ActionButton` (correct color, weight).
   - [x] Secondary cancel button is `SecondaryButton`.
   - [x] If a duplicate-URL banner appears (paste a known existing product URL), the banner uses `p-4` padding (was `p-3` pre-polish).
5. From the parts catalog, click "Add to Build List" on any part to open the dialog. Verify:
   - [x] Dialog uses the dark Dialog panel from `common/Dialog.tsx`.
   - [x] Part-preview h3 (the part name) is `text-xl` (was `text-lg` pre-polish).
   - [x] "Select Build List(s)" h3 is `text-xl` (was `text-lg` pre-polish).
   - [x] Close / Cancel / Confirm affordances are clear; clicking Cancel dismisses without side effects.

**Polish checklist applied (source: Plan 06-06 Task 2):**
- [x] Spacing scale consistency — PartList card-layout inner row `p-3` -> `p-4`; CreatePartForm duplicate-URL banner `p-3` -> `p-4`
- [x] Typography hierarchy — AddToBuildListDialog h3s `text-lg` -> `text-xl` (Part Preview heading + "Select Build List(s)" heading)
- [x] Card.tsx shadow + rounded alignment — PartList card-layout surface `rounded-lg` -> `rounded-xl shadow-md` (matches Card.tsx vocabulary)
- [x] Button variant consistency — REVIEWED: parts-catalog already uses `ActionButton` / `SecondaryButton` / `LinkButton` consistently; no changes required
- [x] Responsive grid — REVIEWED: PartsCatalog uses `flex-col lg:flex-row` sidebar pattern (not a grid); already responsive; no changes required

**Files modified by Plan 06-06:**
- `frontend/src/components/parts/PartList.tsx` (refactor 06-06)
- `frontend/src/components/parts/CreatePartForm.tsx` (refactor 06-06)
- `frontend/src/components/parts/AddToBuildListDialog.tsx` (refactor 06-06)

**Files in scope but not modified (already compliant):**
- `frontend/src/pages/parts/PartsCatalog.tsx` — uses `PageHeader` (canonical) + standard layout; no violations
- `frontend/src/pages/parts/EditPart.tsx` — uses `PageHeader` + `Card` (canonical); no violations
- `frontend/src/pages/parts/UserParts.tsx` — uses `PageHeader` (canonical); no violations
- `frontend/src/components/parts/PartListItem.tsx` — h3 already `text-xl` (canonical)
- `frontend/src/components/parts/EditPartForm.tsx` — hand-rolled `<select>` element styled to match `input-modern` form pattern; replacing with SearchableSelect would be structural refactor (out of D-17 scope)
- `frontend/src/components/parts/ImageGalleryManage.tsx` — `gap-3` is part of an established gallery convention; matches non-parts ImageGallery sibling
- `frontend/src/components/parts/ImageGallery.tsx` — same convention as ImageGalleryManage
- `frontend/src/components/parts/PartsFilterSidebar.tsx`, `PartsActiveFilterChips.tsx`, `CategoryFilter.tsx`, `VoteButtons.tsx`, `PriceHistoryLineChart.tsx` — internal class strings consistent with their existing patterns; no obvious violations of canonical Card/Button/Home scale

**Expected result:** Every checkbox above ticked by the operator. No visual regression vs. pre-Phase-6 staging screenshots.

**Out of scope (explicitly NOT verified here):**
- Information-architecture changes (none made per D-17)
- New components or pages (none added)
- Copy changes (none made)
- Color-palette migration `gray-*` -> `neutral-*` across the parts catalog (deferred — that's a design-token rollout, not bounded polish; revisit in UX-V2-01)
- Full parts-catalog redesign (deferred to UX-V2-01)

**Sign-off:** Tyler Webb (date: 2026-04-23)

***

## Summary sign-off

All four items signed -> Phase 6 manual gates closed. Record the date of final sign-off in the phase SUMMARY.

Phase 6 manual verification complete: Tyler Webb (date: 2026-04-23) — all 4 sections signed off (Section 1 chrome extension smoke, Section 2 Sentry route-group tags, Section 3 Terraform apply, Section 4 parts-catalog polish). User manually approved all items 2026-04-23.
