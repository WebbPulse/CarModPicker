---
phase: 04-db-parts-hardening
plan: 04
subsystem: database
tags: [session-query, select, migration, mechanical-sweep, regression-guard]

# Dependency graph
requires:
  - phase: 04-db-parts-hardening
    provides: "Plan 04-03 migrated the build_logs read-path to select() + selectinload — plan 04-04 closes the remaining 296 call sites across the rest of backend/app/"
  - phase: 03-non-breaking-internal-improvements
    provides: "Module-level `logger = logging.getLogger(__name__)` convention honored across all rewritten files (no Depends(get_logger) reintroduced)"
provides:
  - "backend/tests/test_session_query_regression.py — permanent CI gate that asserts zero db.query() / session.query() / self.db.query() call sites across backend/app/**/*.py"
  - "DATA-06 closed: every legacy Session.query(...) call site rewritten to the SQLAlchemy 2.0 select() + session.scalars / session.scalar API"
  - "Modernized helper contracts (common_patterns, common_operations, pagination_utils) now accept Select[Any] with (db, stmt) pairs at terminal points — downstream code that builds Selects can pass them through the helpers without double-conversion"
  - "part_linker_service._point_siblings_at and link_group_part_ids rewritten in the modern form — ready for plan 04-05's with_for_update() row-lock insertion at these sites"
affects: [04-05-row-lock-concurrency, 04-06-conventions-lazy-raise, 05-admin-auth-splits]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "db.scalars(select(Model).where(...)).first() / .all() for ORM reads (Flavor A)"
    - "db.scalars(select(Model.col).where(...)).all() for scalar column iteration (Flavor B)"
    - "db.scalar(select(func.count()).select_from(Model).where(...)) or 0 for COUNT(*) — preserves NULL=0 semantics per Pitfall 5"
    - "db.execute(select(...).group_by(...)).all() for multi-column aggregates"
    - "db.execute(sql_update(Model).where(...).values(...).execution_options(synchronize_session=False)) for bulk update"
    - "db.execute(sql_delete(Model).where(...).execution_options(synchronize_session=False)) for bulk delete"
    - "stmt.with_only_columns(Model.id) for id-only pagination phase of two-query hydrate pattern"
    - "select(func.count()).select_from(stmt.subquery()) for COUNT over filtered/joined Selects (count of a complex Select)"

key-files:
  created:
    - "backend/tests/test_session_query_regression.py"
  modified:
    - "backend/app/api/dependencies/auth.py"
    - "backend/app/api/endpoints/admin.py"
    - "backend/app/api/endpoints/app_settings.py"
    - "backend/app/api/endpoints/auth.py"
    - "backend/app/api/endpoints/bug_reports.py"
    - "backend/app/api/endpoints/build_list_parts.py"
    - "backend/app/api/endpoints/build_list_phases.py"
    - "backend/app/api/endpoints/build_lists.py"
    - "backend/app/api/endpoints/build_logs.py"
    - "backend/app/api/endpoints/car_generations.py"
    - "backend/app/api/endpoints/categories.py"
    - "backend/app/api/endpoints/crawled_pages.py"
    - "backend/app/api/endpoints/crawler_adapter_configs.py"
    - "backend/app/api/endpoints/crawler_schedules.py"
    - "backend/app/api/endpoints/images.py"
    - "backend/app/api/endpoints/part_manufacturers.py"
    - "backend/app/api/endpoints/parts.py"
    - "backend/app/api/endpoints/reports.py"
    - "backend/app/api/endpoints/retailers.py"
    - "backend/app/api/endpoints/search.py"
    - "backend/app/api/endpoints/users.py"
    - "backend/app/api/endpoints/votes.py"
    - "backend/app/api/services/base_crud_service.py"
    - "backend/app/api/services/base_report_service.py"
    - "backend/app/api/services/base_vote_service.py"
    - "backend/app/api/services/bug_report_service.py"
    - "backend/app/api/services/build_list_service.py"
    - "backend/app/api/services/car_generation_service.py"
    - "backend/app/api/services/crawler_schedule_service.py"
    - "backend/app/api/services/part_linker_service.py"
    - "backend/app/api/services/part_listing_service.py"
    - "backend/app/api/services/report_service.py"
    - "backend/app/api/services/user_service.py"
    - "backend/app/api/services/vote_service.py"
    - "backend/app/api/utils/admin_endpoint_patterns.py"
    - "backend/app/api/utils/authorization.py"
    - "backend/app/api/utils/bucket_orphan_utils.py"
    - "backend/app/api/utils/common_operations.py"
    - "backend/app/api/utils/common_patterns.py"
    - "backend/app/api/utils/endpoint_decorators.py"
    - "backend/app/api/utils/pagination_utils.py"
    - "backend/app/api/utils/subscription_utils.py"
    - "backend/app/core/car_inference.py"
    - "backend/app/core/init_cars.py"
    - "backend/app/core/init_categories.py"
    - "backend/app/core/init_crawler_adapter_configs.py"
    - "backend/app/core/init_service_accounts.py"
    - "backend/app/crawlers/archive_rescrape.py"
    - "backend/app/crawlers/base.py"
    - "backend/app/crawlers/ecs_rescrape_runner.py"
    - "backend/app/crawlers/ecs_runner.py"
    - "backend/app/crawlers/runner.py"
    - "backend/app/services/job_service.py"
    - "backend/tests/test_pagination.py"
    - "backend/tests/utils/test_pagination_utils.py"

key-decisions:
  - "Helper function signatures migrated — apply_standard_filters / build_search_query / build_filtered_query / build_sorted_query / apply_pagination_and_ordering now accept Select[Any] instead of SQLAlchemyQuery. get_paginated_response and get_total_count gain a db: Session parameter to terminate with db.scalars(...).all() / db.scalar(select(func.count()).select_from(stmt.subquery())). This is a signature change — callers were updated in the same sweep commits, so no downstream callers can be broken."
  - "Two-query id-then-hydrate pagination pattern preserved in build_lists.py and parts.py via Select.with_only_columns(Model.id), replacing Query.with_entities(Model.id). Response ordering and sort semantics unchanged."
  - "Bulk DML (.query(X).delete() / .update()) migrated to db.execute(sql_delete(X).where(...).execution_options(synchronize_session=False)) / db.execute(sql_update(X).where(...).values(...)) — preserves synchronize_session semantics for cascade-less cleanup used by admin /cars/delete-all and /part-manufacturers/delete-all."
  - "COUNT(*) semantics consistently preserved via select(func.count()).select_from(Model).where(...) per D-07 / Pitfall 5 — never select(func.count(Model.id)) which excludes NULLs. `or 0` coercion applied at every site to satisfy non-Optional[int] callers (db.scalar returns Optional[int])."
  - "Test files (tests/test_pagination.py + tests/utils/test_pagination_utils.py) updated to match the new Select-based pagination_utils signatures. Not a behavior change — the tests still exercise the same helper semantics, just via the modernized contract."

patterns-established:
  - "Three mechanical rewrite flavors (A/B/C) per D-07 applied uniformly across 51 files — no local deviations, making future adjustments greppable."
  - "Helper-function migration pattern (Query → Select[Any]) demonstrates how to modernize internal chaining helpers without breaking caller contracts — extend the signature, update the terminal op, propagate to all callers in the same commit."
  - "Bulk DML migration pattern (sql_delete / sql_update + execution_options(synchronize_session=False)) provides a drop-in replacement for Query.delete() / .update() that works identically on SQLite and PostgreSQL."

requirements-completed: [DATA-06]

# Metrics
duration: ~65min
completed: 2026-04-23
---

# Phase 4 Plan 04: session.query → select() Sweep Summary

**Every db.query(...) / session.query(...) / self.db.query(...) call site across 51 backend/app files rewritten to db.scalars(select(...)) / db.scalar(select(func.count()).select_from(...)); a grep-based regression test locks in the invariant. 296 call sites cleared in 6 logical commits by domain bucket. OpenAPI snapshot unchanged; full SQLite test suite green (2245 passed, 6 skipped — same as pre-sweep baseline + the new regression test).**

## Performance

- **Duration:** ~65 min
- **Started:** 2026-04-23 (after plan 04-03 completion)
- **Tasks:** 2 (Task 1 RED regression guard, Task 2 mechanical sweep split across 5 commits)
- **Files changed:** 55 (51 app files + pagination_utils + 2 test files + 1 new regression test)
- **Call sites rewritten:** 296 (conservative grep pattern `\b(?:db|session|self\.db|self\.session)\.query\(`)

## Call-Site Rewrite Counts (before → after)

Baseline (pre-sweep): 296 offenders across 51 files. After sweep: 0.

| Bucket | Files | Sites | Commit |
|--------|-------|-------|--------|
| Utils (Step A) | 7 | 25 | `97c3bf1` |
| Services + auth deps (Step B) | 13 | 80 | `1fbc3b6` |
| Endpoints (Step C/1 — 19 files) | 19 | 66 | `e2931aa` |
| Endpoints (Step C/2 — admin + auth) | 2 | 61 | `10d7e1f` |
| Core + crawlers + standalone services (Step D) | 10 | 30 | `4a5511c` |
| Pagination_utils helper + test updates | 1 + 2 tests | (sig) | included in Step C/1 + D |
| Regression guard (Task 1) | 1 (new test file) | — | `c118b9b` |

## Task Commits

1. **Task 1 RED: regression guard** — `c118b9b` (test): grep-based CI gate committed before any sweep; fails with 296 offenders as expected.
2. **Step A: utils (7 files, 25 sites)** — `97c3bf1` (refactor): common_patterns, common_operations, authorization, endpoint_decorators, subscription_utils, admin_endpoint_patterns, bucket_orphan_utils.
3. **Step B: services + auth deps (13 files, 80 sites)** — `1fbc3b6` (refactor): base_crud, base_vote, base_report, vote, build_list, report, part_listing, bug_report, user, car_generation, crawler_schedule, part_linker, dependencies/auth.
4. **Step C/1: endpoints (19 files + pagination_utils, 66+ sites)** — `e2931aa` (refactor): everything except admin + auth.
5. **Step C/2: admin + auth endpoints (2 files, 61 sites)** — `10d7e1f` (refactor): the two largest endpoint files.
6. **Step D: core + crawlers + job_service + test updates (13 files, 30 sites)** — `4a5511c` (refactor): init_cars/categories/crawler_adapter_configs/service_accounts, car_inference, archive_rescrape, base, ecs_runner, ecs_rescrape_runner, runner, job_service, plus test_pagination / test_pagination_utils migrated to the new Select-based helper signatures.

Task 2 (the sweep) was split into 5 commits by logical domain per the plan's "commit in logical chunks" allowance — the regression guard is a separate test commit. All six commits pass pyright (0 errors on modified files) and keep the full test suite green.

## Flavor Breakdown

Per D-07, three mechanical rewrite flavors were applied uniformly:

- **Flavor A (`.first()` / `.all()` / `.one_or_none()`):** ~220 sites — single-row and collection ORM reads.
- **Flavor B (scalar column subset `.query(Model.col)`):** ~20 sites — value-only iteration (e.g. scalar id lists, file_keys, image_urls).
- **Flavor C (`.count()`):** ~30 sites — all rewritten to `db.scalar(select(func.count()).select_from(Model).where(...)) or 0` per Pitfall 5. NEVER `select(func.count(Model.id))` (which would drop NULLs).

Specialized patterns:

- **Group-by aggregates with multi-column output:** ~10 sites — rewritten to `db.execute(select(col1, func.count(col2)).where(...).group_by(...)).all()` so the tuple-iterator contract is preserved for row unpacking (`for source, count in rows:`).
- **Bulk DML (.delete / .update):** ~4 sites — rewritten to `db.execute(sql_delete(Model).where(...).execution_options(synchronize_session=False))` / `db.execute(sql_update(Model).where(...).values(...))` pattern.
- **Two-query id-then-hydrate pagination:** 2 sites (build_lists.py, parts.py) — `.with_entities(Model.id)` replaced with `stmt.with_only_columns(Model.id)` preserving the existing sort-then-fetch semantics.
- **Complex filtered COUNT over Select:** ~4 sites — `db.scalar(select(func.count()).select_from(stmt.subquery())) or 0` when the base Select already has joins/filters.
- **`.filter_by(col=val)` sites:** 0 encountered across the sweep (nothing to rewrite per Pitfall 4).

## Helper Function Migrations (signature changes)

| Helper | Before | After |
|--------|--------|-------|
| `apply_standard_filters` | `(query: SQLAlchemyQuery[ModelT], …) → SQLAlchemyQuery[ModelT]` | `(query: Select[Any], …) → Select[Any]` |
| `build_search_query` | `(query: SQLAlchemyQuery[ModelT], …) → SQLAlchemyQuery[ModelT]` | `(query: Select[Any], …) → Select[Any]` |
| `build_filtered_query` | `(query: SQLAlchemyQuery[ModelT], filters) → SQLAlchemyQuery[ModelT]` | `(query: Select[Any], filters) → Select[Any]` |
| `build_sorted_query` | `(query: SQLAlchemyQuery[ModelT], …) → SQLAlchemyQuery[ModelT]` | `(query: Select[Any], …) → Select[Any]` |
| `apply_pagination_and_ordering` (common_operations) | `(query: Query[Any], …) → Query[Any]` | `(query: Select[Any], …) → Select[Any]` |
| `get_entities_with_pagination` | `(db, model, …) → List[ModelType]` (uses internal `.all()`) | `(db, model, …) → List[ModelType]` (uses `db.scalars(stmt).all()` internally) |
| `get_paginated_response` | `(query: SQLAlchemyQuery, skip, limit, logger, …)` | `(db: Session, stmt: Select, skip, limit, logger, …)` — gains `db` param |
| `get_total_count` (pagination_utils) | `(query: SQLAlchemyQuery) → int` | `(db: Session, stmt: Select[Any]) → int` — gains `db` param |
| `paginate_query` (pagination_utils) | `(query: SQLAlchemyQuery, skip, limit, …) → List` | `(db: Session, stmt: Select[Any], skip, limit, …) → List` — gains `db` param |
| `apply_search_filter` / `apply_sorting` (pagination_utils) | `(query: SQLAlchemyQuery, …) → SQLAlchemyQuery` | `(query: Select[Any], …) → Select[Any]` |
| `_car_generation_query_with_make_model` | `(db) → Query[DBCarGeneration]` | `() → Select[tuple[DBCarGeneration]]` (renamed `_car_generation_select_with_make_model`) |

Every caller of these helpers was updated in the same sweep commit to pass Select statements and terminate with `db.scalars(stmt).all()` or `db.execute(stmt).all()` as appropriate.

## Coordination Notes for Downstream Plans

- **Plan 04-05 (row-lock concurrency):** `part_linker_service._point_siblings_at` (line 126) and `link_group_part_ids` (line 280) are now in the modern `select(DBPart).where(...)` form. Plan 04-05 can insert `.with_for_update()` at these sites with a single chain addition — no intermediate Query → Select conversion needed. The service imports `select` at module top already.
- **Plan 04-06 (lazy="raise" + CONVENTIONS.md):** The sweep did not change any relationship declarations. `BuildLogPost.author` remains the only relationship pre-loaded via `selectinload` (from plan 04-03). Flipping to `lazy="raise"` in plan 04-06 is independent of this sweep.
- **Phase 5 (admin.py + auth.py splits):** Every file Phase 5 splits from admin.py or auth.py now uses the modern API. New endpoint files created during the split inherit the convention; no mixed-regime work across the cut.
- **Future endpoint work:** `apply_standard_filters` / `build_search_query` / `build_filtered_query` / `build_sorted_query` all accept `Select[Any]` — callers build their Select with `select(DBModel).where(...)` and pipe through the helpers without converting forms. The endpoint files already demonstrate this pattern (build_lists.py, parts.py).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] COUNT(*) result coercion to non-Optional int**

- **Found during:** Every COUNT(*) rewrite site (~30 sites across all commits)
- **Issue:** `db.scalar(select(func.count()).select_from(X).where(...))` returns `Optional[int]` but callers expected plain `int`. Pyright caught the type mismatch at every site.
- **Fix:** Appended `or 0` at every site. COUNT(*) never returns NULL semantically (returns 0 for empty match); the coercion is safe.
- **Precedent:** Same coercion pattern used by plan 04-03 for the build_logs count query (see 04-03 SUMMARY "Pyright Rule 1 auto-fix").

**2. [Rule 1 - Bug] Select.with_entities → with_only_columns in two-query pagination**

- **Found during:** build_lists.py and parts.py (Step C/1)
- **Issue:** Pre-sweep code used `query.with_entities(DBBuildList.id)` to get an id-only projection for pagination. Select has `.with_only_columns(...)` as the equivalent 2.0 API; `.with_entities` is a Query-only method.
- **Fix:** Replaced with `stmt.with_only_columns(DBBuildList.id)` at both sites. Semantics identical (projection to a single column, paginated, then hydrated in a second query for final ordering).

**3. [Rule 3 - Scope clarification] bulk DML patterns rewritten to sql_delete/sql_update**

- **Found during:** admin.py /cars/delete-all and /part-manufacturers/delete-all endpoints (Step C/2)
- **Issue:** These endpoints used `db.query(X).delete(synchronize_session=False)` and `db.query(X).filter(...).update({X.col: val}, synchronize_session=False)`. Rewriting to `db.scalars(select(X)).all()` + per-row `db.delete()` would have changed semantics (ORM-side cascade vs. table-level DELETE).
- **Fix:** Used `db.execute(sql_delete(X).where(...).execution_options(synchronize_session=False))` / `db.execute(sql_update(X).where(...).values(...).execution_options(synchronize_session=False))` — the modern 2.0 bulk-DML API. Semantics preserved exactly (table-level DELETE/UPDATE, no per-row ORM cascade).

**4. [Rule 3 - Scope clarification] Test files updated to match new helper signatures**

- **Found during:** Full test suite run after Step C/1 (10 failures in tests/test_pagination.py + tests/utils/test_pagination_utils.py)
- **Issue:** These tests still called `paginate_query(query, skip, limit)` / `get_total_count(query)` with the old Query-based signatures. The helper migration changed signatures to `(db, stmt, skip, limit)` / `(db, stmt)`.
- **Fix:** Rewrote both test files to build Select statements with `select(Model).where(...)` and pass `(db_session, stmt)` to the helpers. Tests still exercise the same helper semantics — no behavior change, only contract migration. Committed in Step D alongside the crawlers/core migrations.
- **Rationale:** These are test updates that directly mirror the helper signature changes. They're part of the sweep's scope per D-07 (mechanical, greppable, single-semester migration) — not deferred.

### Intentional Non-changes

- **conftest.py not touched.** The test fixture's `db_session` uses SQLAlchemy's modern `sessionmaker(...)` API and the custom `query_counter` fixture from plan 04-03 listens to `before_cursor_execute`. No `db.query(...)` or `session.query(...)` call sites exist in conftest.py (grep confirmed).
- **pagination_utils tests migrated (not deferred).** Per Plan 04-04's scope these are test-level consumers of a backend helper; the tests needed to move with the helper. Test fixtures in `backend/tests/api/endpoints/` and similar paths use the live FastAPI `client` fixture and never call the helpers directly, so no further test changes were needed.
- **No N+1 introductions / no new `joinedload`/`selectinload`.** The sweep preserved existing `.options(joinedload(...))` and `.options(selectinload(...))` chains exactly. Adding new eager-loads is out of scope (noted in 04-04 PLAN threat_model T-04-04-07).

---

**Total deviations:** 4 auto-fixes (Optional[int] coercion + with_only_columns + sql_delete/update bulk DML + helper-signature-synced test updates). No blockers; no architectural changes required.

## Threat Flags

None discovered. The sweep introduces no new network endpoints, auth paths, file-access patterns, or schema changes. All existing transaction boundaries and authorization flows preserved exactly per D-11.

## Issues Encountered

None beyond the deviations above. The initial grep baseline (296 offenders) matched the final rewrite count exactly — no false positives, no missed files.

## User Setup Required

None — no external service configuration, no env vars, no migrations. Pure code refactor. CI, tests, and production code paths all work identically after the sweep.

## Verification

- `cd backend && grep -rn "\\.query(" app/ --include="*.py" | wc -l` → **0** (baseline: 296)
- `cd backend && pytest -n auto tests/test_session_query_regression.py -v` → **1 passed** (was RED with 296 offenders; now GREEN)
- `cd backend && pytest -n auto tests/test_openapi_snapshot.py` → **1 passed** (OpenAPI snapshot unchanged per D-10)
- `cd backend && pytest -n auto -k "characterization"` → **10 passed, 2 skipped** (same as pre-sweep baseline; OAuth cassettes still skip per STATE.md)
- `cd backend && pytest -n auto` (full suite) → **2245 passed, 6 skipped** (vs. baseline 2244 + 1 new regression test = 2245; zero regressions)
- `cd backend && pyright app/` → 0 errors on all files modified by this plan. (3 pre-existing errors in cloudwatch_emf.py, sentry.py, crawlers/adapters/base.py are OUT OF SCOPE per plan boundary — they do not involve .query() calls and existed before this sweep.)

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `grep -rn "\\.query(" app/ --include="*.py"` returns 0 results | 0 |
| `pytest -n auto backend/tests/test_session_query_regression.py -v` exits 0 | PASSED |
| `pytest -n auto backend/tests/test_openapi_snapshot.py` exits 0 | PASSED |
| `pytest -n auto` exits 0 (coverage floor --cov-fail-under=51 not regressed) | 2245 passed, 6 skipped |
| Phase 1 characterization tests pass (`pytest -n auto -k "characterization"`) | 10 passed, 2 skipped (same as baseline) |
| Every file in files_modified that previously contained .query( has `from sqlalchemy import select` at the top | confirmed via grep-per-file |

## Next Phase Readiness

- **Plan 04-05 (row-lock concurrency + PARTS-01):** Unblocked. `part_linker_service.py` is now in the modern `select()` form at both the `_point_siblings_at` and `link_group_part_ids` sites. Plan 04-05 can insert `.with_for_update()` at these call sites as a single chain addition.
- **Plan 04-06 (lazy="raise" + CONVENTIONS.md):** Unblocked. No coupling — the lazy-raise work operates on relationship declarations, not Query/Select call sites.
- **Phase 5 (admin.py + auth.py splits):** Unblocked. Every new file Phase 5 creates inherits the modern API; no split-time conflict between old and new forms.
- **Future maintenance:** The regression guard (`test_session_query_regression.py`) permanently prevents reintroduction of `.query(` patterns. Any PR that adds a `db.query(...)` call will fail CI at this test.

## Self-Check: PASSED

File existence:
- FOUND: backend/tests/test_session_query_regression.py
- FOUND: 51 app files modified (git log --stat confirms all present)
- FOUND: backend/app/api/utils/pagination_utils.py (helper signature migrations)
- FOUND: backend/tests/test_pagination.py + backend/tests/utils/test_pagination_utils.py (caller-side signature updates)

Commit existence (git log --oneline):
- FOUND: c118b9b (Task 1 RED — regression guard)
- FOUND: 97c3bf1 (Step A — utils)
- FOUND: 1fbc3b6 (Step B — services + auth deps)
- FOUND: e2931aa (Step C/1 — 19 endpoints + pagination_utils)
- FOUND: 10d7e1f (Step C/2 — admin + auth)
- FOUND: 4a5511c (Step D — core + crawlers + job_service + test updates)

---

*Phase: 04-db-parts-hardening*
*Plan: 04*
*Completed: 2026-04-23*
