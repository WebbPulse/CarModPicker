# S10: Parts catalog redesign

**Goal:** Reskin /parts (Parts Catalog) onto the S08 design system. Replace common/Input, common/Dialog, ActionButton, and SecondaryButton usages on PartsCatalog.tsx, PartsFilterSidebar.tsx, PartsActiveFilterChips.tsx, PartList.tsx (row action buttons), and AddToBuildListDialog.tsx with components/ui/* (button, input, dialog) — preserving filter state semantics, sparkline+delta integration (S06), responsive table column-priority logic, and existing accessibility (R020). Land Playwright parts-catalog.spec.ts at mobile/tablet/desktop with mocked API fixtures, an AddToBuildList dialog focus/Escape test, and a Tab focus assertion. Per MEM107, leave layout chrome (PageHeader, Pagination, Card, SectionHeader) for the S12 ripple sweep.
**Demo:** Visit /parts in dev — page on new design system; each part card shows the S06 sparkline + delta where observations exist. Run npm run test:e2e -- parts-catalog.spec.ts — green at mobile/tablet/desktop. Tab through the page; keyboard nav works.

## Must-Haves

- Visit /parts in dev — page renders on the new design system, every part card with observations still shows the S06 sparkline + delta line, exactly one batch POST per displayed page (S06 invariant preserved). Run npm run test:e2e -- parts-catalog — green at mobile/tablet/desktop with three baseline PNGs committed plus the dialog and keyboard interaction tests passing. Tab through the page — focus indicators visible on search input, filter checkboxes, sort headers, and row action buttons. npm run type-check exits 0; npm run lint produces no NEW errors beyond the existing 104-error baseline (MEM062).

## Proof Level

- This slice proves: - This slice proves: integration — page-level reskin proven by Playwright multi-viewport visual regression + dialog/keyboard assertions and unchanged unit tests; real runtime required (Vite dev server + mocked API fixtures); no human UAT required for the automated portion; brief manual keyboard pass documented in slice summary follow-ups.

## Integration Closure

- Upstream surfaces consumed: frontend/src/components/ui/{button,input,dialog}.tsx, frontend/src/components/parts/{PriceDeltaLine,SparklineCell}.tsx (S06), frontend/src/hooks/usePartPriceSummaries.ts (S06), frontend/src/lib/utils.ts (cn), frontend/src/styles/tokens.css, frontend/playwright.config.ts (mobile/tablet/desktop projects + 0.2% threshold).
- New wiring introduced in this slice: PartsCatalog.tsx + PartsFilterSidebar.tsx + PartsActiveFilterChips.tsx + PartList.tsx (row actions) + AddToBuildListDialog.tsx rewired onto ui/* primitives, frontend/e2e/parts-catalog.spec.ts + 3 baseline PNGs.
- What remains before the milestone is truly usable end-to-end: S11 (admin shell + extraction-health UI), S12 (ripple reskin of remaining ~17 pages including layout chrome — PageHeader, SectionHeader, Card, Pagination, VehicleFilterSection, VehicleFilterChips — and removal of components/common/), S13 (final integration + milestone verification). VehicleFilterSection (rendered inside PartsFilterSidebar) and Pagination (rendered by PartsCatalog) intentionally stay on legacy primitives this slice — they're shared layout chrome that rides the S12 sweep so the diff stays focused.

## Verification

- Runtime signals: ui/dialog onOpenChange transitions + dialog-data-state attributes from Radix; existing usePartPriceSummaries console.warn on batch fetch failure (S06); existing SparklineCell console.warn on per-row fetch failure (S06).
- Inspection surfaces: /parts in dev with React DevTools; Playwright HTML reporter at frontend/playwright-report/ on failed runs; pixel-diff PNGs at frontend/test-results/parts-catalog-* on regression; data-testid hooks (parts-catalog-search, parts-catalog-add-to-build-list-dialog, parts-catalog-add-to-build-list-trigger) make focused targeting deterministic.
- Failure visibility: pageerror listener in parts-catalog.spec.ts re-throws runtime React errors as hard test failures; default-404 mock-miss responses surface unexpected /api/* drift.
- Redaction constraints: none (page is public-readable; mocked user is fixture-only).

## Tasks

- [x] **T01: Reskin PartsCatalog search Input + PartsFilterSidebar inputs/checkboxes + PartsActiveFilterChips onto ui/* primitives** `est:1.5h`
  Migrate the catalog page-level chrome and filter UI onto S08 primitives. Three files, all interactive primitives only — leave VehicleFilterSection (legacy common/) and Pagination untouched per MEM107.

In frontend/src/pages/parts/PartsCatalog.tsx:
- Replace `import Input from '../../components/common/Input'` with `import { Input } from '../../components/ui/input'`.
- The search Input has props `type='text' placeholder value onChange className='w-full max-w-md'` — the S08 Input forwards all standard HTMLInputAttributes, so pass props directly. Add `data-testid='parts-catalog-search'` for T04.
- DO NOT touch the Pagination import or call site; that's S12 layout-chrome.
- DO NOT touch the LinkButton 'My Parts' import (it's a layout-tier link); S12 sweep.

In frontend/src/components/parts/PartsFilterSidebar.tsx:
- Replace the four raw `<input type='checkbox'/>` rows (Source / Categories / PartManufacturers) with raw `<input>` elements styled to use the new design tokens. The S08 ui/input is a single-line text input only — there is no ui/checkbox primitive yet, and adding one is out of scope (S12 will introduce it if needed). Instead, retire the `checkboxInputClass` Tailwind blob in favor of token-driven utility classes: `accent-primary border-input bg-background focus-visible:ring-2 focus-visible:ring-ring`.
- Replace the two price-range raw `<input type='number'/>` instances and the part-manufacturer search raw `<input type='text'/>` with `<Input>` from ui/input — pass `id`, `min`, `step`, `placeholder`, `value`, `onChange`. Use `<Input>` directly; do not introduce wrappers.
- Replace the 'Clear all' raw `<button>` and the 'Clear categories' / 'Clear part manufacturers' raw `<button>` elements with `<Button variant='ghost' size='sm' className='...preserved layout classes...'>` from ui/button. Preserve original alignment (block w-full text-left for inline section clears; inline link-style for the top-right Clear all — use `variant='link' size='sm'` for that one).
- Keep the outer Card wrapper and the section title <h2>/<h3> markup as-is — they are layout chrome (S12 sweep). The aside's `lg:w-64 flex-shrink-0` layout container is also untouched.
- Keep VehicleFilterSection's legacy import — it stays on legacy primitives until S12.

In frontend/src/components/parts/PartsActiveFilterChips.tsx:
- The chip itself uses `filterChipClass` from common/VehicleFilterChips (a shared style constant). Retain the import but move the per-chip remove `<button>` to `<Button variant='ghost' size='icon' className='h-5 w-5 ...preserved classes...'>` from ui/button so focus rings inherit ring tokens. Pass `aria-label` through unchanged.

Failure modes: filter-state callbacks (toggleCategory / togglePartManufacturer / clearVehicleFilter / clearPriceRange / setSelectedCategoryIds / setSelectedPartManufacturerIds / setPriceMin / setPriceMax) MUST stay wired identically — the test that proves they still work is the existing PartsCatalog.test.tsx + the new e2e spec exercising the search input. Negative tests: typing into the search field must trigger setSearchTerm without losing keystrokes (no debounce regression).

Threat surface: search-term value flows into the URL via usePartsFilters({syncToUrl:true}) and into a backend query param. No new XSS surface — value is rendered as text and used as a search filter. Existing rate-limit/sanitize behavior preserved.

Load profile: identical to before; no new fetches or re-renders introduced.
  - Files: `frontend/src/pages/parts/PartsCatalog.tsx`, `frontend/src/components/parts/PartsFilterSidebar.tsx`, `frontend/src/components/parts/PartsActiveFilterChips.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- PartsCatalog && grep -c "from '../../components/common/Input'\|from '../components/common/Input'" src/pages/parts/PartsCatalog.tsx | grep -q '^0$'

- [x] **T02: Reskin PartList row action buttons (Add to Build List / Edit / Delete) onto ui/Button — table + card layouts** `est:45m`
  Migrate the four row-action <ActionButton>/<SecondaryButton> usages in PartList.tsx (two per layout × table + card) to ui/Button while preserving the sparkline + delta-line integration (S06) and the responsive column-priority logic untouched.

In frontend/src/components/parts/PartList.tsx:
- Drop `import ActionButton from '../buttons/ActionButton'` and `import SecondaryButton from '../buttons/SecondaryButton'`.
- Add `import { Button } from '../ui/button'`.
- Table layout (lines ~847–869): the `actions` td renders three optional buttons. Replace `<ActionButton onClick={() => onAddToBuildList(part)} className='text-xs px-2 py-1 whitespace-nowrap shrink-0'>` with `<Button size='sm' className='text-xs px-2 py-1 whitespace-nowrap shrink-0' onClick={...}>`. Replace `<SecondaryButton onClick={() => onEdit(part)} className='text-xs px-2 py-1'>` with `<Button variant='secondary' size='sm' className='text-xs px-2 py-1' onClick={...}>`. Replace the destructive `<ActionButton ... className='text-xs px-2 py-1 bg-red-600 hover:bg-red-700'>` with `<Button variant='destructive' size='sm' className='text-xs px-2 py-1' onClick={...}>` — drop the bespoke red Tailwind classes since the destructive variant from buttonVariants already encodes them.
- Card layout (lines ~991–1014): same three substitutions, preserving the `text-xs px-3 py-1` size override. Keep the leading 📋 emoji prefix on Add-to-Build-List in the card layout.
- Add `data-testid='parts-catalog-add-to-build-list-trigger'` to the Add-to-Build-List Button in the TABLE layout only (T04's e2e clicks via this selector; the card layout is only used in non-catalog contexts so no testid needed there).
- DO NOT touch SortableTh, the surrounding ResponsiveTableWrapper, the LoadingSpinner / ErrorAlert / Card containers, or the price-cell SparklineCell + PriceDeltaLine integration. Those stay on legacy primitives — S12 sweep handles SortableTh, Card, ErrorAlert. The S06 invariant (one batch POST per page, multi-observation lazy-load) MUST remain intact — verified by T04's network counter.
- DO NOT change column-priority logic, sort logic, cache logic, or the providedData/providedPagination prop contract — they're consumed by other surfaces (UserParts, build-list views) outside this slice.

Failure modes: button onClick handlers MUST keep the same arity (`() => onAddToBuildList(part)` etc.) — Vitest's existing PartList.priceHistory.test.tsx exercises these via fireEvent.click. The destructive variant must still trigger onDelete with the part as a single argument. Negative tests: with onAddToBuildList undefined OR showAddToBuildListButton false, the button must NOT render (existing && short-circuit preserved). Load profile: rendered N×3 times per page where N is row count; no extra reflow.

Threat surface: row actions are currently gated by canEdit/canDelete predicates and showAddToBuildListButton; migration preserves all three gates. No new authorization surface introduced.
  - Files: `frontend/src/components/parts/PartList.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- PartList && grep -c "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/parts/PartList.tsx | grep -q '^0$'

- [ ] **T03: Reskin AddToBuildListDialog onto ui/Dialog + ui/Button while preserving form-submit semantics** `est:45m`
  Replace the common/Dialog wrapper, ActionButton, and SecondaryButton in AddToBuildListDialog.tsx with ui/Dialog (+ DialogContent/DialogHeader/DialogTitle/DialogFooter) and ui/Button. Preserve the form contract (handleSubmit, error/loading states, build-list multi-select, car-mismatch warning) — only swap the outer dialog primitive and the two footer buttons.

In frontend/src/components/parts/AddToBuildListDialog.tsx:
- Drop `import Dialog from '../common/Dialog'`, `import ActionButton from '../buttons/ActionButton'`, `import SecondaryButton from '../buttons/SecondaryButton'`.
- Add: `import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog'` and `import { Button } from '../ui/button'`.
- Replace `<Dialog isOpen={isOpen} onClose={onClose} title={...}>` with `<Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>` wrapping `<DialogContent data-testid='parts-catalog-add-to-build-list-dialog' className='sm:max-w-3xl max-h-[90vh] overflow-y-auto'>` containing `<DialogHeader><DialogTitle>{`Add ${part.name} to Build List`}</DialogTitle></DialogHeader>` followed by the existing form. The S08 DialogContent default max width is `max-w-lg` — override to `sm:max-w-3xl` to roughly preserve the legacy width that fit the part-preview Card + build-list multi-select UI without horizontal cramp. Keep `max-h-[90vh] overflow-y-auto` so the scroll behavior on tall content survives.
- Replace the footer pair: `<SecondaryButton type='button' onClick={onClose} disabled={isAdding}>Cancel</SecondaryButton><ActionButton type='submit' disabled={isAdding || selectedBuildListIds.size === 0}>{...}</ActionButton>` with `<Button type='button' variant='secondary' onClick={onClose} disabled={isAdding}>Cancel</Button><Button type='submit' loading={isAdding} disabled={selectedBuildListIds.size === 0} data-testid='parts-catalog-add-to-build-list-submit'>{selectedBuildListIds.size === 1 ? 'Add to Build List' : `Add to ${selectedBuildListIds.size} Build Lists`}</Button>`. Drop the inline `<LoadingSpinner/>` ternary — Button's `loading` prop renders the spinner via lucide Loader2. Note: ui/Button auto-disables when `loading=true` (see button.tsx line ~59), so keep the redundant `disabled={selectedBuildListIds.size === 0}` only for the empty-selection guard, not the loading guard.
- DO NOT touch the inner Cards (part preview, build-list rows), the quantity raw `<input type='number'/>`, the car-mismatch banner, the ErrorAlert message, or the LoadingSpinner used during build-list fetch — those are nested chrome that S12 will sweep. The form's onSubmit handler stays exactly as-is.
- The existing 4xl-equivalent width is purely aesthetic; sm:max-w-3xl is close enough and keeps the diff minimal. Document the slight width change in the slice summary.

Failure modes: handleSubmit awaits buildListPartsApi.addPartToBuildList in a loop; if any iteration throws, the catch block sets error and isAdding=false. The Button's `loading` prop must NOT auto-close the dialog (DialogContent doesn't auto-dismiss on loading), so the existing flow (success → onPartAdded() + onClose()) is preserved. Negative tests: clicking Cancel while isAdding=true must be a no-op (Cancel button disabled). Pressing Escape while isAdding=true: Radix Dialog's default behavior closes — accept this as documented in S09's confirm-dialog gotchas.

Threat surface: the dialog adds a part to user-owned build-lists by calling buildListPartsApi.addPartToBuildList(buildListId, partId, {quantity, notes:null}). Ownership is enforced server-side; quantity is clamped to >=1 in handleSubmit (`Math.max(1, quantity)`). Migration preserves both gates. No new XSS surface — part.name and buildList.name render as text.

Load profile: dialog opens on demand; no autoload. The build-list fetch fires once on isOpen=true (existing behavior).
  - Files: `frontend/src/components/parts/AddToBuildListDialog.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- PartsCatalog && grep -c "from '../common/Dialog'\|from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/parts/AddToBuildListDialog.tsx | grep -q '^0$'

- [ ] **T04: Add frontend/e2e/parts-catalog.spec.ts with mocked fixtures, multi-viewport screenshots, sparkline assertion, dialog focus + Escape, and Tab keyboard test** `est:1.5h`
  Create a new Playwright spec for /parts that runs at mobile/tablet/desktop (already configured in playwright.config.ts) and asserts the slice's R015 + R020 success criteria plus the S06 sparkline integration invariant.

Follow the conventions established in frontend/e2e/price-history.spec.ts (S06/T04) and frontend/e2e/build-list.spec.ts (S09/T04):
- page.route() URL matcher MUST be `/\/api\/(?!.*\.ts)/` (MEM082) — never use **/api/** glob.
- Pre-accept cookie-consent banner via page.addInitScript (MEM098).
- Pre-dismiss chrome-extension promo via addInitScript writing chrome_extension_promo_last_dismissed=YYYY-MM-DD (MEM108).
- Pin Date.now() via addInitScript to FIXED_NOW_ISO so any 'now'-dependent rendering is deterministic.
- page.on('pageerror', err => { throw err }) so runtime React errors fail the test loudly.
- Authenticate the mocked user (MOCK_USER returned from /api/users/me) so the 'Add to Build List' affordance and the 'My Parts' link both render — the catalog page checks isAuthenticated.

Mock fixtures needed (modeled on price-history.spec.ts mockApi router):
- GET /api/users/me → MOCK_USER (200, authenticated — distinguishes this spec from price-history.spec.ts which mocks anonymous 401)
- GET /api/app-settings/ → { premium_disabled: true, updated_at: FIXED_NOW_ISO }
- GET /api/categories/ → [MOCK_CATEGORY]
- GET /api/part-manufacturers/?active_only=true → [MOCK_PART_MANUFACTURER]
- GET /api/car-generations/stats/car-makes → {}
- GET /api/car-generations/by-ids → [] (used by PartList's on-demand car lookup)
- GET /api/parts/with-votes → MOCK_PAGINATED_PARTS (3 parts: multi-obs / single-obs / zero-obs, mirrors price-history.spec.ts)
- GET /api/parts/filter-options → { category_ids:[MOCK_CATEGORY_ID], part_manufacturer_ids:[MOCK_PART_MANUFACTURER_ID], car_ids:[], make_names:[] }
- POST /api/parts/price-history → MOCK_BATCH_RESPONSE (counter-incremented to assert exactly 1 call per page)
- GET /api/build-lists/?user_id=... → 1-entry MOCK_BUILD_LISTS array (so T04 dialog test sees a build-list row in the multi-select)
- Default 404 with `Mock miss: ${method} ${path}` (catches drift)

Tests to author:
  1. 'parts catalog visual regression' — goto /parts, waitForPageReady (networkidle + fonts.ready + 300ms), scrollIntoViewIfNeeded the multi-observation row (MEM079/MEM083) so the SparklineCell IO observer fires deterministically across all 3 projects, expect [data-part-id='${MULTI_PART_ID}'] [role='img'] toBeVisible, expect counters.batchPriceHistoryPostCount toBe 1 (S06 invariant), expect(page).toHaveScreenshot({ fullPage: true }). Three baseline PNGs land under e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-{mobile,tablet,desktop}-linux.png on first run.
  2. 'add-to-build-list dialog opens, focus moves into it, Escape closes it' — desktop only (test.skip on mobile/tablet to keep suite light) — click [data-testid='parts-catalog-add-to-build-list-trigger'].first(), expect [data-testid='parts-catalog-add-to-build-list-dialog'] toBeVisible, expect locator(':focus') to resolve to a node inside the dialog, press Escape, expect dialog toBeHidden.
  3. 'tab traversal lands visible focus on search input' — desktop only — page.keyboard.press('Tab') a couple of times until reaching the search input, assert via page.evaluate(() => document.activeElement?.dataset.testid === 'parts-catalog-search'). Allow up to 5 tabs to absorb any leading skip-link / 'My Parts' link focus.

Run npx playwright test parts-catalog --update-snapshots once locally to generate baselines, then commit baselines + spec.

Failure modes: a stray non-mocked /api/* call surfaces as a default-404 + console error → pageerror → hard test failure. Negative tests: the keyboard test guards R020 regression; the Escape-closes test guards Radix focus management. Load profile: per spec run, ~10 mocked HTTP calls per project + 3 snapshots; total runtime ~10s.

Threat surface: spec consumes mocked fixtures only; no real DB or network. The MOCK_USER's id matches the build-list fixture's user_id so the canManage / showAddToBuildListButton gate evaluates true.
  - Files: `frontend/e2e/parts-catalog.spec.ts`, `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-mobile-linux.png`, `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-tablet-linux.png`, `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-desktop-linux.png`
  - Verify: cd frontend && npm run test:e2e -- parts-catalog

- [ ] **T05: Slice-level verification sweep and evidence capture** `est:30m`
  Final cross-task verification that the slice goal is met. Run the full local test gauntlet from frontend/, capture exit codes, spot-check the page in dev, and make sure no regressions slipped into adjacent areas.

Steps:
  1. cd frontend && npm run type-check — must exit 0.
  2. cd frontend && npm run test -- PartsCatalog PartList AddToBuildListDialog — must exit 0 (vitest passes for the directly-touched units).
  3. cd frontend && npm run test:e2e -- parts-catalog price-history components — must exit 0; parts-catalog runs 3 visual + 1 desktop dialog + 1 desktop keyboard test, price-history.spec.ts must STILL be 9/9 green (S06 invariant: row actions migration in T02 must not have broken sparkline integration), components.spec.ts must STILL be 3/3 green (no token regression).
  4. cd frontend && npm run lint 2>&1 | tail -1 — capture the error count. MUST equal the existing 104-error baseline (MEM062). Any net-new error in src/pages/parts/PartsCatalog.tsx, src/components/parts/PartsFilterSidebar.tsx, src/components/parts/PartsActiveFilterChips.tsx, src/components/parts/PartList.tsx, src/components/parts/AddToBuildListDialog.tsx, or e2e/parts-catalog.spec.ts is a fail — route back to T01–T04 for fix.
  5. Manual smoke (1–2 minutes, document the result in slice summary): start dev server (cd frontend && npm run dev) with a populated local DB, navigate to /parts, visually confirm the page renders on the new dark token palette, type into the search field and watch results filter, click the search-by-make / category checkboxes, click an 'Add to Build List' row button to open the dialog, press Escape to close, confirm focus rings visible on all action buttons under keyboard Tab, scroll to verify SparklineCell still renders for the multi-observation row.
  6. grep -r "from '../../components/common/Input'" src/pages/parts/PartsCatalog.tsx — must return 0.
  7. grep -r "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'\|from '../common/Dialog'" src/components/parts/PartList.tsx src/components/parts/AddToBuildListDialog.tsx — must return 0.
  8. Confirm no new pre-commit lint errors introduced; if step 4 finds any, route them back to the originating task (T01–T04) for fix.

This task is verification-only — no source files modified. The output is the slice summary doc and updated checkboxes on the slice plan.
  - Verify: cd frontend && npm run type-check && npm run test -- PartsCatalog PartList AddToBuildListDialog && npm run test:e2e -- parts-catalog price-history components && grep -r "from '../../components/common/Input'" src/pages/parts/PartsCatalog.tsx; if [ $? -ne 1 ]; then exit 1; fi && grep -r "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'\|from '../common/Dialog'" src/components/parts/PartList.tsx src/components/parts/AddToBuildListDialog.tsx; if [ $? -ne 1 ]; then exit 1; fi

## Files Likely Touched

- frontend/src/pages/parts/PartsCatalog.tsx
- frontend/src/components/parts/PartsFilterSidebar.tsx
- frontend/src/components/parts/PartsActiveFilterChips.tsx
- frontend/src/components/parts/PartList.tsx
- frontend/src/components/parts/AddToBuildListDialog.tsx
- frontend/e2e/parts-catalog.spec.ts
- frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-mobile-linux.png
- frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-tablet-linux.png
- frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-desktop-linux.png
