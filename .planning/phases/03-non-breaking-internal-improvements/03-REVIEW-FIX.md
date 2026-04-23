---
phase: 03-non-breaking-internal-improvements
fixed_at: 2026-04-23T05:47:13Z
review_path: .planning/phases/03-non-breaking-internal-improvements/03-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 5
skipped: 1
status: partial
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-04-23T05:47:13Z
**Source review:** `.planning/phases/03-non-breaking-internal-improvements/03-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (Critical: 0, Warning: 6; Info: 9 deferred per fix_scope=critical_warning)
- Fixed: 5
- Skipped: 1 (already fixed in a prior phase commit)

## Fixed Issues

### WR-01: `car_generations_data.py` shim eagerly loads JSON at import

**Files modified:** `backend/app/core/car_generations_data.py`
**Commit:** 4113746
**Applied fix:** Replaced the eager `CAR_GENERATIONS = load_car_generations()` module-level bind with a PEP 562 `__getattr__` hook. First access to the attribute triggers the `@lru_cache`'d loader; subsequent accesses return the same dict (so `test_shim_and_loader_agree` identity assertion still holds). Also rewired `get_all_car_generations()` to call `load_car_generations()` directly instead of referencing the now-deferred module attribute. All 17 car-generations / init-cars tests pass.

### WR-02: `add_filter_endpoint` path parameter name mismatch

**Files modified:** `backend/app/api/utils/base_endpoint_router.py`, `backend/tests/fixtures/openapi_snapshot.json`
**Commit:** 66aacd7
**Applied fix:** Changed the URL template from `f"/{filter_name}/{{{filter_name}_id}}"` to `f"/{filter_name}/{{filter_id}}"` so the path placeholder name matches the function's `filter_id: UUID` parameter. Added an inline WR-02 comment explaining the rationale. Regenerated the OpenAPI snapshot — the diff shows the previously broken duplicate path `/api/parts/category/{category_id}` (filter_entities) is now correctly registered as `/api/parts/category/{filter_id}` while the hand-written `get_parts_by_category` keeps `{category_id}`. All 28 parts/openapi tests pass.

### WR-04: `breaker.open()` may double-fire on terminal 429/503 in HALF_OPEN state

**Files modified:** `backend/app/crawlers/runner.py`
**Commit:** f468b86
**Applied fix:** Wrapped the `breaker.open()` call in a `current_state != "open"` guard (Option A from the review). This avoids re-issuing the warning log when a concurrent worker has already tripped the breaker, and keeps the manual force-open visibly tied to a state transition. Behavior is unchanged on the happy path (closed/half-open → open) since pybreaker treats open→open as a no-op anyway. Added a multi-line comment explaining the double-accounting interaction with `breaker.call()`. All 6 circuit-breaker tests pass.

### WR-05: `count_*` endpoints rebind `logger` to common_patterns module logger

**Files modified:** `backend/app/api/endpoints/bug_reports.py`, `backend/app/api/endpoints/reports.py`, `backend/app/api/endpoints/votes.py`
**Commit:** 21c7aba
**Applied fix:** Removed `logger = deps["logger"]` from each `count_*` function so the module-level `logger = logging.getLogger(__name__)` is used. Records emitted from `count_bug_reports` / `count_reports` / `count_votes` now correctly carry their own module name (`app.api.endpoints.bug_reports` etc.) instead of `app.api.utils.common_patterns`. Did NOT remove `logger` from `PublicEndpointDeps` (deferred — would touch every `deps["logger"]` site across the codebase, out of scope for this fix). All 53 endpoint tests pass.

### WR-06: `google_link` OTP try/except mis-scopes verify-time errors

**Files modified:** `backend/app/api/endpoints/auth.py`
**Commit:** c3636b2
**Applied fix:** Split the single try/except wrapping `pyotp.TOTP(...)` + `totp.verify(...)` into two blocks, mirroring the `verify_2fa` pattern. A `(ValueError, TypeError, binascii.Error)` raised during construction now logs "Invalid TOTP secret format" before returning 500; the same exception class raised during verify logs "TOTP verification failed". Both still surface to the user as "2FA configuration error" (preserving existing client-visible behavior), but server logs now correctly distinguish the failure mode. All 61 auth + google-oauth tests pass.

## Skipped Issues

### WR-03: `CRAWLER_USER_ID` env var parsed as `int(raw)` but `User.id` is `uuid.UUID`

**File:** `backend/app/crawlers/runner.py:113-123`
**Reason:** Already fixed in a prior phase commit. `git log` shows commit `245b6b0 fix(02): WR-03 parse CRAWLER_USER_ID as UUID not int in runner fallback`. The current file already parses with `UUID(raw)` and raises `CrawlerConfigError("CRAWLER_USER_ID must be a valid UUID.")` — the exact fix the review proposed. No new commit required; the finding was carried forward from Phase 02 and has been resolved upstream.
**Original issue:** Legacy fallback path used `int(raw)` for `CRAWLER_USER_ID` even though `User.id` is a UUID column, causing misleading error messages and silent "no user found" results for valid UUID inputs.

---

_Fixed: 2026-04-23T05:47:13Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
