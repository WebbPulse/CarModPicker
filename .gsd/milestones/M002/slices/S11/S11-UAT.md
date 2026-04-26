# S11: Admin shell redesign + extraction-health UI — UAT

**Milestone:** M002
**Written:** 2026-04-26T00:22:18.821Z

# S11 UAT — Admin shell redesign + extraction-health UI

## Preconditions

- Frontend dev server running on port 4000 (`npm run dev` in `frontend/`).
- Backend running on port 8000 with `/api/admin/extraction-health` reachable (or use the Playwright-mocked path for offline UAT).
- Logged in as a user with `is_admin: true` and `email_verified: true` (use `populate_sample_data.py` admin seed or promote a user via DB).
- Browser at desktop viewport (≥1280px) for full visual fidelity; mobile/tablet viewports also covered.

---

## Test 1 — `/admin` reskin: ui/Button entry cards render under new design system

**Steps:**
1. Navigate to `/admin` while logged in as admin.
2. Observe the page header reads "Admin Dashboard" and a grid of section cards renders.
3. Confirm 8 entry cards are visible: the existing 7 sub-pages plus a new "Extraction Health" card with the 🩺 icon and description "Adapter compliance, per-tier coverage, and 7d failure rates".
4. Hover over each card's CTA button — it should show the S08 `ui/Button` default-variant hover treatment (not the legacy `ActionButton` styling).
5. Tab through the cards — focus rings should be visible on each button (`focus-visible:ring-2 focus-visible:ring-ring`).

**Expected:** All 8 cards render. CTAs use S08 `ui/Button` styling. Layout chrome (Card, PageHeader, SectionHeader) is unchanged from pre-S11 (intentional — retired in S12).

---

## Test 2 — `/admin/extraction-health` route resolves and renders the extraction-health view

**Steps:**
1. From `/admin`, click the new "Extraction Health" card's CTA.
2. The page navigates to `/admin/extraction-health` and shows a Compliance Card.
3. Confirm the hero figure displays `108 / 108` (or whatever the live backend returns) with three per-tier pills labeled `http`, `tls`, `browser`, each showing a `<n>/<n>` ratio.
4. Confirm a Coverage Card below renders three per-tier sections; each section shows `parts_with_specs / parts_total` and a table of universal-field names with their presence ratios as percentages.
5. Confirm a Failure-Rate Card below renders a 5-column table (Adapter / Tier / Parsed / Failed / Rate) sorted by rate desc, with the windowed subtitle "Last 7 days (since YYYY-MM-DD)".

**Expected:** Page renders with all three Cards. Numbers match the backend `ExtractionHealthResponse`. No console errors.

**Edge case — empty tier:** If a tier has `parts_total: 0`, the per-tier ratio displays `—` (em dash) instead of `NaN%`. (Verified by the Playwright `MOCK_EXTRACTION_HEALTH` fixture's empty `browser` tier.)

**Edge case — no failures in window:** If `failure_rate_7d` is empty, the Failure-Rate table renders the message "No failures in window" instead of an empty table.

---

## Test 3 — Refresh button re-fetches without unmounting

**Steps:**
1. On `/admin/extraction-health`, click the Refresh button in the Compliance Card header.
2. Loading spinner briefly appears, then the data refreshes.
3. Numbers may change if the backend has new data; otherwise the page stays stable.

**Expected:** No flicker, no duplicate alerts, no race-condition errors. The `cancelled` flag + `reloadTick` counter pattern guards against unmount races.

---

## Test 4 — Network failure is visible in the UI

**Steps:**
1. Stop the backend (`docker-compose down` or kill the uvicorn process).
2. Navigate to `/admin/extraction-health` (or click Refresh if already there).
3. After the spinner clears, an inline `ErrorAlert` should render.

**Expected:** Alert text includes `HTTP <status>` (or `Network error` if no response) and the hint "Check crawled_pages.parse_status for details". The compliance hero is NOT rendered (since `data` is null).

---

## Test 5 — Non-admin user is redirected away

**Steps:**
1. Log out and log in as a regular non-admin user.
2. Manually navigate to `/admin/extraction-health` via the URL bar.
3. The page renders a permission-denied `ErrorAlert` and immediately redirects to `/`.

**Expected:** No data fetch fires (no network request to `/api/admin/extraction-health`); URL bar shows `/` after redirect.

---

## Test 6 — Keyboard navigation lands a visible focus ring (R020)

**Steps:**
1. On `/admin/extraction-health` at desktop viewport, click outside any focusable element to clear focus.
2. Press `Tab` once.
3. Visually confirm a focus ring (or other visible focus indication) is rendered on the first reachable interactive control.

**Expected:** `:focus` element is visible. Either its className contains `ring` (ui/Button via `focus-visible:ring-2 focus-visible:ring-ring`) or its computed `outline`/`box-shadow` is non-empty for anchor/link controls.

---

## Test 7 — Multi-viewport visual regression (Playwright)

**Steps:**
1. From `frontend/`, run `npm run test:e2e -- admin.spec.ts`.
2. The Playwright runner exercises 9 tests across mobile/tablet/desktop projects: 2 visual-regression tests at all 3 viewports (6 PNG comparisons) + 1 keyboard test (desktop only, mobile/tablet skipped by design).

**Expected:** 7 passed, 2 skipped, 0 pixel diffs at `maxDiffPixelRatio: 0.002`. Baselines live under `frontend/e2e/admin.spec.ts-snapshots/`.

---

## Test 8 — App.coverage drift guard catches missing route mirror

**Steps:**
1. From `frontend/`, run `npm test -- --run App.coverage.test.tsx`.

**Expected:** All ALL_ROUTES boundary-fallback assertions pass, including the new `/admin/extraction-health` entry. Total assertion count meets the `>= 38` floor.

---

## Negative cases explicitly covered

- Empty per-tier coverage (`parts_total: 0` → `—` rendered, not `NaN%`).
- Failure rate of 1.0 (100%) — table cell renders correctly without overflow.
- Empty `failure_rate_7d` array — "No failures in window" message renders.
- HTTP 500 from backend — inline `ErrorAlert` with parse_status hint.
- Non-admin user — redirect to `/`, no data fetch.
- Missing `coverage.per_tier.<tier>` key — render guarded via `Object.entries(data?.coverage?.per_tier ?? {})`, no crash.

---

## Out of scope (intentionally deferred)

- Admin shell layout chrome (Card / PageHeader / SectionHeader / ErrorAlert / LoadingSpinner) — retired in **S12**.
- Other admin sub-pages (CrawlerAdmin, etc.) — reskinned in **S12**.
- Live extraction-health endpoint stress-test — covered by **S04**'s load-test deliverable.
- E2E spec exercising live scrape → extraction → ingest → admin-health visibility — covered by **S13** final integration.
