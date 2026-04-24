# Phase 6: Frontend Cleanup & Final CI Gates - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Final-gate phase for the tech-debt milestone. Two distinct workstreams:

**Frontend structural + quality:**
- Turn on `@typescript-eslint/no-explicit-any` + `no-unsafe-*` errors; narrow API response types so they stop leaking `any` through the client (FE-01, FE-04).
- Audit `import.meta.env.VITE_*` usage and remove any stray `process.env` references (FE-02).
- Add route-level error boundaries on top of the existing app-root ErrorBoundary so a single page crash no longer blanks the whole app (FE-03).
- Sweep Tailwind v3-era `bg-gradient-to-*` class names to the v4 `bg-linear-to-*` form with a regression guard (FE-05).
- Add `madge --circular` as a CI gate (FE-06).
- Opportunistic UX polish on any page touched by the above structural fixes, plus one bounded targeted pass on the parts catalog (FE-07).

**Backend/infra final gates:**
- Apply stack patch upgrades (FastAPI 0.128 → 0.136, Pydantic 2.11 → 2.13, SQLAlchemy 2.0.41 → 2.0.49, Alembic 1.16 → 1.18, Uvicorn 0.34 → 0.45) with Chrome-extension `Content-Type` audit gating FastAPI 0.136 (QUAL-05, QUAL-06).
- Verify `bandit` HIGH-severity findings actually gate CI; add regression fixture (QUAL-04).
- Add Terraform S3 Glacier Deep Archive lifecycle rule on `carmodpicker-production-crawl-data` at 90 days (QUAL-08).

**Explicitly out of scope:**
- New user-facing features (PROJECT.md milestone cap).
- Dedicated parts-catalog UX redesign — single bounded pass only; full redesign is v2 (UX-V2-01).
- `python-jose` retention (deferred from Phase 5 Risk 6 is closed here; jose is removed).
- Zod/generated-client adoption for API response validation.

</domain>

<decisions>
## Implementation Decisions

### Typing strictness rollout (FE-01, FE-04)

- **D-01:** Roll out `@typescript-eslint/no-explicit-any: error` and `no-unsafe-*: error` as **fix-all before merge** — not a day-one-error-plus-allowlist, not a warn-then-error ratchet. Scout found only 1 explicit `any` in source (`frontend/src/utils/lazyWithReload.ts:23`). The blast radius is small enough that landing the gate and the fixes in the same PR is cheaper than maintaining an allowlist.
- **D-02:** The typing-rollout plan starts with a committed **lint audit baseline**: task 1 runs `cd frontend && npm run lint 2>&1 | tee 06-LINT-BASELINE.txt` against the stricter config and commits the file so scope is visible up front. Subsequent tasks break fixes into reviewable chunks by directory (pages, components, api, hooks, contexts, utils).
- **D-03:** FE-04 API response typing uses **`unknown` + narrowing at the API-client boundary** — no runtime validator (zod/valibot) and no generated client from `openapi_snapshot.json`. PROJECT.md explicitly excludes OpenAPI Pact contracts; a runtime validator is a stack addition with thin benefit at current traffic. The OpenAPI snapshot (SAFE-05, Phase 1) already guards backend-side drift.
- **D-04:** Hand-written response types live **next to each API client module in `frontend/src/api/`** (co-located). Narrowing happens at the API-client layer; pages import already-typed results. Mirrors the backend endpoint/domain split.
- **D-05:** **Ratchet test-file ESLint config to match source** — drop the `no-unsafe-*` `off` overrides in `src/test/**`. Test mocks must be type-honest. Accept the churn; don't maintain a split rule surface long-term.
- **D-06:** The `any` in `lazyWithReload<T extends ComponentType<any>>` is replaced with `ComponentType<unknown>` or `ComponentType<Record<string, unknown>>` depending on how React.lazy's type inference threads through — planner decides, but **it is not `any`**.

### Route-level error boundaries (FE-03)

- **D-07:** **Per route-group wrappers** — not per-lazy-page, not a single RouteErrorBoundary component. Four wrappers matching the `pages/` folder split: admin, authentication, builder, public. Each wraps its `<Route>` children with an ErrorBoundary instance. One bug in `pages/admin/*` cannot blank-screen the builder.
- **D-08:** Fallback UX is an **inline panel matching the dark site theme**: error summary line, **Retry** button (resets boundary state), **Go Home** link (router navigate), and the **Sentry event ID** captured by `@sentry/react`'s error-capture hook (Phase 2 OBS-05). Header + Footer remain rendered and usable.
- **D-09:** **Keep the existing top-level `<Suspense>`** in App.tsx. Route-group ErrorBoundaries live under Suspense and handle render-time errors only. No per-group Suspense fallbacks — loading UX is unchanged this phase.
- **D-10:** CI coverage for FE-03 is a **parametrized vitest test** that imports App.tsx's route table, iterates every `<Route element>`, and asserts the element's ancestor tree includes one of the four route-group wrappers. Mirrors Phase 5's parametrized 401/403 coverage pattern. A new `<Route>` that skips a wrapper fails CI.

### Stack upgrade sequencing (QUAL-05, QUAL-06)

- **D-11:** Ship the upgrade train as **two PRs**, not one combined PR and not five single-library PRs:
  - **PR-A: FastAPI 0.128 → 0.136 + Pydantic 2.11 → 2.13** — highest coupling, highest blast-radius pair. Includes the QUAL-06 extension Content-Type audit and the auth characterization suite (SAFE-06) re-run as a gate.
  - **PR-B: SQLAlchemy 2.0.41 → 2.0.49 + Alembic 1.16 → 1.18 + Uvicorn 0.34 → 0.45** — minor patches, low risk. Lands after PR-A merges.
- **D-12:** QUAL-06 extension audit = **static grep guard + extension smoke test**:
  - (a) CI grep in `chrome-extension/src/**/*.ts` asserting every `fetch(...{ method: 'POST' ... })` call either sets `'Content-Type': 'application/json'` or is sending a `FormData` body. Regex guard committed as a pytest/vitest test with a deterministic fixture.
  - (b) Run the Phase 1 auth characterization suite (`pytest -k "auth and characterization"`) against FastAPI 0.136 locally before PR-A merges. No Playwright-with-extensions (D-39 defers that to Phase 7+).
- **D-13:** **Ride the existing guards** for Pydantic 2.13 deprecations and Alembic 1.18 changes:
  - The Phase 3 Pydantic-v1-grep CI guard + `catch_warnings` pytest guard (plan 03-05) surface any 2.13 deprecations as test failures. Fix warnings inline as they appear.
  - The Phase 4 `test_migration_round_trip.sh` script (plan 04-06) verifies every migration head-revision still round-trips under Alembic 1.18.
  - No new pre-upgrade warnings baseline file — existing guards are the right place.
- **D-14:** **Remove `python-jose[cryptography]==3.5.0`** from `backend/requirements.txt` as part of PR-B. Phase 5 Risk 6 kept it only to power `test_pyjwt_migration.py` byte-identity parity. That test is no longer load-bearing (PyJWT is in prod, no pre-migration tokens in flight); delete the test when jose is removed. This closes the deferred Phase 5 follow-up explicitly called out in 05-SUMMARY.md.

### UX polish + Tailwind/madge cleanup (FE-05, FE-06, FE-07)

- **D-15:** **One-shot codemod + regression guard** for the `bg-gradient-to-*` → `bg-linear-to-*` rename. Single commit converts all ~15 sites across App.tsx, Header, Footer, Card, ChromeExtensionPromo, DeleteConfirmationDialog, SubscriptionPromo. Regression guard: **vitest test** that greps `frontend/src/**/*.{ts,tsx}` and fails on any `bg-gradient-to-` match (eslint no-restricted-syntax is harder to scope to className strings). Tailwind v4 still accepts the old class name today, so the guard is the mechanism that makes the rename stick.
- **D-16:** `madge --circular` runs **CI-only** in `frontend-ci.yml` — new `Check circular imports` step after `Run tests`, before `Build application`. `npx madge --circular src/` fails on any hit. madge added to `frontend/package.json` as a devDependency. No husky pre-commit hook — avoid local-dev install friction.
- **D-17:** FE-07 UX polish scope: **touched-file-only + one targeted parts-catalog pass**. The planner may add visual polish to any page that a FE-01/FE-03/FE-04 fix already touches. Additionally, one bounded plan task does a visual polish pass on `pages/parts/*` and `components/parts/*` ONLY, with a written checklist (spacing, typography, card variants matching Card.tsx existing shadow/rounded variants). No polish pass outside those files; no redesign of information architecture or interactions.

### Final CI gates (QUAL-04, QUAL-08)

- **D-18:** QUAL-04 bandit verification path:
  - Step 1: create a synthetic bandit HIGH fixture (e.g., `subprocess.call(cmd, shell=True)` with dynamic input) in a temp file.
  - Step 2: run `bandit -r <fixture> -ll` locally and observe the exit code.
  - Step 3a: if exit code is non-zero on HIGH → add a committed regression test (pytest subprocess that runs bandit on a known-HIGH fixture and asserts exit code != 0) + a comment in `.bandit` documenting the current flag behavior.
  - Step 3b: if exit code is zero on HIGH → adjust the CI invocation to `bandit -r app --severity-level high --confidence-level medium` so HIGH definitionally fails, then add the same regression test.
  - Don't change the working config without verification.
- **D-19:** QUAL-08 Terraform lifecycle rule: add `aws_s3_bucket_lifecycle_configuration` on `carmodpicker-production-crawl-data` ONLY. HTML snapshot objects transition to Glacier Deep Archive at **90 days** after creation. `carmodpicker-prod-user-images` bucket stays hot — active product imagery, user-facing serve latency cannot regress to Glacier retrieval windows (minutes-hours).
- **D-20:** Terraform change lands in `terraform/` with a plan output committed to the PR description. No manual state manipulation.

### Execution sequencing across Phase 6

- **D-21:** Suggested wave order for planning (planner may adjust):
  - **Wave 1 (parallel-safe):** FE-02 (`process.env` audit), FE-06 (madge setup), FE-05 (gradient codemod + guard), QUAL-04 (bandit verification), QUAL-08 (Terraform lifecycle).
  - **Wave 2:** FE-01 lint baseline → chunked fix tasks by directory + FE-04 `unknown` + co-located types.
  - **Wave 3:** FE-03 route-group wrappers + parametrized coverage test.
  - **Wave 4 (PR-A):** FastAPI 0.136 + Pydantic 2.13 + QUAL-06 extension audit + auth characterization re-run.
  - **Wave 5 (PR-B):** SQLAlchemy + Alembic + Uvicorn patch + `python-jose` removal.
  - **Wave 6:** FE-07 opportunistic polish sweep over files touched in waves 1-5 + the single bounded parts-catalog pass.

### Claude's Discretion

- Exact shape of the `lazyWithReload` generic fix (`ComponentType<unknown>` vs a narrower bound) — planner picks based on React.lazy inference compatibility with the call sites.
- Directory-chunking strategy for FE-01 fix tasks (by-folder vs by-violation-count) — planner picks based on the 06-LINT-BASELINE.txt output.
- Whether the FE-03 coverage test reads App.tsx statically (AST) or runs RTL renders — planner picks the least-fragile option.
- Parts-catalog polish checklist contents — planner drafts, UAT approves.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone-level framing
- `.planning/PROJECT.md` — milestone vision, out-of-scope list, "opportunistic UX only" key decision, Python 3.13 / AWS stack lock.
- `.planning/REQUIREMENTS.md` §Frontend Structure & Quality — FE-01…FE-07 full text.
- `.planning/REQUIREMENTS.md` §General Code-Quality Sweep — QUAL-04, QUAL-05, QUAL-06, QUAL-08 full text.
- `.planning/ROADMAP.md` §Phase 6 — success criteria + plan list.

### Prior phase context that carries forward directly
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` — SAFE-04 DROP-guard pattern, SAFE-05 OpenAPI snapshot, SAFE-06 auth characterization.
- `.planning/phases/02-observability/02-CONTEXT.md` — OBS-05 @sentry/react + ErrorBoundary integration, captureException + setUser wiring.
- `.planning/phases/03-non-breaking-internal-improvements/03-CONTEXT.md` — Pydantic v1 grep guard + catch_warnings pytest guard (plan 03-05) — QUAL-05 Pydantic 2.13 upgrade relies on these.
- `.planning/phases/04-db-parts-hardening/04-CONTEXT.md` — `test_migration_round_trip.sh` round-trip script (plan 04-06) — QUAL-05 Alembic 1.18 upgrade relies on this.
- `.planning/phases/05-structural-router-splits/05-CONTEXT.md` — PyJWT migration risk 6 (jose retention rationale), Chrome extension D-14 (extension untouched), AUTH-05 staging UAT checklist.
- `.planning/phases/05-structural-router-splits/05-04-SUMMARY.md` §Deviations / Deferred — explicit call-out that python-jose removal is a Phase 6 follow-up.

### Codebase maps (all relevant)
- `.planning/codebase/STACK.md` — current dependency versions as baseline for upgrade deltas.
- `.planning/codebase/CONVENTIONS.md` — import ordering, error handling, Alembic downgrade testing procedure.
- `.planning/codebase/CONCERNS.md` — known frontend and performance concerns to check against after fixes land.
- `.planning/codebase/STRUCTURE.md` — directory layout used to scope FE-01 chunking and FE-07 polish boundaries.
- `.planning/codebase/TESTING.md` — existing test scaffolding + pytest/vitest conventions.

### Files directly touched by Phase 6
- `frontend/eslint.config.js` — FE-01 rule enablement + test-file override removal (D-05).
- `frontend/src/api/*.ts` — FE-04 co-located response types (D-04).
- `frontend/src/App.tsx` — FE-03 route-group wrapper insertion; FE-05 gradient rename.
- `frontend/src/components/common/ErrorBoundary.tsx` — FE-03 reference for new route-group boundary component (D-07, D-08).
- `frontend/src/components/layout/globalHeader/Header.tsx`, `.../globalFooter/Footer.tsx`, `frontend/src/components/common/Card.tsx`, `.../ChromeExtensionPromo.tsx`, `.../DeleteConfirmationDialog.tsx`, `.../SubscriptionPromo.tsx` — FE-05 gradient call sites.
- `frontend/src/utils/lazyWithReload.ts` — FE-01 `any` fix.
- `frontend/package.json`, `.github/workflows/frontend-ci.yml` — FE-06 madge gate wiring.
- `backend/requirements.txt` — QUAL-05 version bumps; D-14 python-jose removal.
- `backend/.bandit`, `.github/workflows/backend-ci.yml` — QUAL-04 verification + regression test.
- `chrome-extension/src/**/*.ts` — QUAL-06 Content-Type audit target.
- `terraform/` — QUAL-08 S3 lifecycle rule.

### No external ADRs or specs beyond project planning docs required.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/components/common/ErrorBoundary.tsx` — existing class-component boundary used at App root (main.tsx:22 + App.tsx:132). Route-group wrappers either compose it or subclass it.
- `@sentry/react` + Session Replay-on-error + ErrorBoundary captureException — wired in Phase 2 (OBS-05). Sentry event ID is already surfaced by the existing integration; route-group fallbacks read from it.
- `frontend/src/utils/lazyWithReload.ts` — lazy-loader used for all ~40 pages; the typing fix is load-bearing across every `<Route element>`.
- `frontend/src/api/*.ts` Axios client modules by domain — the FE-04 co-location home.
- `frontend/eslint.config.js` already extends `tseslint.configs.recommendedTypeChecked` — FE-01 is about auditing what the existing rules surface, not about adding rule sets from scratch.
- `backend/tests/fixtures/openapi_snapshot.json` + `test_openapi_snapshot.py` (SAFE-05) — backward-compatibility oracle for PR-A FastAPI 0.136 upgrade.

### Established Patterns
- Parametrized coverage tests over `app.routes` (Phase 5 `test_admin_auth_coverage.py`, `test_auth_auth_coverage.py`) — template for D-10 route-group coverage test.
- `pytest -n auto` parallel test execution — every new backend test must tolerate xdist.
- Vitest for all frontend tests, co-located under `src/test/**` — D-05 removes the unsafe relaxations there.
- `catch_warnings` pytest guard + Pydantic v1 grep guard (plan 03-05) — the Pydantic 2.13 canary for QUAL-05.
- `test_migration_round_trip.sh` (plan 04-06) — the Alembic 1.18 canary for QUAL-05.
- Tailwind v4 `@import 'tailwindcss'` + `@theme` block in `frontend/src/index.css` — already the v4 pattern; FE-05 is class-name cleanup only, not a v4 migration.
- `.github/workflows/frontend-ci.yml` step ordering: install → lint → test → build. madge (D-16) slots between test and build.

### Integration Points
- `App.tsx` `<Routes>` tree — route-group wrappers insert at `<Route element={<AdminWrapper><Outlet /></AdminWrapper>}>` style.
- Sentry `@sentry/react` ErrorBoundary has `beforeCapture` + `fallback` props — the route-group wrappers plug into this.
- Terraform `terraform/` module(s) own all S3 bucket state — QUAL-08 lifecycle rule lands next to existing `aws_s3_bucket` declarations, not in a separate module.
- `backend-ci.yml` already has a `Security scan (bandit)` step — QUAL-04 changes either the step's flags (D-18 path B) or adds a regression test next to it (D-18 path A).

</code_context>

<specifics>
## Specific Ideas

- Phase-6 plan should open with the committed LINT-BASELINE.txt task — scope visibility before fix work starts.
- The parts-catalog polish pass is the ONE exception to "touched-file-only" — everything else in FE-07 is strictly opportunistic.
- python-jose removal belongs to PR-B (the low-risk patch PR), not PR-A (the high-coupling FastAPI+Pydantic PR) — so a jose-related regression doesn't conflate with a FastAPI 0.136 regression during bisect.
- Glacier lifecycle rule is crawl-archive ONLY — user-images bucket latency cannot regress.
- No runtime validator (zod) and no generated client — deliberate scope control, not an oversight.

</specifics>

<deferred>
## Deferred Ideas

- **Generated API client from openapi_snapshot.json** — not this phase. Revisit if FE-04 hand-maintained types become a maintenance burden after the next milestone's data-enrichment work lands and response shapes churn.
- **Full parts-catalog UX redesign** — captured in REQUIREMENTS.md v2 as UX-V2-01. Phase 6 bounded polish pass is the cap.
- **Playwright-with-extensions E2E** — deferred by Phase 5 D-39; surfaces again as an option for QUAL-06 audit but explicitly declined (D-12). Revisit next milestone if extension regressions become recurrent.
- **Zod / valibot runtime validation of API responses** — declined in D-03. Revisit if cross-tier schema drift becomes a real source of production bugs.
- **Husky pre-commit hooks (madge, lint)** — declined in D-16. Revisit if CI-only guards are consistently caught late and force re-pushes.
- **Glacier lifecycle on `carmodpicker-prod-user-images`** — declined in D-19. Revisit only if storage cost analysis demonstrates the tradeoff against retrieval latency.
- **Python 3.13 → 3.14 bump** — out of scope this milestone per PROJECT.md constraints.

</deferred>

---

*Phase: 06-frontend-cleanup-final-ci-gates*
*Context gathered: 2026-04-23*
