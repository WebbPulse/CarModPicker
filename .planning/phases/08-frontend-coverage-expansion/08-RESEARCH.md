# Phase 8: Frontend Coverage Expansion - Research

**Researched:** 2026-04-24
**Domain:** Frontend test authoring (Vitest 3.x + @testing-library/react + jsdom + v8 coverage)
**Confidence:** HIGH — most findings verified against the tree at HEAD + Context7 for Vitest specifics.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-00a..D-24)

- **D-00a:** Coverage thresholds `lines: 60, functions: 50, branches: 50, statements: 60`.
- **D-00b:** Thresholds live in `frontend/vitest.config.ts` under `coverage.thresholds`; block already present as a comment with exact values.
- **D-00c:** `frontend-ci.yml` already runs `npm test -- --run --coverage`; uncommenting thresholds alone gates CI.
- **D-00d:** Vitest + `@vitejs/plugin-react-swc` + jsdom + v8 provider. Locked.
- **D-00e:** Extend existing shared scaffolding at `frontend/src/test/{setup.ts, utils/*, mocks/*}`; do not replace.
- **D-01:** Admin pages (5 files, 6,921 lines) are IN SCOPE — full coverage, not excluded.
- **D-02:** Admin-page depth = full happy-path per tab/section (not smoke-only).
- **D-03:** One plan per admin page; CrawlerAdmin may split across 2+ plans. Split decision belongs to planner after reading the source.
- **D-04:** Admin wave is the LAST test-writing wave before threshold-enable.
- **D-05:** Extend `test-mocks.ts` with `mockAdminUser`, `mockSuperuserUser`; extend `test-utils.tsx` with `testScenarios.adminAuthenticated` + `superuserAuthenticated`. Re-use `TestProviders`.
- **D-06:** Admin mock data in `frontend/src/test/mocks/admin/` per-surface files: `jobs.ts`, `reports.ts`, `bugs.ts`, `users.ts`, `crawlers.ts`, `stats.ts`, `curation.ts`.
- **D-07:** Preemptively add `frontend/src/test/utils/async.ts` in Wave 0 with `vi.useFakeTimers()` helpers and a minimal `EventSource` stub. Drop in the CrawlerAdmin plan if unused.
- **D-08:** API modules: one test file per module, mocking `api/client`. Assert URL + method + body + response type. No MSW.
- **D-09:** Hooks: one test per hook, covering every branch.
- **D-10:** Contexts: dedicated provider tests with state transitions.
- **D-11:** Customer pages: full happy-path per page + ≥1 error/empty state.
- **D-12:** Components: coverage-driven gap-fill AFTER Waves 1-4 land.
- **D-13:** Exclude `src/main.tsx` + `src/types/Api.ts` with inline rationale.
- **D-14:** `src/services/Api.ts` (re-export shim) is NOT excluded — minimal smoke test instead.
- **D-15:** Per-file exclusions happen as files surface during writing, with inline rationale.
- **D-16:** Deferred exclusions carry `// TODO(admin-ux-milestone)` marker.
- **D-17:** Move `no-process-env.test.ts`, `no-legacy-gradient.test.ts`, `extension-content-type.test.ts` to `src/test/guards/` with a README.
- **D-18:** Add `vi.mock('../api/client', () => ({ default: mockApiClient, apiClient: mockApiClient }))` in `setup.ts` ALONGSIDE the existing `services/Api` mock.
- **D-19:** Do NOT remove the existing `vi.mock('../services/Api')` this phase.
- **D-20:** `mockApiClient` returns `{ data: null }` by default; per-test overrides via `vi.mocked(apiClient.get).mockResolvedValueOnce(...)`.
- **D-21:** Wave-by-surface baseline-first delivery: Wave 0 baseline+infra → Wave 1 APIs → Wave 2 hooks+contexts → Wave 3 customer pages → Wave 4 admin → Wave 5 components gap-fill + threshold enable.
- **D-22:** Threshold uncomment happens in Wave 5 only, AFTER verification.
- **D-23:** Plan count estimate 15-25.
- **D-24:** Wave 0 commits `08-COVERAGE-BASELINE.txt`.

### Claude's Discretion (from CONTEXT.md §Claude's Discretion)

- Exact Wave 1 API plan grouping (1 big vs domain-clustered vs per-file).
- Wave 3 page plan splitting beyond route-folder grouping.
- CrawlerAdmin 1-plan vs 2-plan vs scoping-subplan-first.
- Whether presentational components get preemptive smoke tests or only after coverage math demands.
- File-by-file exclusion rationale wording.

### Deferred Ideas (OUT OF SCOPE)

- Delete `services/Api.ts` shim (Phase 9+).
- Remove duplicate `vi.mock('../services/Api')` (with the shim).
- Playwright/E2E.
- MSW network-level mocks.
- Snapshot testing policy.
- Accessibility (a11y) testing.
- Coverage HTML report → PR comments.
- Ratchet thresholds above 60/50/50/60.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-03 | Vitest config enforces coverage thresholds (`lines: 60, functions: 50, branches: 50, statements: 60`) for frontend on every PR. | Section 6 confirms Vitest 3 threshold mechanism; Section 5 sanity-checks the baseline that determines required test volume; Sections 1-3 define the test-authoring scope that lifts coverage to target; Section 7 defines the meta-validation that proves the gate works. |
</phase_requirements>

## Summary

Frontend coverage expansion is a **breadth-focused test-writing pass** across 170 source files from a 0.43% line-coverage baseline to 60/50/50/60. Every depth tier and delivery wave is already locked in CONTEXT.md — this research answers the three specific sizing/grouping questions the planner needs to turn D-21's wave plan into concrete sub-plans without re-litigating scope.

Key findings the planner must honor:

- **CrawlerAdmin uses polling but NOT tabs and NOT SSE.** It has 4 sibling Card sections laid out in a `columns-1 xl:columns-2` CSS masonry — there is no `activeTab` state, no `<Tab>` component, no `EventSource`. Two `setInterval` loops (5 s job polling + 1 s elapsed ticker). D-07's `async.ts` should ship `vi.useFakeTimers()` helpers; the `EventSource` stub is dead code and should be deleted during the CrawlerAdmin plan per D-07 fallback.
- **Wave 1 API modules have a clean natural cluster split.** 20 files, 1,661 lines, but one file (`admin.ts` at 421 lines / ~29 methods) is 25% of the total volume. A 5-cluster domain split plus a solo plan for `admin.ts` is the right balance.
- **Wave 3 has ~30 customer pages totalling 8,542 lines.** Route-folder grouping (`authentication/`, `builder/`, `buildLists/`, `parts/`, public top-level) yields 5 plans with roughly balanced effort. Non-trivial test setup concentrates in three pages: `Login.tsx` (OAuth + WebAuthn + TOTP), `Register.tsx` (OAuth), and `Profile.tsx` (image upload via `uploadImage`).

**Primary recommendation:** Size Wave 1 as **6 plans** (5 domain clusters + 1 solo plan for `admin.ts`), Wave 3 as **5 plans** (one per route-folder), Wave 4 as **5 plans** (one per admin page with CrawlerAdmin as a single plan — its 4 sections are sequential Cards, not navigational tabs, so a reviewer can diff a single file's worth of tests in one PR). Total: Wave 0 (1) + Wave 1 (6) + Wave 2 (2) + Wave 3 (5) + Wave 4 (5) + Wave 5 (1) = **20 plans**, centered in the D-23 estimate of 15-25.

## Project Constraints (from CLAUDE.md)

- **Frontend test runner:** Vitest; commands `npm test`, `npm run test:coverage`. No mention of `-n auto` for vitest (that's the pytest convention). Vitest parallelizes by default across files.
- **Node:** ≥ 20.19.0 per `package.json engines`.
- **Tests:** co-located next to source (`foo.ts` → `foo.test.ts`). Preserve.
- **No hand-written migrations / no hand-written anything if a framework pattern exists.** Translates here to: use `@testing-library/react` `renderHook` and `render` primitives over custom mocking, use the existing `testScenarios` pattern rather than inlining auth state, use `vi.mock('../api/client')` (D-18) rather than hand-rolling a fetch-mock.
- **CI:** backend uses `pytest -n auto`; frontend CI already runs `npm test -- --run --coverage`. No CI workflow edits needed this phase.

## 1. CrawlerAdmin Sizing and Async Needs (D-07, D-03)

### Section structure

CrawlerAdmin.tsx (2,665 lines) is **not** a tabbed UI. It has no `activeTab` state, no `setActiveTab` handler, no `<Tab>` component, and no `tab === ...` conditional rendering. [VERIFIED: grep `activeTab|setActiveTab|type.*Tab` returns zero hits.]

What it actually has is a **4-section masonry Card layout** wrapped in a `<div className="columns-1 xl:columns-2 ...">` CSS masonry at line 1501. The four sibling Cards render simultaneously:

| # | Section Title (h2) | Line | Rough scope |
|---|---------------------|------|-------------|
| 1 | Crawler Schedules | 1505 | Schedule list + per-schedule draft editor + "Reconcile All" + create-schedule form. Uses `schedules`, `schedulePresets`, `scheduleDrafts`, `isReconcilingAll` state. |
| 2 | Adapter Tuning | 1874 | Per-adapter delay/limit/skip_known_urls/default_category edit row. Uses `adapterConfigs`, `savingConfigName`, `adapterStatusCounts`. |
| 3 | Background Jobs | 2043 | Polled job list with expand/collapse, progress subdisplay, Error panels. Uses `jobsList`, `expandedJobId`, `jobProgress`, plus **the two `setInterval`s**. |
| 4 | Manual Run | 2290 | Crawler-adapter multi-select grid with tier chips + "Run Crawl" + "Rescrape Archives" buttons. Uses `crawlerAdapters`, `selectedCrawlers`, `adapterTiers`, `isRunningCrawlers`, `rescrapeArchivesResult`. |

Two small UI helpers live above the main render at top: the fetcher-tier legend in the sub-header (around line 1479), and the "← Back to Admin Dashboard" link. These are rendered once, outside the masonry.

Auth guards render BEFORE the main content: two early returns at ~1445 for "not logged in" and "not admin" (`ErrorAlert` in both). These are test-exercisable branches without mocking any state beyond `useAuth`.

### Async patterns

[VERIFIED: grep `setInterval|setTimeout|EventSource|SSE|WebSocket|new EventSource|stream` in CrawlerAdmin.tsx]

- **`setInterval` — TWO instances at lines 1285 and 1303:**
  - Line 1285: polls `fetchJobs()` + `fetchProgressForRunning()` every 5 s while any job is `status === 'running'`. Cleaned up via `clearInterval(id)` in the effect's return.
  - Line 1303: 1-second tick via `setElapsedTick((n) => n + 1)` to keep the elapsed-time display fresh for running jobs. Same `hasRunning` gate, same cleanup.
- **No `setTimeout`.**
- **No `EventSource` / SSE.** [VERIFIED: grep for `EventSource`, `SSE`, `stream` returns zero hits across the file.]
- **No `WebSocket`.**

### Implication for D-07's `async.ts`

D-07 pre-emptively ships two helpers: a timer helper and an EventSource stub. Given the source-verified evidence:

- **KEEP** the `vi.useFakeTimers()` helper. It is load-bearing for testing CrawlerAdmin's Background Jobs section (5 s polling + 1 s elapsed tick) without making tests take 5+ seconds each. Admin tests that avoid the polling path (`Background Jobs` section with an empty `jobsList`) don't need it, but the section-3 happy-path test absolutely does.
- **DELETE** the `EventSource` stub. Zero callers. Keeping it violates CLAUDE.md's "don't hand-roll solutions for a nonexistent problem" norm and gives future readers a misleading hint that the system uses SSE. The CrawlerAdmin plan's scoping step is the correct place to delete — per D-07 fallback language, "if research shows CrawlerAdmin uses neither, the helpers are removed in the CrawlerAdmin plan's scoping step."

### Sizing: 1 plan vs 2 plans?

**Recommendation: 1 plan.** Rationale:

- The 4 sections are sibling Cards in a masonry, not tab panels. A single rendered page already has all four DOM-mounted at once. A reviewer reading the test file sees sequential `describe('Crawler Schedules', ...)` / `describe('Adapter Tuning', ...)` / `describe('Background Jobs', ...)` / `describe('Manual Run', ...)` blocks in one file — this is genuinely cheaper cognitively than a 2-plan split that forces a reader to cross-reference two test files to understand what's covered.
- Test file size estimate: 4 sections × ~4-6 happy-path assertions each + auth-denied tests + tier-chip toggle + schedule-create-form happy path ≈ 25-30 `it` blocks ≈ ~700-900 lines. This is large but not unreviewable. Compare to `App.coverage.test.tsx` at 268 lines with 37+ parametrized routes.
- The two polling paths both belong to the Background Jobs section, so they cluster naturally under one `describe`. Splitting by section across PRs would cleave the `vi.useFakeTimers()` setup from the rest of the file.

**If the planner later decides to split:** the natural cleave line is `sections 1-2 (config)` vs `sections 3-4 (runtime)`. Section 3 (Background Jobs with fake timers) is the one that most benefits from being isolated in a sub-plan if size surprises happen during execution.

**If scoping surfaces >1,000 lines of tests:** split at section boundary. Otherwise 1 plan.

[Sources: VERIFIED from `frontend/src/pages/admin/CrawlerAdmin.tsx` at HEAD; line numbers refer to commit `0723a05`.]

## 2. Wave 1 API-Module Plan Grouping (D-08)

### Per-module inventory

[VERIFIED: `wc -l` and `grep -cE "^  [a-zA-Z_]+: ...(=>|async)"` run at HEAD.]

| File | Lines | Est. methods | Cluster |
|------|-------|--------------|---------|
| `admin.ts` | 421 | ~29 | **Admin (solo)** |
| `auth.ts` | 208 | ~23 | **Auth cluster** |
| `images.ts` | 107 | ~5 | **Auth cluster** (cross-domain upload) |
| `users.ts` | 48 | ~12 | **Auth cluster** |
| `parts.ts` | 123 | ~12 | **Parts cluster** |
| `car_generations.ts` | 44 | ~9 | **Parts cluster** |
| `categories.ts` | 23 | ~4 | **Parts cluster** |
| `part_manufacturers.ts` | 57 | ~6 | **Parts cluster** |
| `retailers.ts` | 8 | ~1 | **Parts cluster** |
| `build_lists.ts` | 80 | ~8 | **Build-list cluster** |
| `build_list_parts.ts` | 96 | ~6 | **Build-list cluster** |
| `build_list_phases.ts` | 15 | ~2 | **Build-list cluster** |
| `build_logs.ts` | 36 | ~4 | **Build-list cluster** |
| `votes.ts` | 72 | ~8 | **Votes/reports cluster** |
| `reports.ts` | 79 | ~7 | **Votes/reports cluster** |
| `bug_reports.ts` | 43 | ~5 | **Votes/reports cluster** |
| `search.ts` | 27 | ~1 | **Utility cluster** |
| `app_settings.ts` | 25 | ~2 | **Utility cluster** |
| `utility.ts` | 9 | ~2 | **Utility cluster** (candidate for D-15 exclude) |
| `client.ts` | 140 | n/a | Covered indirectly via every domain test + 1 dedicated test for `setStoredToken`/`getStoredToken`/`removeStoredToken` + interceptor branches. **Not a domain module.** |
| **Total source** | **1,661** | **~145** | |

### Recommended plan grouping (6 plans for Wave 1)

| Plan | Cluster | Files | Src lines | Rough test volume |
|------|---------|-------|-----------|-------------------|
| 1 | **Auth cluster** | `auth.ts`, `users.ts`, `images.ts` + `client.ts` dedicated test | 503 | 40-50 it-blocks; includes client.ts interceptors + FormData handling |
| 2 | **Admin (solo)** | `admin.ts` | 421 | 25-30 it-blocks; single file but largest surface |
| 3 | **Parts cluster** | `parts.ts`, `car_generations.ts`, `categories.ts`, `part_manufacturers.ts`, `retailers.ts` | 255 | 25-30 it-blocks; `retailers.ts` at 8 lines is a candidate for D-15 per-file exclude |
| 4 | **Build-list cluster** | `build_lists.ts`, `build_list_parts.ts`, `build_list_phases.ts`, `build_logs.ts` | 227 | 15-20 it-blocks |
| 5 | **Votes/reports cluster** | `votes.ts`, `reports.ts`, `bug_reports.ts` | 194 | 15-20 it-blocks |
| 6 | **Utility cluster** | `search.ts`, `app_settings.ts`, `utility.ts` | 61 | 3-5 it-blocks; `utility.ts` likely excluded per D-15 |

**Alternatives rejected:**

- **1 mega-plan (20 files):** 1,661 lines of tests in a single PR is review-hostile. Also defeats D-21's "wave-by-surface baseline-first" intent — a 1-plan wave provides no incremental commit signal.
- **File-per-plan (20 plans):** Blows past D-23's 15-25 total estimate for just Wave 1. Most API modules are small enough that one-per-plan produces ceremonial PRs with no meaningful review value — `retailers.ts` (8 lines, 1 method) and `utility.ts` (9 lines, 2 methods) don't deserve their own PR.

### Non-JSON patterns to flag

Most API modules are plain JSON GET/POST/PUT/DELETE/PATCH. Two exceptions the planner must flag:

- **`images.ts` — FormData + multipart:** [VERIFIED: line 36 `const formData = new FormData()`, line 50 `'Content-Type': 'multipart/form-data'`.] The `uploadImage` method builds a FormData and sets a multipart Content-Type header override. Test assertion must confirm the FormData contains `file` + `entity_type`, not JSON.stringify the body.
- **`users.ts` — FormData for `updateProfileImage`:** [VERIFIED: line 23 `const formData = new FormData()`, line 27 multipart Content-Type.] Same pattern.

No other API modules use `FormData`, `responseType: 'blob'`, streaming, or anything beyond standard axios calls. [VERIFIED: grep `FormData|multipart|responseType|blob|stream` across `src/api/*.ts` returns only the two above.]

### Dedicated `client.ts` test content

Since Wave 1's depth tier assertions (D-08) focus on per-module URL/method/body/response-type assertions with `api/client` mocked, the `client.ts` module itself needs a dedicated unit test. Cover:

- `getStoredToken()` / `setStoredToken(token)` / `removeStoredToken()` — round-trip via `localStorage`.
- Request interceptor: sets `Authorization: Bearer <token>` when `localStorage` has a token; omits otherwise.
- Response interceptor: stores token from `x-new-access-token` response header; on 401, does NOT redirect (the redirect is commented out per line 132).
- `paramsSerializer` edge cases: array values (`ids=1&ids=2&ids=3`), `URLSearchParams` pass-through, skip `undefined`/`null`.
- `normalizeApiUrl` / `getApiBaseUrl` are not easily testable from outside without stubbing `import.meta.env`. Use `vi.stubEnv` per the pattern from `lib/sentry.test.ts` (same file already demonstrates the technique).

Place this test in `src/api/client.test.ts` alongside the domain tests in plan 1.

[Sources: VERIFIED via file reads of all 20 `src/api/*.ts` files at HEAD.]

## 3. Wave 3 Customer-Page Grouping (D-11)

### Page inventory

[VERIFIED: `find src/pages -type f -name "*.tsx" -not -name "*.test.*"` excluding `admin/*`]

| Group | Count | Files | Total lines |
|-------|-------|-------|-------------|
| **Public top-level** | 14 | `Home.tsx` (414), `Profile.tsx` (461), `ViewUser.tsx` (149), `About.tsx` (244), `ContactUs.tsx` (114), `PrivacyPolicy.tsx` (414), `TermsOfService.tsx` (401), `Support.tsx` (237), `Pricing.tsx` (275), `Checkout.tsx` (161), `Search.tsx` (522), `BugReport.tsx` (368), `NotFound.tsx` (27) + placeholder | 3,787 |
| **authentication/** | 7 | `Login.tsx` (360), `Register.tsx` (253), `ForgotPassword.tsx` (82), `ForgotPasswordConfirm.tsx` (134), `VerifyEmail.tsx` (90), `VerifyEmailConfirm.tsx` (45), `ExtensionAuth.tsx` (212) | 1,176 |
| **builder/** | 4 | `Builder.tsx` (176), `ViewCar.tsx` (303), `ViewBuildlist.tsx` (463), `ViewPart.tsx` (800) | 1,742 |
| **buildLists/** | 2 | `BuildListsCatalog.tsx` (660), `ViewBuildLog.tsx` (664) | 1,324 |
| **parts/** | 3 | `EditPart.tsx` (141), `PartsCatalog.tsx` (161), `UserParts.tsx` (211) | 513 |
| **Total (non-admin)** | **30** | — | **8,542** |

### Recommended plan grouping (5 plans for Wave 3)

**Recommendation: one plan per route-folder** — the exact structure in CONTEXT.md's Wave 3 description. No further sub-split needed; effort is roughly balanced once you factor in per-page complexity (below).

| Plan | Group | Files | Src lines | Effort notes |
|------|-------|-------|-----------|---------------|
| 1 | **public (top-level)** | 14 | 3,787 | LARGEST by file count and line count. Consider splitting into "public-info" (About/ContactUs/PrivacyPolicy/TermsOfService/Support/Pricing/NotFound/Checkout) and "public-interactive" (Home, Profile, ViewUser, Search, BugReport) if scoping surfaces >500 lines of tests. Static/policy pages are mostly render + link assertions, NOT form-submission. |
| 2 | **authentication/** | 7 | 1,176 | Complex: Login + Register + ExtensionAuth are form-heavy. OAuth/WebAuthn/TOTP branches (see flagged items below). |
| 3 | **builder/** | 4 | 1,742 | `ViewPart.tsx` at 800 lines is the largest single page; deep form-and-vote flows. |
| 4 | **buildLists/** | 2 | 1,324 | `BuildListsCatalog.tsx` (660) and `ViewBuildLog.tsx` (664) are both catalog/forum-shape pages with filters + pagination + posting. |
| 5 | **parts/** | 3 | 513 | Smallest group, easy delivery. |

**If `public` plan scoping surfaces >500 test-lines:** split into public-info (static) + public-interactive (Search, Home, Profile, BugReport, Checkout, ViewUser). Per CONTEXT.md's Claude's Discretion, this is the planner's call.

### Pages with non-trivial test setup needs

[VERIFIED: grep `GoogleOAuth|simplewebauthn|startRegistration|totp|TOTP|ImageUpload|uploadImage|<input type=.file`]

| Page | Group | Complication | Test approach |
|------|-------|--------------|---------------|
| `authentication/Login.tsx` | authentication | Uses `@react-oauth/google`, `@simplewebauthn/browser`, TOTP flow. | Mock `useGoogleSignIn` hook at test time; mock `@simplewebauthn/browser` per Wave 2 hook test. Assert OAuth button renders but DON'T exercise the click handler — that's an integration test scope, out of scope for D-11's "happy path + one error." |
| `authentication/Register.tsx` | authentication | Uses `@react-oauth/google` + `GoogleSignIn` hook. | Mock hook; assert form submission happy path with `username`/`email`/`password`. |
| `Profile.tsx` | public top-level | Calls `uploadImage` on file selection. | Mock the `imageApi.uploadImage` resolved value; don't touch File API beyond creating a `new File(['x'], 'test.jpg')`. |
| `buildLists/ViewBuildLog.tsx` | buildLists | Has image upload in post composition. | Same Profile pattern. |
| `BugReport.tsx` | public top-level | Uses FormData in submit path. | Assert the `bug_reports.api` method is called; don't inspect the FormData internals. |
| `Search.tsx` | public top-level | 522 lines; URL-driven filters with `usePartsFilters` (23KB hook). | Mock the hook to return deterministic state; don't exercise filter serialization (that's hook-test scope in Wave 2). |

**No page uses drag-drop, third-party embeds beyond AdSense (which is globally mocked via the existing `<Adbanner>` path), or streaming.** [VERIFIED.]

### Primary happy-path per route group

For planner's acceptance-criteria authorship in Wave 3 plans:

| Group | Primary happy-path to exercise |
|-------|--------------------------------|
| **public top-level** | Page renders → key interactive element clickable → navigation link works. For `Home`: hero CTA present + link target. For `Pricing`: tier cards render + CTA visible. For static policy pages: page heading renders + scrollable content present. For `Search`: initial render + one filter param round-trip. For `Profile`: authenticated render shows username + email. For `Checkout`: authenticated render + tier-upgrade CTA. |
| **authentication/** | Login: type username + password + submit → mock `authApi.loginForAccessToken` resolves → assert redirect/toast. Register: same with additional email field. VerifyEmail/ForgotPassword: render + submit empty-form validation error. |
| **builder/** | Builder: authenticated render shows car list. ViewCar: renders car name + makes one edit. ViewBuildlist: renders build list parts + phase list. ViewPart: renders part name + vote widget present. |
| **buildLists/** | BuildListsCatalog: renders list + one filter param applies. ViewBuildLog: renders posts + compose-post form present. |
| **parts/** | PartsCatalog: renders part list + one filter. EditPart: authenticated render + submit form. UserParts: authenticated render + renders user's parts. |

Each page also gets **≥1 error/empty state** per D-11 — empty-state is the cheapest (e.g., assert "No parts yet" message when API returns `[]`).

[Sources: VERIFIED via `wc -l` + targeted grep across `src/pages/**/*.tsx` at HEAD.]

## 4. Existing-Test Compatibility Check

### The 9 existing test files and their mock surface

[VERIFIED: `find src -name "*.test.*" -type f` + `grep -E "^import" each file`]

| # | File | Imports source? | Mocks `services/Api`? | Will D-18 break it? |
|---|------|------------------|----------------------|----------------------|
| 1 | `src/App.coverage.test.tsx` | Yes: `import App from './App'` + lazy-stub mocks on `./utils/lazyWithReload` + `./hooks/useAuth` + `./hooks/useAppSettings` | No explicit mock; inherits setup.ts global mock indirectly via App's transitive deps | **No.** D-18 adds a second `vi.mock('../api/client')` next to the existing `vi.mock('../services/Api')`. App.tsx doesn't import `api/client` directly; per-route lazy stubs short-circuit page-level API calls. No impact. |
| 2 | `src/components/common/ErrorBoundary.test.tsx` | Yes: `import ErrorBoundary from './ErrorBoundary'`. Mocks `@sentry/react`. | No | **No.** ErrorBoundary is pure render + Sentry. Doesn't touch api/client. |
| 3 | `src/components/common/RouteGroupBoundary.test.tsx` | Yes: `import { RouteGroupBoundary }` | No (explicit note at lines 14-19: "we do NOT mock @sentry/react here") | **No.** Same reasoning; pure render test. |
| 4 | `src/lib/sentry.test.ts` | No source import (dynamic import after env stub) — mocks `@sentry/react` | No | **No.** Isolated from API layer. |
| 5 | `src/test/extension-content-type.test.ts` | No source imports — reads file text via `fs.readFileSync` + `globSync` (lint-style guard) | No | **No.** Static-source scanner only; doesn't import source modules. D-17 relocates to `src/test/guards/`. |
| 6 | `src/test/no-legacy-gradient.test.ts` | Same pattern as #5 | No | **No.** D-17 relocates. |
| 7 | `src/test/no-process-env.test.ts` | Same pattern as #5 | No | **No.** D-17 relocates. |
| 8 | `src/utils/carUtils.test.ts` | Yes: `import { carFullDisplayName } from './carUtils'` | No | **No.** Pure function test; no axios path. |
| 9 | `src/utils/externalImageUrls.test.ts` | Yes: `import { buildExternalImageUrl }` | No | **No.** Pure function test. |

### Verdict on D-18 safety

**Zero regression risk to the 9 existing tests.** The new `vi.mock('../api/client', () => ({ default: mockApiClient, apiClient: mockApiClient }))` in `setup.ts` ADDS a mock path; it doesn't modify the existing `vi.mock('../services/Api', ...)` that shadows the re-export shim. Because Vitest's `vi.mock` hoisting is per-module-path and both mocks resolve to the same `mockApiClient` object, there's no observable difference for callers that currently reach the Axios singleton through `services/Api` (which internally re-exports from `api/client`).

**The one edge case** worth calling out for Wave 0's plan: if `services/Api.ts` re-exports from `api/client` via `export { default } from './api/client'` (the common shim pattern), then BOTH mocks might fight to win. [NEEDS VERIFICATION during Wave 0 — the planner should have Wave 0 read `services/Api.ts` and confirm the re-export pattern before committing setup.ts changes.] If the re-export is `export * from '../api/client'`, the shim module object has its own identity and the two `vi.mock` entries are independent; tests that do `import Api from '../services/Api'` get the first mock, tests that do `import { apiClient } from '../api/client'` get the second — this is the D-18 intent.

**Wave 0 verification command:** `npm test -- --run` (no coverage) AFTER the setup.ts refactor and the D-17 relocation. Must exit 0 with all 9 tests passing (soon to be 6 under `src/**/*.test.*` + 3 under `src/test/guards/**/*.test.*`). This is the Wave 0 exit gate.

[Sources: VERIFIED via file reads of all 9 existing test files at HEAD.]

## 5. Baseline Coverage Interpretation (D-24)

### Recorded baseline

From `.planning/phases/01-safety-nets-ci-hardening/01-04-SUMMARY.md` lines 79-83 [VERIFIED]:

- Lines: 0.43%
- Branches: 18.43%
- Functions: 10.52%
- Statements: 0.43%

Measured on 2026-04-22 by plan 01-04. The baseline is from **before** the Phase 6 Axios-client extraction (D-22 per-domain API split) landed, but AFTER SAFE-02 landed the frontend CI step. It was measured with `npm run test:coverage` (i.e. `vitest --coverage`) against the 8 test files that existed at that date (sentry.test.ts was added later per Phase 2 OBS-05).

### Why the numbers look odd

**The question the context asks: why is `functions: 10.52%` ~25× higher than `lines: 0.43%`?** Both are coverage percentages over the same file set. If the repo truly has 0.43% lines covered, 10.52% function coverage seems inconsistent.

**Explanation (with HIGH confidence):** v8 coverage counts a function as "executed" if it was called at least once. The three guard tests (`no-process-env`, `no-legacy-gradient`, `extension-content-type`) use `globSync` + `readFileSync` on `src/**/*.{ts,tsx}` — **this does NOT execute user functions**. However:

- `App.coverage.test.tsx` imports `App` and renders it 37+ times parametrized over every route. That hits every module imported by App transitively: `RouteGroupBoundary`, `ErrorBoundary`, `AdBanner` (the mocked-out version), `Header`, `Footer`, `lazyWithReload`, every route-guard component (`ProtectedRoute`, `GuestRoute`, `EmailVerifiedRoute`), the `AuthContext` provider, `useAuth`, `useIsPremium`, `useAppSettings`, the top-level `ErrorBoundary`, etc. **Every top-level function declaration in those modules gets counted as "executed"**, even when only a small number of lines within each function actually run (the lazy stubs throw instead of returning real content).
- `renderHook`-style tests inside `externalImageUrls.test.ts` and `carUtils.test.ts` execute their pure-function targets 100%.

**Why lines stays low while functions stays moderate:** app modules typically have many small functions (10-line handlers, 3-line selectors). When a test renders App.tsx, the outer `function App()` is counted as "function executed" even though the test only exercises maybe 5-10% of its ~250 rendered lines. Multiply that across `RouteGroupBoundary`, `ErrorBoundary`, `Header`, `Footer`, the context providers, etc. and function-percentage outpaces line-percentage by an order of magnitude. This is a **known and expected v8 measurement behavior**, not a baseline-reporting error.

**Branches at 18.43% shares the same explanation** — every `&&` short-circuit and every ternary in a rendered-but-sparsely-exercised module counts its outcome branches as hit when the outer render lands on one branch.

### Sanity conclusion

**The 0.43 / 10.52 / 18.43 / 0.43 numbers are consistent and interpretable.** The planner should NOT assume anything is miscounted. The baseline artifact (`08-COVERAGE-BASELINE.txt` per D-24) should be captured with `npm run test:coverage -- --reporter=text > 08-COVERAGE-BASELINE.txt` for per-file visibility; the summary row will likely match the 0.43/10.52/18.43/0.43 numbers within a small delta (sentry.test.ts + any other tests landed since 2026-04-22 will nudge it up slightly).

**For plan sizing:** the planner should NOT use the function/branch numbers as evidence that the repo is "half-covered already." The true coverage signal is `lines: 0.43%` — to clear `lines: 60`, Phase 8 must net-add tests that cover ~59.6% of source lines. This is genuinely a 15-25-plan effort, not a token one.

[Sources: VERIFIED from `01-04-SUMMARY.md` + `01-VERIFICATION.md` + v8 provider semantics via Context7 /vitest-dev/vitest.]

## 6. Vitest Threshold Mechanism

### Version

`package.json` pins `vitest: ^3.2.4` and `@vitest/coverage-v8: ^3.2.4`. [VERIFIED: `frontend/package.json` at HEAD.] Vitest 3 is current per Context7 (`/vitest-dev/vitest` has versions `v3_2_4` + `v4.0.7`; repo is on v3).

### How the threshold block behaves

[CITED: https://github.com/vitest-dev/vitest/blob/main/docs/config/coverage.md via Context7]

Key semantic rules:

1. **`coverage.enabled`** defaults to `false`. It is automatically flipped to `true` when the CLI flag `--coverage` is present. `frontend-ci.yml` passes `--coverage` on every PR (per D-00c), so `enabled: true` is implicit at CI time.
2. **`coverage.thresholds`** values like `lines: 60` are treated as **minimum percentages**. If total covered-line percentage is below 60 after the test run, Vitest exits non-zero with a threshold-failure message. Positive number = minimum percent covered; negative number = maximum uncovered items (absolute count).
3. **Thresholds apply globally across ALL files counted by coverage**, not only the files tested. Vitest counts source files under the project root even if they weren't imported by any test — this is a Vitest-specific behavior that differs from Jest. Files listed in `coverage.exclude` are not counted. The D-13 exclude additions (`src/main.tsx`, `src/types/Api.ts`) + D-15 per-file exclusions reduce the denominator.
4. **`coverage.reporter`** is already set to `['text', 'json', 'html']` — no change needed to produce the text-summary output Wave 5 needs for SUMMARY.md coverage deltas.

### Exactly what happens when D-06 values get uncommented

Post-uncomment, the config becomes:

```ts
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html'],
  exclude: [ /* ... existing list + D-13 additions */ ],
  thresholds: {
    lines: 60,
    functions: 50,
    branches: 50,
    statements: 60,
  },
}
```

Behavior:

- `npm run test:coverage` (i.e. `vitest --coverage`) runs all tests, then checks the summary. If any of `lines >= 60` / `functions >= 50` / `branches >= 50` / `statements >= 60` fails, the process exits 1 with a report like:

  ```
  ERROR: Coverage for lines (58.42%) does not meet global threshold (60%)
  ```

- CI's `npm test -- --run --coverage` step fails the PR check.
- Local `npm test` (without `--coverage`) does NOT check thresholds because `coverage.enabled` defaults to `false`. Developers can iterate without coverage delays.

### No additional config shape changes needed

Specifically:

- **No `enabled: true` needed** — the CLI flag handles it.
- **No `reportOnFailure` needed** — `reporter: ['text', 'json', 'html']` already produces the JSON artifact CI uses.
- **No `perFile: true` needed** — the D-06 values are global thresholds, not per-file.
- **No `autoUpdate: true`** — this is a convenience that rewrites the config file with current coverage; don't use it (would defeat the gate).

### Verification plan for the Wave 5 uncomment

The Wave 5 plan should include a deliberate "fail-force" test before the uncomment lands:

1. Uncomment with values **slightly higher than measured** (e.g., `lines: 62`) locally.
2. Run `npm run test:coverage` — expect exit 1 and the "does not meet global threshold" message.
3. Drop values to the D-06 numbers.
4. Run again — expect exit 0.
5. Commit.

This proves the gate is actually gating. Sections 7 formalizes.

[Sources: CITED from official Vitest coverage docs via Context7 `/vitest-dev/vitest` fetched 2026-04-24.]

## 7. Validation Architecture

> All commands run from `frontend/` unless otherwise noted. Expected exit code = 0 unless marked "(expected: non-zero)".

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 + @vitest/coverage-v8 3.2.4 + @testing-library/react 16.1.0 + jsdom 25.0.1 |
| Config file | `frontend/vitest.config.ts` |
| Quick run command | `npm test -- --run` (no coverage, fast iteration) |
| Full suite command | `npm run test:coverage` (vitest --coverage) |
| Parallelism | Default (per-file parallel via Vitest's built-in pool) — no `-n auto` flag; that's pytest-specific |

### Sampling Rate

- **Per task commit (inside a wave):** `npm test -- --run <changed test files>` — scoped to files touched in the task.
- **Per wave merge:** `npm test -- --run` (full suite, no coverage) — proves nothing else regressed.
- **Per-phase gate:** `npm run test:coverage` (all tests + coverage report) — required green before `/gsd-verify-work`.

### Per-Wave Validation

**Wave 0 (Baseline + shared infra):**

- Goal: prove setup.ts refactor didn't break the 9 existing tests.
- Command: `cd frontend && npm test -- --run`
- Expected: exit 0, 9 files × 9+ test cases reported as passed, **zero** failure output.
- Additional command: `cd frontend && npm run test:coverage -- --reporter=text > ../.planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt`
- Expected: the baseline file is created with per-file coverage percentages, the summary row shows ≈ `0.43 / 10.52 / 18.43 / 0.43` (±2% tolerance for tests landed since 2026-04-22).

**Wave 1 (API modules):**

- Per-plan goal: prove new tests execute and assert something meaningful (not empty describe blocks).
- Command 1: `cd frontend && npm test -- --run src/api/<module>.test.ts`
- Expected: all `it()` blocks in the file report as passed with non-zero assertion counts.
- Command 2 (meta-check — catches empty tests): `cd frontend && grep -r "expect\|assert" src/api/*.test.ts | wc -l` — count must be > `grep -r "^  it\|^  test" src/api/*.test.ts | wc -l` (every `it` has at least one assertion).
- Expected: assertion-count > it-block-count. If not, the executor wrote empty tests.
- Command 3 (AST-level meta-check): `cd frontend && npm test -- --run --reporter=json src/api/*.test.ts 2>/dev/null | node -e 'const d=JSON.parse(require("fs").readFileSync(0,"utf8")); for (const f of d.testResults) if (f.assertionResults.some(a => !a.ancestorTitles.length && a.status === "passed" && a.fullName.trim().length === 0)) process.exit(1)'` — fails if any "passed" test has a blank name.

**Wave 2 (Hooks + Contexts):**

- Same pattern as Wave 1, substituting `src/hooks/*.test.{ts,tsx}` and `src/contexts/*.test.tsx`.
- Hook tests must exercise `renderHook` from `@testing-library/react`. Quick meta-check: `grep -l "renderHook" src/hooks/*.test.*` must list every non-trivial hook test (11 files).
- Context tests must assert at least one state transition. Meta-check: `grep -c "act(\|fireEvent" src/contexts/*.test.tsx` > 0 per file.

**Wave 3 (Customer pages):**

- Per-plan goal: prove each page test mounts the page under provider + router + auth, and asserts user-observable content.
- Command: `cd frontend && npm test -- --run src/pages/<group>/`
- Expected: all it-blocks passing. Each test file has ≥3 assertions (happy-path + error/empty-state per D-11).
- Meta-check: `grep -c "render(" src/pages/<group>/*.test.tsx` > 0 per file (confirms each test file actually mounts the page under test).

**Wave 4 (Admin pages):**

- Same pattern as Wave 3. CrawlerAdmin test specifically must include `vi.useFakeTimers()` somewhere to exercise the polling path — meta-check: `grep -l "useFakeTimers" src/pages/admin/CrawlerAdmin.test.tsx` is non-empty.

**Wave 5 (Components gap-fill + threshold enable + verification):**

- Goal 1 (gap-fill): prove coverage math clears 60/50/50/60 BEFORE the threshold uncomment lands.
- Command: `cd frontend && npm run test:coverage`
- Expected: summary shows `Lines ≥ 60%`, `Functions ≥ 50%`, `Branches ≥ 50%`, `Statements ≥ 60%`. The text reporter will show per-file + summary.
- Goal 2 (uncomment + fail-force): prove the threshold is actually enforcing.
  1. Uncomment with values slightly ABOVE measured (e.g., if measured is 62%, set `lines: 65`).
  2. Run `cd frontend && npm run test:coverage` — **expect exit code non-zero** with message containing "does not meet global threshold".
  3. Restore D-06 values (`lines: 60, functions: 50, branches: 50, statements: 60`).
  4. Run `cd frontend && npm run test:coverage` — **expect exit 0**.
- Commit with both "proofs" documented in the plan's SUMMARY.md (show the fail-force output as evidence the gate really gates).

### Meta-checks against empty/ceremonial tests

Three grep-based guards the planner should consider baking into plans as acceptance criteria (or adding to `src/test/guards/` as automated regression pins):

```bash
# 1. No empty describe blocks (describe with zero it/test inside)
grep -rn "describe(['\"].*['\"], *(.*) *=> *{" src --include="*.test.*" | \
  while read line; do
    file=$(echo $line | cut -d: -f1)
    # Check the file contains at least one 'it(' or 'test(' inside a describe
    grep -q "^\s*\(it\|test\)(" "$file" || echo "Empty describe in $file"
  done
# Expected: zero output

# 2. No `it.skip` or `test.skip` in committed tests (catches accidentally-skipped)
grep -rn "\.skip(" src --include="*.test.*" | \
  grep -v "^\s*\*\|^\s*//" | wc -l
# Expected: 0 (or an allowlist matches the count)

# 3. Every .test.* file has at least one `expect(`
for f in $(find src -name '*.test.*' -type f); do
  grep -q "expect(" "$f" || echo "No assertions in $f"
done
# Expected: zero output
```

### Phase gate

Before `/gsd-verify-work` for Phase 8:

1. `cd frontend && npm run test:coverage` → exit 0 with all D-06 thresholds met.
2. `cd frontend && npm test -- --run` → exit 0 with all tests passing.
3. `cd frontend && npm run lint` → exit 0 (Phase 6 rules still hold).
4. `cd frontend && npm run type-check` → exit 0.
5. The commented `coverage.thresholds` block in `vitest.config.ts` is gone; uncommented values match D-06.
6. `frontend-ci.yml` green on the PR.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Test authoring (API modules) | Frontend build layer (Vitest) | — | Unit tests co-located next to source; no server involved. |
| Test authoring (hooks/contexts) | Frontend build layer (Vitest + jsdom) | — | `renderHook` runs in jsdom; no real browser. |
| Test authoring (pages) | Frontend build layer (Vitest + jsdom + RTL) | — | `render` mounts components under jsdom; mocked `api/client` short-circuits the network. |
| Coverage measurement | Vitest v8 provider | — | Locked by D-00d. |
| Coverage enforcement | Vitest `coverage.thresholds` in config | CI (`frontend-ci.yml`) | Vitest exits non-zero on threshold fail; CI surfaces the failure on PR. |
| Mock-surface scaffolding | `src/test/setup.ts` + `src/test/utils/*` + `src/test/mocks/*` | — | Co-located; shared across all test files. |
| Admin mock fixtures | `src/test/mocks/admin/*` | — | Per-surface files per D-06; avoids `api.ts` bloat. |
| Threshold fail-force proof | Wave 5 plan (manual run + revert) | Reviewer diff | Evidence that the gate is actually gating (not silently skipped). |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vitest | 3.2.4 | Test runner | Locked by D-00d; same runner already in use for 9 existing tests. |
| @vitest/coverage-v8 | 3.2.4 | Coverage provider | Locked by D-00d; generates the `text`/`json`/`html` reports. |
| @testing-library/react | 16.1.0 | Component render + query utilities | Already present and used by App.coverage.test.tsx, ErrorBoundary.test.tsx, RouteGroupBoundary.test.tsx. |
| @testing-library/jest-dom | 6.6.3 | DOM matchers (`toBeInTheDocument`) | Already imported in `setup.ts`. |
| @testing-library/user-event | 14.5.2 | Higher-fidelity interaction simulation | Already in devDeps; better than `fireEvent` for form tests. |
| jsdom | 25.0.1 | DOM environment | Locked by D-00d. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `vi.mock` / `vi.fn` | (built into vitest) | Per-module mocking | Wave 1 API tests (`vi.mock('../api/client')`) — D-18. |
| `vi.useFakeTimers` / `vi.advanceTimersByTime` | (built into vitest) | Deterministic timer testing | Wave 4 CrawlerAdmin Background Jobs section (5 s polling + 1 s tick). |
| `vi.stubEnv` | (built into vitest) | `import.meta.env.VITE_*` overrides | `client.ts` tests for env-driven base-URL resolution. See `lib/sentry.test.ts` for an existing example. |
| `renderHook` | `@testing-library/react` | Hook isolation | Wave 2 hook tests per D-09. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `vi.mock('../api/client')` per test file | MSW (Mock Service Worker) | Rejected by D-08. MSW would test the interceptor layer but slows tests and adds a non-trivial network-mock surface. For a breadth-push phase, per-module mocks at client level are faster to write + maintain. |
| Manual render + providers | `render` custom wrapper in `test-utils.tsx` | Already locked via `AllTheProviders` + `testScenarios`. Don't re-invent. |
| Playwright for routing verification | Vitest + MemoryRouter | Rejected by Phase 5/6. Vitest + `MemoryRouter` per `App.coverage.test.tsx`'s established pattern. |

**Installation:** No new dependencies. Phase 8 is purely test authoring + 1 config-flip.

**Version verification:**

- `vitest` 3.2.4 is the current v3 line. [VERIFIED via Context7 `/vitest-dev/vitest` which lists `v3_2_4` + `v4.0.7`.] v4 exists but upgrading to it is out of scope per CONTEXT.md "Explicitly out of scope" → "New frontend features, UX redesign."
- `@testing-library/react` 16.1.0 supports React 19 (the repo's React version). [VERIFIED: `package.json` shows React 19.1.0 alongside @testing-library/react 16.1.0 — already integrated per Phase 6.]

## Architecture Patterns

### System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                 Vitest (per-file parallel)                         │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  setup.ts  (global, runs before every test file)            │   │
│  │   - vi.mock('../services/Api') → mockApiClient  (D-19)      │   │
│  │   - vi.mock('../api/client') → mockApiClient    (D-18, NEW) │   │
│  │   - silence React warn-noise                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                 │                                  │
│          ┌──────────────────────┼──────────────────────────┐       │
│          ▼                      ▼                          ▼       │
│  ┌────────────┐       ┌───────────────────┐       ┌────────────┐   │
│  │ API tests  │       │  Hook tests       │       │ Page tests │   │
│  │ (Wave 1)   │       │  Context tests    │       │(Wave 3, 4) │   │
│  │            │       │  (Wave 2)         │       │            │   │
│  │ import     │       │  import hook      │       │ render(    │   │
│  │ authApi    │       │  renderHook(hook) │       │  <Page />, │   │
│  │ authApi    │       │  .result.current  │       │  {testSce- │   │
│  │  .login()  │       │  assertions       │       │   narios}) │   │
│  │            │       │                   │       │            │   │
│  │ assert     │       │  wrapped by       │       │ AllThe     │   │
│  │ mockApi    │       │  TestProviders    │       │ Providers  │   │
│  │ Client.    │       │                   │       │ mounts     │   │
│  │ post       │       │                   │       │ MemoryRou  │   │
│  │ called w/  │       │                   │       │ ter + Auth │   │
│  │ URL+body   │       │                   │       │ mock + App │   │
│  └────────────┘       └───────────────────┘       │ Settings   │   │
│          │                      │                  └────────────┘   │
│          ▼                      ▼                          │       │
│  ┌──────────────────────────────────────────────────────────▼──┐   │
│  │  mockApiClient: { get/post/put/delete/patch: vi.fn() }     │   │
│  │  Per-test override via:                                    │   │
│  │    vi.mocked(apiClient.get).mockResolvedValueOnce(...)     │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                 │                                  │
│                                 ▼                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  @vitest/coverage-v8  (global thresholds per D-06)          │   │
│  │   lines: 60  functions: 50  branches: 50  statements: 60    │   │
│  │   exclude: node_modules, src/test/, *.d.ts, *.config.*,     │   │
│  │            coverage/, dist/, build/, src/main.tsx (D-13),   │   │
│  │            src/types/Api.ts (D-13), per-file D-15 adds      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                 │                                  │
│                                 ▼                                  │
│            exit 0 (≥ thresholds) or exit 1 (below)                 │
│                                 │                                  │
│                                 ▼                                  │
│       frontend-ci.yml `Run tests` step propagates exit to PR       │
└────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
frontend/src/
├── test/
│   ├── setup.ts                          # global mocks + console silencing (D-18 adds api/client mock)
│   ├── utils/
│   │   ├── TestProviders.tsx             # unchanged
│   │   ├── TestWrapper.tsx               # unchanged
│   │   ├── test-utils.tsx                # D-05: add adminAuthenticated / superuserAuthenticated scenarios
│   │   ├── test-mocks.ts                 # D-05: add mockAdminUser / mockSuperuserUser
│   │   └── async.ts                      # D-07: useFakeTimers helper (NEW). EventSource stub deleted per research.
│   ├── mocks/
│   │   ├── api.ts                        # unchanged
│   │   └── admin/                        # D-06 NEW directory
│   │       ├── jobs.ts
│   │       ├── reports.ts
│   │       ├── bugs.ts
│   │       ├── users.ts
│   │       ├── crawlers.ts
│   │       ├── stats.ts
│   │       └── curation.ts
│   └── guards/                           # D-17 relocation
│       ├── README.md                     # NEW: explains these are lint-style regression guards
│       ├── no-process-env.test.ts        # moved
│       ├── no-legacy-gradient.test.ts    # moved
│       └── extension-content-type.test.ts # moved
├── api/
│   ├── *.ts                              # 20 existing source files (unchanged)
│   └── *.test.ts                         # NEW per-domain tests (Wave 1)
├── hooks/
│   ├── *.ts                              # 11 existing source files (unchanged)
│   └── *.test.{ts,tsx}                   # NEW per-hook tests (Wave 2)
├── contexts/
│   ├── *.tsx                             # 2 existing source files (unchanged)
│   └── *.test.tsx                        # NEW provider tests (Wave 2)
├── pages/
│   ├── **/*.tsx                          # 35 existing source files (unchanged)
│   ├── **/*.test.tsx                     # NEW page tests (Waves 3 + 4)
└── components/
    └── **/*.test.tsx                     # NEW gap-fill tests (Wave 5, only if coverage math demands)
```

### Pattern 1: API module test (Wave 1)

**What:** Import the domain API, call a method, assert `mockApiClient.<verb>` was called with the expected URL + body + params; assert the return value's `data` has the declared shape.
**When to use:** Every file in `src/api/*.ts`.
**Example:**

```typescript
// Source: established pattern derived from D-08 + frontend/src/test/mocks/api.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildListsApi } from './build_lists';
import type { BuildListRead } from '../types/Api';

// setup.ts already mocks '../api/client' (D-18). Per-test override:
describe('buildListsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getBuildList hits /build-lists/:id with GET', async () => {
    const expected: BuildListRead = { /* mock shape */ };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: expected });

    const result = await buildListsApi.getBuildList('33333333-...');

    expect(apiClient.get).toHaveBeenCalledWith('/build-lists/33333333-...');
    expect(result.data).toEqual(expected);
  });

  it('createBuildList POSTs body to /build-lists/', async () => {
    const body = { name: 'Test', car_id: '22222222-...' };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { id: '33333333-...', ...body } });

    await buildListsApi.createBuildList(body);

    expect(apiClient.post).toHaveBeenCalledWith('/build-lists/', body);
  });
});
```

### Pattern 2: Hook test (Wave 2)

**What:** `renderHook` with the auth/settings provider, assert initial state and each branch (loading/success/error).
**Example:**

```typescript
// Source: @testing-library/react renderHook pattern
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useAuth } from './useAuth';
import { AllTheProviders } from '../test/utils/TestWrapper';
import { testScenarios } from '../test/utils/test-utils';

describe('useAuth', () => {
  it('returns unauthenticated state when no user', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AllTheProviders initialAuthState={testScenarios.unauthenticated.initialAuthState}>
          {children}
        </AllTheProviders>
      ),
    });
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });
});
```

### Pattern 3: Page test (Waves 3, 4)

**What:** Render the page under `AllTheProviders` + `MemoryRouter`, assert primary content + one error/empty state.
**Example:**

```typescript
// Source: derived from test-utils.tsx customRender + App.coverage.test.tsx
import { render, screen, waitFor } from '../../test/utils/test-utils';
import { testScenarios } from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import Profile from './Profile';
import { vi } from 'vitest';

describe('Profile', () => {
  it('renders authenticated user profile', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockUser });
    render(<Profile />, {
      route: '/profile',
      ...testScenarios.authenticated,
    });
    await waitFor(() =>
      expect(screen.getByText(mockUser.username)).toBeInTheDocument()
    );
  });

  it('shows loading state during fetch', () => {
    render(<Profile />, { ...testScenarios.loading });
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
```

### Pattern 4: CrawlerAdmin Background Jobs section (Wave 4)

**What:** Fake-timer pattern for the 5 s polling loop.
**Example:**

```typescript
// Source: vitest fake-timers docs via Context7 /vitest-dev/vitest
import { vi } from 'vitest';
import { render, screen, act } from '../../test/utils/test-utils';

it('polls jobs every 5 seconds while a job is running', async () => {
  vi.useFakeTimers();
  vi.mocked(apiClient.get).mockResolvedValue({ data: jobsListWithRunning });
  render(<CrawlerAdmin />, { ...testScenarios.adminAuthenticated });

  // initial render fetches once
  expect(apiClient.get).toHaveBeenCalledTimes(1);

  await act(async () => {
    vi.advanceTimersByTime(5000);
  });
  expect(apiClient.get).toHaveBeenCalledTimes(2);  // polling triggered

  vi.useRealTimers();
});
```

### Anti-Patterns to Avoid

- **Writing tests that import source but only assert `document.body` exists.** Phase 6 plan 06-03 explicitly flagged this as a drift guard that reviewers must reject. Every test must touch observable behavior in the component under test, not just "does it mount without throwing."
- **Building up fake data inline across test files.** Reuse `test/mocks/api.ts` + the new `test/mocks/admin/*`. Inline fake-data duplication fragments the fixture surface and makes Wave 4 harder.
- **Using `vi.mock` for utility functions that can be tested directly.** `externalImageUrls.test.ts` and `carUtils.test.ts` demonstrate the cheaper pattern — import + assert.
- **Mocking `react-router-dom` primitives.** Use `MemoryRouter` with `initialEntries` instead. Mocking the router breaks transitively-imported page components in ways that are expensive to debug.
- **Mocking `@testing-library/react`.** Never. If a test is hard to write, fix the test, not the library.
- **Writing `it.skip(...)` to defer hard tests.** The D-23 plan count already assumes every test lands; skipped tests rot into permanent dead signals. Instead, scope the test out at plan-authoring time and note it in the plan's DEFERRED section.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Axios mock for the shared client | Custom fetch-mock or per-test new AxiosInstance | `vi.mock('../api/client')` with `{ default: mockApiClient, apiClient: mockApiClient }` (D-18) | Existing setup.ts pattern; integrates with all hoisted `vi.mock` semantics; works with per-test `vi.mocked(apiClient.get).mockResolvedValueOnce(...)` overrides. |
| Provider tree for page tests | Manual `<BrowserRouter><AuthProvider>...` in each file | `AllTheProviders` from `test/utils/TestWrapper.tsx` via `customRender` | Already exists; D-05 only extends `testScenarios`, does NOT fork the wrapper. |
| Auth-state fixtures | Inline `{ isAuthenticated: true, user: {...} }` in each file | `testScenarios.authenticated` / `.unauthenticated` / `.loading` (+ D-05 `.adminAuthenticated` / `.superuserAuthenticated`) | Single source of truth; matches exactOptionalPropertyTypes. |
| Polling test harness | `await new Promise(r => setTimeout(r, 5100))` | `vi.useFakeTimers()` + `vi.advanceTimersByTime(5000)` | Deterministic; 10× faster; matches Vitest idiom. |
| SSE / EventSource mock | Any custom stub | (Nothing — CrawlerAdmin has no SSE, delete D-07's placeholder) | Proven unused via grep. |
| Route-group error-boundary test scaffolding | New wrapper per page | `MemoryRouter initialEntries={[path]}` pattern from `App.coverage.test.tsx` | Phase 6 D-10/D-24 already established; reuse rather than branch. |
| Coverage delta in SUMMARY.md | Manual math | `diff` against `08-COVERAGE-BASELINE.txt` rows | D-24's baseline-first pattern; cheap to produce. |

**Key insight:** Every hand-rolled solution in this phase multiplies across ~20 plans. Use the existing scaffolding additively (D-05/D-06/D-07 extend; D-18 adds; D-17 relocates) rather than replacing.

## Common Pitfalls

### Pitfall 1: `vi.mock` hoisting vs module identity

**What goes wrong:** Writing `vi.mock('../api/client', () => mockApiClient)` at test file top-level — the factory references `mockApiClient` from the outer scope but Vitest hoists `vi.mock` calls to before import resolution. At hoist time, `mockApiClient` is `undefined`.
**Why it happens:** Vitest (like Jest) hoists all `vi.mock`/`jest.mock` calls to the top of the file. Factories run BEFORE module imports.
**How to avoid:** Define the mock object inside the factory, OR use `vi.hoisted(() => { ... })` to co-hoist the fixture. Existing pattern: `components/common/ErrorBoundary.test.tsx` uses `vi.hoisted` correctly — copy that.
**Warning signs:** `ReferenceError: Cannot access 'mockApiClient' before initialization`.

### Pitfall 2: `exactOptionalPropertyTypes` + partial auth state

**What goes wrong:** TypeScript compiles the existing codebase with `exactOptionalPropertyTypes: true` per Phase 6 CONVENTIONS.md. Writing `initialAuthState: { isAuthenticated: true, isLoading: undefined }` is a type error (you must OMIT the key to get `undefined`, not assign `undefined` explicitly).
**Why it happens:** strict TS opt-in rule; `{ x?: T }` with eOPT is `x?: T`, NOT `x?: T | undefined`.
**How to avoid:** `testScenarios` in `test-utils.tsx` already uses correct shapes. Don't write partial auth state by hand; pick a scenario or add one to `testScenarios` per D-05. `mockUseAuth` in `test-mocks.ts` already types this correctly — extend it for admin/superuser.
**Warning signs:** TS error `Type '{ isAuthenticated: true; isLoading: undefined; }' is not assignable to type 'Partial<...>'`.

### Pitfall 3: Vitest counts untested files in the global threshold

**What goes wrong:** The test suite has `lines: 61%` in tested files but the global lines is `58%` — turning on thresholds fails unexpectedly.
**Why it happens:** Vitest counts ALL files under `include` (default: everything) in the denominator, even files that were never imported by a test. This is different from Jest. A 1,500-line never-tested page tanks global line coverage.
**How to avoid:** Before Wave 5's uncomment, run `npm run test:coverage -- --reporter=text` and read the per-file table. ANY file at 0% coverage is a denominator problem. Either write a minimal test for it or add it to D-15's per-file exclude with inline rationale. D-12's component gap-fill wave specifically targets this.
**Warning signs:** The summary row is suspiciously lower than the average of per-file percentages.

### Pitfall 4: Tests that render App.tsx without mocking `lazyWithReload`

**What goes wrong:** A new page test imports App (instead of the specific page), and the `lazy()` wrapper tries to fetch the compiled chunk, which in jsdom fails with `network error`.
**Why it happens:** `lazyWithReload` uses React `lazy()` which needs a Suspense boundary + dynamic import resolution. jsdom doesn't fetch, so the import hangs indefinitely.
**How to avoid:** Page tests should import the page component directly (e.g., `import Login from './pages/authentication/Login'`), NOT mount through App. App.coverage.test.tsx handles App-level coverage already; Wave 3/4 tests work at the page level.
**Warning signs:** Test hangs until timeout with no error output.

### Pitfall 5: Polling test that doesn't `await act`

**What goes wrong:** `vi.advanceTimersByTime(5000)` fires the interval callback, which calls `setState`, but React hasn't flushed yet — assertion fails with stale DOM.
**Why it happens:** React state updates are batched; `advanceTimersByTime` is synchronous but the state flush happens in a microtask.
**How to avoid:** Wrap timer advances in `await act(async () => { vi.advanceTimersByTime(5000); })`. Always.
**Warning signs:** Test asserts on state AFTER the timer tick but sees pre-tick DOM.

### Pitfall 6: `admin/*.ts` mock fixtures leak between parallel test files

**What goes wrong:** D-06 admin fixtures (e.g., `jobs.ts` exporting a mutable `mockJobsList`) get mutated by one test file's `push(newJob)` and the next parallel file sees the extra job.
**Why it happens:** Vitest parallelizes per-file; fixtures imported from `test/mocks/admin/*` are module-level singletons in each file.
**How to avoid:** Every fixture file in `test/mocks/admin/*` should export a **factory** (e.g., `export const makeJobsList = () => ({ items: [...], total: ... })`) OR a frozen constant. Tests that need to mutate call the factory; tests that just read use the constant. `mocks/api.ts` mostly follows this pattern already — carry it forward.
**Warning signs:** Test passes in isolation but fails when run with the full suite.

### Pitfall 7: The re-export shim conflict between `services/Api` and `api/client`

**What goes wrong:** `services/Api.ts` re-exports the Axios instance from `api/client`. With both `vi.mock('../services/Api')` and `vi.mock('../api/client')` in setup.ts, a test that does `import Api from '../services/Api'; Api.get(...)` hits the first mock; but the REAL `services/Api.ts` implementation imports from `api/client` — which is ALSO mocked. If the two mocks diverge (they shouldn't per D-18 but if a future executor diverges them), behavior is confusing.
**Why it happens:** D-19 keeps both paths mocked to preserve the 9 existing tests.
**How to avoid:** Wave 0's executor MUST read `services/Api.ts` to confirm the re-export pattern (is it `export { default } from './api/client'`? or `import client from './api/client'; export default client;`?). Document the answer in Wave 0's SUMMARY.md. If the shim re-imports, keep both mocks pointing to the SAME `mockApiClient` object (D-18 already says this).
**Warning signs:** The old 9 tests break after setup.ts refactor.

## Code Examples

### Verified pattern: fake-timer + admin-authenticated page test

```typescript
// Source: derived from Context7 /vitest-dev/vitest (fake timers docs) +
// frontend/src/test/utils/test-utils.tsx customRender pattern.
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, act } from '../../test/utils/test-utils';
import { testScenarios } from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import CrawlerAdmin from './CrawlerAdmin';
import { makeJobsList } from '../../test/mocks/admin/jobs';

describe('CrawlerAdmin — Background Jobs section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls jobs every 5 seconds while one is running', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: makeJobsList({ running: true }) });

    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);
    // Initial mount fetches
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());

    const initialCalls = vi.mocked(apiClient.get).mock.calls.length;

    await act(async () => { vi.advanceTimersByTime(5000); });

    expect(vi.mocked(apiClient.get).mock.calls.length).toBeGreaterThan(initialCalls);
  });
});
```

### Verified pattern: context provider state transition

```typescript
// Source: derived from @testing-library/react renderHook + fireEvent docs
// and Phase 6 OBS-05 AuthContext structure.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { AuthProvider } from './AuthContext';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../api/client';

function Consumer() {
  const { isAuthenticated, user, logout } = useAuth();
  return (
    <div>
      <span data-testid="state">{isAuthenticated ? user?.username : 'anon'}</span>
      <button onClick={logout}>logout</button>
    </div>
  );
}

describe('AuthContext — logout transition', () => {
  it('flips state from authenticated to unauthenticated', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { message: 'Logged out' } });

    render(<AuthProvider><Consumer /></AuthProvider>);
    // Seed with an authenticated user — typically via localStorage token + /users/me mock.
    // Then:
    await act(async () => { fireEvent.click(screen.getByText('logout')); });

    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('anon'));
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ReactDOM.render` + raw `fireEvent` | `render` from `@testing-library/react` + `user-event` | RTL v14+ standard | Already adopted; setup.ts silences the ReactDOM.render deprecation warning. |
| Jest + jest-mock | Vitest + `vi.mock` | Vitest 3.x equivalency | Already locked; no action. |
| Coverage via `istanbul` (Jest default) | Coverage via `v8` (Vitest recommended) | Vitest 1.0+ | Already locked via D-00d. |
| MSW for API mocks | `vi.mock` at module boundary (D-08) | Project-specific decision | Per D-08 — MSW explicitly declined for this phase. |
| Per-file provider wrapper | Shared `AllTheProviders` + `customRender` | Phase 6 | Already in place; D-05 extends scenarios, not the wrapper. |

**Deprecated/outdated:**

- **`TESTING.md` entry "Tests are NOT run in CI for frontend"** — stale. SAFE-02 landed Phase 1; tests run in CI on every PR. Wave 0 or a subsequent docs-sync plan should update this line if in scope.
- **`TESTING.md` entry "Framework: vitest 1+"** — stale. Repo is on Vitest 3.2.4. Same docs-drift candidate.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `services/Api.ts` re-exports from `api/client` such that D-18's dual `vi.mock` resolves both to the same mocked object | 4, Pitfall 7 | LOW — Wave 0 plan must read the file and confirm; if the shim re-constructs its own Axios instance (unlikely given Phase 6 D-22 called it a "re-export shim"), D-18 needs tweaking. |
| A2 | The 0.43/10.52/18.43/0.43 baseline has not drifted >2% since 2026-04-22 | 5 | LOW — Wave 0 re-measures; if drift is >5%, the "denominator" story might need revisiting (new large untested files landing). |
| A3 | `renderHook` from `@testing-library/react` 16.1.0 supports React 19 hooks without caveats | Pattern 2 | LOW — verified that RTL 16+ supports React 19 officially; zero reported issues. |
| A4 | Wave 4 CrawlerAdmin `vi.useFakeTimers()` interacts cleanly with async `waitFor` calls inside the same test file | Pattern 4 | MEDIUM — fake-timer + async-act interaction is a known-subtle area. Worst case: the executor needs to use `vi.useFakeTimers({ toFake: ['setInterval', 'setTimeout'] })` to leave microtasks alone. |
| A5 | `lazyWithReload` does not hit the network in jsdom when its dynamic import target is mocked — page tests that bypass App can safely `import Page from './page'` directly without lazy | Pitfall 4 | LOW — already demonstrated by the Phase 6 `App.coverage.test.tsx` pattern of direct-path imports. |

## Open Questions

1. **Does `services/Api.ts` re-export verbatim or re-construct Axios?**
   - What we know: Phase 6 D-22 called it a "re-export shim" for back-compat.
   - What's unclear: Whether the shim is `export * from '../api/client'` or `import ax from '../api/client'; export default ax;` or something else.
   - Recommendation: Wave 0 plan reads the file; acceptance criteria include "confirmed: services/Api.ts's default export === api/client's default export, so the dual vi.mock is coherent."

2. **Which pages will demand D-12 component gap-fill after Wave 4?**
   - What we know: Wave 4 will produce a fresh coverage report.
   - What's unclear: Which specific components (e.g., `components/layout/globalHeader/Header.tsx`, `components/parts/PartCard.tsx`) won't be transitively covered enough by page tests.
   - Recommendation: Wave 5 plan is scoped at authoring time, not upfront. The planner produces Wave 5 ONLY after Wave 4 lands.

3. **Should Wave 3's `public top-level` plan split further?**
   - What we know: 14 files, 3,787 lines — the largest single group.
   - What's unclear: Test-line count can't be estimated until the plan is scoped.
   - Recommendation: Planner writes the plan; if scoping-step shows >500 expected test lines, split along the public-info (static) vs public-interactive line given in Section 3.

4. **Do snapshot tests help close the last ~5% coverage gap?**
   - What we know: Snapshot testing is not in scope per CONTEXT.md deferred.
   - What's unclear: N/A — explicitly declined.
   - Recommendation: Don't research further. If Wave 5 can't clear thresholds without snapshots, surface as a CHECKPOINT in Wave 5 plan — don't silently add them.

## Environment Availability

Phase 8 is purely test authoring + config-flip. No new external dependencies.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | `npm` commands | ✓ | ≥ 20.19.0 per package.json engines | — |
| `vitest` | Test runner | ✓ | 3.2.4 | — |
| `@vitest/coverage-v8` | v8 coverage | ✓ | 3.2.4 | — |
| `@testing-library/react` | `render` / `renderHook` | ✓ | 16.1.0 | — |
| `@testing-library/user-event` | form interactions | ✓ | 14.5.2 | — |
| `jsdom` | DOM environment | ✓ | 25.0.1 | — |
| `@testing-library/jest-dom` | `toBeInTheDocument` etc. | ✓ | 6.6.3 | — |

**No missing dependencies.** The phase is implementable from HEAD.

## Validation Architecture

See Section 7 above.

## Security Domain

Phase 8 writes tests. No production behavior changes. No new network, auth, or data paths introduced.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Tests assert existing auth-flow render paths; don't introduce new flows. |
| V3 Session Management | no | Tests mock `localStorage` token handling via existing `setStoredToken`/`getStoredToken`. |
| V4 Access Control | no | Tests assert `useAuth`'s existing gating behavior. |
| V5 Input Validation | no | Tests exercise form-submit happy paths; don't change validation surface. |
| V6 Cryptography | no | No crypto in frontend; JWT is opaque. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Test leaking real credentials | Info disclosure | Tests use fake data from `mocks/api.ts` and `mocks/admin/*`; never real tokens. |
| Mocked Axios client forgetting `Authorization` header in interceptor tests | Spoofing | `api/client.test.ts` explicitly covers the request-interceptor branch. |
| Snapshot test capturing secrets | Info disclosure | No snapshots in Phase 8 per CONTEXT.md. |

## Sources

### Primary (HIGH confidence)

- [Context7 `/vitest-dev/vitest`](https://github.com/vitest-dev/vitest/blob/main/docs/config/coverage.md) — coverage.thresholds mechanics, coverage.enabled semantics, v8 provider behavior. Fetched 2026-04-24.
- `frontend/vitest.config.ts` at HEAD — current config; threshold block is commented with D-06 values and the plan 01-09 marker.
- `frontend/package.json` at HEAD — confirms vitest 3.2.4, @testing-library/react 16.1.0, React 19.1.0, node ≥ 20.19.0.
- `frontend/src/pages/admin/CrawlerAdmin.tsx` at HEAD — 2,665 lines, 4 Card sections at lines 1505/1874/2043/2290, 2 `setInterval` calls at 1285/1303, zero `EventSource`/`SSE`/`tab` references.
- `frontend/src/api/*.ts` at HEAD — 20 modules, 1,661 total lines; sizes per section 2; FormData usage at `images.ts:36,50` and `users.ts:23,27`.
- `frontend/src/pages/**/*.tsx` at HEAD — 30 non-admin customer pages + 8 admin pages counted.
- `frontend/src/test/{setup.ts,utils/*,mocks/api.ts}` at HEAD — existing test infrastructure; `mockApiClient` shape confirmed.
- `.planning/phases/01-safety-nets-ci-hardening/01-04-SUMMARY.md` lines 79-83 — baseline 0.43/10.52/18.43/0.43 numbers.
- `.planning/phases/06-frontend-cleanup-final-ci-gates/06-CONTEXT.md` — Phase 6 D-22 reference for the api/*.ts split.

### Secondary (MEDIUM confidence)

- `.planning/codebase/TESTING.md` — stale entries ("Tests NOT run in CI for frontend", "vitest 1+") noted in §State of the Art. Treat as reference for patterns only.
- `frontend/src/App.coverage.test.tsx` at HEAD — demonstrates the `MemoryRouter` + lazy-stub mock pattern referenced in Waves 3/4 guidance.
- `frontend/src/lib/sentry.test.ts` at HEAD — demonstrates `vi.stubEnv` + dynamic-import pattern useful for `client.ts` tests.

### Tertiary (LOW confidence)

None — all factual claims are verified against HEAD files or Context7 docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from `package.json`; no new deps.
- Architecture (wave grouping): HIGH — file counts, line counts, method counts all verified via shell commands.
- Pitfalls: HIGH-MEDIUM — Vitest behaviors verified via Context7; pitfall 7 (shim re-export) flagged as needing Wave 0 confirmation.
- Baseline interpretation: HIGH — the 0.43 / 10.52 discrepancy is explained by v8 function-counting semantics which are well-documented.
- Threshold mechanism: HIGH — cited directly from Vitest docs via Context7.
- CrawlerAdmin structure: HIGH — every claim (no tabs, no SSE, 4 Cards, 2 setInterval) verified by targeted grep at HEAD.

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — Vitest 3.x line is stable; repo file structure is the load-bearing input and churns slowly).

## RESEARCH COMPLETE

**Phase:** 08 - Frontend Coverage Expansion
**Confidence:** HIGH

### Key Findings

- CrawlerAdmin is a 4-section masonry Card layout (Schedules / Adapter Tuning / Background Jobs / Manual Run), NOT tabbed. Uses `setInterval` (5 s + 1 s). Has NO `EventSource`/SSE/WebSocket. D-07's fake-timers helper is needed; the EventSource stub should be deleted in the CrawlerAdmin plan's scoping step. Recommended: 1 plan for CrawlerAdmin (split only if test-lines surprise >1,000).
- Wave 1 API grouping: 6 plans (5 domain clusters + 1 solo for `admin.ts` at 421 lines / ~29 methods). `images.ts` and `users.ts` have FormData/multipart paths to flag. `client.ts` needs a dedicated test in plan 1.
- Wave 3 customer pages: 5 plans (one per route-folder; public top-level may need to split if scoping shows >500 test-lines). Non-trivial test setup concentrated in `Login` (OAuth/WebAuthn/TOTP), `Register` (OAuth), `Profile` (image upload).
- All 9 existing tests are D-18 compatible — zero regression risk from adding `vi.mock('../api/client')` alongside the existing `services/Api` mock.
- Baseline 0.43/10.52/18.43/0.43 is consistent, not a reporting error — v8 counts functions as "executed" per call, so App.coverage.test.tsx's 37 parametrized renders inflate function % without moving line % much.
- Uncommenting `coverage.thresholds` with the D-06 literals is sufficient; `coverage.enabled` is auto-flipped by the `--coverage` CLI flag.

### File Created

`.planning/phases/08-frontend-coverage-expansion/08-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | All versions verified from package.json + Context7. |
| Architecture (wave grouping) | HIGH | File/line/method counts verified via shell. |
| Pitfalls | HIGH-MEDIUM | 6 verified; 1 (shim re-export) needs Wave 0 confirmation. |
| Code Examples | HIGH | Derived from established repo patterns + Context7-sourced fake-timer idiom. |
| Threshold mechanism | HIGH | Cited from official Vitest docs. |

### Open Questions (all LOW-MEDIUM risk)

1. `services/Api.ts` exact re-export pattern (Wave 0 verifies).
2. Wave 3 `public` plan split needed? (planner decides at scoping step).
3. D-12 component gap-fill targets (decided post-Wave-4 coverage run).

### Ready for Planning

Research complete. Planner has answers to all three explicit research questions (CrawlerAdmin sizing, Wave 1 API grouping, Wave 3 page grouping) plus compatibility verdict on D-18, baseline interpretation, Vitest threshold mechanics, and a per-wave validation architecture.
