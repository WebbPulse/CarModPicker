"""M004 gold-set labeling tool.

Resumable CLI that walks ``CrawledPage`` rows (or, when the DB is unreachable,
the inline ``BOOTSTRAP_FIXTURES`` list) and writes one row per part to
``.gsd/milestones/M004/gold-set/parts.json``. The persisted shape is locked by
``LABELING-RULES.md`` and validated structurally on load (malformed inputs
fail loud rather than silently dropping rows).

Usage::

    python -m scripts.m004_label_gold_set --bootstrap 30
    python -m scripts.m004_label_gold_set --bootstrap 5 --resume
    python -m scripts.m004_label_gold_set --strata-out path/to/strata.json

The auto-mode runner ALWAYS goes through ``--bootstrap N``. The interactive
human-labeling path is intentionally left as a stub (``_run_interactive``)
that raises with a pointer to LABELING-RULES.md — the auto-mode close-out is
what S01 needs and the human pass is operator-driven follow-up work that
spans multiple sessions.

DB-less fallback
----------------
If ``app.db.session.SessionLocal`` cannot connect (no Postgres, no env),
``--bootstrap`` falls back to ``m004_bootstrap_fixtures.BOOTSTRAP_FIXTURES``
(5 hand-crafted parts spanning JSON-LD, microdata, and OG-only pages). The
fallback is deterministic and idempotent — required for auto-mode CI where
no DB is reachable.

File-write safety
-----------------
Writes use ``fcntl.flock(LOCK_EX)`` on the parts.json file so two parallel
runs (e.g. an operator hand-labeling while a bootstrap runner closes a slice)
cannot race a partial JSON write. Each new row is appended-then-flushed in
one ``json.dump`` of the full list.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# Resolve repo root from this file's location: backend/scripts/m004_label_gold_set.py
# → repo root = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_SET_PATH = _REPO_ROOT / ".gsd/milestones/M004/gold-set/parts.json"
DEFAULT_STRATA_PATH = _REPO_ROOT / ".gsd/milestones/M004/gold-set/sampling-strata.json"

# Truncate persisted html_excerpt to keep parts.json under git-friendly size.
HTML_EXCERPT_BYTES = 8 * 1024


class GoldSetLoadError(ValueError):
    """Raised when the on-disk parts.json is structurally malformed."""


# ---------------------------------------------------------------------------
# Tier lookup — derived from ADAPTER_TO_EXPECTED_MAKES (see LABELING-RULES.md)
# ---------------------------------------------------------------------------

# Adapters with single-make expected sets that historically ship rich JSON-LD
# Product blocks. T0 = JSON-LD + spec tables.
_T0_ADAPTERS: frozenset[str] = frozenset(
    {
        "ind",
        "bimmerworld",
        "turnermotorsport",
        "ecstuning",
        "fcpeuro",
        "hondata",
        "ktuner",
        "studiorsr",
        "a90shop",
    }
)

# Adapters with semi-structured pages — microdata + partial spec markup.
_T1_ADAPTERS: frozenset[str] = frozenset(
    {
        "rallysportdirect",
        "subispeed",
        "iagperformance",
        "prlmotorsports",
        "z1motorsports",
        "awetuning",
        "apr",
        "ie",
        "034motorsport",
        "mackinindustries",
        "americanmuscle",
        "steeda",
        "texasspeed",
        "lingenfelter",
    }
)


def adapter_to_tier(adapter: Optional[str]) -> str:
    """Return the page-structure tier for an adapter name.

    - ``T0`` — rich JSON-LD + spec tables (BMW/Honda specialists, ECS/FCP).
    - ``T1`` — microdata or partial spec markup.
    - ``T2`` — prose-heavy listings (default for unmapped adapters per
      LABELING-RULES.md § Tier Assignment).
    """
    if not adapter:
        return "T2"
    if adapter in _T0_ADAPTERS:
        return "T0"
    if adapter in _T1_ADAPTERS:
        return "T1"
    return "T2"


# ---------------------------------------------------------------------------
# parts.json — locked schema load + write
# ---------------------------------------------------------------------------

REQUIRED_ROW_KEYS: tuple[str, ...] = (
    "part_id",
    "retailer",
    "category",
    "tier",
    "raw_name",
    "raw_description",
    "html_excerpt",
    "truth_car_triples",
    "truth_manufacturer",
    "truth_category",
    "truth_specifications",
    "labeled_at",
    "labeled_by",
)

VALID_LABELED_BY: frozenset[str] = frozenset({"human", "bootstrap-ground-truth"})
VALID_TIERS: frozenset[str] = frozenset({"T0", "T1", "T2"})


def load_gold_set(path: Path) -> list[dict[str, Any]]:
    """Load parts.json and validate every row's shape.

    Raises ``GoldSetLoadError`` on JSON parse failure, non-list root, or any
    row missing required keys / having wrong types. This is "fail loud at
    startup" per the task plan's negative-test contract — a malformed file
    must not silently degrade to an empty list (which would re-bootstrap on
    top of a partially-labeled file and overwrite human work).
    """
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GoldSetLoadError(f"could not read {path}: {exc}") from exc
    if not text.strip():
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GoldSetLoadError(
            f"{path} is not valid JSON: {exc.msg} at line {exc.lineno} col {exc.colno}"
        ) from exc
    if not isinstance(data, list):
        raise GoldSetLoadError(
            f"{path} root must be a JSON array, got {type(data).__name__}"
        )
    for idx, row in enumerate(data):
        _validate_row(row, where=f"{path}[{idx}]")
    return data


def _validate_row(row: Any, *, where: str) -> None:
    if not isinstance(row, dict):
        raise GoldSetLoadError(
            f"{where}: row must be a dict, got {type(row).__name__}"
        )
    missing = [k for k in REQUIRED_ROW_KEYS if k not in row]
    if missing:
        raise GoldSetLoadError(f"{where}: missing required key(s): {missing!r}")
    if not isinstance(row["part_id"], str) or not row["part_id"]:
        raise GoldSetLoadError(f"{where}: part_id must be a non-empty string")
    if row["tier"] not in VALID_TIERS:
        raise GoldSetLoadError(
            f"{where}: tier must be one of {sorted(VALID_TIERS)!r}, got {row['tier']!r}"
        )
    if row["labeled_by"] not in VALID_LABELED_BY:
        raise GoldSetLoadError(
            f"{where}: labeled_by must be one of {sorted(VALID_LABELED_BY)!r}, "
            f"got {row['labeled_by']!r}"
        )
    if not isinstance(row["truth_car_triples"], list):
        raise GoldSetLoadError(
            f"{where}: truth_car_triples must be a list, got "
            f"{type(row['truth_car_triples']).__name__}"
        )
    if not isinstance(row["truth_specifications"], dict):
        raise GoldSetLoadError(
            f"{where}: truth_specifications must be a dict, got "
            f"{type(row['truth_specifications']).__name__}"
        )


def _atomic_write_with_lock(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows to ``path`` under fcntl.flock(LOCK_EX).

    The lock is held on the destination file itself (or a freshly created
    handle when the file does not yet exist). Any concurrent run targeting
    the same path will block on ``flock`` until this write completes,
    eliminating partial-JSON races between an operator hand-labeling and the
    bootstrap runner.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open in r+ when the file exists, else w+. fcntl.flock requires an open fd.
    mode = "r+" if path.exists() else "w+"
    # Newline=os.linesep to keep cross-platform-stable JSON files.
    with open(path, mode, encoding="utf-8") as fp:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        except OSError as exc:  # pragma: no cover — flock failure is platform-specific
            logger.warning("could not acquire flock on %s: %s; writing without lock", path, exc)
        fp.seek(0)
        fp.truncate()
        json.dump(rows, fp, indent=2, sort_keys=True, ensure_ascii=False)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())


# ---------------------------------------------------------------------------
# Bootstrap — programmatic ground-truth from HTML
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_bootstrap_row(
    *,
    part_id: str,
    retailer: str,
    category: str,
    tier: str,
    raw_name: str,
    raw_description: str,
    html: str,
) -> dict[str, Any]:
    """Run truth_from_html on raw HTML and assemble a gold-set row."""
    # Lazy import so the module is loadable when app.* is unavailable
    # (e.g. tests that monkey-patch the truth helper).
    from scripts.m004_ground_truth import truth_from_html

    truth = truth_from_html(html, retailer=retailer)
    excerpt = html[:HTML_EXCERPT_BYTES]
    return {
        "part_id": part_id,
        "retailer": retailer,
        "category": category,
        "tier": tier,
        "raw_name": raw_name,
        "raw_description": raw_description,
        "html_excerpt": excerpt,
        "truth_car_triples": list(truth.get("car_triples", [])),
        "truth_manufacturer": truth.get("manufacturer"),
        "truth_category": truth.get("category"),
        "truth_specifications": dict(truth.get("specifications", {})),
        "labeled_at": _now_iso(),
        "labeled_by": "bootstrap-ground-truth",
    }


def _iterate_db_pages(target: int, log: logging.Logger) -> Iterable[dict[str, Any]]:
    """Yield page dicts from the live DB up to ``target`` rows.

    Returns an empty iterator (and logs the reason) when SQLAlchemy can't
    connect or the import path is unreachable. Caller falls back to fixtures.
    """
    try:
        from sqlalchemy.orm import selectinload  # type: ignore[import-not-found]

        from app.api.models.crawled_page import CrawledPage  # type: ignore[import-not-found]
        from app.api.models.part import Part  # type: ignore[import-not-found]
        from app.crawlers.archive_rescrape import load_archived_html  # type: ignore[import-not-found]
        from app.db.session import SessionLocal  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 — broad: any import failure should fall back
        log.info("db_path_unavailable", extra={"reason": "import_failed", "error": repr(exc)})
        return iter(())

    try:
        session = SessionLocal()
    except Exception as exc:  # noqa: BLE001
        log.info("db_path_unavailable", extra={"reason": "session_error", "error": repr(exc)})
        return iter(())

    def _gen() -> Iterable[dict[str, Any]]:
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
                    .yield_per(500)
                )
                pages = list(q.limit(target * 2))  # materialize early so any
                # query-time error (missing table, no DB) surfaces here, not
                # mid-iteration where the caller can't recover.
            except Exception as exc:  # noqa: BLE001
                log.info(
                    "db_path_unavailable",
                    extra={"reason": "query_failed", "error": repr(exc)},
                )
                return
            for page in pages:
                if emitted >= target:
                    break
                try:
                    html = load_archived_html(page, log)
                except Exception as exc:  # noqa: BLE001
                    log.info(
                        "skip_page_load_error",
                        extra={"page_id": str(page.id), "error": repr(exc)},
                    )
                    continue
                if not html:
                    log.info(
                        "skip_page_no_html",
                        extra={"page_id": str(page.id), "url": page.url},
                    )
                    continue
                part = page.part
                yield {
                    "part_id": str(part.id) if part else f"page-{page.id}",
                    "retailer": page.source or "unknown",
                    "category": (
                        part.category.name if part and part.category else "unknown"
                    ),
                    "tier": adapter_to_tier(page.source),
                    "raw_name": (part.name if part and part.name else "") or "",
                    "raw_description": (
                        part.description if part and part.description else ""
                    )
                    or "",
                    "html": html,
                }
                emitted += 1
        finally:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                pass

    return _gen()


def bootstrap_label(
    target: int,
    *,
    existing_part_ids: frozenset[str],
    log: logging.Logger,
) -> list[dict[str, Any]]:
    """Produce up to ``target`` bootstrap-labeled rows.

    Tries the DB iterator first; if it yields nothing (no DB reachable, or
    no parts with archived HTML), falls back to the inline fixtures. Skips
    any part_id already present in ``existing_part_ids`` (idempotent resume).
    """
    rows: list[dict[str, Any]] = []
    for page_dict in _iterate_db_pages(target, log):
        if page_dict["part_id"] in existing_part_ids:
            continue
        rows.append(_build_bootstrap_row(**page_dict))
        if len(rows) >= target:
            return rows

    if not rows:
        log.info("bootstrap_using_fixtures", extra={"target": target})
        # Lazy import keeps this file loadable when scripts/ isn't on path.
        from scripts.m004_bootstrap_fixtures import BOOTSTRAP_FIXTURES

        for fx in BOOTSTRAP_FIXTURES:
            if fx["part_id"] in existing_part_ids:
                continue
            rows.append(_build_bootstrap_row(**fx))
            if len(rows) >= target:
                break

    return rows


# ---------------------------------------------------------------------------
# Strata report
# ---------------------------------------------------------------------------


def write_strata_report(
    rows: list[dict[str, Any]],
    *,
    out_path: Path,
) -> None:
    """Write a per-(retailer × category × tier) coverage report.

    Counts are absolute; totals plus the bin breakdown let an operator see
    where the gold set is over- or under-represented relative to the
    corpus distribution.
    """
    bins: Counter[tuple[str, str, str]] = Counter()
    for r in rows:
        bins[(r["retailer"], r["category"], r["tier"])] += 1
    payload = {
        "total_rows": len(rows),
        "labeled_at": _now_iso(),
        "bins": [
            {"retailer": r, "category": c, "tier": t, "count": n}
            for (r, c, t), n in sorted(bins.items())
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m004_label_gold_set",
        description=(
            "M004 gold-set labeling tool. Bootstrap rows come from "
            "m004_ground_truth.truth_from_html; human rows are stubbed and "
            "documented in .gsd/milestones/M004/gold-set/LABELING-RULES.md."
        ),
    )
    p.add_argument(
        "--target-count",
        type=int,
        default=50,
        help="Target total row count (default 50). The interactive human pass uses this.",
    )
    p.add_argument(
        "--bootstrap",
        type=int,
        default=None,
        help=(
            "Auto-label up to N rows via m004_ground_truth (DB-first, "
            "fixture fallback). Required for auto-mode."
        ),
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Append to an existing parts.json without duplicating part_ids.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_GOLD_SET_PATH,
        help="Output gold-set parts.json path.",
    )
    p.add_argument(
        "--strata-out",
        type=Path,
        default=DEFAULT_STRATA_PATH,
        help="Write per-stratum coverage to this path.",
    )
    return p


def _run_interactive(args: argparse.Namespace) -> int:  # noqa: ARG001
    """Stub for the operator hand-labeling pass."""
    print(
        "Interactive labeling is operator-driven and not implemented in auto-mode. "
        "See .gsd/milestones/M004/gold-set/LABELING-RULES.md for the rule book; "
        "rerun with --bootstrap N to seed the gold set programmatically.",
        file=sys.stderr,
    )
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _build_parser().parse_args(argv)

    out_path: Path = args.out
    strata_path: Path = args.strata_out

    if args.resume or out_path.exists():
        try:
            existing = load_gold_set(out_path)
        except GoldSetLoadError:
            # Fail loud — surface the exact reason. Auto-mode operator can
            # delete or repair the file deliberately rather than have the
            # bootstrap silently overwrite a corrupted file.
            raise
    else:
        existing = []

    existing_ids: frozenset[str] = frozenset(r["part_id"] for r in existing)

    if args.bootstrap is None:
        return _run_interactive(args)

    new_rows = bootstrap_label(
        args.bootstrap,
        existing_part_ids=existing_ids,
        log=logger,
    )
    merged = existing + new_rows
    _atomic_write_with_lock(out_path, merged)
    write_strata_report(merged, out_path=strata_path)

    logger.info(
        "bootstrap_complete",
        extra={
            "added_rows": len(new_rows),
            "total_rows": len(merged),
            "out_path": str(out_path),
            "strata_path": str(strata_path),
        },
    )
    print(
        json.dumps(
            {
                "added_rows": len(new_rows),
                "total_rows": len(merged),
                "out_path": str(out_path),
                "strata_path": str(strata_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
