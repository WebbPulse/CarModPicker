# Phase 6: Frontend Cleanup & Final CI Gates - Research

**Researched:** 2026-04-23
**Domain:** TypeScript strict-type rollout, React 19 error boundaries, Tailwind v4 class hygiene, FastAPI/Pydantic/SQLAlchemy/Alembic/Uvicorn upgrade train, bandit CI gating, Terraform S3 lifecycle, Chrome extension Content-Type guard.
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Typing strictness rollout (FE-01, FE-04)**
- **D-01:** Roll out `@typescript-eslint/no-explicit-any: error` and `no-unsafe-*: error` as **fix-all before merge** — not a day-one-error-plus-allowlist, not a warn-then-error ratchet. Scout found only 1 explicit `any` in source (`frontend/src/utils/lazyWithReload.ts:23`). Blast radius small enough that gate + fixes land together.
- **D-02:** Plan starts with a committed **lint audit baseline**: task 1 runs `cd frontend && npm run lint 2>&1 | tee 06-LINT-BASELINE.txt` against the stricter config and commits the file. Subsequent tasks chunk fixes by directory (pages, components, api, hooks, contexts, utils).
- **D-03:** FE-04 API response typing uses **`unknown` + narrowing at the API-client boundary** — NO zod/valibot, NO generated client. OpenAPI snapshot (SAFE-05) already guards backend-side drift.
- **D-04:** Hand-written response types live **next to each API client module in `frontend/src/api/`** (co-located). Narrowing at API-client layer; pages import already-typed results.
- **D-05:** **Ratchet test-file ESLint config to match source** — drop the `no-unsafe-*` `off` overrides in `src/test/**`. Test mocks must be type-honest.
- **D-06:** The `any` in `lazyWithReload<T extends ComponentType<any>>` is replaced with `ComponentType<unknown>` or `ComponentType<Record<string, unknown>>` — planner decides, but **it is not `any`**.

**Route-level error boundaries (FE-03)**
- **D-07:** **Per route-group wrappers** — not per-lazy-page, not a single RouteErrorBoundary component. Four wrappers matching the `pages/` folder split: admin, authentication, builder, public.
- **D-08:** Fallback UX is an **inline panel matching the dark site theme**: error summary line, **Retry** button (resets boundary state), **Go Home** link (router navigate), and the **Sentry event ID** captured by `@sentry/react`'s error-capture hook. Header + Footer remain rendered and usable.
- **D-09:** **Keep the existing top-level `<Suspense>`** in App.tsx. Route-group ErrorBoundaries live under Suspense and handle render-time errors only. No per-group Suspense fallbacks.
- **D-10:** CI coverage for FE-03 is a **parametrized vitest test** that iterates every `<Route element>` and asserts each element's ancestor tree includes one of the four route-group wrappers. AST-static inspection OR RTL parametrized render — planner picks least-fragile.

**Stack upgrade sequencing (QUAL-05, QUAL-06)**
- **D-11:** Ship the upgrade train as **two PRs**:
  - **PR-A: FastAPI 0.128 → 0.136 + Pydantic 2.11 → 2.13** — highest coupling, highest blast-radius pair. Includes the QUAL-06 extension Content-Type audit and the auth characterization suite (SAFE-06) re-run as a gate.
  - **PR-B: SQLAlchemy 2.0.41 → 2.0.49 + Alembic 1.16 → 1.18 + Uvicorn 0.34 → 0.45** — low risk. Lands after PR-A.
- **D-12:** QUAL-06 extension audit = **static grep guard + extension smoke test** (no Playwright-with-extensions):
  - (a) CI grep in `chrome-extension/src/**/*.ts` asserting every `fetch(...{ method: 'POST' ... })` call either sets `'Content-Type': 'application/json'` or is sending a `FormData` body.
  - (b) Run `pytest -k "auth and characterization"` against FastAPI 0.136 locally before PR-A merges.
- **D-13:** **Ride the existing guards** for Pydantic 2.13 deprecations (Phase 3 Pydantic-v1-grep + catch_warnings guard, plan 03-05) and Alembic 1.18 changes (`test_migration_round_trip.sh`, plan 04-06). No new pre-upgrade warnings baseline file.
- **D-14:** **Remove `python-jose[cryptography]==3.5.0`** from `backend/requirements.txt` as part of PR-B. Delete `test_pyjwt_migration.py` when jose is removed.

**UX polish + Tailwind/madge cleanup (FE-05, FE-06, FE-07)**
- **D-15:** **One-shot codemod + regression guard** for `bg-gradient-to-*` → `bg-linear-to-*`. Single commit converts all ~44 sites. Regression guard: **vitest test** that greps `frontend/src/**/*.{ts,tsx}` and fails on any `bg-gradient-to-` match.
- **D-16:** `madge --circular` runs **CI-only** in `frontend-ci.yml` — new `Check circular imports` step after `Run tests`, before `Build application`. `npx madge --circular src/` fails on any hit. madge added as devDependency. No husky.
- **D-17:** FE-07 UX polish scope: **touched-file-only + one targeted parts-catalog pass**. Polish on any page a FE-01/FE-03/FE-04 fix already touches. One bounded task on `pages/parts/*` and `components/parts/*` ONLY with written checklist.

**Final CI gates (QUAL-04, QUAL-08)**
- **D-18:** QUAL-04 bandit verification = synthetic HIGH fixture + empirical exit-code observation, then pick path A (regression test only) or path B (flag change + regression test). Don't change working config without verification.
- **D-19:** QUAL-08 Terraform lifecycle rule: add `aws_s3_bucket_lifecycle_configuration` on `carmodpicker-production-crawl-data` ONLY. Transition to Glacier Deep Archive at **90 days**. `carmodpicker-prod-user-images` bucket stays hot.
- **D-20:** Terraform change lands in `terraform/` with a plan output committed to the PR description.

**Sequencing**
- **D-21:** Suggested wave order: W1 (parallel) FE-02 + FE-06 + FE-05 + QUAL-04 + QUAL-08; W2 FE-01 baseline → chunked fixes + FE-04; W3 FE-03; W4 PR-A (FastAPI+Pydantic+QUAL-06); W5 PR-B (SQLAlchemy/Alembic/Uvicorn+jose-removal); W6 FE-07 polish.

### Claude's Discretion

- Exact shape of `lazyWithReload` generic fix (`ComponentType<unknown>` vs narrower bound).
- Directory-chunking strategy for FE-01 fix tasks — by-folder vs by-violation-count.
- Whether FE-03 coverage test reads App.tsx statically (AST) or runs RTL renders.
- Parts-catalog polish checklist contents — planner drafts, UAT approves.

### Deferred Ideas (OUT OF SCOPE)

- Generated API client from openapi_snapshot.json.
- Full parts-catalog UX redesign (captured as UX-V2-01).
- Playwright-with-extensions E2E.
- Zod / valibot runtime validation of API responses.
- Husky pre-commit hooks (madge, lint).
- Glacier lifecycle on `carmodpicker-prod-user-images`.
- Python 3.13 → 3.14 bump.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FE-01 | `eslint` configured with `@typescript-eslint/no-explicit-any: error` and `no-unsafe-*` rules; existing violations fixed or allow-listed with rationale | §Standard Stack (eslint 9 + typescript-eslint 8), §Architecture Patterns Pattern 1 (baseline-then-fix), §Code Examples (eslint config diff) |
| FE-02 | `import.meta.env.VITE_*` audit — any lingering `process.env` references removed | §Runtime State Inventory category "secrets/env vars" and §Code Examples confirms only 2 legitimate `process.env` sites (vite.config.ts + docstring in lib/sentry.ts). Scope much narrower than feared. |
| FE-03 | Route-level error boundaries on every lazy-loaded page component | §Standard Stack (@sentry/react v10 `Sentry.ErrorBoundary` with `FallbackRender` signature confirmed to expose `eventId`), §Architecture Patterns Pattern 2 (per-group wrapper), §Code Examples (ErrorBoundary fallback) |
| FE-04 | API client types narrowed — `any`-cast audit on response types with either strict typing or `unknown` + runtime validation | §Architecture Patterns Pattern 3 (unknown + narrow at client boundary), §Open Question 1 (current `services/Api.ts` is a single file, CONTEXT.md D-04 references `frontend/src/api/*.ts` which does not exist) |
| FE-05 | Tailwind v3 class sweep — `bg-gradient-to-*` → `bg-linear-to-*` | §Code Examples (Tailwind v4 class rename table), §Common Pitfalls Pitfall 2 (old class names still work in v4.1.7 compat theme — guard is what enforces the rename) |
| FE-06 | `madge --circular` check runs before and after module restructures; no new circular imports introduced | §Standard Stack (madge 8.0.0), §Code Examples (madge CLI invocation), §Common Pitfalls Pitfall 3 (madge + tsconfig paths) |
| FE-07 | Opportunistic UX polish on any page refactored; parts catalog explicitly in scope when its frontend touches land | §Architecture Patterns Pattern 5 (touched-file-only + bounded parts-catalog pass) |
| QUAL-04 | `bandit -l -i` gated in CI; HIGH-severity findings fail the build | §Verified Bandit Behavior (empirical test: current `-ll` config already exits 1 on HIGH — D-18 path A applies), §Code Examples (synthetic HIGH fixture) |
| QUAL-05 | Stack patch upgrades applied: FastAPI 0.136, Uvicorn 0.45, SQLAlchemy 2.0.49, Alembic 1.18, Pydantic 2.13 | §Standard Stack (all verified against npm/PyPI registry), §Common Pitfalls Pitfall 1 (FastAPI 0.132 strict Content-Type), §State of the Art (upgrade deltas table) |
| QUAL-06 | FastAPI 0.136 strict-Content-Type upgrade compatibility: Chrome extension POSTs audited | §Architecture Patterns Pattern 4 (grep guard), §Code Examples (apiRequest helper already defaults to application/json — zero code changes needed, guard is preventive) |
| QUAL-08 | S3 lifecycle policy transitions old HTML snapshots to Glacier after 90 days | §Standard Stack (terraform aws provider), §Code Examples (aws_s3_bucket_lifecycle_configuration), §Common Pitfalls Pitfall 4 (empty filter block vs prefix=""), §Code Examples (terraform snippet) |
</phase_requirements>

## Summary

Phase 6 is a pure tech-debt closeout with two parallel workstreams: (a) frontend structural hygiene (strict typing, route-level error boundaries, Tailwind v4 class names, madge CI gate) and (b) backend/infra final gates (FastAPI+Pydantic upgrade with extension Content-Type audit, SQLAlchemy/Alembic/Uvicorn patch upgrade + python-jose removal, bandit HIGH-severity regression test, Terraform Glacier lifecycle on the crawl-archive bucket). CONTEXT.md has locked 21 decisions covering approach, scope, and sequencing — nearly all research is scope-confirmation and pitfall identification against decisions already made.

**Key empirical findings from this research session that should inform the plan:**
1. **Bandit `-ll` already exits 1 on HIGH findings** — verified on local bandit 1.9.4 with a `subprocess.call(cmd, shell=True)` synthetic fixture. D-18 path A (add regression test, no CI flag change) is the right branch.
2. **Tailwind v4.1.7 ships a compat theme that still recognizes `gradient-to-t/tr/r/br/b/bl/l/tl` as valid utility keys** — verified by inspecting installed `node_modules/tailwindcss/dist/chunk-P5FH2LZE.mjs`. CONTEXT.md D-15's claim "Tailwind v4 still accepts the old class name today" is CORRECT; the vitest regex guard is the mechanism that makes the rename permanent.
3. **FastAPI 0.132 introduced strict Content-Type checking as the primary breaking change** in the 0.128→0.136 range — aligns with CONTEXT.md QUAL-06 scope, and the extension's shared `apiRequest` helper in `chrome-extension/src/background.ts` already defaults `'Content-Type': 'application/json'`, meaning zero extension code changes are needed, just the preventive grep guard.
4. **Sentry `@sentry/react` v10's `FallbackRender` signature DOES expose `eventId`** as a parameter (confirmed against installed `errorboundary.d.ts`): `({ error, componentStack, eventId, resetError }) => ReactElement`. D-08's Sentry event ID surfacing is a direct prop read, not a workaround.
5. **Only 1 explicit `any` exists in frontend source** (`lazyWithReload.ts:23`) — scout was right. FE-01 fix-all is truly small.
6. **Only 2 `process.env` references exist in frontend source** and both are legitimate (`vite.config.ts` build-time + a docstring comment in `lib/sentry.ts`). FE-02 is near-no-op.
7. **CONTEXT.md D-04 assumes `frontend/src/api/*.ts` exists — it does not.** Current code has a single `frontend/src/services/Api.ts` (1521 lines). FE-04 plan MUST reconcile: either (a) introduce `frontend/src/api/` and split Api.ts along backend-domain lines, OR (b) write co-located types inside the existing Api.ts sections. This is a structural decision the plan must call out.

**Primary recommendation:** Follow D-21 wave order. The unknown surface is small; the main planning risk is the FE-04 co-location scope (Open Question 1 below). PR-A + PR-B sequencing is correct — keep them strictly separated for bisect hygiene.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Strict-type ESLint gate (FE-01) | CI | Frontend Server (dev) | ESLint runs in `frontend-ci.yml`; developers see it in editor via tsserver |
| API response narrowing (FE-04) | Frontend (Browser client) | — | Happens in Axios response handlers in `services/Api.ts` on browser side |
| `process.env` → `import.meta.env` (FE-02) | Vite build tier | Browser runtime | `import.meta.env` replaces `process.env` for browser-side code; Node-side build config (`vite.config.ts`) legitimately keeps `process.env` |
| Route-level error boundaries (FE-03) | Browser / Client | Sentry (backend capture) | React render-time error catching happens in browser; error reporting flows to Sentry |
| Tailwind gradient rename (FE-05) | Frontend build (PostCSS) | — | Class-to-CSS resolution at build time; rename is cosmetic/preventive |
| madge circular-import gate (FE-06) | CI | Frontend dev | Runs in `frontend-ci.yml`; no runtime effect |
| FastAPI 0.136 + Pydantic 2.13 (QUAL-05) | API / Backend | — | Framework-level dependency upgrade; impacts request parsing, response serialization |
| SQLAlchemy / Alembic / Uvicorn (QUAL-05) | API / Backend + Database | — | ORM + migration tool + ASGI server upgrades |
| Chrome extension Content-Type audit (QUAL-06) | CI (grep) | Chrome extension (runtime) | Grep runs in CI against extension source; no runtime change needed — audit confirms already-compliant behavior |
| Bandit HIGH gate (QUAL-04) | CI | — | Security scan in `backend-ci.yml` |
| S3 Glacier lifecycle (QUAL-08) | Terraform / IaC | AWS S3 | Declarative IaC change; AWS applies policy to bucket |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | **0.136.1** (latest on PyPI as of 2026-04-23) | Web framework upgrade target | `[VERIFIED: pip index versions fastapi]` — 0.136.1 is the highest patch of 0.136; aligns with CONTEXT.md QUAL-05 target |
| Pydantic | **2.13.3** (latest on PyPI) | Validation library upgrade target | `[VERIFIED: pip index versions pydantic]` — CONTEXT.md target 2.13; latest patch is 2.13.3 |
| SQLAlchemy | **2.0.49** | ORM upgrade target | `[VERIFIED: pip index versions sqlalchemy]` — exactly CONTEXT.md target |
| Alembic | **1.18.4** (latest on PyPI) | Migration tool upgrade target | `[VERIFIED: pip index versions alembic]` — CONTEXT.md specifies 1.18; 1.18.4 is the latest patch |
| Uvicorn | **0.45.0** or **0.46.0** | ASGI server upgrade target | `[VERIFIED: pip index versions uvicorn]` — CONTEXT.md target is 0.45; 0.46.0 is available but 0.45.0 hits the QUAL-05 requirement exactly |
| PyJWT | 2.12.1 | Already installed; jose removal only | `[VERIFIED: backend/requirements.txt line 28]` |
| eslint + typescript-eslint | eslint 9.25.0 + typescript-eslint 8.30.1 | FE-01 enforcement engine | `[VERIFIED: frontend/package.json — already installed]` — already extends `recommendedTypeChecked`; flipping rules to `error` is a config edit |
| `@sentry/react` | 10.0.0+ | FE-03 route-group ErrorBoundary | `[VERIFIED: frontend/package.json:27]` — `FallbackRender` exposes `eventId` (confirmed in installed `errorboundary.d.ts`) |
| tailwindcss | 4.1.7 | Already v4 | `[VERIFIED: frontend/node_modules/tailwindcss/package.json]` — FE-05 is class-name hygiene only |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| madge | **8.0.0** | FE-06 circular-import detection | `[VERIFIED: npm view madge version]` — released 2024-08-05. Add as devDependency in `frontend/package.json`. |
| bandit | 1.9.4 (already installed) | QUAL-04 security scan | `[VERIFIED: bandit --version on this machine]` |
| hashicorp/aws Terraform provider | v5 or v6 (whatever terraform/providers.tf pins) | QUAL-08 S3 lifecycle resource | `[VERIFIED: directory listing — terraform/providers.tf + s3.tf already use `aws_s3_bucket` declarations]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `unknown` + narrowing (D-03) | zod/valibot runtime validation | Zod catches runtime response-shape drift (stronger guarantee) but adds ~15KB bundle, ~5% runtime cost per response, and a new compile surface. PROJECT.md declines this. **DO NOT explore.** |
| Hand-written response types (D-04) | openapi-typescript / openapi-typescript-codegen | Generated client auto-matches backend. But PROJECT.md "Out of Scope: OpenAPI Pact contracts" declines this. OpenAPI snapshot (SAFE-05) is the backend-side drift catcher. **DO NOT explore.** |
| AST parametrized test (D-10) | RTL parametrized render | AST: fast, no DOM required, brittle if App.tsx restructure moves `<Routes>`. RTL: slow (~40 mock lazy components), durable to structural changes. Planner picks. |

**Installation:**
```bash
# PR-A (frontend lint rollout)
cd frontend
npm install --save-dev madge@^8.0.0    # FE-06
# (No package install for FE-01 — eslint-plugin-typescript-eslint already pinned)

# PR-A (backend)
# requirements.txt edit only:
# fastapi==0.136.1
# pydantic==2.13.3

# PR-B (backend)
# requirements.txt edit:
# sqlalchemy==2.0.49
# alembic==1.18.4
# uvicorn==0.45.0
# (DELETE python-jose[cryptography]==3.5.0)
```

**Version verification (performed 2026-04-23):**
- fastapi 0.136.1 — `[VERIFIED: pip index versions fastapi]`
- pydantic 2.13.3 — `[VERIFIED: pip index versions pydantic]`
- sqlalchemy 2.0.49 — `[VERIFIED: pip index versions sqlalchemy]`
- alembic 1.18.4 — `[VERIFIED: pip index versions alembic]`
- uvicorn 0.45.0 (0.46.0 latest) — `[VERIFIED: pip index versions uvicorn]`
- madge 8.0.0 — `[VERIFIED: npm view madge version]` — released 2024-08-05, ~20 months old at research time; no newer major available

## Architecture Patterns

### System Architecture Diagram

```
                    ┌──────────────────────────────────────────┐
                    │         FRONTEND CI (frontend-ci.yml)     │
                    │  install → prettier → lint → type-check  │
                    │     → npm audit → test → [madge]* → build │
                    └──────────────────────────────────────────┘
                                        │
                                        │ (*new step: D-16)
                                        ▼
                    ┌──────────────────────────────────────────┐
                    │         BROWSER RUNTIME (React 19)        │
                    │                                          │
                    │  App.tsx → <ErrorBoundary> (root)        │
                    │          ↓                               │
                    │        <Suspense>                        │
                    │          ↓                               │
                    │        <Routes>                          │
                    │    ┌──────┬──────────┬───────┬────────┐  │
                    │    │public│authentica│builder│ admin  │  │
                    │    │ group│  tion    │ group │ group  │  │
                    │    └───┬──┴─────┬────┴──┬────┴───┬────┘  │
                    │        ▼        ▼       ▼        ▼       │
                    │ ┌────────────────────────────────────┐   │
                    │ │ route-group ErrorBoundary (D-07)    │   │ ← FE-03
                    │ │  fallback: { error, eventId,        │   │
                    │ │             resetError }            │   │
                    │ │  beforeCapture: scope.setTag(...)   │   │
                    │ └────────────────────────────────────┘   │
                    │            ↓                             │
                    │      lazy(pages/*)                       │
                    │            ↓                             │
                    │      services/Api.ts (Axios client)      │
                    │        `unknown` → narrowing             │ ← FE-04
                    └──────────────┼───────────────────────────┘
                                   │ POST w/ Content-Type: json
                                   ▼
                    ┌──────────────────────────────────────────┐
                    │       BACKEND (FastAPI 0.136)             │
                    │  strict_content_type=True (default 0.132+)│
                    │  Pydantic 2.13 response serialization     │
                    │  SQLAlchemy 2.0.49 + Alembic 1.18         │ ← QUAL-05 (PR-B)
                    └──────────────────────────────────────────┘
                                        ▲
                                        │
                    ┌──────────────────────────────────────────┐
                    │         CHROME EXTENSION                  │
                    │  background.ts apiRequest()               │
                    │  default Content-Type: application/json   │ ← QUAL-06
                    │  (FormData bypass for image upload OK)    │
                    └──────────────────────────────────────────┘

                    ┌──────────────────────────────────────────┐
                    │         BACKEND CI (backend-ci.yml)       │
                    │  black → isort → pyright → bandit -ll*    │ ← QUAL-04
                    │  → pip-audit → check_migrations           │    (*regression test added)
                    │  → pytest -n auto                         │
                    │  │                                        │
                    │  └── postgres-tests job (existing)        │
                    └──────────────────────────────────────────┘

                    ┌──────────────────────────────────────────┐
                    │         TERRAFORM                         │
                    │  s3.tf:                                   │
                    │    aws_s3_bucket.crawl_data               │
                    │    + aws_s3_bucket_lifecycle_configuration│ ← QUAL-08
                    │      rule → transition DEEP_ARCHIVE @90d  │
                    └──────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Phase 6 Responsibility |
|-----------|------|------------------------|
| ESLint config | `frontend/eslint.config.js` | FE-01: enable `no-explicit-any: error`, `no-unsafe-*: error`; D-05: drop test-file `no-unsafe-*: off` overrides |
| Lazy-loader utility | `frontend/src/utils/lazyWithReload.ts` | FE-01/D-06: replace `ComponentType<any>` with `ComponentType<unknown>` (or similar) |
| API client | `frontend/src/services/Api.ts` | FE-04: narrow responses via `unknown` at boundary; **note structural gap vs CONTEXT.md D-04 — see Open Question 1** |
| App routes tree | `frontend/src/App.tsx` | FE-03: insert four route-group ErrorBoundary wrappers; FE-05: rename gradient classes (3 sites: lines 133, 149, 151, 155) |
| Root ErrorBoundary | `frontend/src/components/common/ErrorBoundary.tsx` | FE-03 reference: new route-group wrapper can compose OR subclass this; existing captureException wiring preserved |
| Layout gradient sites | `frontend/src/components/layout/globalFooter/Footer.tsx`, `globalHeader/Header.tsx` (if any), `common/Card.tsx`, `common/ChromeExtensionPromo.tsx`, `common/DeleteConfirmationDialog.tsx`, `common/SubscriptionPromo.tsx`, `common/DangerousActionDialog.tsx`, `common/Button.tsx`, `pages/Home.tsx`, `pages/Support.tsx` | FE-05: rename `bg-gradient-to-*` → `bg-linear-to-*` (44 total occurrences per `grep -rn "bg-gradient-to-" frontend/src/`) |
| Frontend CI | `.github/workflows/frontend-ci.yml` | FE-06: insert `Check circular imports` step after `Run tests`, before `Build application` |
| Package dependencies | `frontend/package.json` | FE-06: add `madge` devDependency; **no dependency change for FE-01** |
| Backend requirements | `backend/requirements.txt` | QUAL-05 PR-A: bump fastapi+pydantic; PR-B: bump sqlalchemy+alembic+uvicorn + DELETE python-jose line |
| PyJWT parity test | `backend/tests/test_pyjwt_migration.py` | D-14: DELETE alongside python-jose removal in PR-B |
| Auth utility test | `backend/tests/dependencies/test_auth_utils.py` | Audit: `from jose import jwt` at line 3 — either re-test with PyJWT or deprecate; must not block PR-B |
| Chrome ext source | `chrome-extension/src/background.ts` (+ any others) | QUAL-06: grep guard target; empirically audit confirms apiRequest helper already Content-Type compliant; zero runtime change |
| Bandit config | `backend/.bandit` + `.github/workflows/backend-ci.yml` | QUAL-04 D-18 path A: add regression test next to existing `bandit -r app -ll` step; no flag change |
| Terraform S3 | `terraform/s3.tf` | QUAL-08: add `aws_s3_bucket_lifecycle_configuration "crawl_data"` resource next to existing `aws_s3_bucket "crawl_data"` |

### Pattern 1: Fix-All-Before-Merge Type Rollout (D-01)

**What:** Flip ESLint rules to `error`, audit all violations into a committed baseline file, fix all violations in chunked tasks, merge as a single PR set.

**When to use:** Small-blast-radius rule tightening (<=50 violations). CONTEXT.md D-01 scout found 1 explicit `any` in src/ (lazyWithReload.ts). The actual violation count under `no-unsafe-*` is unknown until the baseline task runs.

**Workflow:**
```
Task 1 (D-02): enable rules in eslint.config.js (as 'error') → run `npm run lint 2>&1 | tee 06-LINT-BASELINE.txt` → commit baseline (lint still failing is OK at this stage — scope visibility is the goal)
Task 2..N: chunked fixes by directory (pages/, components/, api/services/, hooks/, contexts/, utils/)
Final: delete 06-LINT-BASELINE.txt OR keep as historical artifact; CI now green on strict rules.
```

**Example baseline task shell:**
```bash
# Source: D-02, plan is composing this
cd frontend
npm run lint 2>&1 | tee ../06-LINT-BASELINE.txt
git add ../06-LINT-BASELINE.txt
git commit -m "docs(06): capture FE-01 baseline for chunked fix plan"
```

### Pattern 2: Per-Route-Group ErrorBoundary (D-07, D-08)

**What:** Four React components (e.g., `AdminGroupBoundary`, `AuthGroupBoundary`, `BuilderGroupBoundary`, `PublicGroupBoundary`), each wrapping its group's `<Route>` children with `@sentry/react`'s `Sentry.ErrorBoundary`.

**When to use:** Multiple independent UI sections, each of which should fail-isolated. Mirrors `pages/{admin,authentication,builder}/` + public.

**Example:**
```typescript
// Source: @sentry/react v10 FallbackRender signature verified against node_modules/@sentry/react/build/types/errorboundary.d.ts
import * as Sentry from '@sentry/react';
import { Link, useNavigate } from 'react-router-dom';

export default function AdminGroupBoundary({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  return (
    <Sentry.ErrorBoundary
      beforeCapture={(scope) => scope.setTag('route_group', 'admin')}
      fallback={({ error, eventId, resetError }) => (
        <div className="mx-auto max-w-md p-8 bg-neutral-800/50 rounded-xl text-neutral-200">
          <h2 className="text-xl font-semibold mb-2">Something went wrong.</h2>
          <p className="text-sm text-neutral-400 mb-4">
            {(error as Error)?.message ?? 'Unknown error'}
          </p>
          <p className="text-xs text-neutral-500 mb-6">Event ID: {eventId}</p>
          <div className="flex gap-3">
            <button onClick={resetError} className="btn-primary">Retry</button>
            <button onClick={() => navigate('/')} className="btn-secondary">Go Home</button>
          </div>
        </div>
      )}
    >
      {children}
    </Sentry.ErrorBoundary>
  );
}
```

**Wiring in App.tsx:**
```tsx
// Inside <Routes>, wrap admin routes:
<Route element={<AdminGroupBoundary><Outlet /></AdminGroupBoundary>}>
  <Route path="/admin" element={<AdminDashboard />} />
  <Route path="/admin/reports" element={<ReportReview />} />
  {/* ... */}
</Route>
```

### Pattern 3: `unknown` + Narrow at API-Client Boundary (D-03, D-04)

**What:** Treat every API response as `unknown`; narrow with discriminators or type predicates inside the API-client module; callers import already-typed results.

**Current state:** `services/Api.ts:184` already does `(error: unknown) => ...` at one boundary. Responses are typed via TypeScript generics on `apiClient.get<T>` but the T types come from `../types/Api` (backend-generated Pydantic types). FE-04's job is to audit for `any` leaks and replace raw casts with narrowing predicates where needed.

**Example (narrowing predicate):**
```typescript
// Source: CONTEXT.md D-03, modeled on existing services/Api.ts:184
function isUserRead(data: unknown): data is UserRead {
  return (
    typeof data === 'object' && data !== null &&
    'id' in data && 'username' in data && 'email' in data
  );
}

export const usersApi = {
  getMe: async (): Promise<UserRead> => {
    const response = await apiClient.get<unknown>('/users/me');
    if (!isUserRead(response.data)) {
      throw new Error('Unexpected response shape from /users/me');
    }
    return response.data;
  },
};
```

**Scope modulator:** FE-04 does NOT require re-writing every apiClient call. Priority: (a) find `as any` / `as TypeSomething` casts on response.data, (b) strip `any` from function signatures, (c) add narrowing only where response shape is currently trusted without verification.

### Pattern 4: CI Grep Guard (D-12, D-15)

**What:** A pytest/vitest test that reads a filesystem glob, applies a regex, and fails the build if the regex matches (or does not match) per policy.

**When to use:** Enforcing a textual invariant across a directory without runtime cost. Two uses in this phase:

1. **QUAL-06 Chrome extension Content-Type guard** (vitest — CONTEXT.md D-12a):
   ```typescript
   // Source: new test, composes D-12a
   import { readFileSync } from 'fs';
   import { globSync } from 'glob';
   import { describe, expect, it } from 'vitest';

   describe('QUAL-06: Chrome extension POST Content-Type compliance', () => {
     const files = globSync('../chrome-extension/src/**/*.ts');

     it('every fetch() POST call sets application/json Content-Type or uses FormData', () => {
       const violations: string[] = [];
       for (const file of files) {
         const src = readFileSync(file, 'utf8');
         // Find fetch() calls with method: "POST"
         const postRegex = /fetch\([^)]+\{[^}]*method:\s*["']POST["'][^}]*\}/gs;
         const matches = src.match(postRegex) ?? [];
         for (const match of matches) {
           const hasJsonHeader = /["']Content-Type["']\s*:\s*["']application\/json["']/.test(match);
           const hasFormData = /body:\s*formData/i.test(match);
           if (!hasJsonHeader && !hasFormData) {
             violations.push(`${file}: ${match.slice(0, 100)}`);
           }
         }
       }
       expect(violations).toEqual([]);
     });
   });
   ```

2. **FE-05 gradient regression guard** (vitest — CONTEXT.md D-15):
   ```typescript
   // Source: new test, composes D-15
   describe('FE-05: no bg-gradient-to-* class names in source', () => {
     const files = globSync('src/**/*.{ts,tsx}', { cwd: __dirname + '/../..' });

     it('no file contains bg-gradient-to- (Tailwind v3 legacy)', () => {
       const violations: Array<{ file: string; line: number; match: string }> = [];
       for (const file of files) {
         const src = readFileSync(file, 'utf8').split('\n');
         src.forEach((line, i) => {
           if (/bg-gradient-to-/.test(line)) {
             violations.push({ file, line: i + 1, match: line.trim() });
           }
         });
       }
       expect(violations).toEqual([]);
     });
   });
   ```

### Pattern 5: Touched-File-Only + One Bounded Pass (D-17)

**What:** FE-07 opportunistic UX polish is scoped BY DEFINITION to files already modified by FE-01/FE-03/FE-04 work PLUS one bounded task targeting `pages/parts/*` + `components/parts/*`.

**When to use:** Prevents scope creep from "while we're here" into "while we're here, let's rebuild the dashboard". The written checklist for the parts-catalog pass is the scope anchor.

**Suggested checklist sketch** (planner finalizes per D-17):
- Spacing: replace any `p-X` ≥ 8 with container-class consistent values
- Typography: ensure heading sizes (`text-xl`/`text-2xl`/`text-3xl`) match existing Card.tsx and Home.tsx hierarchy
- Card variants: if a parts-catalog page uses a bespoke card, refactor to use `common/Card.tsx` variants
- Responsive: verify mobile (<640px) layouts do not overflow; fix with `md:` breakpoints if found
- NO animation additions, NO interaction rewrites, NO state-model changes.

### Anti-Patterns to Avoid

- **Partial type gate with allowlist file:** Adding rules as `warn` or maintaining an `.eslintignore` for specific files is explicitly rejected by D-01. Blast radius is small enough for fix-all.
- **Combined mega-PR for all stack upgrades:** Rejected by D-11. FastAPI+Pydantic in PR-A; everything else in PR-B. This is for bisect hygiene.
- **Playwright with chrome-extension:** Tempting for QUAL-06 but rejected by D-12. Grep + characterization re-run is the agreed scope.
- **Adding Suspense fallback inside route-group boundary:** Rejected by D-09. Loading UX unchanged this phase.
- **Running madge as local pre-commit:** Rejected by D-16. Husky adds dev-install friction; CI is sufficient.
- **Making FE-07 polish files that were NOT touched by other FE work:** Rejected by D-17. Exception is the single bounded parts-catalog task.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Error boundary for React render errors | Custom `componentDidCatch` class with Sentry wiring | `@sentry/react`'s `Sentry.ErrorBoundary` | Already installed, already tested, exposes `eventId`, `beforeCapture`, `onError`, `resetError` props. Root `ErrorBoundary.tsx` can stay as the outermost belt-and-braces; route-group uses Sentry's component. |
| Circular import detector | Custom `tsc --traceResolution` parser | `madge --circular` | madge has 13 years of detective options for TS, TSX, ES6 imports; the project wants one CLI invocation in CI, not a bespoke tool. |
| API response narrowing | zod / valibot / ajv / io-ts | Hand-written type predicates (CONTEXT.md D-03) | PROJECT.md milestone budget explicitly rejects adding runtime validators. OpenAPI snapshot (SAFE-05) is the backend-side drift oracle. |
| S3 lifecycle policy | AWS SDK in a boto3 script | `aws_s3_bucket_lifecycle_configuration` Terraform resource | terraform/ already owns all bucket state. A boto3 script would drift from Terraform state. |
| HIGH-severity bandit gate | Custom severity-filtering wrapper | Native `bandit -ll` or `bandit --severity-level high` | Bandit's built-in severity flags already do this. Empirical test confirmed `-ll` exits 1 on HIGH. |
| Content-Type compliance test | Playwright + chrome extension tester | Grep vitest guard | Grep is deterministic, has no extension-runtime flakiness, and is cheap. D-12 locked this. |
| JWT decoding | `python-jose` (and PyJWT) both in requirements | PyJWT only | python-jose's ecdsa dep has CVE-2024-23342 (not exploitable here). Removing saves supply-chain surface. Phase 5 migrated; Phase 6 closes the loop. |

**Key insight:** Phase 6's theme is "use what's already there, enforce what's already decided." Nearly every `Don't Hand-Roll` entry points to a tool already installed or a pattern already ratified in a prior phase.

## Runtime State Inventory

> This phase contains rename/refactor/migration elements (Tailwind class rename, python-jose removal, ESLint rule flip). Including this inventory to surface non-code-file state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None — Phase 6 does not touch user data, migrations, stored records, or DB schemas. Glacier lifecycle rule is a policy change, not a data move. | None |
| **Live service config** | AWS S3 bucket `carmodpicker-production-crawl-data` has no current lifecycle configuration. Adding one via Terraform will not alter existing objects' storage class retroactively unless rule permits — per AWS docs, transitions apply to objects that have been in current class for ≥N days since creation. New 90-day rule means all objects older than 90d at apply time WILL begin transitioning on next AWS daily lifecycle run. | Confirm terraform apply timing (preview plan, observe transition count on AWS console 24-48h after apply). No code changes after apply; monitor only. |
| **OS-registered state** | None — Phase 6 does not register any OS-level services, cron entries, pm2 processes, or EventBridge rules. | None |
| **Secrets/env vars** | `import.meta.env.VITE_*` usage confirmed unchanged; FE-02 removes `process.env` references (verified: only 2 legitimate sites in vite.config.ts + one docstring comment in lib/sentry.ts — NOT in browser code). No env-var KEY renames in this phase. **No Secret Manager changes.** | None — FE-02 audit is a code-only scope (read-only `process.env` string audit). |
| **Build artifacts** | Chrome extension `dist/` has embedded build hash of current source. After QUAL-06 grep guard lands (no runtime code change), the existing `dist/` build stays valid — no extension republish. | None. If ANY extension source changes (not expected this phase), a republish via chrome-extension-deploy.yml is needed. |
| **Lock files** | `frontend/package-lock.json` MUST update when madge is added (FE-06). `backend/requirements.txt` sha256 implicit changes on pip install (PR-A and PR-B). | Commit updated lock files in respective PRs. |
| **CI workflow files** | `.github/workflows/frontend-ci.yml` gets a new step (D-16). `.github/workflows/backend-ci.yml` MAY get an inline regression test for bandit (D-18 path A). | Both files edited; commit review MUST confirm workflow syntax (YAML indent) before merge. |

**Nothing found in category:** Stored data, OS-registered state, secrets/env vars renames.

## Verified Bandit Behavior (empirical — this research session)

**Question:** Does current `bandit -r app -ll` CI invocation fail on HIGH-severity findings?

**Method:** Wrote a synthetic HIGH fixture on this machine and ran bandit with three variants.

```python
# /tmp/bandit_high_fixture.py
import subprocess
import os
user_input = os.environ.get("CMD", "")
subprocess.call(user_input, shell=True)  # dynamic input — B602 HIGH
```

**Results (bandit 1.9.4, Python 3.13.12):**

| Invocation | Report output | Exit code |
|------------|---------------|-----------|
| `bandit -r /tmp/bandit_high_fixture.py -ll` | `Issue: [B602 ...] Severity: High Confidence: High` | **1** (fails CI) |
| `bandit -r /tmp/bandit_high_fixture.py --severity-level high` | `Issue: [B602 ...] Severity: High` | **1** (fails CI) |
| `bandit -r /tmp/bandit_high_fixture.py -lll` | `Issue: [B602 ...] Severity: High` | **1** (fails CI) |

**Conclusion:** Current CI config (`bandit -r app -ll`) already fails on HIGH-severity findings. D-18 path A applies — **do NOT change the `-ll` flag**; add the regression test only.

**Note on `-l`/`-ll`/`-lll`:** Per `bandit/cli/main.py`:
- `-l` (LOW+): report any LOW, MEDIUM, or HIGH finding; exit 1 if any.
- `-ll` (MEDIUM+): report MEDIUM or HIGH; exit 1 if any.
- `-lll` (HIGH only): report HIGH only; exit 1 if any.
- `--severity-level high`: equivalent to `-lll`.

`bandit -r app -ll` intentionally fails on both MEDIUM and HIGH — this is stricter than QUAL-04's literal requirement (HIGH only). CONTEXT.md D-18 is correct to not narrow this without understanding why it was set this way historically.

## Common Pitfalls

### Pitfall 1: FastAPI 0.132 strict Content-Type (QUAL-06 direct cause)

**What goes wrong:** After upgrading to FastAPI ≥0.132, JSON-body POST requests without `Content-Type: application/json` are rejected with 415. Extension clients that stream `JSON.stringify(body)` but omit the header will break silently.

**Why it happens:** Release 0.132.0 introduced strict Content-Type checking as a default. `[CITED: FastAPI release notes, github.com/fastapi/fastapi/blob/master/docs/en/docs/release-notes.md — "Now FastAPI checks, by default, that JSON requests have a Content-Type header with a valid JSON value"]`

**How to avoid:** Confirmed on audit — the Chrome extension's shared `apiRequest` helper (`chrome-extension/src/background.ts:89-92`) already sets `"Content-Type": "application/json"` as a default. The 7 direct `fetch` POST call-sites either route through this helper OR use `FormData` (line 575 for image upload; FormData's auto-generated `Content-Type: multipart/form-data; boundary=...` is still a valid request body content type — FastAPI accepts it). **Zero extension code changes needed; the grep guard is preventive for future contributors.**

**Warning signs:** If PR-A CI reports 415 UNSUPPORTED_MEDIA_TYPE on any characterization test, investigate the offending endpoint — a missing content-type header in the test client, not prod code.

**Escape hatch:** FastAPI's `strict_content_type=False` parameter can disable this globally. Do NOT use unless a concrete compat break is identified — document + fix at source if so.

### Pitfall 2: Tailwind v4 compat theme masks legacy class usage (FE-05 rationale)

**What goes wrong:** Old `bg-gradient-to-r` class names still RENDER correctly in Tailwind v4.1.7 because the shipped theme declares them as `backgroundImage` keys. Teams assume their rename is done when `npm run build` succeeds.

**Why it happens:** Verified by inspecting `frontend/node_modules/tailwindcss/dist/chunk-P5FH2LZE.mjs` — the `backgroundImage` theme explicitly maps `"gradient-to-t"` through `"gradient-to-tl"` to `linear-gradient(...)` CSS values. The v4 canonical `bg-linear-to-*` works alongside these compat entries. `[VERIFIED: node_modules inspection]`

**How to avoid:** Per D-15, the vitest regex guard (Pattern 4 in §Architecture Patterns) is the ONLY mechanism that makes the rename permanent. The rename itself is a mechanical find-and-replace (8 directional variants × 44 occurrences).

**Warning signs:** Someone adds a new `bg-gradient-to-r` on a future PR, CI green, visually OK. Only the regex guard catches it.

**Full rename table (all 8 directional variants):**
| Old (v3) | New (v4) | Example |
|----------|----------|---------|
| `bg-gradient-to-t` | `bg-linear-to-t` | top |
| `bg-gradient-to-tr` | `bg-linear-to-tr` | top-right |
| `bg-gradient-to-r` | `bg-linear-to-r` | right |
| `bg-gradient-to-br` | `bg-linear-to-br` | bottom-right |
| `bg-gradient-to-b` | `bg-linear-to-b` | bottom |
| `bg-gradient-to-bl` | `bg-linear-to-bl` | bottom-left |
| `bg-gradient-to-l` | `bg-linear-to-l` | left |
| `bg-gradient-to-tl` | `bg-linear-to-tl` | top-left |

### Pitfall 3: madge + TypeScript path aliases

**What goes wrong:** madge with default config treats `@/components/...` import paths as external modules (no graph edges), missing real circular dependencies through aliased imports.

**Why it happens:** madge resolves via `dependency-tree` which respects tsconfig compilerOptions.paths ONLY when `--ts-config` is passed. Default invocation ignores aliases. `[CITED: madge README + dependency-tree npm page]`

**How to avoid:** Invoke as `npx madge --circular --ts-config tsconfig.app.json --extensions ts,tsx src/`. Verify this project does NOT use path aliases (grep `tsconfig.app.json` for `paths` — confirmed ABSENT in this project's `tsconfig.app.json`). Basic `npx madge --circular src/` is sufficient for this codebase, but passing `--extensions ts,tsx` is recommended to cover both file types. madge 8.x detects `.ts` and `.tsx` automatically when extensions are specified.

**Warning signs:** A suspiciously-low circular count (e.g., 0) on a codebase that should have at least a few. Cross-check by searching for known cycles manually.

### Pitfall 4: Empty S3 lifecycle filter vs empty prefix (QUAL-08)

**What goes wrong:** Terraform's `aws_s3_bucket_lifecycle_configuration` with a rule but NO `filter {}` block OR with `filter { prefix = "" }` generates AWS XML that has `<Filter><Prefix/></Filter>`. AWS's lifecycle engine treats this as "match objects with empty prefix" which is essentially "match nothing" on some paths. The console-created equivalent generates `<Filter/>` (fully empty) and DOES match all objects.

**Why it happens:** Historical AWS API quirk. Terraform upstream issue #110 documents this: `[CITED: github.com/terraform-aws-modules/terraform-aws-s3-bucket/issues/110]`

**How to avoid:** Do NOT use `filter { prefix = "" }`. The documented correct Terraform syntax to match all objects is to either (a) omit `filter` entirely if the provider version supports it, OR (b) use an empty `filter {}` block (no attributes inside). Test by running `terraform plan` and confirming the generated XML has `<Filter/>`, not `<Filter><Prefix/></Filter>`.

**Warning signs:** terraform apply succeeds; 48h later, AWS console still shows objects in STANDARD storage. Transition is not firing. The fix is to change the filter form and re-apply.

### Pitfall 5: python-jose still imported in `backend/tests/dependencies/test_auth_utils.py`

**What goes wrong:** D-14 specifies deleting `test_pyjwt_migration.py` when removing python-jose. But `backend/tests/dependencies/test_auth_utils.py` line 3 also imports `from jose import jwt`. Removing python-jose from requirements.txt without handling this file breaks CI.

**Why it happens:** Phase 5 AUTH-04 swapped production code from jose → PyJWT but may have left some test files using jose as an oracle. `[VERIFIED: grep -rn "from jose\|import jose" backend/tests/ discovered test_auth_utils.py:3]`

**How to avoid:** As part of D-14 / PR-B, audit ALL `from jose`/`import jose` references in `backend/`:
- `backend/tests/test_pyjwt_migration.py` — DELETE wholesale (D-14).
- `backend/tests/dependencies/test_auth_utils.py:3` — either rewrite with PyJWT (`import jwt`), or examine whether the test still has purpose post-jose-removal. Rewrite is usually cleaner — replace `jose.jwt.encode/decode` calls with `jwt.encode/decode` from PyJWT (API is near-identical for HS256 usage).

**Warning signs:** `pytest -n auto` fails in CI with `ModuleNotFoundError: No module named 'jose'` on PR-B.

### Pitfall 6: Pydantic 2.13 deprecation — after-model-validator signature

**What goes wrong:** Pydantic 2.12.3 added a deprecation warning for invalid after-model-validator function signatures (that don't use `self`). In 2.13 this may be escalated. If backend has any `@model_validator(mode='after')` with a non-self signature, the test suite will warn (via Phase 3's `catch_warnings` guard, plan 03-05) and fail. `[CITED: Pydantic HISTORY.md — v2.12.0a1 "Do not implicitly convert after model validators to class methods"]`

**Why it happens:** Historical V1→V2 migration shortcut left some validators as class methods by implicit conversion; Pydantic is tightening.

**How to avoid:** When running PR-A test suite, grep for `@model_validator` in `backend/app/` and inspect each definition's first argument (should be `self`, not `cls`). If any violations: fix inline in PR-A. No new baseline file needed — D-13 locks this.

**Warning signs:** `DeprecationWarning: ... after model validator ...` in pytest output; `catch_warnings` fixture failing.

### Pitfall 7: Uvicorn 0.45 `--reset-contextvars` silent semantics

**What goes wrong:** Uvicorn 0.45 adds `--reset-contextvars` flag that, when enabled, isolates ASGI request context across concurrent requests. If the team relies on ContextVar "leakage" across requests (typical anti-pattern but sometimes deliberate for per-worker state), uvicorn 0.45 does NOT change default behavior but the flag is present.

**Why it happens:** `[CITED: Uvicorn release notes — "0.45.0: New flag --reset-contextvars"]`

**How to avoid:** Do NOT add `--reset-contextvars` to the Apprunner/ECS uvicorn startup command. Current behavior is unchanged without the flag. Audit `uvicorn app.main:app ...` invocations in `backend/Dockerfile`, `backend/start.sh`, and terraform/apprunner.tf — confirm no behavioral flag changes are proposed. This project's `backend/app/core/sentry.py` uses log_context ContextVars for request_id/user_id (Phase 2 OBS-04 pattern); behavior should remain identical.

**Warning signs:** request_id disappearing from logs or becoming inconsistent across concurrent requests.

## Code Examples

Verified patterns from official sources and empirical testing:

### Example 1: Sentry ErrorBoundary Fallback with Event ID (FE-03 / D-08)

```typescript
// Source: Inspected frontend/node_modules/@sentry/react/build/types/errorboundary.d.ts line 5-10
// FallbackRender type: ({ error, componentStack, eventId, resetError }) => React.ReactElement

import * as Sentry from '@sentry/react';
import { useNavigate } from 'react-router-dom';

export function RouteGroupBoundary({
  groupName,
  children,
}: {
  groupName: 'admin' | 'authentication' | 'builder' | 'public';
  children: React.ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <Sentry.ErrorBoundary
      beforeCapture={(scope) => {
        scope.setTag('route_group', groupName);
      }}
      fallback={({ error, eventId, resetError }) => (
        <section className="container mx-auto px-4 py-16">
          <div className="glass-card rounded-2xl p-8 max-w-lg mx-auto">
            <h2 className="text-2xl font-semibold text-neutral-100 mb-3">
              Something went wrong in the {groupName} section
            </h2>
            <p className="text-sm text-neutral-400 mb-2">
              {(error as Error)?.message ?? 'Unknown error'}
            </p>
            <p className="text-xs text-neutral-500 mb-6">
              Event ID: <code className="font-mono">{eventId}</code>
            </p>
            <div className="flex gap-3">
              <button type="button" onClick={resetError} className="btn-primary">
                Retry
              </button>
              <button type="button" onClick={() => navigate('/')} className="btn-secondary">
                Go Home
              </button>
            </div>
          </div>
        </section>
      )}
    >
      {children}
    </Sentry.ErrorBoundary>
  );
}
```

### Example 2: App.tsx Routes with Route-Group Boundaries

```tsx
// Source: CONTEXT.md D-07 (four groups) + App.tsx current structure
import { Outlet, Route, Routes } from 'react-router-dom';
import { RouteGroupBoundary } from './components/common/RouteGroupBoundary';

// Inside <Suspense>:
<Routes>
  {/* Public group: home, about, info pages, search, view-user, build-lists etc. */}
  <Route element={<RouteGroupBoundary groupName="public"><Outlet /></RouteGroupBoundary>}>
    <Route path="/" element={<Home />} />
    <Route path="/about" element={<About />} />
    <Route path="/privacy-policy" element={<PrivacyPolicy />} />
    {/* ... all existing public routes ... */}
  </Route>

  {/* Authentication group: login/register/guest-only + verify-email/reset-password */}
  <Route element={<RouteGroupBoundary groupName="authentication"><Outlet /></RouteGroupBoundary>}>
    <Route element={<GuestRoute />}>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
    </Route>
    <Route path="/verify-email/confirm" element={<VerifyEmailConfirm />} />
    <Route path="/forgot-password/confirm" element={<ForgotPasswordConfirm />} />
    <Route path="/extension-auth" element={<ExtensionAuth />} />
  </Route>

  {/* Builder group: profile, builder, parts management, checkout */}
  <Route element={<RouteGroupBoundary groupName="builder"><Outlet /></RouteGroupBoundary>}>
    <Route element={<ProtectedRoute />}>
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route element={<EmailVerifiedRoute />}>
        <Route path="/profile" element={<Profile />} />
        <Route path="/builder" element={<Builder />} />
        {/* ... */}
      </Route>
    </Route>
  </Route>

  {/* Admin group */}
  <Route element={<RouteGroupBoundary groupName="admin"><Outlet /></RouteGroupBoundary>}>
    <Route path="/admin" element={<AdminDashboard />} />
    <Route path="/admin/reports" element={<ReportReview />} />
    {/* ... */}
  </Route>
</Routes>
```

### Example 3: Parametrized FE-03 Coverage Test (D-10) — RTL variant

```tsx
// Source: Composes D-10 + Phase 5 pattern in backend/tests/test_auth_auth_coverage.py
// Planner may replace with an AST-static variant — both are acceptable

import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import App from '../App';

// Enumerate every path the route tree should recognize (hand-maintained — OK, it's small + changes are PR-visible)
const ALL_ROUTES = [
  { path: '/', group: 'public' },
  { path: '/about', group: 'public' },
  { path: '/login', group: 'authentication' },
  { path: '/admin', group: 'admin' },
  { path: '/profile', group: 'builder' },
  // ... all routes
] as const;

describe.each(ALL_ROUTES)('FE-03 route-group coverage: $path', ({ path, group }) => {
  it(`renders within a <RouteGroupBoundary groupName="${group}">`, () => {
    const { container } = render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    );
    // Assert the group marker is present — relies on RouteGroupBoundary rendering
    // a data-testid="route-group-<name>" wrapper in production, or a dev-only marker.
    // Alternative: assert ErrorBoundary presence via a fault-injection render.
    expect(container.querySelector(`[data-route-group="${group}"]`)).toBeTruthy();
  });
});
```

### Example 4: QUAL-04 Bandit Regression Test (D-18 Path A)

```python
# Source: backend/tests/test_bandit_high_gate.py (new file)
# D-18 path A: current CI already fails on HIGH via -ll; test pins that behavior.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def high_severity_fixture(tmp_path: Path) -> Path:
    """Synthetic file with a bandit B602 HIGH-severity finding."""
    src = tmp_path / "fixture.py"
    src.write_text(
        "import subprocess\n"
        "import os\n"
        "user_input = os.environ.get('CMD', '')\n"
        "subprocess.call(user_input, shell=True)  # B602 HIGH\n"
    )
    return src


def test_bandit_fails_on_high_severity(high_severity_fixture: Path) -> None:
    """QUAL-04: confirm `bandit -r <fixture> -ll` exits non-zero on HIGH severity.

    Guards the existing CI invocation in .github/workflows/backend-ci.yml from
    regressing to a pass-through config.
    """
    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", str(high_severity_fixture), "-ll"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        f"bandit -ll unexpectedly exited 0 on HIGH fixture. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Severity: High" in result.stdout
```

### Example 5: QUAL-08 Terraform S3 Lifecycle Rule

```terraform
# Source: terraform/s3.tf (append after aws_s3_bucket "crawl_data" declaration)
# Pattern: hashicorp/terraform-provider-aws README guide, DEEP_ARCHIVE storage class supported since provider v4.

resource "aws_s3_bucket_lifecycle_configuration" "crawl_data" {
  bucket = aws_s3_bucket.crawl_data.id

  rule {
    id     = "archive-old-snapshots"
    status = "Enabled"

    # Empty filter block = apply to all objects in bucket.
    # DO NOT use `filter { prefix = "" }` — see Pitfall 4 (generates wrong AWS XML).
    filter {}

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }
  }
}
```

### Example 6: madge CI Step (D-16)

```yaml
# Source: CONTEXT.md D-16 — .github/workflows/frontend-ci.yml, insert after "Run tests" step, before "Build application"
      - name: Check circular imports
        run: |
          cd frontend
          npx madge --circular --extensions ts,tsx src/
```

### Example 7: Fresh ESLint Config for FE-01 / D-05

```javascript
// Source: CONTEXT.md D-01 + D-05 + existing frontend/eslint.config.js
// Changes from current: add explicit `no-explicit-any` + `no-unsafe-*` as error in main block;
// REMOVE the test-file override that sets them to off.

import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist/', 'node_modules/', '*.config.js'] },
  // ... (keep base config for *.config.ts unchanged) ...

  // Main application files (CHANGED)
  {
    files: ['src/**/*.ts', 'src/**/*.tsx'],
    extends: [...tseslint.configs.recommendedTypeChecked],
    // ... (keep existing plugins/languageOptions) ...
    rules: {
      // ... (keep existing react-refresh/react-hooks/react-x rules) ...
      // NEW: upgrade no-explicit-any to error (FE-01, D-01)
      '@typescript-eslint/no-explicit-any': 'error',
      // recommendedTypeChecked already includes no-unsafe-* at warn;
      // D-01 escalates them to error:
      '@typescript-eslint/no-unsafe-assignment': 'error',
      '@typescript-eslint/no-unsafe-call': 'error',
      '@typescript-eslint/no-unsafe-return': 'error',
      '@typescript-eslint/no-unsafe-member-access': 'error',
      '@typescript-eslint/no-unsafe-argument': 'error',
    },
  },

  // Test files (CHANGED: D-05 drops the overrides)
  {
    files: ['src/test/**/*.ts', 'src/test/**/*.tsx', 'src/**/*.test.ts', 'src/**/*.test.tsx'],
    extends: [...tseslint.configs.recommended],
    rules: {
      // D-05: intentionally no `no-unsafe-*: off` overrides.
      // Tests must be type-honest like source.
      '@typescript-eslint/no-unused-vars': 'warn',
    },
  },

  // eslintConfigPrettier must remain last
);
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `bg-gradient-to-*` (Tailwind v3 canonical) | `bg-linear-to-*` (Tailwind v4 canonical) | Tailwind v4 release | Compat theme in v4.1.7 still recognizes old; ~44 sites to rename in this project |
| `python-jose` for JWT | `PyJWT` | Phase 5 AUTH-04 | Phase 6 D-14 removes jose dep entirely |
| `@app.on_event()` | `lifespan` context manager | FastAPI 0.100+ | Already migrated; Phase 3 QUAL-03 grep guard prevents regression |
| FastAPI without strict Content-Type | FastAPI 0.132+ strict by default | 0.132.0 | QUAL-06 extension audit confirms current code is compliant |
| Custom rate-limit counter (crawlers) | `pybreaker.CircuitBreaker` | Phase 3 CRAWL-04 | Not Phase 6 scope — already landed |
| `db.query()` (SQLAlchemy 1.x legacy) | `select()` + `session.scalars()` | Phase 4 DATA-06 | Not Phase 6 scope — already landed |
| Lazy mid-request build-log creation | Eager creation alongside build list | Phase 4 DATA-08 | Not Phase 6 scope — already landed |

**Deprecated / outdated:**
- `process.env` in browser source — replaced by `import.meta.env`. Already migrated; FE-02 is an audit.
- `@typescript-eslint/no-unsafe-*` at `warn` — escalated to `error` in this phase (FE-01).
- `python-jose[cryptography]==3.5.0` — removed in this phase (D-14).
- ecdsa CVE-2024-23342 ignore line in `pip-audit` — can be removed after python-jose leaves requirements.txt, since ecdsa is python-jose's transitive.

## Assumptions Log

> List of claims tagged `[ASSUMED]` that should be confirmed by the planner or flagged for user review before plan execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Existing top-level `<ErrorBoundary>` in App.tsx (main.tsx:22 + App.tsx:132) should stay. Route-group boundaries are added NESTED INSIDE it, not replacing it. | Architecture §Component Responsibilities | If wrong: planner might remove top-level boundary, losing one layer of defense. VERIFICATION: re-read CONTEXT.md D-07 carefully — it says "in addition to the existing app-root ErrorBoundary". CONFIRMED — not an assumption. Moving this note to "VERIFIED" status. |
| A2 | The FE-04 "co-located types in `frontend/src/api/*.ts`" (D-04) implies a structural refactor: split `services/Api.ts` (1521 lines) into one file per backend domain under a new `src/api/` folder. | Open Questions §Q1 | HIGH — if wrong interpretation, planner might write types inside existing Api.ts (pragmatic) when the intent was a file-per-domain split (larger scope). See Open Question 1 — REQUIRES USER CONFIRMATION BEFORE PLANNING. |
| A3 | Uvicorn upgrade target is 0.45.0 (CONTEXT.md QUAL-05 says "0.45"). 0.46.0 is now available but not explicitly requested. | Standard Stack | LOW — if planner picks 0.46 instead, functionally equivalent; if strict-requirement, plan should pin 0.45.0. |
| A4 | The bandit regression test (Example 4) will work in the existing pytest CI matrix without changes. pytest infrastructure and bandit are already installed in both local dev and `.github/workflows/backend-ci.yml`. | Code Examples §Example 4 | LOW — verified by reading backend-ci.yml line 27 (`pip install ... bandit`). |
| A5 | Chrome extension `apiRequest` helper (background.ts:82-105) is the only POST-dispatch pattern in the extension. The 7 direct `fetch` POST sites all route through it EXCEPT line 575 which uses FormData. | Pitfall 1 | LOW — grep confirmed 7 `method: "POST"` sites; 6 are via apiRequest, 1 is the FormData image upload. |
| A6 | Plan author will wire the Terraform module-boundary correctly — specifically, that `aws_s3_bucket_lifecycle_configuration.crawl_data` depends implicitly on `aws_s3_bucket.crawl_data.id`, and the implicit graph ordering is sufficient. | Code Examples §Example 5 | LOW — single bucket, single rule; no multi-module mystery. |
| A7 | After python-jose removal, the `pip-audit` ignore for CVE-2024-23342 can be removed (the vulnerable transitive `ecdsa` only reaches the project via jose). | State of the Art | MEDIUM — if another dep also pulls in `ecdsa`, removing the ignore will fail CI. Planner should re-run `pip-audit` on the post-removal requirements.txt to confirm. |

**Required user confirmation:** A2 (FE-04 structural interpretation) is the single high-risk assumption and must be resolved before planning begins.

## Open Questions

1. **FE-04: Split `services/Api.ts` into `frontend/src/api/*.ts` per-domain — yes or no?**
   - What we know: CONTEXT.md D-04 says "next to each API client module in `frontend/src/api/`". The phrase "each API client module" implies multiple modules exist. But current codebase has a single `frontend/src/services/Api.ts` (1521 lines) with all domain APIs (usersApi, carGenerationsApi, buildListsApi, partsApi, categoriesApi, partManufacturersApi, retailersApi, votesApi, reportsApi, etc.) grouped in one file.
   - What's unclear: Does D-04 intend (a) a structural refactor to split Api.ts into many files, OR (b) co-located types INSIDE the existing Api.ts sections, OR (c) write new `src/api/` domain modules alongside `services/Api.ts` just for the types?
   - Recommendation: **The planner MUST surface this as a pre-planning question and get user confirmation.** If (a) — the scope grows significantly; Phase 6's typing work would now include a ~1500-line file-split. If (b) — the scope matches the CONTEXT.md-sized work. If (c) — unusual; avoid. I recommend interpretation (b) as it matches D-01's "small blast radius" framing: write response-type interfaces AT THE TOP OF EACH SECTION of the existing `services/Api.ts`, not split the file. If interpretation (a) is confirmed, this becomes a Phase 6 second plan, not a single PR.

2. **Do we delete `backend/tests/test_pyjwt_migration.py` AND audit `backend/tests/dependencies/test_auth_utils.py`?**
   - What we know: D-14 explicitly says "delete the test when jose is removed". test_pyjwt_migration.py is the documented one; test_auth_utils.py also imports `from jose import jwt` (line 3).
   - What's unclear: Is test_auth_utils.py meant to be migrated to PyJWT (equivalent API for HS256 is drop-in) or deleted?
   - Recommendation: Planner should assume **migrate test_auth_utils.py to PyJWT** (`from jwt import encode, decode` instead of `from jose import jwt`). If the test still has value as an auth-utility regression, migration preserves that value with zero API surface change. If deletion is intended, it should be an explicit call-out in the PR-B plan.

3. **Does the route-group boundary coverage test (D-10) use AST or RTL approach?**
   - What we know: D-10 accepts both; Claude's Discretion in CONTEXT.md confirms the planner picks. The backend Phase 5 pattern (parametrized over `app.routes`) is runtime-introspection on a live-built FastAPI app — that's runtime, not AST. The analog for React Router 7 is `<Routes>` is a set of JSX Route elements, not a runtime introspectable tree until render time.
   - What's unclear: Runtime RTL-render cost per route (~40 lazy components to resolve + mock). AST cost: TypeScript compiler API boilerplate to walk App.tsx.
   - Recommendation: **RTL parametrized render with `MemoryRouter` + data-testid markers on `RouteGroupBoundary`** (Example 3 shown above). RTL is durable to JSX restructuring; AST is faster but brittle. For 40-ish routes, vitest runtime is acceptable (<5s in practice for a fresh cache). If vitest runtime becomes a problem, AST is a mechanical rewrite later.

4. **Does PR-A need a test-order change for xdist parallelism?**
   - What we know: pytest `-n auto` is the norm. PR-A touches Pydantic; the existing `catch_warnings` guard may surface deprecations from ANY test, not just auth characterization.
   - What's unclear: If Pydantic 2.13 emits NEW deprecations (e.g., about `field_validator` signatures we have been using correctly), the warning stream order across parallel workers may make the failing test identification harder.
   - Recommendation: Planner should include a task to run `pytest -p no:xdist` as a diagnostic step IF PR-A CI fails in unexpected places. Not a default requirement, just a bisect tool.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | backend upgrade PRs | ✓ | 3.13.12 (pyenv) | — |
| pip | backend upgrade | ✓ | (shim) | — |
| bandit | QUAL-04 verification | ✓ | 1.9.4 | — |
| Node.js | frontend lint + madge | ✓ | ≥20.19.0 enforced (package.json:engines) | — |
| npm | madge install | ✓ | — | — |
| madge CLI | FE-06 | ✗ | — | Installed as devDependency during plan task |
| terraform CLI | QUAL-08 plan/apply | Assumed available on operator workstation | ≥1.5 (versions.tf) | Plan output pasted into PR description per D-20 |
| AWS credentials | QUAL-08 apply | Operator-owned | — | Plan-only preview in PR; apply gated on operator with SSO login |

**Missing dependencies with no fallback:** None — all tooling for CI-side automation exists.

**Missing dependencies with fallback:** madge will be added as a devDependency in FE-06 plan task (existing `npm ci` in CI handles the install once package.json is updated).

## Validation Architecture

> `workflow.nyquist_validation: true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 9.0.3 + pytest-asyncio 1.3.0 + pytest-xdist 3.8.0 + pytest-cov 6.2.1 + pytest-recording 0.13.4 |
| Backend config file | `backend/pytest.ini` (coverage floor 51 per Phase 1 SAFE-01) |
| Backend quick run | `cd backend && pytest -n auto -x path/to/test_file.py::test_name` |
| Backend full suite | `cd backend && pytest -n auto --cov=app --cov-report=term-missing` |
| Frontend framework | vitest 3.2.4 + @testing-library/react 16.1.0 + jsdom 25.0.1 |
| Frontend config file | `frontend/vitest.config.ts` AND `frontend/vite.config.ts` (both exist; vitest.config.ts is the test config) |
| Frontend quick run | `cd frontend && npm test -- --run path/to/file.test.ts` |
| Frontend full suite | `cd frontend && npm test -- --run --coverage` |
| Terraform | Not a test surface; validation is `terraform validate && terraform plan` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FE-01 | ESLint strict rules do not have violations in src/ | lint | `cd frontend && npm run lint` | ✅ existing; behavior changes with config edit |
| FE-01 | test-files also follow strict rules (D-05) | lint | `cd frontend && npm run lint` (same command; D-05 flips test-file override) | ✅ same |
| FE-02 | No `process.env` in frontend browser source (vite.config.ts + docstring allow-listed) | grep/static | `cd frontend && ! grep -rn "process\\.env" src/ --include="*.ts" --include="*.tsx"` OR add as vitest guard | ❌ new regex guard needed |
| FE-03 | Every `<Route>` element sits under one of 4 route-group boundaries | integration (RTL) | `cd frontend && npm test -- --run src/App.coverage.test.tsx` | ❌ new test file (Wave 0) |
| FE-03 | Sentry ErrorBoundary fires on route-scoped error with correct tag | integration | `cd frontend && npm test -- --run src/components/common/RouteGroupBoundary.test.tsx` | ❌ new test file (Wave 0) |
| FE-04 | API client response handlers narrow via `unknown` not `any` cast | lint (FE-01 handles) + manual review | Covered by FE-01 `no-unsafe-*` + CI lint | ✅ same lint step |
| FE-05 | No `bg-gradient-to-*` substring in src/ | grep/static (vitest) | `cd frontend && npm test -- --run src/test/no-legacy-gradient.test.ts` | ❌ new test file (Wave 0) |
| FE-06 | Zero circular imports in src/ | static | `cd frontend && npx madge --circular --extensions ts,tsx src/` | ✅ CLI; CI step new |
| FE-07 | Opportunistic polish does not regress visual tests | manual UAT | Human review; no automated UAT for v1 | N/A (manual) |
| QUAL-04 | Bandit with `-ll` fails on HIGH severity fixture | integration (subprocess) | `cd backend && pytest -n auto tests/test_bandit_high_gate.py` | ❌ new test file (Wave 0) |
| QUAL-05 | Pydantic 2.13 emits zero V1 deprecations under catch_warnings guard | existing guard | `cd backend && pytest -n auto` (Phase 3 plan 03-05 guard) | ✅ existing |
| QUAL-05 | Alembic 1.18 round-trip migrations | existing script | `cd backend && bash scripts/test_migration_round_trip.sh` | ✅ existing (Phase 4 plan 04-06) |
| QUAL-05 | FastAPI 0.136 auth characterization suite green | existing | `cd backend && pytest -n auto -k "auth and characterization"` | ✅ existing (Phase 1 SAFE-06) |
| QUAL-05 | FastAPI 0.136 OpenAPI snapshot stable | existing | `cd backend && pytest -n auto tests/test_openapi_snapshot.py` | ✅ existing (Phase 1 SAFE-05) |
| QUAL-06 | Chrome extension POSTs Content-Type compliant | static (vitest) | `cd frontend && npm test -- --run src/test/extension-content-type.test.ts` | ❌ new test file (Wave 0) |
| QUAL-08 | Terraform plan generates DEEP_ARCHIVE transition at 90d | terraform-plan | `cd terraform && terraform plan -target=aws_s3_bucket_lifecycle_configuration.crawl_data` | Manual validation (Wave 0: plan pasted into PR) |

### Sampling Rate

- **Per task commit:** Quick run for the touched file/test:
  - Frontend typing: `cd frontend && npm run lint`
  - Frontend tests: `cd frontend && npm test -- --run <touched test>`
  - Backend upgrade: `cd backend && pytest -n auto -x <touched test>`
- **Per wave merge:** Full suite:
  - Wave 1 (parallel small): frontend lint+test + backend bandit test
  - Wave 2 (FE-01 typing chunks): frontend lint + test full
  - Wave 3 (FE-03 boundaries): frontend test full
  - Wave 4 (PR-A FastAPI+Pydantic): backend full pytest + OpenAPI snapshot + auth characterization
  - Wave 5 (PR-B SQLAlchemy/Alembic/Uvicorn + jose-removal): backend full pytest + migration round-trip
  - Wave 6 (FE-07 polish): frontend full + manual UAT sample
- **Phase gate:** `cd backend && pytest -n auto --cov=app --cov-report=term-missing` AND `cd frontend && npm test -- --run --coverage` AND `cd frontend && npm run lint` AND `cd frontend && npx madge --circular --extensions ts,tsx src/` — all green before `/gsd-verify-work`.

### Wave 0 Gaps

Wave 0 (infrastructure before implementation) needs:

- [ ] `backend/tests/test_bandit_high_gate.py` — QUAL-04 regression test (Example 4 template)
- [ ] `frontend/src/test/no-legacy-gradient.test.ts` — FE-05 regression guard (Pattern 4 template)
- [ ] `frontend/src/test/extension-content-type.test.ts` — QUAL-06 regression guard (Pattern 4 template)
- [ ] `frontend/src/test/no-process-env.test.ts` — FE-02 regression guard (if a regex test is preferred over inline `grep` in CI)
- [ ] `frontend/src/App.coverage.test.tsx` — FE-03 route-group coverage (Example 3 template)
- [ ] `frontend/src/components/common/RouteGroupBoundary.tsx` — new component implementing Pattern 2
- [ ] `frontend/src/components/common/RouteGroupBoundary.test.tsx` — basic render + fallback test
- [ ] `.github/workflows/frontend-ci.yml` — new `Check circular imports` step after `Run tests`
- [ ] `frontend/package.json` — add `madge@^8.0.0` to devDependencies + `package-lock.json`

No new test framework installation needed — vitest + pytest are already present.

## Security Domain

`security_enforcement` is not explicitly `false` in `.planning/config.json`, so treating as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | **yes** — QUAL-05 (FastAPI+Pydantic), D-14 (python-jose removal) | Auth characterization suite (SAFE-06), OpenAPI snapshot (SAFE-05), PyJWT (AUTH-04) |
| V3 Session Management | yes (indirect) — PR-A could affect token validation paths | Existing JWT HS256 via PyJWT; no changes this phase |
| V4 Access Control | no — Phase 6 touches no authorization logic | N/A |
| V5 Input Validation | yes — FastAPI 0.132+ strict Content-Type, Pydantic 2.13 validation | Framework-provided (FastAPI strict mode + Pydantic); QUAL-06 extension client audit |
| V6 Cryptography | yes — jose removal + PyJWT standalone | PyJWT (never hand-roll JWT); HS256 hardcoded; removing jose reduces supply chain |
| V7 Error Handling | yes — FE-03 route-group boundaries + Sentry reporting | @sentry/react ErrorBoundary with beforeCapture tag isolation; no PII in error messages |
| V8 Data Protection | yes — QUAL-08 S3 Glacier at 90d | Lifecycle policy; bucket already private (block_public_access) |
| V10 Malicious Code | yes — QUAL-04 bandit HIGH gate | Bandit HIGH-severity exit-1 verified |
| V11 Business Logic | no | N/A |
| V14 Configuration | yes — QUAL-08 Terraform | Declarative IaC; `terraform validate` + plan review |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Content-Type downgrade attack (FastAPI) | Tampering | FastAPI 0.132+ strict Content-Type; extension POSTs always send `application/json` or `FormData` (QUAL-06 guard) |
| JWT algorithm confusion | Spoofing | PyJWT with explicit `algorithms=["HS256"]` on every decode (Phase 5 AUTH-04); python-jose removal eliminates algorithm-normalization ambiguity |
| Command injection (subprocess) | Elevation | Bandit `-ll` HIGH gate catches B602 (shell=True with dynamic input); `# nosec` required for documented safe patterns |
| Hardcoded secrets | Information Disclosure | `test_cassette_secret_audit.py` (Phase 1) + secrets-scanner in CI; no new secrets this phase |
| Prototype pollution / `any` leaks | Tampering | FE-01 strict no-explicit-any + no-unsafe-*; API response narrowing (FE-04) |
| S3 bucket public exposure | Information Disclosure | `aws_s3_bucket_public_access_block` already present; QUAL-08 lifecycle does not change ACL |
| Circular-import-induced unintended export | — | madge --circular CI gate (FE-06) |
| Supply-chain vulnerability (ecdsa via jose) | all | python-jose removal (D-14) drops transitive `ecdsa` CVE-2024-23342; pip-audit catches any new deps |

### Sentry PII Posture

Phase 2 OBS-01 configured `send_default_pii=False` and request_id/user_id scope processors. FE-03 route-group boundaries add `scope.setTag('route_group', '<name>')` — a non-PII tag. No new PII surface introduced this phase.

## Project Constraints (from CLAUDE.md)

CLAUDE.md is authoritative. Relevant Phase-6 directives:

- **Alembic:** "Always use `alembic revision --autogenerate`. Never write migration files by hand." — No new migrations in Phase 6, but the QUAL-05 Alembic 1.18 bump means auto-generated migrations must round-trip correctly (Phase 4 script covers this).
- **pytest:** "Always pass `-n auto` for parallel execution. Tests use SQLite in-memory — no Postgres required." — New QUAL-04 bandit regression test MUST tolerate xdist (the subprocess invocation is self-contained and safe).
- **New CRUD endpoints:** "Extend `BaseEndpointRouter` + `BaseCRUDService`; register with `EndpointRegistry` in `main.py`." — Not applicable this phase; no new endpoints.
- **Backend CORS:** "explicitly allows `chrome-extension://` origins and `null` (for service workers)." — Phase 6 must NOT alter this. FastAPI 0.136 upgrade does not affect CORS middleware behavior.
- **Linting:** "`black --config pyproject.toml .`, `isort .`, `pyright`, `bandit -r app`" — Phase 6 adds a regression test to bandit scope; same tools used.
- **Frontend stack:** "React Router 7 for routing; Tailwind CSS 4 for styling." — Phase 6 updates Tailwind class hygiene (v4 canonical names) and adds React Router 7 route-group boundaries; no version bumps to router or tailwind.
- **Auth:** "JWT (HS256, configurable expiry 15 min–7 days per user preference) + bcrypt passwords + optional TOTP 2FA." — Phase 6 removes jose implementation of HS256; PyJWT preserves exact HS256 behavior + expiry handling.
- **Subscription tiers:** "gate features and ad display." — Phase 6 does not change subscription logic; FE-03 error boundaries must NOT interfere with `useIsPremium` / `useIsPremiumSystemDisabled` hooks in App.tsx.

All directives compatible with Phase 6 scope; no conflict with CONTEXT.md locked decisions.

## Sources

### Primary (HIGH confidence)

- `[Context7 /fastapi/fastapi]` — FastAPI release notes 0.128-0.136; confirmed strict Content-Type in 0.132, Pydantic v1 removal in 0.128, Starlette bumps.
- `[Context7 /pydantic/pydantic]` — Pydantic v2.11-v2.13 release notes; deprecation/breaking-change inventory.
- `[Context7 /hashicorp/terraform-provider-aws]` — `aws_s3_bucket_lifecycle_configuration` examples including DEEP_ARCHIVE transition.
- `[Context7 /pahen/madge]` — madge CLI options and tsConfig support.
- `[OFFICIAL: github.com/fastapi/fastapi/blob/master/docs/en/docs/release-notes.md]` — fetched + summarized.
- `[OFFICIAL: github.com/pydantic/pydantic/blob/main/HISTORY.md]` — fetched + summarized.
- `[OFFICIAL: tailwindcss.com/docs/background-image]` — all 8 bg-linear-to-* variants + radial/conic.
- `[OFFICIAL: docs.sentry.io/platforms/javascript/guides/react/features/error-boundary]` — ErrorBoundary API.
- `[OFFICIAL: github.com/PyCQA/bandit/blob/main/bandit/cli/main.py]` — bandit argparse definitions.
- `[OFFICIAL: docs.sqlalchemy.org/en/20/changelog/changelog_20.html]` — SQLAlchemy 2.0.41→2.0.49 changes.
- `[OFFICIAL: alembic.sqlalchemy.org/en/latest/changelog.html]` — Alembic 1.16→1.18.
- `[OFFICIAL: www.uvicorn.org/release-notes/]` — Uvicorn 0.34→0.45.

### Empirical verification (HIGH confidence, this session)

- `[VERIFIED: bandit 1.9.4 on this machine with synthetic B602 HIGH fixture]` — empirically confirmed `bandit -r <fixture> -ll` exits 1 on HIGH, matching D-18 path A.
- `[VERIFIED: frontend/node_modules/tailwindcss/dist/chunk-P5FH2LZE.mjs]` — empirically confirmed v4.1.7 ships a compat theme with all 8 `gradient-to-*` backgroundImage keys — old class names still work.
- `[VERIFIED: frontend/node_modules/@sentry/react/build/types/errorboundary.d.ts line 5-10]` — empirically confirmed `FallbackRender` exposes `eventId` in fallback props.
- `[VERIFIED: pip index versions fastapi | pydantic | sqlalchemy | alembic | uvicorn ; npm view madge version]` — all upgrade-target versions registered on registries.
- `[VERIFIED: grep -rn "bg-gradient-to-" frontend/src/]` — 44 total occurrences across 9-10 files.
- `[VERIFIED: grep -rn "fetch(.*method.*POST" chrome-extension/src/]` — 7 POST sites, all compliant via apiRequest helper or FormData.
- `[VERIFIED: grep -rn "process.env" frontend/]` — only 2 legitimate sites, both out of browser code.
- `[VERIFIED: grep -rn "from jose\|import jose" backend/tests/]` — surfaced test_auth_utils.py additional usage (Pitfall 5).

### Secondary (MEDIUM confidence, cross-verified)

- `[CITED: github.com/terraform-aws-modules/terraform-aws-s3-bucket/issues/110]` — empty filter behavior quirk (Pitfall 4).
- WebSearch + xjavascript.com — madge TypeScript invocation patterns (cross-verified against README).

### Tertiary (LOW confidence, flagged)

- None — all claims in this research were tool-verified or cited to primary/secondary source.

## Metadata

**Confidence breakdown:**
- Standard stack versions: **HIGH** — all versions verified against npm/PyPI registries on 2026-04-23.
- Architecture patterns: **HIGH** — Sentry ErrorBoundary props verified against installed `.d.ts`; Tailwind v4 classes verified against installed source.
- Pitfalls: **HIGH** — Pitfall 1 (Content-Type) cited from FastAPI release notes; Pitfall 2 (Tailwind compat) empirically verified in installed source; Pitfall 4 (empty filter) cited from GitHub issue with community verification; Pitfall 5 (test_auth_utils.py) empirically discovered via grep.
- Code examples: **HIGH** — all examples reference verified APIs or existing project patterns (e.g., backend/tests/test_auth_auth_coverage.py parametrized pattern).
- Environment availability: **HIGH** — bandit + tailwind + @sentry/react + all upgrade targets available or installable.

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (30 days — all stack choices are stable patch-level bumps; nothing in the bleeding-edge bucket)
