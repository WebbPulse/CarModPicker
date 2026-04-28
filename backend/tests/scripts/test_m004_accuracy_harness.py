"""Smoke + negative tests for ``backend/scripts/m004_accuracy_harness.py``.

These tests invoke the harness as a subprocess (``python -m
scripts.m004_accuracy_harness``) so we exercise the actual CLI surface — the
in-process call path is covered indirectly by the per-signal scoring tests in
``test_m004_scoring.py``. Subprocess invocation also catches argparse/exit-code
regressions that an in-process call would miss.

Coverage:

* ``--corpus gold`` against a tmp 3-row gold-set fixture exits 0, prints one
  ``validate_baseline``-passing JSON line per signal.
* ``--baseline-out`` writes per-signal JSON files that round-trip through
  ``validate_baseline``.
* ``--baseline-compare`` against a synthetic prior baseline showing a 5%
  regression exits 1 and emits ``regressed=true`` for that signal.
* Missing gold-set file exits 2 with structured error.
* Schema-drift baseline (wrong ``harness_version``) exits 3.
* (S03 T04) ``_predict_manufacturer`` is invoked with html and resolves the
  JSON-LD brand on an HTML-only row (no title/description signal). Locks the
  new contract so a future signature regression breaks loudly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# backend/ is the working directory the harness is invoked from
_BACKEND_DIR = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _row(
    *,
    part_id: str,
    retailer: str,
    category: str,
    tier: str,
    raw_name: str,
    raw_description: str,
    html_excerpt: str,
    truth_manufacturer: str | None,
    truth_category: str | None,
    truth_specifications: dict[str, Any],
    truth_car_triples: list[list[str]] | None = None,
) -> dict[str, Any]:
    return {
        "part_id": part_id,
        "retailer": retailer,
        "category": category,
        "tier": tier,
        "raw_name": raw_name,
        "raw_description": raw_description,
        "html_excerpt": html_excerpt,
        "truth_car_triples": truth_car_triples or [],
        "truth_manufacturer": truth_manufacturer,
        "truth_category": truth_category,
        "truth_specifications": truth_specifications,
        "labeled_at": "2026-01-01T00:00:00+00:00",
        "labeled_by": "human",
    }


@pytest.fixture
def low_score_gold_set(tmp_path: Path) -> Path:
    """Three-row gold set whose `truth_manufacturer` is engineered to mismatch
    whatever the universal predictor extracts from each row's HTML/title/desc.

    Required because the realistic ``tiny_gold_set`` fixture now scores 1.0
    on manufacturer post-S03 (predictor extracts JSON-LD/microdata/OG brands
    correctly), so a "+0.5 inflate the baseline" regression-detection test
    saturates at 1.0/1.0 and produces delta=0 — no regression to detect.
    Setting truth to "DefinitelyNotMatching" forces current=0.0, so an
    inflated prior of 1.0 gives a clean delta=-1.0 regression every time.
    """
    rows = [
        _row(
            part_id="lowscore-row-001",
            retailer="ind",
            category="suspension",
            tier="T0",
            raw_name="KW Variant 3 Coilover Kit",
            raw_description="KW Variant 3 coilovers.",
            html_excerpt=(
                '<html><head><script type="application/ld+json">'
                '{"@type":"Product","brand":{"@type":"Brand","name":"KW"}}'
                "</script></head><body></body></html>"
            ),
            truth_manufacturer="DefinitelyNotMatchingBrandA",
            truth_category="suspension",
            truth_specifications={},
        ),
        _row(
            part_id="lowscore-row-002",
            retailer="bimmerworld",
            category="brakes",
            tier="T1",
            raw_name="Brembo Brake Pads",
            raw_description="Brembo high-performance brake pads.",
            html_excerpt='<html><body></body></html>',
            truth_manufacturer="DefinitelyNotMatchingBrandB",
            truth_category="brakes",
            truth_specifications={},
        ),
        _row(
            part_id="lowscore-row-003",
            retailer="rallysportdirect",
            category="exhaust",
            tier="T2",
            raw_name="Borla Cat-Back Exhaust",
            raw_description="Borla S-Type exhaust system.",
            html_excerpt='<html><body></body></html>',
            truth_manufacturer="DefinitelyNotMatchingBrandC",
            truth_category="exhaust",
            truth_specifications={},
        ),
    ]
    out = tmp_path / "low_parts.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return out


@pytest.fixture
def tiny_gold_set(tmp_path: Path) -> Path:
    """Three-row gold set covering all five signals with realistic HTML."""
    rows = [
        _row(
            part_id="test-row-001",
            retailer="ind",
            category="suspension",
            tier="T0",
            raw_name="KW Variant 3 Coilover Kit",
            raw_description="KW Variant 3 coilovers. Material: stainless steel.",
            html_excerpt=(
                '<html><head>'
                '<script type="application/ld+json">'
                '{"@type":"Product","brand":{"@type":"Brand","name":"KW"}}'
                "</script></head><body>"
                '<table><tr><td>Material</td><td>Stainless Steel</td></tr></table>'
                "</body></html>"
            ),
            truth_manufacturer="KW",
            truth_category="suspension",
            truth_specifications={"material": "stainless steel"},
        ),
        _row(
            part_id="test-row-002",
            retailer="bimmerworld",
            category="brakes",
            tier="T1",
            raw_name="Brembo Brake Pads",
            raw_description="Brembo high-performance brake pads.",
            html_excerpt=(
                '<html><body>'
                '<div itemscope><span itemprop="brand">Brembo</span></div>'
                "</body></html>"
            ),
            truth_manufacturer="Brembo",
            truth_category="brakes",
            truth_specifications={},
        ),
        _row(
            part_id="test-row-003",
            retailer="rallysportdirect",
            category="exhaust",
            tier="T2",
            raw_name="Borla Cat-Back Exhaust",
            raw_description="Borla S-Type exhaust system.",
            html_excerpt=(
                '<html><head><meta property="og:brand" content="Borla">'
                "</head><body></body></html>"
            ),
            truth_manufacturer="Borla",
            truth_category="exhaust",
            truth_specifications={},
        ),
    ]
    out = tmp_path / "parts.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return out


def _run_harness(*args: str, cwd: Path = _BACKEND_DIR) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scripts.m004_accuracy_harness", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _parse_stdout_lines(stdout: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Happy path: --corpus gold runs all signals
# ---------------------------------------------------------------------------


class TestGoldCorpusSmoke:
    def test_all_signals_exit_zero_and_validate(self, tiny_gold_set: Path) -> None:
        result = _run_harness(
            "--signal", "all",
            "--corpus", "gold",
            "--gold-set", str(tiny_gold_set),
        )
        assert result.returncode == 0, (
            f"harness exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        lines = _parse_stdout_lines(result.stdout)
        # Five signals: car, manufacturer, category, spec_field_level, spec_part_level
        assert len(lines) == 5, f"expected 5 signal lines, got {len(lines)}: {lines}"

        # Every line should carry harness_version, signal, sample_size,
        # generated_at, and validate against the locked schema.
        from scripts.m004_baseline_schema import VALID_SIGNALS, validate_baseline

        seen_signals: set[str] = set()
        for line in lines:
            assert line["sample_size"] == 3
            assert line["signal"] in VALID_SIGNALS
            seen_signals.add(line["signal"])
            # Strip the convenience "n" key + any "compare" block before validate.
            envelope = {k: v for k, v in line.items() if k not in ("n", "compare")}
            validate_baseline(envelope)
        assert seen_signals == set(VALID_SIGNALS)

    def test_baseline_out_writes_per_signal_files(
        self, tiny_gold_set: Path, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "baselines"
        result = _run_harness(
            "--signal", "all",
            "--corpus", "gold",
            "--gold-set", str(tiny_gold_set),
            "--baseline-out", str(out_dir),
        )
        assert result.returncode == 0, result.stderr
        from scripts.m004_baseline_schema import VALID_SIGNALS, validate_baseline

        for signal in VALID_SIGNALS:
            path = out_dir / f"{signal}.json"
            assert path.exists(), f"baseline file missing: {path}"
            data = json.loads(path.read_text())
            validate_baseline(data)
            assert data["signal"] == signal


# ---------------------------------------------------------------------------
# --baseline-compare regression detection
# ---------------------------------------------------------------------------


class TestBaselineCompareDetectsRegression:
    def test_inflated_prior_triggers_regression_exit_1(
        self, low_score_gold_set: Path, tmp_path: Path
    ) -> None:
        # Step 1: generate the current run's baselines using the low-score
        # fixture so manufacturer P/R/F1 land at 0.0 (truth labels engineered
        # to mismatch what the universal predictor extracts).
        baseline_dir = tmp_path / "baselines"
        first = _run_harness(
            "--signal", "manufacturer",
            "--corpus", "gold",
            "--gold-set", str(low_score_gold_set),
            "--baseline-out", str(baseline_dir),
        )
        assert first.returncode == 0, first.stderr

        # Step 2: synthesize an inflated prior baseline pinned at 1.0 — the
        # current run scored 0.0, so the prior - current delta is -1.0,
        # well past the 0.02 absolute threshold.
        manufacturer_path = baseline_dir / "manufacturer.json"
        baseline = json.loads(manufacturer_path.read_text())
        for metric in ("precision", "recall", "f1"):
            baseline[metric] = 1.0
        manufacturer_path.write_text(json.dumps(baseline, indent=2) + "\n")

        # Step 3: re-run with --baseline-compare. The current run's metrics
        # are now ~1.0 below the inflated baseline → regressed=true → exit 1.
        result = _run_harness(
            "--signal", "manufacturer",
            "--corpus", "gold",
            "--gold-set", str(low_score_gold_set),
            "--baseline-compare", str(baseline_dir),
        )
        assert result.returncode == 1, (
            f"expected exit 1 for regression, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        lines = _parse_stdout_lines(result.stdout)
        # Exactly one signal line emitted (manufacturer) with a compare block.
        manufacturer_lines = [l for l in lines if l.get("signal") == "manufacturer"]
        assert manufacturer_lines, f"no manufacturer signal in: {lines}"
        compare = manufacturer_lines[0].get("compare")
        assert compare is not None
        assert compare["regressed"] is True
        # f1 metric should be marked regressed.
        f1_block = compare["metrics"]["f1"]
        assert f1_block["regressed"] is True
        assert f1_block["delta"] < 0


# ---------------------------------------------------------------------------
# --guard pass / fail
# ---------------------------------------------------------------------------


class TestR069Guard:
    def test_guard_pass_when_baseline_matches(
        self, tiny_gold_set: Path, tmp_path: Path
    ) -> None:
        guard_dir = tmp_path / "guard"
        first = _run_harness(
            "--signal", "all",
            "--corpus", "gold",
            "--gold-set", str(tiny_gold_set),
            "--baseline-out", str(guard_dir),
        )
        assert first.returncode == 0, first.stderr
        # Re-run against the freshly-written baseline → no regression.
        second = _run_harness(
            "--signal", "all",
            "--corpus", "gold",
            "--gold-set", str(tiny_gold_set),
            "--guard", str(guard_dir),
        )
        assert second.returncode == 0, (
            f"guard expected pass, got exit {second.returncode}\n{second.stderr}"
        )
        lines = _parse_stdout_lines(second.stdout)
        # The last line is the guard verdict.
        guard_lines = [l for l in lines if "guard_verdict" in l]
        assert guard_lines, f"no guard verdict in stdout: {lines}"
        assert guard_lines[-1]["guard_verdict"] == "pass"
        assert guard_lines[-1]["regressions"] == []

    def test_guard_fail_when_baseline_inflated(
        self, low_score_gold_set: Path, tmp_path: Path
    ) -> None:
        # Use the low-score fixture so manufacturer current=0.0; inflated
        # prior at 1.0 produces a 1.0 absolute drop, comfortably tripping
        # the 0.02 R069 threshold. The realistic tiny_gold_set fixture now
        # scores 1.0 post-S03 (predictor extracts JSON-LD/microdata/OG
        # brands correctly), which would saturate the inflate-by-0.5 trick.
        guard_dir = tmp_path / "guard"
        first = _run_harness(
            "--signal", "manufacturer",
            "--corpus", "gold",
            "--gold-set", str(low_score_gold_set),
            "--baseline-out", str(guard_dir),
        )
        assert first.returncode == 0, first.stderr
        # Pin the baseline at 1.0 so prior - current = 1.0 (>> 0.02).
        path = guard_dir / "manufacturer.json"
        data = json.loads(path.read_text())
        for metric in ("precision", "recall", "f1"):
            data[metric] = 1.0
        path.write_text(json.dumps(data, indent=2) + "\n")
        result = _run_harness(
            "--signal", "manufacturer",
            "--corpus", "gold",
            "--gold-set", str(low_score_gold_set),
            "--guard", str(guard_dir),
        )
        assert result.returncode == 1
        lines = _parse_stdout_lines(result.stdout)
        guard_lines = [l for l in lines if "guard_verdict" in l]
        assert guard_lines and guard_lines[-1]["guard_verdict"] == "fail"
        # At least one regression entry naming the manufacturer signal.
        regressions = guard_lines[-1]["regressions"]
        assert any(r["signal"] == "manufacturer" for r in regressions)


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------


class TestNegativePaths:
    def test_missing_gold_set_exits_2(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.json"
        result = _run_harness(
            "--signal", "manufacturer",
            "--corpus", "gold",
            "--gold-set", str(missing),
        )
        assert result.returncode == 2, (
            f"expected exit 2 for missing gold set, got {result.returncode}\n{result.stderr}"
        )
        # Structured error JSON on stderr.
        err_lines = [
            json.loads(line)
            for line in result.stderr.splitlines()
            if line.strip().startswith("{")
        ]
        assert any(l.get("error") == "gold_set_missing" for l in err_lines)

    def test_baseline_schema_drift_exits_3(
        self, tiny_gold_set: Path, tmp_path: Path
    ) -> None:
        guard_dir = tmp_path / "guard"
        guard_dir.mkdir()
        # Hand-write a schema-drift baseline (wrong harness_version).
        bad = {
            "harness_version": 999,  # current is 1
            "signal": "manufacturer",
            "sample_size": 3,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "precision": 0.9,
            "recall": 0.9,
            "f1": 0.9,
        }
        (guard_dir / "manufacturer.json").write_text(json.dumps(bad), encoding="utf-8")
        result = _run_harness(
            "--signal", "manufacturer",
            "--corpus", "gold",
            "--gold-set", str(tiny_gold_set),
            "--guard", str(guard_dir),
        )
        assert result.returncode == 3, (
            f"expected exit 3 for schema drift, got {result.returncode}\n{result.stderr}"
        )
        err_lines = [
            json.loads(line)
            for line in result.stderr.splitlines()
            if line.strip().startswith("{")
        ]
        assert any(l.get("error") == "baseline_schema_drift" for l in err_lines)


# ---------------------------------------------------------------------------
# S03 T04: _predict_manufacturer consumes html + product_url
# ---------------------------------------------------------------------------


class TestPredictManufacturerConsumesHtml:
    """Locks the post-S03 contract that `_predict_manufacturer` accepts html
    (and an optional product_url) and routes through `part_manufacturer_universal`.

    The fixture HTML carries a JSON-LD brand but the title/description carry
    no detectable manufacturer string — so the only path to a non-None result
    is through the HTML-aware ladder. A future regression that drops the html
    parameter or routes through the old title→description chain will fail
    this test loudly.
    """

    def test_html_only_row_resolves_via_jsonld_brand(self) -> None:
        # Make the harness importable in-process. _BACKEND_DIR is backend/.
        if str(_BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(_BACKEND_DIR))
        from scripts.m004_accuracy_harness import _predict_manufacturer

        html = (
            '<html><head>'
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Product",'
            '"name":"Generic Widget","brand":{"@type":"Brand","name":"AcmeBrand"}}'
            "</script></head><body></body></html>"
        )
        # Title + description carry no detectable manufacturer string —
        # neither part_manufacturer_from_title nor part_manufacturer_from_description
        # would match these on their own.
        predicted = _predict_manufacturer(
            "test-html-only-row",
            "generic part",
            "no brand mentioned in description",
            html,
            None,
        )
        assert predicted == "AcmeBrand", (
            f"expected JSON-LD brand 'AcmeBrand' from HTML, got {predicted!r} — "
            "either the html parameter is being ignored or part_manufacturer_universal "
            "is no longer being routed through."
        )

    def test_signature_accepts_html_and_product_url(self) -> None:
        """Defensive: confirm the post-S03 signature has html + product_url."""
        if str(_BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(_BACKEND_DIR))
        import inspect

        from scripts.m004_accuracy_harness import _predict_manufacturer

        params = inspect.signature(_predict_manufacturer).parameters
        assert "html" in params, (
            f"_predict_manufacturer missing 'html' parameter — got {list(params)}"
        )
        assert "product_url" in params, (
            f"_predict_manufacturer missing 'product_url' parameter — got {list(params)}"
        )
