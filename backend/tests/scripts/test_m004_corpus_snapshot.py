"""Unit + smoke tests for ``backend/scripts/m004_corpus_snapshot.py``.

Coverage (mirrors S04 T01 plan, Verification section):

* 6 unit tests on the pure counting helpers.
* 2 subprocess smoke tests covering the pre_s04 + post_s04 happy paths.
* 1 zero-corpus test that monkeypatches ``iterate_corpus_snapshot`` to raise
  ``OperationalError`` and asserts the MEM216 degraded branch.

The pure-helper tests do not require a DB session — they exercise
``part_has_car``, ``specs_any_field_non_null``, and
``specs_all_universal_fields_non_null`` against ``SimpleNamespace`` shims.

Subprocess tests follow the MEM209 cwd contract: every CLI invocation runs
from ``backend/`` so ``python -m scripts.m004_corpus_snapshot`` resolves the
package correctly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# backend/tests/scripts/test_m004_corpus_snapshot.py
#                ^^^^^^^^ parents[2] = backend/
# Per MEM222: parents[2] is canonical for backend/, parents[3] for repo root.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts import m004_corpus_snapshot as snap  # noqa: E402


# ---------------------------------------------------------------------------
# Pure counting-helper tests (no DB)
# ---------------------------------------------------------------------------


def _make_part(
    *,
    car_generations: list[Any] | None = None,
    part_manufacturer_id: Any = None,
    specifications: Any = None,
) -> Any:
    """Build a ``SimpleNamespace`` Part shim usable by the counting helpers."""
    return SimpleNamespace(
        id="part-id",
        car_generations=car_generations if car_generations is not None else [],
        part_manufacturer_id=part_manufacturer_id,
        specifications=specifications,
    )


class TestZeroCorpusYieldsAllZeros:
    def test_no_parts_means_all_signal_counts_zero(self) -> None:
        counts = snap.SignalCounts()
        # No part contributions registered.
        result = counts.to_dict()
        assert result == {
            "car_non_null": 0,
            "manufacturer_non_null": 0,
            "spec_any_field_non_null": 0,
            "spec_all_universal_fields_non_null": 0,
        }


class TestSpecsAnyFieldCountsMixedNulls:
    def test_any_field_true_when_at_least_one_value_non_null(self) -> None:
        # Mixed: weight is non-null, others are None -> any_field is True.
        specs = {"weight_grams": 12.5, "material": None, "finish": None}
        assert snap.specs_any_field_non_null(specs) is True

    def test_any_field_false_when_all_values_none(self) -> None:
        # JSON 'null' deserializes to Python None — must count as empty per MEM044.
        specs = {"weight_grams": None, "material": None}
        assert snap.specs_any_field_non_null(specs) is False

    def test_any_field_false_for_empty_dict(self) -> None:
        # JSON '{}' lands here as an empty Python dict — must count as empty.
        assert snap.specs_any_field_non_null({}) is False


class TestSpecsAllUniversalFieldsRequiresEveryKey:
    def test_all_present_and_non_null_returns_true(self) -> None:
        specs = {
            "weight_grams": 100,
            "material": "steel",
            "finish": "anodized",
            "warranty_days": 365,
            "fitment_notes": "fits all",
            "manufacturer_part_number": "ABC-123",
            # Extra keys are fine — they don't disqualify.
            "extra_field": "ignored",
        }
        assert snap.specs_all_universal_fields_non_null(specs) is True

    def test_missing_one_key_fails(self) -> None:
        specs = {
            "weight_grams": 100,
            "material": "steel",
            "finish": "anodized",
            "warranty_days": 365,
            # fitment_notes is absent.
        }
        assert snap.specs_all_universal_fields_non_null(specs) is False

    def test_one_key_present_but_null_fails(self) -> None:
        # Per the plan: "missing key OR null key fails".
        specs = {
            "weight_grams": 100,
            "material": "steel",
            "finish": "anodized",
            "warranty_days": 365,
            "fitment_notes": None,  # JSON null literal — counts as missing.
        }
        assert snap.specs_all_universal_fields_non_null(specs) is False


class TestPartHasCar:
    def test_empty_car_generations_returns_false(self) -> None:
        # Per the plan: a part with empty car_generations list does NOT count
        # toward car_non_null.
        part = _make_part(car_generations=[])
        assert snap.part_has_car(part) is False

    def test_one_car_generation_returns_true(self) -> None:
        part = _make_part(car_generations=[SimpleNamespace(id="cg-1")])
        assert snap.part_has_car(part) is True


class TestJsonNullLiteralTreatedAsEmptyMem044:
    def test_python_none_specs_is_empty(self) -> None:
        # SQL NULL or JSON 'null' deserialize to Python None at the SQLA layer.
        assert snap.specs_any_field_non_null(None) is False
        assert snap.specs_all_universal_fields_non_null(None) is False

    def test_dict_with_only_none_values_is_empty_for_any_field(self) -> None:
        # Even with all five universal field keys, all-None values still fails
        # both signals — JSON null literal is empty per MEM044.
        specs = {name: None for name in snap.UNIVERSAL_FIELD_NAMES}
        assert snap.specs_any_field_non_null(specs) is False
        assert snap.specs_all_universal_fields_non_null(specs) is False


class TestCountSignalsForPartAggregates:
    """Sanity-check the per-part aggregator that the iterator calls."""

    def test_full_signal_part_increments_all_four_counts(self) -> None:
        counts = snap.SignalCounts()
        part = _make_part(
            car_generations=[SimpleNamespace(id="cg-1")],
            part_manufacturer_id="manu-1",
            specifications={
                "weight_grams": 100,
                "material": "steel",
                "finish": "anodized",
                "warranty_days": 365,
                "fitment_notes": "fits",
                "manufacturer_part_number": "ABC-123",
            },
        )
        snap.count_signals_for_part(part, counts)
        assert counts.to_dict() == {
            "car_non_null": 1,
            "manufacturer_non_null": 1,
            "spec_any_field_non_null": 1,
            "spec_all_universal_fields_non_null": 1,
        }


# ---------------------------------------------------------------------------
# DoD verdict tests (small bonus — guard the post-phase exit code path)
# ---------------------------------------------------------------------------


class TestEvaluateDodVerdict:
    def test_pass_when_car_up_others_within_tolerance(self) -> None:
        verdict, regressions = snap.evaluate_dod_verdict(
            delta_pct={"car": 5.0, "manufacturer": -0.5, "spec_any_field": 0.0, "spec_all_universal_fields": -0.9},
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 50, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 105, "manufacturer_non_null": 50, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
        )
        assert verdict == "pass"
        assert regressions == []

    def test_fail_when_manufacturer_drops_more_than_one_pct(self) -> None:
        verdict, regressions = snap.evaluate_dod_verdict(
            delta_pct={"car": 1.0, "manufacturer": -2.5, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 101, "manufacturer_non_null": 97, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
        )
        assert verdict == "fail"
        assert "manufacturer" in regressions

    def test_zero_corpus_pass_when_both_sides_all_zero(self) -> None:
        zero = {k: 0 for k in ("car_non_null", "manufacturer_non_null", "spec_any_field_non_null", "spec_all_universal_fields_non_null")}
        verdict, regressions = snap.evaluate_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            zero_corpus=True,
            pre_counts=zero,
            post_counts=zero,
        )
        assert verdict == "zero_corpus_pass"
        assert regressions == []


# ---------------------------------------------------------------------------
# Subprocess smoke tests (MEM209 cwd contract — must run from backend/)
# ---------------------------------------------------------------------------


def test_subprocess_pre_s04_writes_valid_envelope_and_exits_zero(tmp_path: Path) -> None:
    out = tmp_path / "snapshot.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s04",
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
        f"pre_s04 exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert out.exists(), f"expected snapshot at {out}; stderr={result.stderr}"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "pre_s04" in payload, payload
    assert payload["post_s04"] is None, payload
    assert payload["delta_pct"] is None, payload
    assert "zero_corpus" in payload, payload
    assert "snapshot_taken_at" in payload, payload
    # stdout JSON envelope was emitted.
    stdout_lines = [ln for ln in result.stdout.strip().splitlines() if ln.startswith("{")]
    assert stdout_lines, f"expected at least one JSON line on stdout, got: {result.stdout!r}"
    parsed = json.loads(stdout_lines[-1])
    assert parsed["phase"] == "pre_s04"


def test_subprocess_post_s04_after_pre_s04_emits_dod_verdict(tmp_path: Path) -> None:
    out = tmp_path / "snapshot.json"
    pre = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s04",
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
    assert pre.returncode == 0, pre.stderr
    post = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "post_s04",
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
    assert post.returncode == 0, (
        f"post_s04 exited {post.returncode}\nstdout={post.stdout}\nstderr={post.stderr}"
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["pre_s04"] is not None, payload
    assert payload["post_s04"] is not None, payload
    assert payload["delta_pct"] is not None, payload
    # Final stdout line should carry dod_verdict.
    stdout_lines = [ln for ln in post.stdout.strip().splitlines() if ln.startswith("{")]
    assert len(stdout_lines) >= 2, f"expected >=2 JSON lines, got: {post.stdout!r}"
    final = json.loads(stdout_lines[-1])
    assert "dod_verdict" in final, final
    # On a fresh test environment with no live corpus, expect zero_corpus_pass
    # OR pass — never fail (no signal can drop below pre when both are zero).
    assert final["dod_verdict"] in ("pass", "zero_corpus_pass"), final


# ---------------------------------------------------------------------------
# Zero-corpus / OperationalError monkeypatch test
# ---------------------------------------------------------------------------


def test_iterate_corpus_snapshot_degrades_to_zero_corpus_on_operational_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per MEM216 — missing crawled_pages table should NOT abort the run."""
    from sqlalchemy.exc import OperationalError

    class _ExplodingQuery:
        def options(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def yield_per(self, _n):
            # Emulate the missing-table path: SQLAlchemy raises when the
            # iterator is constructed, exactly the MEM216 SQLite-fallback
            # signature.
            raise OperationalError("SELECT", {}, Exception("no such table: crawled_pages"))

    class _StubDB:
        def query(self, _model):
            return _ExplodingQuery()

    counts, per_field_counts, total, zero_corpus = snap.iterate_corpus_snapshot(
        _StubDB(), limit=None
    )
    assert total == 0
    assert zero_corpus is True
    assert counts.to_dict() == {
        "car_non_null": 0,
        "manufacturer_non_null": 0,
        "spec_any_field_non_null": 0,
        "spec_all_universal_fields_non_null": 0,
    }
    # MEM216 degrade also zeroes the per-field block.
    assert per_field_counts == {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}


# ---------------------------------------------------------------------------
# S05 — per-universal-field counter helper tests (5 unit tests)
# ---------------------------------------------------------------------------


class TestCountPerFieldForPart:
    def test_empty_dict_yields_all_zeros(self) -> None:
        per_field = {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}
        part = _make_part(specifications={})
        snap.count_per_field_for_part(part, per_field)
        assert per_field == {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}

    def test_only_weight_grams_increments_only_that_key(self) -> None:
        per_field = {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}
        part = _make_part(specifications={"weight_grams": 12.5})
        snap.count_per_field_for_part(part, per_field)
        assert per_field["weight_grams"] == 1
        for other in (
            "material",
            "finish",
            "warranty_days",
            "fitment_notes",
            "manufacturer_part_number",
        ):
            assert per_field[other] == 0

    def test_all_universal_present_and_non_null_increments_all(self) -> None:
        per_field = {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}
        part = _make_part(
            specifications={
                "weight_grams": 100,
                "material": "steel",
                "finish": "anodized",
                "warranty_days": 365,
                "fitment_notes": "fits",
                "manufacturer_part_number": "ABC-123",
            }
        )
        snap.count_per_field_for_part(part, per_field)
        assert per_field == {name: 1 for name in snap.UNIVERSAL_FIELD_NAMES}

    def test_key_present_but_value_none_does_not_increment(self) -> None:
        # MEM044: JSON 'null' deserializes to Python None — counts as missing.
        per_field = {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}
        part = _make_part(
            specifications={
                "weight_grams": None,
                "material": None,
                "finish": None,
                "warranty_days": None,
                "fitment_notes": None,
                "manufacturer_part_number": None,
            }
        )
        snap.count_per_field_for_part(part, per_field)
        assert per_field == {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}

    def test_missing_key_does_not_increment(self) -> None:
        # Only material is set; the other keys are entirely absent.
        per_field = {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}
        part = _make_part(specifications={"material": "steel"})
        snap.count_per_field_for_part(part, per_field)
        assert per_field["material"] == 1
        for other in (
            "weight_grams",
            "finish",
            "warranty_days",
            "fitment_notes",
            "manufacturer_part_number",
        ):
            assert per_field[other] == 0

    def test_only_manufacturer_part_number_increments_only_that_key(self) -> None:
        # M004/S06 T03: the new universal field threads through
        # ``count_per_field_for_part`` because the helper iterates the live
        # ``UNIVERSAL_FIELD_NAMES`` tuple.
        per_field = {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}
        part = _make_part(specifications={"manufacturer_part_number": "ABC-123"})
        snap.count_per_field_for_part(part, per_field)
        assert per_field["manufacturer_part_number"] == 1
        for other in ("weight_grams", "material", "finish", "warranty_days", "fitment_notes"):
            assert per_field[other] == 0


# ---------------------------------------------------------------------------
# S05 DoD verdict
# ---------------------------------------------------------------------------


class TestEvaluateS05DodVerdict:
    """Cover the four branches of the S05 DoD verdict in one test class."""

    @staticmethod
    def _zero_aggregates() -> dict[str, int]:
        return {
            "car_non_null": 0,
            "manufacturer_non_null": 0,
            "spec_any_field_non_null": 0,
            "spec_all_universal_fields_non_null": 0,
        }

    @staticmethod
    def _zero_per_field() -> dict[str, int]:
        return {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}

    def test_zero_corpus_pass_when_all_zero_on_both_sides(self) -> None:
        verdict, regressions = snap.evaluate_s05_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            per_field_delta_pct={name: 0.0 for name in snap.UNIVERSAL_FIELD_NAMES},
            zero_corpus=True,
            pre_counts=self._zero_aggregates(),
            post_counts=self._zero_aggregates(),
            pre_per_field=self._zero_per_field(),
            post_per_field=self._zero_per_field(),
        )
        assert verdict == "zero_corpus_pass"
        assert regressions == []

    def test_pass_with_positive_material_delta_and_manufacturer_drop_within_tolerance(self) -> None:
        # material per-field delta strictly positive; manufacturer drop is
        # -0.5 (within the 1% tolerance); no other field regresses.
        per_field_delta = {
            "weight_grams": 0.0,
            "material": 4.0,
            "finish": 0.0,
            "warranty_days": 0.0,
            "fitment_notes": 0.0,
        }
        verdict, regressions = snap.evaluate_s05_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": -0.5, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            per_field_delta_pct=per_field_delta,
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 100, "manufacturer_non_null": 99, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            pre_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
            post_per_field={"weight_grams": 50, "material": 26, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
        )
        assert verdict == "pass", regressions
        assert regressions == []

    def test_fail_when_aggregate_signal_drops_more_than_one_pct(self) -> None:
        per_field_delta = {
            "weight_grams": 1.0,
            "material": 0.0,
            "finish": 0.0,
            "warranty_days": 0.0,
            "fitment_notes": 0.0,
        }
        verdict, regressions = snap.evaluate_s05_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": -1.5, "spec_all_universal_fields": 0.0},
            per_field_delta_pct=per_field_delta,
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 100, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 98, "spec_all_universal_fields_non_null": 10},
            pre_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
            post_per_field={"weight_grams": 51, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
        )
        assert verdict == "fail"
        assert "spec_any_field" in regressions

    def test_fail_when_no_per_field_increase_in_non_zero_corpus(self) -> None:
        # All aggregate deltas within tolerance but no per-field strictly
        # positive — must fail with the no_per_field_increase sentinel.
        per_field_delta = {name: 0.0 for name in snap.UNIVERSAL_FIELD_NAMES}
        verdict, regressions = snap.evaluate_s05_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            per_field_delta_pct=per_field_delta,
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            pre_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
            post_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
        )
        assert verdict == "fail"
        assert "no_per_field_increase" in regressions


# ---------------------------------------------------------------------------
# S05 subprocess smoke tests (MEM209 cwd contract — must run from backend/)
# ---------------------------------------------------------------------------


def test_subprocess_pre_s05_writes_valid_envelope_with_per_field_block(tmp_path: Path) -> None:
    out = tmp_path / "s05_snapshot.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s05",
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
        f"pre_s05 exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert out.exists(), f"expected snapshot at {out}; stderr={result.stderr}"
    payload = json.loads(out.read_text(encoding="utf-8"))
    # Envelope shape per slice plan.
    assert "pre_s05" in payload, payload
    assert payload["post_s05"] is None, payload
    assert "per_universal_field_pre_s05" in payload, payload
    assert payload["per_universal_field_post_s05"] is None, payload
    assert payload["delta_pct"] is None, payload
    assert payload["per_field_delta_pct"] is None, payload
    assert "zero_corpus" in payload, payload
    # Per-field block keys mirror the live UNIVERSAL_FIELD_NAMES tuple
    # (extended in M004/S06 T03 with manufacturer_part_number).
    assert set(payload["per_universal_field_pre_s05"].keys()) == set(
        snap.UNIVERSAL_FIELD_NAMES
    ), payload
    # stdout JSON envelope was emitted.
    stdout_lines = [ln for ln in result.stdout.strip().splitlines() if ln.startswith("{")]
    assert stdout_lines, f"expected at least one JSON line on stdout, got: {result.stdout!r}"
    parsed = json.loads(stdout_lines[-1])
    assert parsed["phase"] == "pre_s05"
    assert "per_universal_field_pre_s05" in parsed


def test_subprocess_post_s05_after_pre_s05_emits_dod_verdict_with_per_field_deltas(tmp_path: Path) -> None:
    out = tmp_path / "s05_snapshot.json"
    pre = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s05",
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
    assert pre.returncode == 0, pre.stderr
    post = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "post_s05",
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
    assert post.returncode == 0, (
        f"post_s05 exited {post.returncode}\nstdout={post.stdout}\nstderr={post.stderr}"
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["pre_s05"] is not None, payload
    assert payload["post_s05"] is not None, payload
    assert payload["per_universal_field_pre_s05"] is not None, payload
    assert payload["per_universal_field_post_s05"] is not None, payload
    assert payload["delta_pct"] is not None, payload
    assert payload["per_field_delta_pct"] is not None, payload
    # Final stdout line should carry dod_verdict + per_field_deltas.
    stdout_lines = [ln for ln in post.stdout.strip().splitlines() if ln.startswith("{")]
    assert len(stdout_lines) >= 2, f"expected >=2 JSON lines, got: {post.stdout!r}"
    final = json.loads(stdout_lines[-1])
    assert "dod_verdict" in final, final
    assert "per_field_deltas" in final, final
    assert set(final["per_field_deltas"].keys()) == set(snap.UNIVERSAL_FIELD_NAMES), final
    # On a fresh test environment with no live corpus, expect zero_corpus_pass —
    # never fail (no signal can drop below pre when both are zero).
    assert final["dod_verdict"] in ("pass", "zero_corpus_pass"), final


# ---------------------------------------------------------------------------
# S05 zero-corpus monkeypatch (mirrors the S04 zero-corpus test for the new path)
# ---------------------------------------------------------------------------


def test_iterate_corpus_snapshot_s05_zero_corpus_emits_zero_per_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The MEM216 degrade path must zero the per-field block too — the S05
    envelope's ``per_universal_field_*`` keys depend on this.
    """
    from sqlalchemy.exc import OperationalError

    class _ExplodingQuery:
        def options(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def yield_per(self, _n):
            raise OperationalError("SELECT", {}, Exception("no such table: crawled_pages"))

    class _StubDB:
        def query(self, _model):
            return _ExplodingQuery()

    counts, per_field_counts, total, zero_corpus = snap.iterate_corpus_snapshot(
        _StubDB(), limit=None
    )
    assert total == 0
    assert zero_corpus is True
    # Per-field block all zero (slice-plan defensive contract).
    assert per_field_counts == {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}


# ---------------------------------------------------------------------------
# S04 regression — pre_s04 still byte-stable in shape after S05 extension.
# ---------------------------------------------------------------------------


def test_subprocess_pre_s04_envelope_shape_unchanged_after_s05_extension(
    tmp_path: Path,
) -> None:
    """Belt-and-braces regression: the S04 envelope must NOT have grown any
    of the new S05 keys (per_universal_field_*, per_field_delta_pct).
    The slice plan locks the S04 file to byte-identical behavior; this
    test pins the on-disk schema as a last-mile guard.
    """
    out = tmp_path / "s04_snapshot.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s04",
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
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    # S04 keys present.
    assert set(payload.keys()) == {
        "snapshot_taken_at",
        "corpus_total",
        "pre_s04",
        "post_s04",
        "delta_pct",
        "zero_corpus",
    }, payload
    # S05 keys must NOT have leaked into the S04 envelope.
    assert "per_universal_field_pre_s05" not in payload
    assert "per_universal_field_post_s05" not in payload
    assert "per_field_delta_pct" not in payload


# ---------------------------------------------------------------------------
# S06 — envelope builder unit tests
# ---------------------------------------------------------------------------


class TestBuildPreS06Envelope:
    def test_pre_s06_envelope_shape_and_null_post_keys(self) -> None:
        counts = snap.SignalCounts(
            car_non_null=3,
            manufacturer_non_null=2,
            spec_any_field_non_null=1,
            spec_all_universal_fields_non_null=0,
        )
        per_field = {name: 1 for name in snap.UNIVERSAL_FIELD_NAMES}
        envelope = snap.build_pre_s06_envelope(
            counts=counts,
            per_field_counts=per_field,
            corpus_total=10,
            zero_corpus=False,
            snapshot_taken_at="2026-04-30T19:00:00+00:00",
        )
        # S06-keyed names; post side null until --phase post_s06 lands.
        assert envelope["pre_s06"] == counts.to_dict()
        assert envelope["post_s06"] is None
        assert envelope["per_universal_field_pre_s06"] == per_field
        assert envelope["per_universal_field_post_s06"] is None
        assert envelope["delta_pct"] is None
        assert envelope["per_field_delta_pct"] is None
        assert envelope["zero_corpus"] is False
        assert envelope["corpus_total"] == 10
        assert envelope["snapshot_taken_at"] == "2026-04-30T19:00:00+00:00"
        # The per-field block must be a copy — mutating the source must not
        # mutate the envelope.
        per_field["weight_grams"] = 999
        assert envelope["per_universal_field_pre_s06"]["weight_grams"] == 1


class TestBuildPostS06Envelope:
    def test_post_s06_reads_pre_s06_and_computes_deltas(self) -> None:
        existing = {
            "pre_s06": {
                "car_non_null": 100,
                "manufacturer_non_null": 100,
                "spec_any_field_non_null": 30,
                "spec_all_universal_fields_non_null": 10,
            },
            "per_universal_field_pre_s06": {
                "weight_grams": 50,
                "material": 25,
                "finish": 15,
                "warranty_days": 10,
                "fitment_notes": 5,
            },
        }
        counts = snap.SignalCounts(
            car_non_null=100,
            manufacturer_non_null=100,
            spec_any_field_non_null=31,
            spec_all_universal_fields_non_null=10,
        )
        per_field = {
            "weight_grams": 50,
            "material": 26,
            "finish": 15,
            "warranty_days": 10,
            "fitment_notes": 5,
        }
        envelope = snap.build_post_s06_envelope(
            existing=existing,
            counts=counts,
            per_field_counts=per_field,
            corpus_total=200,
            zero_corpus=False,
            snapshot_taken_at="2026-04-30T20:00:00+00:00",
        )
        assert envelope["pre_s06"] == existing["pre_s06"]
        assert envelope["post_s06"] == counts.to_dict()
        assert envelope["per_universal_field_pre_s06"] == existing["per_universal_field_pre_s06"]
        assert envelope["per_universal_field_post_s06"] == per_field
        # Delta math: spec_any_field went 30 -> 31 = +3.3333...% rounded to 4dp.
        assert envelope["delta_pct"]["spec_any_field"] == pytest.approx(3.3333, abs=1e-4)
        # material per-field went 25 -> 26 = +4%.
        assert envelope["per_field_delta_pct"]["material"] == pytest.approx(4.0, abs=1e-4)
        assert envelope["zero_corpus"] is False

    def test_post_s06_falls_back_to_zero_blocks_when_existing_missing_keys(self) -> None:
        # Defensive: if the pre-phase JSON was older / partial, builders must
        # fall back to zero blocks rather than crash.
        existing = {}  # no pre_s06 / per_universal_field_pre_s06
        counts = snap.SignalCounts()
        per_field = {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}
        envelope = snap.build_post_s06_envelope(
            existing=existing,
            counts=counts,
            per_field_counts=per_field,
            corpus_total=0,
            zero_corpus=True,
            snapshot_taken_at="2026-04-30T21:00:00+00:00",
        )
        assert envelope["pre_s06"] == counts.to_dict()
        assert envelope["per_universal_field_pre_s06"] == per_field


# ---------------------------------------------------------------------------
# S06 DoD verdict
# ---------------------------------------------------------------------------


class TestEvaluateS06DodVerdict:
    """S06 verdict logic mirrors S05 (per slice plan); cover happy /
    fail / zero-corpus branches."""

    @staticmethod
    def _zero_aggregates() -> dict[str, int]:
        return {
            "car_non_null": 0,
            "manufacturer_non_null": 0,
            "spec_any_field_non_null": 0,
            "spec_all_universal_fields_non_null": 0,
        }

    @staticmethod
    def _zero_per_field() -> dict[str, int]:
        return {name: 0 for name in snap.UNIVERSAL_FIELD_NAMES}

    def test_zero_corpus_pass_when_all_zero_on_both_sides(self) -> None:
        verdict, regressions = snap.evaluate_s06_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            per_field_delta_pct={name: 0.0 for name in snap.UNIVERSAL_FIELD_NAMES},
            zero_corpus=True,
            pre_counts=self._zero_aggregates(),
            post_counts=self._zero_aggregates(),
            pre_per_field=self._zero_per_field(),
            post_per_field=self._zero_per_field(),
        )
        assert verdict == "zero_corpus_pass"
        assert regressions == []

    def test_pass_with_one_positive_per_field_delta(self) -> None:
        per_field_delta = {
            "weight_grams": 0.0,
            "material": 0.0,
            "finish": 2.0,  # one strictly positive entry satisfies the gate
            "warranty_days": 0.0,
            "fitment_notes": 0.0,
        }
        verdict, regressions = snap.evaluate_s06_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            per_field_delta_pct=per_field_delta,
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            pre_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
            post_per_field={"weight_grams": 50, "material": 25, "finish": 16, "warranty_days": 10, "fitment_notes": 5},
        )
        assert verdict == "pass", regressions
        assert regressions == []

    def test_fail_when_no_per_field_increase_in_non_zero_corpus(self) -> None:
        per_field_delta = {name: 0.0 for name in snap.UNIVERSAL_FIELD_NAMES}
        verdict, regressions = snap.evaluate_s06_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            per_field_delta_pct=per_field_delta,
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            pre_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
            post_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
        )
        assert verdict == "fail"
        assert "no_per_field_increase" in regressions

    def test_fail_when_per_field_drops_more_than_one_pct(self) -> None:
        per_field_delta = {
            "weight_grams": 0.0,
            "material": -2.0,  # > 1% drop
            "finish": 0.0,
            "warranty_days": 0.0,
            "fitment_notes": 0.0,
        }
        verdict, regressions = snap.evaluate_s06_dod_verdict(
            delta_pct={"car": 0.0, "manufacturer": 0.0, "spec_any_field": 0.0, "spec_all_universal_fields": 0.0},
            per_field_delta_pct=per_field_delta,
            zero_corpus=False,
            pre_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            post_counts={"car_non_null": 100, "manufacturer_non_null": 100, "spec_any_field_non_null": 30, "spec_all_universal_fields_non_null": 10},
            pre_per_field={"weight_grams": 50, "material": 25, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
            post_per_field={"weight_grams": 50, "material": 24, "finish": 15, "warranty_days": 10, "fitment_notes": 5},
        )
        assert verdict == "fail"
        assert "material" in regressions


# ---------------------------------------------------------------------------
# S06 subprocess smoke tests (MEM209 cwd contract — must run from backend/)
# ---------------------------------------------------------------------------


def test_subprocess_pre_s06_writes_valid_envelope_with_per_field_block(tmp_path: Path) -> None:
    out = tmp_path / "s06_snapshot.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s06",
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
        f"pre_s06 exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert out.exists(), f"expected snapshot at {out}; stderr={result.stderr}"
    payload = json.loads(out.read_text(encoding="utf-8"))
    # Envelope shape per slice plan.
    assert "pre_s06" in payload, payload
    assert payload["post_s06"] is None, payload
    assert "per_universal_field_pre_s06" in payload, payload
    assert payload["per_universal_field_post_s06"] is None, payload
    assert payload["delta_pct"] is None, payload
    assert payload["per_field_delta_pct"] is None, payload
    assert "zero_corpus" in payload, payload
    # Per-field block keys mirror the live UNIVERSAL_FIELD_NAMES tuple
    # (extended in M004/S06 T03 with ``manufacturer_part_number``).
    assert set(payload["per_universal_field_pre_s06"].keys()) == set(
        snap.UNIVERSAL_FIELD_NAMES
    ), payload
    # stdout JSON envelope was emitted.
    stdout_lines = [ln for ln in result.stdout.strip().splitlines() if ln.startswith("{")]
    assert stdout_lines, f"expected at least one JSON line on stdout, got: {result.stdout!r}"
    parsed = json.loads(stdout_lines[-1])
    assert parsed["phase"] == "pre_s06"
    assert "per_universal_field_pre_s06" in parsed


def test_subprocess_post_s06_after_pre_s06_emits_dod_verdict_with_per_field_deltas(tmp_path: Path) -> None:
    out = tmp_path / "s06_snapshot.json"
    pre = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s06",
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
    assert pre.returncode == 0, pre.stderr
    post = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "post_s06",
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
    assert post.returncode == 0, (
        f"post_s06 exited {post.returncode}\nstdout={post.stdout}\nstderr={post.stderr}"
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["pre_s06"] is not None, payload
    assert payload["post_s06"] is not None, payload
    assert payload["per_universal_field_pre_s06"] is not None, payload
    assert payload["per_universal_field_post_s06"] is not None, payload
    assert payload["delta_pct"] is not None, payload
    assert payload["per_field_delta_pct"] is not None, payload
    # Final stdout line should carry dod_verdict + per_field_deltas.
    stdout_lines = [ln for ln in post.stdout.strip().splitlines() if ln.startswith("{")]
    assert len(stdout_lines) >= 2, f"expected >=2 JSON lines, got: {post.stdout!r}"
    final = json.loads(stdout_lines[-1])
    assert "dod_verdict" in final, final
    assert "per_field_deltas" in final, final
    assert set(final["per_field_deltas"].keys()) == set(snap.UNIVERSAL_FIELD_NAMES), final
    # On a fresh test environment with no live corpus, expect zero_corpus_pass —
    # never fail (no signal can drop below pre when both are zero).
    assert final["dod_verdict"] in ("pass", "zero_corpus_pass"), final


def test_subprocess_post_s06_without_pre_s06_exits_one_with_operator_message(
    tmp_path: Path,
) -> None:
    """Q5 Failure Modes: missing pre-phase JSON on --phase post_s06 must
    surface an operator-facing 'snapshot file missing — run --phase pre_s06
    first' line on stderr and exit 1 (mirrors S05 error path)."""
    out = tmp_path / "missing_s06_snapshot.json"
    assert not out.exists()
    post = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "post_s06",
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
    assert post.returncode == 1, (
        f"expected exit 1 on missing pre_s06 file; got {post.returncode}\n"
        f"stdout={post.stdout}\nstderr={post.stderr}"
    )
    # Stderr carries the structured snapshot_pre_phase_unreadable line.
    assert "snapshot_pre_phase_unreadable" in post.stderr, post.stderr
    # The operator-facing detail mentions running the pre phase first.
    assert "pre_s06" in post.stderr, post.stderr


# ---------------------------------------------------------------------------
# S05 byte-stability regression — pre_s05 envelope shape must NOT change
# after S06 extension (mirrors the S04 byte-stability test the S05 work
# introduced).
# ---------------------------------------------------------------------------


def test_subprocess_pre_s05_envelope_shape_unchanged_after_s06_extension(
    tmp_path: Path,
) -> None:
    """Belt-and-braces regression: the S05 envelope must NOT have grown any
    of the new S06 keys (per_universal_field_pre_s06, per_universal_field_post_s06).
    The slice plan locks the S05 file shape to byte-stable behavior; this
    test pins the on-disk schema as a last-mile guard.
    """
    out = tmp_path / "s05_snapshot.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_corpus_snapshot",
            "--phase",
            "pre_s05",
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
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    # S05 keys present (exact set — no S06 leakage).
    assert set(payload.keys()) == {
        "snapshot_taken_at",
        "corpus_total",
        "pre_s05",
        "post_s05",
        "per_universal_field_pre_s05",
        "per_universal_field_post_s05",
        "delta_pct",
        "per_field_delta_pct",
        "zero_corpus",
    }, payload
    # S06 keys must NOT have leaked into the S05 envelope.
    assert "pre_s06" not in payload
    assert "post_s06" not in payload
    assert "per_universal_field_pre_s06" not in payload
    assert "per_universal_field_post_s06" not in payload
