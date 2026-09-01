"""S03 T05 helper: dump per-row manufacturer predictions for error analysis.

The accuracy harness (`m004_accuracy_harness`) only emits aggregate envelopes
via ``--output-json``; this helper re-runs the manufacturer signal one row at a
time, captures the resolution ``source`` from the structured
``manufacturer_universal_resolved`` debug log, and writes a per-row JSON dump
plus retailer-grouped error buckets so a future agent (or the operator after
expanding the gold set) can run T05's retailer-grouping step against a
deterministic artifact instead of re-running the harness blind.

This script is intentionally NOT shipped to production — see MEM212.

Usage (from ``backend/``)::

    python -m scripts.m004_s03_dump_manufacturer_errors \\
        --output ../.gsd/milestones/M004/slices/S03/S03-ERROR-ANALYSIS.json

The output JSON has shape::

    {
      "generated_at": "...",
      "harness_version": 1,
      "corpus": "gold",
      "gold_set_path": "...",
      "row_count": 5,
      "agreement_count": 5,
      "rows": [
        {
          "part_id": "...",
          "retailer": "...",
          "predicted": "BrandX",
          "truth": "BrandX",
          "agreed": true,
          "source": "jsonld_brand"
        },
        ...
      ],
      "source_counts": {"jsonld_brand": 2, "microdata": 2, "opengraph": 1},
      "errors_by_retailer": {}  # empty when fully agreed
    }
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_SET = REPO_ROOT / ".gsd" / "milestones" / "M004" / "gold-set" / "parts.json"
DEFAULT_OUTPUT = REPO_ROOT / ".gsd" / "milestones" / "M004" / "slices" / "S03" / "S03-ERROR-ANALYSIS.json"

HARNESS_VERSION = 1


class _SourceCaptureHandler(logging.Handler):
    """Captures the most recent ``manufacturer_universal_resolved`` source.

    The universal predictor emits exactly one ``manufacturer_universal_resolved``
    log per call (slice plan contract). This handler stores the source from the
    most recent record so the dump helper can attribute each row's prediction
    to the ladder layer that fired.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.last_source: Optional[str] = None
        self.last_value: Optional[str] = None

    def reset(self) -> None:
        self.last_source = None
        self.last_value = None

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() != "manufacturer_universal_resolved":
            return
        self.last_source = getattr(record, "source", None)
        self.last_value = getattr(record, "value", None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m004_s03_dump_manufacturer_errors",
        description=("Dump per-row manufacturer predictions for S03 T05 error analysis."),
    )
    parser.add_argument(
        "--gold-set",
        type=Path,
        default=DEFAULT_GOLD_SET,
        help=f"Path to gold-set parts.json (default: {DEFAULT_GOLD_SET})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path for the JSON dump (default: {DEFAULT_OUTPUT})",
    )
    return parser


def _row_source(handler: _SourceCaptureHandler) -> str:
    return handler.last_source or "unknown"


def _serialize(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    from scripts.m004_accuracy_harness import _iter_gold_set, _predict_manufacturer

    parsing_logger = logging.getLogger("app.crawlers.parsing")
    capture = _SourceCaptureHandler()
    prior_level = parsing_logger.level
    parsing_logger.addHandler(capture)
    parsing_logger.setLevel(logging.DEBUG)
    # Stop the structured debug log from propagating to root so the CLI stays quiet.
    prior_propagate = parsing_logger.propagate
    parsing_logger.propagate = False

    rows_out: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    errors_by_retailer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    agreement_count = 0

    try:
        for row in _iter_gold_set(args.gold_set):
            capture.reset()
            part_id = str(row.get("part_id") or "")
            retailer = str(row.get("retailer") or "unknown")
            name = str(row.get("raw_name") or "")
            description = str(row.get("raw_description") or "")
            html_excerpt = row.get("html_excerpt") or ""
            url = row.get("url") or row.get("product_url")
            truth = row.get("truth_manufacturer")

            predicted = _predict_manufacturer(part_id, name, description, html_excerpt, product_url=url)

            agreed = bool(predicted == truth)
            if agreed:
                agreement_count += 1

            source = _row_source(capture)
            source_counts[source] += 1

            entry = {
                "part_id": part_id,
                "retailer": retailer,
                "predicted": _serialize(predicted),
                "truth": _serialize(truth),
                "agreed": agreed,
                "source": source,
            }
            rows_out.append(entry)
            if not agreed:
                errors_by_retailer[retailer].append(entry)
    finally:
        parsing_logger.removeHandler(capture)
        parsing_logger.setLevel(prior_level)
        parsing_logger.propagate = prior_propagate

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness_version": HARNESS_VERSION,
        "corpus": "gold",
        "gold_set_path": str(args.gold_set),
        "row_count": len(rows_out),
        "agreement_count": agreement_count,
        "rows": rows_out,
        "source_counts": dict(source_counts),
        "errors_by_retailer": {k: v for k, v in errors_by_retailer.items()},
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: payload[k] for k in ("row_count", "agreement_count", "source_counts")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
