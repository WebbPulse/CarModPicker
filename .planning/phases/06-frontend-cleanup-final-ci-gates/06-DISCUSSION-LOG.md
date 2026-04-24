# Phase 6: Frontend Cleanup & Final CI Gates - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 06-frontend-cleanup-final-ci-gates
**Areas discussed:** Typing strictness rollout, Error boundary granularity, Stack upgrade sequencing, UX polish + Tailwind/madge cleanup

---

## Typing strictness rollout

### How should FE-01/FE-04 land?

| Option | Description | Selected |
|--------|-------------|----------|
| Fix-all before merge | Hard-error on CI day-one; fix all violations in the same PR. No allowlist. | ✓ |
| Day-one error + allowlist | Enable errors, inventory existing violations into eslint.config.js overrides, burn down. | |
| Warn-then-error ratchet | Land as warnings first, flip to error in follow-up PR. | |

**User's choice:** Fix-all before merge
**Notes:** Scout found only 1 explicit `any` in source (lazyWithReload.ts) — blast radius is small.

### How should FE-04 narrow API response types?

| Option | Description | Selected |
|--------|-------------|----------|
| unknown + narrow at boundary | Responses typed `unknown`; hand-written TS interfaces at call sites. | ✓ |
| Zod runtime validation | Adopt zod for API response parsing; inferred TS types. | |
| Generated client from openapi.json | openapi-typescript against the committed snapshot. | |

**User's choice:** unknown + narrow at boundary
**Notes:** PROJECT.md excludes OpenAPI Pact contracts; runtime validator is stack-add with thin benefit at current traffic.

### Should the test-file relaxations in eslint.config.js stay?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep the relaxed test config | `src/test/**` keeps `no-unsafe-*` as warn. | |
| Ratchet tests to match source | Apply same rules to tests; accept the churn. | ✓ |

**User's choice:** Ratchet tests to match source
**Notes:** Test mocks must be type-honest; don't maintain a split rule surface long-term.

### Where should the hand-written response types live?

| Option | Description | Selected |
|--------|-------------|----------|
| In `frontend/src/api/` next to each client module | One types.ts per API domain module. | ✓ |
| Centralized `frontend/src/types/api/*.ts` | Single shared directory for all response types. | |
| Claude's discretion | Planner picks based on module-graph output. | |

**User's choice:** In `frontend/src/api/` next to each client module
**Notes:** Mirrors backend domain split; existing Axios clients already domain-sharded.

### Should the plan start with a full lint audit task, or go straight to fixes?

| Option | Description | Selected |
|--------|-------------|----------|
| Audit task first, then fix tasks | Commit LINT-BASELINE.txt before fix tasks. | ✓ |
| Fix-as-you-go, no baseline file | Planner breaks fixes into tasks without committed inventory. | |

**User's choice:** Audit task first, then fix tasks
**Notes:** Test ratchet is likely to surface dozens of hits; baseline makes scope visible up front.

---

## Error boundary granularity

### Where should route-level error boundaries sit?

| Option | Description | Selected |
|--------|-------------|----------|
| Per route-group wrapper | 4 wrappers (admin / authentication / builder / public). | ✓ |
| Per lazy page boundary | ErrorBoundary around every lazy-loaded component (~40 wrappers). | |
| Single RouteErrorBoundary component | One wrapper, ~40 usages. | |

**User's choice:** Per route-group wrapper
**Notes:** Matches the folder split under `pages/`; bounded boundary count.

### What should the route-level fallback look like?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline panel + Retry + Home + Sentry ID | Dark-theme card, Retry/Go Home buttons, Sentry event ID. Header/Footer usable. | ✓ |
| Reuse the top-level ErrorBoundary fallback | Same fallback as the app root. | |
| Claude's discretion | Planner picks based on existing ErrorBoundary render. | |

**User's choice:** Inline panel + Retry + Home + Sentry ID

### How should Suspense loading work with the boundary split?

| Option | Description | Selected |
|--------|-------------|----------|
| One top-level Suspense, boundaries below | Keep existing top-level Suspense; boundaries under it handle render errors. | ✓ |
| Per-group Suspense + boundary pair | Each route group gets its own Suspense + ErrorBoundary pair. | |

**User's choice:** One top-level Suspense, boundaries below
**Notes:** No change to loading UX; boundary is purely additive.

### How is FE-03 coverage verified in CI?

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest parametrized test | Iterates every Route and asserts wrapper ancestor. | ✓ |
| Manual audit at merge only | No automated guard; reviewers check diff. | |

**User's choice:** Vitest parametrized test
**Notes:** Mirrors Phase 5's parametrized 401/403 coverage pattern.

---

## Stack upgrade sequencing

### How should the upgrade train ship?

| Option | Description | Selected |
|--------|-------------|----------|
| Two PRs: FastAPI+Pydantic first, rest second | PR-A: FastAPI 0.136 + Pydantic 2.13 + QUAL-06; PR-B: SQLAlchemy + Alembic + Uvicorn. | ✓ |
| Single combined PR | All five upgrades in one PR. | |
| One PR per library (five PRs) | Max bisect resolution; Dependabot-style. | |

**User's choice:** Two PRs: FastAPI+Pydantic first, rest second
**Notes:** Isolates the one risky pair, keeps the rest as one clean sweep.

### What form should the QUAL-06 Chrome-extension Content-Type audit take?

| Option | Description | Selected |
|--------|-------------|----------|
| Grep guard + extension smoke test | CI regex on fetch POST calls + local auth characterization run vs 0.136. | ✓ |
| Grep guard only | Static regex only; misses runtime drift. | |
| Extension Playwright E2E | Full browser test with extension loaded. | |

**User's choice:** Grep guard + extension smoke test
**Notes:** Playwright-with-extensions deferred by Phase 5 D-39.

### How should Pydantic 2.13 deprecations and Alembic 1.18 changes be handled?

| Option | Description | Selected |
|--------|-------------|----------|
| Ride existing guards | Phase 3 Pydantic-v1 + catch_warnings guards + Phase 4 round-trip script. | ✓ |
| New pre-upgrade baseline | Warnings diff committed as baseline file. | |

**User's choice:** Ride existing guards

### Any other stack version bumps to fold in?

| Option | Description | Selected |
|--------|-------------|----------|
| python-jose removal | Drop python-jose[cryptography]==3.5.0 and delete the parity test. | ✓ |
| Defer jose removal to next milestone | Leave in requirements.txt. | |
| Bump Python 3.13 to 3.14 | Out of scope per PROJECT.md. | |

**User's choice:** python-jose removal
**Notes:** Closes the Phase 5 SUMMARY follow-up.

---

## UX polish + Tailwind/madge cleanup

### How should the `bg-gradient-to-*` → `bg-linear-to-*` sweep land?

| Option | Description | Selected |
|--------|-------------|----------|
| One-shot codemod + grep guard | Single commit converts ~15 sites; vitest guard prevents regression. | ✓ |
| Touched-file-only rename | Only rename files already being edited for FE-01/FE-03. | |
| Defer to next milestone | Violates REQUIREMENTS.md FE-05. | |

**User's choice:** One-shot codemod + grep guard
**Notes:** Tailwind v4 still accepts old class name; guard is the mechanism that makes the rename stick.

### How should `madge --circular` run (FE-06)?

| Option | Description | Selected |
|--------|-------------|----------|
| CI-only on frontend-ci.yml | New `Check circular imports` step in the existing workflow. | ✓ |
| CI + pre-commit husky hook | Run in both places; adds local-dev setup churn. | |
| One-time audit, no guard | Run once, don't add persistent check. | |

**User's choice:** CI-only on frontend-ci.yml

### FE-07 opportunistic UX polish — what's the cap?

| Option | Description | Selected |
|--------|-------------|----------|
| Touched-file-only polish | Polish only on pages a FE-01/FE-03/FE-04 fix already touches. | |
| Touched-file + one targeted parts-catalog pass | Above + a single bounded pass on pages/parts/* and components/parts/* with a written checklist. | ✓ |
| No UX work this phase | Violates FE-07. | |

**User's choice:** Touched-file + one targeted parts-catalog pass
**Notes:** Parts catalog flagged in PROJECT.md as "known rough spot"; this is the one exception to strict opportunistic rule.

### QUAL-04 (bandit HIGH gates CI) + QUAL-08 (S3 Glacier lifecycle) — how to land?

| Option | Description | Selected |
|--------|-------------|----------|
| Verify HIGH-exit + crawl-archive only | Synthetic HIGH fixture verifies current flags gate; Terraform lifecycle on production-crawl-data only at 90d. | ✓ |
| Switch bandit to explicit --severity-level high + crawl-archive Glacier | Skip verification; change the invocation definitionally. | |
| Verify HIGH-exit + Glacier on both buckets | Include user-images in lifecycle; risks image-serve latency. | |

**User's choice:** Verify HIGH-exit + crawl-archive only
**Notes:** Don't change working config without verification; user-images must stay hot.

---

## Claude's Discretion

- `lazyWithReload` generic fix (`ComponentType<unknown>` vs narrower bound) — planner picks based on React.lazy inference compatibility.
- Directory-chunking strategy for FE-01 fix tasks — planner picks based on the 06-LINT-BASELINE.txt output.
- Whether the FE-03 coverage test reads App.tsx statically (AST) or runs RTL renders — planner picks least-fragile option.
- Parts-catalog polish checklist contents — planner drafts, UAT approves.

## Deferred Ideas

- Generated API client from openapi_snapshot.json — revisit next milestone if hand-maintained types become a maintenance burden.
- Full parts-catalog UX redesign — captured in REQUIREMENTS.md v2 as UX-V2-01.
- Playwright-with-extensions E2E for QUAL-06 — deferred by Phase 5 D-39.
- Zod / valibot runtime validation — declined; revisit if cross-tier schema drift becomes a real source of production bugs.
- Husky pre-commit hooks (madge, lint) — declined; revisit if CI-only guards are consistently caught late.
- Glacier lifecycle on user-images bucket — declined; revisit only if cost analysis justifies retrieval-latency tradeoff.
- Python 3.13 → 3.14 bump — out of scope this milestone.
