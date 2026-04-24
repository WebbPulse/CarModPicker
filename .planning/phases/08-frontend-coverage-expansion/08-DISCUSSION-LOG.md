# Phase 8: Frontend Coverage Expansion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 08-frontend-coverage-expansion
**Areas discussed:** Admin-page scope, Test depth by tier, Coverage exclusions, Delivery sequencing + mocks

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Admin-page scope | 5 admin pages are 6,921 lines. Include (smoke vs deep), exclude entirely as operator-only tooling, or split by page? | ✓ |
| Test depth by tier | Per-file depth tiers: API modules, hooks/contexts, pages, components. Smoke-only vs smoke+error vs interaction tests. | ✓ |
| Coverage exclusions | Which categories get excluded with inline rationale per success criterion #5. | ✓ |
| Delivery sequencing + mocks | Single PR vs wave-based plans. Plus: refresh setup.ts to mock api/client or stay on services/Api shim? | ✓ |

**User's choice:** All four areas selected.

---

## Admin-page scope

### Admin treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude entirely (Recommended) | Remove pages/admin/** from coverage; re-add in future admin-UX milestone. | |
| Smoke-render only | One render test per admin page; minimal coverage math boost. | |
| Include with real tests | Full real testing for admin page happy paths. High-effort given page sizes. | ✓ |
| Split: critical kept, rest excluded | AdminDashboard + ReportReview + BugReportReview kept; CrawlerAdmin, SystemAdmin, etc. excluded. | |

**User's choice:** Include with real tests
**Notes:** Ambitious choice given 6,921 lines; flagged scope implication in CONTEXT.md for planner.

### Exclusion deferral marker

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add '// TODO(admin-ux-milestone)' | Inline comment marking exclusion as intentional + deferred. | ✓ |
| Just rationale, no TODO (Recommended) | Inline rationale only; PROJECT.md excludes new admin UX. | |
| No comment, file them as Deferred Ideas in CONTEXT.md | Keep exclude block clean; track in phase Deferred Ideas. | |

**User's choice:** Yes, add '// TODO(admin-ux-milestone)'
**Notes:** Technically moot given admin is in-scope per first answer; recorded as a fallback pattern in case any file ends up excluded unintentionally. Captured as D-16.

### Admin test depth

| Option | Description | Selected |
|--------|-------------|----------|
| Happy-path render + 1 primary action (Recommended) | ~5-8 test cases per admin file. | |
| Happy-path + error state + auth gate | Render + one action + error toast + auth redirect. | |
| Full happy-path workflow per tab/section | Every tab/section in every admin page gets its own happy-path test. Most thorough, highest maintenance. | ✓ |
| Smoke render + granular unit tests on extracted logic | Extract complex state into testable helpers. Implies mid-phase refactor. | |

**User's choice:** Full happy-path workflow per tab/section
**Notes:** Highest-effort choice; planner will size plans accordingly. CrawlerAdmin with ~8 sections in 2,665 lines may become 2+ plans on its own.

### Admin plan sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| Split per page (Recommended) | One plan per admin page; 5 plans minimum. | ✓ |
| Group small + isolate large | Small pages grouped; CrawlerAdmin solo; others split by complexity. | |
| One big admin-tests wave | Single plan covering all 5 admin files; giant PR. | |

**User's choice:** Split per page (Recommended)

### Admin auth gate handling

| Option | Description | Selected |
|--------|-------------|----------|
| Extend test-mocks with admin/superuser variants (Recommended) | Add mockAdminUser, mockSuperuserUser + testScenarios.adminAuthenticated / .superuserAuthenticated. | ✓ |
| Per-test inline auth mocks | Each admin test sets up its own admin auth state inline. | |
| Separate AdminTestProviders wrapper | New wrapper component defaulting to admin-authenticated state. | |

**User's choice:** Extend test-mocks with admin/superuser variants (Recommended)

### Admin mock data structure

| Option | Description | Selected |
|--------|-------------|----------|
| Per-admin-surface fixture files (Recommended) | test/mocks/admin/{jobs,reports,bugs,users,crawlers,stats,curation}.ts | ✓ |
| Extend test/mocks/api.ts with admin section | Single flat mocks file with new admin exports. | |
| Inline mocks in each admin test | Each admin test defines its own fixtures. | |

**User's choice:** Per-admin-surface fixture files (Recommended)

### CrawlerAdmin-specific infra

| Option | Description | Selected |
|--------|-------------|----------|
| Timer/interval mocks + WebSocket/EventSource stubs (Recommended) | Preemptive async scaffolding in test/utils/. | ✓ |
| Only add scaffolding if CrawlerAdmin actually needs it | Planner decides based on actual code during its plan. | |
| Defer to research | gsd-phase-researcher reads CrawlerAdmin.tsx and surfaces needs. | |

**User's choice:** Timer/interval mocks + WebSocket/EventSource stubs (Recommended)

---

## Test depth by tier

### API-module test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Per-module file mocking api/client (Recommended) | One test file per api module; mock axios methods; assert URL + body + response shape. | ✓ |
| MSW network-level mocks | Add MSW dep; real Axios calls intercepted. | |
| Grouped domain tests + integration smoke | Blur unit/integration lines across a domain. | |
| Spot-test only high-risk modules | admin/auth/parts/client only; smaller modules covered incidentally. | |

**User's choice:** Per-module file mocking api/client (Recommended)

### Hooks and contexts depth

| Option | Description | Selected |
|--------|-------------|----------|
| Unit test each hook + provider behavior (Recommended) | One test file per hook + provider tests. ~13 small focused files. | ✓ |
| Test hooks only through pages that use them | No dedicated hook tests; covered incidentally. | |
| Spot-test high-branch hooks | Only hooks with heavy branching. | |

**User's choice:** Unit test each hook + provider behavior (Recommended)

### Customer-facing page depth

| Option | Description | Selected |
|--------|-------------|----------|
| Smoke + one error path (roadmap default) (Recommended) | Matches roadmap's (c) spec. | |
| Smoke + error + one primary action | Add one primary interaction per page. | |
| Tiered by page complexity | Thin pages smoke-only; heavy pages full coverage. | |
| Full happy-path per page | Primary flow end-to-end + error state. Symmetric with admin. | ✓ |

**User's choice:** Full happy-path per page
**Notes:** Deliberately chose above roadmap default depth. Symmetric with admin-page depth choice.

### Components depth

| Option | Description | Selected |
|--------|-------------|----------|
| Coverage-driven fill-in-the-gaps (Recommended) | Target only components below threshold after other waves land. | ✓ |
| Test every component with branching logic | Systematic walk through components/. | |
| Test only shared/common components | Skip feature-specific components. | |

**User's choice:** Coverage-driven fill-in-the-gaps (Recommended)

---

## Coverage exclusions

### Files added to coverage.exclude (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| types/Api.ts (generated/pure types) | No executable runtime code. | ✓ |
| services/Api.ts (re-export shim) | Covered transitively by per-domain tests. | |
| main.tsx (app bootstrap) | Executes once on mount; not meaningfully testable. | ✓ |
| lib/sentry.ts | Third-party SDK wiring; already has test. | |

**User's choice:** main.tsx + types/Api.ts excluded.

### services/Api.ts treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Keep in coverage (Recommended) | Minimal re-export smoke test. | ✓ |
| Exclude with rationale | Cleanest once removed in future phase. | |

**User's choice:** Keep in coverage (Recommended)

### Barrel / re-export files

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude per-file as found (Recommended) | Planner/executor adds exclusions file-by-file during test writing. | ✓ |
| Pre-scan and exclude in the first plan | Wave 0 plan does the full scan up front. | |
| Don't exclude any — smoke-test them all | One-line smoke tests per barrel. | |

**User's choice:** Exclude per-file as found (Recommended)

### Guard tests placement

| Option | Description | Selected |
|--------|-------------|----------|
| No change — already in test tree (Recommended) | Leave as-is; no coverage impact. | |
| Move to separate 'guards' test folder with note | Re-home under src/test/guards/ with README. | ✓ |

**User's choice:** Move to separate 'guards' test folder with note
**Notes:** Purely organizational; no behavior change. Captured as D-17.

---

## Delivery sequencing + mocks

### Wave sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| Wave-by-surface baseline-first (Recommended) | Wave 0 baseline+infra, Waves 1-4 APIs/hooks/pages/admin, Wave 5 components+threshold. | ✓ |
| Priority-first, admin last | Same order, admin at very end so customer surface lands first. | |
| Parallel waves per surface | Non-sequential parallel streams. | |

**User's choice:** Wave-by-surface baseline-first (Recommended)
**Notes:** Admin is wave 4, before components gap-fill and threshold enable in wave 5.

### Threshold uncomment timing

| Option | Description | Selected |
|--------|-------------|----------|
| Final wave, after coverage verified (Recommended) | Zero window of red CI. Matches Phase 1 D-05. | ✓ |
| Uncomment early as a ratchet | Threshold edits multiple times as coverage grows. | |
| Uncomment in wave 0, accept red CI until coverage catches up | Most aggressive; blocks unrelated PRs. | |

**User's choice:** Final wave, after coverage verified (Recommended)

### setup.ts refresh strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Mock api/client directly + keep services/Api mock (Recommended) | Both mock paths; zero regression risk to existing 9 tests. | ✓ |
| Refactor setup.ts to mock only api/client | Delete services/Api mock; rely on shim transitively. | |
| Remove auto-mock from setup.ts entirely | Each test opts in via vi.mock(); highest blast radius. | |

**User's choice:** Mock api/client directly + keep services/Api mock (Recommended)

### Coverage baseline artifact

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, commit 08-COVERAGE-BASELINE.txt (Recommended) | Plan 08-01 commits per-file coverage baseline. Mirrors Phase 6 plan 06-01 pattern. | ✓ |
| No baseline file — CI output is the truth | Rely on PR CI output comparisons. | |

**User's choice:** Yes, commit 08-COVERAGE-BASELINE.txt (Recommended)

---

## Claude's Discretion

- Exact grouping of Wave 1 API test plans (20 files in one plan vs domain-clustered vs per-file)
- Whether Wave 3 page plans group by route folder or split further by page size
- Whether CrawlerAdmin lands in 1 plan, 2 plans, or gets a scoping sub-plan first
- Whether pure presentational components get smoke tests pre-emptively in Wave 5 or only if coverage math demands them
- File-by-file exclusion rationale wording in D-13/D-15 (prose composition, not the exclusion decision itself)

## Deferred Ideas

- Deleting `services/Api.ts` re-export shim (Phase 9+)
- Removing the duplicate `vi.mock('../services/Api', ...)` in setup.ts (tied to shim deletion)
- Playwright / E2E (declined prior phases)
- MSW network-level API mocks (may revisit if per-module mocks prove brittle)
- Snapshot testing policy (no decision made)
- Accessibility (a11y) testing (future milestone)
- Coverage HTML report publishing to PR comments
- Ratcheting thresholds above 60/50/50/60 (future-milestone call)
