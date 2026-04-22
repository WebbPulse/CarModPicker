# Pitfalls Research

**Domain:** Tech-debt audit + refactor milestone — brownfield FastAPI + React + crawler + Chrome extension
**Researched:** 2026-04-21
**Confidence:** HIGH (grounded in the actual codebase; all claims traceable to specific files)

---

## Critical Pitfalls

### Pitfall 1: Refactor Death Spiral — Enthusiasm Without Momentum Gates

**Severity:** HIGH

**What goes wrong:**
The milestone starts as a focused cleanup. Three weeks in, eight things are half-done: `admin.py` split started but not finished, auth refactor broke something in the TOTP flow, N+1 fix works locally but the query count assertion isn't in CI, and the car-data lazy-load is half-migrated. The 80%-done state is worse than the starting state — the original code at least worked. Momentum collapses.

**Why it happens:**
Debt work has no visible user-facing output. There's no reward loop. Every phase touches fragile code, which means each one can surface unexpected bugs that feel like "scope creep" but are actually just debt being honest. Solo developers with AI-assisted coding move fast in short bursts but can lose thread continuity across sessions.

**How to avoid:**
- Each phase must have a concrete, binary done-state: "CI is green, old code is deleted, coverage didn't drop." No "mostly done."
- Enforce a "kill the old code before calling it done" rule. If `admin.py` is being split, the old monolith must be deleted, not left beside the new files.
- Commit after every logical sub-step. AI sessions lose context; a commit is the handoff artifact.
- Define scope ruthlessly at phase start. If a phase is "split admin.py," it is NOT "also refactor the job service it calls."

**Warning signs:**
- More than one file has both old and new versions simultaneously for more than a single work session
- Git log shows many small commits on different files with no clear "done" commit
- Coverage report shows the same module appearing in uncovered lines across multiple sessions

**Phase to address:**
Every phase — enforce these constraints in the phase definition, not as an afterthought. Especially critical for: Auth refactor (Area 1), Admin.py split (Area 8), Crawler hardening (Area 2).

---

### Pitfall 2: Double-Maintenance Trap — Old and New Code Left in Place

**Severity:** HIGH

**What goes wrong:**
`admin.py` gets split into `admin_jobs.py`, `admin_crawlers.py`, `admin_stats.py`. But the original `admin.py` stays registered in `EndpointRegistry` as a safety net "until we're sure the new ones work." A week later both are running. Bugs get fixed in one place, not the other. A month later nobody knows which version is authoritative.

In this codebase specifically: `adapters/__init__.py` currently has 114 manually-registered imports. During auto-discovery refactor, there's a real risk of running both the old manual registry and the new scan-based one simultaneously.

**Why it happens:**
Fear of breaking prod. Absence of a clear deletion checkpoint.

**How to avoid:**
- Deletion is part of the definition of done. If you haven't deleted the old code, the phase isn't closed.
- For `admin.py` split: `EndpointRegistry` registration of old `admin` router must be removed in the same commit that adds the new routers. No overlap window.
- For adapter auto-discovery: implement the new discovery mechanism, validate it produces the same set as the manual registry, then delete the manual imports list entirely. Use a test that asserts the two sets are identical before the cutover.
- Use git to enforce: the PR that adds new code must also delete old code.

**Warning signs:**
- Two files doing the same job exist simultaneously
- `from app.api.endpoints import admin` still in `main.py` after the split
- Both ADAPTER_REGISTRY and a new auto-discovery mechanism are loaded

**Phase to address:**
Area 8 (admin.py split), Area 2 (crawler adapter auto-discovery)

---

### Pitfall 3: Alembic Autogen Missing Unnamed Constraints — Silent Prod Failure

**Severity:** HIGH

**What goes wrong:**
`alembic revision --autogenerate` produces a migration that looks correct locally, runs against SQLite in CI (which is more permissive), passes CI, and then fails on prod RDS PostgreSQL 16 because a constraint drop references `None` (unnamed constraint). PostgreSQL requires explicit constraint names for `op.drop_constraint()`. SQLite ignores it entirely.

This has already happened: three migrations in the history contain `op.drop_constraint(None, ...)`:
- `097024200e60_add_canonical_part_id_to_parts.py:33`
- `172d1c205fb3_add_build_list_phases.py:45`
- `6eae6b1393c5_add_brand_model.py:48`

These are latent prod migration failures waiting for someone to run `downgrade`.

**Why it happens:**
Autogenerate doesn't always know the constraint name on SQLite-generated schemas. The developer sees the migration file, trusts the tooling, and doesn't spot `None` in the constraint name position.

**How to avoid:**
- Add a pre-commit or CI check: `grep -r "drop_constraint(None" alembic/versions/` fails the build if it finds matches.
- Before any migration is merged, run `alembic downgrade -1 && alembic upgrade head` against a real Postgres instance (local Docker). Not SQLite.
- Fix the three existing `drop_constraint(None, ...)` instances before any new schema work touches those tables.
- Configure `alembic.ini` with `naming_convention` to force all constraints to be named from the start. This is the correct long-term fix.

**Warning signs:**
- Migration file contains `drop_constraint(None, ...)` anywhere
- `alembic downgrade` was never tested locally (only `upgrade head`)
- CI uses only SQLite but prod is Postgres (this codebase's current state — SQLite tests don't catch this)

**Phase to address:**
Area 4 (DB / migrations / perf pass) — fix the existing three, add naming_convention, add CI grep check.

---

### Pitfall 4: SQLite / PostgreSQL Feature Divergence — Tests Green, Prod Broken

**Severity:** HIGH

**What goes wrong:**
Tests use SQLite in-memory. PostgreSQL 16 has features and constraints SQLite doesn't: strict foreign key enforcement by default, real enum types, generated columns, check constraints with names, upsert behavior differences, `ON CONFLICT DO UPDATE` syntax. A refactor that touches parts deduplication (canonical part linking, `pg_insert` upsert) or adds Postgres-specific constructs will pass CI and silently fail or behave differently in prod.

Specifically: `runner.py` already uses `from sqlalchemy.dialects.postgresql import insert as pg_insert`. This import will fail if ever run in a SQLite test context. The test suite currently avoids crawler ingestion paths — that's the only reason this hasn't broken CI.

**Why it happens:**
The SQLite-in-CI decision was made for speed and simplicity (correct tradeoff). The risk is that the test boundary is implicit, not explicit. Developers adding new tests don't know which code paths are Postgres-only.

**How to avoid:**
- Document explicitly which modules are Postgres-only (crawler ingestion, `pg_insert` usage) and mark them with `pytest.mark.skip` or separate them into integration tests that run against a real Postgres Docker instance.
- Add a `conftest.py` check: if `pg_insert` is imported in non-crawler test code, fail with a clear error.
- For the parts dedup consolidation (Area 5): any new upsert/merge logic must be tested against Postgres, not just SQLite. Spin up a local Postgres Docker for these specific tests.
- The existing `check_db_ready()` and `get_db()` session behavior should be validated against Postgres connection pool exhaustion scenarios, not just SQLite.

**Warning signs:**
- New test imports `from sqlalchemy.dialects.postgresql import ...`
- A refactor adds `ON CONFLICT` or `RETURNING` clauses that are Postgres-specific
- Coverage for parts ingestion path is low but tests are "passing"

**Phase to address:**
Area 4 (DB / migrations / perf), Area 5 (parts dedup consolidation)

---

### Pitfall 5: Breaking FastAPI `Depends()` During Router Split — Silent 422s or Auth Bypass

**Severity:** HIGH

**What goes wrong:**
When splitting `admin.py` into sub-routers, each new router must have its own `Depends(get_current_admin_user)` or `Depends(get_current_superuser)` guards. If a route handler is moved to a new file but its dependency is inherited from the old router's include prefix rather than declared on the route itself, the endpoint either loses auth protection (if the router prefix dependency is stripped) or silently 422s on auth parameters (if the dependency is renamed or shadowed).

FastAPI dependency injection scope is a frequent source of subtle bugs during router splits. A missing `Depends()` on an admin endpoint is a security regression, not just a bug.

**Why it happens:**
Developers assume router-level `dependencies=` propagate correctly to all routes. They do — but only if the router is included correctly. During a split, the registration path changes, and assumptions about which `APIRouter` carries which dependencies break.

**How to avoid:**
- Every route in the new admin sub-routers must declare its auth dependency explicitly on the route decorator, not solely at router-include time.
- Write an integration test for each new admin sub-router that verifies: (1) an unauthenticated request returns 401, (2) a regular user returns 403, (3) an admin user succeeds.
- Use the existing `test_admin_user` and `test_superuser_user` fixtures — they exist for exactly this purpose.
- After the split, grep for any admin route that lacks `current_user: DBUser = Depends(get_current_admin_user)` or equivalent.

**Warning signs:**
- A new admin route returns 200 for an unauthenticated request in tests
- `Depends()` appears only in `app.include_router(admin_router, dependencies=[...])` but not on individual route handlers
- CI passes but no test asserts auth behavior for the new routes

**Phase to address:**
Area 8 (admin.py split), Area 1 (auth refactor)

---

### Pitfall 6: N+1 Reintroduction During Refactor

**Severity:** HIGH

**What goes wrong:**
The known N+1 in `build_logs.py:119` gets fixed with `joinedload`. Six months later a refactor of the build-log post listing (to add a new field or paginate differently) iterates over posts again and introduces a new loop query. Without a query-count assertion in the test suite, CI stays green while prod performance silently regresses.

More broadly: the `BaseCRUDService` abstraction means developers don't always see the ORM queries they're generating. A refactor that changes how related data is fetched (e.g., accessing `post.author` inside a loop after a session refactor) can introduce N+1 without any obvious code change.

**Why it happens:**
ORM makes queries invisible. SQLAlchemy's default lazy loading means `post.author` inside a loop fires a query per iteration — no warning, no error, just slow code.

**How to avoid:**
- When fixing the existing N+1, add a `sqlalchemy-query-counter` or equivalent assertion: `assert query_count == 1` (or whatever the expected fixed count is). This becomes the regression guard.
- For any endpoint that returns a list of objects with relationships, use `selectinload` or `joinedload` explicitly in the service layer, never rely on lazy-load defaults.
- Models currently use `lazy="selectin"` for only one relationship (`part.py:65`). Audit all other `relationship()` declarations during Area 4 and set explicit loading strategies.
- Run `SQLALCHEMY_WARN_20=1` locally during development to surface lazy-load warnings.

**Warning signs:**
- An endpoint's response time grows proportionally with the list size
- No query count assertion exists for the fixed N+1 endpoint
- A new field is added to a list endpoint without also checking how it's loaded

**Phase to address:**
Area 4 (DB / migrations / perf pass) for the fix; Area 7 (test coverage) for the regression guard.

---

### Pitfall 7: Crawler Adapter Discovery Breakage — Silent Adapter Dropout

**Severity:** HIGH

**What goes wrong:**
The current `adapters/__init__.py` manually registers 114 adapters with explicit imports. When auto-discovery is implemented (Area 2), a new scan-based registry replaces the manual list. If any adapter has an import error (e.g., its dependencies changed, a circular import was introduced), the new auto-discovery silently skips it. With the manual registry, a broken import crashes startup loudly. With auto-discovery, a broken import means that adapter runs zero pages and nobody notices.

**Why it happens:**
Auto-discovery improves ergonomics (no manual registration) but trades import-time failure for silent runtime dropout. The failure mode is invisible — the crawler runs, ingests from other adapters, and the broken adapter is simply absent from results.

**How to avoid:**
- Auto-discovery must validate imports, not just scan for files. Catch `ImportError` per adapter and emit a startup ERROR log (not just a warning) with the full traceback. Fail the entire crawler run if any adapter fails to load in strict mode.
- Add a CI test that asserts `len(ADAPTER_REGISTRY) == expected_count`. If an adapter silently drops out, the count assertion fails.
- During the transition period: run old and new registry in parallel, assert they produce the same set of adapter names, then delete the old one. Don't delete first.
- Keep the adapter validation test (asserting count) as a permanent CI gate.

**Warning signs:**
- Adapter count in `ADAPTER_REGISTRY` drops between deploys without a corresponding deletion commit
- Crawl job reports show fewer adapters run than expected
- A new adapter file exists in the directory but doesn't appear in job reports

**Phase to address:**
Area 2 (crawler system hardening)

---

### Pitfall 8: Auth Refactor Breaking 2FA / WebAuthn / OAuth Flows — Regression in Non-Happy-Path

**Severity:** HIGH

**What goes wrong:**
`auth.py` is 1,195 lines covering email/password, TOTP 2FA, WebAuthn passkeys, Google OAuth, and JWT session management — all accreted together. During the split, it's easy to correctly extract the happy path but break a non-happy-path: TOTP failure handling, the OAuth account-link flow for existing users, the WebAuthn assertion verification, or the redirect chain after email verification. These flows are rarely exercised in CI because they're hard to test (real TOTP secrets, WebAuthn ceremony, OAuth redirects).

**Why it happens:**
Non-happy-path auth flows are undertested. The existing test suite covers `test_login`, but probably not `test_login_with_totp_then_totp_secret_rotated` or `test_oauth_link_existing_account_already_has_oauth`. When you move code without tests, you can't know what broke.

**How to avoid:**
- Before splitting `auth.py`, write characterization tests for every flow that currently works: TOTP enable/disable, TOTP verify-fail, WebAuthn enroll, WebAuthn assert, Google OAuth new account, Google OAuth link existing account, email verify success, email verify expired token, JWT expiry with configurable TTL. These tests don't need to be perfect — they just need to exercise the code paths and assert the HTTP status codes.
- Split is then safe because tests will catch regressions.
- Never delete code from `auth.py` until the corresponding test passes in the new module.

**Warning signs:**
- Auth refactor PR has no new test files
- Coverage of `auth.py` drops after the split (it should stay the same or increase)
- The TOTP or WebAuthn code paths have zero test coverage before the refactor starts

**Phase to address:**
Area 1 (auth refactor) — tests first, split second.

---

### Pitfall 9: Chrome Extension API Schema Drift — Silent Breaking Change

**Severity:** HIGH

**What goes wrong:**
A backend refactor changes a response schema (renames a field, adds a required field, changes a type) in an endpoint the Chrome extension calls. The extension is not updated. The extension either silently breaks (users can't submit parts) or continues working with stale data. The extension is not in CI for backend changes — CI only triggers on `backend/**` or `frontend/**` path changes, not `chrome-extension/**`. There is no contract test between extension and backend.

This is especially likely during Area 5 (parts dedup consolidation), which touches the parts schema, and Area 1 (auth refactor), which touches auth endpoints the extension uses for its token handoff.

**Why it happens:**
The extension is treated as a separate project. Backend developers don't have a mental model of which API endpoints the extension calls.

**How to avoid:**
- Create and maintain a `chrome-extension/API_CONTRACT.md` that lists every backend endpoint the extension calls, with expected request/response shape.
- When a backend endpoint changes its schema, the PR must include an update to that contract doc and a corresponding extension change.
- Add the extension's endpoint list to a CI check: if `backend/app/api/schemas/parts.py` changes, the CI step warns to verify the extension contract.
- For auth: the extension's `background.ts:156` 10-minute nonce TTL is a known issue — fixing it is part of Area 1.

**Warning signs:**
- A parts schema field is renamed without checking `chrome-extension/src/`
- The extension popup shows errors users don't report (because traffic is low)
- `chrome-extension/API_CONTRACT.md` doesn't exist (currently the case)

**Phase to address:**
Area 1 (auth refactor), Area 5 (parts dedup), Area 6 (frontend cleanup — treat extension as a consumer alongside the web frontend)

---

### Pitfall 10: Refactoring Without a Coverage Baseline — Silent Regression

**Severity:** HIGH

**What goes wrong:**
CI runs tests with coverage, but there's no coverage threshold enforced. Coverage can drop from 70% to 50% across this milestone if refactored code moves into untested paths. CI stays green. Nobody notices until a production bug surfaces in code that "should have been tested."

The frontend CI is worse: tests are not run in CI at all (`frontend-ci.yml` runs lint, type-check, and build — but not `npm test`). Frontend coverage is completely untracked in CI.

**Why it happens:**
Coverage thresholds weren't set initially. Adding them retroactively requires knowing the current baseline first.

**How to avoid:**
- Immediately before the milestone starts: run `pytest --cov=app --cov-report=term-missing` and record the current coverage number as a floor. Configure `pytest.ini` with `--cov-fail-under=<baseline>`.
- Add `npm test` to `frontend-ci.yml`. This should have been there already.
- Coverage must not decrease phase-over-phase. If a refactor drops coverage, either add tests to the refactored code or explicitly justify the drop in the PR description.
- Track coverage as a metric, not just a pass/fail: look at per-module coverage for the modules being changed.

**Warning signs:**
- `pytest.ini` has no `--cov-fail-under` configured (currently the case)
- Frontend tests not in CI (currently the case)
- A PR deletes a test file because "the code was refactored"

**Phase to address:**
Area 7 (test coverage & CI gates) — this should be the first phase or run concurrently with every other phase.

---

## Moderate Pitfalls

### Pitfall 11: `car_generations_data.py` Load Strategy — Startup Latency Regression

**Severity:** MEDIUM

**What goes wrong:**
If `car_generations_data.py` (8,412 lines) is moved to lazy-load (correct fix, per CONCERNS.md) but the refactor is done incorrectly, the lazy-load fires on every import of `car_inference.py` instead of once per process. With `uvicorn --reload` during development, this hits on every reload. In production, App Runner cold starts become noticeably slower.

**How to avoid:**
- Use a module-level singleton with `functools.lru_cache` or a `_cache = None` guard pattern. The data loads once, stays in memory.
- Test the fix with a simple `python -c "import time; t=time.time(); from app.core.car_inference import infer_car_generations; print(time.time()-t)"` before and after.
- Do not move the data to a database query path unless you add an in-process cache — a DB query on every car inference call at crawler scale would be far worse than the current eager import.

**Warning signs:**
- `uvicorn --reload` takes noticeably longer after the refactor
- Crawler initialization time increases

**Phase to address:**
Area 8 (general code-quality sweep)

---

### Pitfall 12: Rate-Limit Circuit Breaker Masking Real Bugs

**Severity:** MEDIUM

**What goes wrong:**
`RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD = 5` in `runner.py:70`. When a retailer's site is broken (not rate-limiting, but returning 503 due to a broken CDN or DNS issue), the circuit breaker fires after 5 retries. The log says "circuit breaker tripped" but the real cause is a parse failure or a structural site change, not rate limiting. Reducing the threshold (correct for rate-limit cases) makes this ambiguity worse.

**How to avoid:**
- Distinguish circuit breaker cause before tripping: log the specific HTTP status codes seen (429 vs. 503 vs. connection timeout). The circuit breaker message should include "5× 429 (rate limited)" vs. "5× 503 (upstream error)" — these require different follow-up actions.
- When hardening the crawler (Area 2), do not just reduce the threshold; fix the signal quality so operators know why it tripped.

**Warning signs:**
- Circuit breaker logs say "rate limited" but manual visit to the retailer site shows it's up
- Multiple adapters trip the circuit breaker on the same day (systemic issue, not rate limiting)

**Phase to address:**
Area 2 (crawler hardening), Area 3 (observability)

---

### Pitfall 13: ThreadPoolExecutor Sizing — Connection Pool Exhaustion During Parallelization

**Severity:** MEDIUM

**What goes wrong:**
`runner.py` currently runs adapters serially. CONCERNS.md flags parallelizing adapter execution as a scaling improvement. If parallelization is implemented naively — e.g., `ThreadPoolExecutor(max_workers=50)` — and each worker holds a `SessionLocal` for its entire run, 50 workers × 1 session = 50 connections. The pool is `DB_POOL_SIZE=25` + `DB_MAX_OVERFLOW=75` = 100 max. This looks fine until you add API traffic reserve (`API_CONNECTION_RESERVE=20`) and realize a full parallel crawl of 114 adapters would exceed the pool.

**How to avoid:**
- The existing code in `session.py` already exports `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, and `API_CONNECTION_RESERVE` for exactly this reason. The crawler runner should compute max parallel workers as `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE`, not hardcode a number.
- Test connection pool exhaustion locally with `max_workers = pool_max + 1` and verify it errors cleanly rather than deadlocking.
- Add a startup log: "Crawler will use N parallel workers (pool capacity: X, API reserve: Y)."

**Warning signs:**
- `QueuePool limit of size X overflow Y reached` in crawler logs
- API endpoints start returning 503 during crawl runs
- Crawler workers hang indefinitely (they're waiting for a connection that never becomes available)

**Phase to address:**
Area 2 (crawler hardening)

---

### Pitfall 14: Context Re-renders Cascading — Frontend Performance Regression During Cleanup

**Severity:** MEDIUM

**What goes wrong:**
The frontend has two contexts: `AuthContext` and `AppSettingsContext`. If the frontend cleanup (Area 6) moves state out of local component state into context, or restructures how context consumers are organized, any state change in `AuthContext` will re-render every component that calls `useAuth()`. This is the canonical React context anti-pattern: a broad context with frequently-changing state causes full re-renders on every change.

At low traffic this is invisible. With React 19's concurrent features, it may produce subtle rendering order issues.

**How to avoid:**
- Do not add new state to existing contexts during cleanup. If new state is needed, create a narrowly-scoped context or use `useState` + prop drilling for localized state.
- After any restructure involving context, use React DevTools Profiler to check which components re-render on auth state changes. If more than 3-4 top-level components re-render on a token refresh, the context is too broad.
- Split `AuthContext` if it currently holds both auth state and user-preference state — these have different update frequencies.

**Warning signs:**
- React DevTools shows "why did this render?" fires on unrelated components after an auth state change
- Page transitions feel sluggish after context restructure
- `useAuth()` is called in deeply-nested leaf components that don't need auth state

**Phase to address:**
Area 6 (frontend structure cleanup)

---

### Pitfall 15: Vite HMR vs. Production Build Divergence

**Severity:** MEDIUM

**What goes wrong:**
During frontend cleanup (Area 6), a component or module works in `npm run dev` (Vite HMR) but fails in `npm run build` (production ESM bundle). Common causes: circular imports that HMR tolerates but bundler tree-shaking rejects, dynamic imports that work with dev server but produce wrong chunk splits in prod, or environment variables accessed at module scope that differ between dev and prod.

The `Api.ts` file is 1,519 lines — a monolith. If it's split during cleanup, the split introduces import order assumptions that HMR masks.

**How to avoid:**
- Run `npm run build` in CI (it already does this — good). Do not merge any frontend cleanup PR without a passing build step.
- If `Api.ts` is split: run `npm run build && npm run preview` and verify the app loads correctly in the production bundle before merging.
- Check for circular imports with `madge --circular src/` before and after any service-layer restructure.

**Warning signs:**
- `npm run dev` works but `npm run build` throws a type error or bundler error
- The production deploy shows a blank page or module not found error
- `madge` finds new circular dependencies after a refactor

**Phase to address:**
Area 6 (frontend structure cleanup)

---

### Pitfall 16: Archive-Replay Drift — Stale HTML Causing False "Fixed" Status

**Severity:** MEDIUM

**What goes wrong:**
The self-archive bucket lets the crawler re-run against stored HTML. During crawler hardening (Area 2), a developer "fixes" a parse failure by tuning the adapter against archived HTML, runs it against the archive, sees green results, and marks the adapter as fixed. But the archived HTML is weeks old. The live retailer page has since changed its DOM again. The fix looks complete but breaks on the next real crawl run.

**Why it happens:**
Archive-replay is fast and offline — it's a natural shortcut. But the archive timestamp is invisible unless you explicitly check it.

**How to avoid:**
- When using archive-replay to fix an adapter, always also run against one live URL from that retailer as a sanity check before closing the fix.
- Add a `--max-archive-age-days` flag to the crawler CLI that rejects archive entries older than N days when used for validation.
- Log the archive entry's crawl date alongside the parse result: "Parsed successfully from archive (crawled: 2026-03-01)."

**Warning signs:**
- An adapter is marked "fixed" but the next real crawl shows the same parse failures
- Archive entries being used for testing are more than 30 days old

**Phase to address:**
Area 2 (crawler hardening)

---

### Pitfall 17: Migration Runs Without Downgrade Test — Unrecoverable Schema State

**Severity:** MEDIUM

**What goes wrong:**
A migration runs `alembic upgrade head` on prod. Something in application code is wrong, and the team needs to roll back. `alembic downgrade -1` runs and fails because the `downgrade()` function wasn't tested, uses `op.drop_constraint(None, ...)` (already present in 3 migrations), or drops a column that application code still references. The database is now in an inconsistent state. Recovery requires manual SQL surgery.

**How to avoid:**
- Every migration must have a tested `downgrade()` function. Test it locally: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`. If downgrade fails, fix it before merging.
- For `op.drop_constraint(None, ...)` — this is a known issue in the codebase. Fix all three instances during Area 4 before adding any new migrations.
- Add `naming_convention` to SQLAlchemy `MetaData` so autogenerate always produces named constraints.

**Warning signs:**
- A migration's `downgrade()` function is a pass or a TODO comment
- `op.drop_constraint(None, ...)` appears in any new migration
- No test of `downgrade` exists in any migration in the history

**Phase to address:**
Area 4 (DB / migrations / perf pass)

---

## Minor Pitfalls

### Pitfall 18: Error Boundary Gaps After Component Split

**Severity:** LOW

**What goes wrong:**
The frontend cleanup splits large page components into smaller sub-components. The original page had no error boundary (there are no error boundaries currently — E2E tests don't exist per TESTING.md). A sub-component that previously was part of a large render tree now throws an unhandled error that bubbles up to the root, showing a blank page instead of a degraded-but-functional UI.

**How to avoid:**
- Any new sub-component that makes an API call should be wrapped in a local error boundary.
- Add a top-level `ErrorBoundary` around each route's lazy-loaded page component in `App.tsx` if one doesn't already exist.
- When in doubt: if a component can throw (async data, missing data, etc.), wrap it.

**Phase to address:**
Area 6 (frontend structure cleanup)

---

### Pitfall 19: `__tablename__` Conflicts After Model File Split

**Severity:** LOW

**What goes wrong:**
If `admin.py`'s embedded logic causes someone to accidentally define a new model class with a duplicate `__tablename__`, SQLAlchemy will raise a mapper conflict at import time. This is loud (import error), not silent, but can block the entire app from starting.

Currently all 26 `__tablename__` values appear unique (verified in this analysis). The risk is low but increases if model files are restructured.

**How to avoid:**
- Add a CI test that imports all models and asserts no duplicate `__tablename__` values exist.
- This is a 5-line test and a permanent guard.

**Phase to address:**
Area 8 (code quality sweep)

---

### Pitfall 20: Build Log Auto-Creation Failure on First Access

**Severity:** LOW

**What goes wrong:**
`build_logs.py:87–98` auto-creates a `DBBuildLog` if missing when a build list is first accessed. This mid-request creation is not wrapped in error handling (per CONCERNS.md). A DB error during auto-creation returns an inconsistent state to the caller. During any refactor of the build-logs endpoint, this fragile path can become worse — especially if the refactor changes session scope or transaction boundaries.

**How to avoid:**
- Fix the root cause during Area 8: create the `DBBuildLog` eagerly when the `BuildList` is created, not lazily on first access.
- If the lazy approach stays, wrap the auto-creation in a proper try/except with a 500 response.
- Add a test for the auto-create failure path before any refactor touches this file.

**Phase to address:**
Area 8 (code quality sweep), also relevant to Area 4 if transaction refactoring touches build logs

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep old code alongside new "just in case" | Feels safe, easy to revert | Double-maintenance, confusion about which is authoritative, never get deleted | Never — use git revert instead |
| Skip downgrade() in migration | Saves 10 minutes | Unrecoverable schema state if rollback needed | Never |
| Trust SQLite tests for Postgres-specific code | CI is fast and simple | Prod failures that passed CI | Acceptable only for code that never uses Postgres-specific SQL |
| Run adapter fixes only against archive | Offline, fast iteration | Archive drift — fix looks done but breaks on live pages | Acceptable for initial diagnosis; never for final validation |
| Not deleting dead code | "Might need it later" | Maintenance burden, confusion, prevents safe refactoring | Never — delete and use git history |
| No coverage threshold | Avoids CI friction | Coverage silently erodes across the milestone | Never for a refactor milestone |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Alembic + PostgreSQL | Using `op.drop_constraint(None, ...)` — works in SQLite, fails on Postgres | Always name constraints; use `naming_convention` in MetaData; test downgrade on real Postgres |
| SQLAlchemy relationships | Accessing `.author` inside a list loop (lazy load fires per item) | Set explicit `lazy="selectin"` or use `joinedload`/`selectinload` in query; assert query count in tests |
| FastAPI `Depends()` during router split | Assuming router-level `dependencies=` propagates; it does, but only if include is correct | Declare auth dependency on each route explicitly; test 401/403 for every admin route |
| Chrome extension + backend schema change | Renaming a response field breaks extension silently | Maintain API_CONTRACT.md; check extension imports when backend schemas change |
| Crawler adapter + auto-discovery | Import errors silently drop adapters from registry | Catch ImportError per adapter, emit ERROR log, assert adapter count in CI |
| AWS RDS + Alembic | Migration that worked locally fails on RDS due to constraint naming or permission differences | Test migrations against a Postgres Docker instance, not just SQLite |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 in list endpoints | Response time grows linearly with list size | `selectinload`/`joinedload` + query count assertion in tests | At ~20+ items in list |
| Sequential crawler adapter execution | Total crawl time grows with each new adapter added | Parallelize with `ThreadPoolExecutor` bounded by connection pool math | At 50+ adapters (currently 114 — already hitting this) |
| `car_generations_data.py` eager import | Startup latency, slow `uvicorn --reload` | Lazy-load singleton with module-level cache | Every restart |
| No cache on reference data endpoints | DB hit on every `/categories/`, `/car-generations/`, `/part-manufacturers/` request | In-memory or Redis cache with TTL invalidation on write | At ~500 concurrent users |
| S3 HTML archive unbounded growth | `ListObjects` pagination slow; S3 costs grow | Lifecycle policy to expire/archive old crawl HTML | At ~100k stored pages |
| Connection pool exhaustion during parallel crawl | API requests return 503 during crawl runs | Cap crawler workers at `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE` | When parallelizing beyond 80 workers |

---

## "Looks Done But Isn't" Checklist

- [ ] **Auth refactor:** Old `auth.py` endpoints still registered? Verify no duplicate routes — FastAPI silently uses first-match routing.
- [ ] **Admin.py split:** Old `admin` router still imported in `main.py`? Verify the old import is deleted and all admin routes return 401 for unauthenticated requests.
- [ ] **N+1 fix:** Is there a query-count assertion in the test? If not, the fix will regress silently.
- [ ] **Crawler adapter auto-discovery:** Does CI assert adapter count matches expected? If not, a silent dropout won't be caught.
- [ ] **Migration safety:** Does every new migration have a tested `downgrade()`? Is `op.drop_constraint(None, ...)` absent from all new migrations?
- [ ] **Coverage threshold:** Is `--cov-fail-under` set in `pytest.ini`? Is `npm test` in `frontend-ci.yml`?
- [ ] **Chrome extension contract:** After any parts schema change — was the extension tested? Does `API_CONTRACT.md` exist and was it updated?
- [ ] **Lazy-load fix for `car_generations_data.py`:** Does the data still load correctly after switching to lazy? Test with a real `infer_car_generations()` call.
- [ ] **Parts dedup transactional fix:** Are concurrent link/unlink operations now safe? Is there a concurrency test?
- [ ] **Build log auto-creation:** Is the fragile mid-request creation replaced or wrapped in proper error handling?

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Refactor death spiral | HIGH | Stop all work. Identify the last working commit. Revert incomplete refactors to that state. Restart with smaller, phase-gated scope. |
| Double-maintenance trap | MEDIUM | Pick one as authoritative. Delete the other. Fix any divergent bug fixes. Document which was chosen and why. |
| Prod migration failure (constraint error) | HIGH | Do NOT run `alembic downgrade` without testing it first (downgrade may also fail). Fix the constraint name manually in SQL, then update the migration file to match. |
| N+1 reintroduced | LOW | Add `selectinload` to the query. Add query-count assertion. Deploy. |
| Adapter dropout | LOW | Add the dropped adapter back to the registry or fix its import. Trigger a manual crawl run to backfill missed pages. |
| Chrome extension API drift | MEDIUM | Identify the schema change that broke compatibility. Update the extension to match the new schema. Test the full scrape-to-submit flow. Publish a new extension version. |
| Coverage regression | LOW | Find which modules lost coverage. Add targeted tests. Do not lower the threshold — fix the coverage. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Refactor death spiral | All phases — enforce done-state definition | Each phase closes with old code deleted and CI green |
| Double-maintenance trap | Area 8 (admin split), Area 2 (crawler discovery) | `grep` for old router imports; verify adapter count |
| Alembic unnamed constraints | Area 4 (DB / migrations) | `grep -r "drop_constraint(None"` returns empty |
| SQLite / Postgres divergence | Area 4, Area 5 | Migrations tested against Postgres Docker; pg-specific tests separated |
| Broken `Depends()` after router split | Area 1 (auth), Area 8 (admin split) | Every admin route has 401/403 test |
| N+1 reintroduction | Area 4 (DB / perf) + Area 7 (tests) | Query-count assertion exists in CI |
| Adapter discovery breakage | Area 2 (crawler hardening) | CI asserts adapter count |
| Auth refactor regression | Area 1 (auth refactor) | Characterization tests written before split begins |
| Chrome extension drift | Area 1, Area 5, Area 6 | `API_CONTRACT.md` exists; extension tests in CI |
| Coverage regression | Area 7 (test coverage) | `--cov-fail-under` set; `npm test` in frontend CI |
| car_generations_data.py latency | Area 8 (code quality) | Startup time measured before/after |
| Circuit breaker signal confusion | Area 2 (crawler) + Area 3 (observability) | Log includes HTTP status breakdown, not just "tripped" |
| ThreadPoolExecutor sizing | Area 2 (crawler) | Worker count = pool math formula; pool exhaustion tested |
| Context re-render cascade | Area 6 (frontend) | React DevTools profiler checked after restructure |
| Vite HMR divergence | Area 6 (frontend) | `npm run build` passes in CI (already does) |
| Archive-replay drift | Area 2 (crawler) | Fixed adapters validated against one live URL |
| Migration without downgrade test | Area 4 (DB / migrations) | downgrade tested in local Postgres Docker |
| Error boundary gaps | Area 6 (frontend) | Error boundaries on all async data-fetching components |
| `__tablename__` conflict | Area 8 (code quality) | CI test imports all models and asserts unique tablenames |
| Build log auto-create | Area 8 (code quality) | Lazy creation replaced with eager; failure path tested |

---

## Sources

- Codebase analysis: `.planning/codebase/CONCERNS.md` (2026-04-22) — primary source for fragile areas and known bugs
- Codebase analysis: `.planning/codebase/TESTING.md` (2026-04-22) — test posture, CI configuration
- Direct code inspection: `backend/alembic/versions/` — unnamed constraint instances found in 3 migrations
- Direct code inspection: `backend/app/crawlers/adapters/__init__.py` — 114 manually-registered adapters
- Direct code inspection: `backend/app/api/endpoints/auth.py` (1,195 lines), `admin.py` (2,055 lines)
- Direct code inspection: `backend/app/db/session.py` — connection pool constants
- Direct code inspection: `.github/workflows/frontend-ci.yml` — frontend tests absent from CI (confirmed)
- Direct code inspection: `backend/app/api/models/*.py` — lazy loading strategy (selectin used in only 1 of 26+ relationships)
- Project context: `.planning/PROJECT.md` — milestone scope and constraints

---

*Pitfalls research for: CarModPicker tech-debt audit + refactor milestone*
*Researched: 2026-04-21*
