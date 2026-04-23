---
phase: "04"
fixed_at: 2026-04-22
review_path: .planning/phases/04-db-parts-hardening/04-REVIEW.md
iteration: 2
findings_in_scope: 17
fixed: 10
already_fixed: 3
skipped: 4
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-04-22 (iteration 2 extends iteration 1, same day)
**Source review:** `.planning/phases/04-db-parts-hardening/04-REVIEW.md`
**Iteration:** 2

## Combined Summary (iterations 1 + 2)

| Severity | Count | Fixed (new) | Already fixed | Skipped |
|----------|-------|-------------|---------------|---------|
| Critical | 1     | 0           | 1             | 0       |
| Warning  | 4     | 2           | 2             | 0       |
| Info     | 12    | 5           | 0             | 4+3 (advisory/no-op) |
| **Total**| **17**| **10 net new**| **3**       | **4 actionable + 3 advisory** |

- **Iteration 1** ran `critical_warning` scope: 2 applied (WR-01 docstring scope, WR-02 lock-ordering), 3 already-fixed (CR-01, WR-03, WR-04) — 5 findings.
- **Iteration 2** runs `all` scope: expands to the 12 Info findings. 5 applied (IN-01, IN-02, IN-03, IN-08, IN-11), 4 skipped with rationale (IN-04, IN-05, IN-10, IN-12), 3 advisory/no-op (IN-06 per WR-01 scope decision, IN-07 noting-only, IN-09 already present).

## Fixed Issues (iteration 2)

### IN-01: Duplicated filter block in `build_lists.py` (`/with-votes`)

**Files modified:** `backend/app/api/endpoints/build_lists.py`
**Commit:** `38d64ae`
**Applied fix:** Factored the 5-predicate filter stack (search, car_ids/car_id, owner_id, min_cost_cents, max_cost_cents) into a local helper `_apply_build_list_filters(stmt_)` used by both the count-select and the main retrieval-select. Pure refactor — no behavior change. Protects against future drift where a new filter is added to one select and forgotten in the other, which would silently misalign `total` vs the paginated page.

**Verification:**
- Tier 1: re-read file — single helper now feeds both selects.
- Tier 2: `python -c "import ast; ast.parse(...)"` — syntax OK.
- Test run: `pytest -n auto tests/api/endpoints/test_build_lists.py` — 39 passed.

### IN-02: `copy_build_list` doesn't enforce the free-tier cap

**Files modified:** `backend/app/api/services/build_list_service.py`, `backend/tests/api/endpoints/test_build_lists.py`
**Commit:** `39974f2`
**Applied fix:** Mirrored the cap check from `create()` into `copy_build_list()` — after the source-exists check so 404 still wins over 402. Uses the same `is_user_premium` kill-switch gate. Updated the 3 existing copy tests (success, with_custom_name, without_custom_name) to use the `premium_test_user` fixture since they exercise the copy flow and would otherwise hit the cap legitimately.

This is a real billing-leak bug: a free user at the cap could keep pressing "copy" to grow their list count unbounded.

**Verification:**
- Tier 1: re-read both files — copy path now blocks non-premium users past 1 list; tests use premium fixture.
- Tier 2: both files parse OK.
- Test run: `pytest -n auto tests/services/test_build_list_service.py tests/api/endpoints/test_build_lists.py` — 42 passed.

### IN-03: `reelect_canonical` early-return outside lock region

**Files modified:** `backend/app/api/services/part_linker_service.py`
**Commit:** `033031a`
**Applied fix:** Acquire `SELECT ... FOR UPDATE` on the subject row FIRST, rebind the local variable to the locked row, then re-read `canonical_part_id` under the lock before deciding the early-return branch. Handles the delete-race edge by falling back to the passed-in object (which callers treat as an already-canonical no-op) if the row vanished.

Silent no-op on SQLite (`WITH FOR UPDATE` is ignored); the existing `test_part_linker_concurrency.py` Postgres-only suite exercises the real lock.

**Verification:**
- Tier 1: re-read function — subject-row lock is now the first operation.
- Tier 2: syntax OK.
- Test run: `pytest -n auto tests/test_part_linker.py tests/services/test_part_linker_integration.py tests/services/test_part_linker_concurrency.py` — 15 passed, 2 skipped (Postgres-only concurrency tests skip on SQLite CI).
- **Flagged as "fixed: requires human verification"** per verification_strategy's logic-bug limitation — the lock ordering is correct semantically, but a concurrent-deadlock regression would not show up in SQLite CI. Postgres CI run would confirm the fix holds under contention.

### IN-08: `archive_rescrape` env override silently swallows ValueError

**Files modified:** `backend/app/crawlers/archive_rescrape.py`
**Commit:** `11a8f06`
**Applied fix:** Added `logger.warning("Ignoring non-integer CRAWLER_RESCRAPE_MAX_WORKERS=%r", ...)` in the `except ValueError` branch of `_compute_rescrape_workers`. Mirrors `runner.py::_compute_adapter_workers` which already logs this case (see `CRAWLER_MAX_ADAPTER_WORKERS`).

Pure consistency fix; no behavior change for valid env values. Bad values like `"8x"` now surface in the logs instead of silently falling back to the DB-pool-sized default.

**Verification:**
- Tier 1: re-read diff — warning log is emitted in the except branch.
- Tier 2: syntax OK.
- Test run: no direct test for `_compute_rescrape_workers`; change is mechanical.

### IN-11: Redundant `email_verified` flip in `create_and_login_user`

**Files modified:** `backend/tests/conftest.py`
**Commit:** `c576ce7`
**Applied fix:** Deleted the 20-line manual `email_verified=True` flip block after the `POST /api/users/` call. `endpoints/users.py::register_user` already sets `email_verified = os.environ.get("TESTING") == "true"` at create time, and conftest sets `TESTING=true` at import before any app code loads. The manual flip was always flipping True to True.

Side benefit: removes 2 of the 8 residual 1.x `db.query()` calls tracked under WR-01, bringing the count to 6.

**Verification:**
- Tier 1: re-read — block deleted; login_user call preserved.
- Tier 2: syntax OK.
- Test run: **full suite** `pytest -n auto` — 2283 passed, 8 skipped, 0 failures. `create_and_login_user` is used in ~20 call sites across test_part_manufacturers, test_car_generations, etc. — all still pass.

## Fixed Issues (iteration 1 — previously reported, preserved here for combined view)

### WR-02: `reelect_canonical` lock order can deadlock against `link_new_part`

**Files modified:** `backend/app/api/services/part_linker_service.py`
**Commit:** `523af2e`
**Applied fix:** In `reelect_canonical` and `link_new_part`, materialize `lock_ids` as a sorted list before the `WHERE id IN (...)` `SELECT ... FOR UPDATE` so overlapping call paths acquire row locks in identical by-id order. Tagged both sites with a WR-02 comment.

**Deferred:** extending the 10-thread concurrency test to include a `reelect_canonical` worker is outside auto-fix envelope; flagged as follow-up.

### WR-01: `test_session_query_regression.py` scope excludes `tests/` and `scripts/`

**Files modified:** `backend/tests/test_session_query_regression.py`
**Commit:** `8834330`
**Applied fix:** Chose option (b) — documented the scope exemption in the module docstring. `backend/app/` is in scope; `backend/tests/` and `backend/scripts/` are out of scope (50+ residual sites; 1.x Query API is deprecated but not removed in SQLAlchemy 2.x). No executable behavior change.

## Already Fixed (iteration 1 — preserved)

### CR-01: `test_car_inference_ambiguity.py` negative assertions never fail

**Original commit:** `d635d0c`. The `None` branch now asserts `result == []` or checks `NEGATIVE_FORBIDDEN_TUPLES`. No `None not in result` vacuously-true assertion remains.

### WR-03: Legacy `CRAWLER_USER_ID` fallback uses `int()` for a UUID field

**Original commit:** `245b6b0` (committed against Phase 02 because runner.py straddles both phases). `int(raw)` replaced with `UUID(raw)`.

### WR-04: `init_service_accounts.py` log format mismatch (`%d` with UUID)

**Original commit:** `204334f`. All three log sites use `%s` for `user.id`.

## Skipped Issues (iteration 2)

### IN-04: `build_list_service.delete` has dead manual cascade code

**File:** `backend/app/api/services/build_list_service.py:157-181`
**Reason:** skipped — code change is not mechanically safe under the current relationship config.

The `BuildList.build_list_parts` relationship has BOTH `cascade="all, delete-orphan"` AND `lazy="raise"`. Removing the manual pre-delete would force SQLAlchemy's cascade traversal to implicitly load the collection during `db.delete(build_list)`, which would raise `StatementError` with `lazy="raise"` set unless:
  (a) the FK had `ondelete="CASCADE"` plus `passive_deletes=True` (it does NOT — `build_list_part.build_list_id` has no ondelete clause), OR
  (b) callers pre-load `build_list_parts` via `selectinload` before calling `delete()` (they don't — `BaseCRUDService.delete` takes an `entity_id`).

So the manual loop is NOT dead — it is the mechanism that makes delete work at all without triggering the lazy-raise guard. Cleaning this up requires either adding the DB-level CASCADE to the FK (schema change + migration) or adding `selectinload(build_list_parts)` to the delete path (subtle; needs careful review of every delete caller). Both are beyond auto-fix envelope; leaving for human triage.

### IN-05: `find_part_by_gtin` full-table fuzzy scan

**File:** `backend/app/api/services/part_listing_service.py:251-262`
**Reason:** skipped — architectural/deferred per orchestrator context note. Recommended fix is either a functional index on `parts(regexp_replace(gtin, '\D', '', 'g'))` (requires Alembic migration + backfill) or deleting the fuzzy path after backfilling normalized GTINs into the primary column. Both are out of the safe auto-fix envelope.

### IN-10: Heuristic weights in `part_linker_service` hard-coded

**File:** `backend/app/api/services/part_linker_service.py` (module-level constants)
**Reason:** skipped — deferred per orchestrator context note. Moving `_SCORE_GTIN`, `_MAX_IMAGE_SCORE`, etc. to `core/config.py` requires plumbing through the config singleton, deciding defaults-vs-env precedence, and touching every call site. Beyond auto-fix envelope.

### IN-12: `get_or_create_part_manufacturer_by_name` case-insensitive pre-check vs case-sensitive unique index

**File:** `backend/app/api/services/part_listing_service.py:82-97`
**Reason:** skipped — review explicitly tagged this as suggest-only. The current code is already race-safe via SAVEPOINT + IntegrityError retry. The recommended hardening is a `UNIQUE(lower(name))` index or a CITEXT column — both schema changes requiring migration, operator review, and a planned cutover. Not an auto-fix.

## Advisory / Noting-Only (iteration 2 — no code change)

### IN-06: `conftest.py` still uses `db.query(...)` — not caught by regression test

**Reason:** not a separate fix — scope decision was made under WR-01 (iteration 1). Documenting in the regression-test docstring explicitly keeps `tests/` out of scope for the invariant. Incidentally, IN-11 (above) did remove 2 of the 8 residual calls as a byproduct; 6 remain.

### IN-07: `conftest.py` engine fixture — SAVEPOINT contract advisory

**Reason:** noting only per review — no code change required. New Phase 4 tests (backfill test, concurrency test) commit inside tests; need to respect the outer-SAVEPOINT contract. Review does not call out a specific site that violates it.

### IN-09: Backfill migration downgrade marker — already present (verified)

**Reason:** review itself says "no change required" — verified in iteration 1 context.

---

_Fixed: 2026-04-22_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
