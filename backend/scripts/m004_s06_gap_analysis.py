"""M004 S06 corpus-gap analyzer.

Measurement-only script (MEM212) that produces a research artifact at
``.gsd/milestones/M004/s06-gap-report.json`` so T03/T04 can confirm or override
the planner pre-commits (``manufacturer_part_number`` as the new universal
field; ``wheel`` as the new category-spec slug).

Two questions answered per run:

(a) **Per-universal-field non-null counts** — for each name in
    ``UNIVERSAL_FIELD_NAMES`` (mirrored from
    ``scripts.m004_corpus_snapshot``), how many corpus parts currently have a
    non-None value? The field with the LOWEST count is the most-missing field
    today and is the natural target for S06 expansion. Reuses
    ``iterate_corpus_snapshot`` so the count semantics match the snapshot CLI
    (MEM044).

(b) **Top-N universal-routed DB category names** — the long tail of categories
    whose parts get validated against ``UniversalSpec`` instead of a dedicated
    spec model. Walks ``crawled_pages → part → category`` once with
    ``selectinload`` on ``Part.category`` and counts category names whose
    ``category_to_subslug`` returns ``'universal'``. The category with the
    HIGHEST count is the natural target for the next category-spec model.

Output schema (machine-readable; written to ``--out``)::

    {
      "snapshot_taken_at": "...ISO8601...",
      "corpus_total": int,
      "zero_corpus": bool,
      "per_universal_field_non_null": {<field>: int, ...},
      "top_universal_routed_categories": [{"name": str, "parts_count": int}, ...],
      "qualitative_fallback": {
        "chosen_universal_field": "manufacturer_part_number",
        "chosen_category_spec_slug": "wheel",
        "source": "corpus" | "qualitative_fallback"
      }
    }

Defensive contract (MEM216)
---------------------------
Per-row iteration is wrapped in ``try/except (OperationalError,
ProgrammingError)`` and degrades to ``corpus_total: 0, zero_corpus: True``,
exit 0, with empty count blocks and ``qualitative_fallback.source =
'qualitative_fallback'`` (the planner pre-commits stand). Real DB-unreachable
from ``SessionLocal()`` construction still exits 1.

Exit codes
----------
* ``0`` — success (including zero-corpus / missing-table degraded branch).
* ``1`` — DB-unreachable at ``SessionLocal()``, argparse failure, or JSON
  write failure.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("m004_s06_gap_analysis")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default output path; relative to ``backend/`` per MEM209.
DEFAULT_OUT_PATH: Path = Path("../.gsd/milestones/M004/s06-gap-report.json")

#: How many universal-routed category names to report. Bounded by the number
#: of distinct category names in the corpus (~< 100 today); 20 is the planner
#: default.
DEFAULT_TOP_N: int = 20

#: Planner pre-commits per S06-PLAN.md and M004-CONTEXT:209. Used as the
#: qualitative-fallback recommendation when the corpus is empty.
QUALITATIVE_FALLBACK_UNIVERSAL_FIELD: str = "manufacturer_part_number"
QUALITATIVE_FALLBACK_CATEGORY_SLUG: str = "wheel"


# ---------------------------------------------------------------------------
# Pure helpers (no DB, unit-test friendly)
# ---------------------------------------------------------------------------


def top_n_categories(
    counts: dict[str, int], *, n: int = DEFAULT_TOP_N
) -> list[dict[str, int]]:
    """Return the top-``n`` (name, parts_count) pairs sorted by count desc,
    name asc as a stable tiebreaker. When fewer than ``n`` distinct names
    exist, returns all of them.
    """
    if not counts:
        return []
    items = sorted(counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))
    return [{"name": name, "parts_count": int(count)} for name, count in items[:n]]


def choose_qualitative_fallback(
    *,
    per_field_non_null: dict[str, int],
    top_universal_routed: list[dict[str, int]],
    zero_corpus: bool,
) -> dict[str, str]:
    """Decide the recommended universal field + category spec slug.

    * ``zero_corpus`` true → return planner pre-commits with
      ``source='qualitative_fallback'``.
    * Otherwise, pick the universal field with the lowest non-null count
      (ties broken by name asc) and the highest-count universal-routed
      category, with ``source='corpus'``. The chosen category slug is the
      category NAME (e.g. ``'wheels'``) — mapping name → SpecRegistry slug
      remains a human/T04 decision; this function just surfaces the
      best-evidence pick.

    The returned dict's ``chosen_category_spec_slug`` is the category NAME
    when sourced from corpus (operator chooses a sub-slug when registering),
    or ``QUALITATIVE_FALLBACK_CATEGORY_SLUG`` (``'wheel'``) when sourced from
    qualitative fallback.
    """
    if zero_corpus or not per_field_non_null or not top_universal_routed:
        return {
            "chosen_universal_field": QUALITATIVE_FALLBACK_UNIVERSAL_FIELD,
            "chosen_category_spec_slug": QUALITATIVE_FALLBACK_CATEGORY_SLUG,
            "source": "qualitative_fallback",
        }

    field_items = sorted(
        per_field_non_null.items(), key=lambda kv: (int(kv[1]), str(kv[0]))
    )
    chosen_field = field_items[0][0]

    # top_universal_routed is already sorted by count desc.
    chosen_category = top_universal_routed[0]["name"]

    return {
        "chosen_universal_field": str(chosen_field),
        "chosen_category_spec_slug": str(chosen_category),
        "source": "corpus",
    }


# ---------------------------------------------------------------------------
# DB iteration for (b): universal-routed category names
# ---------------------------------------------------------------------------


def iterate_universal_routed_categories(
    db,
    *,
    limit: Optional[int] = None,
) -> tuple[dict[str, int], int, bool]:
    """Walk ``crawled_pages → part → category`` once and return
    ``(counts_by_name, corpus_total, zero_corpus)`` where ``counts_by_name``
    is a dict of category name → count for every distinct part whose category
    routes to ``'universal'`` via ``category_to_subslug``.

    The same MEM216 degrade contract applies: ``OperationalError`` or
    ``ProgrammingError`` at the iterator boundary returns
    ``({}, 0, True)``. Real DB-unreachable surfaces from ``SessionLocal()``
    in ``main()`` and exits 1.
    """
    from sqlalchemy.exc import OperationalError, ProgrammingError
    from sqlalchemy.orm import selectinload

    from app.api.models.crawled_page import CrawledPage
    from app.api.models.part import Part
    from app.crawlers.specs.category_bridge import (
        UNIVERSAL_SUBSLUG,
        category_to_subslug,
    )

    counts: Counter[str] = Counter()
    total = 0
    seen_part_ids: set[Any] = set()

    q = (
        db.query(CrawledPage)
        .options(selectinload(CrawledPage.part).selectinload(Part.category))
        .filter(CrawledPage.part_id.is_not(None))
        .order_by(CrawledPage.source, CrawledPage.id)
    )
    if limit:
        q = q.limit(limit)

    try:
        page_iter = iter(q.yield_per(500))
    except (OperationalError, ProgrammingError) as exc:
        logger.warning(
            "snapshot_corpus_table_missing",
            extra={"error_class": type(exc).__name__},
        )
        return {}, 0, True

    while True:
        try:
            page = next(page_iter)
        except StopIteration:
            break
        except (OperationalError, ProgrammingError) as exc:
            logger.warning(
                "snapshot_corpus_table_missing",
                extra={"error_class": type(exc).__name__},
            )
            return {}, 0, True
        try:
            part = page.part
            if part is None:
                continue
            pid = getattr(part, "id", None)
            if pid is None or pid in seen_part_ids:
                continue
            seen_part_ids.add(pid)
            total += 1
            category = getattr(part, "category", None)
            category_name = getattr(category, "name", None) if category is not None else None
            if not category_name:
                continue
            slug = category_to_subslug(
                category_name,
                name=getattr(part, "name", None),
                description=getattr(part, "description", None),
            )
            if slug == UNIVERSAL_SUBSLUG:
                counts[category_name] += 1
        except Exception as exc:  # noqa: BLE001 — defensive (MEM206 pattern)
            logger.debug(
                "gap_row_failed",
                extra={
                    "page_id": getattr(page, "id", "?"),
                    "error_class": type(exc).__name__,
                },
            )
            continue

    return dict(counts), total, total == 0


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def build_gap_report(
    *,
    per_universal_field_non_null: dict[str, int],
    universal_routed_counts: dict[str, int],
    corpus_total: int,
    zero_corpus: bool,
    snapshot_taken_at: str,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    """Construct the on-disk JSON report dict."""
    top_universal_routed = top_n_categories(universal_routed_counts, n=top_n)
    qualitative_fallback = choose_qualitative_fallback(
        per_field_non_null=per_universal_field_non_null,
        top_universal_routed=top_universal_routed,
        zero_corpus=zero_corpus,
    )
    return {
        "snapshot_taken_at": snapshot_taken_at,
        "corpus_total": int(corpus_total),
        "zero_corpus": bool(zero_corpus),
        "per_universal_field_non_null": dict(per_universal_field_non_null),
        "top_universal_routed_categories": top_universal_routed,
        "qualitative_fallback": qualitative_fallback,
    }


def write_report(report: dict[str, Any], out_path: Path) -> None:
    """Write the JSON report, creating parent dirs as needed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")


def emit_json_envelope(payload: dict[str, Any]) -> None:
    """Emit one structured JSON line to stdout (machine-pipeable)."""
    print(json.dumps(payload, sort_keys=True))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m004_s06_gap_analysis",
        description=(
            "M004 S06 corpus-gap analyzer (MEM212 measurement-only tool). "
            "Iterates the local crawled_pages -> part corpus and produces a "
            "JSON report enumerating per-universal-field non-null counts and "
            "the top-N DB category names that currently route to "
            "'universal' via category_to_subslug. Output guides the S06 "
            "expansion picks (new universal field, new category-spec model)."
        ),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help=(
            "Output JSON path. Default: "
            "../.gsd/milestones/M004/s06-gap-report.json (relative to "
            "backend/ cwd)."
        ),
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"Max universal-routed category names to report (default {DEFAULT_TOP_N}).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap iteration at N pages (smoke-test hook only).",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # DB connect — exit 1 on unreachable.
    try:
        from app.db.session import SessionLocal  # local import; respects TESTING env
    except Exception as exc:  # noqa: BLE001
        logger.error("db_unreachable", extra={"error_class": type(exc).__name__})
        print(
            json.dumps({"error": "db_unreachable", "detail": repr(exc)}),
            file=sys.stderr,
        )
        return 1

    try:
        db = SessionLocal()
    except Exception as exc:  # noqa: BLE001
        logger.error("db_unreachable", extra={"error_class": type(exc).__name__})
        print(
            json.dumps({"error": "db_unreachable", "detail": repr(exc)}),
            file=sys.stderr,
        )
        return 1

    try:
        # Reuse iterate_corpus_snapshot for (a) per-universal-field counts.
        # The aggregate counts and corpus_total it returns mirror what the
        # snapshot CLI would produce; we only use per_field_counts +
        # zero_corpus here.
        from scripts.m004_corpus_snapshot import iterate_corpus_snapshot

        _signals, per_field_counts, corpus_total, zero_corpus = iterate_corpus_snapshot(
            db, limit=args.limit
        )

        # (b) Universal-routed category-name counts. Run a separate iterator
        # because iterate_corpus_snapshot does NOT eager-load Part.category;
        # accessing it inline would lazy-load per row.
        if zero_corpus:
            # MEM216 — first iterator already saw missing/empty corpus; skip
            # the second walk and fall through to empty counts.
            universal_routed_counts: dict[str, int] = {}
            ur_total = 0
            ur_zero_corpus = True
        else:
            universal_routed_counts, ur_total, ur_zero_corpus = (
                iterate_universal_routed_categories(db, limit=args.limit)
            )

        # If either iterator hit MEM216 degrade, treat the run as zero-corpus.
        effective_zero_corpus = bool(zero_corpus or ur_zero_corpus)
        # corpus_total used in the report comes from iterate_corpus_snapshot
        # so the per-field denominators stay consistent with the snapshot CLI.
        # ``ur_total`` is a sanity input only; both walkers see the same corpus.
        _ = ur_total  # intentionally unused — see comment above

        report = build_gap_report(
            per_universal_field_non_null=per_field_counts,
            universal_routed_counts=universal_routed_counts,
            corpus_total=corpus_total,
            zero_corpus=effective_zero_corpus,
            snapshot_taken_at=datetime.now(timezone.utc).isoformat(),
            top_n=args.top_n,
        )

        try:
            write_report(report, args.out)
        except OSError as exc:
            logger.error(
                "gap_report_write_failed",
                extra={"out_path": str(args.out), "error_class": type(exc).__name__},
            )
            print(
                json.dumps(
                    {
                        "error": "gap_report_write_failed",
                        "out_path": str(args.out),
                        "detail": repr(exc),
                    }
                ),
                file=sys.stderr,
            )
            return 1

        emit_json_envelope(
            {
                "snapshot_taken_at": report["snapshot_taken_at"],
                "corpus_total": report["corpus_total"],
                "zero_corpus": report["zero_corpus"],
                "qualitative_fallback": report["qualitative_fallback"],
                "out_path": str(args.out),
            }
        )
        return 0
    finally:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
