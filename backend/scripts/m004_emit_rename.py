"""M004 per-rename Alembic migration + JSON-seed patch emitter (T02).

One-shot CLI that consumes a single decision row from
``.gsd/milestones/M004/taxonomy-audit-dryrun.csv`` (T01 output) — or a
``--decision-json`` payload — and atomically emits TWO coordinated artifacts:

1. ONE hand-written Alembic migration under ``backend/alembic/versions/``
   chained off the current head, with::

       op.execute(
           sa.text("UPDATE car_generations SET generation_name=:new WHERE id=:id"),
           {"new": ..., "id": ...},
       )

   in ``upgrade()`` and the inverse in ``downgrade()``. Migration docstring
   captures ``(audit_revision_or_dryrun_csv_row, corpus_count, retailer_count,
   edit_distance, decided_at)`` so the audit trail lives in-tree.

2. A coordinated patch to ``backend/app/core/car_generations_data.json`` that
   updates the row's ``generation_name`` to the new form AND pins the row's
   ``slug`` field to the OLD ``slugify(canonical_generation_name)`` value so
   ``init_car_generations`` finds the row by its stable slug on every boot
   (load-bearing precedent: ``backend/tests/test_init_cars_display_name.py:208-221``).

Why hand-written
----------------
``alembic revision --autogenerate`` is for DDL only — it does NOT detect
``UPDATE`` data migrations (per **MEM086** + standing project convention).
Generating "no-op" autogenerate revisions for these renames would silently
drop the rename in production. The CLI emits an explicit migration with
``op.execute(sa.text(...))`` and named bind params (NEVER string
interpolation — bind params keep operator-supplied generation names safe
from SQL injection in this single-row UPDATE).

Atomicity
---------
The JSON-seed write is serialized via ``fcntl.flock(LOCK_EX)`` over the
seed file itself, mirroring the S01 atomic-file pattern from
``backend/scripts/m004_label_gold_set.py``. Concurrent invocations targeting
the same seed will block until the first releases the lock — no partial
JSON corruption.

Usage
-----
::

    # Dry-run (default): print proposed migration filename + JSON diff,
    # write nothing.
    python -m scripts.m004_emit_rename \\
        --from-csv-row 2

    # Apply: write migration file + patch JSON seed atomically.
    python -m scripts.m004_emit_rename \\
        --decision-json '{"canonical_id": 42, "old_generation_name": "1st Gen", "new_generation_name": "F20", ...}' \\
        --apply

Exit codes
----------
* 0 — success (or successful dry-run).
* 1 — any of:
  - ``head_lookup_failed`` (alembic head not parsable)
  - ``head_drifted`` (head changed mid-emission)
  - ``seed_load_failed`` / ``seed_concurrent_edit``
  - ``ambiguity_test_unreadable`` / ``ambiguity_audit_blocked``
  - ``canonical_id_not_in_seed``
  - ``noop_rename_rejected``
  - ``slug_collision_detected``

Run from inside ``backend/`` (per **MEM209**):
``python -m scripts.m004_emit_rename ...``.
"""

from __future__ import annotations

import argparse
import ast
import csv
import dataclasses
import fcntl
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger("m004_emit_rename")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default paths assume CWD == backend/ (per MEM209).
DEFAULT_CSV_PATH = Path("../.gsd/milestones/M004/taxonomy-audit-dryrun.csv")
DEFAULT_ALEMBIC_VERSIONS_DIR = Path("alembic/versions")
# Per-make seed directory (one JSON file per make). The legacy monolithic
# car_generations_data.json was split in 2026-05; --seed-path may still point
# at a single .json file for tests / backward compat.
DEFAULT_SEED_PATH = Path("app/core/car_generations_seed")
DEFAULT_AMBIGUITY_TEST_PATH = Path("tests/test_car_inference_ambiguity.py")

REVISION_RE = re.compile(r'^revision:\s*str\s*=\s*"([^"]+)"', re.MULTILINE)
DOWN_REVISION_RE = re.compile(
    r'^down_revision:\s*Union\[str,\s*None\]\s*=\s*"([^"]+)"',
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Decision:
    """One rename decision row from T01's CSV (or --decision-json payload)."""

    canonical_id: int
    old_generation_name: str
    new_generation_name: str
    corpus_count: int
    retailer_count: int
    edit_distance: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Decision":
        # Accept both T01's CSV column names and the more compact decision-json shape.
        old_name = raw.get("old_generation_name") or raw.get("canonical_form")
        new_name = raw.get("new_generation_name") or raw.get("challenger_form")
        corpus_count = raw.get("corpus_count")
        if corpus_count is None:
            corpus_count = raw.get("corpus_count_challenger", 0)
        if old_name is None or new_name is None:
            raise ValueError(
                "decision row missing old_generation_name/canonical_form or " "new_generation_name/challenger_form"
            )
        return cls(
            canonical_id=int(raw["canonical_id"]),
            old_generation_name=str(old_name),
            new_generation_name=str(new_name),
            corpus_count=int(corpus_count or 0),
            retailer_count=int(raw.get("retailer_count", 0) or 0),
            edit_distance=int(raw.get("edit_distance", 0) or 0),
        )


# ---------------------------------------------------------------------------
# Pure helpers (unit-test friendly)
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    """Mirror of ``app.core.car_generations_data.slugify`` to avoid the heavy
    JSON-load that re-importing that module triggers via ``car_generations``.
    """
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def short_filename_slug(value: str) -> str:
    """Filesystem-friendly slug for the migration filename (no leading digits stripping)."""
    out = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return out or "x"


def deterministic_revision_id(*, canonical_id: int, new_generation_name: str, decided_at: str) -> str:
    """12-hex-digit revision id derived from the rename triple.

    Re-running emission for the same triple at the same ``decided_at`` produces
    the same revision id, which keeps ``--dry-run`` and ``--apply`` aligned.
    """
    payload = f"{canonical_id}|{new_generation_name}|{decided_at}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:12]  # nosec B324 — non-crypto identifier


def parse_alembic_head(versions_dir: Path) -> str:
    """Return the head revision (the file whose `revision` is referenced by no
    other file's `down_revision`).

    Raises ``RuntimeError`` if zero or multiple heads are found.
    """
    if not versions_dir.is_dir():
        raise RuntimeError(f"alembic versions dir not found: {versions_dir}")

    revisions: set[str] = set()
    referenced: set[str] = set()
    for py in versions_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        rev_match = REVISION_RE.search(text)
        down_match = DOWN_REVISION_RE.search(text)
        if rev_match:
            revisions.add(rev_match.group(1))
        if down_match:
            referenced.add(down_match.group(1))

    heads = revisions - referenced
    if not heads:
        raise RuntimeError("no alembic head found (cycle or empty versions/)")
    if len(heads) > 1:
        raise RuntimeError(f"multiple alembic heads found, refusing to chain: {sorted(heads)}")
    return heads.pop()


def render_migration(
    *,
    new_revision: str,
    down_revision: str,
    decision: Decision,
    audit_source: str,
    decided_at: str,
) -> str:
    """Render the body of one Alembic migration file (hand-written, MEM086).

    Uses named bind params via ``sa.text(...).bindparams(...)`` — never string
    interpolation — so quotes/backslashes in operator-supplied names cannot
    forge SQL.
    """
    return f'''"""m004 rename car_generation {decision.old_generation_name!r} -> {decision.new_generation_name!r}

Hand-written data migration. ``alembic revision --autogenerate`` does NOT
detect UPDATE statements (DDL-only, MEM086) — generating this with
autogenerate would silently produce a no-op.

Audit trail:
    audit_source     = {audit_source}
    canonical_id     = {decision.canonical_id}
    corpus_count     = {decision.corpus_count}
    retailer_count   = {decision.retailer_count}
    edit_distance    = {decision.edit_distance}
    decided_at       = {decided_at}

Revision ID: {new_revision}
Revises: {down_revision}
Create Date: {decided_at}

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "{new_revision}"
down_revision: Union[str, None] = "{down_revision}"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE car_generations SET generation_name = :new_name WHERE id = :id"
        ).bindparams(new_name={decision.new_generation_name!r}, id={decision.canonical_id})
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE car_generations SET generation_name = :old_name WHERE id = :id"
        ).bindparams(old_name={decision.old_generation_name!r}, id={decision.canonical_id})
    )
'''


# ---------------------------------------------------------------------------
# Decision-row consumer
# ---------------------------------------------------------------------------


def load_decision_from_csv(csv_path: Path, row_number: int) -> Decision:
    """Read CSV at ``csv_path``, return the decision at 1-indexed ``row_number``
    (excluding the header).
    """
    if not csv_path.is_file():
        raise FileNotFoundError(f"taxonomy-audit-dryrun.csv not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if row_number < 1 or row_number > len(rows):
        raise IndexError(f"--from-csv-row {row_number} out of range " f"(file has {len(rows)} non-header rows)")
    raw = rows[row_number - 1]
    if raw.get("decision") and raw["decision"].strip().lower() != "rename":
        raise ValueError(f"row {row_number} has decision={raw['decision']!r}; emit only on " f"decision=rename")
    return Decision.from_dict(raw)


def load_decision_from_json(payload: str) -> Decision:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--decision-json is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("--decision-json must be a JSON object")
    return Decision.from_dict(raw)


# ---------------------------------------------------------------------------
# JSON-seed patch
# ---------------------------------------------------------------------------


def _find_generation_entry(seed: dict[str, list[dict[str, Any]]], old_name: str) -> Optional[tuple[str, int, int]]:
    """Locate ``(make_key, model_index, gen_index)`` for the first entry whose
    ``generation_name`` matches ``old_name``. Returns ``None`` if no match.

    Note: the JSON seed is keyed by canonical_id only via the *position* in
    the load order. The CLI cannot directly resolve canonical_id without
    standing up the DB; instead we match on the unique
    ``(make, model, generation_name)`` triple that the operator's CSV review
    confirmed. The contract with T01 is: when a rename row exists in
    taxonomy-audit-dryrun.csv, the ``(old_generation_name)`` is unique enough
    in the seed (per the corpus-vote rule's ``edit_distance`` gate).
    """
    for make, models in seed.items():
        for m_idx, model in enumerate(models):
            generations = model.get("generations", [])
            for g_idx, gen in enumerate(generations):
                if gen.get("generation_name") == old_name:
                    return (make, m_idx, g_idx)
    return None


def _detect_slug_collision(
    seed: dict[str, list[dict[str, Any]]],
    *,
    make: str,
    model_index: int,
    gen_index: int,
    pinned_slug: str,
) -> Optional[str]:
    """Scan the same model's other generations for a ``slug`` collision."""
    generations = seed[make][model_index].get("generations", [])
    for i, gen in enumerate(generations):
        if i == gen_index:
            continue
        existing_slug = gen.get("slug") or slugify(gen.get("generation_name", ""))
        if existing_slug == pinned_slug:
            return existing_slug
    return None


def _resolve_seed_target(seed_path: Path, old_name: str) -> Path:
    """Resolve a seed_path (file OR per-make directory) to the single JSON file
    that contains a generation with generation_name == old_name.

    Directory mode (the post-split layout): scan every *.json under seed_path
    until one contains old_name. Raises ValueError if none does.

    File mode (legacy / tests): return seed_path unchanged.
    """
    if seed_path.is_file():
        return seed_path
    if not seed_path.is_dir():
        raise FileNotFoundError(f"seed path is neither file nor directory: {seed_path}")
    for entry in sorted(seed_path.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith(".json"):
            continue
        try:
            payload = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if _find_generation_entry(payload, old_name) is not None:
            return entry
    raise ValueError(f"canonical_id_not_in_seed: no generation_name={old_name!r} found " f"under {seed_path}")


def patch_seed(
    *,
    seed_path: Path,
    decision: Decision,
    apply: bool,
) -> dict[str, Any]:
    """Patch the JSON seed: set new generation_name, pin slug to old slugify form.

    ``seed_path`` may be either a single JSON file (legacy / tests) or the
    per-make directory (default). In directory mode the script first locates
    the file owning ``decision.old_generation_name`` and operates on that
    single file under flock.

    When ``apply=False`` (dry-run), returns the planned diff but does not
    write or even acquire the file lock.

    When ``apply=True``, opens the resolved file with ``r+`` mode, takes
    ``fcntl.flock(LOCK_EX)``, mutates the in-memory dict, and atomically
    rewrites the file in-place within the locked region. Returns the diff
    dict on success.
    """
    target = _resolve_seed_target(seed_path, decision.old_generation_name)

    if not apply:
        seed = json.loads(target.read_text(encoding="utf-8"))
        return _compute_seed_patch(seed, decision)

    # Apply path: hold flock for the entire read-mutate-write cycle.
    with target.open("r+", encoding="utf-8") as fp:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        except OSError as exc:  # pragma: no cover — flock failure is platform-specific
            logger.warning("could not acquire flock on %s: %s; aborting apply", target, exc)
            raise RuntimeError("seed_lock_failed") from exc
        fp.seek(0)
        seed = json.loads(fp.read())
        diff = _compute_seed_patch(seed, decision)

        # Apply the mutation in-place.
        make = diff["make"]
        m_idx = diff["model_index"]
        g_idx = diff["gen_index"]
        seed[make][m_idx]["generations"][g_idx]["generation_name"] = decision.new_generation_name
        seed[make][m_idx]["generations"][g_idx]["slug"] = diff["pinned_slug"]

        _atomic_rewrite_under_lock(fp, seed)
    return diff


def _compute_seed_patch(seed: dict[str, list[dict[str, Any]]], decision: Decision) -> dict[str, Any]:
    """Resolve the (make, model_index, gen_index) and detect collisions
    without mutating the seed.
    """
    if decision.old_generation_name == decision.new_generation_name:
        raise ValueError("noop_rename_rejected")

    located = _find_generation_entry(seed, decision.old_generation_name)
    if located is None:
        raise ValueError(f"canonical_id_not_in_seed: no generation_name={decision.old_generation_name!r} in seed")
    make, m_idx, g_idx = located
    pinned_slug = slugify(decision.old_generation_name)

    collision = _detect_slug_collision(seed, make=make, model_index=m_idx, gen_index=g_idx, pinned_slug=pinned_slug)
    if collision is not None:
        raise ValueError(
            f"slug_collision_detected: pinned slug {pinned_slug!r} already used "
            f"by another generation under make={make!r}, model_index={m_idx}"
        )

    return {
        "make": make,
        "model_index": m_idx,
        "gen_index": g_idx,
        "old_generation_name": decision.old_generation_name,
        "new_generation_name": decision.new_generation_name,
        "pinned_slug": pinned_slug,
    }


def _atomic_rewrite_under_lock(fp: Any, payload: dict[str, list[dict[str, Any]]]) -> None:
    """Rewrite the locked file atomically.

    The ``flock`` is held on ``fp`` for the duration of this call. We
    truncate-in-place rather than temp-and-rename so the lock and file
    identity stay paired (a rename swaps the inode, which would orphan the
    lock for any other waiter).
    """
    fp.seek(0)
    fp.truncate()
    json.dump(payload, fp, indent=2, sort_keys=True, ensure_ascii=False)
    fp.write("\n")
    fp.flush()
    os.fsync(fp.fileno())


# ---------------------------------------------------------------------------
# Ambiguity-AST audit
# ---------------------------------------------------------------------------


def ambiguity_audit(test_path: Path, old_generation_name: str) -> Optional[tuple[int, str]]:
    """Walk ``test_path`` AST for any ``ast.Constant`` string equal to
    ``old_generation_name``. Returns ``(line_number, snippet)`` on first hit
    or ``None`` if clean.

    Raises ``RuntimeError`` if the test file is unreadable / unparsable.
    """
    if not test_path.is_file():
        raise RuntimeError(f"ambiguity_test_unreadable: {test_path} not found")
    try:
        source = test_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as exc:
        raise RuntimeError(f"ambiguity_test_unreadable: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value == old_generation_name:
                line = getattr(node, "lineno", 0)
                snippet = source.splitlines()[line - 1] if 0 < line else ""
                return (line, snippet.strip())
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m004_emit_rename",
        description=("Emit one Alembic migration + JSON-seed patch per rename decision " "(M004/S02/T02)."),
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--from-csv-row",
        type=int,
        metavar="N",
        help=("1-indexed row number (excluding header) into " "../.gsd/milestones/M004/taxonomy-audit-dryrun.csv."),
    )
    src.add_argument(
        "--decision-json",
        type=str,
        metavar="JSON",
        help=(
            "JSON object with keys: canonical_id, old_generation_name, "
            "new_generation_name, [corpus_count, retailer_count, edit_distance]."
        ),
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=(f"Path to taxonomy-audit-dryrun.csv (default: {DEFAULT_CSV_PATH}, " "relative to backend/)."),
    )
    parser.add_argument(
        "--versions-dir",
        type=Path,
        default=DEFAULT_ALEMBIC_VERSIONS_DIR,
        help=f"Path to alembic versions/ (default: {DEFAULT_ALEMBIC_VERSIONS_DIR}).",
    )
    parser.add_argument(
        "--seed-path",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help=(f"Path to per-make seed directory (default: {DEFAULT_SEED_PATH}) " f"or a single legacy JSON file."),
    )
    parser.add_argument(
        "--ambiguity-test-path",
        type=Path,
        default=DEFAULT_AMBIGUITY_TEST_PATH,
        help=(f"Path to test_car_inference_ambiguity.py " f"(default: {DEFAULT_AMBIGUITY_TEST_PATH})."),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write migration file + patch JSON seed (default: dry-run only).",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Default. Print planned migration filename + JSON diff, write nothing.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _setup_logging(args.verbose)

    # Decision row.
    try:
        if args.from_csv_row is not None:
            decision = load_decision_from_csv(args.csv_path, args.from_csv_row)
            audit_source = f"csv:{args.csv_path}#row={args.from_csv_row}"
        else:
            decision = load_decision_from_json(args.decision_json)
            audit_source = "decision-json"
    except (FileNotFoundError, IndexError, ValueError, KeyError) as exc:
        logger.error("decision_load_failed: %s", exc)
        return 1

    if decision.old_generation_name == decision.new_generation_name:
        logger.error("noop_rename_rejected: old == new == %r", decision.old_generation_name)
        return 1

    # Ambiguity-AST audit (block on collision).
    try:
        hit = ambiguity_audit(args.ambiguity_test_path, decision.old_generation_name)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    if hit is not None:
        line, snippet = hit
        logger.warning(
            "ambiguity_audit_blocked: old generation_name=%r appears in %s:%d (%s)",
            decision.old_generation_name,
            args.ambiguity_test_path,
            line,
            snippet,
        )
        return 1

    # Alembic head lookup.
    try:
        head = parse_alembic_head(args.versions_dir)
    except RuntimeError as exc:
        logger.error("head_lookup_failed: %s", exc)
        return 1

    decided_at = _now_iso()
    new_revision = deterministic_revision_id(
        canonical_id=decision.canonical_id,
        new_generation_name=decision.new_generation_name,
        decided_at=decided_at,
    )
    filename = (
        f"{new_revision}_m004_rename_"
        f"{short_filename_slug(decision.old_generation_name)}_to_"
        f"{short_filename_slug(decision.new_generation_name)}.py"
    )
    migration_path = args.versions_dir / filename

    # Plan the JSON-seed patch (read-only) before doing the apply.
    try:
        if args.apply:
            seed_diff = patch_seed(seed_path=args.seed_path, decision=decision, apply=False)
        else:
            seed_diff = patch_seed(seed_path=args.seed_path, decision=decision, apply=False)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("seed_load_failed: %s", exc)
        return 1

    plan = {
        "revision": new_revision,
        "down_revision": head,
        "filename": str(migration_path),
        "audit_source": audit_source,
        "decided_at": decided_at,
        "seed_diff": seed_diff,
        "decision": dataclasses.asdict(decision),
    }
    print(json.dumps({"event": "rename_plan", **plan}))

    if not args.apply:
        logger.info("dry-run complete; pass --apply to write artifacts")
        return 0

    # Apply mode — re-check head right before writing to detect drift.
    try:
        head_now = parse_alembic_head(args.versions_dir)
    except RuntimeError as exc:
        logger.error("head_lookup_failed: %s", exc)
        return 1
    if head_now != head:
        logger.error(
            "head_drifted: head was %s at planning time, now %s; refusing to chain",
            head,
            head_now,
        )
        return 1

    if migration_path.exists():
        logger.error("migration_already_exists: %s — refusing to overwrite", migration_path)
        return 1

    body = render_migration(
        new_revision=new_revision,
        down_revision=head,
        decision=decision,
        audit_source=audit_source,
        decided_at=decided_at,
    )
    # Atomically write the migration via temp-file-and-rename (single-writer file,
    # no concurrent emitter touches it because the JSON seed is the shared resource).
    migration_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=migration_path.stem + ".",
        suffix=".tmp",
        dir=str(migration_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(body)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, migration_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    # Coordinated JSON-seed write (under flock).
    try:
        patch_seed(seed_path=args.seed_path, decision=decision, apply=True)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        # Roll back the migration file so we don't leave a dangling head.
        logger.error("seed_apply_failed: %s; rolling back migration file", exc)
        try:
            migration_path.unlink()
        except OSError:
            pass
        return 1

    logger.info(
        "migration_emitted: %s (canonical_id=%d, old=%r, new=%r)",
        migration_path,
        decision.canonical_id,
        decision.old_generation_name,
        decision.new_generation_name,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
