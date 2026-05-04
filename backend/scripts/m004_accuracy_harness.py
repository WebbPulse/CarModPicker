"""M004 accuracy harness CLI.

Canonical entry point for the M004 accuracy gate. Run as
``python -m scripts.m004_accuracy_harness`` from inside ``backend/``.

What it does
------------
For each requested signal (``car``, ``manufacturer``, ``category``) the
harness:

1. Loads a corpus — either the locked, hand/bootstrap-labeled gold set under
   ``.gsd/milestones/M004/gold-set/parts.json`` (``--corpus gold``) or the
   live ``CrawledPage`` table with programmatic ground truth (``--corpus
   full``, directional only).
2. Runs the live production predictors against each part (no DB writes —
   harness is read-only).
3. Scores predictions against truth via :mod:`scripts.m004_scoring`.
4. Aggregates per-part scores into a single baseline-shaped envelope per
   signal and prints one structured JSON line per signal to stdout.
5. Optionally writes the envelopes to disk (``--baseline-out``), compares
   against an existing baseline (``--baseline-compare``), and runs the R069
   no-regression guard (``--guard``).

Failure modes
-------------
* Gold-set file missing → exit 2 with structured error.
* Prior baseline schema drift (HARNESS_VERSION mismatch) → exit 3 with the
  offending file path.
* Live predictor raises on a single part → log ``predictor_crashed`` with
  ``part_id`` and exception class, score that part as ``all wrong``,
  continue.
* DB unreachable in ``--corpus full`` → exit 4 with diagnostic message.
  ``--corpus gold`` has no DB dependency.

Exit codes
----------
* ``0`` — run completed successfully (and, for ``--baseline-compare`` /
  ``--guard``, no regression).
* ``1`` — comparison or guard failed (regression detected, lift below
  ``--min-relative-lift``).
* ``2`` — gold-set file missing.
* ``3`` — baseline schema drift.
* ``4`` — DB unreachable for ``--corpus full``.
* ``2`` is also reused for "no rows scored" which the caller treats as a
  setup failure.

Banner / directional warning
----------------------------
``--corpus full`` always prints a startup banner AND embeds
``"directional_only": true`` plus the warning string in the run summary so
operators don't accidentally treat full-corpus numbers as the canonical
absolute accuracy. Hand-labeled gold remains the only honest gate.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger("m004_accuracy_harness")


# ---------------------------------------------------------------------------
# Constants & paths
# ---------------------------------------------------------------------------

# repo root from backend/scripts/m004_accuracy_harness.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_SET_PATH = _REPO_ROOT / ".gsd/milestones/M004/gold-set/parts.json"
DEFAULT_CURSOR_PATH = (
    Path(__file__).resolve().parents[1] / ".crawler-state" / "m004_harness_cursor.json"
)

ALL_SIGNALS: tuple[str, ...] = (
    "car",
    "manufacturer",
    "category",
)

# CLI --signal values map to which harness signals to run.
_SIGNAL_GROUPS: dict[str, tuple[str, ...]] = {
    "car": ("car",),
    "manufacturer": ("manufacturer",),
    "category": ("category",),
    "all": ALL_SIGNALS,
}

REGRESSION_ABS_THRESHOLD = 0.02  # R069: >2% absolute drop on any metric

# Directional banner for --corpus full.
DIRECTIONAL_WARNING = (
    "Programmatic ground truth shares blind spots with the live extractor. "
    "Hand-labeled gold is the only honest absolute number."
)


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m004_accuracy_harness",
        description=(
            "M004 accuracy harness. Scores live extractor predictions against "
            "the gold set (or, directionally, the full corpus) and produces "
            "per-signal baseline-shaped JSON envelopes."
        ),
    )
    p.add_argument(
        "--signal",
        choices=sorted(_SIGNAL_GROUPS.keys()),
        default="all",
        help="Signal(s) to score.",
    )
    p.add_argument(
        "--corpus",
        choices=("gold", "full"),
        default="gold",
        help="'gold' = hand/bootstrap-labeled fixture; 'full' = directional run over CrawledPage.",
    )
    p.add_argument(
        "--gold-set",
        type=Path,
        default=DEFAULT_GOLD_SET_PATH,
        help="Path to the gold-set parts.json (default: .gsd/milestones/M004/gold-set/parts.json).",
    )
    p.add_argument(
        "--baseline-out",
        type=Path,
        default=None,
        help="Directory: write per-signal baseline JSON files (validated on write).",
    )
    p.add_argument(
        "--baseline-compare",
        type=Path,
        default=None,
        help="Directory: compare current run against per-signal baseline JSON files.",
    )
    p.add_argument(
        "--min-relative-lift",
        type=float,
        default=None,
        help="With --baseline-compare, exit 1 if any signal's f1 lift is below this threshold.",
    )
    p.add_argument(
        "--guard",
        type=Path,
        default=None,
        help="R069 guard: directory of baselines. Exit 1 if any signal regressed >2% absolute on any metric.",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="--corpus full: resume from on-disk cursor (no-op for --corpus gold).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="--corpus full: cap rows scored (debugging).",
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Write the run summary as JSON to this path (in addition to stdout).",
    )
    p.add_argument(
        "--cursor-path",
        type=Path,
        default=DEFAULT_CURSOR_PATH,
        help="Override the --corpus full cursor file location.",
    )
    return p


# ---------------------------------------------------------------------------
# Live predictors — thin wrappers that never raise (per Failure Modes)
# ---------------------------------------------------------------------------


def _safe_predict(
    fn_name: str,
    part_id: str,
    fn,  # callable
    *args,
    **kwargs,
):
    """Run ``fn`` and return ``(value, error_repr_or_None)``.

    On exception, log ``predictor_crashed`` and return ``(None, error_repr)``
    so the caller can score the part as "all wrong" without aborting the
    harness. Never re-raises.
    """
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001 — defensive harness boundary
        logger.warning(
            "predictor_crashed",
            extra={
                "predictor": fn_name,
                "part_id": part_id,
                "error_class": type(exc).__name__,
                "error": repr(exc),
            },
        )
        return None, repr(exc)


def _predict_car_triples(
    part_id: str, name: str, description: str, url: Optional[str] = None
) -> list[tuple[str, str, str]]:
    from app.core.car_inference import infer_car_generations

    triples, _ = _safe_predict(
        "infer_car_generations",
        part_id,
        infer_car_generations,
        name,
        description,
        url,
    )
    if triples is None:
        return []
    # Defensive: ensure tuples (some callers might return lists internally).
    return [tuple(t) for t in triples if isinstance(t, (list, tuple)) and len(t) == 3]


def _predict_manufacturer(
    part_id: str,
    name: str,
    description: str,
    html: str = "",
    product_url: Optional[str] = None,
) -> Optional[str]:
    """Resolve the manufacturer for one row through the universal predictor.

    S03 T04 widened this from a title→description chain to consume the row's
    archived HTML so the JSON-LD/microdata/OpenGraph layers in
    ``part_manufacturer_universal`` can fire. ``html`` defaults to ``""`` so
    legacy callers without HTML still resolve through the title/description
    fallback ladder. The ``_safe_predict`` wrapper preserves the failure
    contract: a single broken page logs ``predictor_crashed`` and the row
    scores all-wrong (None) without aborting the run (MEM214).
    """
    from app.crawlers.parsing import part_manufacturer_universal

    guess, _ = _safe_predict(
        "part_manufacturer_universal",
        part_id,
        part_manufacturer_universal,
        name,
        description,
        html,
        product_url=product_url,
    )
    return guess


def _predict_category(
    part_id: str, name: str, description: str
) -> Optional[str]:
    from app.core.category_inference import infer_category

    cat, _ = _safe_predict(
        "infer_category", part_id, infer_category, name, description
    )
    return cat


# ---------------------------------------------------------------------------
# Gold-set iteration
# ---------------------------------------------------------------------------


class GoldSetMissingError(Exception):
    """Raised when the gold-set parts.json does not exist or is empty."""


def _iter_gold_set(path: Path) -> Iterable[dict[str, Any]]:
    """Load and yield each row from the gold-set parts.json.

    Re-uses ``load_gold_set`` from the labeling tool so structural
    validation stays consistent (malformed file → fail loud at startup).
    """
    if not path.exists():
        raise GoldSetMissingError(
            f"gold-set file not found: {path} — run "
            f"`python -m scripts.m004_label_gold_set --bootstrap N` first."
        )
    from scripts.m004_label_gold_set import load_gold_set

    rows = load_gold_set(path)
    if not rows:
        raise GoldSetMissingError(
            f"gold-set file is empty: {path} — re-run the labeling tool with "
            f"--bootstrap N to seed it."
        )
    yield from rows


def _row_html(row: dict[str, Any]) -> str:
    return row.get("html_excerpt") or ""


def _row_url(row: dict[str, Any]) -> Optional[str]:
    return row.get("url") or row.get("product_url")


# ---------------------------------------------------------------------------
# Per-row scoring → per-part dicts (one per signal)
# ---------------------------------------------------------------------------


def _score_row(
    row: dict[str, Any],
    signals: Iterable[str],
) -> dict[str, Any]:
    """Run every requested signal's predictor + scorer for one row."""
    from scripts.m004_scoring import (
        score_car,
        score_category,
        score_manufacturer,
    )

    part_id = str(row["part_id"])
    name = row.get("raw_name") or ""
    description = row.get("raw_description") or ""
    html = _row_html(row)
    url = _row_url(row)
    truth_category = row.get("truth_category")

    out: dict[str, Any] = {"part_id": part_id}
    signals = set(signals)

    if "car" in signals:
        truth_triples = [tuple(t) for t in (row.get("truth_car_triples") or [])]
        predicted_triples = _predict_car_triples(part_id, name, description, url)
        out["car"] = score_car(predicted_triples, truth_triples)

    if "manufacturer" in signals:
        predicted = _predict_manufacturer(part_id, name, description, html, url)
        out["manufacturer"] = score_manufacturer(
            predicted, row.get("truth_manufacturer")
        )

    if "category" in signals:
        predicted = _predict_category(part_id, name, description)
        out["category"] = score_category(predicted, truth_category)

    return out


# ---------------------------------------------------------------------------
# Aggregation per signal → baseline envelope
# ---------------------------------------------------------------------------


def _aggregate(
    per_part_scores: list[dict[str, Any]], signals: Iterable[str]
) -> dict[str, dict[str, Any]]:
    """Dispatch to the right ``aggregate_*`` for each requested signal."""
    from scripts.m004_scoring import (
        aggregate_car,
        aggregate_category,
        aggregate_manufacturer,
    )

    envelopes: dict[str, dict[str, Any]] = {}
    for signal in signals:
        per_signal = [s[signal] for s in per_part_scores if signal in s]
        if signal == "car":
            envelopes[signal] = aggregate_car(per_signal)
        elif signal == "manufacturer":
            envelopes[signal] = aggregate_manufacturer(per_signal)
        elif signal == "category":
            envelopes[signal] = aggregate_category(per_signal)
        else:  # pragma: no cover — guarded by CLI choices
            raise ValueError(f"unknown signal {signal!r}")
    return envelopes


# ---------------------------------------------------------------------------
# Baseline I/O — read/write with schema validation
# ---------------------------------------------------------------------------


class BaselineFileError(Exception):
    """Raised when a baseline file fails to load or validate."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def _read_baseline(path: Path) -> dict[str, Any]:
    from scripts.m004_baseline_schema import (
        BaselineSchemaError,
        validate_baseline,
    )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BaselineFileError(path, f"could not read: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BaselineFileError(path, f"invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise BaselineFileError(path, f"root must be a dict, got {type(data).__name__}")
    try:
        validate_baseline(data)
    except BaselineSchemaError as exc:
        raise BaselineFileError(path, f"schema drift: {exc}") from exc
    return data


def _write_baseline(path: Path, envelope: dict[str, Any]) -> None:
    from scripts.m004_baseline_schema import validate_baseline

    validate_baseline(envelope)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Compare / guard
# ---------------------------------------------------------------------------


_GUARDED_METRICS: tuple[str, ...] = (
    "precision",
    "recall",
    "f1",
)


def _detect_regressions(
    current: dict[str, dict[str, Any]],
    baseline_dir: Path,
) -> tuple[list[dict[str, Any]], list[BaselineFileError]]:
    """For each signal, load ``baseline_dir/<signal>.json`` and compare.

    Returns ``(regressions, schema_errors)``. A regression is any metric in
    ``_GUARDED_METRICS`` whose current value dropped by more than
    ``REGRESSION_ABS_THRESHOLD`` versus the baseline.
    """
    regressions: list[dict[str, Any]] = []
    schema_errors: list[BaselineFileError] = []
    for signal, env in current.items():
        path = baseline_dir / f"{signal}.json"
        if not path.exists():
            logger.info(
                "baseline_missing",
                extra={"signal": signal, "path": str(path)},
            )
            continue
        try:
            prior = _read_baseline(path)
        except BaselineFileError as exc:
            schema_errors.append(exc)
            continue
        for metric in _GUARDED_METRICS:
            if metric not in env or metric not in prior:
                continue
            cur_v = float(env[metric])
            prev_v = float(prior[metric])
            delta = cur_v - prev_v
            if delta < -REGRESSION_ABS_THRESHOLD:
                regressions.append(
                    {
                        "signal": signal,
                        "metric": metric,
                        "prior": prev_v,
                        "current": cur_v,
                        "delta": delta,
                    }
                )
    return regressions, schema_errors


def _compute_lift(
    current: dict[str, dict[str, Any]],
    baseline_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[BaselineFileError]]:
    """Compute per-signal {prior, delta_relative, regressed} for every metric.

    Used by ``--baseline-compare``. ``regressed=True`` means *any* guarded
    metric on this signal dropped past the absolute threshold.
    """
    out: dict[str, dict[str, Any]] = {}
    errors: list[BaselineFileError] = []
    for signal, env in current.items():
        path = baseline_dir / f"{signal}.json"
        if not path.exists():
            continue
        try:
            prior = _read_baseline(path)
        except BaselineFileError as exc:
            errors.append(exc)
            continue
        signal_block: dict[str, Any] = {"baseline_path": str(path), "metrics": {}}
        any_regressed = False
        for metric in _GUARDED_METRICS:
            if metric not in env or metric not in prior:
                continue
            cur_v = float(env[metric])
            prev_v = float(prior[metric])
            delta = cur_v - prev_v
            delta_rel = delta / prev_v if prev_v != 0 else 0.0
            regressed = delta < -REGRESSION_ABS_THRESHOLD
            if regressed:
                any_regressed = True
            signal_block["metrics"][metric] = {
                "prior": prev_v,
                "current": cur_v,
                "delta": delta,
                "delta_relative": delta_rel,
                "regressed": regressed,
            }
        signal_block["regressed"] = any_regressed
        out[signal] = signal_block
    return out, errors


# ---------------------------------------------------------------------------
# --corpus full iteration (DB-backed, directional)
# ---------------------------------------------------------------------------


class DBUnreachableError(Exception):
    """Raised when --corpus full cannot reach the DB."""


def _iter_full_corpus(
    *,
    cursor_path: Path,
    resume: bool,
    limit: Optional[int],
    log: logging.Logger,
) -> Iterable[dict[str, Any]]:
    """Iterate ``CrawledPage`` rows, yielding gold-set-shaped dicts.

    Mirrors ``m004_label_gold_set._iterate_db_pages`` for the iteration
    shape, but generates ground truth via ``truth_from_html`` instead of
    ``bootstrap_label``. Persists a cursor (``last_page_id``) so long runs
    can resume.

    Raises :class:`DBUnreachableError` if the DB / app.* imports cannot
    resolve — caller maps that to exit code 4.
    """
    try:
        from sqlalchemy.exc import OperationalError, ProgrammingError  # type: ignore[import-not-found]
        from sqlalchemy.orm import selectinload  # type: ignore[import-not-found]

        from app.api.models.crawled_page import CrawledPage  # type: ignore[import-not-found]
        from app.api.models.part import Part  # type: ignore[import-not-found]
        from app.crawlers.archive_rescrape import load_archived_html  # type: ignore[import-not-found]
        from app.db.session import SessionLocal  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise DBUnreachableError(f"import failed: {exc!r}") from exc

    from scripts.m004_ground_truth import truth_from_html

    try:
        session = SessionLocal()
    except Exception as exc:  # noqa: BLE001
        raise DBUnreachableError(f"session error: {exc!r}") from exc

    cursor: dict[str, Any] = {"last_page_id": None}
    if resume and cursor_path.exists():
        try:
            cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            log.warning("cursor_unreadable", extra={"path": str(cursor_path), "error": repr(exc)})

    emitted = 0

    try:
        try:
            q = (
                session.query(CrawledPage)
                .options(
                    selectinload(CrawledPage.part).selectinload(
                        Part.part_manufacturer
                    )
                )
                .filter(CrawledPage.part_id.is_not(None))
            )
            if cursor.get("last_page_id"):
                q = q.filter(CrawledPage.id > cursor["last_page_id"])
            q = q.order_by(CrawledPage.id).yield_per(500)
            if limit is not None:
                q = q.limit(limit)
        except Exception as exc:  # noqa: BLE001
            raise DBUnreachableError(f"query failed: {exc!r}") from exc

        try:
            page_iter = iter(q)
        except (OperationalError, ProgrammingError) as exc:
            raise DBUnreachableError(
                f"schema unavailable: {exc.orig!r}"
            ) from exc
        while True:
            try:
                page = next(page_iter)
            except StopIteration:
                break
            except (OperationalError, ProgrammingError) as exc:
                # Lazy query execution surfaces missing/incompatible schema
                # only when rows are pulled. Translate to the documented
                # exit-4 path instead of leaking a SQLAlchemy traceback.
                raise DBUnreachableError(
                    f"schema unavailable: {exc.orig!r}"
                ) from exc
            try:
                html = load_archived_html(page, log)
            except Exception as exc:  # noqa: BLE001
                log.info(
                    "skip_page_load_error",
                    extra={"page_id": str(page.id), "error": repr(exc)},
                )
                continue
            if not html:
                continue

            part = page.part
            try:
                truth = truth_from_html(html, retailer=page.source)
            except Exception as exc:  # noqa: BLE001
                log.info(
                    "skip_truth_error",
                    extra={"page_id": str(page.id), "error": repr(exc)},
                )
                continue
            yield {
                "part_id": str(part.id) if part else f"page-{page.id}",
                "retailer": page.source or "unknown",
                "category": (
                    part.category.name if part and part.category else None
                ),
                "raw_name": (part.name if part and part.name else "") or "",
                "raw_description": (
                    part.description if part and part.description else ""
                )
                or "",
                "html_excerpt": html,
                "truth_car_triples": truth.get("car_triples") or [],
                "truth_manufacturer": truth.get("manufacturer"),
                "truth_category": truth.get("category"),
            }
            emitted += 1
            cursor["last_page_id"] = page.id
            if emitted % 100 == 0:
                _persist_cursor(cursor_path, cursor, log)
        # Final cursor flush so the next --resume picks up from end-of-run.
        _persist_cursor(cursor_path, cursor, log)
    finally:
        try:
            session.close()
        except Exception:  # noqa: BLE001
            pass


def _persist_cursor(path: Path, cursor: dict[str, Any], log: logging.Logger) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cursor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        log.warning("cursor_write_failed", extra={"path": str(path), "error": repr(exc)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _print_json_line(payload: dict[str, Any]) -> None:
    """One JSON object per line on stdout — machine-readable signal stream."""
    print(json.dumps(payload, sort_keys=True))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    args = _build_parser().parse_args(argv)
    signals = _SIGNAL_GROUPS[args.signal]

    # ------------------------------------------------------------------ corpus
    if args.corpus == "gold":
        try:
            rows = list(_iter_gold_set(args.gold_set))
        except GoldSetMissingError as exc:
            logger.error("gold_set_missing", extra={"path": str(args.gold_set)})
            print(
                json.dumps(
                    {
                        "error": "gold_set_missing",
                        "message": str(exc),
                        "path": str(args.gold_set),
                    }
                ),
                file=sys.stderr,
            )
            return 2
    else:
        # Banner so operators don't accidentally treat full-corpus numbers as canonical.
        sys.stderr.write(
            "[m004_accuracy_harness] --corpus full: directional only. "
            + DIRECTIONAL_WARNING
            + "\n"
        )
        try:
            rows = list(
                _iter_full_corpus(
                    cursor_path=args.cursor_path,
                    resume=args.resume,
                    limit=args.limit,
                    log=logger,
                )
            )
        except DBUnreachableError as exc:
            logger.error("db_unreachable", extra={"error": repr(exc)})
            print(
                json.dumps(
                    {"error": "db_unreachable", "message": str(exc)}
                ),
                file=sys.stderr,
            )
            return 4

    if not rows:
        print(
            json.dumps(
                {
                    "error": "no_rows_scored",
                    "message": "corpus iterator produced zero rows",
                    "corpus": args.corpus,
                }
            ),
            file=sys.stderr,
        )
        return 2

    # ---------------------------------------------------------------- scoring
    per_part_scores: list[dict[str, Any]] = []
    for row in rows:
        try:
            per_part_scores.append(_score_row(row, signals))
        except Exception as exc:  # noqa: BLE001 — defensive harness boundary
            # _safe_predict already catches predictor crashes; a TypeError here
            # comes from the scorer itself (malformed truth shape). Log + skip
            # so one bad row can't abort the whole run.
            logger.warning(
                "row_scoring_failed",
                extra={
                    "part_id": str(row.get("part_id")),
                    "error": repr(exc),
                    "trace": traceback.format_exc(limit=2),
                },
            )
            continue

    envelopes = _aggregate(per_part_scores, signals)

    # ------------------------------------------------------------ baseline-out
    if args.baseline_out is not None:
        for signal, env in envelopes.items():
            out_path = args.baseline_out / f"{signal}.json"
            _write_baseline(out_path, env)
            logger.info(
                "baseline_written",
                extra={"signal": signal, "path": str(out_path)},
            )

    # --------------------------------------------------------- baseline-compare
    comparison_block: Optional[dict[str, Any]] = None
    compare_exit = 0
    if args.baseline_compare is not None:
        comparison_block, schema_errors = _compute_lift(
            envelopes, args.baseline_compare
        )
        if schema_errors:
            for err in schema_errors:
                print(
                    json.dumps(
                        {
                            "error": "baseline_schema_drift",
                            "path": str(err.path),
                            "reason": err.reason,
                        }
                    ),
                    file=sys.stderr,
                )
            return 3
        # Lift threshold check (relative lift on f1)
        if args.min_relative_lift is not None:
            for signal, block in comparison_block.items():
                f1 = block["metrics"].get("f1")
                if f1 is None:
                    continue
                if f1["delta_relative"] < args.min_relative_lift:
                    compare_exit = 1
                    logger.warning(
                        "lift_below_threshold",
                        extra={
                            "signal": signal,
                            "delta_relative": f1["delta_relative"],
                            "threshold": args.min_relative_lift,
                        },
                    )
        # Regression in any signal also fails the compare.
        if any(b.get("regressed") for b in comparison_block.values()):
            compare_exit = 1

    # ------------------------------------------------------------------- guard
    guard_block: Optional[dict[str, Any]] = None
    guard_exit = 0
    if args.guard is not None:
        regressions, schema_errors = _detect_regressions(envelopes, args.guard)
        if schema_errors:
            for err in schema_errors:
                print(
                    json.dumps(
                        {
                            "error": "baseline_schema_drift",
                            "path": str(err.path),
                            "reason": err.reason,
                        }
                    ),
                    file=sys.stderr,
                )
            return 3
        guard_block = {
            "guard_verdict": "fail" if regressions else "pass",
            "regressions": regressions,
            "threshold_abs": REGRESSION_ABS_THRESHOLD,
        }
        if regressions:
            guard_exit = 1

    # --------------------------------------------------------------- emit
    # One structured JSON line per signal, then optional comparison + guard
    # blocks.
    for signal, env in envelopes.items():
        line: dict[str, Any] = {**env, "n": env.get("sample_size")}
        if comparison_block is not None and signal in comparison_block:
            line["compare"] = comparison_block[signal]
        _print_json_line(line)

    summary: dict[str, Any] = {
        "corpus": args.corpus,
        "signal": args.signal,
        "rows_scored": len(per_part_scores),
        "rows_attempted": len(rows),
        "signals_emitted": list(envelopes.keys()),
        "generated_at": _now_iso(),
        "envelopes": envelopes,
    }
    if args.corpus == "full":
        summary["directional_only"] = True
        summary["warning"] = DIRECTIONAL_WARNING
    if comparison_block is not None:
        summary["compare"] = comparison_block
    if guard_block is not None:
        summary["guard"] = guard_block
        _print_json_line(guard_block)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return guard_exit or compare_exit


if __name__ == "__main__":
    sys.exit(main())
