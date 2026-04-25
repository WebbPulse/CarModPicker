---
phase: 04-db-parts-hardening
plan: 06
subsystem: database
tags: [lazy-raise, conventions, docs, integration-tests, car-inference]

# Dependency graph
requires:
  - phase: 04-db-parts-hardening
    provides: "Plan 04-03 pre-loaded BuildLogPost.author via selectinload on the build-log read path — lazy='raise' on BuildLogPost.author is safe because this caller is covered"
  - phase: 04-db-parts-hardening
    provides: "Plan 04-04 session.query sweep — part_linker_service.py is in the modern select() form; integration tests can call link_new_part/reelect_canonical/unlink_part on SQLite without any pre-conversion"
  - phase: 04-db-parts-hardening
    provides: "Plan 04-05 delivered docker-compose.test.yml on port 5433 — CONVENTIONS.md documents it as the recommended Postgres side-car for the reviewer-gated round-trip"
provides:
  - "DATA-10: lazy='raise' applied surgically to 3 N+1-prone relationships (BuildLogPost.author, BuildList.build_list_parts, BuildList.build_list_phases) — future N+1 regressions fail loud at test time"
  - "PARTS-02: AMBIGUOUS_STANDALONE_CODES has a multi-line dangling docstring documenting purpose, add/remove criteria, and v2 deferral pointer; test_car_inference_ambiguity.py pins 26 parametrized ambiguity vectors (plan floor: ≥20)"
  - "PARTS-03: test_part_linker_integration.py covers 5 canonical-flow scenarios on SQLite; merge case seeds concrete PartListing rows so find_part_by_product_url + find_part_by_gtin both return distinct canonicals"
  - "DATA-09: .planning/codebase/CONVENTIONS.md has a new 'Alembic downgrade testing' subsection; backend/scripts/test_migration_round_trip.sh exists, executable, requires a REVISION arg (INFO 13)"
  - "test_lazy_raise_callers.py — uses first-access trigger to raise InvalidRequestError without the db_session.expire() hack (WARN 10); reusable template for future lazy='raise' additions"
affects: [05-admin-auth-splits]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "lazy='raise' on Mapped[...]=relationship(...) paired with .options(selectinload(...)) at every caller — fails loud when a future site misses the eager-load"
    - "First-access trigger for InvalidRequestError (WARN 10) — no db_session.expire() hack; a freshly-fetched entity without the selectinload option is already in the 'unloaded' state"
    - "Dangling docstring idiom (triple-quoted string after the assignment) for documenting module-level constants like AMBIGUOUS_STANDALONE_CODES"
    - "Pinned-behavior regression test shape — parametrized (input, expected, rationale) vectors with module docstring explicitly disclaiming correctness (PARTS-V2-01 defers to v2)"
    - "Merge-case integration seed — Retailer + canon_a (gtin) + canon_b + PartListing(part_id=canon_b, product_url=shared_url) + new_part(gtin, product_url) → link_new_part exercises the gtin+url multi-candidate merge path on SQLite"
    - "Bash round-trip helper with mandatory REVISION arg (INFO 13) — set -euo pipefail + explicit usage message on missing arg prevents silent `head` defaulting"

key-files:
  created:
    - "backend/tests/test_lazy_raise_callers.py"
    - "backend/tests/test_car_inference_ambiguity.py"
    - "backend/tests/services/test_part_linker_integration.py"
    - "backend/scripts/test_migration_round_trip.sh"
  modified:
    - "backend/app/api/models/build_log.py"
    - "backend/app/api/models/build_list.py"
    - "backend/app/core/car_inference.py"
    - ".planning/codebase/CONVENTIONS.md"

key-decisions:
  - "No callers needed a new selectinload addition — audit of build_list_parts/build_list_phases attribute access across app/ found zero lazy consumers (only local-variable name reuse in service/endpoint code) and BuildListRead schema does not expose the relationships. BuildLogPost.author was already paired with selectinload in plan 04-03. Result: flipping to lazy='raise' was a zero-caller-change operation."
  - "test_lazy_raise_callers.py uses first-access to trigger InvalidRequestError (WARN 10) — freshly-fetched entity without selectinload is already in the 'unloaded' state, so `_ = fetched.author` raises directly without a db_session.expire() call"
  - "AMBIGUOUS_STANDALONE_CODES docstring placed AFTER the frozenset assignment (dangling-docstring idiom) to preserve the frozenset's literal contents unchanged — keeps the audit trail clean and matches Python tooling expectations"
  - "26 ambiguity vectors chosen (>plan floor of 20): 7 positive (explicit disambiguation) + 19 negative (ambiguous-standalone codes that must not fire). Covers B4, B6, B8, B16, HI, NA, EVO, D2, V10, P1, HD, S1, OS, MD, XT, BP, RS, roman-numeral V, decimal-fractional 0.42 (Audi R8 42 false-positive guard)"
  - "Integration test (e) unlink_promotes_sibling_to_standalone also exercises reelect_canonical en route to the final unlink — gives all three mutators (link_new_part, reelect_canonical, unlink_part) named coverage in one file"
  - "Integration tests use direct DBPart(...) construction (bypassing PartService.create) — controlled metadata scoring for the re-elect scenario (c) without side-effects from PartService's PartListing / price-history autocreate path"
  - "Round-trip script REVISION arg is REQUIRED (INFO 13) — silent `head` defaulting disabled so reviewers can confirm the author ran the script against the specific revision under review; explicit `head` still works"

patterns-established:
  - "lazy='raise' rollout pattern: (1) ensure every caller pre-loads via selectinload, (2) add lazy='raise' to relationship(), (3) add a callers-coverage test pair (without/with selectinload) per relationship, (4) commit model change + test together"
  - "Pinned-behavior regression pattern — explicitly document 'asserts current behavior, not correctness' in the module docstring so future behavior-fixing PRs update the vectors intentionally rather than hiding drift"
  - "Reviewer-gated convention pattern — helper script + CONVENTIONS.md subsection together; CI-automation deferred with an explicit pointer to the Deferred Ideas log"

requirements-completed: [DATA-09, DATA-10, PARTS-02, PARTS-03]

# Metrics
duration: ~9min
completed: 2026-04-23
---

# Phase 4 Plan 06: lazy='raise' + Conventions + Integration Summary

**Wave 6 closes the Phase 4 cleanup requirements (DATA-09, DATA-10, PARTS-02, PARTS-03). Three N+1-prone relationships (`BuildLogPost.author`, `BuildList.build_list_parts`, `BuildList.build_list_phases`) are flipped to `lazy="raise"` with zero caller changes required (plan 04-03 already paired the only lazy consumer with `selectinload`); a new `test_lazy_raise_callers.py` uses WARN 10's first-access trigger — no `db_session.expire()` hack. `AMBIGUOUS_STANDALONE_CODES` gains a multi-line dangling docstring with add/remove criteria and a PARTS-V2-01 deferral pointer; `test_car_inference_ambiguity.py` pins 26 parametrized behaviors (plan floor: 20). `test_part_linker_integration.py` covers all five canonical-flow scenarios on SQLite — the merge case seeds a concrete `DBPartListing` per WARN 7. `.planning/codebase/CONVENTIONS.md` appends an "Alembic downgrade testing" subsection and `backend/scripts/test_migration_round_trip.sh` ships executable with a mandatory REVISION arg (INFO 13). Full backend suite stays green at 2283 passed, 8 skipped (+32 tests vs plan 04-05 baseline of 2251).**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-04-23T04:59:54Z
- **Completed:** 2026-04-23T05:09:30Z
- **Tasks:** 4 (+ final cleanup audit — no changes needed)
- **Files changed:** 8 (4 new: 3 tests + 1 shell script; 4 modified: 2 models + 1 core + 1 CONVENTIONS.md)

## Task Commits

1. **Task 1 RED — failing lazy='raise' callers-coverage test** — `a951dce` (test)
2. **Task 1 GREEN — flip 3 relationships to lazy='raise'** — `d0f9f29` (feat)
3. **Task 2 (test first) — 26 car_inference ambiguity vectors** — `484fe83` (test)
4. **Task 2 (docstring) — AMBIGUOUS_STANDALONE_CODES dangling docstring** — `5b0add9` (docs)
5. **Task 3 — 5 canonical-flow integration tests on SQLite** — `b0048a4` (test)
6. **Task 4 — CONVENTIONS.md subsection + round-trip script** — `6d759de` (docs)

Final-cleanup task (per objective): investigated, **no changes needed** — see "Final Cleanup Audit" section below.

## Callers-Coverage Audit

Three relationships flipped to `lazy="raise"`:

| File | Relationship | Line |
|------|--------------|------|
| `backend/app/api/models/build_log.py` | `BuildLogPost.author` | 64 |
| `backend/app/api/models/build_list.py` | `BuildList.build_list_parts` | 41 |
| `backend/app/api/models/build_list.py` | `BuildList.build_list_phases` | 46 |

Callers audited — zero new selectinload additions needed:

- **`BuildLogPost.author`** — the only lazy consumer is `get_build_log_by_build_list` in `backend/app/api/endpoints/build_logs.py:117-124`, which already carries `.options(selectinload(DBBuildLogPost.author))` (landed plan 04-03). The create/update paths (`build_logs.py:224` and `:292`) fetch the author via a separate `db.scalars(select(DBUser)...)` query, NOT via `post.author` attribute access — so lazy='raise' does not fire there.
- **`BuildList.build_list_parts` + `BuildList.build_list_phases`** — grep across `app/` shows no attribute access to either relationship. `BuildListRead`/`BuildListReadWithVotes` Pydantic schemas do NOT expose them (Pitfall 7 check passed). Endpoints query `DBBuildListPart` / `DBBuildListPhase` directly by `build_list_id` (see `build_list_parts.py:429`, `build_lists.py:400`). The local variable `build_list_parts` in `build_list_service.py:165` is a freshly-queried list, not the ORM relationship.

Full `pytest -n auto tests/api/endpoints/test_build_logs.py tests/api/endpoints/test_build_lists.py` passes (71 passed) — no existing endpoint test broke. All 6 tests in the new `test_lazy_raise_callers.py` are green.

## Car-Inference Ambiguity Vector Count

**26 total** (plan floor: ≥20). Broken down:

- **7 positive cases** (explicit make+model — MUST match): MKV Supra A90 (×2), G8X M3, FK8 Civic Type R, Civic 10th Gen, GR Corolla, E46 M3.
- **19 negative cases** (in `AMBIGUOUS_STANDALONE_CODES` — must NOT fire without disambiguation): HI (HKS Hi Power), NA (CTEK NA), B4 (Bilstein B4), EVO (Bilstein EVO), D2 (D2 Racing), V10 (Rexpeed), P1 (ADRO AT-P1), HD (ACT HD), B6 / B8 / B16 (Bilstein shock line), V/V3 (KW V3 roman-numeral), S1 (ARE hose), OS (Cusco OS), MD (MAGDRAIN), XT (Thule XT), BP (BP Automotive), RS (KW RS), 42 (decimal-fractional 0.42 Mu friction coef — Audi R8 42 false-positive guard).

The test's `test_vector_count_meets_floor` asserts `len(AMBIGUITY_VECTORS) >= 20` so any future pruning fails loud.

## Merge-Case Integration Test (Scenario d) — Code-Path Coverage Evidence

The merge code path in `link_new_part` (lines 278-299 of `part_linker_service.py`) is only exercised when `find_canonical_candidates` returns **multiple distinct canonicals**. Test `test_merge_multiple_candidate_canonicals` in `backend/tests/services/test_part_linker_integration.py` seeds the exact preconditions:

- **1 Retailer row** (`_make_retailer` helper with per-test unique name+domain)
- **canon_a**: `DBPart(name="A (gtin source)", gtin=shared_gtin)` — matchable via `find_part_by_gtin`
- **canon_b**: `DBPart(name="B (url source)")` — NO gtin, matchable only via `find_part_by_product_url`
- **1 DBPartListing row**: `DBPartListing(part_id=canon_b.id, retailer_id=retailer.id, product_url=shared_url)` — makes canon_b URL-findable
- **new_part**: `DBPart(name="Merger", gtin=shared_gtin)` — carries the gtin key

Invocation: `link_new_part(db_session, new_part, product_url=shared_url)` — passes both keys. `find_canonical_candidates` returns `{canon_a, canon_b}` (two distinct canonicals), triggering the merge branch.

Post-call assertion: `len([p for p in (canon_a, canon_b, new_part) if p.canonical_part_id is None]) == 1` — exactly one canonical survives. The test additionally asserts that every non-canonical points at the surviving canonical (no cycles, no orphans).

grep evidence: `grep -c "DBPartListing(" backend/tests/services/test_part_linker_integration.py` → **1** (meets WARN 7 floor).

## Decisions Made

### No caller changes needed for lazy='raise'

Per plan 04-06 Task 1 Step C, the plan mandated an audit of every `.build_list_parts`, `.build_list_phases`, and `post.author` attribute access site. The audit found:

- **`post.author`**: 1 lazy consumer (plan 04-03's selectinload in build_logs.py:117); 2 non-lazy fetches (create/update paths use `db.scalars(select(DBUser))`).
- **`.build_list_parts` / `.build_list_phases`**: zero lazy consumers in `app/` — every read of the relationship goes through `DBBuildListPart`/`DBBuildListPhase` queries filtered by `build_list_id`, not via the ORM relationship traversal.

Outcome: the 3 lazy='raise' additions are purely defensive. Their value is forward — they catch future regressions introduced by Phase 5 splits or v2 work.

### WARN 10 first-access trigger — no db_session.expire() hack

Earlier drafts of the lazy='raise' test pattern used `db_session.expire(fetched)` before attempting the raise-triggering access. SQLAlchemy's semantics do not require expire: a freshly-fetched instance WITHOUT the `.options(selectinload(...))` option is already in the "unloaded" state, so the first attribute access triggers `InvalidRequestError` directly. Using expire masks the test intent (suggests the instance was in "loaded" state first, which it wasn't). The new test follows WARN 10 exactly: fetch → access → raise.

Verified via `grep -c "db_session.expire(fetched)" backend/tests/test_lazy_raise_callers.py` → **0**.

### Pinned-behavior test docstring explicitly disclaims correctness

`test_car_inference_ambiguity.py` uses the phrase "pins current behavior, not correctness" in its module docstring to preempt the natural reviewer instinct to "fix" vectors that look wrong. If a vector needs updating because the underlying behavior changed intentionally, the PR diff will surface both the code change and the test-vector change together; if a vector is updated because someone disagrees with current behavior, the module docstring directs them to file a PARTS-V2-01 issue instead.

### Round-trip script REVISION arg is REQUIRED (INFO 13)

Instead of defaulting to `head` when invoked with no args, the script exits 1 with a Usage message. Rationale: reviewers need to know the author tested the specific revision they're reviewing, not an arbitrary "head" that may have advanced since PR opening. Explicit `head` still works — the enforcement is against silent defaulting, not against targeting head.

## Deviations from Plan

### Intentional Non-changes

**1. [Rule 3 - Scope] No endpoint caller changes needed for lazy='raise'**

- **Found during:** Task 1 Step C audit.
- **Issue:** Plan mandated auditing callers of `.build_list_parts`, `.build_list_phases`, and `post.author` to add `.options(selectinload(...))` where missing.
- **Resolution:** Audit returned zero missing sites. Plan 04-03 already pre-loaded `BuildLogPost.author` on the only lazy consumer; `build_list_parts` / `build_list_phases` have no attribute-access callers at all (endpoints use `DBBuildListPart`/`DBBuildListPhase` queries).
- **Impact:** Task 1 landed in a single commit pair (RED test + GREEN model edits); no follow-up endpoint commits were needed.

**2. [Rule 3 - Scope] Final-cleanup task (objective-level) is a no-op**

- **Found during:** Final-cleanup audit per the plan executor objective instructions.
- **Issue:** Objective suggested removing stale unused `select` / `sql_delete` / `sql_update` / `func` imports from admin.py, crawled_pages.py, crawler_schedules.py, runner.py — presumed leftovers from Wave 4's sweep.
- **Audit result:** `pyright --outputjson` on all four files returned zero unused-import diagnostics. Grep confirmed: `admin.py` uses all four (`select`=30, `func`=8, `sql_delete`=5, `sql_update`=3); `crawled_pages.py` uses only `select`+`func` (which it imports); `crawler_schedules.py` imports only `select` (which it uses); `runner.py` imports only `select` (which it uses). No files import `sql_delete` / `sql_update` / `func` unnecessarily.
- **Resolution:** Plan 04-04's Wave 4 sweep already landed with clean imports. The stale-import assumption in the executor objective was based on pre-sweep state. No cleanup commit needed.

### Auto-fixed Issues

None. All four tasks landed without requiring Rule 1 / 2 / 3 auto-fixes. Pyright and pytest both stayed green on first run for every task.

## Threat Flags

None discovered. The plan introduces:

- 3 lazy='raise' flips — additive, covered by T-04-06-01 and T-04-06-02 in the threat register (mitigated via tests + schema audit).
- A docstring addition — covered by T-04-06-05 (accept — no new data exposure).
- 3 new test files — covered by T-04-06-06 (accept — ms-scale additions to the suite).
- A CONVENTIONS.md subsection — covered by T-04-06-04 (mitigate — deferred per D-31, SAFE-04 DROP-guard still active).
- A bash helper script — covered by T-04-06-07 (mitigate — REQUIRED arg + docs around DATABASE_URL scoping).

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries.

## Issues Encountered

None. No blockers, no architectural decisions, no auto-fixes required.

## Coordination Notes for Downstream Plans

- **Phase 5 (admin.py + auth.py splits):** Any new code that accesses `BuildLogPost.author`, `BuildList.build_list_parts`, or `BuildList.build_list_phases` MUST pre-load via `.options(selectinload(...))`. The canonical pattern lives in `backend/app/api/endpoints/build_logs.py:117-124` (build log read path). `test_lazy_raise_callers.py` fails immediately if any future caller misses the eager-load.
- **Phase 5 admin / auth query_counter usage:** Plan 04-03's `query_counter` fixture + Plan 04-05's `postgres_engine` fixture compose cleanly — a future admin-endpoint test can wrap the post-split read path in `with query_counter() as counter:` to assert bounded query counts, matching the `test_build_log_n_plus_one` pattern.
- **Plan 04-06's round-trip script is reviewer-gated.** Phase 5 migration PRs must paste the green 3-step output into the PR conversation. When the Postgres side-car CI infra matures (deferred per D-31), the script can move behind a CI step.
- **Future lazy='raise' additions follow the pattern here:** (1) ensure every caller pre-loads via selectinload, (2) add lazy='raise', (3) add a callers-coverage test pair (without/with selectinload) per relationship, (4) commit model + test together. Reuse `test_lazy_raise_callers.py` as the template.

## Phase 4 Completion Status

**All 13 Phase 4 requirements addressed across plans 04-01..04-06:**

| Req | Description | Plan | Status |
|-----|-------------|------|--------|
| DATA-01 | Fix N+1 in GET /build-logs/build-list/{id} via selectinload(Post.author) | 04-03 | ✅ |
| DATA-02 | CI-gated query-count regression test | 04-03 | ✅ |
| DATA-03 | Pessimistic with_for_update() locks on link/unlink/reelect | 04-05 | ✅ |
| DATA-04 | 10-thread Postgres concurrency test | 04-05 | ✅ |
| DATA-05 | FK-index audit + autogenerated migration | 04-01 | ✅ |
| DATA-06 | session.query → select() sweep across 304 call sites | 04-04 | ✅ |
| DATA-07 | Prod pool reconciliation (pool_recycle=1800) | 04-01 | ✅ |
| DATA-08 | Delete lazy build-log fallback branches + data backfill | 04-02 | ✅ |
| DATA-09 | Alembic downgrade-testing CONVENTIONS.md subsection | **04-06** | ✅ |
| DATA-10 | lazy='raise' on 3 N+1-prone relationships | **04-06** | ✅ |
| PARTS-01 | Row-lock concurrency proof for canonical parts | 04-05 | ✅ |
| PARTS-02 | car_inference AMBIGUOUS_STANDALONE_CODES docstring + regression test | **04-06** | ✅ |
| PARTS-03 | Canonical-flow integration coverage | **04-06** | ✅ |

Phase 4 — COMPLETE. Unblocks Phase 5 (admin.py / auth.py structural splits).

## User Setup Required

None — no external service configuration, no env vars, no migrations. Pure code + test + docs changes. The round-trip script is invoked manually by the reviewer against a local Postgres; no CI or runtime coupling.

## Verification

- `grep -c 'lazy="raise"' backend/app/api/models/build_log.py` → **1**
- `grep -c 'lazy="raise"' backend/app/api/models/build_list.py` → **2**
- `grep -c "db_session.expire(fetched)" backend/tests/test_lazy_raise_callers.py` → **0** (WARN 10 compliance)
- `grep -c "Criterion for adding a code" backend/app/core/car_inference.py` → **1**
- `grep -c "PARTS-V2-01" backend/app/core/car_inference.py` → **1**
- `grep -c "pins current behavior" backend/tests/test_car_inference_ambiguity.py` → **1**
- `grep -c "def test_" backend/tests/services/test_part_linker_integration.py` → **5**
- `grep -c "DBPartListing(" backend/tests/services/test_part_linker_integration.py` → **1** (WARN 7 — merge case seed)
- `grep -c "_make_retailer" backend/tests/services/test_part_linker_integration.py` → **2**
- `grep -c "link_new_part\|reelect_canonical\|unlink_part" backend/tests/services/test_part_linker_integration.py` → **9** (≥5 threshold)
- `test -x backend/scripts/test_migration_round_trip.sh` → executable
- `bash backend/scripts/test_migration_round_trip.sh` (no arg) → exits 1 with "Usage:" message (INFO 13)
- `grep -c "alembic upgrade\|alembic downgrade" backend/scripts/test_migration_round_trip.sh` → **6** (≥3)
- `grep -c "Alembic downgrade testing" .planning/codebase/CONVENTIONS.md` → **1**
- `grep -c "# SAFE: forward-only" .planning/codebase/CONVENTIONS.md` → **1** (exception documented)
- `grep -c "docker-compose.test.yml" .planning/codebase/CONVENTIONS.md` → **1**
- `grep -c "REQUIRED" .planning/codebase/CONVENTIONS.md` → **1**
- `pytest -n auto tests/test_lazy_raise_callers.py -v` → **6 passed**
- `pytest -n auto tests/test_car_inference_ambiguity.py -v` → **27 passed** (26 vectors + count-floor sentinel)
- `pytest -n auto tests/services/test_part_linker_integration.py -v` → **5 passed**
- `pytest -n auto tests/api/endpoints/test_build_logs.py tests/api/endpoints/test_build_lists.py` → **71 passed** (existing endpoint tests stay green)
- `pytest -n auto tests/test_session_query_regression.py tests/test_openapi_snapshot.py` → **2 passed** (sweep invariants + snapshot)
- `pytest -n auto -k "characterization"` → **10 passed, 2 skipped** (OAuth cassette skip baseline preserved)
- `pytest -n auto` (full backend suite) → **2283 passed, 8 skipped** (+32 tests vs plan 04-05 baseline of 2251)
- `pyright app/api/models/build_log.py app/api/models/build_list.py tests/test_lazy_raise_callers.py tests/test_car_inference_ambiguity.py tests/services/test_part_linker_integration.py` → **0 errors, 0 warnings, 0 informations**

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `grep -c 'lazy="raise"' build_log.py ≥ 1` | 1 |
| `grep -c 'lazy="raise"' build_list.py ≥ 2` | 2 |
| `grep -c "db_session.expire(fetched)" test_lazy_raise_callers.py == 0` | 0 |
| `pytest -n auto tests/test_lazy_raise_callers.py -v` → 6 tests pass | 6 passed |
| `pytest -n auto tests/api/endpoints/test_build_logs.py` | 32 passed |
| `pytest -n auto tests/api/endpoints/test_build_lists.py` | 39 passed |
| `pytest -n auto` full suite | 2283 passed, 8 skipped |
| car_inference docstring has "Criterion for adding a code" | 1 |
| car_inference docstring has "PARTS-V2-01" | 1 |
| test_car_inference_ambiguity.py ≥ 20 vectors | 26 |
| test_car_inference_ambiguity.py has "pins current behavior" | 1 |
| test_part_linker_integration.py has exactly 5 `def test_` | 5 |
| test_part_linker_integration.py has ≥ 1 `DBPartListing(` | 1 |
| test_part_linker_integration.py has ≥ 1 `_make_retailer` | 2 |
| test_part_linker_integration.py has ≥ 5 `link_new_part\|reelect_canonical\|unlink_part` | 9 |
| test_migration_round_trip.sh is executable | OK |
| test_migration_round_trip.sh has ≥ 3 `alembic upgrade\|downgrade` lines | 6 |
| test_migration_round_trip.sh zero-args exits non-zero with Usage | OK (exit 1) |
| CONVENTIONS.md has "Alembic downgrade testing" | 1 |
| CONVENTIONS.md has "# SAFE: forward-only" exception | 1 |
| CONVENTIONS.md has "docker-compose.test.yml" | 1 |
| CONVENTIONS.md has "REQUIRED" | 1 |
| Coverage floor --cov-fail-under=51 not regressed | confirmed (full suite green) |

## Final Cleanup Audit

The executor objective requested a final cleanup pass to remove stale unused `select` / `sql_delete` / `sql_update` / `func` imports left over from Wave 4's sweep across `admin.py`, `crawled_pages.py`, `crawler_schedules.py`, and `runner.py`. Investigation:

| File | Imports from sqlalchemy | Unused? |
|------|-------------------------|---------|
| `admin.py` | `delete as sql_delete`, `func`, `select`, `update as sql_update` | No — all 4 used (select=30, func=8, sql_delete=5, sql_update=3) |
| `crawled_pages.py` | `func`, `select` | No — both used (select=9, func=4) |
| `crawler_schedules.py` | `select` | No — used (select=6) |
| `runner.py` | `select` | No — used (select=10) |

Pyright `--outputjson` across all four files returned **zero** unused-import diagnostics. Plan 04-04's sweep already landed with clean imports.

**No cleanup commit created** — nothing to clean up.

## Next Phase Readiness

- **Phase 5 (admin.py + auth.py splits):** Unblocked. All Phase 4 hardening complete.
- **Phase 6 and beyond:** The `query_counter` fixture (plan 04-03), `postgres_engine` / `postgres_session` fixtures (plan 04-05), `test_lazy_raise_callers.py` template (this plan), and the Alembic round-trip script (this plan) are all ready to use.

## Self-Check: PASSED

File existence:
- FOUND: backend/tests/test_lazy_raise_callers.py
- FOUND: backend/tests/test_car_inference_ambiguity.py
- FOUND: backend/tests/services/test_part_linker_integration.py
- FOUND: backend/scripts/test_migration_round_trip.sh (executable)
- FOUND: backend/app/api/models/build_log.py (lazy='raise' on BuildLogPost.author)
- FOUND: backend/app/api/models/build_list.py (lazy='raise' on build_list_parts + build_list_phases)
- FOUND: backend/app/core/car_inference.py (dangling docstring on AMBIGUOUS_STANDALONE_CODES)
- FOUND: .planning/codebase/CONVENTIONS.md (Alembic downgrade testing subsection)

Commit existence (git log --oneline):
- FOUND: a951dce (Task 1 RED — test_lazy_raise_callers.py)
- FOUND: d0f9f29 (Task 1 GREEN — lazy='raise' on 3 relationships)
- FOUND: 484fe83 (Task 2 test — 26 ambiguity vectors)
- FOUND: 5b0add9 (Task 2 docstring — AMBIGUOUS_STANDALONE_CODES)
- FOUND: b0048a4 (Task 3 — 5 integration tests)
- FOUND: 6d759de (Task 4 — CONVENTIONS.md + round-trip script)

TDD Gate Compliance:
- Task 1: RED commit (a951dce, `test(04-06): add failing lazy='raise' callers-coverage test`) → GREEN commit (d0f9f29, `feat(04-06): flip 3 N+1-prone relationships to lazy='raise'`) — gates satisfied
- Task 2: test-first commit (484fe83, `test(04-06): add 26 car_inference ambiguity regression vectors`) → docs commit (5b0add9, `docs(04-06): add multi-line docstring to AMBIGUOUS_STANDALONE_CODES`) — behavior pinning landed before docstring
- Task 3: direct test commit (b0048a4) — integration tests pin behavior that already works; no implementation change required
- Task 4: non-TDD (docs-only per plan `tdd="false"`)

---

*Phase: 04-db-parts-hardening*
*Plan: 06*
*Completed: 2026-04-23*
