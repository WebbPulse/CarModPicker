"""Linker matches across part-number styling drift.

Tier-3 Item #7 contract: ``find_part_by_part_manufacturer_and_part_number``
keys lookups off ``part_number_normalized`` (alphanumeric-uppercase) so a
later ingest of ``"AEM 30/2400"`` finds a canonical that was first ingested
as ``"AEM-30-2400"``. SQLite-backed.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.api.services.part_listing_service import (
    find_part_by_part_manufacturer_and_part_number,
)
from app.db.dynamo.catalog import Category as DBCategory
from app.db.dynamo.catalog import Part as DBPart
from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer
from tests.conftest import save_catalog


def _unique(prefix: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{prefix}_{worker}_{uuid.uuid4().hex[:10]}"


def _seed_part(
    db_session: Session,
    *,
    part_manufacturer_id: uuid.UUID,
    category_id: uuid.UUID,
    user_id: uuid.UUID,
    part_number: str,
    part_number_normalized: str,
) -> DBPart:
    part = DBPart(
        name=_unique("part"),
        category_id=category_id,
        user_id=user_id,
        part_manufacturer_id=part_manufacturer_id,
        part_number=part_number,
        part_number_normalized=part_number_normalized,
        is_universal=True,
    )
    part = save_catalog(part)
    return part


def test_linker_matches_across_styling_drift(
    db_session: Session,
    test_user: Any,
    test_part_manufacturer: DBPartManufacturer,
    test_category: DBCategory,
) -> None:
    """A canonical seeded with ``"AEM-30-2400"`` is found via ``"AEM 30/2400"``
    and ``"aem_30_2400"`` because the linker keys off the canonical
    ``part_number_normalized`` column."""
    canonical = _seed_part(
        db_session,
        part_manufacturer_id=test_part_manufacturer.id,
        category_id=test_category.id,
        user_id=test_user.id,
        part_number="AEM-30-2400",
        part_number_normalized="AEM302400",
    )
    db_session.commit()

    # Each of these styling variants of the same code should resolve.
    for variant in ("AEM-30-2400", "AEM 30/2400", "aem_30_2400", "AEM30-2400"):
        match = find_part_by_part_manufacturer_and_part_number(test_part_manufacturer.id, variant)
        assert match is not None, f"linker missed {variant!r}"
        assert match.id == canonical.id


def test_linker_returns_none_for_blacklisted_short_input(
    db_session: Session,
    test_user: Any,
    test_part_manufacturer: DBPartManufacturer,
    test_category: DBCategory,
) -> None:
    """``Z4M`` collapses to a blacklisted canonical; even with a row carrying
    that exact part_number, the linker refuses to key off chassis codes."""
    _seed_part(
        db_session,
        part_manufacturer_id=test_part_manufacturer.id,
        category_id=test_category.id,
        user_id=test_user.id,
        part_number="Z4M",
        part_number_normalized="Z4M",
    )
    db_session.commit()

    assert find_part_by_part_manufacturer_and_part_number(test_part_manufacturer.id, "Z4M") is None


def test_linker_returns_none_for_under_4_chars(
    db_session: Session,
    test_user: Any,
    test_part_manufacturer: DBPartManufacturer,
    test_category: DBCategory,
) -> None:
    """A 3-char input collapses to <4 chars and is rejected by the canonical
    builder; the linker treats this as a non-match without scanning rows."""
    _seed_part(
        db_session,
        part_manufacturer_id=test_part_manufacturer.id,
        category_id=test_category.id,
        user_id=test_user.id,
        part_number="ABC",
        part_number_normalized="ABC",
    )
    db_session.commit()

    assert find_part_by_part_manufacturer_and_part_number(test_part_manufacturer.id, "ABC") is None
