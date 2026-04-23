---
phase: "04"
fixed_at: 2026-04-22
review_path: .planning/phases/04-db-parts-hardening/04-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 2
already_fixed: 3
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-04-22
**Source review:** `.planning/phases/04-db-parts-hardening/04-REVIEW.md`
**Iteration:** 1
**Scope:** `critical_warning` (CR-01, WR-01, WR-02, WR-03, WR-04 — Info items skipped)

**Summary:**
- Findings in scope: 5
- Fixed this run: 2 (WR-01, WR-02)
- Already fixed in prior commits: 3 (CR-01, WR-03, WR-04)
- Skipped: 0

## Fixed Issues

### WR-02: `reelect_canonical` lock order can deadlock against `link_new_part`

**Files modified:** `backend/app/api/services/part_linker_service.py`
**Commit:** `523af2e`
**Applied fix:**
- In `reelect_canonical`: build the lock set as `set[UUID]`, then materialize a sorted list (`sorted(lock_ids_set)`) before the `WHERE id IN (...)` `SELECT ... FOR UPDATE`.
- In `link_new_part`: replace `[c.id for c in candidates] + [new_part.id]` with `sorted({c.id for c in candidates} | {new_part.id})` so overlapping link paths acquire row locks in identical (by-id) order.
- Added inline comments tagging both sites with the WR-02 rationale.

**Verification:**
- Tier 1: re-read file — both call sites show deterministic sorted list feeding `.in_(...)`.
- Tier 2: `python -c "import ast; ast.parse(...)"` — syntax OK.
- Test run: `pytest -n auto tests/test_part_linker.py tests/services/` — 97 passed, 2 skipped (the 2 skips are Postgres-only concurrency tests that do not execute on SQLite CI).

**Deferred:** The review also recommends extending the 10-thread concurrency test to include a `reelect_canonical` worker. That test expansion is outside the safe auto-fix envelope (requires designing new concurrency scenarios) and is flagged as follow-up work in the commit body.

### WR-01: `test_session_query_regression.py` scope excludes `tests/` and `scripts/`

**Files modified:** `backend/tests/test_session_query_regression.py`
**Commit:** `8834330`
**Applied fix:** Chose resolution option (b) from the review — document the scope exemption explicitly rather than rewriting ~50 residual test/script call sites. The updated module docstring now spells out the deliberate boundary:

- `backend/app/` is in scope (runtime/request path).
- `backend/tests/` is out of scope (test helpers; 1.x Query API is deprecated but not removed in SQLAlchemy 2.x; rewriting carries regression risk that outweighs invariant value).
- `backend/scripts/` is out of scope (one-off maintenance scripts that run out-of-band).

No executable behavior change; the test still passes.

**Verification:**
- Tier 1: re-read file — docstring now explicitly documents scope; `APP_DIR` unchanged.
- Tier 2: `python -c "import ast; ast.parse(...)"` — syntax OK.
- Test run: `pytest -n auto tests/test_session_query_regression.py` — 1 passed.

**Rationale for choosing option (b) over option (a):** The grep scan showed the residual `.query()` calls span far more than the 8 conftest.py lines the review mentions — there are 50+ sites across `test_auth.py`, `test_google_oauth.py`, `test_admin.py`, `test_build_logs.py`, `test_crawled_page_storage.py`, `test_users.py`, `test_webauthn.py`, `test_part_linker.py`, and others. Rewriting them all is test-suite-wide refactoring work, not an auto-fix. Making the scope exemption explicit preserves the current design intent (invariant applies to the request path only) without touching any runtime code.

## Already Fixed

### CR-01: `test_car_inference_ambiguity.py` negative assertions never fail

**Files:** `backend/tests/test_car_inference_ambiguity.py:225-240`
**Original commit:** `d635d0c` — `fix(04-06): harden ambiguity-vector negative assertions (CR-01)`
**Current state verified:** The `None` branch now asserts `result == []` (18 vectors) or checks `NEGATIVE_FORBIDDEN_TUPLES` for the forbidden triple (1 vector: the Bilstein EVO T1 case). No `None not in result` vacuously-true assertion remains. All 19/20 negative vectors now meaningfully guard the inference behavior.

### WR-03: Legacy `CRAWLER_USER_ID` fallback uses `int()` for a UUID field

**File:** `backend/app/crawlers/runner.py:113-124`
**Original commit:** `245b6b0` — `fix(02): WR-03 parse CRAWLER_USER_ID as UUID not int in runner fallback`
**Current state verified:** `int(raw)` replaced with `UUID(raw)`. Error message updated to "CRAWLER_USER_ID must be a valid UUID." The fallback now matches the actual `Mapped[uuid.UUID]` column type. (Note: this was committed against Phase 02 rather than Phase 04 because runner.py straddles both phases.)

### WR-04: `init_service_accounts.py` log format mismatch (`%d` with UUID) will crash

**File:** `backend/app/core/init_service_accounts.py:53, 57, 59`
**Original commit:** `204334f` — `fix(04): use %s for UUID logging in init_service_accounts (WR-04)`
**Current state verified:** All three log sites (`Created`, `Marked existing`, `already exists`) use `%s` for `user.id`. No `%d`/UUID mismatch remains; the `TypeError` on cold-start is eliminated.

## Info Findings

Out of scope for `critical_warning` fix pass. Not addressed this iteration:

- IN-01 through IN-12 — see REVIEW.md for details. Tracked for future manual triage.

---

_Fixed: 2026-04-22_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
