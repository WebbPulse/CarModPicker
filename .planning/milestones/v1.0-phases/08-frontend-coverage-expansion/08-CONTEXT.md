# Phase 8: Frontend Coverage Expansion (SAFE-03) - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Lift frontend test coverage from the 2026-04-22 baseline (lines 0.43% / functions 10.52% / branches 18.43% / statements 0.43%) to the D-06 targets (lines 60 / functions 50 / branches 50 / statements 60). Uncomment the `thresholds` block in `frontend/vitest.config.ts` so CI gates coverage drops on every PR. Reopens SAFE-03 which was explicitly deferred from Phase 1 plan 01-04 (Option C).

This phase is a breadth-focused test-writing pass — NOT a frontend refactor, NOT a new-feature phase, NOT a redesign. Writing tests is the only deliverable.

**Explicitly out of scope:**
- New frontend features, UX redesign, route restructuring
- Deleting `services/Api.ts` re-export shim (Phase 9+ candidate once all import sites migrate)
- Adding runtime schema validation (zod, valibot) — already declined in Phase 6 D-03
- Playwright / E2E testing — continues to be out of milestone scope
- Generated OpenAPI client — Phase 6 D-03 confirms hand-maintained types only
- Backend coverage ratcheting — separate concern; backend already has SAFE-01 floor
- Non-SAFE-03 success criteria from v1.0 milestone — all other REQUIREMENTS.md items satisfied

</domain>

<decisions>
## Implementation Decisions

### Locked inputs from Phase 1 (do not revisit)

- **D-00a:** Coverage thresholds: `lines: 60, functions: 50, branches: 50, statements: 60` (Phase 1 D-06). Locked by SAFE-03 + REQUIREMENTS.md.
- **D-00b:** Thresholds live in `frontend/vitest.config.ts` under `coverage.thresholds`. The block is already present as a comment with the exact values and a pointer to plan 01-09 — this phase uncomments it.
- **D-00c:** `frontend-ci.yml` already runs `npm test -- --run --coverage` on every PR (SAFE-02, Phase 1). Uncommenting thresholds alone makes CI gate drops; no workflow edit required for the gate itself.
- **D-00d:** Test runner: Vitest with `@vitejs/plugin-react-swc`, jsdom environment, v8 coverage provider. Locked.
- **D-00e:** Shared test scaffolding exists at `frontend/src/test/{setup.ts, utils/TestProviders.tsx, utils/TestWrapper.tsx, utils/test-utils.tsx, utils/test-mocks.ts, mocks/api.ts}`. This phase extends it; does not replace it.

### Admin-page coverage scope

- **D-01:** Admin pages (`frontend/src/pages/admin/**` — 5 files, 6,921 lines) are IN SCOPE for real coverage, not excluded. Customer surface is the top priority but admin tooling is not second-class — it gets full happy-path coverage per tab/section.
- **D-02:** Admin-page test depth: **full happy-path per tab/section** — for each admin page, enumerate every primary workflow (e.g., CrawlerAdmin has ~8 tabs/sections; each gets a happy-path test). Not smoke-only, not happy+error, not a single primary action. This is the highest-effort choice in this phase and planner must size plans accordingly.
- **D-03:** Admin-page plan sequencing: **one plan per admin page**. CrawlerAdmin (2,665 lines, multiple sections) may be split across 2+ plans if its tab count makes a single PR unreviewable. Split decision belongs to the planner after reading CrawlerAdmin.tsx. Likely plan count for admin alone: 5-8.
- **D-04:** Admin wave is the LAST test-writing wave before the threshold-enable wave. Non-admin surface (APIs, hooks, contexts, customer pages) lands first so customer coverage ratchets up before the heavier admin effort begins.

### Admin-specific test infrastructure

- **D-05:** Extend `frontend/src/test/utils/test-mocks.ts` with admin + superuser auth variants (`mockAdminUser`, `mockSuperuserUser`) and add `testScenarios.adminAuthenticated` and `testScenarios.superuserAuthenticated` in `test-utils.tsx`. Matches the existing `authenticated` / `unauthenticated` / `loading` pattern. No separate `AdminTestProviders` wrapper — re-use `TestProviders`.
- **D-06:** Admin mock data lives in `frontend/src/test/mocks/admin/` as per-surface fixture files: `jobs.ts`, `reports.ts`, `bugs.ts`, `users.ts`, `crawlers.ts`, `stats.ts`, `curation.ts`. Each exports the shapes its admin page consumes. Keeps `test/mocks/api.ts` from bloating with admin-only data.
- **D-07:** Preemptively add CrawlerAdmin-flavored async scaffolding in Wave 0 even though CrawlerAdmin tests land in Wave 4: `vi.useFakeTimers()` helpers (for any polling) and a minimal `EventSource` stub (for any SSE streaming) in `frontend/src/test/utils/async.ts`. If research shows CrawlerAdmin uses neither, the helpers are removed in the CrawlerAdmin plan's scoping step — but better to have them ready than let every admin test re-invent them ad-hoc.

### Non-admin test depth tiers

- **D-08:** API modules (`frontend/src/api/*.ts`, 20 files, 1,661 lines): one test file per module, mocking `api/client` (the shared Axios instance). Each test file asserts every exported function (a) hits the correct URL + method, (b) sends the expected body/params shape, (c) returns the declared response type (compile-time + one runtime shape assertion). No MSW dependency added. No grouped / integration-style API tests.
- **D-09:** Hooks (`frontend/src/hooks/*`, 11 files): one test file per hook, using `renderHook` from `@testing-library/react`. Cover every code branch — loading, success, error, param variations. Even thin hooks (`useDocumentMeta`, `useCookieConsent`) get a minimal test.
- **D-10:** Contexts (`frontend/src/contexts/*`, 2 files — `AuthContext.tsx`, `AppSettingsContext.tsx`): dedicated provider tests asserting state transitions (login → logout, settings update → consumers re-render, etc.).
- **D-11:** Customer-facing pages (`frontend/src/pages/**` excluding admin, ~30 files): **full happy-path per page**. For each page: mount under mocked API + router + auth, exercise the primary flow end-to-end (e.g., Login: type credentials + submit + assert redirect; PartsCatalog: render + apply filter + assert results), plus at least one error/empty state. Symmetric with the admin decision. Higher effort than the roadmap's suggested "smoke + one error path" default (deliberately chosen).
- **D-12:** Components (`frontend/src/components/**`): **coverage-driven gap-fill** only. After APIs + hooks + contexts + pages land, run coverage and write tests for components dragging thresholds below target. Purely presentational components (spacing/layout wrappers) may never get dedicated tests. No up-front components-coverage plan.

### Coverage exclusions

- **D-13:** Files added to `vitest.config.ts` `coverage.exclude` with inline rationale comments (success criterion #5):
  - `src/main.tsx` — "app bootstrap; executes once on mount, not meaningfully testable as a unit"
  - `src/types/Api.ts` — "pure TypeScript types; no executable runtime code"
- **D-14:** `frontend/src/services/Api.ts` (re-export shim from Phase 6 D-22) is NOT excluded. A minimal re-export smoke test is cheaper than the exclude-block entry; it also signals the file still functions as a back-compat shim.
- **D-15:** Pure re-export barrels / zero-runtime-logic files are excluded **per-file as they're discovered during test writing**, not via an up-front audit. Each exclusion carries its own rationale. Example targets likely to surface: `api/utility.ts` (9 lines), `api/retailers.ts` (8 lines) — planner/executor decides at the time of their respective test plans.
- **D-16:** If any file ends up excluded for "eventual follow-up" reasons (not a permanent exclusion), the inline rationale MUST include a `// TODO(admin-ux-milestone)` or equivalent deferred-work marker. Permanent exclusions (types, bootstrap) do not need the marker.

### Guard-style tests reorganized

- **D-17:** Move lint-style regression guards (`src/test/no-process-env.test.ts`, `src/test/no-legacy-gradient.test.ts`, `src/test/extension-content-type.test.ts`) to `src/test/guards/` with a short `README.md` explaining they are regression guards that don't import source files and don't contribute to coverage. This is reorganization only — no behavior change and no impact on the coverage threshold math.

### Mock infrastructure refresh

- **D-18:** `frontend/src/test/setup.ts` adds `vi.mock('../api/client', () => ({ default: mockApiClient, apiClient: mockApiClient }))` **alongside** the existing `vi.mock('../services/Api', ...)`. Both paths resolve to the same mocked Axios surface so:
  - Legacy tests importing from `services/Api` continue to pass.
  - New Phase 8 tests importing from `../api/<domain>` (which internally use `../api/client`) also get the mocked client.
  - Zero regression risk to the 9 existing tests.
- **D-19:** Do NOT remove the existing `vi.mock('../services/Api', ...)` in this phase. It continues to serve tests that reach the shim. Removal is a Phase 9+ cleanup candidate after all import sites migrate.
- **D-20:** The `mockApiClient` shape (get/post/put/delete/patch all returning `{ data: null }` by default) is preserved. Per-test overrides continue to use `vi.mocked(apiClient.get).mockResolvedValueOnce(...)` patterns.

### Delivery sequencing

- **D-21:** **Wave-by-surface baseline-first** ordering:
  - **Wave 0 — Baseline + shared infra (1 plan):** run `npm run test:coverage`, commit `08-COVERAGE-BASELINE.txt` under `.planning/phases/08-frontend-coverage-expansion/` with per-file numbers. In the same plan: refresh `test/setup.ts` per D-18, extend `test-mocks.ts` + `test-utils.tsx` per D-05, create `test/mocks/admin/` scaffolding per D-06, create `test/utils/async.ts` per D-07, move guard tests per D-17, add `src/main.tsx` + `src/types/Api.ts` to `coverage.exclude` per D-13.
  - **Wave 1 — API modules:** 20 test files covering `frontend/src/api/*.ts`. Planner decides whether this is one plan (20 files, large PR), grouped plans (by domain clusters: auth/users/admin, parts/categories/retailers/part_manufacturers, build_lists/build_list_parts/build_list_phases/build_logs, votes/reports/bug_reports, etc.), or file-by-file.
  - **Wave 2 — Hooks + Contexts:** 11 hook test files + 2 context test files. Likely 1-2 plans.
  - **Wave 3 — Customer-facing pages:** full happy-path per page. Grouped by route group (authentication, builder, parts, buildLists, public top-level) — 4-5 plans.
  - **Wave 4 — Admin pages:** 5-8 plans per D-03.
  - **Wave 5 — Components gap-fill + threshold enable + verification (1 plan):** measure coverage after Waves 1-4, write targeted component tests for any below-threshold dimensions, then uncomment `coverage.thresholds` in `vitest.config.ts`, run `npm run test:coverage` locally to confirm pass, commit, push. `frontend-ci.yml` goes green on the same PR.
- **D-22:** Threshold uncomment happens in **Wave 5 only**, after Waves 1-4 land and coverage is verified locally. Zero window of red CI. Matches Phase 1 D-05 discipline ("do not land a red CI").
- **D-23:** Total plan count estimate: **15-25 plans**. Planner sizes based on admin page complexity + whether Wave 1 API tests group or split. This is intentionally an ambitious phase given the "full happy-path per page" + "full happy-path per admin tab/section" depth tier picks.

### Baseline artifact

- **D-24:** Wave 0 commits `.planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt` — the raw `npm run test:coverage` per-file report against `main` before any Phase 8 tests land. Mirrors Phase 6 plan 06-01 lint-baseline pattern. Each subsequent plan's SUMMARY.md can diff against this to show coverage delta.

### Claude's Discretion

- Exact grouping of Wave 1 API test plans (one-plan vs domain-clustered vs per-file) — planner picks based on baseline coverage per api module and team preference for PR size.
- Whether Wave 3 pages plans group by route folder or split further by page size — planner picks.
- Whether CrawlerAdmin lands in 1 plan, 2 plans, or gets a scoping sub-plan first — planner picks after reading the source.
- Whether pure presentational components (components/layout/globalHeader, globalFooter, etc.) get smoke tests pre-emptively in Wave 5 or only if coverage math demands them — planner picks from Wave 4 coverage output.
- File-by-file exclusion rationale wording in D-13/D-15 — executor composes natural prose; the rule is that rationale exists, not the exact wording.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-scope framing
- `.planning/PROJECT.md` — milestone scope (no new features; test coverage & CI gates as Active requirement).
- `.planning/REQUIREMENTS.md` §Safety Nets & CI Hardening — SAFE-03 full text, SAFE-02 threshold-enforcement spec.
- `.planning/REQUIREMENTS.md` §D-06 — locked threshold values (lines 60, functions 50, branches 50, statements 60).
- `.planning/ROADMAP.md` §Phase 8 — Goal, Success Criteria (5 items), Note paragraph with roadmap-level priority order hint.

### Prior phase context that carries forward directly
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` — **D-06** lines 60, functions 50, branches 50, statements 60 target; **D-05** "do not land a red CI" discipline; SAFE-02 frontend-ci.yml `Run tests` step already in place.
- `.planning/phases/01-safety-nets-ci-hardening/01-04-PLAN.md` — plan that deferred SAFE-03 threshold enablement (Option C). The reason it's Phase 8 and not already done.
- `.planning/phases/06-frontend-cleanup-final-ci-gates/06-CONTEXT.md` — **D-22** `frontend/src/api/*.ts` per-domain split (the test target surface); **D-04** co-located response types (what API tests must assert); existing frontend test patterns from Phase 6 (RouteGroupBoundary, App.coverage tests).
- `.planning/phases/06-frontend-cleanup-final-ci-gates/06-04-PLAN.md` — services/Api.ts → api/*.ts migration details (what the shim re-exports).

### Codebase maps
- `.planning/codebase/TESTING.md` — existing pytest/vitest conventions, `-n auto` parallelism.
- `.planning/codebase/STRUCTURE.md` — directory layout used to scope D-11 page-test grouping and D-15 per-file exclusion decisions.
- `.planning/codebase/CONVENTIONS.md` — import ordering, TS strict settings (exactOptionalPropertyTypes impacts mockUseAuth typing per D-05).
- `.planning/codebase/STACK.md` — Vitest + @testing-library/react + jsdom baseline.

### Files directly touched by Phase 8
- `frontend/vitest.config.ts` — uncomment `coverage.thresholds` block (D-00b, D-22); add D-13 exclusions + per-file D-15 exclusions as they surface.
- `frontend/src/test/setup.ts` — add `vi.mock('../api/client')` per D-18; keep existing services/Api mock.
- `frontend/src/test/utils/test-mocks.ts` — add admin + superuser mock variants per D-05.
- `frontend/src/test/utils/test-utils.tsx` — add `adminAuthenticated` + `superuserAuthenticated` testScenarios per D-05.
- `frontend/src/test/mocks/admin/` — NEW directory with per-admin-surface fixture files per D-06.
- `frontend/src/test/utils/async.ts` — NEW file with timer + EventSource stubs per D-07.
- `frontend/src/test/guards/` — relocated from `src/test/` per D-17, plus new README.md.
- `frontend/src/api/*.test.ts` (NEW, 20 files) — per-module API tests per D-08.
- `frontend/src/hooks/*.test.{ts,tsx}` (NEW, 11 files) — per-hook tests per D-09.
- `frontend/src/contexts/*.test.tsx` (NEW, 2 files) — provider tests per D-10.
- `frontend/src/pages/**/*.test.tsx` (NEW, ~30 files) — customer-facing pages per D-11.
- `frontend/src/pages/admin/*.test.tsx` (NEW, 5 files) — admin pages per D-02/D-03.
- `frontend/src/components/**/*.test.tsx` (NEW, count TBD) — gap-fill per D-12.
- `.planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt` (NEW) — baseline artifact per D-24.

### No external ADRs or specs referenced.
Requirements are fully captured in REQUIREMENTS.md SAFE-03, Phase 1 D-06, Phase 6 D-22, and the decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `frontend/src/test/setup.ts` — vitest global setup; auto-mocks `services/Api` today. D-18 extends it to mock `api/client` as well.
- `frontend/src/test/utils/TestProviders.tsx` — wraps children with `BrowserRouter` + `mockUseAuth` mock. Handles initialAuthState; D-05 extends scenarios.
- `frontend/src/test/utils/TestWrapper.tsx` — `AllTheProviders` composing TestProviders with optional auth state. Unchanged by Phase 8.
- `frontend/src/test/utils/test-utils.tsx` — custom render + `createMockUser/Car/BuildList/Part` helpers + `testScenarios` (authenticated/unauthenticated/loading) + form/nav helpers. D-05 adds admin/superuser scenarios.
- `frontend/src/test/utils/test-mocks.ts` — `mockUseAuth` typed against `AuthContextType` with `exactOptionalPropertyTypes` handling. Template for D-05's admin variants.
- `frontend/src/test/mocks/api.ts` — canonical `mockUser`, `mockCar`, `mockBuildList`, `mockPart`, `mockCategory`, `mockVoteSummary`, `mockApiResponses`. D-06 adds `test/mocks/admin/*` alongside without bloating this file.
- `frontend/src/api/client.ts` (140 lines) — shared Axios instance with `paramsSerializer`, base-URL resolver, token helpers, request/response interceptors. The mock target for all API tests per D-08.
- `frontend/src/api/*.ts` (20 per-domain modules, 1,661 lines total) — the primary Wave 1 test surface. File sizes: admin.ts 421, auth.ts 208, parts.ts 123, client.ts 140, images.ts 107, build_list_parts.ts 96, build_lists.ts 80, reports.ts 79, votes.ts 72, part_manufacturers.ts 57, users.ts 48, car_generations.ts 44, bug_reports.ts 43, build_logs.ts 36, search.ts 27, app_settings.ts 25, categories.ts 23, build_list_phases.ts 15, utility.ts 9, retailers.ts 8.
- `frontend/src/App.coverage.test.tsx` (268 lines) — Phase 6 parametrized route-coverage test. Already exists; NOT rewritten by Phase 8. Informs how page-level tests can import and iterate App.tsx route table.
- `frontend/src/components/common/ErrorBoundary.test.tsx`, `RouteGroupBoundary.test.tsx` — Phase 6 error-boundary tests. Template for D-11 error-state assertions.

### Established Patterns

- Vitest `describe`/`it` + `@testing-library/react` `render` + `screen` queries. All Phase 8 tests follow this pattern.
- `vi.mock('../services/Api', ...)` auto-mock in setup.ts — D-18 augments with `vi.mock('../api/client', ...)`. Per-test overrides via `vi.mocked(client.get).mockResolvedValueOnce(...)`.
- `mockUseAuth.mockReturnValue(...)` from `test-mocks.ts` — pattern for auth state injection. D-05 extends without changing the mechanism.
- `testScenarios.authenticated` / `.unauthenticated` / `.loading` — named auth-state fixtures passed into `render(ui, { initialAuthState })`. D-05 adds `.adminAuthenticated` / `.superuserAuthenticated`.
- Tests are co-located next to source (`frontend/src/api/auth.ts` → `frontend/src/api/auth.test.ts`). Phase 8 preserves.
- `@testing-library/jest-dom` matchers (`toBeInTheDocument`, `toHaveTextContent`, etc.) — preserved.
- `frontend-ci.yml` step ordering: format → lint → type-check → audit → test (with --coverage) → circular imports → build. No new steps this phase; thresholds become enforcing via vitest.config.ts uncomment only.

### Integration Points

- `frontend/vitest.config.ts` `coverage.thresholds` comment block — the single edit point that flips the CI gate on (D-00b, D-22).
- `frontend/src/api/client.ts` — the Axios singleton. All `api/*.ts` domain modules import this; mocking it at the test layer (D-18) gives every API test deterministic network behavior.
- `frontend/src/contexts/AuthContext.tsx` + `frontend/src/hooks/useAuth.ts` — auth gate for page tests. `mockUseAuth` bypasses the real hook; testScenarios drive state.
- `frontend/src/App.tsx` `<Routes>` tree — iterated by `App.coverage.test.tsx` today; page tests mount individual `<Route element>` via `MemoryRouter` following Phase 6 D-24 pattern.

</code_context>

<specifics>
## Specific Ideas

- Keep the threshold-enable edit reviewable by landing it as its own commit within the Wave 5 plan. A reviewer should be able to see exactly which lines of `vitest.config.ts` uncommented.
- `08-COVERAGE-BASELINE.txt` from Wave 0 is the ground-truth for every plan SUMMARY.md's "coverage delta" claim. Plans that don't show a measurable delta against the baseline are signal for either test quality issues or unexpected exclusions.
- Admin tests must not bleed mock state across files (vitest parallelism). If `test/mocks/admin/*` fixtures carry any mutable state, wrap with `beforeEach` deep-clone helpers — planner catches this if it surfaces.
- "Full happy-path per page" is ambitious compared to the roadmap's suggested "smoke + one error path." Plan sizing should reflect that each page test is ~3-6 assertions, not 1.
- If research surfaces that CrawlerAdmin uses neither polling nor SSE (D-07 predicted), delete `test/utils/async.ts` in the CrawlerAdmin plan rather than letting it sit as dead code.
- setup.ts D-18 refactor MUST verify all 9 existing tests still pass before any Wave 1 work — failure there blocks the whole wave train.

</specifics>

<deferred>
## Deferred Ideas

- **Delete `frontend/src/services/Api.ts` re-export shim** — Phase 9+ candidate. Requires migrating every import site from `services/Api` to `../api/<domain>`. Out of scope this phase to avoid mixing test-writing with structural refactor.
- **Remove the duplicate `vi.mock('../services/Api', ...)` in setup.ts** — deferred with the shim deletion.
- **Remove admin pages from `vitest coverage.exclude`** — not applicable (admin is in-scope per D-01), but noted that if a future decision reverses D-01, the `TODO(admin-ux-milestone)` marker pattern from D-16 applies.
- **Playwright / E2E for customer flows** — explicitly declined in Phase 6 D-12 and Phase 5 D-39. Revisit if post-Phase-8 regressions hint that unit+component tests miss route-boundary issues.
- **MSW network-level API mocks** — declined in D-08. Revisit if per-module mocks at `api/client` prove brittle to refactors (e.g., if interceptor changes need tests to assert network-level behavior).
- **Snapshot testing policy** — not used in Phase 8. Vitest supports it; no decisions captured because no decision was made to adopt it.
- **Accessibility (a11y) testing** — out of scope this phase. Candidate for a future UX-focused milestone.
- **Coverage HTML report publishing to PR comments** — not in scope. CI log is sufficient for the gate.
- **Ratchet thresholds above 60/50/50/60 over time** — Phase 8 hits the SAFE-03 floor; further ratcheting is a future-milestone call, not a Phase 8 deliverable.

</deferred>

---

*Phase: 08-frontend-coverage-expansion*
*Context gathered: 2026-04-24*
