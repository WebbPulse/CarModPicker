"""Endpoint coverage for `GET /api/parts/{id}/price-history` (S05/T02).

Exercises the new aggregated object response + the `legacy=true` shim that
keeps the pre-S05 list shape until S13 audits all callers. Seeding mirrors
`tests/services/test_part_price_aggregation_service.py` so the per-row schema
matches what the aggregation service produces.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.retailer import Retailer as DBRetailer
from app.api.models.user import User
from tests.conftest import INVALID_UUID_STR, get_default_category_id

PRICE_HISTORY_PATH = "/api/parts/{part_id}/price-history"


# --- helpers (mirror tests/services/test_part_price_aggregation_service.py) --


def _make_retailer(db: Session, slug: str) -> DBRetailer:
    retailer = DBRetailer(
        name=f"retailer_{slug}_{uuid.uuid4().hex[:8]}",
        domain=f"{slug}-{uuid.uuid4().hex[:8]}.example.com",
        base_url=f"https://{slug}.example.com",
        is_active=True,
    )
    db.add(retailer)
    db.flush()
    return retailer


def _make_part(
    db: Session,
    user: User,
    *,
    canonical_part_id: uuid.UUID | None = None,
    name: str = "Test Part",
) -> DBPart:
    part = DBPart(
        name=name,
        category_id=get_default_category_id(db),
        user_id=user.id,
        is_universal=True,
        canonical_part_id=canonical_part_id,
        source="scraped",
    )
    db.add(part)
    db.flush()
    return part


def _make_listing(db: Session, part: DBPart, retailer: DBRetailer) -> DBPartListing:
    listing = DBPartListing(
        part_id=part.id,
        retailer_id=retailer.id,
        product_url=f"https://{retailer.domain}/p/{uuid.uuid4().hex[:8]}",
    )
    db.add(listing)
    db.flush()
    return listing


def _add_history(
    db: Session,
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
    db.add(row)
    db.flush()
    return row


# --- tests -------------------------------------------------------------------


def test_get_price_history_default_window_returns_summary_object(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    retailer = _make_retailer(db_session, "default-window")
    part = _make_part(db_session, test_user, name="Default Window Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    for i, price in enumerate([1000, 1100, 1200, 1300, 1400]):
        _add_history(db_session, listing, price_cents=price, observed_at=now - timedelta(days=10 + i))
    db_session.commit()

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id))
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict), f"expected object, got {type(body).__name__}"
    assert set(body.keys()) >= {"summary", "retailers", "history", "window"}
    assert body["window"] == "90d"
    assert body["summary"]["observation_count"] == 5
    assert len(body["history"]) == 5
    assert len(body["retailers"]) == 1


def test_get_price_history_window_30d_filters_old(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    retailer = _make_retailer(db_session, "win30")
    part = _make_part(db_session, test_user, name="Window 30 Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    # 3 rows inside 30 days, 2 rows older.
    for i, days in enumerate([1, 10, 20]):
        _add_history(db_session, listing, price_cents=1000 + i, observed_at=now - timedelta(days=days))
    for i, days in enumerate([45, 90]):
        _add_history(db_session, listing, price_cents=2000 + i, observed_at=now - timedelta(days=days))
    db_session.commit()

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id), params={"window": "30d"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["observation_count"] == 3
    assert len(body["history"]) == 3
    assert body["window"] == "30d"


def test_get_price_history_window_all_includes_everything(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    retailer = _make_retailer(db_session, "win-all")
    part = _make_part(db_session, test_user, name="Window All Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    # 4 rows spanning ~2 years.
    for days in [10, 200, 500, 700]:
        _add_history(db_session, listing, price_cents=1000 + days, observed_at=now - timedelta(days=days))
    db_session.commit()

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id), params={"window": "all"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["observation_count"] == 4
    assert len(body["history"]) == 4
    assert body["window"] == "all"


def test_get_price_history_invalid_window_returns_422(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    part = _make_part(db_session, test_user, name="Bad Window Part")
    db_session.commit()

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id), params={"window": "99x"})
    assert response.status_code == 422
    body = response.json()
    # Standardized error envelope from app.api.middleware.error_handler.
    assert body["error_code"] == "INVALID_WINDOW"
    allowed = body["details"]["allowed"]
    assert isinstance(allowed, list)
    # Must mention the canonical literals so callers can correct themselves.
    assert {"30d", "90d", "180d", "1y", "all"}.issubset(set(allowed))


def test_get_price_history_retailer_filter_narrows_summary(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    retailer_a = _make_retailer(db_session, "filt-a")
    retailer_b = _make_retailer(db_session, "filt-b")
    part = _make_part(db_session, test_user, name="Retailer Filter Part")
    listing_a = _make_listing(db_session, part, retailer_a)
    listing_b = _make_listing(db_session, part, retailer_b)

    now = datetime.now(UTC)
    # Retailer A: cheap rows (500-700). Retailer B: pricier (1500-2000).
    for i, price in enumerate([500, 600, 700]):
        _add_history(db_session, listing_a, price_cents=price, observed_at=now - timedelta(days=20 - i))
    for i, price in enumerate([1500, 1800, 2000]):
        _add_history(db_session, listing_b, price_cents=price, observed_at=now - timedelta(days=15 - i))
    db_session.commit()

    response = client.get(
        PRICE_HISTORY_PATH.format(part_id=part.id),
        params={"retailer_id": str(retailer_a.id)},
    )
    assert response.status_code == 200
    body = response.json()
    # Only retailer A in `retailers`.
    assert len(body["retailers"]) == 1
    assert body["retailers"][0]["retailer_id"] == str(retailer_a.id)
    # Summary reflects retailer A's slice only — NOT the cross-retailer aggregate.
    assert body["summary"]["min_cents"] == 500
    assert body["summary"]["max_cents"] == 700
    assert body["summary"]["observation_count"] == 3
    assert all(h["retailer_id"] == str(retailer_a.id) for h in body["history"])


def test_get_price_history_legacy_param_returns_list_shape(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    retailer = _make_retailer(db_session, "legacy")
    part = _make_part(db_session, test_user, name="Legacy Shape Part")
    listing = _make_listing(db_session, part, retailer)

    now = datetime.now(UTC)
    for i, price in enumerate([1000, 1100, 1200]):
        _add_history(db_session, listing, price_cents=price, observed_at=now - timedelta(days=5 + i))
    db_session.commit()

    response = client.get(PRICE_HISTORY_PATH.format(part_id=part.id), params={"legacy": "true"})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list), f"expected list, got {type(body).__name__}"
    assert len(body) == 3
    # Legacy entry shape mirrors PartPriceHistoryReadWithRetailer exactly.
    sample = body[0]
    assert set(sample.keys()) >= {
        "id",
        "part_listing_id",
        "price_cents",
        "observed_at",
        "retailer_id",
        "retailer_name",
    }
    assert sample["retailer_id"] == str(retailer.id)


def test_get_price_history_part_not_found_returns_404(client: TestClient) -> None:
    response = client.get(PRICE_HISTORY_PATH.format(part_id=INVALID_UUID_STR))
    assert response.status_code == 404


def test_get_price_history_aggregates_link_group(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    retailer_a = _make_retailer(db_session, "lg-a")
    retailer_b = _make_retailer(db_session, "lg-b")
    canonical = _make_part(db_session, test_user, name="Canon Part")
    duplicate = _make_part(
        db_session, test_user, canonical_part_id=canonical.id, name="Dupe Part"
    )

    listing_canon = _make_listing(db_session, canonical, retailer_a)
    listing_dupe = _make_listing(db_session, duplicate, retailer_b)

    now = datetime.now(UTC)
    _add_history(db_session, listing_canon, price_cents=5000, observed_at=now - timedelta(days=10))
    _add_history(db_session, listing_canon, price_cents=4800, observed_at=now - timedelta(days=5))
    _add_history(db_session, listing_dupe, price_cents=3000, observed_at=now - timedelta(days=8))
    _add_history(db_session, listing_dupe, price_cents=3200, observed_at=now - timedelta(days=2))
    db_session.commit()

    response = client.get(PRICE_HISTORY_PATH.format(part_id=canonical.id))
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["observation_count"] == 4
    assert body["summary"]["min_cents"] == 3000
    assert body["summary"]["max_cents"] == 5000
    # Both retailers from the link group surface on the canonical query.
    retailer_ids = {r["retailer_id"] for r in body["retailers"]}
    assert retailer_ids == {str(retailer_a.id), str(retailer_b.id)}
