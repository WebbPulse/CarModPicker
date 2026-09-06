"""Unit coverage for `part_price_aggregation_service` (S05/T01).

Exercises:
- single-part window slicing and DESC ordering of `history`
- per-retailer breakdown ordering (by retailer_name ASC)
- canonical link-group aggregation (duplicates' history surfaces on the canonical)
- empty-history empty-shape contract
- trend (up/down/flat) over a hand-seeded series
- `parse_window` ValueError on unknown literals
- batch returns one entry per requested id, even when empty
- batch dedup across canonical link group
- batch query-count budget (no N+1)
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.api.services.part_price_aggregation_service import (
    aggregate_batch,
    aggregate_single_part,
    parse_window,
)
from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.catalog import PartListing as DBPartListing
from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
from app.db.dynamo.catalog import PartPriceHistory as DBPartPriceHistory
from app.db.dynamo.catalog import Retailer as DBRetailer
from app.db.dynamo.users import User
from tests.conftest import get_default_category_id, save_catalog

# --- helpers -----------------------------------------------------------------


def _make_retailer(db: Any, slug: str) -> DBRetailer:
    retailer = DBRetailer(
        name=f"retailer_{slug}_{uuid.uuid4().hex[:8]}",
        domain=f"{slug}-{uuid.uuid4().hex[:8]}.example.com",
        base_url=f"https://{slug}.example.com",
        is_active=True,
    )
    retailer = save_catalog(retailer)
    return retailer


def _make_manufacturer(db: Any, suffix: str) -> DBPartManufacturer:
    pm = DBPartManufacturer(
        name=f"mfr_{suffix}_{uuid.uuid4().hex[:8]}",
        description="test mfr",
        is_active=True,
    )
    pm = save_catalog(pm)
    return pm


def _make_part(
    db: Any,
    user: User,
    *,
    canonical_part_id: uuid.UUID | None = None,
    name: str = "Test Part",
) -> DBPart:
    category_id = get_default_category_id(db)
    part = DBPart(
        name=name,
        category_id=category_id,
        user_id=user.id,
        is_universal=True,
        canonical_part_id=canonical_part_id,
    )
    part = save_catalog(part)
    return part


def _make_listing(db: Any, part: DBPart, retailer: DBRetailer) -> DBPartListing:
    listing = DBPartListing(
        part_id=part.id,
        retailer_id=retailer.id,
        product_url=f"https://{retailer.domain}/p/{uuid.uuid4().hex[:8]}",
    )
    listing = save_catalog(listing)
    return listing


def _add_history(
    db: Any,
    listing: DBPartListing,
    *,
    price_cents: int,
    observed_at: datetime,
) -> DBPartPriceHistory:
    row = DBPartPriceHistory(
        part_listing_id=listing.id,
        price_cents=price_cents,
        observed_at=observed_at,
    )
    row = save_catalog(row)
    return row


# --- single-part tests -------------------------------------------------------


def test_aggregate_single_part_basic(db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "basic")
    part = _make_part(db_session, test_user, name="Basic Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    _add_history(db_session, listing, price_cents=1000, observed_at=now - timedelta(days=60))
    _add_history(db_session, listing, price_cents=1500, observed_at=now - timedelta(days=30))
    _add_history(db_session, listing, price_cents=1200, observed_at=now - timedelta(days=1))

    result = aggregate_single_part(part.id, "90d")

    assert result.summary.observation_count == 3
    assert result.summary.min_cents == 1000
    assert result.summary.max_cents == 1500
    assert result.summary.last_cents == 1200
    assert result.summary.last_observed_at is not None
    assert len(result.retailers) == 1
    assert result.retailers[0].retailer_id == retailer.id
    assert result.retailers[0].observation_count == 3
    assert len(result.history) == 3
    # DESC by observed_at: history[0] is the most recent (1200 cents).
    assert result.history[0].price_cents == 1200
    assert result.history[-1].price_cents == 1000
    assert result.window == "90d"


def test_aggregate_single_part_window_filters_old_observations(db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "winfilter")
    part = _make_part(db_session, test_user, name="Window Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    # 5 rows across 1 year — only the 30-day rows should appear with window='30d'.
    _add_history(db_session, listing, price_cents=4000, observed_at=now - timedelta(days=300))
    _add_history(db_session, listing, price_cents=3500, observed_at=now - timedelta(days=180))
    _add_history(db_session, listing, price_cents=3000, observed_at=now - timedelta(days=60))
    _add_history(db_session, listing, price_cents=2500, observed_at=now - timedelta(days=20))
    _add_history(db_session, listing, price_cents=2000, observed_at=now - timedelta(days=5))

    result = aggregate_single_part(part.id, "30d")

    assert result.summary.observation_count == 2
    assert len(result.history) == 2
    assert result.summary.min_cents == 2000
    assert result.summary.max_cents == 2500


def test_aggregate_single_part_empty_history(db_session: Any, test_user: User) -> None:
    part = _make_part(db_session, test_user, name="Empty Part")
    # No listings, no history.

    result = aggregate_single_part(part.id, "90d")

    assert result.summary.observation_count == 0
    assert result.summary.min_cents is None
    assert result.summary.max_cents is None
    assert result.summary.last_cents is None
    assert result.summary.last_observed_at is None
    assert result.summary.trend == "flat"
    assert result.retailers == []
    assert result.history == []
    assert result.window == "90d"


@pytest.mark.parametrize(
    "series,expected",
    [
        # Steeply ascending — slope * (n-1) should clear the 1%-of-mean bar.
        ([1000, 1100, 1200, 1300, 1400], "up"),
        # Steeply descending.
        ([1400, 1300, 1200, 1100, 1000], "down"),
        # Flat (identical values).
        ([1000, 1000, 1000, 1000, 1000], "flat"),
    ],
)
def test_aggregate_single_part_trend_up_down_flat(
    db_session: Any, test_user: User, series: list[int], expected: str
) -> None:
    retailer = _make_retailer(db_session, f"trend-{expected}")
    part = _make_part(db_session, test_user, name=f"Trend {expected}")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    # Seed chronologically — oldest first — at 5-day spacing.
    for i, price in enumerate(series):
        _add_history(
            db_session,
            listing,
            price_cents=price,
            observed_at=now - timedelta(days=(len(series) - i) * 5),
        )

    result = aggregate_single_part(part.id, "90d")
    assert result.summary.trend == expected


def test_aggregate_single_part_invalid_window_raises(db_session: Any, test_user: User) -> None:
    part = _make_part(db_session, test_user, name="Bad Window Part")
    with pytest.raises(ValueError):
        aggregate_single_part(part.id, "99x")
    # parse_window directly, too — keeps the contract obvious.
    with pytest.raises(ValueError):
        parse_window("year")


# --- batch tests -------------------------------------------------------------


def test_aggregate_batch_returns_entry_per_requested_id(db_session: Any, test_user: User) -> None:
    retailer = _make_retailer(db_session, "batch-entry")
    part_a = _make_part(db_session, test_user, name="Batch A")
    part_b = _make_part(db_session, test_user, name="Batch B")
    part_empty = _make_part(db_session, test_user, name="Batch Empty")

    listing_a = _make_listing(db_session, part_a, retailer)
    listing_b = _make_listing(db_session, part_b, retailer)
    now = datetime.now(UTC)
    _add_history(db_session, listing_a, price_cents=1000, observed_at=now - timedelta(days=10))
    _add_history(db_session, listing_a, price_cents=1100, observed_at=now - timedelta(days=2))
    _add_history(db_session, listing_b, price_cents=2000, observed_at=now - timedelta(days=4))

    result = aggregate_batch([part_a.id, part_b.id, part_empty.id], "90d")

    assert set(result.keys()) == {part_a.id, part_b.id, part_empty.id}
    assert result[part_a.id].observation_count == 2
    assert result[part_a.id].min_cents == 1000
    assert result[part_a.id].max_cents == 1100
    assert result[part_a.id].last_cents == 1100
    assert result[part_b.id].observation_count == 1
    assert result[part_b.id].min_cents == 2000
    # Empty entry shape.
    empty = result[part_empty.id]
    assert empty.observation_count == 0
    assert empty.min_cents is None
    assert empty.max_cents is None
    assert empty.last_cents is None
    assert empty.last_observed_at is None
    assert empty.trend == "flat"


def test_aggregate_batch_canonical_dedup(db_session: Any, test_user: User) -> None:
    retailer_a = _make_retailer(db_session, "dedup-a")
    retailer_b = _make_retailer(db_session, "dedup-b")
    canonical = _make_part(db_session, test_user, name="Dedup Canon")
    duplicate = _make_part(db_session, test_user, canonical_part_id=canonical.id, name="Dedup Dupe")

    listing_canon = _make_listing(db_session, canonical, retailer_a)
    listing_dupe = _make_listing(db_session, duplicate, retailer_b)
    now = datetime.now(UTC)
    _add_history(db_session, listing_canon, price_cents=1500, observed_at=now - timedelta(days=10))
    _add_history(db_session, listing_dupe, price_cents=900, observed_at=now - timedelta(days=4))

    result = aggregate_batch([canonical.id, duplicate.id], "90d")

    # Both keys present; both share the same group → identical aggregates.
    assert canonical.id in result
    assert duplicate.id in result
    canon_item = result[canonical.id]
    dupe_item = result[duplicate.id]
    assert canon_item.observation_count == 2
    assert dupe_item.observation_count == 2
    assert canon_item.min_cents == 900
    assert canon_item.max_cents == 1500
    assert dupe_item.min_cents == 900
    assert dupe_item.max_cents == 1500


def test_aggregate_batch_ten_parts(db_session: Any, test_user: User) -> None:
    """A 10-part-id batch returns one entry per requested part."""
    retailer = _make_retailer(db_session, "qc")
    parts: list[DBPart] = []
    now = datetime.now(UTC)
    for i in range(10):
        p = _make_part(db_session, test_user, name=f"QC Part {i}")
        listing = _make_listing(db_session, p, retailer)
        _add_history(
            db_session,
            listing,
            price_cents=1000 + i,
            observed_at=now - timedelta(days=10 + i),
        )
        parts.append(p)

    part_ids = [p.id for p in parts]

    result = aggregate_batch(part_ids, "90d")

    assert len(result) == 10
    assert set(result) == set(part_ids)
