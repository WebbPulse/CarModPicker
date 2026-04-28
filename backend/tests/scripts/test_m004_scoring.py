"""Unit tests for ``backend/scripts/m004_scoring.py``.

Pure-function tests with synthetic dict/tuple inputs. No DB, no I/O. Each
test exercises one of the contracts laid out in S01-PLAN.md / S01-RESEARCH.md
and the scoring module's docstrings:

* perfect match, total miss, partial overlap
* empty inputs (predicted=[]/[], should be 0/0/0 and never NaN)
* normalization edge cases (case + whitespace for manufacturer)
* absent-vs-wrong distinction for spec fields (S01-RESEARCH pitfall #8)
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
    aggregate_spec_field_level,
    aggregate_spec_part_level,
    score_car,
    score_category,
    score_manufacturer,
    score_spec_field_level,
    score_spec_part_level,
)


# Field lists used across the spec tests.
UNIVERSAL_FIELDS = [
    "weight_grams",
    "material",
    "finish",
    "warranty_days",
    "fitment_notes",
]

COILOVER_FIELDS = [
    "spring_rate_front",
    "spring_rate_rear",
    "damper_adjustability",
    "height_adjustable",
]


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
# score_spec_field_level — absent-vs-wrong distinction
# ---------------------------------------------------------------------------


class TestScoreSpecFieldLevel:
    def test_perfect_match(self) -> None:
        truth = {"weight_grams": 1500.0, "material": "steel"}
        s = score_spec_field_level(truth, truth, UNIVERSAL_FIELDS)
        assert s["n_universe"] == 2
        # tp=2, no fp, no fn
        assert s["per_field"]["weight_grams"]["tp"] == 1
        assert s["per_field"]["material"]["tp"] == 1
        # Other fields excluded — both None.
        for f in ("finish", "warranty_days", "fitment_notes"):
            assert s["per_field"][f] == {"tp": 0, "fp": 0, "fn": 0}

    def test_absent_in_both_excluded_from_universe(self) -> None:
        # S01-RESEARCH pitfall #8: a field None in BOTH should NOT be a TP.
        s = score_spec_field_level({}, {}, UNIVERSAL_FIELDS)
        assert s["n_universe"] == 0
        for f in UNIVERSAL_FIELDS:
            assert s["per_field"][f] == {"tp": 0, "fp": 0, "fn": 0}

    def test_predicted_hallucination_counts_as_fp(self) -> None:
        # Predictor returned "steel" but truth says no material.
        s = score_spec_field_level(
            {"material": "steel"}, {}, UNIVERSAL_FIELDS
        )
        assert s["n_universe"] == 0  # truth has no fields
        assert s["per_field"]["material"]["fp"] == 1
        assert s["per_field"]["material"]["tp"] == 0
        assert s["per_field"]["material"]["fn"] == 0

    def test_truth_present_predicted_none_counts_as_fn(self) -> None:
        s = score_spec_field_level(
            {}, {"material": "steel"}, UNIVERSAL_FIELDS
        )
        assert s["n_universe"] == 1
        assert s["per_field"]["material"]["fn"] == 1
        assert s["per_field"]["material"]["fp"] == 0
        assert s["per_field"]["material"]["tp"] == 0

    def test_wrong_value_counts_as_both_fp_and_fn(self) -> None:
        s = score_spec_field_level(
            {"material": "aluminum"},
            {"material": "steel"},
            UNIVERSAL_FIELDS,
        )
        assert s["n_universe"] == 1
        assert s["per_field"]["material"]["tp"] == 0
        assert s["per_field"]["material"]["fp"] == 1
        assert s["per_field"]["material"]["fn"] == 1

    def test_string_normalization_in_spec_value(self) -> None:
        s = score_spec_field_level(
            {"material": "  STEEL  "},
            {"material": "steel"},
            UNIVERSAL_FIELDS,
        )
        assert s["per_field"]["material"]["tp"] == 1
        assert s["per_field"]["material"]["fp"] == 0

    def test_float_tolerance(self) -> None:
        s = score_spec_field_level(
            {"weight_grams": 1500.0000001},
            {"weight_grams": 1500.0},
            UNIVERSAL_FIELDS,
        )
        assert s["per_field"]["weight_grams"]["tp"] == 1

    def test_bool_field(self) -> None:
        s = score_spec_field_level(
            {"height_adjustable": True},
            {"height_adjustable": True},
            COILOVER_FIELDS,
        )
        assert s["per_field"]["height_adjustable"]["tp"] == 1

        s2 = score_spec_field_level(
            {"height_adjustable": True},
            {"height_adjustable": False},
            COILOVER_FIELDS,
        )
        assert s2["per_field"]["height_adjustable"]["fp"] == 1
        assert s2["per_field"]["height_adjustable"]["fn"] == 1

    def test_malformed_input_none(self) -> None:
        with pytest.raises(TypeError):
            score_spec_field_level(None, {}, UNIVERSAL_FIELDS)  # type: ignore[arg-type]

    def test_malformed_input_not_mapping(self) -> None:
        with pytest.raises(TypeError):
            score_spec_field_level("not a dict", {}, UNIVERSAL_FIELDS)  # type: ignore[arg-type]

    def test_malformed_fields_not_sequence(self) -> None:
        with pytest.raises(TypeError):
            score_spec_field_level({}, {}, "weight_grams")  # type: ignore[arg-type]


class TestAggregateSpecFieldLevel:
    def test_aggregate_basic(self) -> None:
        # Two parts.
        # Part 1: weight=1500 truth=1500 (tp), material=None truth="steel" (fn)
        # Part 2: weight=2000 truth=1500 (fp+fn), material="steel" truth="steel" (tp)
        per_part = [
            score_spec_field_level(
                {"weight_grams": 1500.0},
                {"weight_grams": 1500.0, "material": "steel"},
                UNIVERSAL_FIELDS,
            ),
            score_spec_field_level(
                {"weight_grams": 2000.0, "material": "steel"},
                {"weight_grams": 1500.0, "material": "steel"},
                UNIVERSAL_FIELDS,
            ),
        ]
        env = aggregate_spec_field_level(per_part)
        # Field totals across parts:
        #   weight_grams: tp=1, fp=1, fn=1 → P=0.5, R=0.5, F1=0.5
        #   material:     tp=1, fp=0, fn=1 → P=1.0, R=0.5, F1≈0.667
        pf = env["per_field"]
        assert pf["weight_grams"]["precision"] == pytest.approx(0.5)
        assert pf["weight_grams"]["recall"] == pytest.approx(0.5)
        assert pf["material"]["precision"] == pytest.approx(1.0)
        assert pf["material"]["recall"] == pytest.approx(0.5)
        # Micro: tp=2, fp=1, fn=2 → P=2/3, R=1/2, F1=4/7
        assert env["micro_f1"] == pytest.approx(4 / 7)
        # Macro: avg(0.5, 0.667) over the two fields with truth.
        assert env["macro_f1"] == pytest.approx((0.5 + (2 * 1.0 * 0.5) / 1.5) / 2)
        assert env["sample_size"] == 2

    def test_aggregate_empty(self) -> None:
        env = aggregate_spec_field_level([])
        assert env["precision"] == 0.0
        assert env["recall"] == 0.0
        assert env["f1"] == 0.0
        assert env["micro_f1"] == 0.0
        assert env["macro_f1"] == 0.0
        assert env["sample_size"] == 0

    def test_aggregate_baseline_round_trip(self) -> None:
        per_part = [
            score_spec_field_level(
                {"weight_grams": 1500.0, "material": "steel"},
                {"weight_grams": 1500.0, "material": "steel"},
                UNIVERSAL_FIELDS,
            ),
        ]
        env = aggregate_spec_field_level(per_part)
        validate_baseline(env)


# ---------------------------------------------------------------------------
# score_spec_part_level — all fields correct
# ---------------------------------------------------------------------------


class TestScoreSpecPartLevel:
    def test_all_fields_correct(self) -> None:
        truth = {"weight_grams": 1500.0, "material": "steel"}
        s = score_spec_part_level(truth, truth, UNIVERSAL_FIELDS)
        assert s["all_fields_correct"] is True
        assert s["n_universe"] == 2

    def test_one_field_wrong(self) -> None:
        s = score_spec_part_level(
            {"weight_grams": 1500.0, "material": "aluminum"},
            {"weight_grams": 1500.0, "material": "steel"},
            UNIVERSAL_FIELDS,
        )
        assert s["all_fields_correct"] is False

    def test_predicted_extra_field_breaks_all_correct(self) -> None:
        # Predictor hallucinated a field truth doesn't have.
        s = score_spec_part_level(
            {"weight_grams": 1500.0, "material": "steel"},
            {"weight_grams": 1500.0},
            UNIVERSAL_FIELDS,
        )
        assert s["all_fields_correct"] is False
        # Truth universe is just weight_grams.
        assert s["n_universe"] == 1

    def test_empty_part_all_correct_when_predicted_also_empty(self) -> None:
        s = score_spec_part_level({}, {}, UNIVERSAL_FIELDS)
        assert s["all_fields_correct"] is True
        assert s["n_universe"] == 0

    def test_aggregate_baseline_round_trip(self) -> None:
        per_part = [
            score_spec_part_level(
                {"weight_grams": 1500.0},
                {"weight_grams": 1500.0},
                UNIVERSAL_FIELDS,
            ),
            score_spec_part_level(
                {"weight_grams": 2000.0},
                {"weight_grams": 1500.0},
                UNIVERSAL_FIELDS,
            ),
        ]
        env = aggregate_spec_part_level(per_part)
        # 1 of 2 all-correct.
        assert env["all_fields_correct_rate"] == pytest.approx(0.5)
        validate_baseline(env)

    def test_aggregate_empty(self) -> None:
        env = aggregate_spec_part_level([])
        assert env["all_fields_correct_rate"] == 0.0
        assert env["sample_size"] == 0


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

    def test_aggregate_spec_field_level(self) -> None:
        per_part = [
            score_spec_field_level(
                {"weight_grams": 1500.0},
                {"weight_grams": 1500.0},
                UNIVERSAL_FIELDS,
            )
        ]
        env = aggregate_spec_field_level(per_part)
        validate_baseline(env)

    def test_aggregate_spec_part_level(self) -> None:
        per_part = [
            score_spec_part_level(
                {"weight_grams": 1500.0},
                {"weight_grams": 1500.0},
                UNIVERSAL_FIELDS,
            )
        ]
        env = aggregate_spec_part_level(per_part)
        validate_baseline(env)

    def test_aggregator_emits_current_harness_version(self) -> None:
        env = aggregate_car([score_car([], [])])
        assert env["harness_version"] == HARNESS_VERSION
        # Hand-mutate to a stale version and confirm validate_baseline rejects.
        env["harness_version"] = HARNESS_VERSION + 1
        with pytest.raises(BaselineSchemaError, match="harness_version mismatch"):
            validate_baseline(env)
