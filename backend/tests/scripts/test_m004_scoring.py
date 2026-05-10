"""Unit tests for ``backend/scripts/m004_scoring.py``.

Pure-function tests with synthetic dict/tuple inputs. No DB, no I/O. Each
test exercises one of the contracts laid out in S01-PLAN.md / S01-RESEARCH.md
and the scoring module's docstrings:

* perfect match, total miss, partial overlap
* empty inputs (predicted=[]/[], should be 0/0/0 and never NaN)
* normalization edge cases (case + whitespace for manufacturer)
* the five baseline-schema shapes round-trip through ``validate_baseline``
* malformed inputs raise TypeError (no silent zero-score)
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from scripts.m004_baseline_schema import (
    HARNESS_VERSION,
    BaselineSchemaError,
    validate_baseline,
)
from scripts.m004_scoring import (
    aggregate_car,
    aggregate_category,
    aggregate_manufacturer,
    score_car,
    score_category,
    score_manufacturer,
)


# ---------------------------------------------------------------------------
# score_car — multiset triple matching
# ---------------------------------------------------------------------------


class TestScoreCar:
    def test_perfect_match(self) -> None:
        triples = [("Toyota", "Supra", "A90"), ("BMW", "M4", "G82/G83")]
        s = score_car(triples, triples)
        assert s["precision"] == 1.0
        assert s["recall"] == 1.0
        assert s["f1"] == 1.0
        assert s["n_correct"] == 2
        assert s["n_predicted"] == 2
        assert s["n_truth"] == 2

    def test_total_miss(self) -> None:
        s = score_car(
            [("Toyota", "Supra", "A90")],
            [("BMW", "M4", "G82/G83")],
        )
        assert s["precision"] == 0.0
        assert s["recall"] == 0.0
        assert s["f1"] == 0.0
        assert s["n_correct"] == 0

    def test_partial_overlap(self) -> None:
        # 1 of 2 predicted correct, 1 of 2 truth recovered.
        s = score_car(
            [("Toyota", "Supra", "A90"), ("Honda", "Civic", "EK")],
            [("Toyota", "Supra", "A90"), ("BMW", "M4", "G82/G83")],
        )
        assert s["precision"] == 0.5
        assert s["recall"] == 0.5
        assert s["f1"] == pytest.approx(0.5)
        assert s["n_correct"] == 1

    def test_empty_inputs_zero_not_nan(self) -> None:
        s = score_car([], [])
        assert s["precision"] == 0.0
        assert s["recall"] == 0.0
        assert s["f1"] == 0.0
        assert not math.isnan(s["f1"])
        assert s["n_correct"] == 0

    def test_empty_predicted_nonempty_truth(self) -> None:
        s = score_car([], [("Toyota", "Supra", "A90")])
        assert s["precision"] == 0.0
        assert s["recall"] == 0.0
        assert s["f1"] == 0.0

    def test_nonempty_predicted_empty_truth(self) -> None:
        s = score_car([("Toyota", "Supra", "A90")], [])
        assert s["precision"] == 0.0
        assert s["recall"] == 0.0
        assert s["f1"] == 0.0

    def test_case_insensitive_match(self) -> None:
        s = score_car(
            [("toyota", "supra", "A90")],
            [("Toyota", "Supra", "a90")],
        )
        assert s["precision"] == 1.0
        assert s["recall"] == 1.0

    def test_whitespace_collapsed(self) -> None:
        s = score_car(
            [("  Toyota  ", "Supra", "A90  ")],
            [("Toyota", "Supra", "A90")],
        )
        assert s["precision"] == 1.0

    def test_multiset_dedup_in_predicted(self) -> None:
        # Predicted emits the same triple twice; truth only has it once.
        # Multiset PR: TP=1, |pred|=2, |truth|=1 → precision=0.5, recall=1.0.
        s = score_car(
            [("Toyota", "Supra", "A90"), ("Toyota", "Supra", "A90")],
            [("Toyota", "Supra", "A90")],
        )
        assert s["precision"] == 0.5
        assert s["recall"] == 1.0
        assert s["n_correct"] == 1

    def test_malformed_input_wrong_arity(self) -> None:
        with pytest.raises(TypeError, match="exactly 3 elements"):
            score_car([("Toyota", "Supra")], [("Toyota", "Supra", "A90")])  # type: ignore[list-item]

    def test_malformed_input_not_tuple(self) -> None:
        with pytest.raises(TypeError, match="must be a tuple"):
            score_car([["Toyota", "Supra", "A90"]], [])  # type: ignore[list-item]

    def test_malformed_input_non_str(self) -> None:
        with pytest.raises(TypeError, match="must be str"):
            score_car([("Toyota", "Supra", 1990)], [])  # type: ignore[list-item]

    def test_malformed_input_none_sequence(self) -> None:
        with pytest.raises(TypeError):
            score_car(None, [])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# score_manufacturer — single-value binary
# ---------------------------------------------------------------------------


class TestScoreManufacturer:
    def test_exact_match(self) -> None:
        s = score_manufacturer("Cusco", "Cusco")
        assert s["correct"] is True
        assert s["has_truth"] is True

    def test_case_insensitive(self) -> None:
        s = score_manufacturer("AC SCHNITZER", "ac schnitzer")
        assert s["correct"] is True

    def test_whitespace_collapsed(self) -> None:
        s = score_manufacturer("  AC  Schnitzer  ", "AC Schnitzer")
        assert s["correct"] is True

    def test_disagreement(self) -> None:
        s = score_manufacturer("Cusco", "KW Suspension")
        assert s["correct"] is False
        assert s["has_truth"] is True
        assert s["predicted_present"] is True

    def test_truth_none_excluded_from_universe(self) -> None:
        s = score_manufacturer("Cusco", None)
        assert s["has_truth"] is False
        assert s["correct"] is False

    def test_predicted_none_with_truth(self) -> None:
        s = score_manufacturer(None, "Cusco")
        assert s["has_truth"] is True
        assert s["predicted_present"] is False
        assert s["correct"] is False

    def test_both_none(self) -> None:
        s = score_manufacturer(None, None)
        assert s["has_truth"] is False
        assert s["correct"] is False

    def test_empty_string_treated_as_none(self) -> None:
        # Empty / whitespace-only strings normalize to "" and are excluded.
        s = score_manufacturer("   ", "Cusco")
        assert s["predicted_present"] is False
        assert s["correct"] is False

    def test_malformed_input_int(self) -> None:
        with pytest.raises(TypeError):
            score_manufacturer(42, "Cusco")  # type: ignore[arg-type]


class TestAggregateManufacturer:
    def test_aggregate_pr_universe(self) -> None:
        # Universe = parts where truth is non-null.
        # Part A: truth=Cusco, pred=Cusco → correct
        # Part B: truth=KW, pred=Cusco → wrong
        # Part C: truth=KW, pred=None → miss
        # Part D: truth=None, pred=anything → not in universe
        per_part = [
            score_manufacturer("Cusco", "Cusco"),
            score_manufacturer("Cusco", "KW Suspension"),
            score_manufacturer(None, "KW Suspension"),
            score_manufacturer("Bilstein", None),
        ]
        env = aggregate_manufacturer(per_part)
        # Parts where truth non-null: 3 (A, B, C)
        # Parts with predicted+truth-non-null: 2 (A, B)
        # Correct: 1 (A)
        # precision = 1/2, recall = 1/3
        assert env["precision"] == pytest.approx(0.5)
        assert env["recall"] == pytest.approx(1 / 3)
        assert env["sample_size"] == 4
        assert env["signal"] == "manufacturer"
        assert env["harness_version"] == HARNESS_VERSION

    def test_aggregate_empty(self) -> None:
        env = aggregate_manufacturer([])
        assert env["precision"] == 0.0
        assert env["recall"] == 0.0
        assert env["f1"] == 0.0
        assert env["sample_size"] == 0
        assert not math.isnan(env["f1"])

    def test_aggregate_baseline_round_trip(self) -> None:
        env = aggregate_manufacturer(
            [score_manufacturer("Cusco", "Cusco")]
        )
        validate_baseline(env)


# ---------------------------------------------------------------------------
# score_category — same shape as manufacturer
# ---------------------------------------------------------------------------


class TestScoreCategory:
    def test_exact_match(self) -> None:
        s = score_category("suspension", "suspension")
        assert s["correct"] is True

    def test_disagreement(self) -> None:
        s = score_category("suspension", "brakes")
        assert s["correct"] is False

    def test_aggregate_round_trip(self) -> None:
        env = aggregate_category(
            [
                score_category("suspension", "suspension"),
                score_category("brakes", "brakes"),
                score_category("suspension", "engine"),
            ]
        )
        # 2 of 3 correct, all 3 in universe, all 3 predicted-present
        assert env["precision"] == pytest.approx(2 / 3)
        assert env["recall"] == pytest.approx(2 / 3)
        validate_baseline(env)


# ---------------------------------------------------------------------------
# Aggregator-baseline round-trips for ALL signals
# ---------------------------------------------------------------------------


class TestAggregateBaselineRoundTrip:
    """Each aggregator output must validate against the locked schema (T01)."""

    def test_aggregate_car(self) -> None:
        per_part = [score_car([("Toyota", "Supra", "A90")], [("Toyota", "Supra", "A90")])]
        env = aggregate_car(per_part)
        validate_baseline(env)

    def test_aggregate_manufacturer(self) -> None:
        per_part = [score_manufacturer("Cusco", "Cusco")]
        env = aggregate_manufacturer(per_part)
        validate_baseline(env)

    def test_aggregate_category(self) -> None:
        per_part = [score_category("suspension", "suspension")]
        env = aggregate_category(per_part)
        validate_baseline(env)


    def test_aggregator_emits_current_harness_version(self) -> None:
        env = aggregate_car([score_car([], [])])
        assert env["harness_version"] == HARNESS_VERSION
        # Hand-mutate to a stale version and confirm validate_baseline rejects.
        env["harness_version"] = HARNESS_VERSION + 1
        with pytest.raises(BaselineSchemaError, match="harness_version mismatch"):
            validate_baseline(env)
