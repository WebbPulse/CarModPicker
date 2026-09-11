"""Covers the DynamoDB table specifications and the name and client helpers built on them."""

import pytest

from app.core.config import settings
from app.db.dynamo import client as dynamo_client
from app.db.dynamo.tables import TABLES, KeyAttribute, TableSpec, gsi, table_by_suffix

EXPECTED_SUFFIXES = {
    "users",
    "oauth_accounts",
    "webauthn_credentials",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "retailers",
    "part_manufacturers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "part_price_alerts",
    "build_lists",
    "build_list_parts",
    "build_list_phases",
    "build_list_labor_estimates",
    "build_logs",
    "build_log_posts",
    "votes",
    "reports",
    "bug_reports",
    "image_source_mappings",
    "app_settings",
    "rate-limits",
}

DROPPED_SUFFIXES = {
    "crawled_pages",
    "crawler_schedules",
    "crawler_schedule_adapters",
    "crawler_adapter_configs",
    "background_jobs",
}


def test_every_surviving_entity_has_a_table() -> None:
    """Every surviving entity has exactly one declared table."""
    assert {spec.suffix for spec in TABLES} == EXPECTED_SUFFIXES


def test_crawler_remnants_are_excluded() -> None:
    """The retired crawler tables are not declared."""
    assert DROPPED_SUFFIXES.isdisjoint({spec.suffix for spec in TABLES})


def test_table_suffixes_are_unique() -> None:
    """No two specs claim the same table suffix."""
    suffixes = [spec.suffix for spec in TABLES]
    assert len(suffixes) == len(set(suffixes))


@pytest.mark.parametrize("spec", TABLES, ids=lambda spec: spec.suffix)
def test_index_names_are_unique_within_table(spec: TableSpec) -> None:
    """No table declares two indexes with the same name."""
    names = [index.name for index in spec.indexes]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("spec", TABLES, ids=lambda spec: spec.suffix)
def test_every_key_attribute_is_declared(spec: TableSpec) -> None:
    """Every attribute used in a key schema has a matching attribute definition."""
    request = spec.create_table_request("x")
    declared = {definition["AttributeName"] for definition in request["AttributeDefinitions"]}
    used = {entry["AttributeName"] for entry in request["KeySchema"]}
    for index in request.get("GlobalSecondaryIndexes", []):
        used.update(entry["AttributeName"] for entry in index["KeySchema"])
    assert used == declared


@pytest.mark.parametrize("spec", TABLES, ids=lambda spec: spec.suffix)
def test_derived_attributes_back_their_indexes(spec: TableSpec) -> None:
    """Every derived attribute is keyed by some index, so nothing is computed for nothing."""
    derived = {target for _, target in spec.lowercase_mirrors}
    derived.update(target for target, _ in spec.composite_keys)
    derived.update(target for target, _ in spec.coalesced_keys)
    for target in derived:
        keyed = any(
            index.hash_key.name == target or (index.range_key is not None and index.range_key.name == target)
            for index in spec.indexes
        )
        assert keyed, f"{spec.suffix}.{target} has no index"


def test_conflicting_attribute_types_are_rejected() -> None:
    """Two indexes giving one attribute different types is a ValueError."""
    spec = TableSpec(
        suffix="broken",
        indexes=(
            gsi("owner_id", "sort_order"),
            gsi("owner_id", "sort_order", name="other", numeric_range=True),
        ),
    )
    with pytest.raises(ValueError):
        spec.attribute_definitions()


def test_composite_table_key_schema() -> None:
    """A composite table declares both key parts and its reversed index."""
    spec = table_by_suffix("part_cars")
    assert spec.is_composite
    assert spec.key_schema() == [
        {"AttributeName": "part_id", "KeyType": "HASH"},
        {"AttributeName": "car_id", "KeyType": "RANGE"},
    ]
    assert spec.index("car_id-part_id-index").hash_key == KeyAttribute("car_id", "S")


def test_app_settings_uses_numeric_partition_key() -> None:
    """The app settings singleton keys on a numeric id."""
    assert table_by_suffix("app_settings").partition_key == KeyAttribute("id", "N")


def test_table_by_suffix_unknown() -> None:
    """An unknown suffix raises KeyError."""
    with pytest.raises(KeyError):
        table_by_suffix("nope")


def test_table_name_applies_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """The table name falls back to the environment when no prefix is configured."""
    monkeypatch.setattr(settings, "DYNAMODB_TABLE_PREFIX", "")
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "Production")
    assert dynamo_client.table_name(table_by_suffix("users")) == "carmodpicker-production-users"

    monkeypatch.setattr(settings, "DYNAMODB_TABLE_PREFIX", "custom")
    assert dynamo_client.table_name(table_by_suffix("users")) == "custom-users"


def test_tables_are_created_from_spec(dynamo_tables: object) -> None:
    """Creating from the specs yields every table with its declared indexes."""
    client = dynamo_client.get_client()
    existing = set(client.list_tables()["TableNames"])
    assert {dynamo_client.table_name(spec) for spec in TABLES} <= existing
    users = client.describe_table(TableName=dynamo_client.table_name(table_by_suffix("users")))["Table"]
    assert {index["IndexName"] for index in users["GlobalSecondaryIndexes"]} == {
        "username_lower-index",
        "email_lower-index",
    }


def test_reset_clients_forgets_cached_resource(dynamo_tables: object) -> None:
    """reset_clients drops the cached boto3 resource."""
    first = dynamo_client.get_resource()
    assert dynamo_client.get_resource() is first
    dynamo_client.reset_clients()
    assert dynamo_client.get_resource() is not first
