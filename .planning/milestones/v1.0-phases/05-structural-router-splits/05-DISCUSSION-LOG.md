# Phase 5: Structural Router Splits - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 05-structural-router-splits
**Areas discussed:** PyJWT migration sequencing; Sub-package router composition; Helper file boundaries; 401/403 integration test shape; Chrome extension API_CONTRACT.md format; Chrome extension post-split validation

---

## PyJWT migration sequencing

### Q1: When should the python-jose→PyJWT swap land relative to the admin/auth splits?

| Option | Description | Selected |
|--------|-------------|----------|
| Before auth split (Recommended) | Swap first as its own dedicated PR; subsequent auth-split PRs work on the new library | ✓ |
| Bundled with auth split | New auth/ modules use PyJWT on creation; library + structural change mixed | |
| After auth split | Split first in python-jose; library sweep last across new auth/ + dependencies/auth.py | |

**User's choice:** Before auth split. Order: admin split → PyJWT swap → auth split.

### Q2: How should JWTError exception catches be replaced?

| Option | Description | Selected |
|--------|-------------|----------|
| except InvalidTokenError (Recommended, REQ literal) | Parent class of all PyJWT token errors; matches AUTH-04 | ✓ |
| Narrower specific exceptions per site | `ExpiredSignatureError`, `DecodeError`, etc. | |
| Alias at import | `from jwt import InvalidTokenError as JWTError` — violates "zero JWTError references" literal | |

**User's choice:** `except InvalidTokenError` from `jwt.exceptions`.

### Q3: Algorithm-explicit requirement — satisfied or tighten?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current pattern — algorithms=[ALGORITHM] already explicit | Add regression grep test | |
| Tighten: hoist ALGORITHM to settings + lint rule | settings.JWT_ALGORITHM + grep ban on bare `jwt.decode` | ✓ |

**User's choice:** Tighten — hoist to `settings.JWT_ALGORITHM` + regression grep test banning bare `jwt.decode(` without `algorithms=[` in same statement.
**Notes:** User deliberately chose stronger enforcement over the lighter recommendation.

### Q4: In-flight token compatibility — how do we prove existing tokens survive?

| Option | Description | Selected |
|--------|-------------|----------|
| Test fixture: jose-encoded token decodes under PyJWT (Recommended) | One parity test; HS256 bytes are identical | ✓ |
| Skip — rely on Phase 1 characterization tests | Weaker signal on the library swap specifically | |
| Production canary | 24h staging observation; low-traffic → weak signal | |

**User's choice:** Parity test fixture in `backend/tests/test_pyjwt_migration.py`.

---

## Sub-package router composition

### Q1: How should auth/ and admin/ packages expose sub-routers to main.py?

| Option | Description | Selected |
|--------|-------------|----------|
| Parent __init__.py exports composite router (Recommended) | Zero main.py churn | |
| Each sub-module registered directly via EndpointRegistry in main.py | 2→10 call sites | |
| Each sub-module at DIFFERENT prefixes (/admin/stats, /admin/jobs, ...) | URL restructure | ✓ |

**User's choice:** Different sub-module prefixes. (Triggered follow-up — see below.)

### Q2: Route decorator path shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Full path relative to /admin (Recommended) | `@router.get("/stats/table-counts")` | |
| Path relative to sub-module prefix | `@router.get("/table-counts")` with prefix=/admin/stats | ✓ |

**User's choice:** Relative to sub-module prefix.

### Q3: Cron endpoints placement?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay in admin/crawlers.py (Recommended) | `_verify_cron_key` stays file-local | ✓ |
| Split: live-crawler in crawlers.py, rescrape in db_ops.py | Unnecessary churn | |

**User's choice:** Crawlers.py.

### Q4: Import compat for callers of `app.api.endpoints.auth/admin`?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard migration — update every caller in same PR (Recommended) | No shim; matches REQ-AUTH-01 / REQ-ADMIN-01 | ✓ |
| Temporary re-export shim in __init__.py | REQ literal prohibits this | |

**User's choice:** Hard migration.

### Follow-up Q5: URL restructure doesn't cleanly split — resolve how?

| Option | Description | Selected |
|--------|-------------|----------|
| Revert to Option (a): mount at /admin with full paths (Recommended) | No URL change | |
| Keep Option (c): accept URL restructure for non-EventBridge paths | Churn + OpenAPI drift | |
| Hybrid: URL unchanged, each sub-module registered at /admin individually | Explicit registration, no URL change | |

**User's choice:** (Answered via the two follow-ups Q6 + Q7 — selected "Aggressive restructure" for both admin and auth.)

### Follow-up Q6: Admin restructure scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal — only db_ops moves (Recommended) | db_ops under /admin/db-ops; crawlers unchanged | |
| Aggressive — everything gets a clean sub-tree (incl. EventBridge paths) | Terraform updates in same PR | ✓ |
| Zero restructure — revert to explicit registration at /admin | | |

**User's choice:** Aggressive. EventBridge paths move with Terraform update in same PR.

### Follow-up Q7: Auth restructure scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal — two_factor + webauthn get sub-prefixes, core + oauth stay at /auth (Recommended) | Zero web-app change | |
| Aggressive — /auth/google/* moves to /auth/oauth/google/* | Frontend Google sign-in paths update | ✓ |
| Zero restructure — all at prefix=/auth | | |

**User's choice:** Aggressive — Google routes consolidate under oauth.

### Follow-up Q8: OpenAPI snapshot handling?

| Option | Description | Selected |
|--------|-------------|----------|
| Regenerate + commit in restructure PR (Recommended) | Phase 1 D-26 convention | ✓ |
| Separate PR first | Wasted PR | |

**User's choice:** Regenerate in same PR.

---

## Helper file boundaries

### Q1: auth/_helpers.py scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Only cross-module helpers (Recommended) | `_issue_login_response`, `_maybe_2fa_challenge` | ✓ |
| All former auth.py helpers move | Loses sub-module cohesion | |
| Only pure utilities | Would duplicate stateful helpers | |

**User's choice:** Only cross-module. WebAuthn-local helpers stay in webauthn.py; OAuth-local helpers stay in oauth.py.

### Q2: Admin cross-concern helper location?

| Option | Description | Selected |
|--------|-------------|----------|
| Create admin/_helpers.py (Recommended) | Parallel to auth/_helpers.py; package consistency | ✓ |
| Consolidate under admin/jobs.py | Jobs owns lifecycle helpers | |
| Move to backend/app/services/job_service.py | Service-layer elevation — scope creep | |

**User's choice:** admin/_helpers.py (parallel to auth).

### Q3: ECS task launchers in crawlers.py — stay inline or extract?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay inline in admin/crawlers.py (Recommended) | Only one caller; no need to extract | ✓ |
| Extract to backend/app/services/ecs_task_service.py | Service-layer rework — scope creep | |
| Move to nested admin/crawlers/_helpers.py (sub-package) | Overkill for 4 functions | |

**User's choice:** Stay inline.

---

## 401/403 integration test shape

### Q1: Test shape for per-route coverage?

| Option | Description | Selected |
|--------|-------------|----------|
| Parametrized over (method, path, role) tuples (Recommended) | One parametrized test per package | ✓ |
| OpenAPI-driven | Allow-list public routes; 403 needs separate mechanism | |
| Per-route explicit test functions | ~45 near-duplicate functions | |

**User's choice:** Parametrized.

### Q2: 401 vs 403 coverage?

| Option | Description | Selected |
|--------|-------------|----------|
| Both 401 (unauthed) AND 403 (non-admin authed) for admin routes (Recommended) | Matches ADMIN-02 literal | ✓ |
| Just 401 | Misses regular-user → admin-route 403 case | |
| Just 403 | Framework-level 401 is fragile | |

**User's choice:** Both 401 + 403 for admin routes; 401 only for auth-protected user routes.

### Q3: Drift guard?

| Option | Description | Selected |
|--------|-------------|----------|
| Cross-check tuple count vs app.routes filtered by prefix (Recommended) | Double-gated with OpenAPI snapshot | ✓ |
| Rely on OpenAPI snapshot only | Snapshot regen doesn't ensure tuple add | |
| No drift guard | High risk of silent gaps | |

**User's choice:** Cross-check assertion.

### Q4: Test file location?

| Option | Description | Selected |
|--------|-------------|----------|
| backend/tests/test_admin_auth_coverage.py + test_auth_auth_coverage.py (Recommended) | Consistent with other guard tests | ✓ |
| Unified test_auth_dependency_coverage.py | Single entry point but mixes domains | |
| Per-sub-module test files colocated | Scattered across 10 files | |

**User's choice:** Two files, one per package.

---

## Chrome extension API_CONTRACT.md format

### Q1: Source and format?

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-written Markdown, frozen once (Recommended) | ~8 endpoint groups; frozen + regenerated on AUTH-06 completion | |
| OpenAPI-extracted (auto-generated from app.openapi()) | Allow-list script; auto-updates with backend drift | ✓ |
| TypeScript types mapped to backend endpoints | Over-engineered | |

**User's choice:** OpenAPI-extracted via `backend/scripts/generate_ext_api_contract.py` + drift-guard test.

---

## Chrome extension post-split validation

### Q1: AUTH-05 validation shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual UAT checklist (Recommended) | 5-min staging validation; proportional | ✓ |
| Backend integration test simulating ext requests | Covers CORS/auth surface in CI | |
| Playwright E2E with headless Chrome + extension | High-fidelity but expensive | |
| Manual UAT + backend integration test (belt + suspenders) | Modest extra scope | |

**User's choice:** Manual UAT checklist (D-38 in CONTEXT.md).

---

## Claude's Discretion

Areas where specifics were left to Claude's judgment, documented in CONTEXT.md `### Claude's Discretion`:

- Exact filenames for new scripts (e.g., `generate_ext_api_contract.py` vs `generate_api_contract.py`)
- Whether PyJWT parity test stays post-migration or is deleted with `python-jose` dependency
- Drift-guard assertion location within test file (inline vs separate function)
- Whether `create_and_login_admin` fixture goes in shared conftest or new test files
- Per-sub-module commit granularity inside PR 1 + PR 4
- Test file names (could be `test_admin_route_protection.py` / `test_auth_dependency_coverage.py`)
- Exact Markdown structure of generated API_CONTRACT.md
- PyJWT parity test secret source (static vs `settings.SECRET_KEY`)

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:

- Extract ECS task launchers to service layer (future service-layer phase)
- Playwright E2E for extension (future testing-infra phase)
- Remove `get_logger` export (Phase 3 D-36 deferred to late Phase 5 / Phase 6)
- Remove `python-jose` dependency (late Phase 5 / Phase 6)
- ALGORITHM rotation / RS256 migration (future security-hardening arc)
- ADMIN-04 "service-level coupling reduced" — plan author to confirm whether concrete target exists

---

*Generated during /gsd:discuss-phase 5 session on 2026-04-22*
