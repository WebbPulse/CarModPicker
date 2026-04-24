---
phase: 07
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/api/endpoints/build_lists.py
autonomous: true
tech_debt_items:
  - IN-01  # build_lists.py with-votes filter duplication helper (verify idempotently that IN-01's _apply_build_list_filters helper is live and complete)
must_haves:
  truths:
    - "`backend/app/api/endpoints/build_lists.py` defines a single `_apply_build_list_filters` helper that is invoked for BOTH the count-select (line ~177) and the main result-select (line ~191)"
    - "The count-select and the main-select apply identical predicates, so `total` and the paginated page slice are drawn from the same population"
    - "No duplicate filter predicate blocks remain at the prior audit line ranges 153-169 / 183-198 — both ranges now call the shared helper"
    - "Full backend test suite passes under `pytest -n auto` after the verification pass"
  artifacts:
    - path: "backend/app/api/endpoints/build_lists.py"
      provides: "IN-01 code-review fix pinned via explicit IN-01 docstring comment on the helper + a static test that greps for the helper's presence"
      contains: "def _apply_build_list_filters"
    - path: "backend/tests/test_build_lists_in01_helper.py"
      provides: "IN-01 static-structure regression: asserts _apply_build_list_filters exists and is called at least twice in build_lists.py (once for count, once for main select)"
      min_lines: 25
  key_links:
    - from: "backend/tests/test_build_lists_in01_helper.py"
      to: "backend/app/api/endpoints/build_lists.py"
      via: "read file as text and grep for helper def and call sites"
      pattern: "_apply_build_list_filters"
---

<objective>
Pin IN-01 (the duplicated with-votes filter block in `build_lists.py` consolidated into `_apply_build_list_filters`) so it cannot drift back into duplication. The helper already landed (`build_lists.py:155-173` with IN-01 docstring). This plan adds a lightweight static regression test that fails if the two call sites diverge or the helper is deleted.

Purpose: The v1.0 milestone audit's Phase 4 tech_debt item IN-01 says: "Duplicated filter block in build_lists.py with-votes paths (lines 153-169, 183-198)." The fix landed — a single `_apply_build_list_filters(stmt_)` is now invoked at line 177 (count path) and line 191 (main select path). This plan pins that invariant with a static grep test so a future PR that accidentally re-inlines one of the two call sites fails CI immediately.

Output: One new static-structure test file. No production code changes (unless a drift is discovered during verification).
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
Current state of `backend/app/api/endpoints/build_lists.py` (lines 151-192 — relevant excerpt):

```python
# IN-01: single helper for the /with-votes filter stack so the count-select
# and the main result-select cannot drift apart. Both selects must apply
# identical predicates — otherwise `total` and the paginated page would be
# taken from different populations.
def _apply_build_list_filters(stmt_: Any) -> Any:
    stmt_ = apply_standard_filters(
        query=stmt_,
        search=search,
        category_id=None,  # Build lists don't have categories
        search_fields=["name", "description"],
    )
    # Car filter: car_ids (make/model) takes precedence over single car_id
    if car_ids:
        stmt_ = stmt_.where(DBBuildList.car_id.in_(car_ids))
    elif car_id is not None:
        stmt_ = stmt_.where(DBBuildList.car_id == car_id)
    if owner_id is not None:
        stmt_ = stmt_.where(DBBuildList.user_id == owner_id)
    if min_cost_cents is not None:
        stmt_ = stmt_.where(func.coalesce(total_cost_subq.c.total_cost_cents, 0) >= min_cost_cents)
    if max_cost_cents is not None:
        stmt_ = stmt_.where(func.coalesce(total_cost_subq.c.total_cost_cents, 0) <= max_cost_cents)
    return stmt_

# Build base select for counting; join total_cost for cost filtering
base_stmt = select(DBBuildList).outerjoin(total_cost_subq, DBBuildList.id == total_cost_subq.c.build_list_id)
base_stmt = _apply_build_list_filters(base_stmt)  # ← call site 1 (count path)
...
# Apply the same filters via the shared helper
stmt = _apply_build_list_filters(stmt)  # ← call site 2 (main select path)
```

Two invocations. The test must assert count == 2 (exactly — growth to 3+ would mean a third call site appeared, which likely indicates a refactor regression).

Location of the handler function that contains `_apply_build_list_filters`: inside `read_build_lists_with_votes(...)` (the GET /with-votes endpoint).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: IN-01 static-structure regression test</name>

  <read_first>
    - backend/app/api/endpoints/build_lists.py  (lines 120-270 — verify current state of _apply_build_list_filters helper and both call sites)
    - .planning/v1.0-MILESTONE-AUDIT.md  (IN-01 description: "Duplicated filter block in build_lists.py with-votes paths (lines 153-169, 183-198)")
  </read_first>

  <files>backend/tests/test_build_lists_in01_helper.py</files>

  <behavior>
    - Test 1: `test_apply_build_list_filters_helper_exists` — reads `backend/app/api/endpoints/build_lists.py` as text and asserts the substring `def _apply_build_list_filters` appears exactly once.
    - Test 2: `test_helper_invoked_from_both_count_and_main_select` — reads the same file and asserts `_apply_build_list_filters(` appears at least 3 times total (once in the def, twice as call sites). Using `grep -c` semantics (count of occurrences).
    - Test 3: `test_in01_docstring_marker_present` — asserts the string `IN-01:` appears at least once as a comment marker near the helper, so future maintainers see the rationale.
  </behavior>

  <action>
    Create `backend/tests/test_build_lists_in01_helper.py` with 3 static-structure tests. No SQL, no fixtures — just file reads.

    ```python
    """IN-01 regression: pins the `_apply_build_list_filters` helper in
    `backend/app/api/endpoints/build_lists.py` so the with-votes filter
    stack cannot drift back into a duplicated pre-audit form.

    Phase 4 audit (v1.0-MILESTONE-AUDIT.md Phase 4 tech_debt item IN-01):
    > Duplicated filter block in build_lists.py with-votes paths
    > (lines 153-169, 183-198)

    Fix: one helper `_apply_build_list_filters(stmt_)` called from both
    the count-select and the main result-select, so `total` and the
    paginated page are always drawn from the same population.
    """
    from pathlib import Path


    _BUILD_LISTS_PATH = (
        Path(__file__).resolve().parent.parent
        / "app" / "api" / "endpoints" / "build_lists.py"
    )


    def _load_source() -> str:
        assert _BUILD_LISTS_PATH.exists(), f"Missing file: {_BUILD_LISTS_PATH}"
        return _BUILD_LISTS_PATH.read_text()


    def test_apply_build_list_filters_helper_exists() -> None:
        src = _load_source()
        occurrences = src.count("def _apply_build_list_filters")
        assert occurrences == 1, (
            f"Expected exactly 1 definition of _apply_build_list_filters, "
            f"found {occurrences}. The IN-01 helper must exist exactly once."
        )


    def test_helper_invoked_from_both_count_and_main_select() -> None:
        """The helper name must appear at least 3 times total:
        - 1× in the `def _apply_build_list_filters(...)` signature
        - 1× in the count-select path (`base_stmt = _apply_build_list_filters(base_stmt)`)
        - 1× in the main-select path (`stmt = _apply_build_list_filters(stmt)`)
        """
        src = _load_source()
        total = src.count("_apply_build_list_filters")
        assert total >= 3, (
            f"Expected >=3 mentions of _apply_build_list_filters (1 def + 2 call sites), "
            f"found {total}. IN-01 consolidation may have regressed."
        )


    def test_in01_docstring_marker_present() -> None:
        src = _load_source()
        assert "IN-01" in src, (
            "IN-01 marker comment missing from build_lists.py — "
            "future readers will not see the consolidation rationale."
        )
    ```

    Do NOT modify `build_lists.py` — IN-01 is already fixed (helper at line 155, call sites at 177 and 191). This plan pins the fix statically so CI catches any accidental re-duplication.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto tests/test_build_lists_in01_helper.py -v</automated>
  </verify>

  <acceptance_criteria>
    - `cd backend &amp;&amp; pytest -n auto tests/test_build_lists_in01_helper.py -v` exits 0 with 3 passed
    - `grep -c "def _apply_build_list_filters" backend/app/api/endpoints/build_lists.py` returns exactly `1`
    - `grep -c "_apply_build_list_filters" backend/app/api/endpoints/build_lists.py` returns at least `3` (def + 2 call sites)
    - `grep -q "IN-01" backend/app/api/endpoints/build_lists.py` (marker present)
  </acceptance_criteria>

  <done>
    Three tests in `backend/tests/test_build_lists_in01_helper.py` pass. IN-01 pinned. Zero production code changes.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Filesystem reads in tests | Test only reads one file (`build_lists.py`) within the repo. No external I/O, no attack surface. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-02-01 | Tampering | Query-result filter predicates | mitigate | This plan strengthens the existing defense. Before IN-01, divergent predicates between count-select and main-select could return a `total` and `data` computed on different populations — a subtle information disclosure / authorization bypass vector. The helper ensures identical predicates; the new static test ensures the helper cannot be bypassed by a future refactor. |
| T-07-02-02 | Spoofing | N/A | N/A | No auth or identity surface changed. |

**No new attack surface introduced.** The static test strengthens the filter-identity invariant already shipped with IN-01.
</threat_model>

<verification>
1. `cd backend && pytest -n auto tests/test_build_lists_in01_helper.py -v` — 3 passed.
2. `grep -c "def _apply_build_list_filters" backend/app/api/endpoints/build_lists.py` → `1`
3. `grep -c "_apply_build_list_filters" backend/app/api/endpoints/build_lists.py` → at least `3`
</verification>

<success_criteria>
- IN-01 (part of phase 7 success criterion 5) closed: `build_lists.py` with-votes filter duplication helper pinned by a static regression test.
</success_criteria>

<output>
After completion, create `.planning/phases/07-v1-residue-cleanup/07-02-SUMMARY.md`. Frontmatter must include `tech_debt_items_closed: [IN-01]`.
</output>
