"""Deduped global part refresh when re-ingesting from archived HTML."""

import logging
import os

import pytest
from sqlalchemy.orm import Session

from app.api.endpoints.parts import PartService
from app.api.models.category import Category
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


def test_dedupe_refresh_updates_category_and_name(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    lighting_category: Category,
) -> None:
    """When refresh_metadata_on_dedupe is set, second create merges payload onto existing part."""
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
        description="Desc",
        category_id=other_id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        is_universal=True,
    )
    part = svc.create(db_session, first, test_user, logger, additional_data={"source": "scraped"})
    assert part.category_id == other_id

    second = PartCreate(
        name="Updated from archive",
        description="Desc",
        category_id=lighting_category.id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        is_universal=True,
    )
    again = svc.create(
        db_session,
        second,
        test_user,
        logger,
        additional_data={"source": "archive_rescrape", "refresh_metadata_on_dedupe": True},
    )
    assert again.id == part.id
    db_session.refresh(part)
    assert part.name == "Updated from archive"
    assert part.category_id == lighting_category.id


def test_dedupe_without_refresh_keeps_category(
    db_session: Session,
    test_user: User,
    test_part_manufacturer: PartManufacturer,
    lighting_category: Category,
) -> None:
    """Default dedupe path does not overwrite category."""
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
        name="Keep me",
        category_id=other_id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        is_universal=True,
    )
    part = svc.create(db_session, first, test_user, logger, None)
    second = PartCreate(
        name="Would change name if refreshed",
        category_id=lighting_category.id,
        part_manufacturer_id=test_part_manufacturer.id,
        retailer_id=retailer.id,
        product_url=url,
        is_universal=True,
    )
    again = svc.create(db_session, second, test_user, logger, additional_data={"source": "scraped"})
    assert again.id == part.id
    db_session.refresh(part)
    assert part.name == "Keep me"
    assert part.category_id == other_id
