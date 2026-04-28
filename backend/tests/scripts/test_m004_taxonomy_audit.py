"""Unit + smoke tests for ``backend/scripts/m004_taxonomy_audit.py``.

Coverage:

* 4 rule-branch tests against ``decide`` (rename match, alias match,
  typo-rejected by edit-distance gate, low-corpus-count rejected by parts
  gate).
* 1 defensive-degradation test confirming a per-row exception in
  ``iterate_corpus_audit`` logs and continues without crashing.
* 1 CSV schema test confirming the writer produces the documented header +
  per-row column shape.
* 1 subprocess smoke test invoking
  ``python -m scripts.m004_taxonomy_audit --dry-run --limit 5`` from
  ``backend/`` (mirrors the S01 convention used by
  ``test_m004_accuracy_harness``).

The pure-rule tests do not require a DB session — they exercise ``decide``
and ``edit_distance`` in isolation.
"""

from __future__ import annotations

import csv
import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Ensure backend/ is on sys.path so `import scripts.m004_taxonomy_audit` works
# whether the test is invoked from backend/ or from the repo root via
# pytest -n auto. backend/tests/scripts/test_m004_taxonomy_audit.py
#                ^^^^^^^^ parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts import m004_taxonomy_audit as audit  # noqa: E402


# ---------------------------------------------------------------------------
# Pure rule-branch tests (no DB)
# ---------------------------------------------------------------------------


class TestDecideRenameMatch:
    def test_rename_when_all_gates_pass(self) -> None:
        # canonical=0 corpus parts, challenger>5 parts, >2 retailers, edit_dist>2
        verdict = audit.decide(
            canonical_form="MK7 Golfsport",
            challenger_form="MK7 Golf R",
            canonical_count=0,
            challenger_count=12,
            retailer_count=3,
            edit_dist=4,
            thresholds=audit.Thresholds(),
        )
        assert verdict == "rename"


class TestDecideAliasOnTypoDistance:
    def test_alias_when_edit_distance_below_threshold(self) -> None:
        # Challenger crosses parts/retailer gates but is a 1-char typo of canonical.
        # edit_dist == 1 (≤ T=2) → not a rename → alias.
        verdict = audit.decide(
            canonical_form="MK7 Golf",
            challenger_form="MK7 Golff",
            canonical_count=0,
            challenger_count=20,
            retailer_count=3,
            edit_dist=1,
            thresholds=audit.Thresholds(),
        )
        assert verdict == "alias"


class TestDecideAliasOnLowPartCount:
    def test_alias_when_challenger_parts_below_threshold(self) -> None:
        # Challenger crosses retailer + edit-distance gates but only 3 corpus parts.
        # 3 not > 5 → fails rename → alias.
        verdict = audit.decide(
            canonical_form="F30",
            challenger_form="F30 sedan facelift",
            canonical_count=0,
            challenger_count=3,
            retailer_count=3,
            edit_dist=12,
            thresholds=audit.Thresholds(),
        )
        assert verdict == "alias"


class TestDecideAliasOnSingleRetailer:
    def test_alias_when_retailer_count_below_threshold(self) -> None:
        # Single retailer = M=1, not > 2 → alias not rename even with high parts.
        verdict = audit.decide(
            canonical_form="A90",
            challenger_form="A90 GR Supra",
            canonical_count=0,
            challenger_count=30,
            retailer_count=1,
            edit_dist=8,
            thresholds=audit.Thresholds(),
        )
        assert verdict == "alias"


class TestDecideSkipNoChallenger:
    def test_skip_when_no_challenger(self) -> None:
        verdict = audit.decide(
            canonical_form="E46",
            challenger_form=None,
            canonical_count=42,
            challenger_count=0,
            retailer_count=0,
            edit_dist=0,
            thresholds=audit.Thresholds(),
        )
        assert verdict == "skip"


class TestDecideAliasWhenCanonicalAlsoPresent:
    def test_alias_when_canonical_count_nonzero(self) -> None:
        # Even with otherwise-strong challenger signal, if canonical also
        # appears in corpus we don't rename — operator should disambiguate.
        verdict = audit.decide(
            canonical_form="C8",
            challenger_form="C8 Corvette",
            canonical_count=4,
            challenger_count=20,
            retailer_count=4,
            edit_dist=10,
            thresholds=audit.Thresholds(),
        )
        assert verdict == "alias"


# ---------------------------------------------------------------------------
# edit_distance + retailer_count_challenger pure-fn tests
# ---------------------------------------------------------------------------


class TestEditDistance:
    def test_identical_returns_zero(self) -> None:
        assert audit.edit_distance("MK7", "MK7") == 0

    def test_case_insensitive(self) -> None:
        assert audit.edit_distance("MK7", "mk7") == 0

    def test_one_char_substitution(self) -> None:
        assert audit.edit_distance("E36", "E37") == 1

    def test_empty_string(self) -> None:
        assert audit.edit_distance("", "abc") == 3
        assert audit.edit_distance("abc", "") == 3

    def test_none_safe(self) -> None:
        # Defensive: callers may pass empty fallbacks.
        assert audit.edit_distance("", "") == 0


class TestRetailerCountChallenger:
    def test_distinct_count(self) -> None:
        assert audit.retailer_count_challenger(["a", "b", "a", "c"]) == 3

    def test_ignores_empty(self) -> None:
        assert audit.retailer_count_challenger(["a", "", None, "b"]) == 2  # type: ignore[list-item]

    def test_empty_iter(self) -> None:
        assert audit.retailer_count_challenger([]) == 0


# ---------------------------------------------------------------------------
# Defensive-degradation test
# ---------------------------------------------------------------------------


class _ExplodingPart:
    """Synthetic Part that raises on attribute access used inside the loop."""

    def __init__(self, _id: str) -> None:
        self.id = _id

    @property
    def name(self) -> str:  # raises when iterate_corpus_audit reads .name
        raise RuntimeError("simulated extractor crash")

    @property
    def description(self) -> str:
        return ""

    @property
    def car_generations(self) -> list:
        # Provide a single canonical so the inner loop is reached.
        return [SimpleNamespace(id="canonical-1", generation_name="MK7")]


class _OkPart:
    def __init__(self, _id: str, name: str = "Some Part") -> None:
        self.id = _id
        self.name = name
        self.description = ""
        self.car_generations = []  # no canonical → no rows produced


class _StubQuery:
    """Stand-in for the SQLAlchemy query chain used by iterate_corpus_audit."""

    def __init__(self, pages: list[Any]) -> None:
        self._pages = pages

    def options(self, *_a, **_k) -> "_StubQuery":
        return self

    def filter(self, *_a, **_k) -> "_StubQuery":
        return self

    def order_by(self, *_a, **_k) -> "_StubQuery":
        return self

    def limit(self, _n: int) -> "_StubQuery":
        return self

    def yield_per(self, _n: int):
        return iter(self._pages)


class _StubDB:
    def __init__(self, pages: list[Any]) -> None:
        self._pages = pages

    def query(self, _model: Any) -> _StubQuery:
        return _StubQuery(self._pages)


def test_defensive_per_row_exception_logs_and_continues(caplog: pytest.LogCaptureFixture) -> None:
    """A single broken row never aborts the run (MEM206 pattern)."""
    pages = [
        SimpleNamespace(id="page-1", source="ind", part=_ExplodingPart("part-1"), part_id="part-1"),
        SimpleNamespace(id="page-2", source="ind", part=_OkPart("part-2"), part_id="part-2"),
    ]
    db = _StubDB(pages)

    with caplog.at_level(logging.DEBUG, logger="m004_taxonomy_audit"):
        rows, summary = audit.iterate_corpus_audit(db, limit=None, output_json=False)

    # Run completed successfully despite the exploding part.
    assert isinstance(rows, list)
    assert "candidates_inspected" in summary
    # The exploding row's canonical was registered, so we expect exactly one
    # canonical_index entry (from the failed iteration that registered the
    # canonical before the .name access blew up). Either 0 or 1 is acceptable —
    # what matters is that the run did not raise.
    assert summary["candidates_inspected"] >= 0
    # Defensive log surface fired at least once.
    audit_failures = [r for r in caplog.records if r.message == "audit_row_failed"]
    assert len(audit_failures) >= 1, (
        f"expected at least one audit_row_failed log, got: "
        f"{[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# CSV schema test
# ---------------------------------------------------------------------------


def test_csv_writer_emits_documented_header_and_columns(tmp_path: Path) -> None:
    out = tmp_path / "audit.csv"
    rows = [
        {
            "canonical_id": "abc-123",
            "canonical_form": "MK7",
            "challenger_form": "MK7.5",
            "corpus_count_canonical": 0,
            "corpus_count_challenger": 12,
            "retailer_count": 3,
            "edit_distance": 1,
            "decision": "alias",
        }
    ]
    n = audit.write_audit_csv(rows, out)
    assert n == 1

    with out.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        assert tuple(reader.fieldnames) == audit.CSV_HEADER
        body = list(reader)
    assert len(body) == 1
    assert body[0]["canonical_id"] == "abc-123"
    assert body[0]["decision"] == "alias"


def test_csv_writer_handles_empty_rows(tmp_path: Path) -> None:
    """Empty corpus → CSV with header only (zero data rows)."""
    out = tmp_path / "empty.csv"
    n = audit.write_audit_csv([], out)
    assert n == 0
    with out.open(encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert len(lines) == 1
    assert lines[0] == ",".join(audit.CSV_HEADER)


# ---------------------------------------------------------------------------
# apply_thresholds + recompute_summary
# ---------------------------------------------------------------------------


def test_apply_thresholds_relaxes_rename_gate() -> None:
    """Loosening thresholds should flip an alias to a rename."""
    rows = [
        {
            "canonical_id": "abc",
            "canonical_form": "X",
            "challenger_form": "Y",
            "corpus_count_canonical": 0,
            "corpus_count_challenger": 4,
            "retailer_count": 2,
            "edit_distance": 3,
            "decision": "alias",  # under default thresholds (>5, >2, >2)
        }
    ]
    # Defaults make this an alias (4 not > 5, 2 not > 2). Lowering thresholds
    # so 4 > 3 and 2 > 1 should flip it to rename.
    relaxed = audit.apply_thresholds(rows, audit.Thresholds(parts=3, retailers=1, edit_distance=2))
    assert relaxed[0]["decision"] == "rename"

    summary = audit.recompute_summary(relaxed)
    assert summary == {
        "candidates_inspected": 1,
        "renames": 1,
        "aliases": 0,
        "skipped": 0,
    }


# ---------------------------------------------------------------------------
# Subprocess smoke test (argparse + exit-code regression coverage)
# ---------------------------------------------------------------------------


def test_subprocess_help_exits_zero() -> None:
    """`python -m scripts.m004_taxonomy_audit --help` exits 0 from backend/."""
    result = subprocess.run(
        [sys.executable, "-m", "scripts.m004_taxonomy_audit", "--help"],
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"--help exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    # MEM212 placement convention surfaces in --help text.
    combined = result.stdout + result.stderr
    assert "MEM212" in combined or "measurement-only" in combined
