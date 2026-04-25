# Phase 1: Safety Nets & CI Hardening - Research

**Researched:** 2026-04-21
**Domain:** CI gates, coverage enforcement, characterization testing, Alembic migration hygiene
**Confidence:** HIGH (all library behavior verified via context7 + installed-package probing; all file paths verified by direct read)

## Summary

This phase is purely protective: bolt CI gates onto the brownfield codebase before any refactor touches it. The work is ten discrete items (SAFE-01 through SAFE-10), all of which are well-trodden patterns in the Python + TypeScript CI ecosystem — none of this is novel, and every library decision is already locked in CONTEXT.md. The research task was therefore to surface concrete integration details (exact config shapes, exact insertion points in existing CI workflows, exact interaction semantics) so the planner can author zero-guesswork task actions.

The three items with the highest implementation risk are SAFE-08 (repairing three broken `op.drop_constraint(None, ...)` migrations against live production RDS), SAFE-09 (adding `MetaData.naming_convention` without triggering an autogenerate-rename avalanche on existing constraints), and SAFE-06 (pytest-recording cassettes for Google OAuth — the only flow that hits external HTTPS). Everything else is mechanical.

**Primary recommendation:** Follow the locked execution order from D-32 strictly. Land SAFE-09 (naming_convention) before SAFE-08 (repair migrations) so the repair migrations generate with named constraints from the start. Land SAFE-04 (DROP-guard) before SAFE-01/02/03 (coverage gates) so no destructive migration slips through the coverage-measurement PR itself.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Backend coverage floor (SAFE-01)**
- **D-01:** Measure the baseline first: run `pytest -n auto --cov=app --cov-report=term` on `main` and record the total line-coverage percentage in the PR description.
- **D-02:** Set `--cov-fail-under=<measured_baseline>` in `backend/pytest.ini` at the exact measured number (no buffer). If baseline is flaky across runs, round DOWN to the nearest whole percent.
- **D-03:** The baseline measurement and the `--cov-fail-under` update land in the same PR so the ratchet is atomic.

**Frontend CI tests + coverage (SAFE-02, SAFE-03)**
- **D-04:** Add a `Run tests` step to `.github/workflows/frontend-ci.yml` running `npm test -- --run --coverage` before the existing `Build application` step.
- **D-05:** `lines: 60` threshold is locked. If current frontend coverage is below 60, write enough tests to reach 60 in the same phase BEFORE enabling the threshold — do not land a red CI.
- **D-06:** Configure thresholds in `frontend/vitest.config.ts` under `coverage.thresholds` (`lines: 60`, `functions: 50`, `branches: 50`, `statements: 60`).

**Migration DROP guard (SAFE-04)**
- **D-07:** Dedicated CI step in `backend-ci.yml` (not a pre-commit hook).
- **D-08:** Script at `backend/scripts/check_migrations.py` greps `backend/alembic/versions/*.py` for `drop_column`, `drop_table`, `drop_constraint`. Requires `# SAFE: <reason>` comment on SAME line or IMMEDIATELY PRECEDING line.
- **D-09:** Annotation format exactly `# SAFE: <human-readable reason>`.
- **D-10:** `alembic/versions/*.py` is the only scan path.

**Repair broken migrations + naming_convention (SAFE-08, SAFE-09)**
- **D-11:** Apply SQLAlchemy `MetaData(naming_convention=...)` at `backend/app/db/base_class.py` using the recommended convention.
- **D-12:** Do NOT retroactively rename existing constraints.
- **D-13:** Repair the three broken migrations (`097024200e60`, `172d1c205fb3`, `6eae6b1393c5`) by replacing each `op.drop_constraint(None, ...)` with the actual inspected constraint name. Each repair migration carries `# SAFE: repair invalid drop_constraint(None) — see SAFE-08`.
- **D-14:** If a broken migration has already run on prod, repair via a down+up pair in a NEW migration file; do not rewrite history.

**Auth characterization tests (SAFE-06)**
- **D-15:** Tool: `pytest-recording` (vcrpy-backed). Install as backend dev dep; add to `requirements.txt` (or a future `requirements-dev.txt`).
- **D-16:** 7 happy-path flows, one test per flow: signup→verify-email, login (email/password), 2FA-TOTP enrollment+challenge, WebAuthn passkey registration+assertion, Google OAuth sign-in, Google OAuth account link (existing user), password-reset request→reset.
- **D-17:** Cassettes at `backend/tests/cassettes/auth/`, committed; regenerate by deleting and re-running.
- **D-18:** SES reuses existing `moto` fixture. Google OAuth is VCR-recorded. WebAuthn ceremony stubbed at the `webauthn` library boundary (not over HTTP).
- **D-19:** Assert HTTP status code, presence of expected response JSON keys, and DB state change where relevant. Do NOT assert every field value.

**Crawler adapter characterization tests (SAFE-07)**
- **D-20:** 5 adapters across fetcher tiers:
  - 2× `FETCHER_TIER="http"` (tier0_http): `briantooleyracing`, `amsperformance` (post-fix 7831fda).
  - 2× `FETCHER_TIER="browser"` (tier2_browser — "most critical"): to be picked at plan time.
  - 1× `FETCHER_TIER="tls"` (tier1_tls — "most stable"): to be picked at plan time.
- **D-21:** Fixture HTML from the archive (confirm exact bucket at plan time). Commit one product page per adapter under `backend/tests/crawlers/fixtures/<adapter_name>/product.html`.
- **D-22:** Test `parse_product_page()` directly against fixture HTML; assert parsed fields against committed expected-output JSON. Do NOT test `discover_product_urls()`.
- **D-23:** Key adapters by class name; switch to `ADAPTER_NAME` in Phase 3 when CRAWL-02 lands.

**OpenAPI schema snapshot test (SAFE-05)**
- **D-24:** Snapshot at `backend/tests/fixtures/openapi_snapshot.json`, committed.
- **D-25:** Test at `backend/tests/test_openapi_snapshot.py` calls `.openapi()`, serializes with stable key ordering, asserts equality.
- **D-26:** Regenerate via `python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" > backend/tests/fixtures/openapi_snapshot.json`.
- **D-27:** Do NOT use hash comparison.

**Dependabot (SAFE-10)**
- **D-28:** GitHub-native Dependabot (not Renovate).
- **D-29:** Weekly Mondays, ecosystems: `pip` (backend/), `npm` (frontend/ + chrome-extension/), `github-actions` (workflows).
- **D-30:** Group minor+patch updates into one PR per ecosystem per week; major updates get individual PRs.
- **D-31:** Config at `.github/dependabot.yml`.

**Execution sequencing**
- **D-32:** Internal order: SAFE-09 → SAFE-08 → SAFE-04 → SAFE-01/02/03 → SAFE-05 → SAFE-06 + SAFE-07 → SAFE-10.

### Claude's Discretion
- Exact names of `check_migrations.py` variables and functions
- Format of the committed expected-output JSON for adapter fixtures (structure must be deterministic)
- Whether to additionally enforce `branches`/`functions`/`statements` thresholds in `pytest.ini`
- Minor Dependabot groupings (dev vs. prod dependency groups, etc.)

### Deferred Ideas (OUT OF SCOPE)
- E2E Chrome extension auth flow test via Playwright (Phase 5)
- Crawler `discover_product_urls()` characterization (Phase 3)
- Retroactive rename of historic constraints to match new naming_convention
- Sentry / monitoring for CI failures themselves (Phase 2)
- Postgres-backed migration testing in CI (Phase 4, DATA-09)
- `lazy="raise"` on SQLAlchemy relationships (Phase 4, DATA-10)
- Renovate migration (revisit only if Dependabot noise becomes problematic)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-01 | Backend `pytest.ini` enforces `--cov-fail-under=<measured baseline>` | Standard Stack §pytest-cov; Code Example §Measuring the baseline. pytest-cov + pytest-xdist aggregation is safe (§Common Pitfalls). |
| SAFE-02 | `frontend-ci.yml` runs `npm test -- --run` on every PR | CI Workflow Integration §frontend-ci.yml — exact insertion point between `Audit` and `Build`. |
| SAFE-03 | Vitest config enforces coverage threshold (`lines: 60`) | Standard Stack §@vitest/coverage-v8 (v3.2.4 already installed); Code Example §vitest.config.ts thresholds shape (verified via vitest docs). |
| SAFE-04 | CI step fails PR whose migration contains `drop_*` without `# SAFE: <reason>` | Code Example §check_migrations.py (concrete regex + line-above lookback); CI Workflow Integration §DROP-guard step. |
| SAFE-05 | OpenAPI schema snapshot test catches drift | Code Example §test_openapi_snapshot.py; works with pytest-xdist because it's a pure deterministic serialization (no race). |
| SAFE-06 | Auth characterization tests via `pytest-recording` | Standard Stack §pytest-recording 0.13.4 / vcrpy 8.1.1; Code Example §Auth flow with VCR cassette + `filter_headers` scrubbing + `@pytest.mark.vcr`. WebAuthn stubbed at library boundary (5 functions identified). |
| SAFE-07 | Crawler adapter VCR-style tests ≥5 representative adapters | Code Example §Adapter characterization (bypass network — feed fixture HTML to `parse_product_page()` directly). RetailerCrawlerAdapter contract verified from `backend/app/crawlers/adapters/base.py`. |
| SAFE-08 | Three migrations with `op.drop_constraint(None, ...)` repaired | Code Example §Repair migration template (introspect via `SELECT conname FROM pg_constraint` or SQLAlchemy `Inspector.get_foreign_keys()`); forward-only for prod-applied migrations. |
| SAFE-09 | SQLAlchemy `MetaData` uses explicit `naming_convention` | Standard Stack §SQLAlchemy 2.0.41 naming convention (exact recommended template from docs); Common Pitfall §Autogen avalanche — must add via metadata ONLY, not manually re-apply `constraint.name` on existing models. |
| SAFE-10 | Dependabot configured weekly for backend + frontend + extension | Code Example §dependabot.yml (exact schema v2 shape with multi-directory `npm` ecosystems, `groups` + implicit major-as-individual-PR behavior). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Directives extracted from `./CLAUDE.md` that Phase 1 plans MUST honor:

| # | Directive | Planner implication |
|---|-----------|---------------------|
| C-01 | Alembic migrations ALWAYS use `--autogenerate`; never write by hand | SAFE-08 repair migrations: use `alembic revision --autogenerate -m "repair ..."` against a Postgres DB with the broken state applied, then manually fix the generated `drop_constraint(None, ...)` line — not a fully hand-rolled file. |
| C-02 | Tests ALWAYS run with `-n auto` | Every new test file must be worker-safe. Existing `conftest.py` uses `os.getpid()`-unique naming; new fixtures follow same pattern. |
| C-03 | Tests use SQLite in-memory; no PostgreSQL required for test run | SAFE-08 repair migrations target Postgres production. Testing the repair migrations locally requires `docker-compose up -d` for Postgres; unit tests around SAFE-09 naming-convention applicability still run on SQLite. |
| C-04 | Rate limiting disabled in tests by default | Auth characterization tests inherit this; do NOT flip `ENABLE_RATE_LIMITING=true`. |
| C-05 | `ENABLE_RATE_LIMITING` and `TESTING` env vars set BEFORE `from app.main import app` | New test modules follow the conftest.py top-of-file order. |
| C-06 | Backend formatting: `black --config pyproject.toml --line-length 120` | All new Python files conform. |
| C-07 | Backend imports sorted with `isort` (profile: "black") | All new Python files conform. |
| C-08 | Backend type-checked with `pyright` (strict) | All new Python files must satisfy pyright strict mode. |

## Architectural Responsibility Map

Phase 1 is infrastructure-only (CI + test scaffolding) with no new user-facing capabilities. The map below shows which tier each SAFE item lives in.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backend coverage gate (SAFE-01) | CI (GitHub Actions) | Test runner (pytest) | `--cov-fail-under` is enforced in `pytest.ini addopts` so local runs also enforce it; CI surfaces the failure. |
| Frontend test + coverage gate (SAFE-02, SAFE-03) | CI (GitHub Actions) | Test runner (vitest) | Same pattern — thresholds in `vitest.config.ts`, CI runs `npm test -- --run --coverage`. |
| Migration DROP-guard (SAFE-04) | CI (GitHub Actions) | — | Static check on `alembic/versions/*.py` files; no runtime component. |
| OpenAPI snapshot (SAFE-05) | Test runner (pytest) | API / Backend | Pure backend test that introspects the registered FastAPI app; runs in the normal pytest suite. |
| Auth characterization (SAFE-06) | Test runner (pytest) | API / Backend | Uses existing TestClient fixture; VCR cassettes live under `backend/tests/cassettes/auth/`. |
| Crawler adapter characterization (SAFE-07) | Test runner (pytest) | Crawlers (`app.crawlers.adapters`) | Fixture-driven; `parse_product_page()` is a pure function of HTML input. |
| Migration repairs (SAFE-08) | Database / Migrations (Alembic) | API / Backend | Touches schema migrations only; no app code change. |
| `MetaData.naming_convention` (SAFE-09) | API / Backend (`backend/app/db/base_class.py`) | Database / Migrations | One-line model-layer change that propagates to all future Alembic autogenerate runs. |
| Dependabot config (SAFE-10) | CI / Repo config (GitHub) | — | `.github/dependabot.yml`; GitHub-managed, no workflow file. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pytest-cov` | 6.2.1 (installed — latest 7.1.0 available) | Coverage measurement + `--cov-fail-under` | De-facto standard for Python coverage gates; integrates with pytest-xdist via built-in combine. [VERIFIED: `pip index versions pytest-cov` — 7.1.0 latest; backend/requirements.txt pins 6.2.1] |
| `pytest-recording` | 0.13.4 | VCR-cassette HTTP recording for pytest | Locked by REQUIREMENTS.md SAFE-06. Modern pytest-native wrapper around vcrpy with `@pytest.mark.vcr` decorator. [VERIFIED: `pip index versions pytest-recording` — 0.13.4 latest, 2025-04 release] |
| `vcrpy` | 8.1.1 (transitive dep of pytest-recording) | Underlying HTTP record/replay engine | Industry standard since ~2012; handles requests, urllib3, httpx, aiohttp. [VERIFIED: `pip index versions vcrpy` — 8.1.1 latest] |
| `@vitest/coverage-v8` | 3.2.4 (already installed — latest 4.1.5 available) | Frontend coverage provider | Already pinned in `frontend/package.json`; do NOT upgrade to 4.x this phase (breaking changes in coverage.include defaults per vitest 4.0 migration guide). [VERIFIED: `npm view @vitest/coverage-v8 version` — 4.1.5 latest; `frontend/package.json` pins `^3.2.4`] |
| `vitest` | 3.2.4 (already installed) | Frontend test runner | Already in use. [VERIFIED: frontend/package.json] |
| SQLAlchemy `MetaData(naming_convention=...)` | Built into SQLAlchemy 2.0.41 (already installed) | Deterministic constraint names | Official SQLAlchemy-recommended mechanism; Alembic autogenerate respects it. [VERIFIED: backend/requirements.txt line 21; context7 `/websites/sqlalchemy_en_20`] |
| GitHub-native Dependabot | Version 2 schema | Automated weekly dependency PRs | Zero extra infra. [VERIFIED: docs.github.com/code-security/dependabot — schema `version: 2`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `moto[s3]` | 5.1.22 (already installed) | In-memory S3 mock | Reuse existing `mock_s3` fixture in `conftest.py` for any SAFE-06 flow that touches S3 (e.g., profile-picture upload during signup, though not in the 7 locked flows). |
| `pytest-xdist` | 3.8.0 (already installed) | Parallel test execution | No new config; existing `-n auto --dist=loadfile` continues to apply. |
| `webauthn` | 2.5.2 (already installed) | WebAuthn server library | SAFE-06 flow 4 stubs `verify_registration_response` / `verify_authentication_response` at this module boundary — see Code Examples §WebAuthn stub. |
| `google-auth` | 2.45.0 (already installed) | Google OAuth ID token verification | SAFE-06 flow 5/6 records `google.oauth2.id_token.verify_oauth2_token`'s JWKS HTTPS traffic via VCR. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pytest-recording` | `responses` (requests-only mock) | Would miss non-requests HTTP libs (google-auth uses its own transport). pytest-recording + vcrpy intercepts all of them. |
| `pytest-recording` | Hand-written fixture responses | Loses the "replay real API" guarantee. Google's OAuth token verification calls JWKS endpoints that rotate keys — a hand-written fixture goes stale; a VCR cassette records a real key in a real response. |
| Istanbul (vitest coverage) | v8 provider | Already chosen (v8 is default + faster; project pinned to `@vitest/coverage-v8` since inception). |
| Renovate | Dependabot | Explicitly deferred in D-28. |
| Pre-commit hook for DROP-guard | CI-only step | D-07 locks CI-only — developer machines stay unencumbered. |

### Version verification

All versions verified via direct probing on 2026-04-21:
- `backend/requirements.txt` (installed package pins)
- `frontend/package.json` (installed package pins)
- `pip index versions <pkg>` (latest available on PyPI)
- `npm view <pkg> version` (latest available on npm)

**Installation:** All Phase 1 libraries are already installed **except** `pytest-recording`. Plan a task to add this line to `backend/requirements.txt`:

```
pytest-recording==0.13.4
```

## Architecture Patterns

### System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                     GITHUB PULL REQUEST                         │
└──────────────────┬──────────────────────────┬──────────────────┘
                   │                          │
                   ▼                          ▼
      ┌─────────────────────────┐   ┌──────────────────────┐
      │   backend-ci.yml        │   │  frontend-ci.yml     │
      │   (Python 3.13)         │   │  (Node 22)           │
      └───────────┬─────────────┘   └──────────┬───────────┘
                  │                             │
                  ▼                             ▼
       ┌────────────────────┐         ┌────────────────────┐
       │ 1. black --check   │         │ 1. prettier --check│
       │ 2. isort --check   │         │ 2. eslint          │
       │ 3. pyright         │         │ 3. tsc -b --noEmit │
       │ 4. bandit -ll      │         │ 4. npm audit       │
       │ 5. pip-audit       │         │ 5. ┌─────────────┐ │
       │ 6. ┌──────────┐    │         │    │Run tests   │◄─┼── SAFE-02
       │    │DROP-guard│◄───┼── SAFE-04│    │--coverage  │ │   SAFE-03
       │    └──────────┘    │         │    └──────┬──────┘ │
       │ 7. pytest -n auto  │         │           ▼        │
       │    --cov=app       │◄─ SAFE-01│    ┌──────────┐    │
       │    --cov-fail-under│         │    │thresholds│    │
       │    (from pytest.ini│         │    │check (v8)│    │
       │    addopts)        │         │    └──────────┘    │
       └─────────┬──────────┘         │ 6. npm run build   │
                 │                    └────────────────────┘
                 ▼                        
       ┌──────────────────────┐
       │ pytest run includes: │
       │ - OpenAPI snapshot   │◄─ SAFE-05
       │   (test_openapi_     │
       │   snapshot.py)       │
       │ - Auth characterization│◄─ SAFE-06 (reads cassettes)
       │   (test_auth_*.py)   │   
       │ - Crawler charact.   │◄─ SAFE-07 (reads HTML fixtures)
       │   (test_characteri-  │
       │   zation_<adapter>.py)│
       └──────────────────────┘

                          ┌─────────────────────┐
                          │.github/dependabot.yml│◄─ SAFE-10
                          │(GitHub-managed;     │
                          │ not a workflow file)│
                          └─────────────────────┘

MODEL-LAYER (runtime behavior):
  backend/app/db/base_class.py
    └─ Base = declarative_base() with MetaData(naming_convention=...)◄─ SAFE-09
         │
         │ (inherited by all ORM models in app/api/models/*.py)
         ▼
  backend/app/db/base.py (imports every model into Base.metadata)
         │
         ▼
  backend/alembic/env.py:
    target_metadata = Base.metadata
         │  (autogenerate now sees the naming_convention;
         │   new migrations produce named constraints)
         ▼
  NEW migrations: named constraints everywhere
  HISTORIC migrations 097024200e60, 172d1c205fb3, 6eae6b1393c5: repair via new migrations ◄─ SAFE-08
```

Data flow:
1. Developer pushes PR → both `backend-ci.yml` and `frontend-ci.yml` run (path-filtered).
2. Backend CI: existing lint → new DROP-guard → existing test step (now with `--cov-fail-under` enforced via pytest.ini).
3. Frontend CI: existing lint/type-check/audit → new test step (with coverage thresholds) → existing build step.
4. Once per week on Monday, Dependabot opens grouped minor+patch PRs per ecosystem + individual PRs for majors.

### Recommended Project Structure

New / modified files in Phase 1:

```
backend/
├── pytest.ini                                    # + --cov-fail-under=<N>
├── requirements.txt                              # + pytest-recording==0.13.4
├── scripts/
│   └── check_migrations.py                       # NEW (SAFE-04)
├── app/
│   └── db/
│       └── base_class.py                         # MODIFIED (SAFE-09) — add MetaData(naming_convention=...)
├── alembic/
│   └── versions/
│       ├── 097024200e60_...py                    # REPAIRED in-place OR new repair migration (SAFE-08)
│       ├── 172d1c205fb3_...py                    # REPAIRED in-place OR new repair migration (SAFE-08)
│       ├── 6eae6b1393c5_...py                    # REPAIRED in-place OR new repair migration (SAFE-08)
│       └── YYYYMMDD_<slug>_repair_drop_constraint_none.py  # NEW if prod-applied (SAFE-08)
├── tests/
│   ├── fixtures/
│   │   └── openapi_snapshot.json                 # NEW (SAFE-05)
│   ├── test_openapi_snapshot.py                  # NEW (SAFE-05)
│   ├── cassettes/
│   │   └── auth/
│   │       ├── test_signup_verify_email.yaml     # NEW (SAFE-06)
│   │       ├── test_login.yaml                   # NEW (SAFE-06)
│   │       ├── test_totp_enrollment.yaml         # NEW (SAFE-06)
│   │       ├── test_webauthn_registration.yaml   # NEW (SAFE-06)
│   │       ├── test_google_oauth_signin.yaml     # NEW (SAFE-06)
│   │       ├── test_google_oauth_link.yaml       # NEW (SAFE-06)
│   │       └── test_password_reset.yaml          # NEW (SAFE-06)
│   ├── test_auth_characterization.py             # NEW (SAFE-06)
│   └── crawlers/
│       ├── fixtures/
│       │   ├── briantooleyracing/
│       │   │   ├── product.html                  # NEW (SAFE-07)
│       │   │   └── expected.json                 # NEW (SAFE-07)
│       │   ├── amsperformance/...
│       │   └── <3 more adapters>/...
│       └── test_characterization_<adapter>.py    # NEW × 5 (SAFE-07)
frontend/
└── vitest.config.ts                              # + coverage.thresholds
.github/
├── dependabot.yml                                # NEW (SAFE-10)
└── workflows/
    ├── backend-ci.yml                            # + DROP-guard step
    └── frontend-ci.yml                           # + Run tests step
```

### Pattern 1: pytest.ini `addopts`-based coverage gate

**What:** Place `--cov-fail-under=<N>` in `pytest.ini addopts` rather than the CI command.

**When to use:** Always. Centralizing in `pytest.ini` means the gate also applies to local developer `pytest` runs, not just CI — giving developers fast feedback.

**Example:**
```ini
# backend/pytest.ini (existing file — one line added)
# Source: https://pytest-cov.readthedocs.io/en/latest/config.html
[tool:pytest]
testpaths = app/tests   # NOTE: This path is STALE — actual tests are in backend/tests/.
                         # CI works because `cd backend && pytest` falls back to auto-discovery.
                         # Optional cleanup: update to `testpaths = tests` — not required this phase.
addopts =
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
    --cov-fail-under=<MEASURED_BASELINE>   # <<< SAFE-01 addition
    -n auto
    --dist=loadfile
    -W ignore::ResourceWarning
```

### Pattern 2: vitest coverage thresholds

**What:** `coverage.thresholds` object in `vitest.config.ts` with positive-integer values representing minimum percentages.

**Example:**
```typescript
// frontend/vitest.config.ts
// Source: https://vitest.dev/config/#coverage-thresholds (verified 2026-04-21)
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/coverage/**',
        'dist/',
        'build/',
      ],
      thresholds: {           // <<< SAFE-03 addition (D-06 floors)
        lines: 60,
        functions: 50,
        branches: 50,
        statements: 60,
      },
    },
  },
});
```

Vitest emits a non-zero exit code when any threshold is unmet; the CI step fails. The exact message format is not documented in the official vitest config page ([CITED: vitest.dev/config/coverage — "does not specify what Vitest outputs when thresholds are violated"]), but empirically it logs `ERROR: Coverage for lines (45.2%) does not meet global threshold (60%)` — this is consistent with istanbul's historic format, which v8 inherited.

### Pattern 3: `MetaData(naming_convention=...)` applied to declarative Base

**What:** Attach a `naming_convention` dict to the `MetaData` object that `Base` uses. Every Table attached to that Base inherits the convention. Alembic autogenerate reads the convention and produces deterministically-named constraints for all NEW migrations.

**Example:**
```python
# backend/app/db/base_class.py (currently 3 lines; becomes ~16)
# Source: https://docs.sqlalchemy.org/en/20/core/constraints.html#constraint-naming-conventions
#         (verified via context7 /websites/sqlalchemy_en_20, 2026-04-21)
from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

# SQLAlchemy-recommended convention. Locked by D-11.
# - ix:   indexes
# - uq:   unique constraints
# - ck:   check constraints
# - fk:   foreign keys (includes referred table for disambiguation)
# - pk:   primary keys
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
Base = declarative_base(metadata=metadata)
```

**Alembic integration:** No change required. `backend/alembic/env.py` already has `target_metadata = Base.metadata` (verified: env.py line 55). As soon as `Base` carries the convention, autogenerate sees it.

### Pattern 4: Forward-only repair migration for historically-broken drops

**What:** When a migration with `op.drop_constraint(None, ...)` has already been applied to prod, you cannot rewrite it in-place without rewriting history. Write a NEW migration whose `upgrade()` is effectively a no-op (the state is already correct) but whose `downgrade()` is the properly-named drop the original migration should have done.

**Example:**
```python
# backend/alembic/versions/YYYYMMDDHHMM_repair_drop_constraint_none_refs.py
# Source: https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.drop_constraint
"""repair invalid drop_constraint(None) — see SAFE-08

Revision ID: <generated>
Revises: <current head>

The three migrations 097024200e60, 172d1c205fb3, 6eae6b1393c5 each contain
`op.drop_constraint(None, <table>, type_='foreignkey')` in their downgrade()
blocks. With None as the name, Alembic can never resolve which constraint
to drop, so `alembic downgrade` to any revision at-or-before those files
fails hard.

This repair migration is a no-op forward (upgrade = pass) because the
current prod schema is correct. Its downgrade() re-expresses the drops
with the constraint names inspected from prod (see task notes for the
`psql \d+` output that established these names). The historic migrations
remain in history unchanged.
"""
from typing import Sequence, Union
from alembic import op

revision: str = "<GENERATED>"
down_revision: Union[str, None] = "<CURRENT HEAD>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Schema is already correct; nothing to do."""
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    pass


def downgrade() -> None:
    """Drop the FKs that the three broken migrations should have named."""
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    op.drop_constraint("fk_parts_canonical_part_id_parts", "parts", type_="foreignkey")
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    op.drop_constraint(
        "fk_build_list_parts_build_list_phase_id_build_list_phases",
        "build_list_parts",
        type_="foreignkey",
    )
    # SAFE: repair invalid drop_constraint(None) — see SAFE-08
    op.drop_constraint("fk_global_parts_brand_id_brands", "global_parts", type_="foreignkey")
```

**Note:** The actual constraint names above are the names the new `naming_convention` would produce. The real prod constraints will be Postgres-auto-generated names like `parts_canonical_part_id_fkey` — the planner must inspect the live DB to find them. See Code Example §Introspecting prod constraint names.

**If the three migrations have NOT yet run on prod** (unlikely per D-14 but worth checking): edit the original three files in-place, swapping `None` for the named constraint. That's lower risk than a repair pair because the broken downgrade() was never reachable.

### Pattern 5: VCR cassette for Google OAuth

**What:** `@pytest.mark.vcr` decorator replays HTTPS traffic from a recorded YAML file. Tests run offline in CI; cassettes are regenerated locally by deleting + re-running with `--record-mode=once`.

**Example:** See Code Examples §Auth characterization with VCR.

### Pattern 6: Characterization test against fixture HTML

**What:** Feed a committed HTML file through `adapter.parse_product_page(html, url)` and assert the returned `ScrapedPayload` matches a committed `expected.json`. Bypasses network entirely — no VCR needed.

**Example:** See Code Examples §Crawler characterization test.

### Anti-Patterns to Avoid

- **Hand-writing the repair migrations from scratch (CLAUDE.md C-01 violation):** Always start from `alembic revision --autogenerate` against a Postgres DB carrying the broken state, then edit only the lines that autogen got wrong.
- **Retroactively renaming historic constraints to match the new convention:** Explicitly forbidden by D-12. Would require a sweep migration with RENAME CONSTRAINT against live RDS — unsafe.
- **Using a hash instead of the formatted-JSON OpenAPI snapshot:** D-27 forbids. Reviewers need the diff as a review artifact.
- **Setting aspirational coverage thresholds above measured baseline (D-02 violation):** Would land red CI on day 1. Measure first, gate at measured value.
- **Placing `--cov-fail-under` in the CI command instead of `pytest.ini`:** Developer would not feel the gate locally until they push. `pytest.ini addopts` is the correct home.
- **Using `ignore` in dependabot.yml to suppress majors:** That suppresses majors entirely. With ONLY a `groups` block for minor+patch, Dependabot automatically raises majors as individual PRs ([CITED: docs.github.com/en/code-security/dependabot/dependabot-version-updates/optimizing-pr-creation-version-updates, verified 2026-04-21]) — that is what D-30 asks for.
- **Skipping cassette secret scrubbing:** VCR recordings of real Google OAuth flows contain the authorization bearer and cookies. Always set `filter_headers=["authorization", "cookie", "set-cookie"]` in the vcr_config fixture.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP record/replay for Google OAuth | Fixture-response dicts | `pytest-recording` (vcrpy) | JWKS key rotation makes fixture responses go stale; VCR records real signed tokens. |
| Coverage aggregation across xdist workers | Manual `.coverage.*` combining | `pytest-cov` built-in | pytest-cov automatically detects xdist and calls `coverage combine` before emitting the report ([CITED: pytest-cov.readthedocs.io/en/latest/xdist.html]). |
| Alembic constraint naming | Manual `.name=` on every Column/Table | `MetaData(naming_convention=...)` | Single point of truth; autogenerate reads it; all models inherit automatically. |
| Dependency-upgrade PR scheduler | Cron job + bash + git | GitHub-native Dependabot | Zero-infra, weekly PRs, grouped + individual out-of-the-box. |
| Multi-directory npm watching | Two separate Dependabot entries with identical group config | One entry with `directories: ["/frontend", "/chrome-extension"]` | Dependabot schema v2 supports multi-directory per ecosystem ([CITED: docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file]). |
| OpenAPI schema drift detection | Handroll endpoint-by-endpoint audit | `app.openapi()` + `json.dumps(..., indent=2, sort_keys=True)` snapshot | FastAPI already computes the full OpenAPI schema; capture it verbatim and diff. |

**Key insight:** Every safety-net in this phase has a canonical library implementation. The risk is not "we didn't solve it" — it's "we solved it badly by writing custom glue." Resist the temptation; every item here has battle-tested tooling.

## Runtime State Inventory

Phase 1 is *additive only* — it does not rename, move, or delete any existing string or runtime asset. However, two items produce durable state that the planner must account for:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — Phase 1 does not touch stored data. | None |
| Live service config | **GitHub Dependabot subscription** is activated simply by committing `.github/dependabot.yml` — GitHub side-effect. Nothing else runs this. | None (automatic on commit; no auth/IAM change) |
| OS-registered state | None | None |
| Secrets and env vars | None — new libraries do not require new env vars. | None |
| Build artifacts / installed packages | Adding `pytest-recording` to `requirements.txt` requires `pip install -r requirements.txt` in dev environments AND in CI. CI does this on every run (no caching side effects). Local devs must rerun install once. | Add note to PR description: "Run `cd backend && pip install -r requirements.txt`." |

**Runtime schema impact of SAFE-09:** Adding `MetaData(naming_convention=...)` is a Python-layer-only change. No DDL is emitted. **The critical thing is that it must NOT cause the next `alembic revision --autogenerate` to produce a rename-everything migration.** See Common Pitfalls §Autogen avalanche for the exact mechanism and mitigation.

## Common Pitfalls

### Pitfall 1: Autogenerate-avalanche after adding `naming_convention`

**What goes wrong:** You add `MetaData(naming_convention=...)` to base_class.py, run `alembic revision --autogenerate -m "test"`, and the generated migration wants to RENAME every existing constraint in the DB to match the new convention (e.g., `parts_canonical_part_id_fkey` → `fk_parts_canonical_part_id_parts`). Running that migration against prod is unsafe and out of scope for this phase (D-12).

**Why it happens:** Alembic compares `Base.metadata` (Python side — now has named constraints per the convention) against the live DB schema (Postgres side — has whatever names Postgres auto-generated). The diff is "rename every constraint".

**How to avoid:**
1. **Do NOT run `alembic revision --autogenerate` immediately after adding naming_convention** unless you expect to discard its output. The SAFE-09 commit is a Python-only change; it produces no new migration.
2. When you later need an autogenerate for a real schema change, **manually delete any `alter_column` / `rename_constraint` lines in the generated migration that are pure-rename** before committing. Real schema changes stay; cosmetic renames get dropped.
3. Document this in `CONVENTIONS.md` so Phase 4 (DATA-09) codifies the expected workflow — but that documentation task is Phase 4 scope, not this phase.

**Warning signs:** Running `alembic revision --autogenerate -m "test"` after the SAFE-09 change produces a migration file with many `op.alter_column(... existing_server_default=...)` or `op.drop_constraint(<old_name>, ...) + op.create_foreign_key(<new_name>, ...)` pairs referring to constraints the models haven't actually changed.

### Pitfall 2: pytest.ini `testpaths` is stale

**What goes wrong:** The existing `pytest.ini` has `testpaths = app/tests` — but tests live at `backend/tests/`, not `backend/app/tests/`. The CI works because `cd backend && pytest` falls back to auto-discovery from CWD when `testpaths` doesn't exist. If a developer adds a new test under `app/tests/` expecting it to run, it won't — or worse, the fallback stops working for some future pytest release.

**Why it happens:** Historical artifact — tests were at `app/tests/` at some point and got moved.

**How to avoid:** Optional cleanup: update `pytest.ini` to `testpaths = tests`. **Do not bundle this with the SAFE-01 PR** — it's an unrelated fix. Note as a candidate follow-up.

**Warning signs:** `pytest --collect-only` in a fresh clone emits `collected 0 items` — but it doesn't in practice because CWD fallback masks the issue.

### Pitfall 3: pytest-xdist + pytest-recording recording race

**What goes wrong:** If you run `pytest -n auto --record-mode=once` with no existing cassettes, multiple workers may try to write the SAME cassette file simultaneously.

**Why it happens:** Default cassette path is `cassettes/<module>/<test_function>.yaml` — one per test function. In practice each test function runs on exactly one worker, so cross-worker conflicts don't arise. But if two tests share the same `vcr_cassette_name`, collision is possible.

**How to avoid:**
- Recording is a one-time local developer operation. Run `pytest -n 0 --record-mode=once backend/tests/test_auth_characterization.py` (serial) when creating cassettes.
- CI only replays (`--record-mode=none`, the pytest-recording default), so parallelization is always safe there.

**Warning signs:** If a cassette file is half-written or ends mid-YAML, it was probably a concurrent-write issue during local recording. Delete and re-record serially.

### Pitfall 4: pytest-cov + pytest-xdist `.coverage` combine race on custom plugins

**What goes wrong:** A rare failure mode where custom coverage plugins fight pytest-cov's automatic `coverage combine` call at session end ([CITED: github.com/pytest-dev/pytest-cov/issues/642]).

**Why it happens:** Only relevant if a custom coverage plugin is configured. CarModPicker uses plain pytest-cov with no plugins — not vulnerable.

**How to avoid:** Do not add custom coverage plugins this phase.

### Pitfall 5: Vitest 4.0 migration breaks `coverage.all` default

**What goes wrong:** Vitest 4.0 changed `coverage.include` semantics: previously `coverage.all: true` was the default (include every file); now `coverage.include` must be explicitly set to include uncovered files ([CITED: vitest.dev/guide/migration, 2026-04-21]).

**Why it happens:** Project is on vitest 3.2.4 — not affected. But if Dependabot later proposes a 4.x upgrade, the SAFE-03 thresholds may silently measure only imported-during-test files instead of the whole `src/` tree, inflating the coverage number.

**How to avoid:** When the vitest 4 upgrade PR lands, add `coverage.include: ['src/**/*.{ts,tsx}']` in the same PR.

**Warning signs:** After a vitest upgrade, `npm run test:coverage` reports unexpectedly high coverage even though no new tests were added.

### Pitfall 6: Dependabot `ignore` for majors suppresses them entirely

**What goes wrong:** A well-meaning engineer adds `ignore: [{dependency-name: "*", update-types: ["version-update:semver-major"]}]` to reduce noise. This SILENTLY prevents any major update from ever being raised — violating D-30.

**Why it happens:** A common bad example in online tutorials.

**How to avoid:** Do NOT use `ignore` for majors. With ONLY a `groups` block configured for minor+patch, Dependabot automatically opens individual PRs for majors — this is the documented default behavior. [CITED: docs.github.com/en/code-security/dependabot/dependabot-version-updates/optimizing-pr-creation-version-updates — Example 3 + confirmed via webfetch 2026-04-21]

### Pitfall 7: CONTEXT.md D-20 label mismatch — `tier1_flaresolverr` does not exist

**What goes wrong:** CONTEXT.md D-20 references `tier1_flaresolverr` as a directory. The actual directory layout is `tier1_tls` (curl_cffi TLS impersonation) and `tier2_browser` (FlareSolverr). The FETCHER_TIER values are `"http"`, `"tls"`, and `"browser"`.

**Why it happens:** Common naming confusion between the fetcher tier number and fetcher tier purpose.

**How to avoid:** Plan SAFE-07 adapter picks as: 2× tier0_http, 2× tier2_browser (FlareSolverr — "most critical" per D-20), 1× tier1_tls (curl_cffi — "most stable" per D-20). **Note this correction in the PLAN.md** so no one wastes time hunting a `tier1_flaresolverr` directory.

**Warning signs:** `ls backend/app/crawlers/adapters/` shows `tier0_http/ tier1_tls/ tier2_browser/` — no `tier1_flaresolverr`.

### Pitfall 8: OpenAPI snapshot app-import timing

**What goes wrong:** `test_openapi_snapshot.py` calls `from app.main import app` and then `app.openapi()`. If the import happens BEFORE the conftest.py's env-var setup (`TESTING=true`, `ENABLE_RATE_LIMITING=false`), the rate-limiter gets wired into the OpenAPI schema, and the snapshot includes rate-limit-related response codes.

**Why it happens:** Module import order in pytest is determined by collection order; conftest.py runs first, so in practice this is fine — but if someone adds a `from app.main import app` at module-top-level BEFORE conftest executes, trouble.

**How to avoid:** Let `TestClient` pull `app` through the existing `client` fixture machinery. The snapshot test imports `app` at function scope, not module scope:
```python
def test_openapi_snapshot_matches():
    from app.main import app
    ...
```

**Warning signs:** Snapshot diff mysteriously includes rate-limit headers the first time; disappears after rerun.

## Code Examples

### 1. Measuring the backend coverage baseline (SAFE-01)

```bash
# Run from backend/. Produces the number you hard-code into --cov-fail-under.
# Source: https://pytest-cov.readthedocs.io/en/latest/readme.html (verified 2026-04-21)
cd backend
pytest -n auto --cov=app --cov-report=term | tail -5
# Output includes line like:
#   TOTAL    12345    3210    74%
# Take the percentage (74 in this example), round DOWN to nearest whole, write that to pytest.ini.
```

### 2. `backend/scripts/check_migrations.py` (SAFE-04)

```python
#!/usr/bin/env python3
"""
SAFE-04: Migration DROP-guard.

Fails CI if any file in backend/alembic/versions/*.py contains
drop_column, drop_table, or drop_constraint without a `# SAFE: <reason>`
annotation on the SAME line or the IMMEDIATELY PRECEDING line.

Usage:
    python backend/scripts/check_migrations.py
    # Exit 0 on success; exit 1 with filename + line number on failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "backend" / "alembic" / "versions"

# Matches the three destructive ops; requires op.<name>( prefix to avoid
# false-positives on e.g. variable names or function definitions.
DESTRUCTIVE_OP_RE = re.compile(r"\bop\.(drop_column|drop_table|drop_constraint)\s*\(")

# The exact annotation token. We grep the full comment for "SAFE:" to
# avoid whitespace/punctuation variants.
SAFE_ANNOTATION_RE = re.compile(r"#\s*SAFE:\s*\S")


def check_file(path: Path) -> list[tuple[int, str]]:
    """Return a list of (1-indexed line number, offending line text) for violations."""
    lines = path.read_text(encoding="utf-8").splitlines()
    violations: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if not DESTRUCTIVE_OP_RE.search(line):
            continue
        # Same line annotation?
        if SAFE_ANNOTATION_RE.search(line):
            continue
        # Immediately-preceding-line annotation?
        if idx > 0 and SAFE_ANNOTATION_RE.search(lines[idx - 1]):
            continue
        violations.append((idx + 1, line.rstrip()))
    return violations


def main() -> int:
    if not MIGRATIONS_DIR.is_dir():
        print(f"ERROR: migrations dir not found: {MIGRATIONS_DIR}", file=sys.stderr)
        return 2

    failures: list[tuple[Path, int, str]] = []
    for py in sorted(MIGRATIONS_DIR.glob("*.py")):
        for lineno, text in check_file(py):
            failures.append((py, lineno, text))

    if not failures:
        print(f"check_migrations: OK ({len(list(MIGRATIONS_DIR.glob('*.py')))} files scanned)")
        return 0

    print("check_migrations: FAILURES")
    print()
    for path, lineno, text in failures:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{lineno}")
        print(f"    {text}")
        print(f"    --> Add `# SAFE: <reason>` on this line or the line above.")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Worked examples:**

PASSES (same-line annotation):
```python
op.drop_column("users", "legacy_avatar_path")  # SAFE: column is empty on prod; see ADR-007
```

PASSES (preceding-line annotation):
```python
# SAFE: table has zero rows on prod (verified via COUNT(*) 2026-04-18)
op.drop_table("abandoned_experiments")
```

FAILS (no annotation):
```python
op.drop_constraint("fk_parts_canonical", "parts", type_="foreignkey")
```

FAILS (annotation two lines above, not immediately preceding):
```python
# SAFE: this is the destructive sweep
some_other_line = 1
op.drop_column("users", "legacy_field")  # <-- FAIL: 1 line gap
```

### 3. CI step for DROP-guard (SAFE-04)

Insert into `.github/workflows/backend-ci.yml` between `Scan dependencies` (step 7) and `Run tests with coverage` (step 8):

```yaml
      - name: Check migrations for unannotated destructive operations
        run: |
          python backend/scripts/check_migrations.py
```

### 4. Introspecting prod constraint names (SAFE-08 prep)

```sql
-- Connect to a Postgres DB that has the broken-migration state applied
-- (a snapshot of prod, OR a docker-compose postgres that ran all migrations up).
--
-- For 097024200e60 — constraint on parts(canonical_part_id) → parts(id):
SELECT conname
FROM pg_constraint
WHERE conrelid = 'parts'::regclass
  AND contype = 'f'
  AND (
    SELECT array_agg(attname ORDER BY attnum)
    FROM unnest(conkey) AS col(colnum)
    JOIN pg_attribute ON attrelid = conrelid AND attnum = col.colnum
  ) = ARRAY['canonical_part_id'];
-- Typical Postgres auto-name: parts_canonical_part_id_fkey

-- For 172d1c205fb3 — constraint on build_list_parts(build_list_phase_id):
SELECT conname FROM pg_constraint
WHERE conrelid = 'build_list_parts'::regclass
  AND contype = 'f'
  AND (SELECT array_agg(attname ORDER BY attnum) FROM unnest(conkey) col(colnum)
       JOIN pg_attribute ON attrelid=conrelid AND attnum=col.colnum) = ARRAY['build_list_phase_id'];
-- Typical auto-name: build_list_parts_build_list_phase_id_fkey

-- For 6eae6b1393c5 — constraint on global_parts(brand_id) → brands(id):
SELECT conname FROM pg_constraint
WHERE conrelid = 'global_parts'::regclass
  AND contype = 'f'
  AND (SELECT array_agg(attname ORDER BY attnum) FROM unnest(conkey) col(colnum)
       JOIN pg_attribute ON attrelid=conrelid AND attnum=col.colnum) = ARRAY['brand_id'];
-- Typical auto-name: global_parts_brand_id_fkey
```

Alternatively, via SQLAlchemy Inspector (pure-Python):

```python
from sqlalchemy import create_engine, inspect
engine = create_engine("postgresql://...local docker postgres with broken state applied...")
insp = inspect(engine)
for fk in insp.get_foreign_keys("parts"):
    if fk["constrained_columns"] == ["canonical_part_id"]:
        print(fk["name"])  # emits the real constraint name
```

### 5. `test_openapi_snapshot.py` (SAFE-05)

```python
"""
SAFE-05: OpenAPI schema snapshot test.

Catches unintended route / schema drift. The snapshot is formatted JSON
(indent=2, sort_keys=True) so the diff in PR review IS the schema change.

Regenerate:
    python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" > backend/tests/fixtures/openapi_snapshot.json
"""
import json
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "openapi_snapshot.json"


def test_openapi_snapshot_matches() -> None:
    # Import at function scope so conftest.py env setup runs first.
    from app.main import app

    actual = json.dumps(app.openapi(), indent=2, sort_keys=True)
    expected = SNAPSHOT_PATH.read_text(encoding="utf-8")

    if actual != expected:
        # Give the developer the shell command to regenerate in one paste.
        msg = (
            "OpenAPI schema drift detected.\n"
            "Review the diff carefully — if intentional, regenerate with:\n"
            "    python -c \"import json; from app.main import app; "
            "print(json.dumps(app.openapi(), indent=2, sort_keys=True))\" "
            f"> {SNAPSHOT_PATH.relative_to(Path.cwd()) if Path.cwd() in SNAPSHOT_PATH.parents else SNAPSHOT_PATH}"
        )
        assert actual == expected, msg
```

Works with pytest-xdist: the test is deterministic and read-only. `-n auto --dist=loadfile` runs it exactly once on one worker.

### 6. Auth characterization with VCR cassette (SAFE-06)

Module-level conftest addition for `backend/tests/conftest.py` or a new `backend/tests/conftest_vcr.py`:

```python
# backend/tests/conftest.py (append near the end)
import pytest

@pytest.fixture(scope="module")
def vcr_config() -> dict:
    """
    VCR configuration for pytest-recording.

    - Scrub auth headers and cookies from cassettes (secrets never committed).
    - Scrub Google OAuth authorization code / refresh token from POST bodies.
    - Match on method + URL + body so replay is deterministic across reruns.
    """
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("cookie", "REDACTED"),
            ("set-cookie", "REDACTED"),
            ("x-goog-api-key", "REDACTED"),
        ],
        "filter_post_data_parameters": [
            ("client_secret", "REDACTED"),
            ("code", "REDACTED"),
            ("refresh_token", "REDACTED"),
        ],
        "filter_query_parameters": [
            ("api_key", "REDACTED"),
            ("access_token", "REDACTED"),
        ],
        "record_mode": "none",  # Replay only in CI. `--record-mode=once` on CLI for local recording.
        "match_on": ("method", "scheme", "host", "port", "path", "query"),
    }
```

Sample test (Google OAuth sign-in, SAFE-06 flow 5):

```python
# backend/tests/test_auth_characterization.py
"""
SAFE-06 auth characterization tests. One test per happy-path flow.

Assertion depth (D-19): HTTP status, presence of expected response keys,
and DB state change where relevant. Flows that touch external HTTPS (Google
OAuth) use pytest-recording; WebAuthn crypto is stubbed at the library
boundary.

Regenerate cassettes:
    cd backend
    # One-time per flow: delete cassette, run serial with --record-mode=once
    rm tests/cassettes/auth/test_google_oauth_signin.yaml
    pytest -n 0 --record-mode=once tests/test_auth_characterization.py::test_google_oauth_signin
"""
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.user import User


@pytest.mark.vcr
def test_google_oauth_signin(client: TestClient, db_session: Session) -> None:
    """First-time Google sign-in creates a user and returns a token."""
    # Trigger the exchange endpoint — real HTTPS would hit Google JWKS; VCR replays.
    response = client.post(
        "/api/auth/google/callback",
        json={"id_token": "<GIS-issued token from recording time>", "nonce": "test_nonce_abc"},
    )
    # D-19: status + key presence + DB side effect
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user" in data
    # DB state change
    user = db_session.query(User).filter(User.email == "recorded_test_user@example.com").first()
    assert user is not None
    assert user.email_verified is True
```

### 7. WebAuthn stub (SAFE-06 flow 4)

The `webauthn` package exposes four cryptographic boundary functions the auth endpoint calls:
- `generate_registration_options`
- `verify_registration_response`
- `generate_authentication_options`
- `verify_authentication_response`

Stub at this boundary — NOT over HTTP:

```python
# backend/tests/test_auth_characterization.py (continued)
from webauthn.helpers.structs import (
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    RegistrationCredential,
)


@patch("app.api.endpoints.auth.verify_registration_response")
@patch("app.api.endpoints.auth.generate_registration_options")
def test_webauthn_registration(
    mock_generate: Any,
    mock_verify: Any,
    client: TestClient,
    db_session: Session,
    test_user: User,
) -> None:
    """WebAuthn passkey registration round-trip with crypto stubbed at lib boundary."""
    from app.tests.conftest import login_user

    token = login_user(client, test_user.username)
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: request options
    mock_generate.return_value = _make_fake_registration_options()
    r1 = client.post("/api/auth/webauthn/register/begin", headers=headers)
    assert r1.status_code == 200
    assert "challenge" in r1.json()

    # Step 2: submit credential — crypto verification stubbed as success
    mock_verify.return_value = _make_fake_verified_registration()
    r2 = client.post(
        "/api/auth/webauthn/register/complete",
        headers=headers,
        json={"credential": _make_fake_client_registration_credential()},
    )
    assert r2.status_code == 200
    # DB state change: credential row exists
    from app.api.models.webauthn_credential import WebAuthnCredential  # adjust actual model path at plan time
    creds = db_session.query(WebAuthnCredential).filter_by(user_id=test_user.id).all()
    assert len(creds) == 1
```

The `_make_fake_*` helpers return minimal objects that satisfy type signatures — the planner fills in the exact shape by reading the `webauthn.helpers.structs` module and the 4-5 fields the endpoint reads off each return.

### 8. Crawler adapter characterization test (SAFE-07)

```python
# backend/tests/crawlers/test_characterization_briantooleyracing.py
"""
SAFE-07 characterization: pin current parse_product_page() output for
briantooleyracing post-7831fda fix. Feeds committed HTML through the adapter;
asserts parsed fields match committed expected.json.

If parse output changes intentionally, delete expected.json and re-run the
regeneration command at the bottom of this file.
"""
import json
from pathlib import Path
from typing import Any

import pytest

from app.crawlers.adapters.tier0_http.briantooleyracing import BrianTooleyRacingAdapter

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "briantooleyracing"
HTML_PATH = FIXTURE_DIR / "product.html"
EXPECTED_PATH = FIXTURE_DIR / "expected.json"


def _payload_to_dict(payload: Any) -> dict:
    """Convert ScrapedPayload dataclass into a dict for JSON comparison."""
    from dataclasses import asdict
    return asdict(payload)


def test_parse_product_page_matches_expected() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    with open(EXPECTED_PATH) as f:
        expected = json.load(f)

    adapter = BrianTooleyRacingAdapter()
    payload = adapter.parse_product_page(html, expected["product_url"])

    assert payload is not None, "parse_product_page returned None for known-good fixture"
    actual = _payload_to_dict(payload)

    # D-22: assert parsed canonical fields match committed expected-output JSON.
    # image_urls: compare as sets because CDN hashes may reorder; the SET of
    # image URLs is stable, their order is not a contract.
    actual_images = set(actual.pop("image_urls") or [])
    expected_images = set(expected.pop("image_urls") or [])
    assert actual_images == expected_images, "image URL set drift"
    assert actual == expected, "parse output drift (non-image fields)"


# To regenerate expected.json:
#   python -c "
#   import json
#   from dataclasses import asdict
#   from pathlib import Path
#   from app.crawlers.adapters.tier0_http.briantooleyracing import BrianTooleyRacingAdapter
#   FIXTURE = Path('backend/tests/crawlers/fixtures/briantooleyracing')
#   html = (FIXTURE/'product.html').read_text()
#   url = 'https://briantooleyracing.com/...fill in the canonical URL...'
#   out = asdict(BrianTooleyRacingAdapter().parse_product_page(html, url))
#   out['product_url'] = url
#   (FIXTURE/'expected.json').write_text(json.dumps(out, indent=2, sort_keys=True))
#   "
```

`expected.json` shape:

```json
{
  "name": "BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT",
  "product_url": "https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html",
  "description": "BTR's .560 lift LS6-style valve springs...",
  "price_cents": 11999,
  "part_manufacturer": "Brian Tooley Racing",
  "part_number": "SP011-16",
  "image_urls": [
    "https://briantooleyracing.com/media/catalog/product/m/2/m2_sp011-16_22.jpg",
    "https://briantooleyracing.com/media/catalog/product/v/a/valve-spring-installed-height-tech_01_1_51.jpg"
  ],
  "gtin": null
}
```

### 9. `.github/dependabot.yml` (SAFE-10)

```yaml
# .github/dependabot.yml
# Source: https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file
# Verified 2026-04-21.
#
# D-30: Group minor+patch per ecosystem. Individual major PRs are emitted
# AUTOMATICALLY by Dependabot for anything not covered by a group — no `ignore`
# block needed. See
# https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/optimizing-pr-creation-version-updates
version: 2
updates:
  # Backend Python dependencies
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    groups:
      minor-patch:
        applies-to: version-updates
        patterns: ["*"]
        update-types: ["minor", "patch"]

  # Frontend npm dependencies (two directories — single ecosystem entry)
  - package-ecosystem: "npm"
    directories:
      - "/frontend"
      - "/chrome-extension"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    groups:
      minor-patch:
        applies-to: version-updates
        patterns: ["*"]
        update-types: ["minor", "patch"]

  # GitHub Actions workflows
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    groups:
      minor-patch:
        applies-to: version-updates
        patterns: ["*"]
        update-types: ["minor", "patch"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Write `coverage` config in `.coveragerc` | `pytest.ini addopts` with `--cov-*` flags | pytest-cov 2.x→3.x (2021) | Single config file; current project already uses addopts. |
| `vitest` with `coverage.all: true` default | `vitest` 4.x with explicit `coverage.include` | vitest 4.0 (2025) | **Project still on 3.2.4 — not affected.** Migration path documented in Pitfall 5. |
| Manual Alembic constraint names on every `ForeignKey` | `MetaData(naming_convention=...)` once | SQLAlchemy 0.9 (2014) | De-facto standard; D-11 adopts. |
| `@pytest.fixture` + hand-rolled fake HTTP clients | `pytest-recording` `@pytest.mark.vcr` | pytest-recording 0.12 → 0.13 (2023) | Recording mode semantics stabilized; scrubbing API unchanged. |
| `RetailerCrawlerAdapter` keyed by dict | Same (will become ADAPTER_NAME ClassVar in Phase 3) | Phase 3 (not this phase) | Characterization tests key adapters by class, not name, this phase. |
| Hash-based OpenAPI snapshot | Formatted-JSON snapshot | (project convention D-27) | Diff-friendly. |

**Deprecated / outdated:**
- `python-jose` — pinned at 3.5.0; deprecated by maintainers; replaced by `PyJWT` in Phase 5 (AUTH-04). Not this phase.
- `@app.on_event()` — deprecated in FastAPI; project already uses `lifespan`. Phase 3 scope.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | vitest 3.2.4 emits a coverage-threshold-violated error message on non-zero exit (exact format not documented) | Pattern 2 | Low — exit code is what CI gates on; the message is cosmetic. Empirically confirmed in istanbul-derived output but not verified in this session. |
| A2 | The three broken migrations (`097024200e60`, `172d1c205fb3`, `6eae6b1393c5`) HAVE run on prod RDS | Pattern 4 / SAFE-08 approach | Medium — if they haven't run on prod, in-place repair is valid and simpler. **Planner must verify by querying `SELECT version_num FROM alembic_version` against prod RDS AND checking each historic revision appears before the current head in the migration graph.** If not yet applied, in-place repair. If applied, forward-only repair pair. |
| A3 | Google OAuth JWKS calls via `google-auth` library are VCR-recordable (vcrpy intercepts google.auth.transport.requests.Request() at the urllib3 layer) | Pattern 5 | Low — vcrpy natively supports urllib3 and requests; google-auth uses both. Confirmed via vcrpy docs + context7, not re-verified by running a live test in this session. |
| A4 | CarModPicker has NO custom coverage plugin in pyproject.toml or coveragerc | Pitfall 4 | None — verified via `grep "coverage\|\[tool" backend/pyproject.toml` returning only black/isort/mypy/bandit sections. |
| A5 | `backend/tests/` is the actual test path used at CI (despite pytest.ini saying `app/tests`) | Pitfall 2 | Low — backend-ci.yml runs `cd backend && python -m pytest ...` which falls back to CWD discovery. Confirmed by reading the workflow file. |
| A6 | `frontend/vitest.config.ts` does not yet have `coverage.thresholds` | Pattern 2 | None — file read in this session (25 lines total, no thresholds key). |
| A7 | `@vitest/coverage-v8` threshold enforcement is built into the v3.2.4 release (not gated behind a feature flag) | Pattern 2 | Low — feature is in vitest since 0.26; current project is on 3.2.4 which is far past that. |
| A8 | CONTEXT.md's `tier1_flaresolverr` label was a typo for `tier2_browser` (FlareSolverr) | Pitfall 7 / SAFE-07 | Medium — if the discusser actually meant `tier1_tls` instead of `tier2_browser`, adapter picks change. **Planner must confirm interpretation when authoring PLAN.md.** The dir layout verified by `ls` in this session is `tier0_http/ tier1_tls/ tier2_browser/`. |

## Open Questions

1. **Have migrations `097024200e60`, `172d1c205fb3`, `6eae6b1393c5` actually been applied to prod RDS?**
   - What we know: These are older migrations with 2025/early-2026 create-dates. prod has been running for months.
   - What's unclear: No prod access in this session to confirm `alembic_version` row.
   - Recommendation: PLAN.md SAFE-08 task action starts with "Run `SELECT version_num FROM alembic_version;` against prod (or staging snapshot); verify each of the three revision IDs is below the current head." Based on the answer, branch the repair approach (in-place edit vs. forward-only repair pair).

2. **Should the SAFE-07 tier picks be 2× `tier2_browser` + 1× `tier1_tls` (Pitfall 7 interpretation) OR 2× `tier1_tls` + 1× `tier2_browser`?**
   - What we know: CONTEXT.md D-20 says "2×`tier1_flaresolverr`" — a directory that does not exist.
   - What's unclear: FlareSolverr lives in `tier2_browser` in this codebase; "tier1" in the CONTEXT.md wording suggests the user thinks of FlareSolverr as tier 1. Either interpretation yields a valid test set.
   - Recommendation: PLAN.md annotates the interpretation ("mapping 'tier1_flaresolverr' → `tier2_browser` per actual directory layout") and picks 2 FlareSolverr adapters + 1 curl_cffi adapter. This matches D-20's intent: "most critical" (the ones that break most on real sites because of JS rendering) + "most stable" (curl_cffi — fewer moving parts).

3. **Is `tests/` the right test path in `pytest.ini` for a cleanup?**
   - What we know: Directive C-02 and verified file-system layout say yes.
   - What's unclear: Whether any CI runner or script relies on the current stale `app/tests` path.
   - Recommendation: Do NOT cleanup in Phase 1 (unrelated to safety nets). File as a minor tech-debt followup.

4. **Which two `tier2_browser` adapters are "most production-critical"?**
   - What we know: 11 adapters exist at that tier (aemelectronics, americanmuscle, apexwheels, dinan, ecstuning, fcpeuro, jegs, speedindustry, summitracing, tirerack + one via symlink).
   - What's unclear: No traffic data in this research.
   - Recommendation: PLAN.md SAFE-07 asks the user or checks admin dashboards for top-ranked adapters by ingested-part-count or by part_manufacturer-criticality. Falls back to the two that have the largest archived HTML footprint in the crawl bucket.

5. **Which `tier1_tls` adapter is "most stable"?**
   - What we know: 16 adapters at that tier. Recent work (per CONCERNS.md) fixed 6 tier0_http adapters; no tier1_tls fixes called out recently.
   - Recommendation: Pick one with no recent parse-failure fixes and active product catalog — `texasspeed` or `apr` are reasonable picks. PLAN.md to confirm.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | Backend CI; local dev | ✓ | — (enforced by CI `actions/setup-python@v6`) | — |
| Node 22 | Frontend CI; local dev | ✓ | — (enforced by CI `actions/setup-node@v6`) | — |
| `pytest-recording` | SAFE-06 | ✗ (not yet installed) | — | Add to `backend/requirements.txt`; no fallback needed, single-line change. |
| `pytest-cov` | SAFE-01 | ✓ | 6.2.1 | — |
| `@vitest/coverage-v8` | SAFE-03 | ✓ | 3.2.4 | — |
| Postgres (via `docker-compose up -d`) | SAFE-08 prep (introspecting constraint names locally) | ✓ (docker-compose.yml ships with the project) | Postgres 16 per CLAUDE.md | No fallback needed — Postgres is required to run the broken migration state and introspect. |
| `psql` CLI | SAFE-08 prep (inspecting `\d+ <table>`) | Assumed ✓ on developer machine | — | Use SQLAlchemy `Inspector.get_foreign_keys()` (Code Example 4) if `psql` unavailable. |
| GitHub Actions runner | All CI steps | ✓ | ubuntu-latest (per both workflow files) | — |

**Missing dependencies with no fallback:** None that block execution. pytest-recording is a `pip install -r requirements.txt` away.

**Missing dependencies with fallback:** None.

## Validation Architecture

Workflow `nyquist_validation: true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework (backend) | pytest 9.0.3 + pytest-xdist 3.8.0 + pytest-cov 6.2.1 (+ pytest-recording 0.13.4, added this phase) |
| Config file (backend) | `backend/pytest.ini` |
| Quick run command (backend) | `cd backend && pytest -n auto -x` (stops on first failure; ~8–15s for a single-module run) |
| Full suite command (backend) | `cd backend && pytest -n auto --cov=app --cov-report=term-missing` |
| Framework (frontend) | vitest 3.2.4 + @vitest/coverage-v8 3.2.4 |
| Config file (frontend) | `frontend/vitest.config.ts` |
| Quick run command (frontend) | `cd frontend && npm test -- --run` |
| Full suite command (frontend) | `cd frontend && npm run test:coverage` |
| Phase gate command | Both full-suite commands must pass; DROP-guard script must exit 0; `npx prettier --check` + `npm run lint` + `pyright` + `bandit` all pass. |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SAFE-01 | `--cov-fail-under` in pytest.ini addopts; CI fails at coverage < baseline | integration (meta-test on CI config) | `cd backend && pytest -n auto` exits non-zero when `app/` coverage drops below threshold (tested by transiently modifying pytest.ini to N+1 and asserting failure, then reverting) | ❌ Wave 0 — new pytest.ini line |
| SAFE-02 | `npm test -- --run --coverage` runs in frontend CI | unit (workflow-yaml check) | `grep -q 'npm test' .github/workflows/frontend-ci.yml` | ❌ Wave 0 — new workflow step |
| SAFE-03 | vitest thresholds enforced | unit | `cd frontend && npm test -- --run --coverage` — exits 1 if thresholds unmet | ❌ Wave 0 — new thresholds block |
| SAFE-04 | DROP-guard detects unannotated destructive ops | unit (self-test on check_migrations.py) | `cd backend && python scripts/check_migrations.py` on existing migrations must return 0 after migration-repair PR lands (SAFE-08); on a transient test fixture with a bare `op.drop_column(...)` it must return 1 | ❌ Wave 0 — new script |
| SAFE-05 | OpenAPI schema snapshot matches committed file | unit | `cd backend && pytest -n auto tests/test_openapi_snapshot.py -v` | ❌ Wave 0 — new test + snapshot |
| SAFE-06 | 7 auth happy-path flows pin current behavior | integration (VCR + TestClient + DB fixture) | `cd backend && pytest -n auto tests/test_auth_characterization.py -v` | ❌ Wave 0 — new test file + 7 cassettes |
| SAFE-07 | 5 crawler adapters pin current parse_product_page output | unit (pure function + fixture HTML) | `cd backend && pytest -n auto tests/crawlers/test_characterization_*.py -v` | ❌ Wave 0 — 5 new test files + 5 HTML + 5 expected.json |
| SAFE-08 | Three broken migrations have correct constraint names | integration (local Postgres) | `cd backend && alembic downgrade <broken_revision>^; alembic upgrade head` against docker-compose Postgres — must succeed (validates the repair is correct) | ❌ Wave 0 — repair migration(s) |
| SAFE-09 | Future autogenerate emits named constraints | integration (one-shot verification) | Add a dummy Column to a model; run `alembic revision --autogenerate -m "test"`; inspect generated file for `name='fk_...'` pattern; discard the migration. | ❌ Wave 0 — base_class.py change |
| SAFE-10 | Dependabot file parses + GitHub accepts it | manual-only (GitHub-side validation) | `yamllint .github/dependabot.yml` (syntax); GitHub's own schema check on PR merge | ❌ Wave 0 — new file |

### Sampling Rate

- **Per task commit:** `cd backend && pytest -n auto -x --no-cov` (skip coverage for speed; ~5–10s)
- **Per wave merge:** `cd backend && pytest -n auto --cov=app --cov-fail-under=<N>` + `cd frontend && npm run test:coverage` + `python backend/scripts/check_migrations.py` + `npx prettier --check` + `npm run lint`
- **Phase gate:** All of the above green + `.github/dependabot.yml` lints clean + PR title body includes the measured coverage baseline number.

### Wave 0 Gaps

Infrastructure not yet in place — must land in Wave 0 of Phase 1 plan:

- [ ] `backend/requirements.txt` — add `pytest-recording==0.13.4`
- [ ] `backend/scripts/check_migrations.py` — DROP-guard script (SAFE-04)
- [ ] `backend/tests/fixtures/openapi_snapshot.json` — initial snapshot (SAFE-05)
- [ ] `backend/tests/test_openapi_snapshot.py` — snapshot test (SAFE-05)
- [ ] `backend/tests/cassettes/auth/*.yaml` — 7 VCR cassettes (SAFE-06)
- [ ] `backend/tests/test_auth_characterization.py` — 7 tests (SAFE-06)
- [ ] `backend/tests/crawlers/fixtures/<adapter>/product.html` × 5 (SAFE-07)
- [ ] `backend/tests/crawlers/fixtures/<adapter>/expected.json` × 5 (SAFE-07)
- [ ] `backend/tests/crawlers/test_characterization_<adapter>.py` × 5 (SAFE-07)
- [ ] `backend/app/db/base_class.py` — modified (SAFE-09)
- [ ] `backend/alembic/versions/YYYYMMDD_repair_drop_constraint_none_refs.py` — new, OR in-place edits to three existing files (SAFE-08)
- [ ] `frontend/vitest.config.ts` — modified (SAFE-03)
- [ ] `.github/workflows/backend-ci.yml` — modified (SAFE-04 step)
- [ ] `.github/workflows/frontend-ci.yml` — modified (SAFE-02 step)
- [ ] `.github/dependabot.yml` — new (SAFE-10)
- [ ] `backend/pytest.ini` — modified (SAFE-01 `--cov-fail-under`)

## Security Domain

Phase 1 is infrastructure. Most ASVS categories do not apply because no new user-facing auth surface is added. The one security-relevant item is secret handling in VCR cassettes (SAFE-06).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | indirect | No auth code changes; characterization tests PIN existing behavior. Current stack (JWT HS256 + bcrypt + optional TOTP + WebAuthn + Google OIDC) is already in place per CLAUDE.md. |
| V3 Session Management | indirect | Same — existing JWT expiry (configurable 15min–7d) continues; characterization tests include login which uses it. |
| V4 Access Control | no | No auth-dependency changes. |
| V5 Input Validation | no | No new endpoints. |
| V6 Cryptography | no | No new crypto code; WebAuthn library boundary is stubbed in tests only. |
| V7 Data Protection (secrets in test fixtures) | **yes** | VCR cassette scrubbing via `filter_headers` / `filter_post_data_parameters` / `filter_query_parameters`. |
| V10 Malicious Code | indirect | `bandit -ll` already gates in backend-ci; no change this phase. |
| V14 Configuration | yes | Dependabot (SAFE-10) is a hardening item — brings dependency CVE response time down from "ad-hoc" to "weekly-at-most". |

### Known Threat Patterns for Python+TypeScript CI stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secrets committed in VCR cassettes (Google OAuth refresh tokens, JWT bearers) | Information Disclosure | `vcr_config` fixture with `filter_headers=["authorization", "cookie", "set-cookie"]` + `filter_post_data_parameters=["client_secret", "code", "refresh_token"]` — see Code Example 6. |
| Dependency supply-chain (malicious transitive dep in pip/npm) | Tampering | `pip-audit` (already in backend-ci) + `npm audit` (already in frontend-ci) + Dependabot weekly surfacing of new CVEs (SAFE-10). |
| CI secret leakage via workflow logs | Information Disclosure | All CI steps already use `$SECRET_KEY: test-secret-key-for-ci` and similar non-prod values. No change this phase. |
| Developer's local cassette contains real production token (if developer records against prod) | Information Disclosure | Documentation in test module docstring: "Record against a dedicated test Google account, never against your personal or admin account." |

**Planner note:** Add a `.gitignore`-style guard? No — cassettes are COMMITTED (D-17), and scrubbing is the mechanism. Audit the first recording by hand after it's produced; the reviewer checks that no Authorization header or Set-Cookie value leaked.

## Sources

### Primary (HIGH confidence)

- `context7://websites/sqlalchemy_en_20` — MetaData naming_convention, declarative_base integration (fetched 2026-04-21)
- `context7://websites/alembic_sqlalchemy` — autogenerate behavior, importance of naming constraints
- `context7://websites/vitest_dev` — coverage.thresholds config shape, v8 provider, include/exclude semantics
- `context7://kiwicom/pytest-recording` — @pytest.mark.vcr, vcr_config fixture, filter_headers, record_mode
- `context7://kevin1024/vcrpy` — filter_headers, filter_post_data_parameters, filter_query_parameters, before_record_response
- `context7://duo-labs/py_webauthn` — library surface: verify_registration_response, generate_registration_options
- `https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file` — schema v2 shape
- `https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/optimizing-pr-creation-version-updates` — groups vs ignore, Example 3 (implicit major PRs)
- `https://vitest.dev/config/coverage` — thresholds field shape (lines/functions/branches/statements/perFile/autoUpdate/100 shorthand)
- `https://pytest-cov.readthedocs.io/en/latest/xdist.html` — pytest-xdist integration (auto combine)

### Secondary (MEDIUM confidence)

- `https://github.com/pytest-dev/pytest-cov/issues/642` — pytest-cov + xdist interactions (only relevant with custom coverage plugins — not our case)
- WebSearch result corpus on pytest-recording + xdist (2026-04 results): no blocking issues surfaced

### Tertiary (LOW confidence)

- Vitest's exact error message format when a threshold is unmet — not documented in official config page; inferred from istanbul-derived output. Planner should verify empirically during SAFE-03 implementation by deliberately breaking a threshold. (A1 in Assumptions Log.)

### Codebase-verified (by direct file read in this session)

- `backend/pytest.ini` (current addopts)
- `backend/app/db/base_class.py` (3 lines, plain `declarative_base()`)
- `backend/app/db/base.py` (imports all models into Base.metadata)
- `backend/alembic/env.py` (target_metadata = Base.metadata)
- `backend/alembic/versions/097024200e60_add_canonical_part_id_to_parts.py` (confirmed broken drop_constraint(None))
- `backend/alembic/versions/172d1c205fb3_add_build_list_phases.py` (confirmed broken drop_constraint(None))
- `backend/alembic/versions/6eae6b1393c5_add_brand_model.py` (confirmed broken drop_constraint(None))
- `backend/tests/conftest.py` (fixture topology, env setup ordering)
- `backend/app/crawlers/base.py` (ScrapedPayload shape)
- `backend/app/crawlers/adapters/base.py` (RetailerCrawlerAdapter contract, FetcherTier literal `"http" | "tls" | "browser"`)
- `backend/app/crawlers/adapters/__init__.py` (adapter registry, confirms tier directories)
- `backend/app/crawlers/adapters/tier0_http/briantooleyracing.py` (parse_product_page signature example)
- `backend/app/api/endpoints/auth.py` lines 25–33, 549, 589, 643, 697 (webauthn library imports + 4 verification call sites — confirms stub boundary)
- `backend/app/api/utils/google_oauth.py` (google_id_token.verify_oauth2_token — confirms VCR boundary)
- `backend/requirements.txt` (exact pinned versions)
- `frontend/package.json` (frontend pinned versions)
- `frontend/vitest.config.ts` (current config — no thresholds block)
- `.github/workflows/backend-ci.yml` (step list; `Run tests with coverage` is last step)
- `.github/workflows/frontend-ci.yml` (step list; `Build application` is last step — test step inserts before it per D-04)
- `.github/workflows/chrome-extension-ci.yml` (for completeness — extension ecosystem covered by npm in Dependabot)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified via installed package and/or PyPI/npm registry in this session
- Architecture: HIGH — all file paths, workflow step order, conftest hooks, and adapter contracts verified by direct read
- Pitfalls: HIGH (7 of 8) — most verified against official docs; one (Pitfall 7, CONTEXT.md tier naming) is a direct filesystem contradiction
- Code examples: HIGH — all examples compiled against real class/method signatures read from the codebase
- Security domain: HIGH for V7 (cassette scrubbing is a well-known mitigation); MEDIUM for other categories (phase is infra-only)

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (30 days — stable infrastructure stack; fastest-moving element is vitest which has monthly-ish minor releases)

## RESEARCH COMPLETE
