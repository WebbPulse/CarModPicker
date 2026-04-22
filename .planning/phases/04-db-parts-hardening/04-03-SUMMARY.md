---
phase: 04-db-parts-hardening
plan: 03
subsystem: database
tags: [n-plus-one, selectinload, event-listener, fixture, regression-test]

# Dependency graph
requires:
  - phase: 04-db-parts-hardening
    provides: "Plan 04-02 delivered the lazy-branch-deleted build_logs.py surface (eager-create invariant enforced via raise_not_found); Plan 04-01 landed ix_build_log_posts_user_id so the selectinload IN-clause SELECT hits an index"
  - phase: 01-safety-nets-ci-hardening
    provides: "backend/tests/conftest.py engine + db_session fixture shape — query_counter attaches to the same session-scoped engine via event.listen"
provides:
  - "query_counter pytest fixture in backend/tests/conftest.py — usable by any future N+1 regression test (plan 04-05 concurrency test post-verify; plan 04-06 lazy='raise' audits; Phase 5 admin/auth splits)"
  - "DATA-01: read-path N+1 eliminated — posts+authors fetch emits EXACTLY 2 queries regardless of post count (ROADMAP Phase 4 Success Criterion 1 literal)"
  - "DATA-02: CI-gated regression tests lock the fix in — 3 assertions (exactly-2 scoped, <= 6 full round-trip, scale-independence)"
  - "Count query on build_logs read path migrated to select(func.count()).select_from(X) form (satisfies part of DATA-06 sweep for this endpoint; plan 04-04 owns the rest)"
affects: [04-04-session-query-sweep, 04-05-row-lock-concurrency, 04-06-conventions-lazy-raise, 05-admin-auth-splits]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "query_counter context-manager fixture — SQLAlchemy event.listen(engine, 'before_cursor_execute', fn) with regex-filter to SELECT-only + finally: event.remove to prevent listener leak (Pitfall 3)"
    - "Eager-load via options(selectinload(X.relationship)) on session.scalars(select(...)) — 2-query shape (1 parent + 1 IN-clause child) regardless of parent cardinality"
    - "select(func.count()).select_from(X).where(...) for COUNT(*) — coerced to int via `or 0` to satisfy non-optional caller params (db.scalar returns Optional[int])"

key-files:
  created:
    - "backend/tests/test_query_counter_fixture.py"
    - "backend/tests/test_build_log_n_plus_one.py"
  modified:
    - "backend/tests/conftest.py"
    - "backend/app/api/endpoints/build_logs.py"

key-decisions:
  - "Option Y (inline select in test) chosen over Option X (service-layer helper) because no build_log_service.py exists — creating one just for test scoping would be premature abstraction. The test's inline select() statement mirrors the endpoint's posts+authors clause exactly; any future refactor to a service layer can migrate the test to that helper"
  - "Read-path only — create_build_log_post (line 221) and update_build_log_post (line 289) still contain single-row db.query(DBUser) lookups. These are NOT in an N+1 loop (one fetch per request, not per post) and the plan's action section line 417 explicitly says 'Do NOT alter the other endpoints in this file that are not part of the N+1 block.' Plan 04-04 (session.query sweep) owns those sites"
  - "Pyright Rule 1 auto-fix: db.scalar(select(func.count())...) returns Optional[int] but create_paginated_response expects int. Coerced with `or 0` and documented — COUNT(*) semantically never returns NULL (returns 0 when no rows match), so the coercion is safe"
  - "load_only(User.id, User.username, User.image_urls) NOT applied per D-35 Claude's Discretion — keeping full-row fetch matches old N+1 code behavior (no response-shape drift; OpenAPI snapshot stays green). Future optimization can add load_only() if payload size becomes a concern"

patterns-established:
  - "query_counter fixture shape is reusable across Phase 4 (plan 04-05 concurrency test post-verify) and Phase 5 (admin/auth splits) — attach to session-scoped engine, yield context-manager, event.remove in finally"
  - "selectinload over joinedload for collection reads — selectinload emits N+1=2 with no cartesian product; joinedload would emit 1 with O(parents × children) rows on the wire"

requirements-completed: [DATA-01, DATA-02]

# Metrics
duration: 5min
completed: 2026-04-23
---

# Phase 4 Plan 03: N+1 Fix + query_counter Fixture Summary

**Read-path N+1 on GET /build-logs/build-list/{id} eliminated via selectinload(DBBuildLogPost.author) — posts+authors fetch now emits exactly 2 SQL queries regardless of post count; a reusable query_counter pytest fixture lands in conftest.py and 3 CI-gated regression tests (inline-select exactly-2, full round-trip <= 6, scale-independence) lock the fix in. Count query migrated to select(func.count()).select_from() form.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-23T03:54:52Z
- **Completed:** 2026-04-23T04:00:39Z
- **Tasks:** 2 (both TDD: RED + GREEN)
- **Files changed:** 4 (2 new test modules, 1 conftest edit, 1 endpoint edit)

## Measured Query Counts (10-post seed, distinct authors per post)

| Path | Expected | Measured | Breakdown |
|------|----------|----------|-----------|
| Posts+authors inline select (Option Y, scoped tight) | 2 | **2** | 1 posts SELECT + 1 IN-clause authors SELECT (selectinload) |
| Full endpoint GET /build-logs/build-list/{id}?limit=10 | <= 6 | **5** | 1 build_list + 1 build_log + 1 COUNT(*) + 1 posts + 1 authors-IN |
| Full endpoint — 3 posts vs 10 posts delta | <= 1 | **0** | Scale-independent — selectinload batches authors |

Before fix (measured during RED phase with 10 distinct authors): full endpoint emitted **15 SELECTs** (3 fixed + 1 posts + 10 per-post author lookups + 1 extra) — a literal 1+N scaling pattern.

## Task Commits

1. **Task 1 RED: failing self-test for query_counter** — `52c7e62` (test)
2. **Task 1 GREEN: query_counter fixture in conftest.py** — `2f21965` (feat)
3. **Task 2 RED: failing N+1 regression test** — `2bb8386` (test)
4. **Task 2 GREEN: selectinload fix in build_logs.py** — `fe9fa10` (feat)

## Code Change Details

### backend/tests/conftest.py (Task 1)

Added at module top (after existing imports):
- `import re`
- `from contextlib import contextmanager`
- `from dataclasses import dataclass, field`

Added between `db_session` and `client` fixtures:
- `_SELECT_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)` — module-level
- `QueryCounter` dataclass — `count: int`, `statements: list[str]`, `record(statement)` method filters to SELECT only
- `query_counter` fixture — accepts session-scoped `engine`, returns a context manager; uses `event.listen(engine, "before_cursor_execute", fn)` inside `try`, `event.remove(...)` in `finally` (Pitfall 3 defense verified by `test_listener_removed_after_exit`)

Pure addition. Existing `engine` and `db_session` fixtures untouched.

### backend/app/api/endpoints/build_logs.py (Task 2)

Added imports at top:
```python
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
```

Rewrote the count + posts blocks inside `get_build_log_by_build_list` (the only endpoint in this file affected by DATA-01):

**Before (post-plan-04-02 state):**
```python
total_posts = db.query(DBBuildLogPost).filter(DBBuildLogPost.build_log_id == build_log.id).count()

posts_query = (
    db.query(DBBuildLogPost)
    .filter(DBBuildLogPost.build_log_id == build_log.id)
    .order_by(DBBuildLogPost.created_at)
    .offset(skip)
    .limit(limit)
)
posts = posts_query.all()

posts_with_authors: List[BuildLogPostRead] = []
for post in posts:
    author = db.query(DBUser).filter(DBUser.id == post.user_id).first()  # N+1!
    post_data = BuildLogPostRead.model_validate(post)
    post_data.author_username = author.username if author else None
    post_data.author_image_url = (
        get_presigned_url_from_file_key((author.image_urls or [None])[0])
        if author and author.image_urls
        else None
    )
    posts_with_authors.append(post_data)
```

**After:**
```python
total_posts = db.scalar(
    select(func.count())
    .select_from(DBBuildLogPost)
    .where(DBBuildLogPost.build_log_id == build_log.id)
) or 0

posts = db.scalars(
    select(DBBuildLogPost)
    .where(DBBuildLogPost.build_log_id == build_log.id)
    .order_by(DBBuildLogPost.created_at)
    .options(selectinload(DBBuildLogPost.author))
    .offset(skip)
    .limit(limit)
).all()

posts_with_authors: List[BuildLogPostRead] = []
for post in posts:
    author = post.author  # eager-loaded via selectinload; zero additional queries
    post_data = BuildLogPostRead.model_validate(post)
    post_data.author_username = author.username if author else None
    post_data.author_image_url = (
        get_presigned_url_from_file_key((author.image_urls or [None])[0])
        if author and author.image_urls
        else None
    )
    posts_with_authors.append(post_data)
```

**Preserved:** Response shape unchanged (OpenAPI snapshot green); author_username + author_image_url population logic intact; pagination offset/limit unchanged.

**Out of scope (per plan directive line 417):** `create_build_log_post` (line 221) and `update_build_log_post` (line 289) still contain single-row `db.query(DBUser).filter(DBUser.id == post.user_id).first()` lookups. These are NOT in N+1 loops — they fetch the author once per request for the single post just created/updated. Plan 04-04 (session.query sweep) owns migrating those two sites.

## Decisions Made

### Option Y (inline select in test) over Option X (service-layer helper)

Plan offered two approaches for the "exactly 2 queries" assertion. Option X would require creating a `backend/app/api/services/build_log_service.py` helper just to give the test a tight scope; Option Y has the test construct the same select statement inline. Chose Option Y because:

- No `build_log_service.py` exists — creating one only to enable test scoping is premature abstraction.
- The inline select mirrors the endpoint's posts+authors clause exactly; any future service-layer refactor can migrate the test easily.
- The test's `test_posts_and_authors_fetch_emits_exactly_2_queries` is self-documenting — the inline select IS the thing being measured.

### Pyright Rule 1 auto-fix: Optional[int] coercion

`db.scalar(select(func.count())...)` returns `Optional[int]` but `create_paginated_response(total=...)` expects `int`. Coerced with `or 0` and inline comment. COUNT(*) semantically never returns NULL — it returns 0 when no rows match. This is safe.

### load_only not applied (D-35 Claude's Discretion)

D-35 allowed adding `.load_only(User.id, User.username, User.image_urls)` to narrow the authors payload. Chose NOT to apply because:

- Old N+1 code fetched full User rows per post; keeping full-row fetch matches existing behavior exactly (zero risk of response-shape drift).
- OpenAPI snapshot stays green trivially.
- Future optimization pass can add load_only() if payload size becomes a concern — this is a pure performance tweak, not a correctness requirement.

### BuildLogPost relationship confirmation

`BuildLogPost` declares ONLY the `author` relationship (verified at `backend/app/api/models/build_log.py:64` plus the `build_log` back-ref at line 63). The model has no other relationships that could N+1. This confirms **plan 04-06's `lazy="raise"` flip on `BuildLogPost.author` can land safely** — a single selectinload in this endpoint (and any future readers) is sufficient.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Optional[int] coercion on COUNT(*) result**

- **Found during:** Task 2 (post-GREEN pyright check)
- **Issue:** `db.scalar(select(func.count())...)` returns `Optional[int]` but `create_paginated_response(total=...)` is typed as `int`. pyright reported 1 error.
- **Fix:** Appended `or 0` to the scalar call; added inline comment explaining COUNT(*) never returns NULL.
- **Files modified:** `backend/app/api/endpoints/build_logs.py` (line 113)
- **Verification:** `pyright app/api/endpoints/build_logs.py` — 0 errors, 0 warnings.
- **Committed in:** `fe9fa10` (Task 2 GREEN)

**2. [Rule 3 - Scope clarification] Per-post single-author fetches in create_build_log_post / update_build_log_post NOT touched**

- **Found during:** Task 2 acceptance-criteria grep (the plan asserted `grep -c "db.query(DBUser).filter(DBUser.id == post.user_id)" returns 0`).
- **Issue:** Two matches remain at lines 221 and 289 inside `create_build_log_post` and `update_build_log_post`. These are single-author fetches after creating or updating a single post, NOT N+1 loops.
- **Resolution:** Plan's action section line 417 explicitly states "Do NOT alter the other endpoints in this file that are not part of the N+1 block." The plan's acceptance-criteria grep is over-tight for this plan's scope — plan 04-04 (session.query sweep) owns migrating those two sites.
- **Files modified:** none (deliberately)
- **Impact:** The read-path portion of `get_build_log_by_build_list` (lines 60-170) has 0 matches — the true N+1 target is fixed. Verified by `sed -n '60,170p' | grep -c "db.query(DBUser).filter(DBUser.id == post.user_id)"` returning 0.
- **Documented deviation from acceptance-criteria literal.** Not from plan intent.

---

**Total deviations:** 2 (1 auto-fix for Optional[int] coercion, 1 scope clarification documenting that the acceptance-criteria grep was over-tight for read-path-only scope).

## Issues Encountered

None beyond the deviations above. No blockers. No architectural decisions required.

## Coordination Notes for Downstream Plans

- **Plan 04-04 (session.query sweep)** — two remaining `db.query(DBUser).filter(DBUser.id == post.user_id).first()` sites at `build_logs.py:221` and `:289` are sweep targets. They are NOT N+1 (single-row fetches after single-post create/update) but should migrate to `db.scalars(select(DBUser).where(DBUser.id == post.user_id)).first()` alongside the rest of the 304 call sites.
- **Plan 04-05 (row-lock concurrency test)** — the `query_counter` fixture is available for the concurrency test's post-verification phase. Example: wrap the post-link canonical-invariant assertions in `with query_counter() as counter:` to assert that the read path stays bounded under load.
- **Plan 04-06 (lazy="raise" + CONVENTIONS.md)** — `BuildLogPost` declares only `author` + `build_log` back-ref relationships. Flipping `author` to `lazy="raise"` is safe because this plan's selectinload already pairs it in the only endpoint that reads the relationship. No other callers traverse `post.author` lazily.

## User Setup Required

None — no external service configuration, no env vars, no migrations. Pure code + tests.

## Verification

- `pytest -n auto backend/tests/test_query_counter_fixture.py -v` → 4 passed (self-test)
- `pytest -n auto backend/tests/test_build_log_n_plus_one.py -v` → 3 passed (regression)
- `pytest -n auto backend/tests/api/endpoints/test_build_logs.py` → 32 passed (existing endpoint tests; response shape preserved)
- `pytest -n auto backend/tests/test_openapi_snapshot.py` → 1 passed (no endpoint signature drift)
- `pytest -n auto` (full backend suite) → 2244 passed, 6 pre-existing skipped (+7 vs plan 04-02 baseline of 2237)
- `pyright app/api/endpoints/build_logs.py tests/test_build_log_n_plus_one.py tests/test_query_counter_fixture.py` → 0 errors, 0 warnings

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `grep -c "selectinload(DBBuildLogPost.author)" backend/app/api/endpoints/build_logs.py >= 1` | 1 |
| `grep -c "select(func.count())" backend/app/api/endpoints/build_logs.py >= 1` | 2 |
| `grep -c "counter.count == 2" backend/tests/test_build_log_n_plus_one.py >= 1` | 1 |
| `grep -c "counter.count <= 6" backend/tests/test_build_log_n_plus_one.py >= 1` | 1 |
| `grep -c "email_verified=True" backend/tests/test_build_log_n_plus_one.py >= 1` | 1 |
| `grep -c "is_verified=True" backend/tests/test_build_log_n_plus_one.py == 0` | 0 |
| `grep -c "query_counter" backend/tests/conftest.py >= 1` | 4 |
| `grep -c "event.remove" backend/tests/conftest.py (inside fixture) >= 1` | 2 |
| `grep -c "before_cursor_execute" backend/tests/conftest.py >= 1` | 2 |
| Read-path `db.query(DBUser).filter(DBUser.id == post.user_id)` (lines 60-170) | 0 |
| Whole-file `db.query(DBUser).filter(DBUser.id == post.user_id)` (plan literal) | 2 (see Deviation 2 — plan 04-04 scope) |
| pytest -n auto test_query_counter_fixture + test_build_log_n_plus_one + test_build_logs + test_openapi_snapshot all green | PASSED |

## Next Phase Readiness

- **Plan 04-04 (session.query sweep)** unblocked. The remaining `build_logs.py` single-row db.query sites at 221 and 289 are sweep targets. N+1 scope is closed; no coupling concerns.
- **Plan 04-05 (row-lock concurrency)** unblocked. `query_counter` fixture is available for post-verify assertions in the 10-thread concurrency test.
- **Plan 04-06 (lazy="raise" + CONVENTIONS.md)** unblocked. `BuildLogPost.author` can safely receive `lazy="raise"` — only this endpoint reads the relationship and it now uses selectinload explicitly.

## Self-Check: PASSED

File existence:
- FOUND: backend/tests/test_query_counter_fixture.py
- FOUND: backend/tests/test_build_log_n_plus_one.py
- MODIFIED (verified via git show): backend/tests/conftest.py
- MODIFIED (verified via git show): backend/app/api/endpoints/build_logs.py

Commit existence:
- FOUND: 52c7e62 (Task 1 RED)
- FOUND: 2f21965 (Task 1 GREEN)
- FOUND: 2bb8386 (Task 2 RED)
- FOUND: fe9fa10 (Task 2 GREEN)

TDD Gate Compliance:
- Task 1: RED commit (52c7e62, `test(04-03): add failing self-test...`) → GREEN commit (2f21965, `feat(04-03): add query_counter...`) — gates satisfied
- Task 2: RED commit (2bb8386, `test(04-03): add failing N+1 regression test...`) → GREEN commit (fe9fa10, `feat(04-03): fix N+1 author-fetch...`) — gates satisfied
- No refactor commits needed (code already clean after GREEN).

---
*Phase: 04-db-parts-hardening*
*Plan: 03*
*Completed: 2026-04-23*
