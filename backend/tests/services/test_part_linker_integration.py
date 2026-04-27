"""PARTS-03 integration coverage — five canonical-flow scenarios on SQLite.

Covers the algorithmic correctness of
``part_linker_service.{link_new_part, reelect_canonical, unlink_part}``:

    (a) Isolated canonical — new part with no matches stays canonical.
    (b) Link-into-existing — new part matches an existing canonical, becomes sibling.
    (c) Re-elect — new part has richer metadata, old canonical becomes sibling.
    (d) Merge — new part shares gtin with canonical A AND url with canonical B;
        canonicals merge under the chosen one. Seeds concrete ``DBPartListing``
        rows per plan 04-06 WARN 7 so ``find_part_by_product_url`` returns
        canon_b and ``find_part_by_gtin`` returns canon_a.
    (e) Unlink → promote — unlink a sibling; it becomes standalone canonical.

Concurrency correctness under row locks is covered by
``test_part_linker_concurrency.py`` (Postgres-backed, plan 04-05).

Each test uses a per-test unique key prefix to avoid cross-test interference
under pytest-xdist `-n auto`.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.retailer import Retailer as DBRetailer
from app.api.services.part_linker_service import (
    link_new_part,
    reelect_canonical,
    unlink_part,
)


def _unique(prefix: str) -> str:
    """Return a unique suffix keyed to the pytest-xdist worker + a UUID."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{prefix}_{worker}_{uuid.uuid4().hex[:10]}"


def _get_or_create_default_category(db_session: Session) -> DBCategory:
    """Return an existing Category row or create a throwaway one for this test."""
    existing = db_session.scalars(select(DBCategory).limit(1)).first()
    if existing is not None:
        return existing
    cat = DBCategory(
        name=_unique("integ_cat"),
        display_name="integration test cat",
        description="auto-created for test_part_linker_integration",
        is_active=True,
        sort_order=1,
    )
    db_session.add(cat)
    db_session.flush()
    return cat


def _make_retailer(db_session: Session) -> DBRetailer:
    """Seed a Retailer — required for PartListing rows in the merge case (WARN 7)."""
    retailer = DBRetailer(
        name=_unique("ret"),
        domain=f"{_unique('dom')}.example.com",
        base_url=f"https://{_unique('host')}.example.com",
        is_active=True,
    )
    db_session.add(retailer)
    db_session.flush()
    return retailer


def _mk_part(
    db_session: Session,
    test_user: Any,
    test_part_manufacturer: Any,
    *,
    name: str = "part",
    gtin: str | None = None,
    part_number: str | None = None,
    description: str | None = None,
    image_urls: list[str] | None = None,
    source: str = "scraped",
    canonical_part_id: uuid.UUID | None = None,
) -> DBPart:
    """Construct a DBPart directly (bypassing PartService) for controlled seeds.

    Defaults ``source='scraped'`` so the linker considers this part (UGC rows
    are excluded by ``find_part_by_*`` helpers).
    """
    p = DBPart(
        name=name,
        description=description,
        image_urls=image_urls,
        category_id=_get_or_create_default_category(db_session).id,
        user_id=test_user.id,
        part_manufacturer_id=test_part_manufacturer.id,
        part_number=part_number,
        gtin=gtin,
        source=source,
        canonical_part_id=canonical_part_id,
        is_universal=True,
    )
    db_session.add(p)
    db_session.flush()
    return p


def test_new_part_with_no_matches_is_canonical(
    db_session: Session, test_user: Any, test_part_manufacturer: Any
) -> None:
    """Scenario (a): part with no dedup matches is its own canonical."""
    p = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Solo part",
        gtin=_unique("gtin"),
    )
    db_session.commit()

    result = link_new_part(db_session, p)
    db_session.commit()
    db_session.refresh(p)

    assert p.canonical_part_id is None, "No matches → should remain canonical"
    assert result.id == p.id, "link_new_part returns the canonical it resolved to"


def test_link_new_part_into_existing_canonical(
    db_session: Session, test_user: Any, test_part_manufacturer: Any
) -> None:
    """Scenario (b): new part matches an existing canonical → links as sibling."""
    shared_gtin = _unique("gtin")
    # Seed a canonical with richer metadata so the new part cannot re-elect it.
    canonical = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Canonical",
        gtin=shared_gtin,
        description="Long-enough description to score for description richness threshold.",
        image_urls=["a", "b", "c"],
        part_number=_unique("PN"),
    )
    db_session.commit()

    # New part with same gtin but sparse metadata.
    new_part = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Duplicate (sparse)",
        gtin=shared_gtin,
    )
    db_session.commit()

    link_new_part(db_session, new_part)
    db_session.commit()
    db_session.refresh(new_part)
    db_session.refresh(canonical)

    assert canonical.canonical_part_id is None, "Canonical must stay canonical"
    assert (
        new_part.canonical_part_id == canonical.id
    ), f"New part should point at canonical; got {new_part.canonical_part_id}"


def test_new_part_reelects_canonical_under_richer_metadata(
    db_session: Session, test_user: Any, test_part_manufacturer: Any
) -> None:
    """Scenario (c): new part has richer metadata → re-elects itself as canonical."""
    shared_gtin = _unique("gtin")
    # Sparse first part — gtin only, no description or images.
    older = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Older (weaker)",
        gtin=shared_gtin,
    )
    db_session.commit()

    # Richer new part — adds description + images + part_number.
    richer = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Newer (richer)",
        gtin=shared_gtin,
        part_number=_unique("PN"),
        description="A reasonably long description exceeding the minimum description-score threshold.",
        image_urls=["a", "b", "c", "d"],
    )
    db_session.commit()

    link_new_part(db_session, richer)
    db_session.commit()
    db_session.refresh(older)
    db_session.refresh(richer)

    assert richer.canonical_part_id is None, "Richer part should be the new canonical"
    assert older.canonical_part_id == richer.id, "Older should be repointed at richer"


def test_merge_multiple_candidate_canonicals(db_session: Session, test_user: Any, test_part_manufacturer: Any) -> None:
    """Scenario (d): new part shares gtin with A and url with B → canonicals merge.

    WARN 7: the merge path is only exercised when BOTH gtin lookup AND url
    lookup return distinct canonicals. That requires concrete PartListing
    rows — a PartListing.product_url pointing at canon_b lets
    find_part_by_product_url return canon_b, and find_part_by_gtin returns
    canon_a via the shared gtin.
    """
    retailer = _make_retailer(db_session)
    shared_gtin = _unique("gtin")
    shared_url = f"https://{_unique('host')}.example.com/p/1"

    # Canonical A — matchable by gtin only.
    canon_a = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="A (gtin source)",
        gtin=shared_gtin,
    )
    db_session.commit()

    # Canonical B — matchable by url only (no gtin); needs a concrete PartListing.
    canon_b = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="B (url source)",
    )
    listing_b = DBPartListing(
        part_id=canon_b.id,
        retailer_id=retailer.id,
        product_url=shared_url,
    )
    db_session.add(listing_b)
    db_session.commit()

    # New part carries BOTH keys; invoking link_new_part with product_url=shared_url
    # should fold canon_a and canon_b under a single canonical.
    new_part = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Merger",
        gtin=shared_gtin,
    )
    db_session.commit()

    link_new_part(db_session, new_part, product_url=shared_url)
    db_session.commit()
    db_session.refresh(canon_a)
    db_session.refresh(canon_b)
    db_session.refresh(new_part)

    canonicals_after = [p for p in (canon_a, canon_b, new_part) if p.canonical_part_id is None]
    assert len(canonicals_after) == 1, (
        f"Merge should leave exactly 1 canonical; got {len(canonicals_after)}: "
        f"canon_a={canon_a.canonical_part_id}, "
        f"canon_b={canon_b.canonical_part_id}, "
        f"new_part={new_part.canonical_part_id}"
    )
    # Every non-canonical must point at the surviving canonical (no cycles/orphans).
    surviving_id = canonicals_after[0].id
    for p in (canon_a, canon_b, new_part):
        if p.id != surviving_id:
            assert (
                p.canonical_part_id == surviving_id
            ), f"{p.name} should point at surviving canonical; got {p.canonical_part_id}"


def test_unlink_promotes_sibling_to_standalone(
    db_session: Session, test_user: Any, test_part_manufacturer: Any
) -> None:
    """Scenario (e): unlink a sibling → it becomes its own canonical."""
    shared_gtin = _unique("gtin")
    canonical = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Canonical",
        gtin=shared_gtin,
        description="Long-enough description to score for description richness threshold.",
        image_urls=["a", "b", "c"],
    )
    db_session.commit()
    sibling = _mk_part(
        db_session,
        test_user,
        test_part_manufacturer,
        name="Sibling",
        gtin=shared_gtin,
        canonical_part_id=canonical.id,
    )
    db_session.commit()

    # Precondition sanity check.
    assert sibling.canonical_part_id == canonical.id

    # Bonus coverage: exercise reelect_canonical on a sibling that is already a
    # duplicate — this returns a new canonical with canonical_part_id cleared.
    # We call it here to prove the path is reachable; the unlink below is the
    # scenario (e) primary assertion.
    reelect_canonical(db_session, sibling)
    db_session.commit()
    db_session.refresh(sibling)
    db_session.refresh(canonical)
    # After reelect, sibling is canonical and canonical points at sibling.
    assert sibling.canonical_part_id is None
    assert canonical.canonical_part_id == sibling.id

    # Now unlink the ORIGINAL canonical (currently a sibling of `sibling`).
    unlink_part(db_session, canonical)
    db_session.commit()
    db_session.refresh(canonical)
    assert canonical.canonical_part_id is None, "Unlinked part should be standalone canonical after unlink_part"
