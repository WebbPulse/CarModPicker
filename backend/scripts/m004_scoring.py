"""M004 accuracy-harness pure scoring functions.

One scorer per signal — pure (no DB, no I/O, no shared resources). Inputs are
synthetic dicts/tuples; outputs match the locked baseline schema in
``m004_baseline_schema.py`` (T01) so aggregator envelopes round-trip through
``validate_baseline``.

Normalization rules (per S01-RESEARCH.md):

* Manufacturer / category comparison: ``s.lower().strip()`` with collapsed
  internal whitespace. ``"AC Schnitzer"`` and ``" ac  schnitzer "`` are equal.
* Car triples: lowercased ``(make, model, generation_name)`` strings; multiset
  semantics for precision/recall (duplicate triples count, in case the predictor
  emits the same triple twice).
* Spec field-level: the universe is ``{fields where truth is non-null}``. A
  field that is ``None`` in BOTH predicted and truth is *excluded* from
  precision/recall — counting it as a true positive would inflate accuracy
  on sparse parts (S01-RESEARCH pitfall #8). A field where predicted is
  non-null but truth is ``None`` counts as a false positive (the predictor
  hallucinated). A field where truth is non-null but predicted differs is a
  miss (false negative).

All public functions raise ``TypeError`` early on malformed inputs (None where
a dict is expected, wrong tuple arity for car triples) — never a silent
zero-score.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

from scripts.m004_baseline_schema import HARNESS_VERSION

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_string(value: Optional[str]) -> Optional[str]:
    """Lowercase + strip + collapse internal whitespace. None passes through."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(
            f"expected str or None for normalization, got {type(value).__name__}={value!r}"
        )
    collapsed = _WHITESPACE_RE.sub(" ", value).strip().lower()
    return collapsed


def _safe_div(num: float, denom: float) -> float:
    """Return num/denom or 0.0 when denom is 0 (never NaN)."""
    if denom == 0:
        return 0.0
    return num / denom


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# score_car
# ---------------------------------------------------------------------------


def _normalize_triple(t: Any) -> tuple[str, str, str]:
    if not isinstance(t, tuple):
        raise TypeError(
            f"car triple must be a tuple of (make, model, generation), got "
            f"{type(t).__name__}={t!r}"
        )
    if len(t) != 3:
        raise TypeError(
            f"car triple must have exactly 3 elements (make, model, generation), "
            f"got {len(t)} in {t!r}"
        )
    out: list[str] = []
    for i, part in enumerate(t):
        if not isinstance(part, str):
            raise TypeError(
                f"car triple element {i} must be str, got "
                f"{type(part).__name__}={part!r}"
            )
        out.append(_normalize_string(part) or "")
    return (out[0], out[1], out[2])


def score_car(
    predicted: Sequence[tuple[str, str, str]],
    truth: Sequence[tuple[str, str, str]],
) -> dict[str, float]:
    """Score a single part's predicted car-generation triples against truth.

    Multiset semantics: TP = sum over unique triples of min(pred_count, truth_count);
    precision = TP / |predicted|, recall = TP / |truth|. Returns
    ``{precision, recall, f1, n_predicted, n_truth, n_correct}``.

    Comparison is case-insensitive + whitespace-collapsed per element.
    Empty predicted + empty truth → 0/0/0 (not NaN).
    """
    if predicted is None or truth is None:
        raise TypeError(
            "score_car: predicted and truth must both be sequences of tuples, "
            f"got predicted={predicted!r} truth={truth!r}"
        )

    pred_norm = Counter(_normalize_triple(t) for t in predicted)
    truth_norm = Counter(_normalize_triple(t) for t in truth)

    tp = sum(min(pred_norm[k], truth_norm[k]) for k in pred_norm.keys() & truth_norm.keys())
    n_pred = sum(pred_norm.values())
    n_truth = sum(truth_norm.values())

    precision = _safe_div(tp, n_pred)
    recall = _safe_div(tp, n_truth)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "n_predicted": n_pred,
        "n_truth": n_truth,
        "n_correct": tp,
    }


# ---------------------------------------------------------------------------
# score_manufacturer / score_category — single-value per-part binary
# ---------------------------------------------------------------------------


def _score_single_value(
    predicted: Optional[str], truth: Optional[str]
) -> dict[str, Any]:
    """Per-part binary scorer used by manufacturer and category.

    Returns ``{predicted, truth, has_truth, predicted_present, correct}`` where
    ``correct`` is True iff truth is non-null AND predicted matches truth
    (after normalization). The aggregator combines these per-part dicts into
    precision/recall over the universe of ``{parts where truth is non-null}``.
    """
    if predicted is not None and not isinstance(predicted, str):
        raise TypeError(
            f"predicted must be Optional[str], got {type(predicted).__name__}={predicted!r}"
        )
    if truth is not None and not isinstance(truth, str):
        raise TypeError(
            f"truth must be Optional[str], got {type(truth).__name__}={truth!r}"
        )

    pred_norm = _normalize_string(predicted) or None
    truth_norm = _normalize_string(truth) or None

    has_truth = truth_norm is not None
    predicted_present = pred_norm is not None
    correct = has_truth and predicted_present and pred_norm == truth_norm

    return {
        "predicted": pred_norm,
        "truth": truth_norm,
        "has_truth": has_truth,
        "predicted_present": predicted_present,
        "correct": bool(correct),
    }


def score_manufacturer(
    predicted: Optional[str], truth: Optional[str]
) -> dict[str, Any]:
    """Per-part manufacturer scorer (binary). See ``_score_single_value``."""
    return _score_single_value(predicted, truth)


def score_category(predicted: Optional[str], truth: Optional[str]) -> dict[str, Any]:
    """Per-part category scorer (binary). See ``_score_single_value``."""
    return _score_single_value(predicted, truth)


# ---------------------------------------------------------------------------
# score_spec_field_level / score_spec_part_level
# ---------------------------------------------------------------------------


def _spec_value_equal(a: Any, b: Any) -> bool:
    """Equality for spec-field values. Strings normalized; floats compared
    with a small tolerance; everything else uses ``==``."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, str) and isinstance(b, str):
        return _normalize_string(a) == _normalize_string(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        # Tolerate JSON-roundtrip / arithmetic float drift; defaults to
        # rel_tol=1e-9 which is ~1.5e-6 at scale 1500 (more than enough for
        # weight_grams, spring_rate, etc.). abs_tol covers values near zero.
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def score_spec_field_level(
    predicted: Mapping[str, Any],
    truth: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, Any]:
    """Per-part, per-field spec scorer.

    For each field in ``fields``:

    * ``truth[field] is None and predicted[field] is None`` → excluded from the
      universe (not a TP, not an FP, not an FN).
    * ``truth[field] is None and predicted[field] is non-null`` → false positive
      (predictor hallucinated).
    * ``truth[field] is non-null and predicted[field] is None`` → false negative.
    * ``truth[field] is non-null and predicted[field] equals truth`` → true positive.
    * ``truth[field] is non-null and predicted[field] disagrees`` → false negative
      (and the predicted non-null value is also a false positive — recorded as
      both ``fp`` and ``fn`` so a wrong-value mistake is double-counted, matching
      the standard PR-curve interpretation for non-binary multi-value fields).

    Returns ``{per_field: {field: {tp, fp, fn}}, n_universe}`` where
    ``n_universe`` is the count of fields where truth was non-null. The
    aggregator turns this into precision/recall/f1 per field plus micro_f1 and
    macro_f1.
    """
    if predicted is None or truth is None:
        raise TypeError(
            "score_spec_field_level: predicted and truth must both be dicts, "
            f"got predicted={predicted!r} truth={truth!r}"
        )
    if not isinstance(predicted, Mapping) or not isinstance(truth, Mapping):
        raise TypeError(
            "score_spec_field_level: predicted and truth must be Mapping[str, Any], "
            f"got predicted={type(predicted).__name__} truth={type(truth).__name__}"
        )
    if not isinstance(fields, (list, tuple)):
        raise TypeError(
            f"fields must be a list or tuple of field names, got {type(fields).__name__}"
        )

    per_field: dict[str, dict[str, int]] = {}
    n_universe = 0

    for field in fields:
        p = predicted.get(field)
        t = truth.get(field)
        cell = {"tp": 0, "fp": 0, "fn": 0}
        if t is None and p is None:
            # Excluded from universe — neither predicted nor truth claims this field.
            per_field[field] = cell
            continue
        if t is None and p is not None:
            cell["fp"] = 1
            per_field[field] = cell
            continue
        # truth is non-null from here on
        n_universe += 1
        if p is None:
            cell["fn"] = 1
            per_field[field] = cell
            continue
        if _spec_value_equal(p, t):
            cell["tp"] = 1
        else:
            # Predicted a non-null wrong value: counts as both a miss against
            # truth (fn) and a wrong claim (fp).
            cell["fp"] = 1
            cell["fn"] = 1
        per_field[field] = cell

    return {"per_field": per_field, "n_universe": n_universe}


def score_spec_part_level(
    predicted: Mapping[str, Any],
    truth: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, Any]:
    """Per-part 'all spec fields correct' scorer.

    Returns ``{all_fields_correct: bool, n_universe: int}``. A part is
    'all_fields_correct' iff every field in ``fields`` either:

    * truth is None AND predicted is None (excluded from comparison), OR
    * truth is non-null AND predicted equals truth (after normalization).

    Equivalently: zero fp and zero fn per ``score_spec_field_level``.
    Parts where ``n_universe == 0`` (no field has a truth value) are
    ``all_fields_correct=True`` only if no field was hallucinated (predicted is
    also all-None) — otherwise ``False``.
    """
    field_scores = score_spec_field_level(predicted, truth, fields)
    all_correct = all(
        cell["fp"] == 0 and cell["fn"] == 0
        for cell in field_scores["per_field"].values()
    )
    return {
        "all_fields_correct": all_correct,
        "n_universe": field_scores["n_universe"],
    }


# ---------------------------------------------------------------------------
# Aggregators — list of per-part scores → baseline-shaped envelope
# ---------------------------------------------------------------------------


def _envelope(
    *,
    signal: str,
    sample_size: int,
    extras: Mapping[str, Any],
) -> dict[str, Any]:
    env: dict[str, Any] = {
        "harness_version": HARNESS_VERSION,
        "signal": signal,
        "sample_size": sample_size,
        "generated_at": _now_iso(),
    }
    env.update(extras)
    return env


def aggregate_car(per_part_scores: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-part car scores (multiset PR) into baseline envelope."""
    scores = list(per_part_scores)
    tp = sum(int(s["n_correct"]) for s in scores)
    n_pred = sum(int(s["n_predicted"]) for s in scores)
    n_truth = sum(int(s["n_truth"]) for s in scores)
    precision = _safe_div(tp, n_pred)
    recall = _safe_div(tp, n_truth)
    return _envelope(
        signal="car",
        sample_size=len(scores),
        extras={
            "precision": precision,
            "recall": recall,
            "f1": _f1(precision, recall),
        },
    )


def _aggregate_single_value(
    per_part_scores: Iterable[dict[str, Any]], *, signal: str
) -> dict[str, Any]:
    """Universe = parts where truth is non-null.

    Precision = correct / parts where predictor returned a value AND truth non-null
    Recall    = correct / parts where truth non-null

    Note: a predictor that returns a value for a part with no truth label is
    *not* penalized in precision (out of scope per S01-RESEARCH pitfall #8) —
    only parts where truth is non-null contribute to either denominator. Matches
    the manufacturer-scoring contract in the slice plan.
    """
    scores = list(per_part_scores)
    n_truth = sum(1 for s in scores if s["has_truth"])
    n_truth_and_predicted = sum(
        1 for s in scores if s["has_truth"] and s["predicted_present"]
    )
    n_correct = sum(1 for s in scores if s["correct"])
    precision = _safe_div(n_correct, n_truth_and_predicted)
    recall = _safe_div(n_correct, n_truth)
    return _envelope(
        signal=signal,
        sample_size=len(scores),
        extras={
            "precision": precision,
            "recall": recall,
            "f1": _f1(precision, recall),
        },
    )


def aggregate_manufacturer(
    per_part_scores: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Aggregate per-part manufacturer scores into baseline envelope."""
    return _aggregate_single_value(per_part_scores, signal="manufacturer")


def aggregate_category(per_part_scores: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-part category scores into baseline envelope."""
    return _aggregate_single_value(per_part_scores, signal="category")


def aggregate_spec_field_level(
    per_part_scores: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate per-part spec-field scores → micro/macro F1 + per_field block.

    Sums tp/fp/fn across parts per field, computes per-field precision/recall/f1,
    then computes:

    * micro_f1: f1 over summed tp/fp/fn across all fields (each universe entry
      weighted equally regardless of which field it lives on).
    * macro_f1: arithmetic mean of per-field f1 over fields whose universe size
      is non-zero (a field that no part has truth for is excluded from macro
      so a single sparse field doesn't drag the average to zero).

    Top-level ``precision``/``recall``/``f1`` mirror the micro view because the
    baseline JSON schema is single-shape across signals; the ``per_field``
    block carries the breakdown.
    """
    scores = list(per_part_scores)
    fields_seen: set[str] = set()
    sum_tp: dict[str, int] = {}
    sum_fp: dict[str, int] = {}
    sum_fn: dict[str, int] = {}

    for s in scores:
        for field, cell in s["per_field"].items():
            fields_seen.add(field)
            sum_tp[field] = sum_tp.get(field, 0) + int(cell["tp"])
            sum_fp[field] = sum_fp.get(field, 0) + int(cell["fp"])
            sum_fn[field] = sum_fn.get(field, 0) + int(cell["fn"])

    per_field: dict[str, dict[str, float]] = {}
    macro_f1_terms: list[float] = []
    for field in fields_seen:
        tp = sum_tp.get(field, 0)
        fp = sum_fp.get(field, 0)
        fn = sum_fn.get(field, 0)
        prec = _safe_div(tp, tp + fp)
        rec = _safe_div(tp, tp + fn)
        f1 = _f1(prec, rec)
        per_field[field] = {"precision": prec, "recall": rec, "f1": f1}
        # Macro: only include fields where at least one part had ground truth.
        if (tp + fn) > 0:
            macro_f1_terms.append(f1)

    total_tp = sum(sum_tp.values())
    total_fp = sum(sum_fp.values())
    total_fn = sum(sum_fn.values())
    micro_p = _safe_div(total_tp, total_tp + total_fp)
    micro_r = _safe_div(total_tp, total_tp + total_fn)
    micro_f1 = _f1(micro_p, micro_r)
    macro_f1 = (
        sum(macro_f1_terms) / len(macro_f1_terms) if macro_f1_terms else 0.0
    )

    extras: dict[str, Any] = {
        "precision": micro_p,
        "recall": micro_r,
        "f1": micro_f1,
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
    }
    if per_field:
        extras["per_field"] = per_field

    return _envelope(
        signal="spec_field_level",
        sample_size=len(scores),
        extras=extras,
    )


def aggregate_spec_part_level(
    per_part_scores: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate per-part 'all fields correct' booleans into baseline envelope.

    Emits ``all_fields_correct_rate`` per the locked baseline schema (T01).
    """
    scores = list(per_part_scores)
    total = len(scores)
    n_all_correct = sum(1 for s in scores if s["all_fields_correct"])
    rate = _safe_div(n_all_correct, total)
    return _envelope(
        signal="spec_part_level",
        sample_size=total,
        extras={
            "all_fields_correct_rate": rate,
        },
    )


__all__ = [
    "score_car",
    "score_manufacturer",
    "score_category",
    "score_spec_field_level",
    "score_spec_part_level",
    "aggregate_car",
    "aggregate_manufacturer",
    "aggregate_category",
    "aggregate_spec_field_level",
    "aggregate_spec_part_level",
]
