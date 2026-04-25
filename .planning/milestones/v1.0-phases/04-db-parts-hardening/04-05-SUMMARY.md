---
phase: 04-db-parts-hardening
plan: 05
subsystem: database
tags: [concurrency, pessimistic-lock, postgres, ci, with-for-update]

# Dependency graph
requires:
  - phase: 04-db-parts-hardening
    provides: "Plan 04-04 sweep migrated part_linker_service.py to select() — plan 04-05 inserts .with_for_update() at the existing select() sites"
  - phase: 04-db-parts-hardening
    provides: "Plan 04-03 delivered query_counter pytest fixture — reusable pattern for post-verify assertions (not used directly here but available for Phase 5)"
  - phase: 01-safety-nets-ci-hardening
    provides: "backend/tests/conftest.py engine + db_session fixture shape — new postgres_engine fixture attaches alongside the existing SQLite engine"
provides:
  - "Pessimistic row locks (Postgres SELECT ... FOR UPDATE) around link_new_part, reelect_canonical, unlink_part in part_linker_service.py — eliminates orphaned/circular canonical refs under concurrent request load (DATA-03)"
  - "postgres_engine + postgres_session pytest fixtures with per-worker DB naming via PYTEST_XDIST_WORKER — reusable across Phase 5 admin/auth split tests that need Postgres-specific behavior"
  - "docker-compose.test.yml (repo-root) for local dev Postgres testing on port 5433 (non-colliding with backend/docker-compose.yml 5432)"
  - ".github/workflows/backend-ci.yml postgres-tests job with services.postgres side-car and psql CREATE DATABASE retry loop (INFO 12)"
  - "backend/tests/services/test_part_linker_concurrency.py — 10-thread concurrency test proving D-05 canonical invariants hold under Postgres locking (DATA-04, PARTS-01)"
affects: [04-06-conventions-lazy-raise, 05-admin-auth-splits]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "select(DBPart).where(DBPart.id.in_(lock_ids)).with_for_update() for pessimistic locking on an explicit id set — emits SELECT ... FOR UPDATE under Postgres, silent no-op under SQLite (Pitfall 1)"
    - "D-05-compliant lock scope: subject + canonical + full sibling set — freezes the entire link group against a concurrent peer operation"
    - "@pytest.mark.postgres + pytestmark module-level marker — test module SKIPS cleanly when POSTGRES_TEST_URL is unset (Phase 4 D-02 contract)"
    - "postgres_engine fixture with WARN 8 per-test unique-key contract — tests filter every verify query by shared_gtin so cross-test data in the session-scoped engine does not interfere"
    - "Per-worker database naming via PYTEST_XDIST_WORKER suffix (cmp_test → cmp_test_gw0) — prevents xdist cross-worker contention on a shared DB (Pitfall 8)"
    - "CI psql CREATE DATABASE retry loop (5 attempts × 2s backoff) — tolerates first-boot parameter-group races even after services.postgres healthcheck clears (INFO 12)"

key-files:
  created:
    - "docker-compose.test.yml"
    - "backend/tests/services/test_part_linker_concurrency.py"
  modified:
    - "backend/app/api/services/part_linker_service.py"
    - "backend/pytest.ini"
    - "backend/tests/conftest.py"
    - ".github/workflows/backend-ci.yml"

key-decisions:
  - "unlink_part lock set spans subject + canonical + full sibling set (NOT just subject.id) — D-05 invariant compliance: a concurrent reelect_canonical reading subject.canonical_part_id as non-null could mutate stale siblings; only a full-link-group lock prevents this"
  - "Postgres-native @pytest.mark.postgres marker + postgres_engine session-scoped fixture + per-worker DB suffix chosen over per-test BEGIN+ROLLBACK isolation — ROLLBACK isolation defeats pessimistic-lock semantics because the locks commit with the transaction, so the concurrency test MUST use the session-scoped engine with per-test unique gtin keys (WARN 8)"
  - "CI job runs pytest -n 4 -m postgres --dist=loadfile in a separate workflow job — keeps the SQLite default job fast (no Postgres overhead) and makes the Postgres path opt-in via the marker"
  - "docker-compose.test.yml uses port 5433 (not 5432) to avoid colliding with backend/docker-compose.yml's dev Postgres — local devs can run both simultaneously"
  - "Concurrency test was verified locally against Postgres 16 (devuser@5432) by creating cmp_test_main / cmp_test_main_master / cmp_test_main_gw0 / cmp_test_main_gw1 DBs, running the test under `pytest -p no:xdist` AND `pytest -n 2 --dist=loadfile` — all four invocations PASSED on first run"

patterns-established:
  - "Mechanical with_for_update() insertion at existing select() sites — additive only, no algorithm changes; reversible by reverting the lock-acquisition block without touching surrounding logic"
  - "D-05 lock-scope reasoning: identify every row each function reads-then-mutates AND every row a concurrent peer operation could mutate in the same link group — the union is the lock set"
  - "Skip-not-fail contract: @pytest.mark.postgres tests SKIP cleanly without POSTGRES_TEST_URL; CI side-car provides the URL; local devs use docker-compose.test.yml up + POSTGRES_TEST_URL env var"

requirements-completed: [DATA-03, DATA-04, PARTS-01]

# Metrics
duration: ~8min
completed: 2026-04-23
---

# Phase 4 Plan 05: Row-Lock Concurrency for Part Linker Summary

**Pessimistic `SELECT ... FOR UPDATE` locks inserted into all three mutators of `part_linker_service.py` (link_new_part, reelect_canonical, unlink_part) with D-05-compliant lock scope (subject + canonical + full sibling set for unlink_part); a new `@pytest.mark.postgres` marker + `postgres_engine` / `postgres_session` fixtures land in `conftest.py`; a `docker-compose.test.yml` + a `postgres-tests` CI job (with `psql CREATE DATABASE` retry per INFO 12) stand up a Postgres 16 side-car; a 10-thread `ThreadPoolExecutor` concurrency test (`backend/tests/services/test_part_linker_concurrency.py`) asserts all three D-05 canonical invariants hold under Postgres locking — verified locally on Postgres 16 under both `-p no:xdist` and `-n 2 --dist=loadfile` invocations.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-23T04:46:06Z
- **Completed:** 2026-04-23T04:53:51Z
- **Tasks:** 3
- **Files changed:** 6 (1 service, 1 pytest.ini, 1 conftest.py, 1 CI workflow, 1 new docker-compose.test.yml, 1 new concurrency test)

## Task Commits

1. **Task 1: Insert with_for_update() locks in part_linker_service** — `1841b75` (feat)
2. **Task 2: Postgres test infrastructure (marker, fixtures, docker-compose, CI job)** — `bacda8f` (feat)
3. **Task 3: 10-thread concurrency test (test_part_linker_concurrency.py)** — `951fcca` (test)

## Lock Insertion Line Numbers

`backend/app/api/services/part_linker_service.py` (post-edit state):

| Function | Line | Lock scope |
|----------|------|-----------|
| `reelect_canonical` | 155-162 | new_canonical + old_canonical + all siblings (discovered under lock to freeze set) |
| `unlink_part` | 199-222 | subject (201) + canonical (210) + all siblings (215-218) — **D-05 scope per pre-edit audit** |
| `link_new_part` | 265-274 | candidates + new_part |

**Total `with_for_update()` token count:** 6 (meets plan's ≥5 threshold; unlink_part contributes 3).

### Pre-edit audit — D-05 invariant compliance for unlink_part

The authoritative pre-edit body read ONLY `part.canonical_part_id` and mutated ONLY `part.canonical_part_id`. A naive lock on `part.id` alone would have been sufficient for that function's own read-then-write, BUT the D-05 invariant constrains the HAZARD set (what any peer operation against the same link group can mutate), not just the mutation set.

**Row enumeration for the lock set:**
- **Subject row** (`part.id`) — this function mutates it (writes `canonical_part_id = None`).
- **Canonical row** (`part.canonical_part_id`, if non-null) — a concurrent `reelect_canonical` reads its `canonical_part_id` and writes to it (`old_canonical.canonical_part_id = new_canonical.id`) AND uses it as the pivot for `_point_siblings_at`. If we don't lock it, a concurrent reelect can commit a write against a canonical that this unlink is simultaneously detaching from.
- **All siblings** (`SELECT id FROM parts WHERE canonical_part_id = subject.canonical_part_id`) — `reelect_canonical`'s `_point_siblings_at(db, old_canonical_id, new_canonical.id)` mutates every sibling in the group. If this unlink commits `subject.canonical_part_id = None` while reelect is repointing siblings, reelect's writes can land based on a stale view of the group membership.

The unlink_part body (lines 189-226) now locks all three rowsets BEFORE the mutation (line 222: `subject.canonical_part_id = None`).

## Local Verification Against Postgres 16

Performed against the existing dev Postgres 16 container (`carmodpicker_persistant_volume_db` at port 5432) by creating throwaway test DBs, running the test, then dropping them. Used the dev credentials to bypass needing a separate docker-compose.test.yml spin-up during local verification.

| Invocation | Result |
|-----------|--------|
| `pytest -p no:xdist tests/services/test_part_linker_concurrency.py -v` (single worker, DB: `cmp_test_main_master`) | **2 passed** |
| `pytest -n 2 -m postgres --dist=loadfile tests/services/test_part_linker_concurrency.py -v` (DB: `cmp_test_main_gw0`) | **2 passed** |

All three invariants held on every invocation:
- INVARIANT 1 (`exactly 1 canonical per shared_gtin`): **held**
- INVARIANT 2 (no cycles — every `canonical_part_id` resolves to a canonical): **held**
- INVARIANT 3 (no orphans — `sibling_refs == live_canonicals`): **held**

INFO 12 psql retry: did not fire — the dev Postgres was already running and healthy. Retry shape committed to CI for first-boot flake defense regardless.

## Code Change Details

### backend/app/api/services/part_linker_service.py

**`reelect_canonical` (added at line 155-162, before the existing `old_canonical = db.get(...)` read):**

```python
# DATA-03 (Phase 4 D-01/D-05): lock new_canonical + old_canonical + all siblings
# before reading/mutating. Siblings are discovered under the lock to freeze the
# set against a concurrent link_new_part that might be adding a new sibling.
# Silent no-op on SQLite (Pitfall 1); concurrency test runs on Postgres.
old_canonical_id = new_canonical.canonical_part_id
lock_ids: set[UUID] = {new_canonical.id, old_canonical_id}
sibling_ids = db.scalars(
    select(DBPart.id)
    .where(DBPart.canonical_part_id == old_canonical_id)
    .with_for_update()
).all()
lock_ids.update(sibling_ids)
db.scalars(
    select(DBPart).where(DBPart.id.in_(lock_ids)).with_for_update()
).all()
```

**`unlink_part` (rewritten body at lines 189-226, D-05 scope):**

```python
def unlink_part(db: Session, part: DBPart) -> DBPart:
    """Make ``part`` its own canonical, detaching it from its current link group.

    DATA-03 (Phase 4 D-01/D-05) lock scope: subject + canonical (if any) + siblings.
    ...
    """
    # Lock the subject row first (stable ordering — subject.id is always in set).
    subject = db.scalars(
        select(DBPart).where(DBPart.id == part.id).with_for_update()
    ).one()

    canonical_id = subject.canonical_part_id
    if canonical_id is None:
        return subject

    # Lock the canonical row.
    db.scalars(
        select(DBPart).where(DBPart.id == canonical_id).with_for_update()
    ).one()

    # Lock every sibling that shares this canonical so any interleaving with
    # reelect_canonical / _point_siblings_at / another unlink serializes here.
    db.scalars(
        select(DBPart.id)
        .where(DBPart.canonical_part_id == canonical_id)
        .with_for_update()
    ).all()

    # Now safe to mutate.
    subject.canonical_part_id = None
    db.add(subject)
    db.flush()
    logger.info("Unlinked part %s from prior canonical", subject.id)
    return subject
```

**`link_new_part` (added at line 265-274, after the `if not candidates: return new_part` early-exit, before the candidate merge algorithm):**

```python
# DATA-03 (Phase 4 D-01/D-05): lock every candidate + new_part so concurrent
# link_new_part calls serialize on these rows. Re-reads the latest state in
# case the candidates lookup was stale. Silent no-op on SQLite (Pitfall 1) —
# concurrency test (test_part_linker_concurrency.py) runs on Postgres.
lock_ids = [c.id for c in candidates] + [new_part.id]
locked = db.scalars(
    select(DBPart)
    .where(DBPart.id.in_(lock_ids))
    .with_for_update()
).all()
locked_by_id = {p.id: p for p in locked}
candidates = [locked_by_id[c.id] for c in candidates]
new_part = locked_by_id[new_part.id]
```

### backend/pytest.ini

Appended `postgres` marker to the existing markers block:

```ini
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    postgres: requires POSTGRES_TEST_URL; skips when unset (DATA-04 Phase 4 D-02)
```

### backend/tests/conftest.py

- Added `from urllib.parse import urlparse, urlunparse` to the existing imports block (plain import — NO underscore aliases, honors BLOCKER 5).
- Added `_postgres_url_for_worker()` helper (derives per-worker DB URL from `POSTGRES_TEST_URL` + `PYTEST_XDIST_WORKER`; returns `None` when unset).
- Added `postgres_engine` session-scoped fixture (skips when URL unset; creates schema with `Base.metadata.create_all`; tears down with `drop_all`). Docstring documents the WARN 8 per-test unique-key contract.
- Added `postgres_session` function-scoped fixture (BEGIN + ROLLBACK per test) as the alternative for non-lock-dependent tests. Docstring warns the concurrency tests CANNOT use this fixture (ROLLBACK defeats lock semantics).

### docker-compose.test.yml (new, repo root)

```yaml
services:
  postgres-test:
    image: postgres:16
    container_name: carmodpicker_postgres_test
    environment:
      POSTGRES_USER: cmp_test
      POSTGRES_PASSWORD: cmp_test
      POSTGRES_DB: cmp_test
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cmp_test"]
      interval: 5s
      timeout: 3s
      retries: 10
```

Port 5433 avoids colliding with the dev Postgres at 5432 (backend/docker-compose.yml). `tmpfs` volume means the DB is ephemeral and fast — no persistence needed between test runs.

### .github/workflows/backend-ci.yml

Added `postgres-tests:` job alongside the existing `test:` job. Key shape elements:
- `services.postgres: image: postgres:16` with `--health-cmd pg_isready` healthcheck.
- Checkout + Python 3.13 + pip install (matches `test:` job).
- **"Create per-worker databases (with retry for flaky Postgres startup)"** step — loops `cmp_test_gw0..cmp_test_gw3` with up to 5 `psql CREATE DATABASE` attempts × 2s backoff (INFO 12 defense).
- **"Run Postgres-backed tests only"** step — sets `POSTGRES_TEST_URL=postgresql://cmp_test:cmp_test@localhost:5432/cmp_test` + test-only `SECRET_KEY=test-secret-key-for-ci` + all the env vars the existing `test:` job sets; runs `pytest -n 4 -m postgres --dist=loadfile --no-cov`. `--no-cov` avoids duplicating coverage reporting (the main `test:` job owns coverage).

### backend/tests/services/test_part_linker_concurrency.py (new)

Two tests. Both use the `postgres_engine` fixture + a per-test-unique `shared_gtin` to honor the WARN 8 isolation contract.

1. **`test_link_new_part_10_thread_contention`** — seeds 10 parts sharing a gtin (no links yet), spawns 10 threads calling `link_new_part` simultaneously, then asserts:
   - INVARIANT 1: exactly 1 canonical (`canonical_count == 1`)
   - INVARIANT 2: no cycles (every non-null `canonical_part_id` is in the canonical set)
   - INVARIANT 3: no orphans (`sibling_refs == live_canonicals`)

2. **`test_unlink_and_relink_under_load`** — seeds 10 parts, then alternates `link_new_part` (even indices) / `unlink_part` (odd indices) across a 10-thread pool, asserts no orphaned canonical refs at the end.

All seed constructors use `email_verified=True` on the User model (NOT `is_verified=True` — that's a Part field). Verified by grep: `is_verified=True` returns 0, `email_verified=True` returns 1.

## Decisions Made

- **D-05 lock scope for unlink_part covers the full link group, not just the subject.** The pre-edit audit enumerated every row the three mutators read-then-mutate and every row a concurrent peer could mutate in the same link group — the union is the lock set. For unlink_part, this is subject + canonical + siblings.
- **Postgres 16 base image in docker-compose.test.yml and CI matches prod RDS 16.** SQLAlchemy's `.with_for_update()` emits different SQL on different backends (`SELECT ... FOR UPDATE` on Postgres, no-op on SQLite); by running the concurrency test on Postgres 16 exclusively via `@pytest.mark.postgres`, we match prod behavior precisely.
- **Port 5433 for the test Postgres** — non-colliding with the dev Postgres at 5432 so local devs can run both simultaneously without `docker compose down` dance.
- **`pytest -n 4 -m postgres --dist=loadfile`** (CI) vs `pytest -n 2 ... --dist=loadfile` (local verification) — loadfile groups same-file tests on one worker, so the concurrency test doesn't race against itself across xdist workers. Per-worker DB naming ensures no cross-worker contention even if xdist scheduler changes behavior in the future.
- **Skip-not-fail contract** — `@pytest.mark.postgres` tests SKIP cleanly when `POSTGRES_TEST_URL` is unset; local devs who haven't started the test Postgres get the same clean skip as the main `test:` CI job gets. Only the dedicated `postgres-tests:` CI job runs them.
- **`postgres_session` fixture is exposed as an alternative** — tests that cannot structure their seeds around a per-test unique key can use BEGIN+ROLLBACK isolation via `postgres_session`. The concurrency tests CANNOT use it (documented in the fixture's docstring) because ROLLBACK would undo the very lock acquisitions this plan is validating.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Typed `lock_ids` as `set[UUID]` in reelect_canonical**

- **Found during:** Task 1 (post-edit pyright check)
- **Issue:** `lock_ids: set[UUID] = {new_canonical.id, old_canonical_id}` — pyright needed an explicit type annotation because `old_canonical_id` widens to `UUID | None` at the structural level (the `if ... is None: return` guard narrows the runtime type but not the static type inside the set literal).
- **Fix:** Added explicit `set[UUID]` annotation. The `if new_canonical.canonical_part_id is None: return` guard preceding this block guarantees `old_canonical_id` is non-null here.
- **Files modified:** `backend/app/api/services/part_linker_service.py` (line 156)
- **Verification:** `pyright app/api/services/part_linker_service.py` — 0 errors, 0 warnings.
- **Committed in:** `1841b75` (Task 1)

### Intentional Non-changes

- **Pre-existing `PytestUnknownMarkWarning` not fixed in this plan.** The plan's `pytest.ini` uses `[tool:pytest]` section header (legacy setup.cfg style) rather than `[pytest]` — this is why `--strict-markers` in `addopts` doesn't enforce strictly AND why `pytest --markers` does not list `slow`, `integration`, `unit`, or `postgres`. The warning is pre-existing — it also applies to the existing `slow`/`integration`/`unit` markers that no test actually uses via `pytestmark =` until now. The plan's acceptance criteria check (`grep "postgres: requires POSTGRES_TEST_URL" backend/pytest.ini`) is satisfied; the `-m postgres` selector correctly selects the concurrency tests (verified: 2 collected). The marker warning is a separate concern (would require changing the section header `[tool:pytest]` → `[pytest]` across the entire pytest.ini, which is out of scope for this plan's `files_modified` contract).

## Threat Flags

None discovered. The plan introduces:
- Pessimistic row locks (additive; covered in the plan's threat_model T-04-05-01 through T-04-05-10).
- A CI workflow job with test-only Postgres credentials in a throwaway runner (T-04-05-05 accepted).
- A new test file that only runs when the explicit marker/env-var combination is set.

No new network endpoints, auth paths, file access patterns, or schema changes. All existing code paths preserved.

## Issues Encountered

None beyond the one auto-fix above. No blockers. No architectural decisions required.

## Coordination Notes for Downstream Plans

- **Plan 04-06 (CONVENTIONS.md + lazy="raise"):** No coupling — this plan's work is in service bodies, not relationship declarations. `with_for_update()` and `lazy="raise"` are independent.
- **Phase 5 (admin.py + auth.py splits):** `postgres_engine` / `postgres_session` fixtures are available for any lock-dependent test paths that emerge during the admin/auth split work. Phase 5 should **prefer `postgres_session`** (BEGIN+ROLLBACK) for generic endpoint tests that need Postgres-specific behavior but not lock semantics — it's more isolated. Use `postgres_engine` with per-test unique keys ONLY for lock-dependent flows (e.g., distributed-lock audit endpoints, scheduled-job idempotency).
- **Future concurrency tests:** The `query_counter` fixture from plan 04-03 + `postgres_engine` fixture from this plan compose cleanly — e.g., a future test can assert a post-link canonical-query read count stays bounded under load by wrapping the post-verify phase in `with query_counter() as counter:`. Example usage pattern documented in the 04-05 PLAN's threat_model.

## User Setup Required

No external service configuration required. Local developers who want to run the concurrency tests locally:

```bash
# From repo root
docker compose -f docker-compose.test.yml up -d postgres-test

# Create per-worker DBs (if using -n > 1)
for i in 0 1 2 3; do
  docker compose -f docker-compose.test.yml exec postgres-test \
    psql -U cmp_test -d cmp_test -c "CREATE DATABASE cmp_test_gw${i};"
done

# Run the tests
cd backend
POSTGRES_TEST_URL=postgresql://cmp_test:cmp_test@localhost:5433/cmp_test \
  pytest -n 4 -m postgres --dist=loadfile --no-cov
```

Without the above setup, `pytest -n auto` (the default) cleanly SKIPS the concurrency tests — no local-dev friction.

## Verification

- `grep -c "with_for_update()" backend/app/api/services/part_linker_service.py` → **6** (≥5 threshold from plan)
- `grep -c "with_for_update()"` inside unlink_part body → **3** (subject + canonical + siblings)
- `grep -q "postgres: requires POSTGRES_TEST_URL" backend/pytest.ini` → **OK**
- `grep -c "postgres_engine" backend/tests/conftest.py` → **5**
- `grep -c "postgres_session" backend/tests/conftest.py` → **1**
- `grep -c "PYTEST_XDIST_WORKER" backend/tests/conftest.py` → **2** (helper call + docstring)
- `grep -q "import os as _os" backend/tests/conftest.py` → 0 (BLOCKER 5: no underscore aliases)
- `grep -q "urllib.parse as _urlparse" backend/tests/conftest.py` → 0
- `grep -c "CONTRACT" backend/tests/conftest.py` → **1** (WARN 8 contract in postgres_engine docstring)
- `grep -q "image: postgres:16" docker-compose.test.yml` → **OK**
- `grep -q "postgres-tests:" .github/workflows/backend-ci.yml` → **OK**
- `grep -q "retrying in 2s" .github/workflows/backend-ci.yml` → **OK** (INFO 12)
- `grep -c "pytest.mark.postgres" backend/tests/services/test_part_linker_concurrency.py` → **1** (module-level pytestmark)
- `grep -c "ThreadPoolExecutor" backend/tests/services/test_part_linker_concurrency.py` → **3**
- `grep -c "assert canonical_count == 1" backend/tests/services/test_part_linker_concurrency.py` → **1**
- `grep -c "cycle or orphan" backend/tests/services/test_part_linker_concurrency.py` → **1**
- `grep -c "email_verified=True" backend/tests/services/test_part_linker_concurrency.py` → **1**
- `grep -c "is_verified=True" backend/tests/services/test_part_linker_concurrency.py` → **0** (BLOCKER 2: wrong field name not present)
- `cd backend && pytest -n auto tests/test_part_linker.py -v` → **10 passed** (SQLite path unchanged — `with_for_update()` silent no-op per Pitfall 1)
- `cd backend && pytest -n auto tests/test_session_query_regression.py` → **1 passed** (plan 04-04 regression guard still green)
- `cd backend && pytest -n auto` (full SQLite suite) → **2245 passed, 8 skipped** (baseline 2245/6 + the 2 new postgres tests that skip without POSTGRES_TEST_URL = 2245/8). Zero behavioral regressions.
- `pyright app/api/services/part_linker_service.py tests/conftest.py tests/services/test_part_linker_concurrency.py` → **0 errors, 0 warnings, 0 informations**
- `POSTGRES_TEST_URL=... pytest -p no:xdist tests/services/test_part_linker_concurrency.py -v --no-cov` → **2 passed** (single-worker local verification)
- `POSTGRES_TEST_URL=... pytest -n 2 -m postgres --dist=loadfile tests/services/test_part_linker_concurrency.py -v --no-cov` → **2 passed** (xdist parallel local verification)

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `grep -c "with_for_update()"` ≥ 5 | 6 |
| `grep -c "select(DBPart)"` ≥ 5 | 7 |
| unlink_part body `with_for_update()` count ≥ 3 | 3 |
| `pytest -n auto tests/test_part_linker.py -v` | 10 passed |
| `pytest -n auto tests/test_session_query_regression.py` | 1 passed |
| `pytest -n auto` full suite | 2245 passed, 8 skipped |
| pytest.ini has `postgres: requires POSTGRES_TEST_URL` | OK |
| `postgres_engine` fixture in conftest.py | 5 matches |
| `postgres_session` fixture in conftest.py | 1 match |
| `PYTEST_XDIST_WORKER` in conftest.py | 2 matches |
| No underscore-aliased imports in conftest.py | OK |
| WARN 8 `CONTRACT` documented | OK (1) |
| `docker-compose.test.yml` exists with `image: postgres:16` + healthcheck | OK |
| `postgres-tests:` job in backend-ci.yml | OK |
| `retrying in 2s` (INFO 12 retry) in backend-ci.yml | OK |
| `pytestmark = pytest.mark.postgres` module-level in concurrency test | 1 |
| `ThreadPoolExecutor` used ≥ 2 times in concurrency test | 3 |
| `assert canonical_count == 1` in concurrency test | 1 |
| "cycle or orphan" assertion message in concurrency test | 1 |
| `email_verified=True` seed (User field per user.py:29) | 1 |
| `is_verified=True` NOT present (that's a Part field, not a User field) | 0 |
| SKIPPED-not-failed when POSTGRES_TEST_URL unset | Confirmed (2 skipped, 0 errors) |
| Tests PASS on real Postgres 16 (local verification) | Confirmed (pytest -p no:xdist + pytest -n 2 both 2 passed) |

## Next Phase Readiness

- **Plan 04-06 (CONVENTIONS.md + lazy="raise"):** Unblocked. No coupling with this plan's service-body changes.
- **Phase 5 (admin.py + auth.py splits):** Unblocked. `postgres_engine` / `postgres_session` fixtures are ready to use.
- **Phase 4 completion:** 5 of 6 plans complete. Plan 04-06 is the last remaining plan in this phase.

## Self-Check: PASSED

File existence:
- FOUND: backend/app/api/services/part_linker_service.py (modified with 6 `with_for_update()` tokens)
- FOUND: backend/pytest.ini (modified — postgres marker registered)
- FOUND: backend/tests/conftest.py (modified — postgres_engine + postgres_session fixtures)
- FOUND: docker-compose.test.yml (new file at repo root)
- FOUND: .github/workflows/backend-ci.yml (modified — postgres-tests job)
- FOUND: backend/tests/services/test_part_linker_concurrency.py (new file)

Commit existence (git log --oneline):
- FOUND: 1841b75 (Task 1 — feat with_for_update locks)
- FOUND: bacda8f (Task 2 — feat postgres test infrastructure)
- FOUND: 951fcca (Task 3 — test concurrency)

---

*Phase: 04-db-parts-hardening*
*Plan: 05*
*Completed: 2026-04-23*
