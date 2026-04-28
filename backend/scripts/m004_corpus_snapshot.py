"""M004 corpus-snapshot CLI: milestone-wide reference baseline producer.

Measurement-only module under ``backend/scripts/`` (per MEM212), NOT
``backend/app/``. Iterates the live ``crawled_pages → part`` corpus and counts,
for each of four signals, how many parts have non-null inference state. Output
is a structured JSON file at ``.gsd/milestones/M004/s04-corpus-delta.json``
plus one stdout JSON envelope per invocation. The script is the milestone-wide
reference-baseline producer that S05/S06/S07 will also consume per
M004-DOD.md "Post-S03 Directional DoD".

Four signals (per M004-DOD.md schema)
-------------------------------------
* ``car_non_null`` — count of parts whose ``car_generations`` relationship has
  at least one row (i.e. ``len(part.car_generations) > 0``).
* ``manufacturer_non_null`` — count of parts where ``part_manufacturer_id`` is
  not None.
* ``spec_any_field_non_null`` — count of parts where ``specifications`` is a
  dict containing at least one key whose value is not None. Per MEM044, the
  ``Part.specifications`` column is JSON without ``none_as_null=True``, so on
  the SQL side we observe three "empty" shapes: SQL NULL, JSON ``'null'``, and
  JSON ``'{}'``. Once SQLAlchemy hands us a Python value, the literal JSON
  ``'null'`` deserializes to Python ``None``; thus a Python-side "non-empty"
  check is ``isinstance(specs, dict) and any(v is not None for v in specs.values())``.
* ``spec_all_universal_fields_non_null`` — count of parts whose
  ``specifications`` dict contains every name in
  ``app.crawlers.parsing._UNIVERSAL_FIELD_NAMES`` (``weight_grams``,
  ``material``, ``finish``, ``warranty_days``, ``fitment_notes``) with a
  non-None value. Missing key OR ``None`` value fails this signal.

CLI
---
Invoke as ``python -m scripts.m004_corpus_snapshot --phase {pre_s04|post_s04}``
from inside ``backend/`` (per MEM209). Output JSON path defaults to
``../.gsd/milestones/M004/s04-corpus-delta.json``.

Exit codes
~~~~~~~~~~
* ``0`` — success (including the MEM216 zero-corpus / missing-table degraded
  branch).
* ``1`` — DB-unreachable at ``SessionLocal()``, argparse failure, JSON-write
  failure, or — only on ``--phase post_s04`` — a fail DoD verdict.

Defensive contract (MEM216 verbatim)
------------------------------------
Per-row iteration is wrapped in ``try/except (OperationalError,
ProgrammingError)`` and degrades to ``corpus_total: 0, zero_corpus: true,
exit 0``. Real DB-unreachable from ``SessionLocal()`` construction still
exits 1 from main().
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger("m004_corpus_snapshot")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default output paths are relative to backend/ so MEM209 conventions hold.
# S04 (closed milestone-wide reference baseline) writes to s04-corpus-delta.json;
# S05 (per-universal-field DoD) writes to a separate s05-corpus-delta.json so
# the S04 file remains byte-stable as the milestone-wide reference baseline.
DEFAULT_OUT_PATH: Path = Path("../.gsd/milestones/M004/s04-corpus-delta.json")
DEFAULT_OUT_PATH_S05: Path = Path("../.gsd/milestones/M004/s05-corpus-delta.json")
# S06 (per-universal-field expansion + new category-spec model) writes to a
# separate s06-corpus-delta.json so the S04/S05 files remain byte-stable per
# MEM242 byte-stability principle. T03 lands `manufacturer_part_number` and
# extends UNIVERSAL_FIELD_NAMES + PerFieldCounts; at this task close the
# per-field block still keys on the S05 five-field tuple.
DEFAULT_OUT_PATH_S06: Path = Path("../.gsd/milestones/M004/s06-corpus-delta.json")

# The six universal field names mirrored from
# ``app.crawlers.parsing._UNIVERSAL_FIELD_NAMES`` (extended in M004/S06 T03
# with ``manufacturer_part_number``). Duplicated as a constant here so the
# snapshot module remains importable in pure unit tests that do not stand up
# the full ``app.crawlers`` import chain (MEM008).
UNIVERSAL_FIELD_NAMES: tuple[str, ...] = (
    "weight_grams",
    "material",
    "finish",
    "warranty_days",
    "fitment_notes",
    "manufacturer_part_number",
)

VALID_PHASES: tuple[str, ...] = (
    "pre_s04",
    "post_s04",
    "pre_s05",
    "post_s05",
    "pre_s06",
    "post_s06",
)

# DoD verdict thresholds (per M004-DOD.md "Post-S03 Directional DoD").
# A drop > 1.0% absolute on any signal triggers fail.
DOD_DROP_TOLERANCE_PCT: float = -1.0


# ---------------------------------------------------------------------------
# Counting types
# ---------------------------------------------------------------------------


@dataclass
class SignalCounts:
    """The four signal counts produced for one phase of the snapshot."""

    car_non_null: int = 0
    manufacturer_non_null: int = 0
    spec_any_field_non_null: int = 0
    spec_all_universal_fields_non_null: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class PerFieldCounts:
    """Per-universal-field non-null counts produced for S05 phases.

    One int per name in ``UNIVERSAL_FIELD_NAMES``. None-vs-missing-vs-present
    semantics match ``specs_all_universal_fields_non_null`` (MEM044 — JSON
    'null' deserializes to Python None; both null AND missing key fail the
    count).
    """

    weight_grams: int = 0
    material: int = 0
    finish: int = 0
    warranty_days: int = 0
    fitment_notes: int = 0
    manufacturer_part_number: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def empty_per_field_counts_dict() -> dict[str, int]:
    """Return a fresh zero-filled per-field counts dict keyed on ``UNIVERSAL_FIELD_NAMES``."""
    return {name: 0 for name in UNIVERSAL_FIELD_NAMES}


# ---------------------------------------------------------------------------
# Pure counting helpers (no DB, unit-test friendly)
# ---------------------------------------------------------------------------


def part_has_car(part: Any) -> bool:
    """Return True iff the part has at least one associated car generation.

    Defensive against missing relationship attribute / non-iterable values.
    """
    cgs = getattr(part, "car_generations", None) or []
    try:
        return len(cgs) > 0
    except TypeError:
        return False


def part_has_manufacturer(part: Any) -> bool:
    """Return True iff ``part.part_manufacturer_id`` is set (non-None)."""
    return getattr(part, "part_manufacturer_id", None) is not None


def specs_any_field_non_null(specs: Any) -> bool:
    """Return True iff ``specs`` is a dict with at least one non-None value.

    Per MEM044, ``Part.specifications`` lacks ``none_as_null=True``; SQL NULL,
    JSON ``'null'``, and JSON ``'{}'`` must all be treated as empty. By the
    time SQLAlchemy hands us a value, the JSON ``'null'`` string has already
    deserialized to Python ``None``, so non-dict / empty-dict / dict-with-only-
    None values all return False here.
    """
    if not isinstance(specs, dict):
        return False
    for value in specs.values():
        if value is not None:
            return True
    return False


def specs_all_universal_fields_non_null(
    specs: Any,
    *,
    field_names: Iterable[str] = UNIVERSAL_FIELD_NAMES,
) -> bool:
    """Return True iff ``specs`` contains every universal field key with a
    non-None value. Missing key OR None value fails this signal.
    """
    if not isinstance(specs, dict):
        return False
    for name in field_names:
        if name not in specs:
            return False
        if specs[name] is None:
            return False
    return True


def count_signals_for_part(part: Any, counts: SignalCounts) -> None:
    """Mutate ``counts`` in-place with this part's contributions."""
    if part_has_car(part):
        counts.car_non_null += 1
    if part_has_manufacturer(part):
        counts.manufacturer_non_null += 1
    specs = getattr(part, "specifications", None)
    if specs_any_field_non_null(specs):
        counts.spec_any_field_non_null += 1
    if specs_all_universal_fields_non_null(specs):
        counts.spec_all_universal_fields_non_null += 1


def count_per_field_for_part(part: Any, per_field_counts: dict[str, int]) -> None:
    """Mutate ``per_field_counts`` in-place with this part's per-field contributions.

    For each name in ``UNIVERSAL_FIELD_NAMES``: increment the corresponding
    counter iff ``specs`` is a dict AND the key is present AND its value is
    not None. Missing key OR None value yields no increment (mirrors
    MEM044 + ``specs_all_universal_fields_non_null`` semantics).
    """
    specs = getattr(part, "specifications", None)
    if not isinstance(specs, dict):
        return
    for name in UNIVERSAL_FIELD_NAMES:
        if specs.get(name) is not None:
            per_field_counts[name] = per_field_counts.get(name, 0) + 1


# ---------------------------------------------------------------------------
# DoD verdict
# ---------------------------------------------------------------------------


def compute_delta_pct(pre: dict[str, int], post: dict[str, int]) -> dict[str, float]:
    """Compute per-signal percent deltas: ``(post - pre) / max(pre, 1) * 100``.

    ``pre`` and ``post`` carry the four-signal counts. The returned dict uses
    the short keys documented in M004-DOD.md (``car``, ``manufacturer``,
    ``spec_any_field``, ``spec_all_universal_fields``).
    """
    return {
        "car": _signed_pct(pre["car_non_null"], post["car_non_null"]),
        "manufacturer": _signed_pct(pre["manufacturer_non_null"], post["manufacturer_non_null"]),
        "spec_any_field": _signed_pct(pre["spec_any_field_non_null"], post["spec_any_field_non_null"]),
        "spec_all_universal_fields": _signed_pct(
            pre["spec_all_universal_fields_non_null"],
            post["spec_all_universal_fields_non_null"],
        ),
    }


def _signed_pct(pre_count: int, post_count: int) -> float:
    denominator = max(int(pre_count), 1)
    return round((int(post_count) - int(pre_count)) / denominator * 100.0, 4)


def evaluate_dod_verdict(
    *,
    delta_pct: dict[str, float],
    zero_corpus: bool,
    pre_counts: dict[str, int],
    post_counts: dict[str, int],
) -> tuple[str, list[str]]:
    """Return (verdict, regressions_list).

    Verdict values:
      * ``zero_corpus_pass`` — corpus_total is zero on both sides AND every
        count is zero (mirrors MEM221 zero-state success branch).
      * ``pass`` — ``delta_pct.car >= 0`` AND every other signal drop is
        within 1% absolute (>= -1.0).
      * ``fail`` — any signal dropped below -1.0 OR ``delta_pct.car < 0``.

    Regressions list contains the signal keys that violated their gate; empty
    on pass / zero_corpus_pass.
    """
    if zero_corpus and all(v == 0 for v in pre_counts.values()) and all(v == 0 for v in post_counts.values()):
        return ("zero_corpus_pass", [])

    regressions: list[str] = []
    if delta_pct["car"] < 0:
        regressions.append("car")
    for key in ("manufacturer", "spec_any_field", "spec_all_universal_fields"):
        if delta_pct[key] < DOD_DROP_TOLERANCE_PCT:
            regressions.append(key)
    if regressions:
        return ("fail", regressions)
    return ("pass", [])


def compute_per_field_delta_pct(
    pre: dict[str, int], post: dict[str, int]
) -> dict[str, float]:
    """Per-universal-field percent deltas using the same formula as
    ``compute_delta_pct``: ``(post - pre) / max(pre, 1) * 100``, rounded
    to 4 decimals. Keys are the literal universal-field names.
    """
    return {
        name: _signed_pct(int(pre.get(name, 0)), int(post.get(name, 0)))
        for name in UNIVERSAL_FIELD_NAMES
    }


def evaluate_s05_dod_verdict(
    *,
    delta_pct: dict[str, float],
    per_field_delta_pct: dict[str, float],
    zero_corpus: bool,
    pre_counts: dict[str, int],
    post_counts: dict[str, int],
    pre_per_field: dict[str, int],
    post_per_field: dict[str, int],
) -> tuple[str, list[str]]:
    """S05 DoD verdict (per-universal-field directional + cross-signal guard).

    Per M004-DOD.md "Post-S03 Directional DoD" S05 row + slice plan:
      * ``zero_corpus_pass`` — ``zero_corpus`` is True AND every count in
        ``pre_counts``, ``post_counts``, ``pre_per_field``, and
        ``post_per_field`` is zero (mirrors MEM221).
      * ``pass`` — at least one entry in ``per_field_delta_pct`` is strictly
        > 0 AND no entry in ``delta_pct`` is < ``DOD_DROP_TOLERANCE_PCT``
        AND no entry in ``per_field_delta_pct`` is < ``DOD_DROP_TOLERANCE_PCT``.
      * ``fail`` — any drop below ``DOD_DROP_TOLERANCE_PCT`` on any aggregate
        or per-field signal, OR no per-field delta is strictly positive in a
        non-zero corpus.

    Regressions list names each signal/field that violated its gate; the
    sentinel ``"no_per_field_increase"`` appears when no per-field count
    increased in a non-zero corpus.
    """
    all_zero = (
        zero_corpus
        and all(v == 0 for v in pre_counts.values())
        and all(v == 0 for v in post_counts.values())
        and all(v == 0 for v in pre_per_field.values())
        and all(v == 0 for v in post_per_field.values())
    )
    if all_zero:
        return ("zero_corpus_pass", [])

    regressions: list[str] = []
    for key in ("car", "manufacturer", "spec_any_field", "spec_all_universal_fields"):
        if delta_pct.get(key, 0.0) < DOD_DROP_TOLERANCE_PCT:
            regressions.append(key)
    for name in UNIVERSAL_FIELD_NAMES:
        if per_field_delta_pct.get(name, 0.0) < DOD_DROP_TOLERANCE_PCT:
            regressions.append(name)

    has_positive_per_field = any(
        per_field_delta_pct.get(name, 0.0) > 0.0 for name in UNIVERSAL_FIELD_NAMES
    )
    if not has_positive_per_field:
        regressions.append("no_per_field_increase")

    if regressions:
        return ("fail", regressions)
    return ("pass", [])


# ---------------------------------------------------------------------------
# DB iteration
# ---------------------------------------------------------------------------


def iterate_corpus_snapshot(
    db,
    *,
    limit: Optional[int],
) -> tuple[SignalCounts, dict[str, int], int, bool]:
    """Iterate ``crawled_pages → part`` rows and return
    ``(counts, per_field_counts, total, zero_corpus)``.

    The per-field counts dict is keyed on ``UNIVERSAL_FIELD_NAMES`` and is
    populated in the same single iteration as the four-signal aggregate
    counts (no extra DB cost — research note: shared resource).

    On ``OperationalError`` / ``ProgrammingError`` at the iterator boundary
    (MEM216 — SQLite fallback, missing crawled_pages table), degrade to
    ``(SignalCounts(), empty_per_field_counts_dict(), 0, True)``. Real
    DB-unreachable failures surface from ``SessionLocal()`` construction in
    ``main()`` and exit 1.
    """
    # Local imports keep this module importable in pure unit tests that do not
    # have ``app/`` on ``sys.path`` (e.g. tests that call only the helpers).
    from sqlalchemy.exc import OperationalError, ProgrammingError
    from sqlalchemy.orm import selectinload

    from app.api.models.crawled_page import CrawledPage
    from app.api.models.part import Part

    counts = SignalCounts()
    per_field_counts = empty_per_field_counts_dict()
    total = 0
    seen_part_ids: set[Any] = set()

    q = (
        db.query(CrawledPage)
        .options(selectinload(CrawledPage.part).selectinload(Part.car_generations))
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
        return SignalCounts(), empty_per_field_counts_dict(), 0, True

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
            return SignalCounts(), empty_per_field_counts_dict(), 0, True
        try:
            part = page.part
            if part is None:
                continue
            # Multiple crawled_pages can point at the same part (re-scrape /
                # canonical_part_id); count each part once per snapshot.
            pid = getattr(part, "id", None)
            if pid is None or pid in seen_part_ids:
                continue
            seen_part_ids.add(pid)
            total += 1
            count_signals_for_part(part, counts)
            count_per_field_for_part(part, per_field_counts)
        except Exception as exc:  # noqa: BLE001 — defensive (MEM206 pattern)
            logger.debug(
                "snapshot_row_failed",
                extra={
                    "page_id": getattr(page, "id", "?"),
                    "error_class": type(exc).__name__,
                },
            )
            continue

    return counts, per_field_counts, total, total == 0


# ---------------------------------------------------------------------------
# JSON envelope readers / writers
# ---------------------------------------------------------------------------


def _empty_signal_block() -> dict[str, int]:
    return SignalCounts().to_dict()


def build_pre_envelope(
    *,
    counts: SignalCounts,
    corpus_total: int,
    zero_corpus: bool,
    snapshot_taken_at: str,
) -> dict[str, Any]:
    """Construct the on-disk JSON envelope for ``--phase pre_s04``."""
    return {
        "snapshot_taken_at": snapshot_taken_at,
        "corpus_total": int(corpus_total),
        "pre_s04": counts.to_dict(),
        "post_s04": None,
        "delta_pct": None,
        "zero_corpus": bool(zero_corpus),
    }


def build_post_envelope(
    *,
    existing: dict[str, Any],
    counts: SignalCounts,
    corpus_total: int,
    zero_corpus: bool,
    snapshot_taken_at: str,
) -> dict[str, Any]:
    """Mutate-and-return the on-disk JSON envelope for ``--phase post_s04``.

    Reads the prior ``pre_s04`` block from ``existing`` and computes
    ``delta_pct``. Updates ``snapshot_taken_at`` to the post-phase timestamp.
    """
    pre_block = existing.get("pre_s04") or _empty_signal_block()
    post_block = counts.to_dict()
    delta = compute_delta_pct(pre_block, post_block)
    return {
        "snapshot_taken_at": snapshot_taken_at,
        "corpus_total": int(corpus_total),
        "pre_s04": pre_block,
        "post_s04": post_block,
        "delta_pct": delta,
        "zero_corpus": bool(zero_corpus),
    }


def read_existing_envelope(path: Path) -> dict[str, Any]:
    """Read + minimally validate the prior pre-phase JSON envelope.

    Raises ``FileNotFoundError`` if the file is missing — the post phase
    requires the pre-phase artifact. ``json.JSONDecodeError`` propagates and
    main() maps it to exit 1.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"snapshot file missing at {path} — run --phase pre_s04 first"
        )
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"snapshot file at {path} is not a JSON object")
    return data


def read_existing_s05_envelope(path: Path) -> dict[str, Any]:
    """S05 sibling of ``read_existing_envelope`` — only the missing-file
    error message differs (mirrors S04 pattern, points operator at
    ``--phase pre_s05``)."""
    if not path.exists():
        raise FileNotFoundError(
            f"snapshot file missing at {path} — run --phase pre_s05 first"
        )
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"snapshot file at {path} is not a JSON object")
    return data


def build_pre_s05_envelope(
    *,
    counts: SignalCounts,
    per_field_counts: dict[str, int],
    corpus_total: int,
    zero_corpus: bool,
    snapshot_taken_at: str,
) -> dict[str, Any]:
    """Construct the on-disk JSON envelope for ``--phase pre_s05``.

    Schema (per slice plan):
      * ``pre_s05`` populated with the four aggregate counts.
      * ``post_s05`` null until ``--phase post_s05`` runs.
      * ``per_universal_field_pre_s05`` populated with per-field counts.
      * ``per_universal_field_post_s05`` null.
      * ``delta_pct`` and ``per_field_delta_pct`` null.
      * ``zero_corpus`` flag.
    """
    return {
        "snapshot_taken_at": snapshot_taken_at,
        "corpus_total": int(corpus_total),
        "pre_s05": counts.to_dict(),
        "post_s05": None,
        "per_universal_field_pre_s05": dict(per_field_counts),
        "per_universal_field_post_s05": None,
        "delta_pct": None,
        "per_field_delta_pct": None,
        "zero_corpus": bool(zero_corpus),
    }


def build_post_s05_envelope(
    *,
    existing: dict[str, Any],
    counts: SignalCounts,
    per_field_counts: dict[str, int],
    corpus_total: int,
    zero_corpus: bool,
    snapshot_taken_at: str,
) -> dict[str, Any]:
    """Construct the on-disk JSON envelope for ``--phase post_s05``.

    Reads ``pre_s05`` and ``per_universal_field_pre_s05`` from ``existing``,
    computes both aggregate ``delta_pct`` and ``per_field_delta_pct``.
    """
    pre_block = existing.get("pre_s05") or _empty_signal_block()
    pre_per_field = existing.get("per_universal_field_pre_s05") or empty_per_field_counts_dict()
    post_block = counts.to_dict()
    post_per_field = dict(per_field_counts)
    delta = compute_delta_pct(pre_block, post_block)
    per_field_delta = compute_per_field_delta_pct(pre_per_field, post_per_field)
    return {
        "snapshot_taken_at": snapshot_taken_at,
        "corpus_total": int(corpus_total),
        "pre_s05": pre_block,
        "post_s05": post_block,
        "per_universal_field_pre_s05": pre_per_field,
        "per_universal_field_post_s05": post_per_field,
        "delta_pct": delta,
        "per_field_delta_pct": per_field_delta,
        "zero_corpus": bool(zero_corpus),
    }


def read_existing_s06_envelope(path: Path) -> dict[str, Any]:
    """S06 sibling of ``read_existing_envelope`` / ``read_existing_s05_envelope`` —
    only the missing-file error message differs (mirrors S05 pattern, points
    operator at ``--phase pre_s06``)."""
    if not path.exists():
        raise FileNotFoundError(
            f"snapshot file missing at {path} — run --phase pre_s06 first"
        )
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"snapshot file at {path} is not a JSON object")
    return data


def build_pre_s06_envelope(
    *,
    counts: SignalCounts,
    per_field_counts: dict[str, int],
    corpus_total: int,
    zero_corpus: bool,
    snapshot_taken_at: str,
) -> dict[str, Any]:
    """Construct the on-disk JSON envelope for ``--phase pre_s06``.

    Schema (mirrors ``build_pre_s05_envelope`` with S06-keyed names):
      * ``pre_s06`` populated with the four aggregate counts.
      * ``post_s06`` null until ``--phase post_s06`` runs.
      * ``per_universal_field_pre_s06`` populated with per-field counts (keyed
        on the live ``UNIVERSAL_FIELD_NAMES`` tuple — at this task close that
        is still the S05 five-field tuple; T03 extends it with
        ``manufacturer_part_number``).
      * ``per_universal_field_post_s06`` null.
      * ``delta_pct`` and ``per_field_delta_pct`` null.
      * ``zero_corpus`` flag.
    """
    return {
        "snapshot_taken_at": snapshot_taken_at,
        "corpus_total": int(corpus_total),
        "pre_s06": counts.to_dict(),
        "post_s06": None,
        "per_universal_field_pre_s06": dict(per_field_counts),
        "per_universal_field_post_s06": None,
        "delta_pct": None,
        "per_field_delta_pct": None,
        "zero_corpus": bool(zero_corpus),
    }


def build_post_s06_envelope(
    *,
    existing: dict[str, Any],
    counts: SignalCounts,
    per_field_counts: dict[str, int],
    corpus_total: int,
    zero_corpus: bool,
    snapshot_taken_at: str,
) -> dict[str, Any]:
    """Construct the on-disk JSON envelope for ``--phase post_s06``.

    Reads ``pre_s06`` and ``per_universal_field_pre_s06`` from ``existing``,
    computes both aggregate ``delta_pct`` and ``per_field_delta_pct``.
    """
    pre_block = existing.get("pre_s06") or _empty_signal_block()
    pre_per_field = existing.get("per_universal_field_pre_s06") or empty_per_field_counts_dict()
    post_block = counts.to_dict()
    post_per_field = dict(per_field_counts)
    delta = compute_delta_pct(pre_block, post_block)
    per_field_delta = compute_per_field_delta_pct(pre_per_field, post_per_field)
    return {
        "snapshot_taken_at": snapshot_taken_at,
        "corpus_total": int(corpus_total),
        "pre_s06": pre_block,
        "post_s06": post_block,
        "per_universal_field_pre_s06": pre_per_field,
        "per_universal_field_post_s06": post_per_field,
        "delta_pct": delta,
        "per_field_delta_pct": per_field_delta,
        "zero_corpus": bool(zero_corpus),
    }


def evaluate_s06_dod_verdict(
    *,
    delta_pct: dict[str, float],
    per_field_delta_pct: dict[str, float],
    zero_corpus: bool,
    pre_counts: dict[str, int],
    post_counts: dict[str, int],
    pre_per_field: dict[str, int],
    post_per_field: dict[str, int],
) -> tuple[str, list[str]]:
    """S06 DoD verdict — identical logic to ``evaluate_s05_dod_verdict``.

    Per slice plan (M004/S06): "the verdict logic is identical — at-least-one
    positive per-field delta in non-zero corpus, no aggregate or per-field
    drop ≥1%, zero_corpus_pass when zero on both sides". Implementation
    delegates straight through.
    """
    return evaluate_s05_dod_verdict(
        delta_pct=delta_pct,
        per_field_delta_pct=per_field_delta_pct,
        zero_corpus=zero_corpus,
        pre_counts=pre_counts,
        post_counts=post_counts,
        pre_per_field=pre_per_field,
        post_per_field=post_per_field,
    )


def write_envelope(envelope: dict[str, Any], out_path: Path) -> None:
    """Write the JSON envelope, creating parent dirs as needed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(envelope, fh, indent=2, sort_keys=True)
        fh.write("\n")


def emit_json_envelope(payload: dict[str, Any]) -> None:
    """Emit one structured JSON line to stdout (machine-pipeable)."""
    print(json.dumps(payload, sort_keys=True))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m004_corpus_snapshot",
        description=(
            "M004 corpus-snapshot CLI (MEM212 measurement-only tool). Iterates "
            "the local crawled_pages -> part corpus and counts non-null "
            "inference state for four signals: car, manufacturer, "
            "spec_any_field, spec_all_universal_fields. Writes a JSON "
            "envelope to --out and emits one structured stdout JSON line per "
            "--phase invocation. On --phase post_s04, computes delta_pct vs. "
            "the prior pre_s04 block and emits a final dod_verdict line."
        ),
    )
    p.add_argument(
        "--phase",
        choices=VALID_PHASES,
        required=True,
        help="Which top-level key in the JSON envelope to populate.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Output JSON path. Default depends on --phase: S04 phases write "
            "../.gsd/milestones/M004/s04-corpus-delta.json; S05 phases write "
            "../.gsd/milestones/M004/s05-corpus-delta.json (relative to "
            "backend/ cwd)."
        ),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap iteration at N pages (smoke-test hook only).",
    )
    return p


def _run_phase_pre_s04(db, *, args: argparse.Namespace) -> int:
    counts, _per_field_unused, corpus_total, zero_corpus = iterate_corpus_snapshot(
        db, limit=args.limit
    )
    envelope = build_pre_envelope(
        counts=counts,
        corpus_total=corpus_total,
        zero_corpus=zero_corpus,
        snapshot_taken_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        write_envelope(envelope, args.out)
    except OSError as exc:
        logger.error(
            "snapshot_write_failed",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {"error": "snapshot_write_failed", "out_path": str(args.out), "detail": repr(exc)}
            ),
            file=sys.stderr,
        )
        return 1
    emit_json_envelope(
        {
            "phase": "pre_s04",
            "snapshot_taken_at": envelope["snapshot_taken_at"],
            "corpus_total": envelope["corpus_total"],
            "pre_s04": envelope["pre_s04"],
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    return 0


def _run_phase_post_s04(db, *, args: argparse.Namespace) -> int:
    try:
        existing = read_existing_envelope(args.out)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        logger.error(
            "snapshot_pre_phase_unreadable",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {
                    "error": "snapshot_pre_phase_unreadable",
                    "out_path": str(args.out),
                    "detail": repr(exc),
                }
            ),
            file=sys.stderr,
        )
        return 1

    counts, _per_field_unused, corpus_total, zero_corpus = iterate_corpus_snapshot(
        db, limit=args.limit
    )
    envelope = build_post_envelope(
        existing=existing,
        counts=counts,
        corpus_total=corpus_total,
        zero_corpus=zero_corpus,
        snapshot_taken_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        write_envelope(envelope, args.out)
    except OSError as exc:
        logger.error(
            "snapshot_write_failed",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {"error": "snapshot_write_failed", "out_path": str(args.out), "detail": repr(exc)}
            ),
            file=sys.stderr,
        )
        return 1

    pre_block = envelope["pre_s04"]
    post_block = envelope["post_s04"]
    delta_pct = envelope["delta_pct"]
    verdict, regressions = evaluate_dod_verdict(
        delta_pct=delta_pct,
        zero_corpus=bool(zero_corpus and corpus_total == 0),
        pre_counts=pre_block,
        post_counts=post_block,
    )

    # Phase envelope (informational).
    emit_json_envelope(
        {
            "phase": "post_s04",
            "snapshot_taken_at": envelope["snapshot_taken_at"],
            "corpus_total": envelope["corpus_total"],
            "post_s04": post_block,
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    # Final close-line consumed by T05 + downstream slices.
    emit_json_envelope(
        {
            "dod_verdict": verdict,
            "regressions": regressions,
            "deltas": delta_pct,
            "pre_s04": pre_block,
            "post_s04": post_block,
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    return 1 if verdict == "fail" else 0


def _run_phase_pre_s05(db, *, args: argparse.Namespace) -> int:
    counts, per_field_counts, corpus_total, zero_corpus = iterate_corpus_snapshot(
        db, limit=args.limit
    )
    envelope = build_pre_s05_envelope(
        counts=counts,
        per_field_counts=per_field_counts,
        corpus_total=corpus_total,
        zero_corpus=zero_corpus,
        snapshot_taken_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        write_envelope(envelope, args.out)
    except OSError as exc:
        logger.error(
            "snapshot_write_failed",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {"error": "snapshot_write_failed", "out_path": str(args.out), "detail": repr(exc)}
            ),
            file=sys.stderr,
        )
        return 1
    emit_json_envelope(
        {
            "phase": "pre_s05",
            "snapshot_taken_at": envelope["snapshot_taken_at"],
            "corpus_total": envelope["corpus_total"],
            "pre_s05": envelope["pre_s05"],
            "per_universal_field_pre_s05": envelope["per_universal_field_pre_s05"],
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    return 0


def _run_phase_post_s05(db, *, args: argparse.Namespace) -> int:
    try:
        existing = read_existing_s05_envelope(args.out)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        logger.error(
            "snapshot_pre_phase_unreadable",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {
                    "error": "snapshot_pre_phase_unreadable",
                    "out_path": str(args.out),
                    "detail": repr(exc),
                }
            ),
            file=sys.stderr,
        )
        return 1

    counts, per_field_counts, corpus_total, zero_corpus = iterate_corpus_snapshot(
        db, limit=args.limit
    )
    envelope = build_post_s05_envelope(
        existing=existing,
        counts=counts,
        per_field_counts=per_field_counts,
        corpus_total=corpus_total,
        zero_corpus=zero_corpus,
        snapshot_taken_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        write_envelope(envelope, args.out)
    except OSError as exc:
        logger.error(
            "snapshot_write_failed",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {"error": "snapshot_write_failed", "out_path": str(args.out), "detail": repr(exc)}
            ),
            file=sys.stderr,
        )
        return 1

    pre_block = envelope["pre_s05"]
    post_block = envelope["post_s05"]
    pre_per_field = envelope["per_universal_field_pre_s05"]
    post_per_field = envelope["per_universal_field_post_s05"]
    delta_pct = envelope["delta_pct"]
    per_field_delta_pct = envelope["per_field_delta_pct"]
    verdict, regressions = evaluate_s05_dod_verdict(
        delta_pct=delta_pct,
        per_field_delta_pct=per_field_delta_pct,
        zero_corpus=bool(zero_corpus and corpus_total == 0),
        pre_counts=pre_block,
        post_counts=post_block,
        pre_per_field=pre_per_field,
        post_per_field=post_per_field,
    )

    # Phase envelope (informational).
    emit_json_envelope(
        {
            "phase": "post_s05",
            "snapshot_taken_at": envelope["snapshot_taken_at"],
            "corpus_total": envelope["corpus_total"],
            "post_s05": post_block,
            "per_universal_field_post_s05": post_per_field,
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    # Final close-line consumed by S07 lift summary.
    emit_json_envelope(
        {
            "dod_verdict": verdict,
            "regressions": regressions,
            "deltas": delta_pct,
            "per_field_deltas": per_field_delta_pct,
            "pre_s05": pre_block,
            "post_s05": post_block,
            "per_universal_field_pre_s05": pre_per_field,
            "per_universal_field_post_s05": post_per_field,
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    return 1 if verdict == "fail" else 0


def _run_phase_pre_s06(db, *, args: argparse.Namespace) -> int:
    counts, per_field_counts, corpus_total, zero_corpus = iterate_corpus_snapshot(
        db, limit=args.limit
    )
    envelope = build_pre_s06_envelope(
        counts=counts,
        per_field_counts=per_field_counts,
        corpus_total=corpus_total,
        zero_corpus=zero_corpus,
        snapshot_taken_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        write_envelope(envelope, args.out)
    except OSError as exc:
        logger.error(
            "snapshot_write_failed",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {"error": "snapshot_write_failed", "out_path": str(args.out), "detail": repr(exc)}
            ),
            file=sys.stderr,
        )
        return 1
    emit_json_envelope(
        {
            "phase": "pre_s06",
            "snapshot_taken_at": envelope["snapshot_taken_at"],
            "corpus_total": envelope["corpus_total"],
            "pre_s06": envelope["pre_s06"],
            "per_universal_field_pre_s06": envelope["per_universal_field_pre_s06"],
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    return 0


def _run_phase_post_s06(db, *, args: argparse.Namespace) -> int:
    try:
        existing = read_existing_s06_envelope(args.out)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        logger.error(
            "snapshot_pre_phase_unreadable",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {
                    "error": "snapshot_pre_phase_unreadable",
                    "out_path": str(args.out),
                    "detail": repr(exc),
                }
            ),
            file=sys.stderr,
        )
        return 1

    counts, per_field_counts, corpus_total, zero_corpus = iterate_corpus_snapshot(
        db, limit=args.limit
    )
    envelope = build_post_s06_envelope(
        existing=existing,
        counts=counts,
        per_field_counts=per_field_counts,
        corpus_total=corpus_total,
        zero_corpus=zero_corpus,
        snapshot_taken_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        write_envelope(envelope, args.out)
    except OSError as exc:
        logger.error(
            "snapshot_write_failed",
            extra={"out_path": str(args.out), "error_class": type(exc).__name__},
        )
        print(
            json.dumps(
                {"error": "snapshot_write_failed", "out_path": str(args.out), "detail": repr(exc)}
            ),
            file=sys.stderr,
        )
        return 1

    pre_block = envelope["pre_s06"]
    post_block = envelope["post_s06"]
    pre_per_field = envelope["per_universal_field_pre_s06"]
    post_per_field = envelope["per_universal_field_post_s06"]
    delta_pct = envelope["delta_pct"]
    per_field_delta_pct = envelope["per_field_delta_pct"]
    verdict, regressions = evaluate_s06_dod_verdict(
        delta_pct=delta_pct,
        per_field_delta_pct=per_field_delta_pct,
        zero_corpus=bool(zero_corpus and corpus_total == 0),
        pre_counts=pre_block,
        post_counts=post_block,
        pre_per_field=pre_per_field,
        post_per_field=post_per_field,
    )

    # Phase envelope (informational).
    emit_json_envelope(
        {
            "phase": "post_s06",
            "snapshot_taken_at": envelope["snapshot_taken_at"],
            "corpus_total": envelope["corpus_total"],
            "post_s06": post_block,
            "per_universal_field_post_s06": post_per_field,
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    # Final close-line consumed by S07 lift summary.
    emit_json_envelope(
        {
            "dod_verdict": verdict,
            "regressions": regressions,
            "deltas": delta_pct,
            "per_field_deltas": per_field_delta_pct,
            "pre_s06": pre_block,
            "post_s06": post_block,
            "per_universal_field_pre_s06": pre_per_field,
            "per_universal_field_post_s06": post_per_field,
            "zero_corpus": envelope["zero_corpus"],
            "out_path": str(args.out),
        }
    )
    return 1 if verdict == "fail" else 0


def _resolve_default_out(phase: str, supplied: Optional[Path]) -> Path:
    """Return the resolved --out path, applying the phase-aware default
    when the user did not supply one. S04 phases default to
    ``DEFAULT_OUT_PATH``; S05 phases default to ``DEFAULT_OUT_PATH_S05``;
    S06 phases default to ``DEFAULT_OUT_PATH_S06``."""
    if supplied is not None:
        return supplied
    if phase in ("pre_s04", "post_s04"):
        return DEFAULT_OUT_PATH
    if phase in ("pre_s05", "post_s05"):
        return DEFAULT_OUT_PATH_S05
    if phase in ("pre_s06", "post_s06"):
        return DEFAULT_OUT_PATH_S06
    # argparse choices=VALID_PHASES guarantees we never reach here, but be
    # explicit for static analyzers.
    return DEFAULT_OUT_PATH


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Apply phase-aware default when --out was omitted.
    args.out = _resolve_default_out(args.phase, args.out)

    # DB connect — exit 1 on unreachable.
    try:
        from app.db.session import SessionLocal  # local import; respects TESTING env
    except Exception as exc:  # noqa: BLE001
        logger.error("db_unreachable", extra={"error_class": type(exc).__name__})
        print(json.dumps({"error": "db_unreachable", "detail": repr(exc)}), file=sys.stderr)
        return 1

    try:
        db = SessionLocal()
    except Exception as exc:  # noqa: BLE001
        logger.error("db_unreachable", extra={"error_class": type(exc).__name__})
        print(json.dumps({"error": "db_unreachable", "detail": repr(exc)}), file=sys.stderr)
        return 1

    try:
        if args.phase == "pre_s04":
            return _run_phase_pre_s04(db, args=args)
        if args.phase == "post_s04":
            return _run_phase_post_s04(db, args=args)
        if args.phase == "pre_s05":
            return _run_phase_pre_s05(db, args=args)
        if args.phase == "post_s05":
            return _run_phase_post_s05(db, args=args)
        if args.phase == "pre_s06":
            return _run_phase_pre_s06(db, args=args)
        if args.phase == "post_s06":
            return _run_phase_post_s06(db, args=args)
        # argparse choices=VALID_PHASES guarantees we never reach here.
        return 1
    finally:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
