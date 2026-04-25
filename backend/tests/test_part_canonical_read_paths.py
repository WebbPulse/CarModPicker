"""Phase 2 read-path behavior: canonical-only catalog, aggregated listings, best-price across link group."""

import logging
import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.endpoints.parts import PartService
from app.api.models.part import Part as DBPart
from app.api.models.part_manufacturer import PartManufacturer
from app.api.models.retailer import Retailer
from app.api.models.user import User
from app.api.schemas.part import PartCreate
from app.api.services.part_linker_service import link_group_part_ids
from tests.conftest import get_default_category_id

logger = logging.getLogger(__name__)


def _make_retailer(db_session: Session, slug: str) -> Retailer:
    retailer = Retailer(
        name=f"retailer_{slug}_{os.getpid()}",
        domain=f"{slug}{os.getpid()}example.com",
        base_url=f"https://{slug}-example.com",
        is_active=True,
    )
    db_session.add(retailer)
    db_session.commit()
    db_session.refresh(retailer)
    return retailer


def _create_part(
    db_session: Session,
    user: User,
    manufacturer: PartManufacturer,
    *,
    product_url: str | None = None,
    retailer_id: UUID | None = None,
    part_number: str | None = None,
    gtin: str | None = None,
    price_cents: int | None = None,
) -> DBPart:
    svc = PartService()
    payload = PartCreate(
        name="Test part",
        category_id=get_default_category_id(db_session),
        part_manufacturer_id=manufacturer.id,
        part_number=part_number,
        gtin=gtin,
        retailer_id=retailer_id,
        product_url=product_url,
        price_cents=price_cents,
        is_universal=True,
    )
    return svc.create(db_session, payload, user, logger, additional_data={"source": "scraped"})


def test_link_group_part_ids_for_canonical_includes_siblings(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    retailer_a = _make_retailer(db_session, "grp-a")
    retailer_b = _make_retailer(db_session, "grp-b")
    retailer_c = _make_retailer(db_session, "grp-c")
    gtin = "012345678981"
    canonical = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://grp-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    sibling_1 = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://grp-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    sibling_2 = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://grp-c-{os.getpid()}.example.com/p/3",
        retailer_id=retailer_c.id,
        gtin=gtin,
    )

    group = set(link_group_part_ids(db_session, canonical.id))
    assert group == {canonical.id, sibling_1.id, sibling_2.id}

    # Querying via a sibling resolves to the same group.
    group_via_sibling = set(link_group_part_ids(db_session, sibling_1.id))
    assert group_via_sibling == group


def test_part_listings_endpoint_aggregates_across_link_group(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    client,
) -> None:
    """GET /parts/{canonical_id}/listings includes listings from every sibling."""
    retailer_a = _make_retailer(db_session, "agg-a")
    retailer_b = _make_retailer(db_session, "agg-b")
    gtin = "012345678998"
    canonical = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://agg-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
        price_cents=4500,
    )
    sibling = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://agg-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
        price_cents=3200,
    )
    assert sibling.canonical_part_id == canonical.id

    response = client.get(f"/api/parts/{canonical.id}/listings")
    assert response.status_code == 200
    listings = response.json()
    retailer_ids = {str(r.id) for r in (retailer_a, retailer_b)}
    got_retailers = {l["retailer_id"] for l in listings}
    assert got_retailers == retailer_ids


def test_best_listing_across_link_group_returns_lowest_sibling_price(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    client,
) -> None:
    retailer_a = _make_retailer(db_session, "best-a")
    retailer_b = _make_retailer(db_session, "best-b")
    gtin = "012345679001"
    canonical = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://best-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
        price_cents=8999,
    )
    _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://best-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
        price_cents=4999,
    )

    response = client.get(f"/api/parts/{canonical.id}/best-listing")
    assert response.status_code == 200
    body = response.json()
    assert body["last_known_price_cents"] == 4999
    assert body["retailer_id"] == str(retailer_b.id)


def test_part_with_listings_returns_canonical_best_price(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    client,
) -> None:
    retailer_a = _make_retailer(db_session, "with-a")
    retailer_b = _make_retailer(db_session, "with-b")
    gtin = "012345679018"
    canonical = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://with-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
        price_cents=7500,
    )
    _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://with-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
        price_cents=6000,
    )

    response = client.get(f"/api/parts/{canonical.id}/with-listings")
    assert response.status_code == 200
    body = response.json()
    assert body["best_price_cents"] == 6000
    assert len(body["listings"]) == 2


def test_price_history_aggregates_across_link_group(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    client,
) -> None:
    retailer_a = _make_retailer(db_session, "ph-a")
    retailer_b = _make_retailer(db_session, "ph-b")
    gtin = "012345679025"
    canonical = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://ph-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
        price_cents=5500,
    )
    _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://ph-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
        price_cents=4000,
    )

    response = client.get(f"/api/parts/{canonical.id}/price-history")
    assert response.status_code == 200
    body = response.json()
    # S05/T02: response is now an object {summary, retailers, history, window}.
    history = body["history"]
    retailer_ids = {h["retailer_id"] for h in history}
    assert retailer_ids == {str(retailer_a.id), str(retailer_b.id)}


def test_public_catalog_hides_non_canonical_duplicates(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    client,
) -> None:
    retailer_a = _make_retailer(db_session, "cat-a")
    retailer_b = _make_retailer(db_session, "cat-b")
    gtin = "012345679032"
    canonical = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://cat-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    duplicate = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://cat-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert duplicate.canonical_part_id == canonical.id

    response = client.get("/api/parts/with-votes?limit=1000")
    assert response.status_code == 200
    part_ids = {p["id"] for p in response.json()["data"]}
    assert str(canonical.id) in part_ids
    assert str(duplicate.id) not in part_ids


def test_non_canonical_detail_returns_canonical_part_id_hint(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    client,
) -> None:
    """Clients read response.canonical_part_id to redirect to the surface part."""
    retailer_a = _make_retailer(db_session, "hint-a")
    retailer_b = _make_retailer(db_session, "hint-b")
    gtin = "012345679049"
    canonical = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://hint-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    duplicate = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://hint-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )

    response = client.get(f"/api/parts/{duplicate.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(duplicate.id)
    assert body["canonical_part_id"] == str(canonical.id)

    canonical_response = client.get(f"/api/parts/{canonical.id}")
    assert canonical_response.status_code == 200
    assert canonical_response.json()["canonical_part_id"] is None
