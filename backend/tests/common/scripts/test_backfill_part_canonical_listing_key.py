"""`scripts/backfill_part_canonical_listing_key.py` against moto."""

from __future__ import annotations

from typing import Any

from uuid6 import uuid7

from app.common.db.dynamo import client as dynamo_client
from app.common.db.dynamo.catalog import PartRepository
from app.common.db.dynamo.serialization import unique_lookup_key
from app.common.db.dynamo.tables import PART_CANONICAL_LISTING_ATTRIBUTE, PARTS
from scripts import backfill_part_canonical_listing_key as script
from tests.common.scripts.conftest import PREFIX


def _legacy_row(table: Any, created_at: str, canonical_part_id: str | None = None) -> str:
    """Write a part row as it was stored before the canonical index key existed."""
    part_id = str(uuid7())
    item = {
        "id": part_id,
        "name": "legacy",
        "category_id": str(uuid7()),
        "user_id": str(uuid7()),
        "created_at": created_at,
        "updated_at": created_at,
    }
    if canonical_part_id is not None:
        item["canonical_part_id"] = canonical_part_id
    table.put_item(Item=item)
    return part_id


def test_backfill_is_a_dry_run_then_idempotent(dynamo_tables: Any) -> None:
    """A dry run writes nothing, an apply keys every legacy canonical row only, and a rerun finds none."""
    table = dynamo_client.get_table(PARTS)
    older = _legacy_row(table, "2026-01-01T00:00:00.000000Z")
    newer = _legacy_row(table, "2026-01-02T00:00:00.000000Z")
    duplicate = _legacy_row(table, "2026-01-03T00:00:00.000000Z", canonical_part_id=older)
    table.put_item(Item={"id": unique_lookup_key("gtin", "012345678905")})
    repo = PartRepository()
    assert repo.list_canonical() == []

    script_table = script.build_table(PREFIX)
    assert script.backfill(script_table, apply=False) == {"missing": 2, "written": 0, "skipped": 0}
    assert repo.list_canonical() == []

    assert script.backfill(script_table, apply=True) == {"missing": 2, "written": 2, "skipped": 0}
    assert sorted(str(part.id) for part in repo.list_canonical()) == sorted([older, newer])
    duplicate_item = table.get_item(Key={"id": duplicate}).get("Item", {})
    assert duplicate_item and PART_CANONICAL_LISTING_ATTRIBUTE not in duplicate_item
    sentinel = table.get_item(Key={"id": unique_lookup_key("gtin", "012345678905")}).get("Item", {})
    assert sentinel and PART_CANONICAL_LISTING_ATTRIBUTE not in sentinel

    assert script.backfill(script_table, apply=True) == {"missing": 0, "written": 0, "skipped": 0}


def test_main_reports_the_summary(dynamo_tables: Any, capsys: Any) -> None:
    """The command line run prints what it found and wrote."""
    _legacy_row(dynamo_client.get_table(PARTS), "2026-01-01T00:00:00.000000Z")

    assert script.main(["--prefix", PREFIX, "--apply"]) == 0
    assert "applied: 1 missing, 1 written, 0 skipped" in capsys.readouterr().out
