"""`scripts/backfill_build_list_listing_key.py` against moto."""

from __future__ import annotations

from typing import Any

from uuid6 import uuid7

from app.common.db.dynamo import client as dynamo_client
from app.common.db.dynamo.build_lists import BuildListRepository
from app.common.db.dynamo.serialization import unique_lookup_key
from app.common.db.dynamo.tables import BUILD_LISTS
from scripts import backfill_build_list_listing_key as script
from tests.common.scripts.conftest import PREFIX


def _legacy_row(table: Any, created_at: str) -> str:
    """Write a build list row as it was stored before the listing key existed."""
    build_list_id = str(uuid7())
    table.put_item(
        Item={
            "id": build_list_id,
            "name": "legacy",
            "user_id": str(uuid7()),
            "base_price_cents": 0,
            "created_at": created_at,
            "updated_at": created_at,
        }
    )
    return build_list_id


def test_backfill_is_a_dry_run_then_idempotent(dynamo_tables: Any) -> None:
    """A dry run writes nothing, an apply keys every legacy row, and a rerun finds none."""
    table = dynamo_client.get_table(BUILD_LISTS)
    older = _legacy_row(table, "2026-01-01T00:00:00.000000Z")
    newer = _legacy_row(table, "2026-01-02T00:00:00.000000Z")
    table.put_item(Item={"id": unique_lookup_key("name", "legacy")})
    repo = BuildListRepository()
    assert repo.all_public() == []

    script_table = script.build_table(PREFIX)
    assert script.backfill(script_table, apply=False) == {"missing": 2, "written": 0, "skipped": 0}
    assert repo.all_public() == []

    assert script.backfill(script_table, apply=True) == {"missing": 2, "written": 2, "skipped": 0}
    assert [str(bl.id) for bl in repo.all_public()] == [newer, older]
    sentinel = table.get_item(Key={"id": unique_lookup_key("name", "legacy")}).get("Item", {})
    assert sentinel and "listing" not in sentinel

    assert script.backfill(script_table, apply=True) == {"missing": 0, "written": 0, "skipped": 0}


def test_main_reports_the_summary(dynamo_tables: Any, capsys: Any) -> None:
    """The command line run prints what it found and wrote."""
    _legacy_row(dynamo_client.get_table(BUILD_LISTS), "2026-01-01T00:00:00.000000Z")

    assert script.main(["--prefix", PREFIX, "--apply"]) == 0
    assert "applied: 1 missing, 1 written, 0 skipped" in capsys.readouterr().out
