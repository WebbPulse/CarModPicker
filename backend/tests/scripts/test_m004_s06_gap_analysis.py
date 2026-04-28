"""Unit + smoke tests for ``backend/scripts/m004_s06_gap_analysis.py``.

Coverage (mirrors S06 T01 plan, Verification section):

* Pure-helper tests for ``top_n_categories`` (sort + truncation).
* Pure-helper tests for ``choose_qualitative_fallback`` (corpus + zero-corpus
  branches).
* Pure-helper tests for ``build_gap_report`` (envelope shape).
* MEM216 zero-corpus degrade path for
  ``iterate_universal_routed_categories`` via monkeypatched stub DB.
* One subprocess smoke test exercising the CLI end-to-end (MEM209 cwd).

The pure-helper tests do not require a DB session.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# backend/tests/scripts/test_m004_s06_gap_analysis.py
#                ^^^^^^^^ parents[2] = backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts import m004_s06_gap_analysis as gap  # noqa: E402


# ---------------------------------------------------------------------------
# top_n_categories
# ---------------------------------------------------------------------------


class TestTopNCategories:
    def test_empty_dict_returns_empty_list(self) -> None:
        assert gap.top_n_categories({}, n=20) == []

    def test_truncates_to_top_n_by_count_desc(self) -> None:
        counts = {"a": 1, "b": 5, "c": 3, "d": 4, "e": 2}
        result = gap.top_n_categories(counts, n=3)
        assert result == [
            {"name": "b", "parts_count": 5},
            {"name": "d", "parts_count": 4},
            {"name": "c", "parts_count": 3},
        ]

    def test_returns_all_when_fewer_than_n(self) -> None:
        # Negative test (Q7): top-N truncation behaviour when fewer categories
        # exist than the cap.
        counts = {"a": 2, "b": 1}
        result = gap.top_n_categories(counts, n=20)
        assert result == [
            {"name": "a", "parts_count": 2},
            {"name": "b", "parts_count": 1},
        ]

    def test_ties_broken_by_name_asc(self) -> None:
        counts = {"zebra": 3, "apple": 3, "mango": 3}
        result = gap.top_n_categories(counts, n=20)
        assert [r["name"] for r in result] == ["apple", "mango", "zebra"]


# ---------------------------------------------------------------------------
# choose_qualitative_fallback
# ---------------------------------------------------------------------------


class TestChooseQualitativeFallback:
    def test_zero_corpus_returns_planner_pre_commits(self) -> None:
        # Negative test (Q7): qualitative fallback when zero_corpus=True.
        result = gap.choose_qualitative_fallback(
            per_field_non_null={},
            top_universal_routed=[],
            zero_corpus=True,
        )
        assert result == {
            "chosen_universal_field": "manufacturer_part_number",
            "chosen_category_spec_slug": "wheel",
            "source": "qualitative_fallback",
        }

    def test_empty_field_counts_falls_back_to_planner_pre_commits(self) -> None:
        # Even when zero_corpus=False, an empty per-field block can't drive a
        # corpus-based choice; fall back to planner pre-commits.
        result = gap.choose_qualitative_fallback(
            per_field_non_null={},
            top_universal_routed=[{"name": "x", "parts_count": 1}],
            zero_corpus=False,
        )
        assert result["source"] == "qualitative_fallback"
        assert result["chosen_universal_field"] == "manufacturer_part_number"
        assert result["chosen_category_spec_slug"] == "wheel"

    def test_corpus_picks_lowest_count_universal_field(self) -> None:
        result = gap.choose_qualitative_fallback(
            per_field_non_null={
                "weight_grams": 100,
                "material": 50,
                "finish": 5,
                "warranty_days": 200,
                "fitment_notes": 80,
            },
            top_universal_routed=[
                {"name": "wheels", "parts_count": 42},
                {"name": "exhaust", "parts_count": 17},
            ],
            zero_corpus=False,
        )
        assert result == {
            "chosen_universal_field": "finish",
            "chosen_category_spec_slug": "wheels",
            "source": "corpus",
        }

    def test_corpus_ties_broken_by_field_name_asc(self) -> None:
        result = gap.choose_qualitative_fallback(
            per_field_non_null={
                "weight_grams": 0,
                "material": 0,
                "finish": 1,
                "warranty_days": 1,
                "fitment_notes": 1,
            },
            top_universal_routed=[{"name": "wheels", "parts_count": 1}],
            zero_corpus=False,
        )
        # Tie at 0 between weight_grams and material; alphabetically material
        # wins.
        assert result["chosen_universal_field"] == "material"
        assert result["source"] == "corpus"


# ---------------------------------------------------------------------------
# build_gap_report
# ---------------------------------------------------------------------------


class TestBuildGapReport:
    def test_zero_corpus_envelope_shape(self) -> None:
        report = gap.build_gap_report(
            per_universal_field_non_null={},
            universal_routed_counts={},
            corpus_total=0,
            zero_corpus=True,
            snapshot_taken_at="2026-04-30T00:00:00+00:00",
        )
        assert report == {
            "snapshot_taken_at": "2026-04-30T00:00:00+00:00",
            "corpus_total": 0,
            "zero_corpus": True,
            "per_universal_field_non_null": {},
            "top_universal_routed_categories": [],
            "qualitative_fallback": {
                "chosen_universal_field": "manufacturer_part_number",
                "chosen_category_spec_slug": "wheel",
                "source": "qualitative_fallback",
            },
        }

    def test_non_zero_corpus_envelope_includes_top_n_and_corpus_source(self) -> None:
        report = gap.build_gap_report(
            per_universal_field_non_null={
                "weight_grams": 10,
                "material": 5,
                "finish": 2,
                "warranty_days": 8,
                "fitment_notes": 12,
            },
            universal_routed_counts={"wheels": 7, "exhaust": 3, "tires": 2},
            corpus_total=20,
            zero_corpus=False,
            snapshot_taken_at="2026-04-30T01:00:00+00:00",
            top_n=2,
        )
        assert report["corpus_total"] == 20
        assert report["zero_corpus"] is False
        assert report["per_universal_field_non_null"]["finish"] == 2
        # top_n=2 truncates the three categories down to two.
        assert report["top_universal_routed_categories"] == [
            {"name": "wheels", "parts_count": 7},
            {"name": "exhaust", "parts_count": 3},
        ]
        assert report["qualitative_fallback"]["source"] == "corpus"
        assert report["qualitative_fallback"]["chosen_universal_field"] == "finish"
        assert (
            report["qualitative_fallback"]["chosen_category_spec_slug"] == "wheels"
        )


# ---------------------------------------------------------------------------
# MEM216 zero-corpus degrade path for iterate_universal_routed_categories
# ---------------------------------------------------------------------------


def test_iterate_universal_routed_categories_degrades_to_zero_corpus_on_operational_error() -> None:
    """Per MEM216 — missing crawled_pages table must NOT abort the gap run."""
    from sqlalchemy.exc import OperationalError

    class _ExplodingQuery:
        def options(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def yield_per(self, _n):
            raise OperationalError(
                "SELECT", {}, Exception("no such table: crawled_pages")
            )

    class _StubDB:
        def query(self, _model):
            return _ExplodingQuery()

    counts, total, zero_corpus = gap.iterate_universal_routed_categories(
        _StubDB(), limit=None
    )
    assert counts == {}
    assert total == 0
    assert zero_corpus is True


def test_iterate_universal_routed_categories_counts_universal_routed_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity-check the happy path: walk a small in-memory page list and
    confirm only universal-routed categories are counted (and only once per
    distinct part id).
    """

    def _make_part(part_id: Any, *, category_name: str | None) -> Any:
        category = SimpleNamespace(name=category_name) if category_name else None
        return SimpleNamespace(
            id=part_id,
            name="filler",
            description="filler",
            category=category,
        )

    parts = [
        # Routes to 'universal' (no special keyword).
        _make_part("p1", category_name="exhaust"),
        # Same part_id repeated — must be counted once.
        _make_part("p1", category_name="exhaust"),
        # Routes to 'brake' (single-subslug category) — NOT counted.
        _make_part("p2", category_name="brakes"),
        # Routes to 'universal'. (Intake stays universal-routed post-S06;
        # 'wheels' was deliberately bridged to the dedicated 'wheel' spec
        # in T04, so it no longer satisfies this fixture's intent.)
        _make_part("p3", category_name="intake"),
        # category=None — skipped silently.
        _make_part("p4", category_name=None),
    ]
    pages = [
        SimpleNamespace(id=f"page-{i}", part=part) for i, part in enumerate(parts)
    ]

    class _Query:
        def options(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def yield_per(self, _n):
            return iter(pages)

    class _StubDB:
        def query(self, _model):
            return _Query()

    counts, total, zero_corpus = gap.iterate_universal_routed_categories(
        _StubDB(), limit=None
    )
    assert zero_corpus is False
    # Distinct parts walked: p1, p2, p3, p4 → total=4.
    assert total == 4
    # Only p1 (exhaust) and p3 (intake) route to universal; p2 → brake;
    # p4 has no category. p1 only counted once despite duplicate page.
    assert counts == {"exhaust": 1, "intake": 1}


# ---------------------------------------------------------------------------
# Subprocess smoke test (MEM209 cwd contract — must run from backend/)
# ---------------------------------------------------------------------------


def test_subprocess_writes_gap_report_and_exits_zero(tmp_path: Path) -> None:
    out = tmp_path / "s06-gap-report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_s06_gap_analysis",
            "--out",
            str(out),
        ],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**__import__("os").environ, "TESTING": "true"},
    )
    assert result.returncode == 0, (
        f"gap analysis exited {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert out.exists(), f"expected report at {out}; stderr={result.stderr}"
    payload = json.loads(out.read_text(encoding="utf-8"))
    # Required keys.
    assert "snapshot_taken_at" in payload, payload
    assert "corpus_total" in payload, payload
    assert "zero_corpus" in payload, payload
    assert "per_universal_field_non_null" in payload, payload
    assert "top_universal_routed_categories" in payload, payload
    assert "qualitative_fallback" in payload, payload
    qf = payload["qualitative_fallback"]
    assert qf["source"] in ("corpus", "qualitative_fallback"), qf
    # Stdout JSON envelope.
    stdout_lines = [ln for ln in result.stdout.strip().splitlines() if ln.startswith("{")]
    assert stdout_lines, f"expected at least one JSON line on stdout, got: {result.stdout!r}"
    parsed = json.loads(stdout_lines[-1])
    assert "qualitative_fallback" in parsed
