"""M004 accuracy-harness baseline JSON schema.

Single source of truth for the shape of `.gsd/milestones/M004/baselines/<signal>.json`
and the per-signal envelope emitted by the harness CLI. Pure (no I/O, no shared
resources). Importable from inside `backend/` as `from scripts.m004_baseline_schema
import HARNESS_VERSION, validate_baseline`.

Downstream readers MUST fail loud on schema drift — `validate_baseline` raises
`BaselineSchemaError` rather than silently coercing. Schema drift propagates
through to the harness CLI (`m004_accuracy_harness --guard ...`) which surfaces
the offending file path and exits non-zero.

The `harness_version` field is a single int. Bump it (and the readers) when the
shape changes incompatibly. Adding a new signal is not a breaking change as long
as existing per-signal schemas stay stable; renaming or removing a required
field IS a breaking change.
"""

from __future__ import annotations

from typing import Any, Iterable

HARNESS_VERSION: int = 1

VALID_SIGNALS: tuple[str, ...] = (
    "car",
    "manufacturer",
    "category",
    "spec_field_level",
    "spec_part_level",
)

_COMMON_REQUIRED: tuple[str, ...] = (
    "harness_version",
    "signal",
    "sample_size",
    "generated_at",
)

_F1_SHAPED_SIGNALS: frozenset[str] = frozenset(
    {"car", "manufacturer", "category", "spec_field_level"}
)

_F1_REQUIRED: tuple[str, ...] = ("precision", "recall", "f1")


class BaselineSchemaError(ValueError):
    """Raised when a baseline dict does not conform to the locked schema."""


def _require_keys(d: dict, keys: Iterable[str], *, context: str) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise BaselineSchemaError(
            f"baseline {context} missing required field(s): {missing!r}"
        )


def _require_type(
    d: dict, key: str, expected: type | tuple[type, ...], *, context: str
) -> None:
    value = d[key]
    if isinstance(expected, tuple):
        ok = isinstance(value, expected) and not isinstance(value, bool)
    else:
        ok = isinstance(value, expected) and not (
            expected is int and isinstance(value, bool)
        )
    if not ok:
        raise BaselineSchemaError(
            f"baseline {context}: field {key!r} must be {expected!r}, "
            f"got {type(value).__name__}={value!r}"
        )


def _require_metric(d: dict, key: str, *, context: str) -> None:
    _require_type(d, key, (int, float), context=context)
    v = d[key]
    if not (0.0 <= float(v) <= 1.0):
        raise BaselineSchemaError(
            f"baseline {context}: metric {key!r} must be in [0, 1], got {v!r}"
        )


def validate_baseline(d: dict[str, Any]) -> None:
    """Validate a baseline dict in-place. Raise BaselineSchemaError on drift.

    Covers the common envelope plus the five signal-specific shapes:
      - car, manufacturer, category, spec_field_level: precision/recall/f1
      - spec_part_level: all_fields_correct_rate
    """
    if not isinstance(d, dict):
        raise BaselineSchemaError(
            f"baseline must be a dict, got {type(d).__name__}"
        )

    _require_keys(d, _COMMON_REQUIRED, context="envelope")

    if not isinstance(d["harness_version"], int) or isinstance(
        d["harness_version"], bool
    ):
        raise BaselineSchemaError(
            f"baseline envelope: harness_version must be int, "
            f"got {type(d['harness_version']).__name__}={d['harness_version']!r}"
        )
    if d["harness_version"] != HARNESS_VERSION:
        raise BaselineSchemaError(
            f"baseline envelope: harness_version mismatch — "
            f"file says {d['harness_version']!r}, current HARNESS_VERSION={HARNESS_VERSION}. "
            f"Re-run the harness with --baseline-out to regenerate, "
            f"or upgrade the schema reader."
        )

    signal = d["signal"]
    if signal not in VALID_SIGNALS:
        raise BaselineSchemaError(
            f"baseline envelope: signal must be one of {VALID_SIGNALS!r}, got {signal!r}"
        )

    _require_type(d, "sample_size", int, context="envelope")
    if d["sample_size"] < 0:
        raise BaselineSchemaError(
            f"baseline envelope: sample_size must be >= 0, got {d['sample_size']!r}"
        )

    _require_type(d, "generated_at", str, context="envelope")
    if not d["generated_at"]:
        raise BaselineSchemaError(
            "baseline envelope: generated_at must be a non-empty ISO8601 string"
        )

    ctx = f"signal={signal!r}"
    if signal in _F1_SHAPED_SIGNALS:
        _require_keys(d, _F1_REQUIRED, context=ctx)
        for k in _F1_REQUIRED:
            _require_metric(d, k, context=ctx)
        if signal == "spec_field_level" and "per_field" in d:
            pf = d["per_field"]
            if not isinstance(pf, dict):
                raise BaselineSchemaError(
                    f"baseline {ctx}: per_field must be a dict, got {type(pf).__name__}"
                )
            for field_name, field_metrics in pf.items():
                if not isinstance(field_metrics, dict):
                    raise BaselineSchemaError(
                        f"baseline {ctx}: per_field[{field_name!r}] must be a dict"
                    )
                for k in _F1_REQUIRED:
                    if k not in field_metrics:
                        raise BaselineSchemaError(
                            f"baseline {ctx}: per_field[{field_name!r}] missing {k!r}"
                        )
                    _require_metric(
                        field_metrics, k, context=f"{ctx} per_field[{field_name!r}]"
                    )
    elif signal == "spec_part_level":
        _require_keys(d, ("all_fields_correct_rate",), context=ctx)
        _require_metric(d, "all_fields_correct_rate", context=ctx)
    else:  # pragma: no cover — defensive; VALID_SIGNALS check above is the gate
        raise BaselineSchemaError(
            f"baseline {ctx}: unhandled signal (schema bug — extend validate_baseline)"
        )
