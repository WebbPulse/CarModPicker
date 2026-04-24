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
import ast
from pathlib import Path


_HELPER_NAME = "_apply_build_list_filters"

_BUILD_LISTS_PATH = (
    Path(__file__).resolve().parent.parent
    / "app" / "api" / "endpoints" / "build_lists.py"
)


def _load_source() -> str:
    assert _BUILD_LISTS_PATH.exists(), f"Missing file: {_BUILD_LISTS_PATH}"
    return _BUILD_LISTS_PATH.read_text()


def _load_tree() -> ast.Module:
    return ast.parse(_load_source())


def test_apply_build_list_filters_helper_exists() -> None:
    """AST-based check: the helper must be defined exactly once as a
    module-level `FunctionDef`. Text `src.count("def ...")` would also
    match a comment or docstring that happens to contain that literal
    string, so we parse and count real definitions instead.
    """
    tree = _load_tree()
    defs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == _HELPER_NAME
    ]
    assert len(defs) == 1, (
        f"Expected exactly 1 FunctionDef named {_HELPER_NAME!r}, "
        f"found {len(defs)}. The IN-01 helper must exist exactly once."
    )


def test_helper_invoked_from_both_count_and_main_select() -> None:
    """AST-based check: the helper must be *called* exactly twice
    (count-select path and main-select path).

    Counting string occurrences as in the pre-IN-04 form produced
    false positives: a docstring or comment mentioning the helper by
    name would satisfy the >=3 threshold even if real call sites
    regressed from 2 to 1. Parsing instead asserts on invocations.
    """
    tree = _load_tree()
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _HELPER_NAME
    ]
    assert len(calls) == 2, (
        f"Expected exactly 2 call sites for {_HELPER_NAME!r} "
        f"(count-select + main-select paths), found {len(calls)}. "
        "IN-01 consolidation may have regressed."
    )


def test_in01_docstring_marker_present() -> None:
    src = _load_source()
    assert "IN-01" in src, (
        "IN-01 marker comment missing from build_lists.py — "
        "future readers will not see the consolidation rationale."
    )
