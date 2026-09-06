"""Row-level tests for scripts/backfill_from_postgres.py under moto."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

import pytest
from uuid6 import uuid7

from app.api.dependencies.repositories import get_repositories
from app.db.dynamo.users import CREDENTIAL_ID, EMAIL, USERNAME
from scripts import backfill_from_postgres as backfill

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _ids(count: int) -> list[UUID]:
    return [uuid7() for _ in range(count)]


def _stamped(**values: Any) -> dict[str, Any]:
    return {"created_at": NOW, "updated_at": NOW, **values}


def sample_rows() -> backfill.Rows:
    user_a, user_b = _ids(2)
    make, model, generation = _ids(3)
    category, retailer, manufacturer = _ids(3)
    canonical, linked = _ids(2)
    listing_a, listing_b = _ids(2)
    build_list = uuid7()
    return {
        "users": [
            _stamped(id=user_a, username="Alice", email="Alice@Example.com", hashed_password="x", image_urls=None),
            _stamped(id=user_b, username="bob", email="bob@example.com", hashed_password=None, image_urls=["a.png"]),
        ],
        "oauth_accounts": [
            {"id": uuid7(), "user_id": user_b, "provider": "google", "provider_account_id": "g-1", "created_at": NOW}
        ],
        "webauthn_credentials": [
            {
                "id": uuid7(),
                "user_id": user_a,
                "credential_id": b"cred-1",
                "public_key": b"\x00\x01",
                "sign_count": 3,
                "transports": ["usb"],
                "nickname": "key",
                "created_at": NOW,
            }
        ],
        "car_makes": [_stamped(id=make, name="Honda")],
        "car_models": [_stamped(id=model, car_make_id=make, slug="civic", name="Civic", display_name=None)],
        "car_generations": [
            _stamped(id=generation, car_model_id=model, slug="fk8", generation_name="FK8", start_year=2017)
        ],
        "categories": [_stamped(id=category, name="Intake")],
        "retailers": [_stamped(id=retailer, name="Shop", domain="shop.example")],
        "part_manufacturers": [_stamped(id=manufacturer, name="ACME")],
        "parts": [
            _stamped(
                id=canonical,
                name="Intake kit",
                category_id=category,
                user_id=user_a,
                part_manufacturer_id=manufacturer,
                part_number="AK-1",
                part_number_normalized="ak1",
                gtin="0123456789012",
                canonical_part_id=None,
            ),
            _stamped(
                id=linked,
                name="Intake kit (dupe)",
                category_id=category,
                user_id=user_b,
                part_manufacturer_id=manufacturer,
                part_number="AK-1",
                part_number_normalized="ak1",
                canonical_part_id=canonical,
            ),
        ],
        "part_cars": [{"part_id": canonical, "car_id": generation}],
        "part_listings": [
            _stamped(id=listing_a, part_id=canonical, retailer_id=retailer, last_known_price_cents=12000),
            _stamped(id=listing_b, part_id=linked, retailer_id=retailer, last_known_price_cents=9900),
        ],
        "votes": [
            _stamped(id=uuid7(), user_id=user_a, entity_type="part", entity_id=canonical, vote_type="upvote"),
            _stamped(id=uuid7(), user_id=user_b, entity_type="part", entity_id=canonical, vote_type="upvote"),
            _stamped(id=uuid7(), user_id=user_b, entity_type="part", entity_id=linked, vote_type="downvote"),
            _stamped(id=uuid7(), user_id=user_a, entity_type="build_list", entity_id=build_list, vote_type="upvote"),
        ],
        "build_lists": [_stamped(id=build_list, name="Track build", user_id=user_a, car_id=generation)],
        "build_logs": [],
        "app_settings": [{"id": 1, "premium_disabled": True, "updated_at": NOW}],
    }


class TestBuildPlan:
    def test_maps_every_row_and_fills_derived_part_attributes(self, dynamo_tables: Any) -> None:
        rows = sample_rows()
        plan = backfill.build_plan(rows, get_repositories())

        assert {table for table in plan.models} == set(backfill.TABLE_NAMES)
        for table, table_rows in rows.items():
            if table != "build_logs":
                assert plan.row_count(table) == len(table_rows), table

        parts = {str(part.id): part for part in plan.models["parts"]}
        canonical = parts[str(rows["parts"][0]["id"])]
        linked = parts[str(rows["parts"][1]["id"])]
        assert canonical.car_ids == [rows["part_cars"][0]["car_id"]]
        assert canonical.best_price_cents == 9900  # min across the link group
        assert linked.best_price_cents == 9900
        assert canonical.net_votes == 2
        assert linked.net_votes == -1

    def test_creates_the_missing_build_log(self, dynamo_tables: Any) -> None:
        rows = sample_rows()
        # psycopg2 returns uuid columns as strings; a list that already has a log must not get another.
        covered_list = str(uuid7())
        rows["build_lists"].append(
            _stamped(id=covered_list, name="Street build", user_id=rows["users"][0]["id"], car_id=None)
        )
        rows["build_logs"].append(
            _stamped(id=str(uuid7()), build_list_id=covered_list, title="Build Log: Street build")
        )
        plan = backfill.build_plan(rows, get_repositories())

        assert plan.created_build_logs == 1
        existing, log = plan.models["build_logs"]
        assert str(existing.build_list_id) == covered_list
        assert log.build_list_id == rows["build_lists"][0]["id"]
        assert log.title == "Build Log: Track build"
        assert log.id == uuid5(backfill.BUILD_LOG_NAMESPACE, str(rows["build_lists"][0]["id"]))
        assert backfill.build_plan(rows, get_repositories()).models["build_logs"][1].id == log.id

    def test_lookup_items_cover_users_oauth_webauthn_and_catalog(self, dynamo_tables: Any) -> None:
        plan = backfill.build_plan(sample_rows(), get_repositories())

        assert len(plan.lookups["users"]) == 4
        assert len(plan.lookups["oauth_accounts"]) == 2
        assert len(plan.lookups["webauthn_credentials"]) == 1
        assert len(plan.lookups["car_makes"]) == 1
        assert len(plan.lookups["car_models"]) == 2
        assert len(plan.lookups["retailers"]) == 2
        assert len(plan.lookups["parts"]) == 2  # gtin + manufacturer part number, canonical part only
        assert plan.lookups["votes"] == []

    def test_rejects_rows_that_collide_on_a_unique_attribute(self, dynamo_tables: Any) -> None:
        rows = sample_rows()
        rows["users"][1]["email"] = "ALICE@example.com"

        with pytest.raises(backfill.BackfillError, match="users: rows collide"):
            backfill.build_plan(rows, get_repositories())


class TestWritePlan:
    def test_round_trips_through_the_repositories(self, dynamo_tables: Any) -> None:
        rows = sample_rows()
        repos = get_repositories()
        plan = backfill.build_plan(rows, repos)

        backfill.write_plan(plan, repos)

        alice = repos.users.get_by_username("alice")
        assert alice is not None and alice.email == "Alice@Example.com"
        assert repos.users.is_unique_taken(USERNAME, "alice")
        assert repos.users.is_unique_taken(EMAIL, "alice@example.com")
        credential = repos.webauthn_credentials.get_by_credential_id(b"cred-1")
        assert credential is not None and credential.public_key == b"\x00\x01"
        assert repos.webauthn_credentials.is_unique_taken(CREDENTIAL_ID, credential and "Y3JlZC0x")
        assert repos.car_makes.get_by_name("honda") is not None
        assert repos.app_settings.get(1) is not None
        part = repos.parts.get_or_raise(str(rows["parts"][0]["id"]))
        assert part.best_price_cents == 9900 and part.net_votes == 2
        assert repos.build_logs.for_build_list(rows["build_lists"][0]["id"]) is not None

        counts = backfill.verify_counts(plan, repos)
        assert all(expected == found for expected, found in counts.values()), counts
        assert counts["users"] == (2, 2)  # lookups are not counted as rows

    def test_is_idempotent(self, dynamo_tables: Any) -> None:
        repos = get_repositories()
        plan = backfill.build_plan(sample_rows(), repos)

        backfill.write_plan(plan, repos)
        backfill.write_plan(plan, repos, tables=("users", "parts"))

        assert repos.users.count() == 2
        assert repos.parts.count() == 2


class FakeCursor:
    description = (("id",), ("blob",))

    def __init__(self) -> None:
        self.executed: list[str] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def execute(self, sql: str) -> None:
        self.executed.append(sql)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [(1, memoryview(b"raw"))]


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def close(self) -> None:
        return None


class TestFetchRows:
    def test_selects_each_table_and_converts_memoryviews(self) -> None:
        conn = FakeConnection()

        rows = backfill.fetch_rows(conn, tables=("users", "parts"))

        assert conn.cursor_obj.executed == ['SELECT * FROM "users"', 'SELECT * FROM "parts"']
        assert rows["users"] == [{"id": 1, "blob": b"raw"}]


class TestCli:
    def test_requires_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert backfill.main([]) == 2

    def test_rejects_unknown_tables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://example")
        assert backfill.main(["--tables", "users,nope"]) == 2

    def test_dry_run_reads_without_writing(self, dynamo_tables: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        rows = sample_rows()
        monkeypatch.setattr(backfill, "connect", lambda url: FakeConnection())
        monkeypatch.setattr(backfill, "fetch_rows", lambda conn: rows)

        assert backfill.main(["--database-url", "postgresql://example", "--dry-run"]) == 0
        assert get_repositories().users.count() == 0

    def test_writes_and_verifies(self, dynamo_tables: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        rows = sample_rows()
        monkeypatch.setattr(backfill, "connect", lambda url: FakeConnection())
        monkeypatch.setattr(backfill, "fetch_rows", lambda conn: rows)

        assert backfill.main(["--database-url", "postgresql://example", "--verify"]) == 0
        assert get_repositories().users.count() == 2

    def test_reports_collisions_as_failure(self, dynamo_tables: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        rows = sample_rows()
        rows["users"][1]["username"] = "ALICE"
        monkeypatch.setattr(backfill, "connect", lambda url: FakeConnection())
        monkeypatch.setattr(backfill, "fetch_rows", lambda conn: rows)

        assert backfill.main(["--database-url", "postgresql://example"]) == 1
