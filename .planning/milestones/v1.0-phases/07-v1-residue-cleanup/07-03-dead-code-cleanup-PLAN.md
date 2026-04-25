---
phase: 07
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/crawlers/test_runner_circuit_breaker.py  # deleted
  - backend/app/api/utils/common_patterns.py
  - backend/tests/conftest.py
autonomous: true
tech_debt_items:
  - TD-03-01  # test_runner_circuit_breaker.py stub removal
  - TD-03-02  # common_patterns.py dead helpers removal (11 helpers with 0 external callers)
  - TD-04-WR01-conftest  # 6 residual db.query sites in backend/tests/conftest.py → select() + session.scalars()
must_haves:
  truths:
    - "`backend/tests/crawlers/test_runner_circuit_breaker.py` no longer exists in the repo"
    - "`pytest -n auto tests/crawlers/ --collect-only` does not include test_runner_circuit_breaker.py; test_runner_breaker.py and test_circuit_breaker.py still collect as replacements"
    - "11 dead helpers in `backend/app/api/utils/common_patterns.py` with zero external callers are deleted (or confirmed live if callers appeared since the audit)"
    - "`grep -rn \"\\bget_standard_endpoint_dependencies\\b|\\bverify_entity_ownership_or_admin\\b|\\bget_paginated_response\\b|\\bverify_ownership\\b|\\bbuild_sorted_query\\b|\\bget_common_dependencies\\b|\\bget_admin_dependencies\\b|\\bhandle_vote_operation\\b|\\bremove_vote_operation\\b|\\bhandle_report_creation\\b|\\bget_standard_pagination_params\\b\" backend/app/ backend/tests/` returns only the definition file (or nothing if fully deleted)"
    - "All 6 `db.query(...)` / `db_session.query(...)` sites in `backend/tests/conftest.py` migrated to `select()` + `db.scalars()` / `db.execute()`"
    - "`grep -c \"db.query(\\|db_session.query(\" backend/tests/conftest.py` returns 0"
    - "`pytest -n auto` on full suite still collects and passes after the migration"
  artifacts:
    - path: "backend/app/api/utils/common_patterns.py"
      provides: "Slimmed common_patterns.py with only externally-called helpers retained"
      pattern: "def get_standard_public_endpoint_dependencies|def verify_user_access_or_admin|def apply_standard_filters|def get_entity_or_404|def verify_entity_ownership|def build_search_query|def build_filtered_query|def create_paginated_response|def handle_integrity_error|def get_vote_summary|def get_reports_by_entity|def update_report_status|def admin_only|def validate_pagination_params"
    - path: "backend/tests/conftest.py"
      provides: "Test helpers migrated to SQLAlchemy 2.0 style — zero legacy db.query usage"
      contains: "db.scalars(select("
  key_links:
    - from: "backend/tests/conftest.py::get_default_category_id"
      to: "sqlalchemy.select + session.scalars"
      via: "replaces db_session.query(Category).filter(...).first()"
      pattern: "db_session\\.scalars\\(select\\(Category\\)"
    - from: "backend/tests/conftest.py::create_car_in_db + create_car_orm_in_db"
      to: "sqlalchemy.select + session.scalars"
      via: "replaces db.query(CarMake).filter(...).first() / db.query(CarModel).filter(...).first() / db.query(CarGeneration).options(...).filter(...).first()"
      pattern: "db\\.scalars\\(select\\(CarMake\\)"
---

<objective>
Remove three tracked dead-code items in one focused pass:
1. Delete the `test_runner_circuit_breaker.py` stub file (zero-test collection, replaced by test_runner_breaker.py + test_circuit_breaker.py in Phase 03).
2. Delete 11 helpers in `backend/app/api/utils/common_patterns.py` that have zero external callers (preserving the 13 helpers that are still used).
3. Migrate 6 residual `db.query(...)` / `db_session.query(...)` call sites in `backend/tests/conftest.py` to SQLAlchemy 2.0 `select()` + `session.scalars()` / `session.execute()` style (DATA-06 scope was originally `backend/app/` only — WR-01 in the audit flagged the test helpers as still on the 1.x API).

Purpose: Close the phase-03 `test_runner_circuit_breaker.py` stub item, the phase-03 `common_patterns.py` dead-helper item, and the phase-04 WR-01 conftest.py legacy-query item from `.planning/v1.0-MILESTONE-AUDIT.md`. All three are mechanical cleanups with no behavior change.

Output: One file deleted, one file slimmed, one file modernized. Full pytest suite must still pass.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/v1.0-MILESTONE-AUDIT.md
@CLAUDE.md

<interfaces>
### Confirmed dead helpers in `backend/app/api/utils/common_patterns.py` (verified zero external callers via `grep -rn "\\b<name>\\b" backend/app/ backend/tests/`)

11 helpers — DELETE these:
- `get_standard_endpoint_dependencies` (line 95)
- `verify_entity_ownership_or_admin` (line 152)
- `get_paginated_response` (line 184)
- `verify_ownership` (line 265)
- `build_sorted_query` (line 460)
- `get_common_dependencies` (line 570)
- `get_admin_dependencies` (line 587)
- `handle_vote_operation` (line 605)
- `remove_vote_operation` (line 671)
- `handle_report_creation` (line 792)
- `get_standard_pagination_params` (line 70)

### Live helpers in `backend/app/api/utils/common_patterns.py` — KEEP (verified via external-caller counts)
- `get_standard_public_endpoint_dependencies` (88 callers)
- `verify_user_access_or_admin` (8 callers)
- `apply_standard_filters` (5 callers)
- `admin_only` (1 caller)
- `get_entity_or_404` (60 callers)
- `verify_entity_ownership` (9 callers)
- `build_search_query` (4 callers)
- `build_filtered_query` (4 callers)
- `create_paginated_response` (27 callers)
- `handle_integrity_error` (4 callers)
- `get_vote_summary` (9 callers)
- `get_reports_by_entity` (3 callers)
- `update_report_status` (3 callers)
- `validate_pagination_params` (re-exported from `endpoint_decorators` per IN-03 note at line 89; preserve the re-export)

TypedDicts to keep (referenced by surviving helpers): `PublicEndpointDeps`, `AuthenticatedEndpointDeps`, `AdminEndpointDeps`.

### Legacy `db.query(...)` sites in `backend/tests/conftest.py` (verified via grep)

6 sites to migrate:

**Site 1 (line 340)** in `get_default_category_id(db_session)`:
```python
# Before:
category = db_session.query(Category).filter(Category.name == "other").first()
# After:
from sqlalchemy import select  # already imported at top
category = db_session.scalars(select(Category).where(Category.name == "other")).first()
```

**Sites 2 & 3 (lines 438, 444)** in `create_car_in_db(db, ...)`:
```python
# Before:
make_entity = db.query(CarMake).filter(CarMake.name == make).first()
car_model_entity = db.query(CarModel).filter(CarModel.car_make_id == make_entity.id, CarModel.name == model).first()
# After:
make_entity = db.scalars(select(CarMake).where(CarMake.name == make)).first()
car_model_entity = db.scalars(
    select(CarModel).where(
        CarModel.car_make_id == make_entity.id,
        CarModel.name == model,
    )
).first()
```

**Sites 4 & 5 (lines 491, 497)** in `create_car_orm_in_db(db, ...)`:
Same pattern as sites 2 & 3 — two calls against CarMake and CarModel.

**Site 6 (line 515)** at the tail of `create_car_orm_in_db` — with `joinedload`:
```python
# Before:
car = (
    db.query(CarGeneration)
    .options(joinedload(CarGeneration.car_model).joinedload(CarModel.car_make))
    .filter(CarGeneration.id == car.id)
    .first()
)
# After:
car = db.scalars(
    select(CarGeneration)
    .options(joinedload(CarGeneration.car_model).joinedload(CarModel.car_make))
    .where(CarGeneration.id == car.id)
).first()
```

### Replacement tests for the removed stub
Confirmed present:
- `backend/tests/crawlers/test_runner_breaker.py` (integration)
- `backend/tests/crawlers/test_circuit_breaker.py` (unit)

### pytest 2.0 patterns elsewhere in conftest.py (for style reference)
Look at `backend/tests/conftest.py` for existing `db.scalars(select(...))` call sites (the file already uses the modern API in many places — this migration only touches the 6 residual legacy calls).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Delete test_runner_circuit_breaker.py stub + verify replacements still collect</name>

  <read_first>
    - backend/tests/crawlers/test_runner_circuit_breaker.py  (confirm it is still the 21-line deprecated stub before deletion)
    - backend/tests/crawlers/test_runner_breaker.py  (confirm replacement file exists and has tests)
    - backend/tests/crawlers/test_circuit_breaker.py  (confirm replacement file exists and has tests)
  </read_first>

  <files>backend/tests/crawlers/test_runner_circuit_breaker.py</files>

  <action>
    Delete `backend/tests/crawlers/test_runner_circuit_breaker.py` using git:

    ```bash
    git rm backend/tests/crawlers/test_runner_circuit_breaker.py
    ```

    Do NOT touch `test_runner_breaker.py` or `test_circuit_breaker.py` — they are the intended replacements. The stub's module-level `pytestmark = pytest.mark.skip(...)` was collecting 0 tests and emitting a misleading skip marker; removing it silences a reviewer noise source.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; test ! -f tests/crawlers/test_runner_circuit_breaker.py &amp;&amp; pytest --collect-only --no-cov -q tests/crawlers/ 2>&amp;1 | tail -3</automated>
  </verify>

  <acceptance_criteria>
    - `test -f backend/tests/crawlers/test_runner_circuit_breaker.py` exits non-zero (file is gone)
    - `git ls-files backend/tests/crawlers/test_runner_circuit_breaker.py` returns empty output
    - `cd backend &amp;&amp; pytest --collect-only --no-cov -q tests/crawlers/test_runner_breaker.py` collects at least 1 test
    - `cd backend &amp;&amp; pytest --collect-only --no-cov -q tests/crawlers/test_circuit_breaker.py` collects at least 1 test
    - Full crawler test subtree still collects: `cd backend &amp;&amp; pytest --collect-only --no-cov -q tests/crawlers/` exits 0
  </acceptance_criteria>

  <done>
    Stub file deleted via `git rm`. Replacement test files still collect. No other code changes.
  </done>
</task>

<task type="auto">
  <name>Task 2: Delete 11 dead helpers from common_patterns.py (zero-caller verification)</name>

  <read_first>
    - backend/app/api/utils/common_patterns.py  (full file — get exact line ranges for each of the 11 helpers)
    - Re-run the zero-caller verification immediately before deletion to confirm no new callers have been added since planning:
      ```bash
      for fn in get_standard_endpoint_dependencies verify_entity_ownership_or_admin get_paginated_response verify_ownership build_sorted_query get_common_dependencies get_admin_dependencies handle_vote_operation remove_vote_operation handle_report_creation get_standard_pagination_params; do
        count=$(grep -rn "\\b$fn\\b" backend/app/ backend/tests/ 2>/dev/null | grep -v "common_patterns.py" | wc -l)
        echo "$fn: $count external callers"
      done
      ```
      If any helper now shows >0 external callers, SKIP that helper and note it in the summary. All planned-dead helpers showed 0 callers at planning time (2026-04-24).
  </read_first>

  <files>backend/app/api/utils/common_patterns.py</files>

  <action>
    Open `backend/app/api/utils/common_patterns.py` and delete the following 11 helpers (function def + body + trailing blank line). Use the Edit tool for each, matching the function signature and body exactly:

    1. `def get_standard_pagination_params(...)` starting at line 70 — ~11 lines through line 80 inclusive. Also remove any lingering `from fastapi import Query` if `Query` is no longer used anywhere else in the file (check with grep after deletion).
    2. `def get_standard_endpoint_dependencies(...)` starting at line 95 — ~17 lines through the closing `}` at line ~110.
    3. `def verify_entity_ownership_or_admin(...)` starting at line 152 — delete through end of function body.
    4. `def get_paginated_response(...)` starting at line 184 — delete through end of function body.
    5. `def verify_ownership(...)` starting at line 265 — delete through end of function body.
    6. `def build_sorted_query(...)` starting at line 460 — delete through end of function body.
    7. `def get_common_dependencies(...)` starting at line 570 — delete through end of function body.
    8. `def get_admin_dependencies(...)` starting at line 587 — delete through end of function body.
    9. `def handle_vote_operation(...)` starting at line 605 — delete through end of function body.
    10. `def remove_vote_operation(...)` starting at line 671 — delete through end of function body.
    11. `def handle_report_creation(...)` starting at line 792 — delete through end of function body.

    **IMPORTANT — do NOT delete:**
    - `PublicEndpointDeps`, `AuthenticatedEndpointDeps`, `AdminEndpointDeps` TypedDicts (used by surviving helpers)
    - `get_standard_public_endpoint_dependencies` (88 callers)
    - `verify_user_access_or_admin` (8 callers)
    - `apply_standard_filters` (5 callers)
    - `admin_only` (1 caller)
    - `get_entity_or_404` (60 callers)
    - `verify_entity_ownership` (9 callers)
    - `build_search_query` (4 callers)
    - `build_filtered_query` (4 callers)
    - `create_paginated_response` (27 callers)
    - `handle_integrity_error` (4 callers)
    - `get_vote_summary` (9 callers)
    - `get_reports_by_entity` (3 callers)
    - `update_report_status` (3 callers)
    - The IN-03 re-export block: `from app.api.utils.endpoint_decorators import validate_pagination_params as validate_pagination_params`

    After all deletions, run the zero-caller verification grep one more time and confirm:
    - Removed names do NOT appear in `grep -rn "\\b<name>\\b" backend/app/`
    - Removed names do NOT appear in `grep -rn "\\b<name>\\b" backend/tests/`

    Also prune any now-unused imports at the top of the file. Likely candidates:
    - `Query` from `fastapi` — check with `grep -n "Query" backend/app/api/utils/common_patterns.py` after deletion.
    - `Callable`, `Awaitable`, `ParamSpec` — only needed by `admin_only`; keep since `admin_only` stays.
    - Anything exclusively used in the deleted bodies.

    Run `pyright backend/app/api/utils/common_patterns.py` (or let CI catch it) after edits to confirm type-check passes.

    Run `pytest -n auto` on the full suite — no test should fail, because none of the removed helpers had callers.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto --no-cov tests/ -x 2>&amp;1 | tail -5</automated>
  </verify>

  <acceptance_criteria>
    - `grep -n "def get_standard_endpoint_dependencies\|def verify_entity_ownership_or_admin\|def get_paginated_response\|def verify_ownership\|def build_sorted_query\|def get_common_dependencies\|def get_admin_dependencies\|def handle_vote_operation\|def remove_vote_operation\|def handle_report_creation\|def get_standard_pagination_params" backend/app/api/utils/common_patterns.py` returns no matches
    - `grep -rn "\bget_standard_endpoint_dependencies\b\|\bverify_entity_ownership_or_admin\b\|\bget_paginated_response\b\|\bverify_ownership\b\|\bbuild_sorted_query\b\|\bget_common_dependencies\b\|\bget_admin_dependencies\b\|\bhandle_vote_operation\b\|\bremove_vote_operation\b\|\bhandle_report_creation\b\|\bget_standard_pagination_params\b" backend/app/ backend/tests/` returns no matches
    - `grep -n "def get_standard_public_endpoint_dependencies\|def verify_user_access_or_admin\|def apply_standard_filters\|def get_entity_or_404\|def verify_entity_ownership\|def build_search_query\|def build_filtered_query\|def create_paginated_response\|def handle_integrity_error\|def get_vote_summary\|def get_reports_by_entity\|def update_report_status\|def admin_only" backend/app/api/utils/common_patterns.py` returns 13 matches (all live helpers preserved)
    - `grep -n "validate_pagination_params as validate_pagination_params" backend/app/api/utils/common_patterns.py` returns a match (IN-03 re-export preserved)
    - `cd backend &amp;&amp; pytest -n auto --no-cov tests/ -x` exits 0
    - Line count decrease vs main baseline: `wc -l backend/app/api/utils/common_patterns.py` returns a value at least 200 lines smaller than the pre-change 965 lines (the 11 removed helpers totaled several hundred lines).
  </acceptance_criteria>

  <done>
    11 helpers removed, 13+ live helpers preserved, full pytest suite passes, no broken imports.
  </done>
</task>

<task type="auto">
  <name>Task 3: Migrate 6 db.query sites in conftest.py to SQLAlchemy 2.0 style</name>

  <read_first>
    - backend/tests/conftest.py  (lines 1-60 for import block, 330-360 for get_default_category_id, 420-520 for create_car_in_db + create_car_orm_in_db)
    - backend/app/api/models/car_generation.py, car_make.py, car_model.py  (confirm class/attribute names are CarMake / CarModel / CarGeneration; verify relationship names)
    - backend/app/api/models/category.py  (confirm class name is Category)
  </read_first>

  <files>backend/tests/conftest.py</files>

  <action>
    At the top of `backend/tests/conftest.py`, confirm `from sqlalchemy import ...` already imports `select` (check line 12 — it currently imports `create_engine, event`). If `select` is not imported, add it:
    ```python
    from sqlalchemy import create_engine, event, select
    ```

    Edit the 6 legacy call sites:

    **Edit 1 — line ~340, `get_default_category_id`:**
    ```python
    # Before:
    category = db_session.query(Category).filter(Category.name == "other").first()
    # After:
    category = db_session.scalars(select(Category).where(Category.name == "other")).first()
    ```

    **Edit 2 — line ~438, in `create_car_in_db`:**
    ```python
    # Before:
    make_entity = db.query(CarMake).filter(CarMake.name == make).first()
    # After:
    make_entity = db.scalars(select(CarMake).where(CarMake.name == make)).first()
    ```

    **Edit 3 — line ~444, same function:**
    ```python
    # Before:
    car_model_entity = db.query(CarModel).filter(CarModel.car_make_id == make_entity.id, CarModel.name == model).first()
    # After:
    car_model_entity = db.scalars(
        select(CarModel).where(
            CarModel.car_make_id == make_entity.id,
            CarModel.name == model,
        )
    ).first()
    ```

    **Edit 4 — line ~491, in `create_car_orm_in_db`:**
    ```python
    # Before:
    make_entity = db.query(CarMake).filter(CarMake.name == make).first()
    # After:
    make_entity = db.scalars(select(CarMake).where(CarMake.name == make)).first()
    ```

    **Edit 5 — line ~497, same function:**
    ```python
    # Before:
    car_model_entity = db.query(CarModel).filter(CarModel.car_make_id == make_entity.id, CarModel.name == model).first()
    # After:
    car_model_entity = db.scalars(
        select(CarModel).where(
            CarModel.car_make_id == make_entity.id,
            CarModel.name == model,
        )
    ).first()
    ```

    **Edit 6 — line ~515, tail of `create_car_orm_in_db`:**
    ```python
    # Before:
    car = (
        db.query(CarGeneration)
        .options(joinedload(CarGeneration.car_model).joinedload(CarModel.car_make))
        .filter(CarGeneration.id == car.id)
        .first()
    )
    # After:
    car = db.scalars(
        select(CarGeneration)
        .options(joinedload(CarGeneration.car_model).joinedload(CarModel.car_make))
        .where(CarGeneration.id == car.id)
    ).first()
    ```

    **Also update the stale comment at line ~391:** Currently reads "...of the 8 residual 1.x db.query() calls tracked under WR-01. Delete." After this plan, ZERO residual db.query() remain in conftest.py. Change the comment to reflect this:
    ```python
    # IN-11: POST /api/users/ already auto-verifies email_verified=True when
    # TESTING=true (see endpoints/users.py::register_user), which conftest sets
    # at import time before any app code loads. The manual flip block that used
    # to live here was a no-op — it flipped True to True and happened to be two
    # of the legacy db.query() calls that Phase 4 WR-01 flagged as residue.
    # (The remaining 6 conftest helpers were migrated in Phase 07 plan 07-03 —
    # zero legacy .query() calls remain in this file.)
    ```

    After edits, run the full suite to confirm nothing broke — most of these helpers are used by many tests (category fixture, car fixtures, build_list tests, part tests). Any regression would show up immediately.

    Do NOT touch `backend/app/` — DATA-06 sweep already handled the app-side migration in Phase 4, and the guard test (`test_session_query_regression.py`) scopes to `backend/app/` so the test helpers were deliberately out of scope.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto --no-cov tests/ -x 2>&amp;1 | tail -5</automated>
  </verify>

  <acceptance_criteria>
    - `grep -c "db.query(\|db_session.query(" backend/tests/conftest.py` returns `0`
    - `grep -c "select(" backend/tests/conftest.py` returns at least the original count + 6 (verify increase)
    - `grep -n "from sqlalchemy import" backend/tests/conftest.py` shows `select` in the import list
    - `cd backend &amp;&amp; pytest -n auto --no-cov tests/ -x` exits 0 (full suite green — migration is behavior-preserving)
    - `grep -n "residual 1.x db.query" backend/tests/conftest.py` returns no matches (stale comment updated)
    - `cd backend &amp;&amp; pytest -n auto tests/api/endpoints/test_build_lists.py -x` exits 0 (a high-traffic consumer of the migrated car fixtures)
    - `cd backend &amp;&amp; pytest -n auto tests/api/endpoints/test_parts.py -x` exits 0 (another high-traffic consumer) — skip this criterion if file does not exist; run `cd backend &amp;&amp; pytest -n auto tests/ -k "part" --no-cov -x 2>&amp;1 | tail -3` instead.
  </acceptance_criteria>

  <done>
    Zero `db.query(...)` / `db_session.query(...)` call sites remain in `backend/tests/conftest.py`; import block has `select`; stale counter comment updated; full pytest suite passes.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test helpers → in-memory SQLite | Migrated code runs only in tests; no prod DB. |
| Dead code removal → import graph | Removing functions with 0 callers cannot break anything by definition; grep-verified before commit. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-03-01 | Tampering | Dead code removal | accept | Each removed helper has been grep-verified to have 0 external callers. A task-level grep check is re-run at execution time to catch any caller added between planning and execution. If a caller is found, that helper is retained and noted in the summary. |
| T-07-03-02 | Elevation of Privilege | Unused auth/admin helpers (`get_admin_dependencies`, `verify_entity_ownership_or_admin`) | accept | Neither is wired into any route. Their removal eliminates a potential footgun (future dev imports a dead helper expecting it to enforce something it doesn't). Live admin enforcement uses `get_current_admin_user` from `dependencies/auth.py` — not affected. |
| T-07-03-03 | Spoofing / Identity | vote_operation / report_creation helpers | accept | Zero callers. Votes and reports are now handled exclusively by `base_vote_router` / `base_report_router` (per CLAUDE.md) which are unaffected by this cleanup. |
| T-07-03-04 | Information Disclosure | conftest.py migration | accept | Pure syntactic change from Query API 1.x (`.query().filter().first()`) to 2.0 (`.scalars(select().where()).first()`). Same SQL emitted; same results. Test-only; no production code touched. |

**No new attack surface introduced.** Removing dead auth-adjacent helpers slightly reduces footgun surface. Test helper migration is behavior-preserving.
</threat_model>

<verification>
1. `cd backend && pytest -n auto --no-cov tests/ -x 2>&1 | tail -3` — full suite exits 0.
2. `test ! -f backend/tests/crawlers/test_runner_circuit_breaker.py` — exit 0 (file gone).
3. `grep -c "def " backend/app/api/utils/common_patterns.py` — returns approximately 14 (13 live helpers + `admin_only` wrapper). Down from 24 pre-change.
4. `grep -c "db.query(\|db_session.query(" backend/tests/conftest.py` — returns `0`.
5. `grep -rn "\\bget_standard_endpoint_dependencies\\b\\|\\bhandle_vote_operation\\b\\|\\bremove_vote_operation\\b\\|\\bhandle_report_creation\\b" backend/ 2>/dev/null | grep -v common_patterns.py` — returns no matches.
</verification>

<success_criteria>
- Phase 7 success criterion 6 (dead-code cleanup) closed:
  - `test_runner_circuit_breaker.py` stub removed
  - `common_patterns.py` dead helpers deleted (11 total)
  - 6 legacy `db.query(...)` sites in `backend/tests/conftest.py` migrated to `select()` + `session.scalars()`
- Full pytest suite still passes.
</success_criteria>

<output>
After completion, create `.planning/phases/07-v1-residue-cleanup/07-03-SUMMARY.md`. Frontmatter must include `tech_debt_items_closed: [TD-03-01, TD-03-02, TD-04-WR01-conftest]` plus a note that the `backend/tests/conftest.py` 8-site audit count was revised to 6 based on current tree state.
</output>
