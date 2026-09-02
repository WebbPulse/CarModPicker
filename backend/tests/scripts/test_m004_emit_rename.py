"""Unit tests for ``backend/scripts/m004_emit_rename.py``.

Coverage:

* Decision-row parsing (CSV + JSON shapes, error paths).
* Alembic head lookup (single head, multi-head rejection, missing dir).
* Deterministic revision id (idempotent for same triple, distinct otherwise).
* JSON-seed patch — happy path, idempotence, slug-collision detection,
  noop-rename rejection, canonical_id-not-in-seed rejection,
  ``fcntl.flock`` mutual exclusion.
* Ambiguity-AST audit (positive + negative).
* CLI dry-run vs --apply behavior + head-drift detection.
"""

from __future__ import annotations

import csv
import fcntl
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

# Ensure backend/ is on sys.path so `import scripts.m004_emit_rename` works
# whether the test is invoked from backend/ or the repo root.
# backend/tests/scripts/test_m004_emit_rename.py
#                ^^^^^^^^ parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts import m004_emit_rename as emit  # noqa: E402

A80_ID = uuid.UUID("0195c9f3-1d2e-7a4b-8c5d-6e7f80912a3b")
E46_ID = uuid.UUID("0195c9f3-2a3b-7c4d-8e5f-90a1b2c3d4e5")
ABSENT_ID = uuid.UUID("0195c9f3-3b4c-7d5e-8f60-a1b2c3d4e5f6")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "Toyota": [
            {
                "model": "Supra",
                "generations": [
                    {
                        "generation_name": "A80",
                        "start_year": 1993,
                        "end_year": 2002,
                    },
                    {
                        "generation_name": "A90",
                        "start_year": 2019,
                        "end_year": None,
                    },
                ],
            }
        ],
        "BMW": [
            {
                "model": "M3",
                "generations": [
                    {
                        "generation_name": "E46",
                        "start_year": 2000,
                        "end_year": 2006,
                    },
                ],
            }
        ],
    }


@pytest.fixture
def seed_file(tmp_path: Path, fake_seed: dict[str, Any]) -> Path:
    p = tmp_path / "car_generations_data.json"
    p.write_text(json.dumps(fake_seed, indent=2, sort_keys=True), encoding="utf-8")
    return p


@pytest.fixture
def fake_versions_dir(tmp_path: Path) -> Path:
    versions = tmp_path / "alembic" / "versions"
    versions.mkdir(parents=True)
    # Three migrations chained linearly: A -> B -> C (head = C).
    _write_alembic_stub(versions / "aaaaaaaaaaaa_a.py", "aaaaaaaaaaaa", None)
    _write_alembic_stub(versions / "bbbbbbbbbbbb_b.py", "bbbbbbbbbbbb", "aaaaaaaaaaaa")
    _write_alembic_stub(versions / "cccccccccccc_c.py", "cccccccccccc", "bbbbbbbbbbbb")
    return versions


def _write_alembic_stub(path: Path, revision: str, down_revision: str | None) -> None:
    down_repr = f'"{down_revision}"' if down_revision else "None"
    path.write_text(
        f'''"""stub"""

from typing import Sequence, Union

revision: str = "{revision}"
down_revision: Union[str, None] = {down_repr}
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None: ...
def downgrade() -> None: ...
''',
        encoding="utf-8",
    )


@pytest.fixture
def clean_ambiguity_test(tmp_path: Path) -> Path:
    p = tmp_path / "test_car_inference_ambiguity.py"
    p.write_text(
        '"""no collisions here."""\n'
        "VECTORS = [\n"
        '    ("Cusco MKV Supra", "A90 explicit", ("Toyota", "Supra", "A90"), "ok"),\n'
        "]\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def csv_with_rename(tmp_path: Path) -> Path:
    p = tmp_path / "taxonomy-audit-dryrun.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "canonical_id",
                "canonical_form",
                "challenger_form",
                "corpus_count_canonical",
                "corpus_count_challenger",
                "retailer_count",
                "edit_distance",
                "decision",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "canonical_id": str(A80_ID),
                "canonical_form": "A80",
                "challenger_form": "A80 (JZA80)",
                "corpus_count_canonical": "0",
                "corpus_count_challenger": "12",
                "retailer_count": "3",
                "edit_distance": "9",
                "decision": "rename",
            }
        )
        w.writerow(
            {
                "canonical_id": str(E46_ID),
                "canonical_form": "E46",
                "challenger_form": "E46 M3",
                "corpus_count_canonical": "5",
                "corpus_count_challenger": "8",
                "retailer_count": "1",
                "edit_distance": "4",
                "decision": "alias",
            }
        )
    return p


# ---------------------------------------------------------------------------
# slugify + filename slug + deterministic revision id
# ---------------------------------------------------------------------------


def test_slugify_matches_app_core_semantics() -> None:
    assert emit.slugify("A80") == "a80"
    assert emit.slugify("A80 (JZA80)") == "a80-jza80"
    assert emit.slugify("Mk5 Supra") == "mk5-supra"
    assert emit.slugify("RX-7") == "rx-7"
    assert emit.slugify("SA/FB") == "sa-fb"


def test_short_filename_slug_collapses_punctuation() -> None:
    assert emit.short_filename_slug("A80 (JZA80)") == "a80_jza80"
    assert emit.short_filename_slug("") == "x"
    assert emit.short_filename_slug("---") == "x"


def test_deterministic_revision_id_idempotent_for_same_triple() -> None:
    a = emit.deterministic_revision_id(canonical_id=A80_ID, new_generation_name="A80 (JZA80)", decided_at="2026-04-27")
    b = emit.deterministic_revision_id(canonical_id=A80_ID, new_generation_name="A80 (JZA80)", decided_at="2026-04-27")
    assert a == b
    assert len(a) == 12


def test_deterministic_revision_id_diverges_on_input_change() -> None:
    base = emit.deterministic_revision_id(
        canonical_id=A80_ID, new_generation_name="A80 (JZA80)", decided_at="2026-04-27"
    )
    by_name = emit.deterministic_revision_id(
        canonical_id=A80_ID, new_generation_name="A80 JZA80", decided_at="2026-04-27"
    )
    by_id = emit.deterministic_revision_id(
        canonical_id=E46_ID, new_generation_name="A80 (JZA80)", decided_at="2026-04-27"
    )
    assert base != by_name != by_id != base


def test_deterministic_revision_id_ignores_uuid_spelling() -> None:
    canonical = emit.deterministic_revision_id(
        canonical_id=A80_ID, new_generation_name="A80 (JZA80)", decided_at="2026-04-27"
    )
    braced = emit.deterministic_revision_id(
        canonical_id=uuid.UUID(f"{{{str(A80_ID).upper()}}}"),
        new_generation_name="A80 (JZA80)",
        decided_at="2026-04-27",
    )
    assert canonical == braced


# ---------------------------------------------------------------------------
# Decision row parsing
# ---------------------------------------------------------------------------


def test_load_decision_from_csv_picks_named_row(csv_with_rename: Path) -> None:
    d = emit.load_decision_from_csv(csv_with_rename, 1)
    assert d.canonical_id == A80_ID
    assert d.old_generation_name == "A80"
    assert d.new_generation_name == "A80 (JZA80)"
    assert d.corpus_count == 12
    assert d.retailer_count == 3
    assert d.edit_distance == 9


def test_load_decision_from_csv_rejects_non_rename_row(csv_with_rename: Path) -> None:
    with pytest.raises(ValueError, match="decision='alias'"):
        emit.load_decision_from_csv(csv_with_rename, 2)


def test_load_decision_from_csv_out_of_range(csv_with_rename: Path) -> None:
    with pytest.raises(IndexError):
        emit.load_decision_from_csv(csv_with_rename, 99)


def test_load_decision_from_json_accepts_compact_shape() -> None:
    d = emit.load_decision_from_json(
        json.dumps(
            {
                "canonical_id": str(E46_ID),
                "old_generation_name": "A",
                "new_generation_name": "B",
                "corpus_count": 5,
                "retailer_count": 2,
                "edit_distance": 1,
            }
        )
    )
    assert d.canonical_id == E46_ID
    assert d.old_generation_name == "A"
    assert d.new_generation_name == "B"


def test_load_decision_from_json_invalid_payload() -> None:
    with pytest.raises(ValueError):
        emit.load_decision_from_json("not-json")
    with pytest.raises(ValueError):
        emit.load_decision_from_json('"a-string"')


def test_load_decision_from_json_rejects_non_uuid_canonical_id() -> None:
    payload = json.dumps(
        {
            "canonical_id": 42,
            "old_generation_name": "A",
            "new_generation_name": "B",
        }
    )
    with pytest.raises(ValueError, match="canonical_id_not_a_uuid"):
        emit.load_decision_from_json(payload)


# ---------------------------------------------------------------------------
# Alembic head lookup
# ---------------------------------------------------------------------------


def test_parse_alembic_head_returns_unique_head(fake_versions_dir: Path) -> None:
    assert emit.parse_alembic_head(fake_versions_dir) == "cccccccccccc"


def test_parse_alembic_head_rejects_multi_head(fake_versions_dir: Path) -> None:
    # Add an unrelated branch to create a second head.
    _write_alembic_stub(fake_versions_dir / "ddddd.py", "ddddddddd", None)
    with pytest.raises(RuntimeError, match="multiple alembic heads"):
        emit.parse_alembic_head(fake_versions_dir)


def test_parse_alembic_head_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not found"):
        emit.parse_alembic_head(tmp_path / "nope")


# ---------------------------------------------------------------------------
# JSON-seed patch
# ---------------------------------------------------------------------------


def test_compute_seed_patch_resolves_unique_match(
    fake_seed: dict[str, Any],
) -> None:
    decision = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="A80",
        new_generation_name="A80 (JZA80)",
        corpus_count=12,
        retailer_count=3,
        edit_distance=9,
    )
    diff = emit._compute_seed_patch(fake_seed, decision)
    assert diff["make"] == "Toyota"
    assert diff["model_index"] == 0
    assert diff["gen_index"] == 0
    assert diff["pinned_slug"] == "a80"


def test_compute_seed_patch_rejects_noop(fake_seed: dict[str, Any]) -> None:
    decision = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="A80",
        new_generation_name="A80",
        corpus_count=0,
        retailer_count=0,
        edit_distance=0,
    )
    with pytest.raises(ValueError, match="noop_rename_rejected"):
        emit._compute_seed_patch(fake_seed, decision)


def test_compute_seed_patch_rejects_unknown_old_name(
    fake_seed: dict[str, Any],
) -> None:
    decision = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="DOES-NOT-EXIST",
        new_generation_name="X",
        corpus_count=0,
        retailer_count=0,
        edit_distance=0,
    )
    with pytest.raises(ValueError, match="canonical_id_not_in_seed"):
        emit._compute_seed_patch(fake_seed, decision)


def test_compute_seed_patch_detects_slug_collision(
    fake_seed: dict[str, Any],
) -> None:
    # Insert a sibling generation whose slug already equals slugify("A80") = "a80".
    fake_seed["Toyota"][0]["generations"].append(
        {
            "generation_name": "A80 Variant",
            "slug": "a80",  # explicit pinned slug
            "start_year": 1995,
            "end_year": 2002,
        }
    )
    decision = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="A80",
        new_generation_name="A80 (JZA80)",
        corpus_count=12,
        retailer_count=3,
        edit_distance=9,
    )
    with pytest.raises(ValueError, match="slug_collision_detected"):
        emit._compute_seed_patch(fake_seed, decision)


def test_patch_seed_dry_run_does_not_mutate_file(seed_file: Path) -> None:
    decision = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="A80",
        new_generation_name="A80 (JZA80)",
        corpus_count=12,
        retailer_count=3,
        edit_distance=9,
    )
    before = seed_file.read_text(encoding="utf-8")
    emit.patch_seed(seed_path=seed_file, decision=decision, apply=False)
    after = seed_file.read_text(encoding="utf-8")
    assert before == after


def test_patch_seed_apply_writes_new_name_and_pins_old_slug(seed_file: Path) -> None:
    decision = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="A80",
        new_generation_name="A80 (JZA80)",
        corpus_count=12,
        retailer_count=3,
        edit_distance=9,
    )
    emit.patch_seed(seed_path=seed_file, decision=decision, apply=True)
    patched = json.loads(seed_file.read_text(encoding="utf-8"))
    gen = patched["Toyota"][0]["generations"][0]
    assert gen["generation_name"] == "A80 (JZA80)"
    assert gen["slug"] == "a80"  # OLD slugify form pinned

    # Unrelated row untouched.
    bmw = patched["BMW"][0]["generations"][0]
    assert bmw["generation_name"] == "E46"
    assert "slug" not in bmw


def test_patch_seed_apply_idempotent_within_same_make(seed_file: Path) -> None:
    """Applying the same rename twice should succeed (no-op the second time)
    OR fail with canonical_id_not_in_seed because old name is gone — either is
    acceptable, as long as the file isn't corrupted.
    """
    decision = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="A80",
        new_generation_name="A80 (JZA80)",
        corpus_count=12,
        retailer_count=3,
        edit_distance=9,
    )
    emit.patch_seed(seed_path=seed_file, decision=decision, apply=True)
    # Second call: old_name no longer present.
    with pytest.raises(ValueError, match="canonical_id_not_in_seed"):
        emit.patch_seed(seed_path=seed_file, decision=decision, apply=True)
    # File still parses cleanly.
    json.loads(seed_file.read_text(encoding="utf-8"))


def test_patch_seed_flock_mutual_exclusion(seed_file: Path) -> None:
    """A second writer must block until the first releases the flock."""
    decision_a = emit.Decision(
        canonical_id=A80_ID,
        old_generation_name="A80",
        new_generation_name="A80 (JZA80)",
        corpus_count=1,
        retailer_count=1,
        edit_distance=1,
    )

    blocker_acquired = threading.Event()
    release_blocker = threading.Event()

    def _hold_lock() -> None:
        with seed_file.open("r+", encoding="utf-8") as fp:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
            blocker_acquired.set()
            release_blocker.wait(timeout=5.0)
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)

    blocker = threading.Thread(target=_hold_lock)
    blocker.start()
    blocker_acquired.wait(timeout=2.0)

    # Now patch_seed should block until the blocker releases.
    result_holder: dict[str, Any] = {}

    def _try_patch() -> None:
        try:
            emit.patch_seed(seed_path=seed_file, decision=decision_a, apply=True)
            result_holder["ok"] = True
        except Exception as exc:  # pragma: no cover — surfaces on test failure
            result_holder["error"] = exc

    writer = threading.Thread(target=_try_patch)
    writer.start()
    # Give the writer a moment to attempt the lock and confirm it hasn't progressed.
    time.sleep(0.3)
    assert "ok" not in result_holder, "writer should be blocked on flock"

    # Release and let the writer complete.
    release_blocker.set()
    blocker.join(timeout=3.0)
    writer.join(timeout=3.0)
    assert result_holder.get("ok") is True


# ---------------------------------------------------------------------------
# Ambiguity-AST audit
# ---------------------------------------------------------------------------


def test_ambiguity_audit_clean_returns_none(clean_ambiguity_test: Path) -> None:
    assert emit.ambiguity_audit(clean_ambiguity_test, "ZZ-NOT-PRESENT") is None


def test_ambiguity_audit_detects_string_constant(clean_ambiguity_test: Path) -> None:
    hit = emit.ambiguity_audit(clean_ambiguity_test, "Cusco MKV Supra")
    assert hit is not None
    line, snippet = hit
    assert line > 0
    assert "Cusco MKV Supra" in snippet


def test_ambiguity_audit_unreadable_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="ambiguity_test_unreadable"):
        emit.ambiguity_audit(tmp_path / "nope.py", "anything")


def test_ambiguity_audit_unparsable_python(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ambiguity_test_unreadable"):
        emit.ambiguity_audit(bad, "anything")


# ---------------------------------------------------------------------------
# CLI wiring (dry-run + apply)
# ---------------------------------------------------------------------------


def _cli_args(
    *,
    versions_dir: Path,
    seed_path: Path,
    ambiguity_path: Path,
    csv_path: Path | None = None,
    decision_json: str | None = None,
    apply: bool = False,
    from_csv_row: int | None = None,
) -> list[str]:
    args = [
        "--versions-dir",
        str(versions_dir),
        "--seed-path",
        str(seed_path),
        "--ambiguity-test-path",
        str(ambiguity_path),
    ]
    if csv_path is not None:
        args.extend(["--csv-path", str(csv_path)])
    if from_csv_row is not None:
        args.extend(["--from-csv-row", str(from_csv_row)])
    if decision_json is not None:
        args.extend(["--decision-json", decision_json])
    if apply:
        args.append("--apply")
    return args


def test_cli_dry_run_emits_plan_and_writes_nothing(
    fake_versions_dir: Path,
    seed_file: Path,
    clean_ambiguity_test: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = json.dumps(
        {
            "canonical_id": str(A80_ID),
            "old_generation_name": "A80",
            "new_generation_name": "A80 (JZA80)",
            "corpus_count": 12,
            "retailer_count": 3,
            "edit_distance": 9,
        }
    )
    rc = emit.main(
        _cli_args(
            versions_dir=fake_versions_dir,
            seed_path=seed_file,
            ambiguity_path=clean_ambiguity_test,
            decision_json=payload,
        )
    )
    assert rc == 0
    captured = capsys.readouterr().out.strip().splitlines()
    plan = json.loads(captured[0])
    assert plan["event"] == "rename_plan"
    assert plan["down_revision"] == "cccccccccccc"
    assert plan["seed_diff"]["pinned_slug"] == "a80"
    # Nothing on disk.
    assert not any(p.name.endswith("_m004_rename_a80_to_a80_jza80.py") for p in fake_versions_dir.iterdir())
    assert json.loads(seed_file.read_text(encoding="utf-8"))["Toyota"][0]["generations"][0]["generation_name"] == "A80"


def test_cli_apply_writes_migration_and_patches_seed(
    fake_versions_dir: Path,
    seed_file: Path,
    clean_ambiguity_test: Path,
) -> None:
    payload = json.dumps(
        {
            "canonical_id": str(A80_ID),
            "old_generation_name": "A80",
            "new_generation_name": "A80 (JZA80)",
            "corpus_count": 12,
            "retailer_count": 3,
            "edit_distance": 9,
        }
    )
    rc = emit.main(
        _cli_args(
            versions_dir=fake_versions_dir,
            seed_path=seed_file,
            ambiguity_path=clean_ambiguity_test,
            decision_json=payload,
            apply=True,
        )
    )
    assert rc == 0
    matches = [p for p in fake_versions_dir.iterdir() if "_m004_rename_a80_to_a80_jza80" in p.name]
    assert len(matches) == 1, f"expected exactly one emitted migration, got {matches}"
    body = matches[0].read_text(encoding="utf-8")
    # Hand-written op.execute with named bind params.
    assert "op.execute(" in body
    assert "sa.text(" in body
    assert "UPDATE car_generations SET generation_name = :new_name WHERE id = :id" in body
    assert "UPDATE car_generations SET generation_name = :old_name WHERE id = :id" in body
    assert f'CANONICAL_ID = uuid.UUID("{A80_ID}")' in body
    assert 'sa.bindparam("id", value=CANONICAL_ID, type_=sa.Uuid(as_uuid=True))' in body
    compile(body, str(matches[0]), "exec")
    # Audit-trail tuple in docstring.
    assert "corpus_count     = 12" in body
    assert "retailer_count   = 3" in body
    assert "edit_distance    = 9" in body
    # Down-revision chains off the head.
    assert 'down_revision: Union[str, None] = "cccccccccccc"' in body
    # Seed patched.
    patched = json.loads(seed_file.read_text(encoding="utf-8"))
    gen = patched["Toyota"][0]["generations"][0]
    assert gen["generation_name"] == "A80 (JZA80)"
    assert gen["slug"] == "a80"


def test_cli_blocks_on_ambiguity_collision(
    fake_versions_dir: Path,
    seed_file: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Counterexample test file references the OLD name as a string constant.
    polluted = tmp_path / "test_car_inference_ambiguity.py"
    polluted.write_text(
        '"""collision lives here."""\n' 'VECTORS = [("Cusco A80 mention", "blah", None, "case")]\n',
        encoding="utf-8",
    )
    payload = json.dumps(
        {
            "canonical_id": str(A80_ID),
            "old_generation_name": "A80",
            "new_generation_name": "A80 (JZA80)",
        }
    )
    rc = emit.main(
        _cli_args(
            versions_dir=fake_versions_dir,
            seed_path=seed_file,
            ambiguity_path=polluted,
            decision_json=payload,
        )
    )
    # Even though "A80" is a substring of "Cusco A80 mention", the audit only
    # matches exact string-constant equality. Confirm we get the *un*-blocked
    # path here, then prove the blocker on an exact match below.
    assert rc == 0  # substring should NOT block

    polluted.write_text(
        '"""collision lives here."""\n' 'VECTORS = [("A80", "exact constant", None, "case")]\n',
        encoding="utf-8",
    )
    rc = emit.main(
        _cli_args(
            versions_dir=fake_versions_dir,
            seed_path=seed_file,
            ambiguity_path=polluted,
            decision_json=payload,
        )
    )
    assert rc == 1


def test_cli_rejects_noop_rename(
    fake_versions_dir: Path,
    seed_file: Path,
    clean_ambiguity_test: Path,
) -> None:
    payload = json.dumps(
        {
            "canonical_id": str(A80_ID),
            "old_generation_name": "A80",
            "new_generation_name": "A80",
        }
    )
    rc = emit.main(
        _cli_args(
            versions_dir=fake_versions_dir,
            seed_path=seed_file,
            ambiguity_path=clean_ambiguity_test,
            decision_json=payload,
        )
    )
    assert rc == 1


def test_cli_rejects_canonical_id_not_in_seed(
    fake_versions_dir: Path,
    seed_file: Path,
    clean_ambiguity_test: Path,
) -> None:
    payload = json.dumps(
        {
            "canonical_id": str(ABSENT_ID),
            "old_generation_name": "ZZZ-NOT-PRESENT",
            "new_generation_name": "Anything",
        }
    )
    rc = emit.main(
        _cli_args(
            versions_dir=fake_versions_dir,
            seed_path=seed_file,
            ambiguity_path=clean_ambiguity_test,
            decision_json=payload,
        )
    )
    assert rc == 1


def test_cli_subprocess_smoke_invocation(
    fake_versions_dir: Path,
    seed_file: Path,
    clean_ambiguity_test: Path,
) -> None:
    """Mirrors the slice-plan invocation form: ``python -m scripts.m004_emit_rename``."""
    payload = json.dumps(
        {
            "canonical_id": str(A80_ID),
            "old_generation_name": "A80",
            "new_generation_name": "A80 (JZA80)",
            "corpus_count": 12,
            "retailer_count": 3,
            "edit_distance": 9,
        }
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.m004_emit_rename",
            "--versions-dir",
            str(fake_versions_dir),
            "--seed-path",
            str(seed_file),
            "--ambiguity-test-path",
            str(clean_ambiguity_test),
            "--decision-json",
            payload,
        ],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONPATH": str(_BACKEND_DIR)},
    )
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout.strip().splitlines()[0])
    assert plan["event"] == "rename_plan"
    assert plan["down_revision"] == "cccccccccccc"
