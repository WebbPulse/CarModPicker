"""Pins terraform/dynamodb_tables.json against app/db/dynamo/tables.py.

Regenerate with python scripts/export_dynamo_tables.py and commit the result alongside the spec change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = BACKEND_DIR.parent / "terraform" / "dynamodb_tables.json"


def _render() -> str:
    """Render the exporter's current output by importing it from backend/scripts."""
    scripts_dir = str(BACKEND_DIR / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from export_dynamo_tables import render

    return render()


def test_dynamodb_tables_json_matches_specs() -> None:
    """The committed JSON matches what the exporter renders today."""
    actual = _render()
    expected = SNAPSHOT_PATH.read_text(encoding="utf-8")

    if actual != expected:
        msg = (
            "terraform/dynamodb_tables.json is out of date with app/db/dynamo/tables.py.\n"
            "Regenerate it and commit the result:\n"
            "\n"
            "    cd backend\n"
            "    python scripts/export_dynamo_tables.py\n"
        )
        assert actual == expected, msg


def test_dynamodb_tables_json_covers_every_spec() -> None:
    """Every declared table appears in the export with the right hash key and index names."""
    from app.db.dynamo.tables import TABLES

    exported = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert set(exported) == {spec.suffix for spec in TABLES}
    for spec in TABLES:
        definition = exported[spec.suffix]
        assert definition["hash_key"] == spec.partition_key.name
        assert {index["name"] for index in definition["global_secondary_indexes"]} == {
            index.name for index in spec.indexes
        }
