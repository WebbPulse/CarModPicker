"""Pins testpaths = tests in backend/pytest.ini so full suite collection cannot silently drift."""

from pathlib import Path

_PYTEST_INI = Path(__file__).resolve().parent.parent / "pytest.ini"


def test_pytest_ini_testpaths_is_tests() -> None:
    """pytest.ini declares testpaths = tests and nothing else."""
    assert _PYTEST_INI.exists(), f"Missing pytest.ini at {_PYTEST_INI}"
    for line in _PYTEST_INI.read_text().splitlines():
        if line.startswith("testpaths"):
            assert line.strip() == "testpaths = tests", (
                f"WR-01 regression: expected `testpaths = tests`, got {line!r}. "
                "Full suite collection depends on this value."
            )
            return
    raise AssertionError("No `testpaths` directive found in pytest.ini")
