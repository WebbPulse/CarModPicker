"""M004 corpus-vote taxonomy audit rule + dry-run CSV writer.

Measurement-only module under ``backend/scripts/`` (per MEM212), NOT
``backend/app/``. Iterates the local Postgres corpus and emits per-canonical-row
decisions: ``rename``, ``alias``, or ``skip``, driven by a *mechanical*
corpus-vote rule with no editorial judgment.

Rule (mechanical, no human-in-the-loop)
---------------------------------------
For each ``CarGeneration`` row in the local DB:

* ``corpus_count(canonical_form)`` — number of parts whose inferred triples
  currently resolve to this canonical id (i.e. parts whose name/description
  contained the canonical generation_name as inferred by
  ``infer_car_generations``).
* ``corpus_count(challenger_form)`` — for the most-popular *non-canonical*
  generation_name observed in the corpus for parts linked to this canonical id.
  Challengers are grouped via case-insensitive equality on the inferred
  generation_name string.
* ``retailer_count(challenger_form)`` — number of distinct retailer source
  slugs (CrawledPage.source) that produced parts emitting the challenger.
* ``edit_distance(canonical, challenger)`` — Levenshtein distance over
  lower-cased forms.

Decision::

    rename  iff corpus_count(canonical) == 0
              AND corpus_count(challenger) >  N
              AND retailer_count(challenger) >  M
              AND edit_distance(canonical, challenger) >  T
    alias   iff there is a challenger but the rename gates fail
    skip    otherwise

Defaults: N=5 parts, M=2 retailers, T=2 edit distance. ``>`` is strict — at
the boundary the rule rounds *down* to ``alias``/``skip``.

Defensive contract
------------------
Every per-row metric call is wrapped in ``try/except Exception`` with a
structured ``audit_row_failed`` debug log carrying ``canonical_id`` plus the
exception class. One broken row never aborts the run (pattern from MEM206 /
``m004_ground_truth``). DB-unreachable / argparse / output-write failures
exit ``1``; rule-decision counts never affect the exit code (always ``0`` on
success regardless of how many renames or aliases were found).

Pure metric functions live at module scope — they take pre-aggregated counts
and strings, **not** a DB session — so unit tests can target them directly
without standing up Postgres.

CLI
---
Invoke as ``python -m scripts.m004_taxonomy_audit`` from inside ``backend/``
(per MEM209). ``--dry-run`` is the default and is non-mutating; the only file
this run writes is the dry-run CSV at the path given by ``--out``.
"""

from __future__ import annotations

import argparse
import ast
import csv
import glob
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger("m004_taxonomy_audit")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD_PARTS: int = 5
DEFAULT_THRESHOLD_RETAILERS: int = 2
DEFAULT_THRESHOLD_EDIT_DISTANCE: int = 2

# Default output path is relative to backend/ so MEM209 conventions hold.
DEFAULT_OUT_PATH: Path = Path("../.gsd/milestones/M004/taxonomy-audit-dryrun.csv")

# T04: applied-state output paths (relative to backend/ per MEM209).
DEFAULT_RENAMES_OUT_PATH: Path = Path("../.gsd/milestones/M004/taxonomy-renames.csv")
DEFAULT_ALIASES_OUT_PATH: Path = Path("../.gsd/milestones/M004/alias-additions.csv")

# T04: where the rename migrations and alias-marker live (relative to backend/).
DEFAULT_ALEMBIC_VERSIONS_DIR: Path = Path("alembic/versions")
DEFAULT_CAR_INFERENCE_PATH: Path = Path("app/core/car_inference.py")

# T03 marker that delimits the appended block in car_inference.py.
ALIAS_MARKER_PATTERN: re.Pattern[str] = re.compile(
    r"#\s*---\s*M004/S02\s+corpus-derived\s+additions",
    re.IGNORECASE,
)

CSV_HEADER: tuple[str, ...] = (
    "canonical_id",
    "canonical_form",
    "challenger_form",
    "corpus_count_canonical",
    "corpus_count_challenger",
    "retailer_count",
    "edit_distance",
    "decision",
)

# T04: applied-state CSV headers (locked by the slice-close verify command).
RENAMES_CSV_HEADER: tuple[str, ...] = (
    "migration_revision",
    "canonical_id",
    "old_generation_name",
    "new_generation_name",
    "corpus_count",
    "retailer_count",
    "edit_distance",
    "applied_at",
)

ALIASES_CSV_HEADER: tuple[str, ...] = (
    "phrase",
    "make",
    "model",
    "generation_name",
    "corpus_count",
    "derived_from_canonical_id",
    "applied_at",
)


# ---------------------------------------------------------------------------
# Pure metric functions (no DB args; unit-test friendly)
# ---------------------------------------------------------------------------


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance over lower-cased strings.

    Pure function — no I/O, no state. Inputs may be ``None``-typed at the
    callsite but this helper requires real strings; callers normalize first.
    """
    a = (a or "").lower()
    b = (b or "").lower()
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Two-row DP: O(len(a) * len(b)) time, O(min(len(a), len(b))) space.
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ch_a in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, ch_b in enumerate(b, start=1):
            cost = 0 if ch_a == ch_b else 1
            curr[j] = min(
                curr[j - 1] + 1,  # insertion
                prev[j] + 1,  # deletion
                prev[j - 1] + cost,  # substitution
            )
        prev = curr
    return prev[-1]


def corpus_count_canonical(canonical_count: int) -> int:
    """Identity-with-clamp wrapper so the rule reads as a metric call.

    Negative inputs (from defensive callers) are clamped to 0.
    """
    return max(0, int(canonical_count))


def corpus_count_challenger(challenger_count: int) -> int:
    """Identity-with-clamp wrapper for the challenger-form corpus count."""
    return max(0, int(challenger_count))


def retailer_count_challenger(retailers: Iterable[str]) -> int:
    """Distinct retailer count for a challenger form.

    Accepts any iterable of retailer source slugs and returns the count of
    distinct, non-empty entries (case-sensitive — CrawledPage.source values
    are already canonical adapter slugs).
    """
    seen: set[str] = set()
    for r in retailers:
        if r:
            seen.add(r)
    return len(seen)


# ---------------------------------------------------------------------------
# Decision rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Thresholds:
    """CLI-tunable rule thresholds. Strict ``>`` semantics (boundary => not-rename)."""

    parts: int = DEFAULT_THRESHOLD_PARTS
    retailers: int = DEFAULT_THRESHOLD_RETAILERS
    edit_distance: int = DEFAULT_THRESHOLD_EDIT_DISTANCE


def decide(
    *,
    canonical_form: str,
    challenger_form: Optional[str],
    canonical_count: int,
    challenger_count: int,
    retailer_count: int,
    edit_dist: int,
    thresholds: Thresholds,
) -> str:
    """Return one of ``"rename"``, ``"alias"``, ``"skip"``.

    Pure function. The rule:

    * ``rename`` — the corpus has clearly defected to a new spelling: zero
      corpus rows currently match the canonical form, the challenger crosses
      every threshold, AND the spelling is far enough off (edit_distance > T)
      that it's not a 1-character typo we should pin via alias instead.
    * ``alias`` — there IS a challenger from the corpus, but the rename gates
      fail (typo distance, single-retailer, low part count). Suitable for the
      CAR_ALIASES additive expansion.
    * ``skip`` — no challenger observed, or no signal worth acting on.
    """
    if not challenger_form:
        return "skip"

    is_rename = (
        canonical_count == 0
        and challenger_count > thresholds.parts
        and retailer_count > thresholds.retailers
        and edit_dist > thresholds.edit_distance
    )
    if is_rename:
        return "rename"
    return "alias"


# ---------------------------------------------------------------------------
# Per-canonical aggregation helpers
# ---------------------------------------------------------------------------


@dataclass
class CanonicalRow:
    """One row in the audit output: a canonical_id + best challenger summary."""

    canonical_id: str
    canonical_form: str
    canonical_count: int = 0
    # Per-challenger-form: count of parts + set of retailer slugs.
    challenger_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    challenger_retailers: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_canonical_hit(self) -> None:
        self.canonical_count += 1

    def add_challenger_hit(self, challenger_form: str, retailer: Optional[str]) -> None:
        key = challenger_form.lower().strip()
        if not key:
            return
        self.challenger_counts[key] += 1
        if retailer:
            self.challenger_retailers[key].add(retailer)

    def best_challenger(self) -> tuple[Optional[str], int, int]:
        """Return (challenger_form, parts_count, retailers_count) for the
        most-popular challenger, or ``(None, 0, 0)`` if no challenger seen.

        Tie-break: prefer higher parts count, then lexicographic challenger.
        """
        if not self.challenger_counts:
            return (None, 0, 0)
        best_form = max(
            self.challenger_counts.keys(),
            key=lambda k: (self.challenger_counts[k], -ord(k[0]) if k else 0),
        )
        return (
            best_form,
            self.challenger_counts[best_form],
            len(self.challenger_retailers.get(best_form, set())),
        )


# ---------------------------------------------------------------------------
# CSV / JSON output
# ---------------------------------------------------------------------------


def write_audit_csv(rows: Iterable[dict[str, Any]], out_path: Path) -> int:
    """Write the audit decisions to CSV and return the row count.

    Caller owns directory creation upstream; this helper raises on write
    failure so the CLI's outer ``try`` can map it to exit code 1.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(CSV_HEADER))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_HEADER})
            written += 1
    return written


def emit_json_envelope(payload: dict[str, Any]) -> None:
    """Emit one structured JSON line to stdout (used by --output-json)."""
    print(json.dumps(payload, sort_keys=True))


# ---------------------------------------------------------------------------
# T04: Applied-state walkers + CSV writers
# ---------------------------------------------------------------------------


# T02's emitter writes a deterministic audit-trail tuple in the migration
# docstring of the form:
#
#   (audit_revision, canonical_id, old_generation_name, new_generation_name,
#    corpus_count, retailer_count, edit_distance, decided_at)
#
# We parse it via ``ast.parse`` and pluck the first tuple literal in the
# module-level docstring. Order in the CSV is by ``decided_at`` ascending so
# the log is reproducible regardless of filename ordering on disk.
_RENAME_MIGRATION_GLOB: str = "*_m004_rename_*.py"


def _extract_audit_tuple_from_docstring(source_text: str) -> Optional[tuple[Any, ...]]:
    """Parse a migration source file and return the audit tuple from its
    module-level docstring, or ``None`` if not found / not parseable.

    The tuple shape is (audit_revision, canonical_id, old_generation_name,
    new_generation_name, corpus_count, retailer_count, edit_distance,
    decided_at). We accept ``ast.literal_eval`` on the entire docstring or
    on the first ``(...)`` substring inside it.
    """
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return None
    docstring = ast.get_docstring(tree, clean=False)
    if not docstring:
        return None
    # Find the first parenthesized literal tuple in the docstring.
    paren_match = re.search(r"\((?:[^()]|\([^()]*\))*\)", docstring, re.DOTALL)
    if not paren_match:
        return None
    candidate = paren_match.group(0)
    try:
        value = ast.literal_eval(candidate)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, tuple) or len(value) < 8:
        return None
    return value


def walk_rename_migrations(versions_dir: Path) -> list[dict[str, Any]]:
    """Enumerate ``*_m004_rename_*.py`` migrations under ``versions_dir`` and
    return one dict per migration shaped for ``taxonomy-renames.csv``.

    Deterministic ordering: by ``decided_at`` ascending (string compare on
    ISO-8601 UTC works correctly), with file-stem as a stable tiebreak so two
    renames stamped in the same second still order the same on every machine.
    Returns an empty list when no matching migrations exist.
    """
    out: list[dict[str, Any]] = []
    if not versions_dir.exists():
        return out
    paths = sorted(glob.glob(str(versions_dir / _RENAME_MIGRATION_GLOB)))
    parsed: list[tuple[str, str, dict[str, Any]]] = []
    for path_str in paths:
        path = Path(path_str)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "rename_migration_unreadable",
                extra={"path": str(path), "error_class": type(exc).__name__},
            )
            continue
        tup = _extract_audit_tuple_from_docstring(source)
        if tup is None:
            logger.warning(
                "rename_migration_missing_audit_tuple",
                extra={"path": str(path)},
            )
            continue
        (
            audit_revision,
            canonical_id,
            old_generation_name,
            new_generation_name,
            corpus_count,
            retailer_count,
            edit_dist,
            decided_at,
        ) = tup[:8]
        row = {
            "migration_revision": str(audit_revision),
            "canonical_id": str(canonical_id),
            "old_generation_name": str(old_generation_name),
            "new_generation_name": str(new_generation_name),
            "corpus_count": int(corpus_count),
            "retailer_count": int(retailer_count),
            "edit_distance": int(edit_dist),
            "applied_at": str(decided_at),
        }
        parsed.append((str(decided_at), path.stem, row))
    parsed.sort(key=lambda t: (t[0], t[1]))
    out = [row for _, _, row in parsed]
    return out


def _slice_alias_block(source_text: str) -> Optional[str]:
    """Return the substring of ``car_inference.py`` from just after the T03
    marker comment up to the closing ``]`` of ``CAR_ALIASES``.

    The CAR_ALIASES list is the only top-level list in scope; the T03 marker
    sits inside it. We slice from the line after the marker comment to the
    next standalone ``]`` line (start of line, optional trailing whitespace).
    """
    marker_match = ALIAS_MARKER_PATTERN.search(source_text)
    if not marker_match:
        return None
    # Move the cursor to the end of the marker line.
    line_end = source_text.find("\n", marker_match.end())
    if line_end == -1:
        return None
    tail = source_text[line_end + 1 :]
    # Find the closing ``]`` that ends CAR_ALIASES — first standalone-on-its-line bracket.
    close_match = re.search(r"^\s*\]\s*$", tail, re.MULTILINE)
    if not close_match:
        return None
    return tail[: close_match.start()]


def walk_alias_additions(
    car_inference_path: Path,
    *,
    dryrun_csv_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Parse the appended CAR_ALIASES block from ``car_inference_path`` and
    return one dict per alias tuple shaped for ``alias-additions.csv``.

    Each tuple in CAR_ALIASES is ``(phrase, make, model, generation_name)``.
    The marker block may be empty (the M004/S02 zero-state outcome) — in that
    case this function returns an empty list.

    ``dryrun_csv_path`` is the T01 CSV; if provided, we use it to pair each
    landed alias to its source canonical_id + corpus_count via the
    ``challenger_form`` column. When unavailable we leave those columns blank.
    """
    out: list[dict[str, Any]] = []
    if not car_inference_path.exists():
        return out
    try:
        source = car_inference_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "car_inference_unreadable",
            extra={"path": str(car_inference_path), "error_class": type(exc).__name__},
        )
        return out
    block = _slice_alias_block(source)
    if not block:
        return out

    # Optionally build the alias-form -> (canonical_id, corpus_count) map from
    # the dry-run CSV. Match on lowercased challenger_form.
    challenger_index: dict[str, tuple[str, int]] = {}
    if dryrun_csv_path is not None and dryrun_csv_path.exists():
        try:
            with dryrun_csv_path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    challenger = (row.get("challenger_form") or "").strip().lower()
                    if not challenger:
                        continue
                    try:
                        cnt = int(row.get("corpus_count_challenger") or 0)
                    except ValueError:
                        cnt = 0
                    challenger_index[challenger] = (
                        row.get("canonical_id") or "",
                        cnt,
                    )
        except OSError as exc:
            logger.warning(
                "dryrun_csv_unreadable",
                extra={"path": str(dryrun_csv_path), "error_class": type(exc).__name__},
            )

    applied_at = datetime.now(timezone.utc).isoformat()
    for raw_line in block.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Trim a trailing comma so ast.literal_eval accepts the lone tuple.
        candidate = stripped.rstrip(",")
        try:
            value = ast.literal_eval(candidate)
        except (SyntaxError, ValueError):
            logger.debug(
                "alias_block_unparseable_line",
                extra={"line": stripped[:120]},
            )
            continue
        if not isinstance(value, tuple) or len(value) != 4:
            continue
        phrase, make, model, generation_name = value
        if not all(isinstance(x, str) for x in (phrase, make, model, generation_name)):
            continue
        canonical_id, corpus_count = challenger_index.get(phrase.lower(), ("", 0))
        out.append(
            {
                "phrase": phrase,
                "make": make,
                "model": model,
                "generation_name": generation_name,
                "corpus_count": corpus_count,
                "derived_from_canonical_id": canonical_id,
                "applied_at": applied_at,
            }
        )
    return out


def _write_csv_with_optional_zero_state_comment(
    rows: list[dict[str, Any]],
    out_path: Path,
    header: tuple[str, ...],
    *,
    zero_state_message: str,
) -> int:
    """Generic CSV writer for the two T04 logs.

    Writes header row, then either data rows (one per dict) or — when the row
    list is empty — a single comment row that documents the zero-state slice
    outcome. Returns the count of *data* rows written (zero-state still
    returns 0).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(header))
        writer.writeheader()
        if not rows:
            # csv-style comment: place the marker in the first column. The
            # remaining columns stay blank. Loud + parseable by csv readers.
            comment_row = {h: "" for h in header}
            comment_row[header[0]] = f"# {zero_state_message}"
            writer.writerow(comment_row)
            return 0
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in header})
    return len(rows)


def write_renames_csv(rows: list[dict[str, Any]], out_path: Path) -> int:
    """Write the taxonomy-renames.csv applied-state log."""
    return _write_csv_with_optional_zero_state_comment(
        rows,
        out_path,
        RENAMES_CSV_HEADER,
        zero_state_message=(
            "M004/S02 zero-state outcome: corpus-vote audit emitted zero rename "
            "decisions; no Alembic m004_rename_* migrations were authored."
        ),
    )


def write_aliases_csv(rows: list[dict[str, Any]], out_path: Path) -> int:
    """Write the alias-additions.csv applied-state log."""
    return _write_csv_with_optional_zero_state_comment(
        rows,
        out_path,
        ALIASES_CSV_HEADER,
        zero_state_message=(
            "M004/S02 zero-state outcome: corpus-vote audit emitted zero alias "
            "decisions; no new tuples appended to CAR_ALIASES under the T03 marker."
        ),
    )


def emit_applied_state_logs(
    *,
    versions_dir: Path,
    car_inference_path: Path,
    dryrun_csv_path: Optional[Path],
    renames_out: Path,
    aliases_out: Path,
) -> dict[str, Any]:
    """Walk renames + aliases, write both CSVs, and return a summary dict.

    Pure orchestration; raises on write failure so the CLI maps to exit 1.
    """
    rename_rows = walk_rename_migrations(versions_dir)
    alias_rows = walk_alias_additions(
        car_inference_path,
        dryrun_csv_path=dryrun_csv_path,
    )
    renames_written = write_renames_csv(rename_rows, renames_out)
    aliases_written = write_aliases_csv(alias_rows, aliases_out)
    return {
        "renames": renames_written,
        "aliases": aliases_written,
        "renames_path": str(renames_out),
        "aliases_path": str(aliases_out),
        "applied_state": True,
    }


# ---------------------------------------------------------------------------
# Driver — DB iteration + per-canonical aggregation
# ---------------------------------------------------------------------------


def _safe_extract_challenger(
    *,
    canonical_form: str,
    part_name: str,
    part_description: str,
    part_url: Optional[str],
) -> Optional[str]:
    """Re-run live inference against the part text, return the inferred
    generation_name string IF it differs (case-insensitively) from the
    canonical form.

    Returns ``None`` when:

    * inference yielded no triple,
    * the inferred generation_name matches the canonical form (no challenger),
    * the inference call raised — caller logs ``audit_row_failed`` and
      continues.

    The import of ``infer_car_generations`` is inside the function so the
    module is importable even when ``app`` is not on ``sys.path`` (e.g. a
    pure unit test that targets only ``decide`` / ``edit_distance``).
    """
    from app.core.car_inference import infer_car_generations  # local import

    triples = infer_car_generations(part_name or "", part_description or "", part_url)
    canonical_lc = (canonical_form or "").lower().strip()
    for triple in triples or []:
        if not isinstance(triple, (tuple, list)) or len(triple) != 3:
            continue
        _make, _model, generation_name = triple
        if not isinstance(generation_name, str):
            continue
        if generation_name.lower().strip() != canonical_lc:
            return generation_name
    return None


def iterate_corpus_audit(
    db,
    *,
    limit: Optional[int],
    output_json: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Iterate ``CrawledPage`` rows and aggregate canonical/challenger counts.

    Returns ``(rows, summary_counts)`` where ``rows`` is the list of CSV-shaped
    decision dicts and ``summary_counts`` carries
    ``{candidates_inspected, renames, aliases, skipped}``.
    """
    # Local imports — module is importable in pure unit tests without app/.
    from sqlalchemy.exc import OperationalError, ProgrammingError

    from app.api.dependencies.repositories import get_repositories
    from app.api.models.crawled_page import CrawledPage
    from app.db.dynamo.catalog import Part

    repos = get_repositories()
    canonical_index: dict[str, CanonicalRow] = {}
    iterated = 0
    failed_rows = 0

    q = db.query(CrawledPage).filter(CrawledPage.part_id.is_not(None)).order_by(CrawledPage.source, CrawledPage.id)
    if limit:
        q = q.limit(limit)

    # SQLAlchemy defers SQL execution until first iteration. Wrap the next()
    # so a missing-table OperationalError (e.g. SQLite fallback in dev when
    # Postgres isn't up — MEM136) degrades to "empty corpus" rather than
    # aborting the run. Real connection failures surface earlier at
    # SessionLocal() and exit 1 from main(). Per the spec: "zero corpus rows
    # → exit 0 with empty CSV".
    empty_summary = {
        "candidates_inspected": 0,
        "renames": 0,
        "aliases": 0,
        "skipped": 0,
    }
    try:
        page_iter = iter(q.yield_per(500))
    except (OperationalError, ProgrammingError) as exc:
        logger.warning(
            "audit_corpus_table_missing",
            extra={"error_class": type(exc).__name__},
        )
        return [], dict(empty_summary)

    while True:
        try:
            page = next(page_iter)
        except StopIteration:
            break
        except (OperationalError, ProgrammingError) as exc:
            logger.warning(
                "audit_corpus_table_missing",
                extra={"error_class": type(exc).__name__},
            )
            return [], dict(empty_summary)
        iterated += 1
        try:
            part: Optional[Part] = repos.parts.get(str(page.part_id))
            if part is None:
                continue
            for cg in repos.car_generations.get_many(part.car_ids).values():
                cg_id = str(cg.id)
                canonical_form = cg.generation_name or ""
                row = canonical_index.setdefault(
                    cg_id,
                    CanonicalRow(canonical_id=cg_id, canonical_form=canonical_form),
                )
                # Did this part's text re-infer to the canonical form?
                challenger = _safe_extract_challenger(
                    canonical_form=canonical_form,
                    part_name=part.name or "",
                    part_description=part.description or "",
                    part_url=None,
                )
                if challenger is None:
                    row.add_canonical_hit()
                else:
                    row.add_challenger_hit(challenger, page.source)
        except Exception as exc:  # noqa: BLE001 — defensive (MEM206 pattern)
            failed_rows += 1
            logger.debug(
                "audit_row_failed",
                extra={
                    "canonical_id": getattr(page, "part_id", "?"),
                    "error_class": type(exc).__name__,
                },
            )
            continue

    rows: list[dict[str, Any]] = []
    summary = {"candidates_inspected": 0, "renames": 0, "aliases": 0, "skipped": 0}

    for canon_id, canon in canonical_index.items():
        challenger_form, challenger_count, retailer_n = canon.best_challenger()
        edit_dist = edit_distance(canon.canonical_form, challenger_form or "") if challenger_form else 0
        # Use module-level Thresholds default; CLI overrides happen in main().
        # We re-call decide() with the configured thresholds at the call site —
        # but inside this driver we use the defaults to keep the function
        # signature simple. The CLI re-decides per-row before writing.
        decision = decide(
            canonical_form=canon.canonical_form,
            challenger_form=challenger_form,
            canonical_count=canon.canonical_count,
            challenger_count=challenger_count,
            retailer_count=retailer_n,
            edit_dist=edit_dist,
            thresholds=Thresholds(),
        )
        row = {
            "canonical_id": canon_id,
            "canonical_form": canon.canonical_form,
            "challenger_form": challenger_form or "",
            "corpus_count_canonical": canon.canonical_count,
            "corpus_count_challenger": challenger_count,
            "retailer_count": retailer_n,
            "edit_distance": edit_dist,
            "decision": decision,
        }
        rows.append(row)
        summary["candidates_inspected"] += 1
        summary[{"rename": "renames", "alias": "aliases", "skip": "skipped"}[decision]] += 1
        if output_json:
            emit_json_envelope(row)

    if failed_rows:
        logger.info(
            "audit_failed_row_summary",
            extra={"failed_rows": failed_rows, "iterated": iterated},
        )

    return rows, summary


def apply_thresholds(rows: Iterable[dict[str, Any]], thresholds: Thresholds) -> list[dict[str, Any]]:
    """Re-run ``decide`` for each pre-built row under operator-tuned
    thresholds. Returns a new list with updated ``decision`` values.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        decision = decide(
            canonical_form=row["canonical_form"],
            challenger_form=row["challenger_form"] or None,
            canonical_count=int(row["corpus_count_canonical"]),
            challenger_count=int(row["corpus_count_challenger"]),
            retailer_count=int(row["retailer_count"]),
            edit_dist=int(row["edit_distance"]),
            thresholds=thresholds,
        )
        out.append({**row, "decision": decision})
    return out


def recompute_summary(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    summary = {"candidates_inspected": 0, "renames": 0, "aliases": 0, "skipped": 0}
    for row in rows:
        summary["candidates_inspected"] += 1
        key = {"rename": "renames", "alias": "aliases", "skip": "skipped"}.get(row.get("decision", "skip"), "skipped")
        summary[key] += 1
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m004_taxonomy_audit",
        description=(
            "M004 corpus-vote taxonomy audit (MEM212 measurement-only tool). "
            "Iterates the local Postgres corpus, applies a mechanical rename / "
            "alias / skip rule, and writes a dry-run CSV. Does NOT mutate any "
            "DB row, JSON seed, or Alembic version — operator review of the "
            "CSV is the gate before T02 emits real migrations."
        ),
    )
    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "(default mode) write the proposed-state audit CSV but mutate "
            "nothing. Selected automatically when --audit-applied-state is "
            "absent."
        ),
    )
    mode_group.add_argument(
        "--audit-applied-state",
        action="store_true",
        default=False,
        help=(
            "T04: emit the FINAL committed state by walking emitted Alembic "
            "rename migrations and the appended CAR_ALIASES marker block. "
            "Writes taxonomy-renames.csv + alias-additions.csv under "
            "../.gsd/milestones/M004/."
        ),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help="Output CSV path (default: ../.gsd/milestones/M004/taxonomy-audit-dryrun.csv)",
    )
    p.add_argument(
        "--renames-out",
        type=Path,
        default=DEFAULT_RENAMES_OUT_PATH,
        help=(
            "T04 applied-state output: taxonomy-renames.csv " "(default: ../.gsd/milestones/M004/taxonomy-renames.csv)"
        ),
    )
    p.add_argument(
        "--aliases-out",
        type=Path,
        default=DEFAULT_ALIASES_OUT_PATH,
        help=(
            "T04 applied-state output: alias-additions.csv " "(default: ../.gsd/milestones/M004/alias-additions.csv)"
        ),
    )
    p.add_argument(
        "--alembic-versions-dir",
        type=Path,
        default=DEFAULT_ALEMBIC_VERSIONS_DIR,
        help=("T04: directory containing Alembic version files " "(default: alembic/versions)"),
    )
    p.add_argument(
        "--car-inference-path",
        type=Path,
        default=DEFAULT_CAR_INFERENCE_PATH,
        help=(
            "T04: path to car_inference.py for parsing the appended "
            "CAR_ALIASES block (default: app/core/car_inference.py)"
        ),
    )
    p.add_argument(
        "--threshold-parts",
        type=int,
        default=DEFAULT_THRESHOLD_PARTS,
        help=f"Min parts for rename gate (default: {DEFAULT_THRESHOLD_PARTS}, strict >).",
    )
    p.add_argument(
        "--threshold-retailers",
        type=int,
        default=DEFAULT_THRESHOLD_RETAILERS,
        help=f"Min retailers for rename gate (default: {DEFAULT_THRESHOLD_RETAILERS}, strict >).",
    )
    p.add_argument(
        "--threshold-edit-distance",
        type=int,
        default=DEFAULT_THRESHOLD_EDIT_DISTANCE,
        help=f"Min edit distance for rename gate (default: {DEFAULT_THRESHOLD_EDIT_DISTANCE}, strict >).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap CrawledPage rows iterated (debugging).",
    )
    p.add_argument(
        "--output-json",
        action="store_true",
        default=False,
        help="Emit one JSON envelope per decision to stdout (machine-readable).",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # T04 applied-state branch: no DB iteration. Walk the committed migrations
    # and the appended CAR_ALIASES block, write the two final logs.
    if getattr(args, "audit_applied_state", False):
        try:
            summary = emit_applied_state_logs(
                versions_dir=args.alembic_versions_dir,
                car_inference_path=args.car_inference_path,
                dryrun_csv_path=args.out if args.out and Path(args.out).exists() else None,
                renames_out=args.renames_out,
                aliases_out=args.aliases_out,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "applied_state_emit_failed",
                extra={"error_class": type(exc).__name__},
            )
            print(
                json.dumps({"error": "applied_state_emit_failed", "detail": repr(exc)}),
                file=sys.stderr,
            )
            return 1
        emit_json_envelope(summary)
        return 0

    thresholds = Thresholds(
        parts=args.threshold_parts,
        retailers=args.threshold_retailers,
        edit_distance=args.threshold_edit_distance,
    )

    # DB connect — exit 1 on unreachable.
    try:
        from app.db.session import SessionLocal  # local import; respects TESTING env
    except Exception as exc:  # noqa: BLE001
        logger.error("db_unreachable", extra={"error_class": type(exc).__name__})
        print(json.dumps({"error": "db_unreachable", "detail": repr(exc)}), file=sys.stderr)
        return 1

    db = None
    try:
        db = SessionLocal()
    except Exception as exc:  # noqa: BLE001
        logger.error("db_unreachable", extra={"error_class": type(exc).__name__})
        print(json.dumps({"error": "db_unreachable", "detail": repr(exc)}), file=sys.stderr)
        return 1

    try:
        rows, _summary_default = iterate_corpus_audit(
            db,
            limit=args.limit,
            output_json=args.output_json,
        )
    except Exception as exc:  # noqa: BLE001 — DB query/connection can blow up after open()
        logger.error("db_query_failed", extra={"error_class": type(exc).__name__})
        print(json.dumps({"error": "db_unreachable", "detail": repr(exc)}), file=sys.stderr)
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass
        return 1
    finally:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass

    # Re-decide with operator-tuned thresholds.
    rows = apply_thresholds(rows, thresholds)
    summary = recompute_summary(rows)

    # Write CSV (exit 1 on write failure).
    try:
        write_audit_csv(rows, args.out)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "output_write_failed",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps({"error": "output_write_failed", "out_path": str(args.out), "detail": repr(exc)}),
            file=sys.stderr,
        )
        return 1

    final_summary = {
        **summary,
        "dry_run": True,
        "output_path": str(args.out),
    }
    emit_json_envelope(final_summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
