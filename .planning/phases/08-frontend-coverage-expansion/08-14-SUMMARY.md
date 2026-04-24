---
phase: 08-frontend-coverage-expansion
plan: 14
subsystem: testing
tags: [frontend, page-tests, public, wave-3, coverage-backfill]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: "01"
    provides: "Dual api-client mock + testScenarios + mockUser shape; services/Api re-export shim over api/<domain>"
provides:
  - "13 public top-level page test files covering Home, Profile, ViewUser, About, ContactUs, PrivacyPolicy, TermsOfService, Support, Pricing, Checkout, Search, BugReport, NotFound"
  - "34 new it-blocks + 79 expect() assertions for Wave 3 public-pages coverage"
  - "Canonical pattern: manual MemoryRouter/BrowserRouter render + local vi.mock('../services/Api', ...) that forwards named domain APIs (buildListsApi, searchApi, bugReportsApi, imageApi, etc.) through the globally-mocked apiClient when the page under test imports named shim exports beyond `default`"
  - "FormData upload assertion pattern (Profile.test.tsx): asserts both shape (expect.any(FormData) + multipart Content-Type header) AND content (fd.get('file') === file) per must_haves key_link"
affects: ["08-15 (admin pages) may reuse the services/Api forwarding pattern when named admin exports are needed", "Wave 5 coverage threshold"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Manual-router-render pattern for page tests that need named services/Api exports: bypass test-utils.tsx's customRender (which mocks services/Api with `default`-only), render under <BrowserRouter>/<MemoryRouter> directly, and install a test-file-local vi.mock('../services/Api', ...) that forwards named APIs through the globally-mocked apiClient"
    - "HTML5-required bypass pattern (BugReport.test.tsx): form.noValidate = true to exercise the JS-side validation guard while still using userEvent.click for the submit"
    - "Route-param test pattern (ViewUser.test.tsx): render under <MemoryRouter initialEntries={[`/user/${id}`]}> + <Routes>/<Route path=\"/user/:userId\"> so useParams resolves the dynamic segment"

key-files:
  created:
    - "frontend/src/pages/About.test.tsx (33 lines, 2 tests)"
    - "frontend/src/pages/PrivacyPolicy.test.tsx (31 lines, 2 tests)"
    - "frontend/src/pages/TermsOfService.test.tsx (28 lines, 2 tests)"
    - "frontend/src/pages/Support.test.tsx (36 lines, 2 tests)"
    - "frontend/src/pages/NotFound.test.tsx (23 lines, 2 tests)"
    - "frontend/src/pages/Home.test.tsx (125 lines, 4 tests)"
    - "frontend/src/pages/ContactUs.test.tsx (53 lines, 3 tests)"
    - "frontend/src/pages/Pricing.test.tsx (82 lines, 3 tests)"
    - "frontend/src/pages/Checkout.test.tsx (72 lines, 3 tests)"
    - "frontend/src/pages/Search.test.tsx (143 lines, 3 tests)"
    - "frontend/src/pages/BugReport.test.tsx (132 lines, 3 tests)"
    - "frontend/src/pages/Profile.test.tsx (165 lines, 3 tests)"
    - "frontend/src/pages/ViewUser.test.tsx (108 lines, 2 tests)"
  modified: []

key-decisions:
  - "For tests that need named services/Api exports (buildListsApi, searchApi, bugReportsApi, imageApi, partManufacturersApi, retailersApi), the test-utils.tsx customRender is NOT suitable — it registers its own vi.mock('../../services/Api', ...) with ONLY `default: mockApiClient`, which SHADOWS the test-file mock and drops the named exports. Such tests bypass customRender and manually wrap in <BrowserRouter> or <MemoryRouter> + explicit mockUseAuth.mockReturnValue(...)."
  - "For tests that only need `default` from services/Api (all five static pages + ContactUs), customRender + testScenarios.unauthenticated is the simpler pattern and was used."
  - "Support page uses useIsPremiumSystemDisabled (AppSettingsContext consumer). Mocked the useIsPremium module directly rather than wiring an AppSettingsProvider into the test — one line, avoids the context-layer complexity."
  - "ContactUs is a static contact-info page (no form submission in source), so the test asserts headings + mailto: link wiring rather than form submission. Plan text hinted at submit, but source verification showed no form."
  - "Pricing + Checkout bypass customRender because testScenarios.authenticated passes createMockUser() which returns an incomplete UserRead (missing is_service_account, subscription_tier, subscription_status, totp_enabled) — those tests use exactOptionalPropertyTypes-compatible mockUser from test/mocks/api.ts."
  - "Profile image upload test asserts BOTH the apiClient.post call shape (URL prefix, FormData body, multipart header) AND the FormData payload contents (fd.get('file') === file), fulfilling the plan's must_haves key_link: `frontend/src/pages/Profile.test.tsx → frontend/src/api/images.ts uploadImage via expect.any(FormData)`."

patterns-established:
  - "Page tests can assert route branching via LinkButton href (e.g. Pricing's Go Premium CTA routes to /register vs /checkout based on useAuth().isAuthenticated)."
  - "ImageUpload tests interact with the hidden <input type=\"file\"> via document.querySelector('input[type=\"file\"]') + userEvent.upload(input, file), then assert the apiClient.post call received a FormData with the expected 'file' field."
  - "Multi-section static pages use grep-robust assertions: getAllByText().length > 0 for phrases that occur in multiple places (e.g. 'Last updated' in policy pages, 'we'd love to hear from you' in ContactUs)."

requirements-completed: [SAFE-03]

# Metrics
duration: "~25min"
completed: 2026-04-24
---

# Phase 8 Plan 14: Public Top-Level Page Tests (Wave 3 — largest group) Summary

**Added 13 new page-test files (34 it-blocks, 79 expect assertions, 1031 total lines) covering every public top-level customer page per D-11, establishing a canonical manual-render-with-local-services/Api-mock pattern for page tests that need named domain API exports. All 420 tests in the repo pass; type-check clean.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-24T11:05:00Z
- **Completed:** 2026-04-24T11:16:00Z
- **Tasks:** 3
- **Files created:** 13
- **Files modified:** 0
- **Test count delta:** +34 it-blocks (386 → 420 passing)

## Accomplishments

- **13/13 public top-level pages now have at least one render test** per D-11 and the plan's must_haves truths. Five static pages (About, PrivacyPolicy, TermsOfService, Support, NotFound) have minimal heading-visible + content-present coverage; eight interactive pages (Home, ContactUs, Pricing, Checkout, Search, BugReport, Profile, ViewUser) have full happy-path + at least one error/empty-state branch.
- **Profile image upload via FormData covered** (must_haves key_link satisfied) — Profile.test.tsx exercises the Edit-Profile → ImageUpload → file picker → apiClient.post(`/images/upload?...`, FormData, {multipart header}) chain, and asserts BOTH the call shape AND that the FormData payload carries the uploaded file under the `file` key.
- **Search URL round-trip covered** — Search.test.tsx renders under `<MemoryRouter initialEntries={['/search?q=honda']}>` and asserts `apiClient.get('/search/', { params: { q: 'honda' } })` fires. Also covers the empty-results branch with the canonical "No results found for 'missing'" message.
- **BugReport submit + validation covered** — BugReport.test.tsx fills title+description, clicks submit, asserts apiClient.post('/bug-reports/', { title, description, ... }). A second test bypasses HTML5 `required` (form.noValidate = true) to exercise the JS "Title is required" guard.
- **Auth-branch pages covered** — Home.test.tsx + Pricing.test.tsx assert CTAs differ between authenticated and unauthenticated users (Hero CTA swaps Get Started/Sign In ↔ Create Build/Browse Parts; Pricing Go Premium CTA swaps /register ↔ /checkout).
- **Zero-regression proof:** `npm test -- --run` → 54 files / 420 tests pass; `npm run type-check` exits 0.

## Task Commits

Each task was committed atomically on the worktree branch:

1. **Task 1: Static pages (About, PrivacyPolicy, TermsOfService, Support, NotFound)** — `5f91df2` (test)
2. **Task 2: Interactive public pages (Home, ContactUs, Pricing, Checkout, Search, BugReport)** — `1f4ac3f` (test)
3. **Task 3: Profile + ViewUser (image upload + 404 path)** — `5df09b5` (test)

## Files Created/Modified

### Created (13)

#### Task 1 — Static pages
- `frontend/src/pages/About.test.tsx` — heading + Mission + Values section assertions.
- `frontend/src/pages/PrivacyPolicy.test.tsx` — heading + last-updated + Information We Collect section.
- `frontend/src/pages/TermsOfService.test.tsx` — heading + last-updated + The Service section.
- `frontend/src/pages/Support.test.tsx` — heading + Buy Me a Coffee + Subscribe to Premium cards (mocks useIsPremium to avoid AppSettingsProvider dependency).
- `frontend/src/pages/NotFound.test.tsx` — 404 heading + "Page not found" text + Go Home link with href="/".

#### Task 2 — Interactive public pages
- `frontend/src/pages/Home.test.tsx` — unauth CTAs (Get Started→/register, Sign In→/login) + auth CTAs (Create Build→/builder, Browse Parts→/parts) + Featured Builds & Popular Parts headings + initial API fetch spy.
- `frontend/src/pages/ContactUs.test.tsx` — heading + hero copy + Business/Tech Support/DMCA section headings with mailto: links (asserted via role=link filter on href^="mailto:").
- `frontend/src/pages/Pricing.test.tsx` — Simple Pricing heading + Free & Premium tier cards + Go Premium CTA route branching (/register unauth → /checkout auth).
- `frontend/src/pages/Checkout.test.tsx` — Go Premium heading + Order Summary + disabled subscribe CTA + authenticated user email in "billed to" row + back-to-pricing link.
- `frontend/src/pages/Search.test.tsx` — initial empty state (no query) + URL-driven API fetch with `/search/?q=honda` + no-results branch.
- `frontend/src/pages/BugReport.test.tsx` — form render (title+description+submit) + POST /bug-reports/ with correct body shape + JS-side validation guard when title is empty.

#### Task 3 — User profile pages
- `frontend/src/pages/Profile.test.tsx` — authenticated render (username/email visible) + image upload via FormData (asserts URL prefix, FormData body shape, multipart Content-Type header, AND the file payload) + upload error path.
- `frontend/src/pages/ViewUser.test.tsx` — public-profile render via `/user/:userId` route + 404 "Failed to load profile for User ID..." error branch.

### Modified

None.

## Decisions Made

- **Manual-render-vs-customRender split by services/Api-named-export need.** Static pages (About, PrivacyPolicy, TermsOfService, Support, NotFound) and ContactUs only need `default` from services/Api — they use the test-utils `customRender` and `testScenarios.unauthenticated`. All other pages (Home, Pricing, Checkout, Search, BugReport, Profile, ViewUser) import named domain APIs (buildListsApi, partsApi, retailersApi, partManufacturersApi, searchApi, bugReportsApi, imageApi) and must bypass customRender — it installs a competing vi.mock('../../services/Api', ...) with `default`-only, dropping the named exports. They manually render under `<BrowserRouter>`/`<MemoryRouter>` + explicit `mockUseAuth.mockReturnValue(...)`.
- **ContactUs is a static contact-info page**, not a form. Source verification showed no form, no API call — just three mailto: sections. Test asserts headings + mailto link wiring.
- **Profile image upload uses apiClient.post (not a dedicated imageApi module mock)** because the setup.ts global mock provides `apiClient.post` as a spy. The local services/Api mock re-exports an `imageApi.uploadImage` implementation that calls client.post, so the assertion chain runs through the existing mock with no extra wiring.
- **Search `no results` test uses a full SearchResults fixture with empty-array data fields** (build_lists.data = [], users.data = [], parts.data = []) + a query = "missing", so the page's sortedSections useMemo + "No results found for '...'" message both run.
- **FormData `expect.any(FormData)` is NOT enough by itself.** Plan must_haves key_link specifically calls out `expect\\.any\\(FormData\\)` as the pattern to use, but the Profile test also asserts `fd.get('file')` matches the uploaded File to confirm the request is structurally correct (not just a FormData with random contents).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test-utils customRender shadows test-file vi.mock('../services/Api')**

- **Found during:** Task 2 (first run of Home/Search/BugReport tests)
- **Issue:** Initial test-file approach imported `render` from `'../test/utils/test-utils'` AND declared `vi.mock('../services/Api', async () => { ... searchApi: ... })`. Result: `[vitest] No "searchApi" export is defined on the "../../services/Api" mock.` The test-utils.tsx file registers its own `vi.mock('../../services/Api', () => ({ default: mockApiClient }))` which Vitest resolves BEFORE the test-file mock, masking the named exports.
- **Fix:** Bypass customRender for pages that need named services/Api exports. Render manually with `<BrowserRouter>`/`<MemoryRouter>` + inline `mockUseAuth.mockReturnValue(...)`. Kept the `vi.mock('../services/Api', ...)` in the test file.
- **Files modified (refactored on Task 2 retry):** Home.test.tsx, Search.test.tsx, BugReport.test.tsx
- **Verification:** All 19 Task 2 tests pass; named exports (buildListsApi, searchApi, bugReportsApi) resolve correctly.
- **Committed in:** `1f4ac3f` (Task 2 — single commit, iterated before landing)

**2. [Rule 1 - Bug] Multiple-element text matcher failures in PrivacyPolicy, TermsOfService, ContactUs**

- **Found during:** Task 1 + Task 2 initial test runs
- **Issue:** `screen.getByText(/last updated/i)` threw `Found multiple elements with the text` because the policy pages mention "Last updated" in both the header stamp AND body cross-references. Similarly, ContactUs's "we'd love to hear from you" appears in both the hero subtitle AND a body paragraph.
- **Fix:** Switched to `getAllByText(...)` with `.length > 0` assertion when the literal phrase is expected to appear in multiple nodes. This is semantically correct (we're testing the phrase is present, not that it's the unique match).
- **Files modified:** PrivacyPolicy.test.tsx, TermsOfService.test.tsx, ContactUs.test.tsx
- **Committed in:** `5f91df2` (Task 1) and `1f4ac3f` (Task 2)

**3. [Rule 1 - Bug] testScenarios.authenticated fails strict TS with exactOptionalPropertyTypes**

- **Found during:** Task 2 type-check after refactoring to customRender-free pattern for Home
- **Issue:** Initial Checkout + Pricing tests used `render(<Page />, testScenarios.authenticated)` from test-utils. TSC flagged `Type '{ id: number; username: string; ... }' is missing the following properties from type 'UserRead': is_service_account, subscription_tier, subscription_status, totp_enabled` because `testScenarios.authenticated.user = createMockUser()` returns an incomplete shape.
- **Fix:** Refactored Checkout and Pricing to use the manual-render pattern with the canonical `mockUser` from `test/mocks/api.ts` (which IS fully typed as UserRead).
- **Files modified:** Checkout.test.tsx, Pricing.test.tsx
- **Verification:** `npm run type-check` → exits 0.
- **Committed in:** `1f4ac3f` (Task 2 — single commit, iterated before landing)

**4. [Rule 3 - Blocking] BugReport HTML5 `required` attr blocks JS validation guard**

- **Found during:** Task 2 first draft of BugReport validation test
- **Issue:** The title Input has `required` (HTML5 attr). `user.click(submit)` triggers browser-level validation BEFORE handleSubmit runs, so the JS guard `if (!formData.title.trim()) { setError('Title is required') }` never fires and the test cannot exercise that branch.
- **Fix:** `document.querySelector('form').noValidate = true` bypasses HTML5 validation, letting the form submit and the JS guard run. The test comment documents the rationale.
- **Files modified:** BugReport.test.tsx
- **Committed in:** `1f4ac3f` (Task 2)

---

**Total deviations:** 4 auto-fixed (2 blocking / tooling, 2 bug-fixes). No out-of-scope work. All fixes were in test code authored within this plan.

## Issues Encountered

- **React `act(...)` warnings during Home and BugReport tests.** Home fires a cascade of `useApiRequest` calls on mount (`void fetchFeaturedBuildLists(); void fetchPopularParts(); ...`) whose resolution occurs after the sync render. These write to React state outside an explicit `act()`. Tests still pass — assertions are all in `await waitFor(...)` blocks which run under `act` implicitly — but the console output is noisy. Treating as an acknowledged known issue (also present in the pre-Phase-8 App.coverage.test.tsx for the same reason). Out of scope to refactor Home's fetch dispatch for this plan.

## User Setup Required

None.

## Next Phase Readiness

- **Plan 08-15 (admin pages, Wave 4) unblocked.** Admin page tests will need the same manual-render pattern plus `testScenarios.adminAuthenticated` from 08-01 (CrawlerAdmin + AdminDashboard + etc.).
- **Wave 5 coverage threshold (D-22) unblocked.** Public pages are now covered; remaining Wave 3 plans (08-10 through 08-13) cover authentication / builder / parts / buildLists pages. When all Wave 3 + Wave 4 plans land, the plan 08-19/08-20 can unblock the `coverage.thresholds` block in vitest.config.ts.
- **Coverage delta (informational, not a gate here):** baseline captured in 08-01 at Lines 4.72 / Funcs 21.36 / Branches 37.11 / Stmts 4.72. This plan adds 13 page tests covering ~3,787 lines of source; a representative post-run coverage snapshot is left to the Wave 5 threshold plan.
- **No blockers. No concerns.**

## Self-Check: PASSED

- `test -f frontend/src/pages/{About,PrivacyPolicy,TermsOfService,Support,NotFound,Home,ContactUs,Pricing,Checkout,Search,BugReport,Profile,ViewUser}.test.tsx` → all 13 FOUND
- `npm test -- --run src/pages/` → 13 files / 34 tests pass
- `npm test -- --run` (full repo) → 54 files / 420 tests pass
- `npm run type-check` → exits 0
- `grep -c "\.skip(" frontend/src/pages/*.test.tsx` → 0 across all 13 files
- `grep -c "FormData\|expect.any(FormData)" frontend/src/pages/Profile.test.tsx` → 7 (must_haves key_link satisfied)
- `grep -c "vi.mocked(apiClient" frontend/src/pages/ContactUs.test.tsx frontend/src/pages/Search.test.tsx frontend/src/pages/BugReport.test.tsx` → 10 (plan required at least 3)
- `git log --oneline` → 3 commits FOUND (`5f91df2`, `1f4ac3f`, `5df09b5`)

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
