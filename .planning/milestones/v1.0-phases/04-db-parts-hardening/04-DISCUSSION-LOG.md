# Phase 4: DB & Parts Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 04-db-parts-hardening
**Mode:** auto (recommended defaults selected for all gray areas)
**Areas discussed:** Concurrency test infrastructure, session.query() migration scope, FK index audit methodology, Pool configuration reconciliation, Build-log eager creation cleanup, lazy="raise" scope, Migration downgrade-testing workflow, Query-count regression test, PARTS-02 car_inference maintainability, PARTS-03 canonical integration coverage

---

## Gray Area 1: Concurrency test infrastructure (DATA-03 / DATA-04 / PARTS-01)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Postgres Docker service side-car in CI + `@pytest.mark.postgres` marker | Most faithful to prod — exercises real FOR UPDATE row locks; marker keeps SQLite as default for the rest of the suite | ✓ |
| B. Simulate locks on SQLite with `threading.Lock` | Lowest infra cost but proves nothing about prod-Postgres behavior | |
| C. Skip concurrency test entirely; rely on code review | Fails the REQUIREMENTS literal for DATA-04 ("verified by a concurrency test") | |

**User's choice:** Option A (recommended — closes STATE.md Phase-4 decision point on Postgres Docker test env).
**Notes:** SQLite does not implement `SELECT ... FOR UPDATE` semantics; testing on SQLite would pass regardless of whether `with_for_update()` was actually added to the part linker. Postgres side-car is the only way to verify the fix. Marker keeps scope narrow — only the concurrency test opts in; the rest of the suite stays SQLite for speed.

---

## Gray Area 2: `session.query()` → `select()` migration scope (DATA-06)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Single atomic sweep PR covering all 304 call sites across ~20 files | Matches Phase 3 QUAL-07 logger-sweep pattern; regression grep-guard goes green in the same PR | ✓ |
| B. Per-file incremental PRs | Smaller review surface but leaves CI with grep-guard disabled until final PR | |
| C. Incrementally inside base-service helpers; leave verbose endpoints for later | Creates two-regime code (new vs. old API coexist) — rejected | |

**User's choice:** Option A (recommended — mechanical sweep proved workable in Phase 3).
**Notes:** The grep regression test (D-09) cannot go CI-green until the sweep is complete. Single-PR is the lowest-friction path to a clean CI gate. File priority order (D-08) surfaces bugs at the shared-helpers layer first.

---

## Gray Area 3: FK index audit methodology (DATA-05)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Declare `index=True` / `Index()` in ORM models; let `alembic --autogenerate` emit CREATE INDEX | Per CLAUDE.md autogenerate-only rule; Phase 1 naming_convention inheritance is automatic | ✓ |
| B. Hand-write the index-add migration | Violates CLAUDE.md autogenerate-only rule | |
| C. Use alembic autogenerate just to surface drift; add indexes in a follow-up milestone | Defers the DATA-05 acceptance criterion | |

**User's choice:** Option A (recommended — aligns with CLAUDE.md + inherits naming_convention).
**Notes:** Phase 1 SAFE-09 landed `MetaData(naming_convention=...)`. All new indexes auto-get `ix_<table>_<column>` names without manual intervention. Exception rule (D-14) for FKs already covered by composite-index left-prefix (e.g., `vote.user_id`) prevents duplicate indexes.

---

## Gray Area 4: Production pool configuration (DATA-07)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Take REQ-07 literal: `pool_size=50, max_overflow=???` | Ambiguous — REQ doesn't specify max_overflow, would require redesigning pool envelope | |
| B. Keep `pool_size=25 + max_overflow=75 = 100`; change pool_recycle 3600→1800 | Total capacity already exceeds REQ's pool_size=50 floor; preserves Phase 3 D-14 crawler worker formula | ✓ |
| C. Bump pool_size to 50, keep max_overflow=75 (total 125) | Over-allocates DB connections relative to current traffic + crawler parallelism | |

**User's choice:** Option B (recommended — deviation from REQ literal documented in D-18, D-21).
**Notes:** REQ-07's literal `pool_size=50` is already exceeded by current `25 + 75 = 100` total capacity. Phase 3 D-14's crawler worker formula depends on the existing trio; changing pool_size ripples into crawler config. Deviation is deliberate and safer for crawler subsystem.

---

## Gray Area 5: Build-log eager creation (DATA-08)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Delete lazy branches in `build_logs.py`; one-shot backfill migration for legacy build_lists | Gives a clean invariant (every build_list has a build_log); matches REQ-08 literal | ✓ |
| B. Leave lazy branches with a warning log | Preserves debt; doesn't achieve REQ-08 "inconsistent-state branch eliminated" | |
| C. Delete lazy branches; 404 on build logs for legacy build_lists (no backfill) | Data loss for existing users with build_lists lacking a build_log | |

**User's choice:** Option A (recommended — clean invariant, one-shot data migration).
**Notes:** Eager-create already exists in `build_list_service.py:82-88`. The target is deleting dead fallback code at `build_logs.py:86-98` and `:191-201`. Separate the data migration from the code-change PR (D-25) for clean revertability.

---

## Gray Area 6: `lazy="raise"` scope (DATA-10)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Global `lazy="raise"` on every relationship | Aggressive; fixture earthquake across 50+ test files + every endpoint | |
| B. Selective `lazy="raise"` on N+1-prone relationships (Post.author, BuildList.*) | Scope-contained; catches actual debt without collateral damage | ✓ |
| C. Global default with per-query `.options(selectinload(...))` escape hatches | Requires auditing every ORM use site; effectively equivalent to A | |

**User's choice:** Option B (recommended — targeted at known N+1-prone relationships).
**Notes:** Each `lazy="raise"` addition (D-30) pairs with a green `.options(selectinload(...))` in every caller path. DATA-01's build-log fix is the first landing point for this pattern.

---

## Gray Area 7: Migration downgrade-testing workflow (DATA-09)

| Option | Description | Selected |
|--------|-------------|----------|
| A. CONVENTIONS.md documentation-only update | Lightweight; aligns with REQ-09 literal ("documented to require downgrade testing") | ✓ |
| B. CI step automating `alembic upgrade → downgrade → upgrade` on every migration PR | Stronger gate but requires Postgres side-car availability on every migration CI run | |
| C. Pure manual workflow; no docs | Leaves convention tribal | |

**User's choice:** Option A (recommended — pairs with Gray Area 1 Postgres infra, defers CI automation).
**Notes:** CI-automated downgrade testing deferred per Phase 4 Deferred Ideas. Documentation establishes the convention; future phase can automate.

---

## Gray Area 8: Query-count regression test (DATA-01 / DATA-02)

| Option | Description | Selected |
|--------|-------------|----------|
| A. SQLAlchemy `event.listen(engine, "before_execute", ...)` fixture in conftest.py | No new dep; composes with pytest-xdist | ✓ |
| B. `pytest-sqlalchemy` plugin | Adds a dep for a single use case | |
| C. Manual log inspection | Not a regression guard | |

**User's choice:** Option A (recommended — minimal surface, reusable fixture).
**Notes:** Counter is per-test via context manager. Test is SQLite-backed (D-34) — query-count semantics match Postgres closely enough for catching ORM-usage regressions.

---

## Gray Area 9: PARTS-02 car_inference maintainability

| Option | Description | Selected |
|--------|-------------|----------|
| A. Docstring on `AMBIGUOUS_STANDALONE_CODES` + regression test with fixed vectors | REQ-02 literal: "documented + a regression test pins current behavior; no new ML logic" | ✓ |
| B. Replace with ML-based disambiguation | Explicitly deferred to v2 (PARTS-V2-01) | |
| C. Docstring only | Misses REQ-02's regression-test requirement | |

**User's choice:** Option A (recommended — pins current behavior, maintainability-only).
**Notes:** Regression test documents "this is how ambiguity resolution behaves today," not "this is correct." Downstream PARTS-V2-01 will rewrite this test when ML disambiguation lands.

---

## Gray Area 10: PARTS-03 canonical-flow integration coverage

| Option | Description | Selected |
|--------|-------------|----------|
| A. SQLite-only integration tests for create/link/unlink/merge | Logic tests; row-lock concurrency covered separately by DATA-04 Postgres test | ✓ |
| B. Postgres-backed (reuse Gray Area 1 infra) | Over-engineers simple algorithm tests | |
| C. Combined concurrency + integration in one test suite | Muddles two concerns — logic correctness vs. lock correctness | |

**User's choice:** Option A (recommended — keep concerns separated).
**Notes:** Canonical-logic correctness is data/algorithm, not lock-dependent. Uses existing SQLite fixtures.

---

## Claude's Discretion

- Exact naming of the `query_counter` fixture and the per-test counter object's public API
- Whether to add a dedicated test file per DATA-requirement or pack related tests into existing files
- Exact SQL dialect for the build-log backfill INSERT (hand-written `op.execute` in the Alembic migration)
- The selectinload implementation exact shape (e.g., `load_only(User.id, User.username, User.image_urls)` to avoid fetching the full User row)
- Whether the `query_counter` counts all SQL statements or just `SELECT` statements
- Whether the FK-index-only migration commits alongside an `autogenerate_diff.md` note or just lives as the standalone revision

## Deferred Ideas

### Deferred to Phase 5 or later
- Global `lazy="raise"` sweep across every relationship — scope-contained in Phase 4
- CI-automated migration downgrade testing — docs-only in Phase 4; infra follow-up
- `car_inference` ML-based disambiguation (PARTS-V2-01) — v2
- Optimistic concurrency control / `version_id_col` (PARTS-V2-03) — v2
- Async SQLAlchemy migration (PERF-V2-03) — v2
- Query-result caching / Redis (PERF-V2-01) — v2
- Retroactive rename of historic constraints to naming_convention — inherited deferral from Phase 1
- Admin UI for part-curation-time ambiguity resolution (PARTS-V2-02) — v2

### Deferred to late Phase 5 or Phase 6
- Cleanup of unused `from sqlalchemy.orm import Session` imports post-sweep
- Benchmarking the pool_recycle 3600→1800 change in production
- Global `__table_args__` style normalization across models

### Noted but not a Phase 4 deliverable
- Postgres readonly replica (PERF-V2-02) — v2
- Alembic `--sql` mode for offline migration review
- `get_logger` export removal — Phase 3 D-36 inherited deferral
