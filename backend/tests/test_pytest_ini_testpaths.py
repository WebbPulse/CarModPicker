"""WR-01 regression: pins `testpaths = tests` in `backend/pytest.ini` so the
full pytest suite continues to collect from `backend/tests/` and cannot silently
regress to `testpaths = app/tests` (the pre-audit value).

The v1.0-MILESTONE-AUDIT.md flagged WR-01 as "pytest.ini testpaths points to
`app/tests` not `tests`" — inspection on current HEAD showed `testpaths = tests`
(correct), so WR-01 was treated as non-issue by Phase 07 plan 07-01. This
static-structure test is the permanent pin so any future drift fails CI.
"""

from pathlib import Path

_PYTEST_INI = Path(__file__).resolve().parent.parent / "pytest.ini"


def test_pytest_ini_testpaths_is_tests() -> None:
    assert _PYTEST_INI.exists(), f"Missing pytest.ini at {_PYTEST_INI}"
    for line in _PYTEST_INI.read_text().splitlines():
        if line.startswith("testpaths"):
            assert line.strip() == "testpaths = tests", (
                f"WR-01 regression: expected `testpaths = tests`, got {line!r}. "
                "Full suite collection depends on this value."
            )
            return
    raise AssertionError("No `testpaths` directive found in pytest.ini")
