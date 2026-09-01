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

All public functions raise ``TypeError`` early on malformed inputs (None where
a dict is expected, wrong tuple arity for car triples) — never a silent
zero-score.
"""

from __future__ import annotations

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
        raise TypeError(f"expected str or None for normalization, got {type(value).__name__}={value!r}")
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
        raise TypeError(f"car triple must be a tuple of (make, model, generation), got " f"{type(t).__name__}={t!r}")
    if len(t) != 3:
        raise TypeError(f"car triple must have exactly 3 elements (make, model, generation), " f"got {len(t)} in {t!r}")
    out: list[str] = []
    for i, part in enumerate(t):
        if not isinstance(part, str):
            raise TypeError(f"car triple element {i} must be str, got " f"{type(part).__name__}={part!r}")
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


def _score_single_value(predicted: Optional[str], truth: Optional[str]) -> dict[str, Any]:
    """Per-part binary scorer used by manufacturer and category.

    Returns ``{predicted, truth, has_truth, predicted_present, correct}`` where
    ``correct`` is True iff truth is non-null AND predicted matches truth
    (after normalization). The aggregator combines these per-part dicts into
    precision/recall over the universe of ``{parts where truth is non-null}``.
    """
    if predicted is not None and not isinstance(predicted, str):
        raise TypeError(f"predicted must be Optional[str], got {type(predicted).__name__}={predicted!r}")
    if truth is not None and not isinstance(truth, str):
        raise TypeError(f"truth must be Optional[str], got {type(truth).__name__}={truth!r}")

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


def score_manufacturer(predicted: Optional[str], truth: Optional[str]) -> dict[str, Any]:
    """Per-part manufacturer scorer (binary). See ``_score_single_value``."""
    return _score_single_value(predicted, truth)


def score_category(predicted: Optional[str], truth: Optional[str]) -> dict[str, Any]:
    """Per-part category scorer (binary). See ``_score_single_value``."""
    return _score_single_value(predicted, truth)


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


def _aggregate_single_value(per_part_scores: Iterable[dict[str, Any]], *, signal: str) -> dict[str, Any]:
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
    n_truth_and_predicted = sum(1 for s in scores if s["has_truth"] and s["predicted_present"])
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


def aggregate_manufacturer(per_part_scores: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-part manufacturer scores into baseline envelope."""
    return _aggregate_single_value(per_part_scores, signal="manufacturer")


def aggregate_category(per_part_scores: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-part category scores into baseline envelope."""
    return _aggregate_single_value(per_part_scores, signal="category")


__all__ = [
    "score_car",
    "score_manufacturer",
    "score_category",
    "aggregate_car",
    "aggregate_manufacturer",
    "aggregate_category",
]
