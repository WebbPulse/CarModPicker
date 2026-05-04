"""Unit tests for ``backend/scripts/m004_label_gold_set.py``.

Covers the auto-mode bootstrap path with the inline fixtures (no DB), plus the
negative paths called out in T04-PLAN.md:

* fixture-bootstrap from a clean tmp_path produces a valid gold-set file
* every row carries the locked schema fields and ``labeled_by``
* ``--resume`` against an existing file does NOT duplicate part_ids
* malformed parts.json fails loud at startup with ``GoldSetLoadError``
* the strata report is written and reflects the actual rows

The DB iterator is patched to a no-op so the tests deterministically take the
fixture-fallback branch without depending on Postgres / app.* import success.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import m004_label_gold_set as labeler
from scripts.m004_bootstrap_fixtures import BOOTSTRAP_FIXTURES


@pytest.fixture
def force_fixture_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``_iterate_db_pages`` always yield nothing → fixture fallback."""

    def _empty(_target: int, _log: Any) -> Any:
        return iter(())

    monkeypatch.setattr(labeler, "_iterate_db_pages", _empty)


def _gold_path(tmp_path: Path) -> Path:
    return tmp_path / "gold-set" / "parts.json"


def _strata_path(tmp_path: Path) -> Path:
    return tmp_path / "gold-set" / "sampling-strata.json"


# ---------------------------------------------------------------------------
# Bootstrap → fixture fallback
# ---------------------------------------------------------------------------


class TestBootstrapFromFixtures:
    def test_writes_all_required_keys(
        self, tmp_path: Path, force_fixture_path: None
    ) -> None:
        out = _gold_path(tmp_path)
        strata = _strata_path(tmp_path)
        rc = labeler.main(
            [
                "--bootstrap",
                "5",
                "--out",
                str(out),
                "--strata-out",
                str(strata),
            ]
        )
        assert rc == 0
        data = json.loads(out.read_text())
        assert isinstance(data, list)
        assert len(data) == 5
        for row in data:
            for k in labeler.REQUIRED_ROW_KEYS:
                assert k in row, f"row missing required key {k!r}"
            assert row["labeled_by"] == "bootstrap-ground-truth"
            assert row["tier"] in {"T0", "T1", "T2"}
            # html_excerpt must be a string and non-empty for these fixtures.
            assert isinstance(row["html_excerpt"], str)
            assert row["html_excerpt"]
            # truth_car_triples must be a list (empty in this iteration).
            assert isinstance(row["truth_car_triples"], list)

    def test_truncated_bootstrap_picks_first_n(
        self, tmp_path: Path, force_fixture_path: None
    ) -> None:
        out = _gold_path(tmp_path)
        strata = _strata_path(tmp_path)
        rc = labeler.main(
            [
                "--bootstrap",
                "3",
                "--out",
                str(out),
                "--strata-out",
                str(strata),
            ]
        )
        assert rc == 0
        data = json.loads(out.read_text())
        assert len(data) == 3
        expected = [BOOTSTRAP_FIXTURES[i]["part_id"] for i in range(3)]
        assert [row["part_id"] for row in data] == expected

    def test_at_least_one_jsonld_brand_extracted(
        self, tmp_path: Path, force_fixture_path: None
    ) -> None:
        """The first fixture has JSON-LD with 'KW Suspensions' as brand —
        ensure the bootstrap labeler actually runs truth_from_html and
        propagates the manufacturer field, not just the empty default."""
        out = _gold_path(tmp_path)
        labeler.main(
            ["--bootstrap", "5", "--out", str(out), "--strata-out", str(_strata_path(tmp_path))]
        )
        data = json.loads(out.read_text())
        manufacturers = [row["truth_manufacturer"] for row in data]
        # At least one fixture must produce a non-null manufacturer or the
        # ground-truth wiring is broken.
        assert any(m for m in manufacturers), (
            f"no fixture produced a non-null truth_manufacturer; "
            f"truth_from_html may not be wired up. got: {manufacturers}"
        )


# ---------------------------------------------------------------------------
# Resume idempotency
# ---------------------------------------------------------------------------


class TestResumeIdempotent:
    def test_second_run_does_not_duplicate(
        self, tmp_path: Path, force_fixture_path: None
    ) -> None:
        out = _gold_path(tmp_path)
        strata = _strata_path(tmp_path)
        # First run: write 5 fixture rows.
        labeler.main(
            ["--bootstrap", "5", "--out", str(out), "--strata-out", str(strata)]
        )
        first = json.loads(out.read_text())
        assert len(first) == 5
        first_ids = [r["part_id"] for r in first]

        # Second run with --resume + same target: no new rows added because
        # all fixture part_ids are already present.
        rc = labeler.main(
            [
                "--bootstrap",
                "5",
                "--resume",
                "--out",
                str(out),
                "--strata-out",
                str(strata),
            ]
        )
        assert rc == 0
        second = json.loads(out.read_text())
        assert len(second) == 5
        # Part IDs unchanged and unique.
        second_ids = [r["part_id"] for r in second]
        assert second_ids == first_ids
        assert len(set(second_ids)) == 5

    def test_partial_resume_appends_only_missing(
        self, tmp_path: Path, force_fixture_path: None
    ) -> None:
        out = _gold_path(tmp_path)
        strata = _strata_path(tmp_path)
        # First: bootstrap 2 fixtures.
        labeler.main(
            ["--bootstrap", "2", "--out", str(out), "--strata-out", str(strata)]
        )
        assert len(json.loads(out.read_text())) == 2
        # Then: resume with target 5 — should add the remaining 3.
        labeler.main(
            [
                "--bootstrap",
                "5",
                "--resume",
                "--out",
                str(out),
                "--strata-out",
                str(strata),
            ]
        )
        rows = json.loads(out.read_text())
        assert len(rows) == 5
        ids = [r["part_id"] for r in rows]
        assert len(set(ids)) == 5


# ---------------------------------------------------------------------------
# Negative tests — malformed file fails loud
# ---------------------------------------------------------------------------


class TestMalformedFileFailsLoud:
    def test_invalid_json_raises_load_error(self, tmp_path: Path) -> None:
        out = _gold_path(tmp_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(labeler.GoldSetLoadError) as exc_info:
            labeler.load_gold_set(out)
        assert "not valid JSON" in str(exc_info.value)

    def test_non_list_root_raises(self, tmp_path: Path) -> None:
        out = _gold_path(tmp_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"oops": "wrong shape"}), encoding="utf-8")
        with pytest.raises(labeler.GoldSetLoadError) as exc_info:
            labeler.load_gold_set(out)
        assert "must be a JSON array" in str(exc_info.value)

    def test_missing_required_key_raises(self, tmp_path: Path) -> None:
        out = _gold_path(tmp_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        bad = [{"part_id": "x", "retailer": "y"}]  # missing most keys
        out.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(labeler.GoldSetLoadError) as exc_info:
            labeler.load_gold_set(out)
        assert "missing required key" in str(exc_info.value)

    def test_invalid_tier_raises(self, tmp_path: Path) -> None:
        out = _gold_path(tmp_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        bad = [
            {
                "part_id": "x",
                "retailer": "ind",
                "category": "Suspension",
                "tier": "T9",  # invalid
                "raw_name": "n",
                "raw_description": "d",
                "html_excerpt": "h",
                "truth_car_triples": [],
                "truth_manufacturer": None,
                "truth_category": None,
                "labeled_at": "2026-04-27T00:00:00Z",
                "labeled_by": "human",
            }
        ]
        out.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(labeler.GoldSetLoadError) as exc_info:
            labeler.load_gold_set(out)
        assert "tier" in str(exc_info.value)

    def test_invalid_labeled_by_raises(self, tmp_path: Path) -> None:
        out = _gold_path(tmp_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        bad = [
            {
                "part_id": "x",
                "retailer": "ind",
                "category": "Suspension",
                "tier": "T0",
                "raw_name": "n",
                "raw_description": "d",
                "html_excerpt": "h",
                "truth_car_triples": [],
                "truth_manufacturer": None,
                "truth_category": None,
                "labeled_at": "2026-04-27T00:00:00Z",
                "labeled_by": "robot",  # invalid
            }
        ]
        out.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(labeler.GoldSetLoadError) as exc_info:
            labeler.load_gold_set(out)
        assert "labeled_by" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Strata report
# ---------------------------------------------------------------------------


class TestStrataReport:
    def test_strata_report_counts_match_rows(
        self, tmp_path: Path, force_fixture_path: None
    ) -> None:
        out = _gold_path(tmp_path)
        strata = _strata_path(tmp_path)
        labeler.main(
            ["--bootstrap", "5", "--out", str(out), "--strata-out", str(strata)]
        )
        assert strata.exists()
        report = json.loads(strata.read_text())
        assert report["total_rows"] == 5
        # Sum of per-bin counts equals total.
        assert sum(b["count"] for b in report["bins"]) == 5
        # Bins reflect the fixture diversity — at least 3 distinct retailers.
        retailers = {b["retailer"] for b in report["bins"]}
        assert len(retailers) >= 3


# ---------------------------------------------------------------------------
# Tier helper
# ---------------------------------------------------------------------------


class TestAdapterToTier:
    def test_known_t0_adapter(self) -> None:
        assert labeler.adapter_to_tier("ind") == "T0"
        assert labeler.adapter_to_tier("hondata") == "T0"

    def test_known_t1_adapter(self) -> None:
        assert labeler.adapter_to_tier("rallysportdirect") == "T1"

    def test_unknown_adapter_defaults_t2(self) -> None:
        assert labeler.adapter_to_tier("totally-made-up") == "T2"
        assert labeler.adapter_to_tier(None) == "T2"
        assert labeler.adapter_to_tier("") == "T2"
