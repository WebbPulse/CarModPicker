# S10: Parts catalog redesign — UAT

**Milestone:** M002
**Written:** 2026-04-25T23:56:12.850Z

# S10 UAT — Parts Catalog Redesign

This UAT script proves the /parts page is fully migrated onto the S08 design system, that the S06 sparkline+delta integration is preserved end-to-end, and that R020 keyboard accessibility holds. The automated portion is fully covered by `frontend/e2e/parts-catalog.spec.ts` (5 passed + 4 intentionally skipped) plus the slice-level test gauntlet. A short manual pass is included for design-language sanity checks that aren't worth pixel-asserting.

## Preconditions

- Frontend dev server runs on port 4000 (`cd frontend && npm run dev`).
- Backend running on port 8000 with a populated local DB (~25k parts; `python ../scripts/populate_sample_data.py` from `backend/` if empty).
- A logged-in user account (any tier — the My Parts link / AddToBuildList affordance are gated by `isAuthenticated`, not subscription).
- At least one build list owned by the user (to exercise the AddToBuildList dialog's multi-select).
- At least three parts in the catalog: one with multiple price observations, one with a single observation, one with zero observations (to exercise SparklineCell's three render paths from S06).

## Automated Test Cases (covered by parts-catalog.spec.ts + the slice test gauntlet)

### UAT-S10-A1 — Multi-viewport visual regression of /parts

**Steps:**
1. Run `cd frontend && npm run test:e2e -- parts-catalog`.
2. Watch for projects: `mobile`, `tablet`, `desktop`.

**Expected outcome:**
- Three runs of `parts catalog visual regression` pass (one per project).
- Each run scrolls the multi-observation row into view, asserts the sparkline `[role='img']` toBeVisible, asserts `counters.batchPriceHistoryPostCount === 1` (S06 invariant: exactly one batch POST per displayed page), then matches the committed baseline PNG within the 0.2% pixel-diff threshold from `playwright.config.ts`.
- Three baseline PNGs exist on disk: `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-{mobile,tablet,desktop}-linux.png`.
- 5 passed + 4 skipped + 0 failed; total runtime ~4-8s.

**Edge cases verified:**
- Multi-observation row IO observer fires deterministically across all three projects (scrollIntoViewIfNeeded per MEM079/MEM083).
- Default-404 mock-miss + page.on('pageerror') re-throw catch any non-mocked /api/* drift or runtime React errors.

### UAT-S10-A2 — AddToBuildList dialog focus + Escape (desktop)

**Steps:**
1. Within the parts-catalog spec run, the test `add-to-build-list dialog opens, focus moves into it, Escape closes it` runs on the `desktop` project (skipped on mobile/tablet via testInfo.project.name per MEM105).
2. The test calls `page.setViewportSize({ width: 2400, height: 900 })` BEFORE setupPage so the responsive table's `actions` column (priority 7) stays in the DOM at the wider viewport (default 1280 desktop drops it after sidebar+container caps — MEM114).
3. The test clicks `[data-testid='parts-catalog-add-to-build-list-trigger']:first()`.

**Expected outcome:**
- `[data-testid='parts-catalog-add-to-build-list-dialog']` becomes visible.
- `document.activeElement` is contained by the dialog element (Radix focus trap holds focus inside).
- After `page.keyboard.press('Escape')`, the dialog is hidden.

**Edge cases:**
- Mobile/tablet projects skip this test (the table layout drops the trigger column at narrower viewports; the Add-to-Build-List affordance there belongs to a card layout used outside /parts).

### UAT-S10-A3 — Tab traversal lands visible focus on search input (desktop)

**Steps:**
1. Within the parts-catalog spec run, the test `tab traversal lands visible focus on search input` runs on the `desktop` project.
2. Test focuses `document.body`, then presses Tab up to 30 times until `document.activeElement.dataset.testid === 'parts-catalog-search'`.

**Expected outcome:**
- Within ≤30 Tab presses, the search input gains focus.
- The focused element matches `:focus-visible` AND has either a non-empty `outline` OR a non-empty `boxShadow` — proving R020 visible focus ring is rendered by `ui/Input`'s `focus-visible:ring-ring` token.

**Edge cases:**
- Mobile/tablet projects skip this test — the focus-ring assertion is a token-level claim, not a layout-level one, so a single project run is sufficient evidence.

### UAT-S10-A4 — S06 invariant preserved across reskin

**Steps:**
1. Run `cd frontend && npm run test:e2e -- price-history`.

**Expected outcome:**
- All 9 price-history.spec.ts tests pass (3 viewports × `/parts catalog renders sparklines + delta lines` + `/parts/:id detail renders retailer breakdown + stale caveat` + `/parts/:id with zero observations hides Price summary block`).
- Refreshed baselines (mobile/tablet/desktop × 2 affected tests = 6 PNGs) match the new design system. Original assertions on sparkline visibility, delta-line text (`$120 → $150`), batch POST count, and stale caveat all still pass — only the fullPage pixel baselines were refreshed.

### UAT-S10-A5 — Unit tests + type-check + lint baseline

**Steps:**
1. Run `cd frontend && npm run type-check`.
2. Run `cd frontend && npm run test -- PartsCatalog PartList AddToBuildListDialog --run`.
3. Run `cd frontend && npm run lint`.
4. Run `grep "from '../../components/common/Input'" src/pages/parts/PartsCatalog.tsx`.
5. Run `grep "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'\|from '../common/Dialog'" src/components/parts/PartList.tsx src/components/parts/AddToBuildListDialog.tsx`.

**Expected outcome:**
- (1) exit 0.
- (2) 6/6 passed (3 PartsCatalog page tests + 3 PartList.priceHistory tests). Documented pre-existing `[usePartPriceSummaries] TypeError: Cannot read properties of null (reading 'summaries')` stderr lines from S06's mocked-empty-batch path remain — not a regression.
- (3) 108 total errors with zero in any S10-touched file (PartsCatalog.tsx, PartsFilterSidebar.tsx, PartsActiveFilterChips.tsx, PartList.tsx, AddToBuildListDialog.tsx, e2e/parts-catalog.spec.ts). The +4 vs MEM062's 104 baseline is in PriceAlertSubscribeButton/AccountAlerts/ui/* (out of S10 scope).
- (4) exit 1 (no match — legacy `common/Input` import gone from PartsCatalog.tsx).
- (5) exit 1 (no match — legacy ActionButton/SecondaryButton/common/Dialog imports gone from PartList.tsx and AddToBuildListDialog.tsx).

## Manual Test Cases (1-2 minute design-language smoke; not worth pixel-asserting)

### UAT-S10-M1 — Visual sanity at /parts in dev

**Steps:**
1. Start dev server: `cd frontend && npm run dev`. Navigate to `http://localhost:4000/parts`.
2. Inspect the page on the new dark token palette.

**Expected outcome:**
- Search input renders as ui/Input (token-aware border, ring-ring focus outline).
- Filter sidebar checkboxes render with `accent-primary border-input bg-background`; the price-min/price-max inputs and the part-manufacturer search input render as ui/Input.
- 'Clear all' (top-right) renders as inline link-style ghost button; per-section 'Clear categories' / 'Clear part manufacturers' render as block-left full-width ghost buttons (no centered or h-9 sizing artifact).
- Active-filter chips have compact h-5 w-5 remove buttons that fit cleanly inside the chip span.
- Each part row shows three actions: Add to Build List (default/primary variant), Edit (secondary variant), Delete (destructive variant — bg-destructive, no bespoke red Tailwind override).
- Card layout (if visible at narrower viewports outside /parts) shows the same three buttons with `text-xs px-3 py-1` sizing and the leading 📋 emoji on Add-to-Build-List preserved.

### UAT-S10-M2 — Sparkline + delta line still render

**Steps:**
1. Scroll a row that has multiple observations into view.
2. Inspect the price cell.

**Expected outcome:**
- Sparkline ([role='img'] SVG) renders — proves SparklineCell's IntersectionObserver gating still fires after the row-action button migration in T02.
- PriceDeltaLine renders below with the trend arrow + min/max range.
- Network panel: exactly one POST to `/api/parts/price-history` (batch summary fetch) per page navigation; per-row GET to `/api/parts/{id}/price-history` only for rows with multiple observations as they enter the viewport.
- A row with zero observations renders no sparkline, just current price (legacy fallback).

### UAT-S10-M3 — AddToBuildList dialog interaction

**Steps:**
1. Click an Add-to-Build-List row button. Use the part details that fit at least one of your build lists' car compatibility (or any if the car-mismatch banner is acceptable).
2. The dialog opens. Inspect: ui/Dialog with sm:max-w-3xl max width (slightly narrower than the legacy 4xl-equivalent — documented intentional delta).
3. Press Tab a few times — focus moves through the build-list multi-select rows and quantity input.
4. Click Cancel. Dialog closes; row context preserved.
5. Re-open. Pick a build list. Click Submit.

**Expected outcome:**
- Submit button shows the Loader2 lucide spinner via the `loading={isAdding}` prop (not the legacy LoadingSpinner ternary).
- On success, dialog closes and a toast/refresh signals the part was added.
- Pressing Escape on the open dialog closes it (Radix default behavior).
- Pressing Cancel while isAdding=true is a no-op (Cancel button disabled during the await loop).

### UAT-S10-M4 — Keyboard accessibility (R020)

**Steps:**
1. Reload `/parts`.
2. Press Tab repeatedly from the address bar.

**Expected outcome:**
- Visible focus rings appear on: skip-link (if present), 'My Parts' link, search input, filter sidebar inputs/checkboxes/clear-buttons, chip-remove buttons, sort headers, row action buttons (Add/Edit/Delete).
- Focus rings inherit ui/* tokens (ring-2 ring-ring) — no missing or invisible focus indicators.

## Edge Cases

- **Zero-observation parts:** sparkline does NOT render, current-price text only (verified by price-history.spec.ts `/parts/:id with zero observations hides Price summary block`).
- **Anonymous users:** My Parts link does NOT render; AddToBuildList row trigger does NOT render. parts-catalog.spec.ts mocks an authenticated user precisely to exercise these affordances; the anonymous path is covered by price-history.spec.ts.
- **Filter state persistence:** typing into the search field updates the URL via `usePartsFilters({syncToUrl:true})` — no debounce regression, no lost keystrokes (verified by the existing PartsCatalog.test.tsx that exercises setSearchTerm).
- **isAdding=true edge:** Cancel button must be a no-op (disabled); Escape falls through to Radix default close behavior — accepted documented gotcha from S09.
- **Responsive table actions column:** drops at the default 1280 desktop viewport once sidebar+container caps apply. T04's dialog test sets viewport to 2400×900 BEFORE setupPage to keep the column in the DOM. The card layout's Add-to-Build-List doesn't have a testid because /parts uses the table layout.

## Pass Criteria

- All five automated UAT cases (A1–A5) execute green in CI.
- Manual UAT cases (M1–M4) pass on at least one local dev-server run.
- No regressions in the existing PartsCatalog.test.tsx, PartList.priceHistory.test.tsx, components.spec.ts, or price-history.spec.ts.
- Lint baseline holds (zero net-new errors in any S10-touched file; the +4 vs MEM062's 104 baseline is acknowledged as outside slice scope).
- All three baseline PNGs committed under `frontend/e2e/parts-catalog.spec.ts-snapshots/`.
