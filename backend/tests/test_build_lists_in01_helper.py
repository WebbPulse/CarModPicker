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
    - 1x in the `def _apply_build_list_filters(...)` signature
    - 1x in the count-select path (`base_stmt = _apply_build_list_filters(base_stmt)`)
    - 1x in the main-select path (`stmt = _apply_build_list_filters(stmt)`)
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
