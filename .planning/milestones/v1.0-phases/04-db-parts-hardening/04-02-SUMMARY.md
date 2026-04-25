---
phase: 04-db-parts-hardening
plan: 02
subsystem: database
tags: [migrations, data-migration, build-log, cleanup]

# Dependency graph
requires:
  - phase: 04-db-parts-hardening
    provides: "Plan 04-01 landed FK indexes and pool_recycle tightening. Migration head at 55291406b6a4 — this plan chains from it (afdf25556c6c → 55291406b6a4)"
  - phase: 01-safety-nets-ci-hardening
    provides: "Migration DROP-guard (backend/scripts/check_migrations.py) validates no destructive ops; SAFE-04 annotation convention recognized by the guard"
  - phase: 01-safety-nets-ci-hardening
    provides: "MetaData(naming_convention=...) on Base.metadata via SAFE-09 — autogenerate scaffolding ran against it; Pitfall 10 noise was discarded per D-13"
provides:
  - "Idempotent backfill migration for build_logs — closes the legacy data gap that made the lazy auto-create branches necessary"
  - "Deleted lazy auto-create branches in backend/app/api/endpoints/build_logs.py — read paths now fail loudly with 404 + error log if invariant is broken"
  - "backend/scripts/check_build_logs_lazy_branch_removed.py — standalone CI-ready check script (replaces fragile inline python -c per WARN 11)"
  - "Two regression tests guarding the backfill shape and the orphan-guard invariant"
affects: [04-03-n-plus-one-fix, 04-04-session-query-sweep]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Alembic data migration with sa.text() wrapper + Postgres-native gen_random_uuid() + WHERE NOT EXISTS guard for idempotency"
    - "No-op downgrade() with exact SAFE-04 annotation for forward-only data migrations"
    - "Invariant-violation raise pattern: logger.error + ResponsePatterns.raise_not_found — surfaces data-integrity issues instead of silently auto-creating"
    - "Standalone verification script pattern (backend/scripts/check_*.py) that replaces shell-embedded python -c invocations when escape fragility becomes a concern"

key-files:
  created:
    - "backend/alembic/versions/afdf25556c6c_backfill_build_logs_for_legacy_build_lists.py"
    - "backend/scripts/check_build_logs_lazy_branch_removed.py"
    - "backend/tests/test_build_log_backfill.py"
    - "backend/tests/test_build_log_orphan_guard.py"
  modified:
    - "backend/app/api/endpoints/build_logs.py"

key-decisions:
  - "Migration uses Postgres-native gen_random_uuid() rather than Python-side uuid7() callable — Pitfall 2 (single-ID collision on row 2 via uq_build_logs_build_list_id)"
  - "downgrade() is a no-op with exact SAFE-04 annotation '# SAFE: forward-only data backfill; no reversal needed' — reversing would destroy user posts captured against backfilled rows (D-26)"
  - "Stripped now-unused `build_list = get_entity_or_404(...)` assignment to bare call (retained for side-effect 404 raise) to keep pyright reportUnusedVariable clean — auto-fix within deletion scope, not scope creep"
  - "Standalone check script invoked from plan's <automated> block rather than inline python -c per WARN 11 (nested quote escaping was fragile under XML embedding)"
  - "CREATE EXTENSION pgcrypto NOT prepended: gen_random_uuid() verified available on local Postgres 16 mirror without extension; prod RDS 16 verification flagged for operator per VALIDATION.md Manual-Only Verifications row"

patterns-established:
  - "Alembic data migration shape: autogenerate scaffolds the revision, discard naming_convention overlay output, hand-write upgrade() body as sa.text()-wrapped INSERT ... SELECT ... WHERE NOT EXISTS"
  - "Post-invariant assertion pattern: logger.error('...invariant violated'...) + ResponsePatterns.raise_not_found — replaces silent-recovery dead-weight branches"

requirements-completed: [DATA-08]

# Metrics
duration: 20min
completed: 2026-04-23
---

# Phase 4 Plan 02: Backfill build_logs and Delete Lazy Auto-Create Branches Summary

**Idempotent data migration backfills build_log rows for every legacy build_list, the two lazy mid-request auto-create branches in backend/app/api/endpoints/build_logs.py are deleted (replaced by loud 404 + logger.error on the post-DATA-08 invariant violation), a standalone verification script replaces the fragile inline python -c invocation (WARN 11), and two regression tests lock in the backfill shape + orphan-guard invariant.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-23T03:45Z (approx)
- **Completed:** 2026-04-23
- **Tasks:** 3
- **Files changed:** 5 (1 migration, 1 endpoint edit, 1 new check script, 2 new test modules)

## Accomplishments

- Alembic data migration `afdf25556c6c_backfill_build_logs_for_legacy_build_lists` committed — chains cleanly from plan 04-01's head `55291406b6a4`
- Upgrade body uses Postgres-native `gen_random_uuid()` + `WHERE NOT EXISTS` idempotency guard + `sa.text()` wrapper
- Downgrade is a deliberate no-op with the exact SAFE-04 annotation (`# SAFE: forward-only data backfill; no reversal needed`) — Phase 1 DROP-guard (`check_migrations.py`) exits 0
- Round-trip verified against local Postgres 16: `upgrade head` → `downgrade -1` → `upgrade head` all clean
- Idempotency verified on live data: running the backfill SQL twice produces `INSERT 0 0` on second invocation (existing 2501 build_logs rows unchanged)
- Both lazy auto-create branches at `backend/app/api/endpoints/build_logs.py:86-98` and `:191-201` deleted; replaced with `logger.error("...DATA-08 invariant violated...")` + `ResponsePatterns.raise_not_found("build log", build_list_id)`
- Standalone check script `backend/scripts/check_build_logs_lazy_branch_removed.py` exits 0 and prints "Lazy-branch deletion OK"
- 4 new regression tests green under `pytest -n auto`
- Full backend suite stays green: 2237 passed, 6 pre-existing skipped (+4 vs plan 04-01 baseline of 2233)
- OpenAPI snapshot unchanged
- `pyright app/api/endpoints/build_logs.py`: 0 errors, 0 warnings (stripped unused `build_list` locals as Rule 1 auto-fix)

## Task Commits

1. **Task 1: Backfill migration** — `de0da63` (feat) — `feat(04-02): add idempotent backfill migration for legacy build_logs`
2. **Task 2: Delete lazy branches + standalone check script** — `6aa16ee` (refactor) — `refactor(04-02): delete lazy auto-create branches in build_logs.py`
3. **Task 3: Regression tests** — `39f6b52` (test) — `test(04-02): regression tests for backfill shape and orphan-guard invariant`

## Migration Details

**Filename:** `backend/alembic/versions/afdf25556c6c_backfill_build_logs_for_legacy_build_lists.py`
**Revision:** `afdf25556c6c`
**Down-revision:** `55291406b6a4` (plan 04-01 FK-index migration)
**Shape:** one `op.execute(sa.text("INSERT INTO build_logs ... SELECT ... WHERE NOT EXISTS ..."))` in `upgrade()`; no-op `pass` with SAFE-04 annotation in `downgrade()`
**Destructive ops:** 0 (no `op.drop_*` / `op.alter_column`) — passes DROP-guard

### Core SQL (exact body)

```sql
INSERT INTO build_logs (id, build_list_id, title, created_at, updated_at)
SELECT gen_random_uuid(), bl.id, 'Build Log: ' || bl.name, NOW(), NOW()
FROM build_lists bl
WHERE NOT EXISTS (
    SELECT 1 FROM build_logs bl2 WHERE bl2.build_list_id = bl.id
)
```

### Idempotency & UUID confirmations

- **Idempotency:** Verified on live local Postgres 16 — after initial run, a second invocation of the identical INSERT returned `INSERT 0 0` (0 rows inserted); build_logs row count unchanged at 2501.
- **gen_random_uuid() availability:** Verified on the local Postgres 16 mirror — `SELECT gen_random_uuid()` returns a UUID without any `CREATE EXTENSION pgcrypto` prereq. No CREATE EXTENSION was prepended to the migration. Per VALIDATION.md "Manual-Only Verifications", the operator must confirm the same on prod RDS 16 via the bastion before merging Wave 2 to prod — if prod lacks it (unusual for RDS 16 defaults but possible depending on parameter-group history), prepend `op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))` as the first statement in `upgrade()`.

### Naming-convention overlay output discarded

Alembic autogenerate emitted the same Pitfall-10 noise as plan 04-01 did (Phase 1 SAFE-09 naming_convention overlay on historic unnamed constraints):

- `op.drop_constraint('categories_name_key')` + `op.create_unique_constraint('uq_categories_name')` — historic UNIQUE rename
- `op.create_foreign_key('fk_build_list_parts_build_list_phase_id_build_list_phases', ...)` — FK re-add with convention-name
- `op.create_foreign_key('fk_parts_canonical_part_id_parts', ...)` — same
- `op.create_foreign_key('fk_parts_part_manufacturer_id_part_manufacturers', ...)` — same

All four were discarded per D-13 / Pitfall 10. These are forward-only historic-name deferrals — retroactive renames are out of scope for Phase 4.

## Code Change Details (Task 2)

### Deleted lazy auto-create branches

**Before state — `backend/app/api/endpoints/build_logs.py:86-98` (get_build_log_by_build_list) and `:191-201` (create_build_log_post):**

```python
build_log = db.query(DBBuildLog).filter(DBBuildLog.build_list_id == build_list_id).first()
if not build_log:
    # Auto-create if it doesn't exist (for backward compatibility with existing build lists)
    build_log = DBBuildLog(
        build_list_id=build_list_id,
        title=f"Build Log: {build_list.name}",
    )
    db.add(build_log)
    db.commit()
    db.refresh(build_log)
    logger.info(f"Auto-created build log thread {build_log.id} for build list {build_list_id}")
```

**After state (both branches now identical modulo surrounding context):**

```python
build_log = db.query(DBBuildLog).filter(DBBuildLog.build_list_id == build_list_id).first()
if not build_log:
    # Post-DATA-08 backfill invariant: every build_list has a build_log row.
    # If this branch fires, something broke the invariant — do not silently
    # auto-create (the old fallback hid data-integrity issues).
    logger.error(
        "Orphan build_list %s has no build_log row; DATA-08 invariant violated", build_list_id
    )
    ResponsePatterns.raise_not_found("build log", build_list_id)
```

**Before-state line numbers (per plan frontmatter):** ~86-98 and ~191-201. After the edits, both branches span 10 lines each at approximately the same line ranges. The `db.query(...).first()` line retained (plan 04-04 owns the session.query sweep).

**Also stripped:** The now-unused `build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")` assignment converted to a bare call at lines 84 and 186 — Rule 1 auto-fix to keep `pyright reportUnusedVariable` clean. The `get_entity_or_404` helper still raises 404 on missing build_list (side-effect); the returned entity is no longer needed since the eager-create path (`build_list_service.py:82-88`) owns the build_log.title.

### Standalone check script (WARN 11)

`backend/scripts/check_build_logs_lazy_branch_removed.py` replaces the plan's original inline `python -c "..."` block. The script uses Python triple-quoted literals (no escape dance) and is invoked directly. Exits 0 with "Lazy-branch deletion OK" on a clean tree; exits 1 with a "FAIL:" prefix listing offending assertions otherwise.

Script verifies (all must pass):
- `DBBuildLog(` construction not present in the file
- `Auto-created build log thread` log message not present
- `DATA-08 invariant violated` string present (one per deleted branch)
- `raise_not_found` call count >= 2 (one per deleted branch)

## Regression Test Details (Task 3)

### backend/tests/test_build_log_backfill.py (static file-read)

- `test_migration_sql_is_idempotent` — asserts `gen_random_uuid()`, `WHERE NOT EXISTS`, `sa.text(`, `INSERT INTO build_logs`, and `'Build Log: ' || bl.name` are present; `uuid7(` is absent
- `test_migration_downgrade_is_no_op` — asserts `downgrade()` body contains no `op.drop_column` / `op.drop_table` / `op.drop_constraint` / `op.alter_column` tokens; contains the exact SAFE-04 annotation

### backend/tests/test_build_log_orphan_guard.py (service + ORM)

- `test_new_build_list_has_eager_build_log` — seeds a BuildList via `BuildListService().create(...)` and asserts a BuildLog row exists via direct `select()` query
- `test_no_orphan_build_lists` — seeds 3 BuildLists via the service (uses `premium_test_user` to bypass the free-tier 1-build-list cap) and asserts `SELECT COUNT(*) FROM build_lists WHERE id NOT IN (SELECT build_list_id FROM build_logs) == 0` (the D-27 invariant)

Adaptation from the plan's sample code: `BuildListCreate` requires a non-null `car_id`, so both tests call `create_car_orm_in_db(...)` before constructing the service payload. This mirrors the existing pattern in `backend/tests/services/test_build_list_service.py`.

## Decisions Made

- **Postgres-native `gen_random_uuid()` chosen over Python-side callable** per D-24 + Pitfall 2: a Python callable passed to `default=` in a raw INSERT fires once at statement prepare and every row gets the same id, tripping `uq_build_logs_build_list_id` on row 2. Postgres function evaluated per-row is the only correct shape.
- **`downgrade()` as deliberate no-op** per D-26: reversing a backfill would delete user posts captured against the backfilled build_log rows in the time between backfill-apply and any code-revert event. Git revert of the code change PR is the functional rollback; data stays.
- **Retained `db.query(...).first()` line in both branches** per plan directive — plan 04-04 owns the `session.query` → `select()` sweep. Doing it here would couple this plan to plan 04-04's larger sweep PR.
- **Rule 1 auto-fix to strip unused `build_list = get_entity_or_404(...)` assignment** at lines 84 and 186 — the deletion of the lazy-create body removed the only read of the `build_list` variable. Leaving it as-is produced `pyright reportUnusedVariable` warnings (verified). Changed to a bare `get_entity_or_404(...)` call with an expanded comment explaining the side-effect validation contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stripped unused `build_list = get_entity_or_404(...)` assignment to bare call**

- **Found during:** Task 2 (post-deletion pyright check)
- **Issue:** After deleting the lazy-create body that referenced `build_list.name`, the `build_list` variable on lines 84 and 186 became unused. `pyright app/api/endpoints/build_logs.py` reported 2 `reportUnusedVariable` warnings.
- **Fix:** Changed `build_list = get_entity_or_404(...)` to a bare `get_entity_or_404(...)` call on both lines. Added a comment explaining the side-effect validation contract (the helper raises 404 if the entity is missing; we no longer need the returned object).
- **Files modified:** `backend/app/api/endpoints/build_logs.py` (lines 83-84 and 185-186)
- **Verification:** `pyright app/api/endpoints/build_logs.py` — 0 errors, 0 warnings (was: 0 errors, 2 warnings).
- **Committed in:** `6aa16ee` (Task 2)

**2. [Rule 1 - Test hygiene] Task 3 orphan-guard test uses `premium_test_user` instead of `test_user`**

- **Found during:** Task 3 (composing the second test)
- **Issue:** Plan's sample code uses `test_user` + a `for i in range(3)` seed loop. The `BuildListService.create()` path enforces a 1-build-list cap for free users (non-premium), which would cause the second iteration to raise `HTTPException(402, ...)`.
- **Fix:** Switched the second test to use `premium_test_user` (existing conftest fixture) to bypass the cap. Noted the rationale in the test docstring.
- **Files modified:** `backend/tests/test_build_log_orphan_guard.py`
- **Verification:** `pytest -n auto tests/test_build_log_orphan_guard.py -v` — 2 passed.
- **Committed in:** `39f6b52` (Task 3)

---

**Total deviations:** 2 auto-fixed (both test-hygiene / lint-cleanness adjustments inside the task scope). No architectural decisions required.
**Impact on plan:** None — both fixes fall under the plan's implicit "keep the tree green" contract.

## Issues Encountered

- **Autogenerate emitted Pitfall-10 naming_convention overlay output.** Expected per the plan (plan 04-01 saw the same ops); deleted all 5 emitted ops cleanly.
- **None beyond the 2 deviations above.** No blockers; no architectural decisions required.

## Coordination Notes for Downstream Plans

- **Plan 04-03 (N+1 fix)** picks up `backend/app/api/endpoints/build_logs.py` in its already-cleaned state. Both lazy branches are gone; plan 04-03's `selectinload(DBBuildLogPost.author)` replacement for the per-post `db.query(DBUser).filter(...)` N+1 at line 116 (current) is the next move.
- **Plan 04-04 (session.query sweep)** also picks up `backend/app/api/endpoints/build_logs.py` in its already-cleaned state. The `db.query(DBBuildLog).filter(...)` calls at lines 87 and 189 remain as intentional retention per plan 04-02's scope contract; plan 04-04's sweep will convert them alongside the rest of the 304 `session.query()` call sites.
- **Plan 04-06 (CONVENTIONS.md + downgrade testing convention)** should cite `afdf25556c6c` as the Phase 4 exemplar of a forward-only data migration with a `# SAFE: forward-only data backfill; no reversal needed` downgrade.

## User Setup Required

**Operator must verify `gen_random_uuid()` availability on prod RDS 16 via the bastion before Wave 2 migration ships to prod.** Per VALIDATION.md "Manual-Only Verifications":

```sql
-- Run via bastion against prod RDS 16
SELECT gen_random_uuid();
```

- If the query returns a UUID: no further action; the migration is prod-ready as-is.
- If the query errors with "function gen_random_uuid() does not exist": prepend the following as the first statement inside `upgrade()` in `backend/alembic/versions/afdf25556c6c_backfill_build_logs_for_legacy_build_lists.py`:
  ```python
  op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
  ```
- The local Postgres 16 mirror was verified during this plan's execution — `SELECT gen_random_uuid()` returned a UUID without any extension prereq, suggesting prod RDS 16 (which typically ships with the same extension baseline) will be OK. But this is an operator-gated manual check per the plan's D-24 and VALIDATION.md directive.

## Verification

- `python backend/scripts/check_build_logs_lazy_branch_removed.py` → exits 0, prints "Lazy-branch deletion OK"
- `cd backend && python scripts/check_migrations.py` → `check_migrations: OK (36 files scanned)` (DROP-guard)
- `cd backend && pytest -n auto tests/test_build_log_backfill.py tests/test_build_log_orphan_guard.py -v` → 4 passed
- `cd backend && pytest -n auto tests/api/endpoints/test_build_logs.py -v` → 32 passed (no regression)
- `cd backend && pytest -n auto tests/test_openapi_snapshot.py` → 1 passed (no endpoint signature drift)
- `cd backend && pytest -n auto` → 2237 passed, 6 pre-existing skipped (+4 vs plan 04-01 baseline)
- `cd backend && alembic upgrade head` → applied afdf25556c6c against local Postgres 16
- `cd backend && alembic downgrade -1 && alembic upgrade head` → round-trip clean
- Idempotency on live Postgres: re-running the INSERT SQL returned `INSERT 0 0` (0 new rows)
- `pyright app/api/endpoints/build_logs.py` → 0 errors, 0 warnings
- `pyright tests/test_build_log_backfill.py tests/test_build_log_orphan_guard.py` → 0 errors, 0 warnings

## Next Phase Readiness

- **Plan 04-03 (N+1 fix + query-count regression)** unblocked — `backend/app/api/endpoints/build_logs.py` is in its cleaned-state (lazy branches gone); the N+1 at line 116 is the next target.
- **Plan 04-04 (session.query sweep)** unblocked — same file included in the sweep; the retained `db.query(...)` calls at 87 and 189 are sweep targets.
- **Plan 04-05 (row-lock concurrency test)** unblocked per D-42 — it depends on plan 04-02's cleaned build_log surface.
- **Plan 04-06 (CONVENTIONS.md + docs)** unblocked per D-42.

## Self-Check: PASSED

File existence:
- FOUND: backend/alembic/versions/afdf25556c6c_backfill_build_logs_for_legacy_build_lists.py
- FOUND: backend/scripts/check_build_logs_lazy_branch_removed.py
- FOUND: backend/tests/test_build_log_backfill.py
- FOUND: backend/tests/test_build_log_orphan_guard.py
- MODIFIED (verified via git show): backend/app/api/endpoints/build_logs.py

Commit existence:
- FOUND: de0da63 (Task 1)
- FOUND: 6aa16ee (Task 2)
- FOUND: 39f6b52 (Task 3)

---
*Phase: 04-db-parts-hardening*
*Plan: 02*
*Completed: 2026-04-23*
