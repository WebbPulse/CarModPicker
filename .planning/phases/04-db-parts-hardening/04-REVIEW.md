---
status: issues_found
phase: "04"
phase_name: db-parts-hardening
depth: standard
files_reviewed: 83
reviewed_at: 2026-04-23
diff_base: ed1bfa5adefee2b86cf8bbc37b8093c39fef586b^
findings:
  critical: 1
  warning: 4
  info: 12
  total: 17
---

# Phase 4 Code Review — db-parts-hardening

## Summary

Phase 4's DB/parts-hardening changes are broadly high-quality. The FK-index migration is strictly
additive and idempotent via autogenerate naming; the backfill migration correctly uses
Postgres-native `gen_random_uuid()` with a `WHERE NOT EXISTS` guard and a deliberate no-op
downgrade. The N+1 fix in `build_logs.py` uses `selectinload(DBBuildLogPost.author)` correctly, and
the new `query_counter` fixture pins the exactly-2-queries contract. `lazy="raise"` is applied on
the three targeted relationships and enforced by `test_lazy_raise_callers.py`. The
`part_linker_service` locking follows stable ordering and includes siblings inside the lock scope.
The 296-call SQLAlchemy 2.0 sweep was spot-checked across endpoints/services/crawlers — no
translation errors found (all `.count()` → `select(func.count()).select_from(X)`, `.filter_by()` →
`.where()`, `.filter()` → `.where()` look correct, and `.with_entities()` → `.with_only_columns()`
conversions are sound).

**Key issues:**
- One **Critical** regression-test bug silently disarms 19/20 negative ambiguity vectors.
- Two **Warnings** around regression-guard coverage (session query scan misses `tests/` and
  `scripts/`, and a lock-ordering concern in `reelect_canonical`).
- Several **Info** items (pre-existing bugs in Phase 4 scope files, duplicate filter blocks, minor
  naming/style).

---

## Critical Issues

### CR-01: `test_car_inference_ambiguity.py` negative assertions never fail

**File:** `backend/tests/test_car_inference_ambiguity.py:204-206`

When the parametrized `expected` is `None` (19 of 28 vectors — every "ambiguous-standalone SHOULD
NOT fire" case), the test executes `assert expected not in result`. `expected` is literally `None`
and `result` is `list[tuple[str, str, str]]`, so `None not in result` is **always True**. None of
the "must not fire" assertions actually test the code path — they pass unconditionally even if
`infer_car_generations()` started returning an unwanted triple for every one of those inputs.
Given PARTS-02's explicit goal is to pin current ambiguity-resolution behavior, this neuters the
entire guard.

**Fix:** Rewrite the `None` branch to assert an empty result (or encode a forbidden tuple
explicitly for vectors where some other match is expected).

---

## Warnings

### WR-01: `test_session_query_regression.py` scope excludes `tests/` and `scripts/`

**File:** `backend/tests/test_session_query_regression.py:15`

`APP_DIR = Path(__file__).resolve().parent.parent / "app"` — the regression guard only scans
`backend/app/`. `backend/tests/conftest.py` still uses legacy `.query()` at 8 locations.
`backend/scripts/` is also not scanned. The DATA-06 "zero db.query()" invariant is global in
spirit but scoped to `app/` in implementation.

**Fix:** Either expand `APP_DIR` to `SEARCH_ROOTS = [app, tests, scripts]` (and rewrite
conftest.py's 8 residual calls), or explicitly document that test-utility code is exempt.

### WR-02: `reelect_canonical` lock order can deadlock against `link_new_part`

**File:** `backend/app/api/services/part_linker_service.py:152-162`

Both call paths lock a mixed set of rows via `WHERE id IN (...)` but do NOT sort by `id` before the
`SELECT ... FOR UPDATE`. Under index-dependent SQL lock acquisition, two transactions locking
overlapping row sets in different orders can deadlock. The 10-thread concurrency test exercises
`link_new_part` only — it does not exercise concurrent `reelect_canonical`.

**Fix:** Sort `lock_ids` before the `WHERE IN` to impose a deterministic order; mirror in
`link_new_part`; extend concurrency test to include a `reelect_canonical` thread.

### WR-03: Legacy `CRAWLER_USER_ID` fallback uses `int()` for a UUID field

**File:** `backend/app/crawlers/runner.py:117-122`

`DBUser.id` is `Mapped[uuid.UUID]`. `int(raw)` will `ValueError` on any UUID string. Pre-existing
bug, but lives in a file Phase 4 modified.

**Fix:** Parse as UUID, or delete the fallback since the service-account path is authoritative.

### WR-04: `init_service_accounts.py` log format mismatch (`%d` with UUID) will crash

**File:** `backend/app/core/init_service_accounts.py:53, 57`

`logger.info("... id=%d", user.id)` with a UUID raises `TypeError` on every cold-start where the
service account is newly created.

**Fix:** Change `%d` to `%s`.

---

## Info

### IN-01: Duplicated filter block in `build_lists.py` (`with-votes`)

**File:** `backend/app/api/endpoints/build_lists.py:153-169` and `:183-198`. Factor into
`_apply_build_list_filters(stmt, ...)` to prevent drift.

### IN-02: `copy_build_list` doesn't enforce the free-tier cap

**File:** `backend/app/api/services/build_list_service.py:243-360`. `BuildListService.create`
enforces `count_by_user >= 1`; `copy_build_list` does not. Free users can bypass the cap via copy.

### IN-03: `reelect_canonical` early-return is outside the lock region

Early return when `new_canonical.canonical_part_id is None` races concurrent `link_new_part`. The
returned-value invariant ("return value is canonical") can be violated under race.

### IN-04: `build_list_service.delete` has dead manual cascade code

**File:** `backend/app/api/services/build_list_service.py:157-181`. `cascade="all, delete-orphan"`
on the relationship handles this; the manual pre-delete is redundant.

### IN-05: `find_part_by_gtin` full-table fuzzy scan

**File:** `backend/app/api/services/part_listing_service.py:251-262`. Fallback path does O(N)
Python-side normalization over every non-null GTIN row. Consider a functional index on
`parts(regexp_replace(gtin, '\D', '', 'g'))` or backfill + delete the fuzzy path.

### IN-06: `conftest.py` still uses `db.query(...)` — not caught by regression test

**File:** `backend/tests/conftest.py:340, 397, 405, 455, 461, 508, 514, 532`. 8 legacy Query-API
calls remain in test helpers. See WR-01.

### IN-07: `conftest.py` engine fixture — SAVEPOINT contract must be honored

Noting only: new Phase 4 tests (backfill test, concurrency test) do commits inside tests. Ensure
each sticks to the outer-SAVEPOINT contract so rows do not leak.

### IN-08: `archive_rescrape` env override silently swallows ValueError

**File:** `backend/app/crawlers/archive_rescrape.py:72-79`. `CRAWLER_RESCRAPE_MAX_WORKERS=8x` goes
silently to default. Inconsistent with `runner.py`'s warning-on-invalid behavior.

### IN-09: Backfill migration downgrade marker — already present (verified)

No change required. Noted for completeness.

### IN-10: Heuristic weights in `part_linker_service` hard-coded

`_MAX_IMAGE_SCORE`, `_SCORE_GTIN`, etc. — module-level constants. Migrate to `core/config.py` for
tunability without code deploy. Defer.

### IN-11: `create_and_login_user` has redundant manual `email_verified` flip

**File:** `backend/tests/conftest.py:389-408`. `POST /api/users/` auto-verifies in TESTING. Delete
the manual flip block.

### IN-12: `get_or_create_part_manufacturer_by_name` case-insensitive pre-check vs case-sensitive unique index

**File:** `backend/app/api/services/part_listing_service.py:82-97`. Race-safe via SAVEPOINT +
IntegrityError retry, but the table can accumulate "Cusco" and "cusco" variants over time. Consider
`UNIQUE(lower(name))` index or CITEXT.

---

## Next Steps

Run `/gsd-code-review-fix 04` to auto-fix the findings, or address manually in priority order:
1. CR-01 first (Phase 4 regression-guard bug — blocks PARTS-02 validation)
2. WR-01 (expand session-query regression scope + rewrite conftest.py sites)
3. WR-02 (add lock-ordering sort + concurrency test for `reelect_canonical`)
4. WR-03, WR-04 (pre-existing UUID bugs in Phase 4-touched files)
5. Info items (IN-01 through IN-12) as time permits
