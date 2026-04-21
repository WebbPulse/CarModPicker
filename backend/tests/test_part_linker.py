"""Canonical part linker behavior (always-create + link model)."""

import logging
import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.endpoints.parts import PartService
from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_manufacturer import PartManufacturer
from app.api.models.retailer import Retailer
from app.api.models.user import User
from app.api.schemas.part import PartCreate
from app.api.services.part_linker_service import (
    reelect_canonical,
    score_metadata_richness,
    unlink_part,
)
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
    name: str = "Test part",
    description: str | None = None,
    image_urls: list[str] | None = None,
) -> DBPart:
    svc = PartService()
    payload = PartCreate(
        name=name,
        description=description,
        image_urls=image_urls,
        category_id=get_default_category_id(db_session),
        part_manufacturer_id=manufacturer.id,
        part_number=part_number,
        gtin=gtin,
        retailer_id=retailer_id,
        product_url=product_url,
        is_universal=True,
    )
    return svc.create(db_session, payload, user, logger, additional_data={"source": "scraped"})


def test_new_part_with_no_matches_is_canonical(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    retailer = _make_retailer(db_session, "solo")
    url = f"https://solo-{os.getpid()}.example.com/p/1"
    part = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=url,
        retailer_id=retailer.id,
        part_number="PN-SOLO-1",
    )
    assert part.canonical_part_id is None


def test_repeat_url_refreshes_existing_part_in_place(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    """URL-level dedup: one Part per product listing. Re-ingesting the same URL updates it in place."""
    retailer = _make_retailer(db_session, "repeat")
    url = f"https://repeat-{os.getpid()}.example.com/p/x"
    first = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=url,
        retailer_id=retailer.id,
        part_number="PN-REPEAT-A",
    )
    assert first.canonical_part_id is None

    second = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=url,
        retailer_id=retailer.id,
        part_number="PN-REPEAT-A",
        name="Second ingest of same product",
    )
    assert second.id == first.id
    assert second.name == "Second ingest of same product"
    assert second.canonical_part_id is None


def test_repeat_gtin_across_retailers_links_to_canonical(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    retailer_a = _make_retailer(db_session, "gtin-a")
    retailer_b = _make_retailer(db_session, "gtin-b")
    gtin = "012345678905"

    first = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    assert first.canonical_part_id is None

    second = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://b-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert second.canonical_part_id == first.id


def test_repeat_part_number_links_to_canonical(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    retailer_a = _make_retailer(db_session, "pn-a")
    retailer_b = _make_retailer(db_session, "pn-b")
    pn = f"PN-SHARE-{os.getpid()}"

    first = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://pn-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        part_number=pn,
    )
    second = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://pn-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        part_number=pn,
    )
    assert second.canonical_part_id == first.id


def test_richer_new_part_reelects_canonical(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    """When the new part has richer metadata than the existing canonical, it is elected canonical."""
    retailer_a = _make_retailer(db_session, "rich-a")
    retailer_b = _make_retailer(db_session, "rich-b")
    pn = f"PN-RICH-{os.getpid()}"

    # First part has only a part number — no GTIN, no description, no images.
    first = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://rich-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        part_number=pn,
    )

    # Second part adds a GTIN, a real description, and several images → scores higher.
    second = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://rich-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        part_number=pn,
        gtin="012345678912",
        description="This is a reasonably detailed description exceeding the minimum length threshold.",
        image_urls=["img1", "img2", "img3"],
    )

    db_session.refresh(first)
    db_session.refresh(second)
    assert second.canonical_part_id is None
    assert first.canonical_part_id == second.id


def test_conflict_merges_link_groups_under_richest(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    """When multiple existing canonicals match different dedup keys, linker merges them."""
    retailer_a = _make_retailer(db_session, "merge-a")
    retailer_b = _make_retailer(db_session, "merge-b")
    retailer_c = _make_retailer(db_session, "merge-c")

    # Canonical 1: matched by GTIN.
    by_gtin = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://merge-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin="012345678929",
    )
    # Canonical 2: matched by part_number (different GTIN so they don't pre-link).
    by_pn = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://merge-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        part_number=f"PN-MERGE-{os.getpid()}",
    )
    assert by_gtin.canonical_part_id is None
    assert by_pn.canonical_part_id is None

    # Third ingest carries BOTH keys → both canonicals should be pulled into one group.
    third = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://merge-c-{os.getpid()}.example.com/p/3",
        retailer_id=retailer_c.id,
        gtin="012345678929",
        part_number=f"PN-MERGE-{os.getpid()}",
    )

    db_session.refresh(by_gtin)
    db_session.refresh(by_pn)
    db_session.refresh(third)

    # Exactly one of the three is canonical; the other two point at it.
    canonicals = [p for p in (by_gtin, by_pn, third) if p.canonical_part_id is None]
    assert len(canonicals) == 1
    canonical_id = canonicals[0].id
    for p in (by_gtin, by_pn, third):
        if p.id != canonical_id:
            assert p.canonical_part_id == canonical_id


def test_score_metadata_richness_monotonic(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    retailer = _make_retailer(db_session, "score")
    sparse = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://score-{os.getpid()}.example.com/sparse",
        retailer_id=retailer.id,
    )
    rich = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://score-{os.getpid()}.example.com/rich",
        retailer_id=retailer.id,
        gtin="012345678936",
        part_number=f"PN-SCORE-{os.getpid()}",
        description="A description that is long enough to score for description richness.",
        image_urls=["a", "b", "c"],
    )
    assert score_metadata_richness(rich) > score_metadata_richness(sparse)


def test_unlink_part_detaches_from_canonical(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    """Unlinking a sibling part makes it its own canonical again."""
    retailer_a = _make_retailer(db_session, "unlink-a")
    retailer_b = _make_retailer(db_session, "unlink-b")
    gtin = "012345678950"
    first = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://unlink-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    second = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://unlink-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert second.canonical_part_id == first.id

    unlink_part(db_session, second)
    db_session.refresh(second)
    assert second.canonical_part_id is None


def test_reelect_canonical_swaps_roles(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    """Re-electing a sibling as canonical flips the roles for the whole link group."""
    retailer_a = _make_retailer(db_session, "reelect-a")
    retailer_b = _make_retailer(db_session, "reelect-b")
    retailer_c = _make_retailer(db_session, "reelect-c")
    gtin = "012345678967"
    first = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://reelect-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    second = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://reelect-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    third = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://reelect-c-{os.getpid()}.example.com/p/3",
        retailer_id=retailer_c.id,
        gtin=gtin,
    )
    assert third.canonical_part_id == first.id

    reelect_canonical(db_session, second)
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(third)
    assert second.canonical_part_id is None
    assert first.canonical_part_id == second.id
    assert third.canonical_part_id == second.id


def test_listings_created_per_part_in_link_group(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    """Each ingest owns its own PartListing; aggregation to canonical is a read-time concern."""
    retailer_a = _make_retailer(db_session, "listings-a")
    retailer_b = _make_retailer(db_session, "listings-b")
    gtin = "012345678943"

    first = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://listings-a-{os.getpid()}.example.com/p/1",
        retailer_id=retailer_a.id,
        gtin=gtin,
    )
    second = _create_part(
        db_session,
        test_user,
        test_part_manufacturer,
        product_url=f"https://listings-b-{os.getpid()}.example.com/p/2",
        retailer_id=retailer_b.id,
        gtin=gtin,
    )
    assert second.canonical_part_id == first.id

    listings_first = db_session.query(DBPartListing).filter(DBPartListing.part_id == first.id).all()
    listings_second = db_session.query(DBPartListing).filter(DBPartListing.part_id == second.id).all()
    assert len(listings_first) == 1
    assert len(listings_second) == 1
    assert listings_first[0].retailer_id == retailer_a.id
    assert listings_second[0].retailer_id == retailer_b.id
