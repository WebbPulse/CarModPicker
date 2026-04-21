"""URL-level dedup at ingest.

One global Part per product listing (URL). Re-ingesting the same URL refreshes
the Part in place from the latest parse and appends a price history point. New
Part rows only get created when a URL is new; canonical linking via GTIN or
manufacturer+part_number is a separate cross-URL concern.
"""

import logging
import os

import pytest
from sqlalchemy.orm import Session

from app.api.endpoints.parts import PartService
from app.api.models.category import Category
from app.api.models.part_listing import PartListing
from app.api.models.part_manufacturer import PartManufacturer
from app.api.models.retailer import Retailer
from app.api.models.user import User
from app.api.schemas.part import PartCreate
from tests.conftest import get_default_category_id

logger = logging.getLogger(__name__)


@pytest.fixture
def lighting_category(db_session: Session) -> Category:
    name = f"lighting_{os.getpid()}_{id(db_session)}"
    existing = db_session.query(Category).filter(Category.name == name).first()
    if existing:
        return existing
    cat = Category(
        name=name,
        display_name="Lighting",
        description="Test",
        is_active=True,
        sort_order=50,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


def test_reingest_same_url_refreshes_in_place(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    lighting_category: Category,
) -> None:
    """Second ingest of the same URL updates the existing Part; no new row."""
    other_id = get_default_category_id(db_session)
    retailer = Retailer(
        name=f"dedupe_retailer_{os.getpid()}",
        domain=f"dedupe{os.getpid()}example.com",
        base_url="https://dedupe-example.com",
        is_active=True,
    )
    db_session.add(retailer)
    db_session.commit()
    db_session.refresh(retailer)

    url = f"https://dedupe-example.com/p/unique-{os.getpid()}"
    svc = PartService()
    first = PartCreate(
        name="Original title",
        description="Original desc",
        category_id=other_id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        is_universal=True,
    )
    part = svc.create(db_session, first, test_user, logger, additional_data={"source": "scraped"})
    original_id = part.id
    assert part.canonical_part_id is None
    assert part.category_id == other_id

    second = PartCreate(
        name="Updated from later crawl",
        description="Updated desc",
        category_id=lighting_category.id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        is_universal=True,
    )
    again = svc.create(db_session, second, test_user, logger, additional_data={"source": "archive_rescrape"})

    # Same Part row — no sibling created.
    assert again.id == original_id
    assert again.canonical_part_id is None

    # Scrape-wins: latest parsed fields are on the Part.
    db_session.refresh(part)
    assert part.name == "Updated from later crawl"
    assert part.description == "Updated desc"
    assert part.category_id == lighting_category.id
    assert part.source == "archive_rescrape"

    # Single PartListing for the (part, retailer) pair survives.
    listings = db_session.query(PartListing).filter(PartListing.part_id == part.id).all()
    assert len(listings) == 1


def test_reingest_keeps_non_null_fields_when_new_payload_omits_them(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
) -> None:
    """If a parser loses a field on one run, the existing value is retained (no erasure)."""
    other_id = get_default_category_id(db_session)
    retailer = Retailer(
        name=f"dedupe2_{os.getpid()}",
        domain=f"dedupe2{os.getpid()}example.com",
        base_url="https://dedupe2-example.com",
        is_active=True,
    )
    db_session.add(retailer)
    db_session.commit()
    db_session.refresh(retailer)

    url = f"https://dedupe2-example.com/p/u-{os.getpid()}"
    svc = PartService()
    first = PartCreate(
        name="Part with GTIN",
        category_id=other_id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        gtin="012345678974",
        part_number="PN-KEEP-1",
        is_universal=True,
    )
    # URL-level refresh only applies to scraped ingests — UGC is isolated — so
    # seed the first part as scraped to match what a crawler would produce.
    part = svc.create(db_session, first, test_user, logger, additional_data={"source": "scraped"})
    assert part.gtin == "012345678974"
    assert part.part_number == "PN-KEEP-1"

    # Second ingest has no GTIN/part_number (parser missed them). Existing values must survive.
    second = PartCreate(
        name="Part with GTIN",
        category_id=other_id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        is_universal=True,
    )
    again = svc.create(db_session, second, test_user, logger, additional_data={"source": "scraped"})
    assert again.id == part.id
    db_session.refresh(part)
    assert part.gtin == "012345678974"
    assert part.part_number == "PN-KEEP-1"
