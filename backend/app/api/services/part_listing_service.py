"""
Service for part listing deduplication and retailer/listing/price operations.

Used by global part create, create-and-add-part, and scrapers to:
- Get-or-create retailers and part_manufacturers
- Find existing parts by URL, part_manufacturer+part_number, or GTIN (UPC/EAN)
- Create/update PartListing and append PartPriceHistory
"""

import re
from datetime import UTC, datetime
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.retailer import Retailer as DBRetailer

# Tokens stripped from the tail of a manufacturer name during canonical comparison.
# Sub-divisions ("Performance", "Racing", "Electronics", ...) and corporate suffixes
# ("Inc", "LLC", ...) all collapse to the parent brand so an adapter submitting
# "AEM Electronics" or "APR Performance" resolves to the existing "AEM" / "APR" row
# rather than creating a duplicate.
_MANUFACTURER_TRAILING_TOKENS = frozenset(
    {
        # Corporate suffixes
        "inc",
        "llc",
        "ltd",
        "co",
        "corp",
        "company",
        "llp",
        "limited",
        # Brand sub-divisions / generic descriptors
        "performance",
        "racing",
        "motorsport",
        "motorsports",
        "tuning",
        "engineering",
        "electronics",
        "induction",
        "industries",
        "usa",
        "america",
        "automotive",
    }
)


def manufacturer_name_canonical(raw: str) -> str:
    """Reduce a manufacturer name to a canonical comparison key.

    Steps:
      1. Lowercase.
      2. Strip non-alphanumerics (collapses ``A'PEX-i`` -> ``apexi``,
         ``Borg Warner`` -> ``borgwarner``, ``K&N`` -> ``kn``, ``Stop Tech``
         -> ``stoptech``, ``Studio RSR`` -> ``studiorsr``).
      3. After tokenizing on whitespace, drop trailing tokens listed in
         ``_MANUFACTURER_TRAILING_TOKENS`` (corporate suffixes + brand
         sub-division words). Iteratively — ``Titan 7 LLC USA`` collapses
         all the way to ``titan7``.

    Returns an empty string if nothing remains. Used for case-insensitive,
    whitespace-insensitive, suffix-insensitive lookups; never written back
    to the DB.
    """
    if not raw:
        return ""
    lowered = raw.lower()
    # Tokenize first (whitespace + punctuation), then apply the trailing-token
    # filter, then strip remaining non-alphanumerics on each surviving token.
    # This way ``AEM Electronics`` -> tokens ["aem", "electronics"] -> drop
    # trailing "electronics" -> "aem", instead of mashing into "aemelectronics"
    # and never matching the trailing-token list.
    tokens = [t for t in re.split(r"[^a-z0-9]+", lowered) if t]
    while tokens and tokens[-1] in _MANUFACTURER_TRAILING_TOKENS:
        tokens.pop()
    return "".join(tokens)


def get_or_create_retailer(
    db: Session,
    name: str,
    *,
    domain: Optional[str] = None,
    base_url: Optional[str] = None,
) -> DBRetailer:
    """Get existing retailer by domain (if provided) or name; otherwise create."""
    if domain:
        domain_normalized = domain.strip().lower()
        # Match both www. and non-www. variants so e.g. "a90shop.com" and
        # "www.a90shop.com" resolve to the same retailer row.
        if domain_normalized.startswith("www."):
            domain_alt = domain_normalized[4:]
        else:
            domain_alt = "www." + domain_normalized
        retailer = db.scalars(
            select(DBRetailer).where(or_(DBRetailer.domain == domain_normalized, DBRetailer.domain == domain_alt))
        ).first()
        if retailer:
            return retailer
    retailer = db.scalars(select(DBRetailer).where(DBRetailer.name.ilike(name.strip()))).first()
    if retailer:
        if domain and not retailer.domain:
            retailer.domain = domain.strip().lower()
            retailer.base_url = base_url or retailer.base_url
            db.add(retailer)
            db.flush()
        return retailer
    retailer = DBRetailer(
        name=name.strip(),
        domain=domain.strip().lower() if domain else None,
        base_url=base_url,
        is_active=True,
    )
    db.add(retailer)
    db.flush()
    return retailer


def _find_pm_by_name(db: Session, name_normalized: str) -> Optional[DBPartManufacturer]:
    """Look up a manufacturer by name.

    Two-pass match:
      1. Exact case-insensitive name match (preserves ``ilike`` semantics —
         the fast path, and the only path the unique index on ``lower(name)``
         enforces).
      2. Canonical-key match: compute ``manufacturer_name_canonical`` for the
         input, then for each row, and return the first row whose canonical
         key matches. This lets ``"APR Performance"`` resolve to the existing
         ``"APR"`` row, or ``"AEM Electronics"`` to ``"AEM"``, without minting
         a duplicate. Pulls all rows in memory; the catalog is small
         (~hundreds), so the cost is negligible compared to the dedup win. If
         two rows share a canonical key, return the first sorted by name for
         determinism.
    """
    exact = db.scalars(select(DBPartManufacturer).where(DBPartManufacturer.name.ilike(name_normalized))).first()
    if exact is not None:
        return exact

    canonical_key = manufacturer_name_canonical(name_normalized)
    if not canonical_key:
        return None
    for pm in db.scalars(select(DBPartManufacturer).order_by(DBPartManufacturer.name)).all():
        if manufacturer_name_canonical(pm.name) == canonical_key:
            return pm
    return None


def get_or_create_part_manufacturer_by_name(db: Session, name: str) -> Optional[DBPartManufacturer]:
    """Get-or-create a manufacturer by name (case-insensitive).

    Used by the Chrome extension, the seed script, admin-driven creates, and
    user part creates. There is a single global manufacturer namespace.

    Returns ``None`` if the name is empty.
    """
    if not name or not name.strip():
        return None
    name_normalized = name.strip()
    existing = _find_pm_by_name(db, name_normalized)
    if existing:
        return existing
    # SAVEPOINT-scoped insert: parallel workers can race here and both try to
    # insert the same manufacturer. The unique index on lower(name) rejects the
    # loser; rolling back just this savepoint lets us re-query for the row the
    # winner created without poisoning the outer txn.
    try:
        with db.begin_nested():
            part_manufacturer = DBPartManufacturer(
                name=name_normalized,
                is_active=True,
            )
            db.add(part_manufacturer)
            db.flush()
        return part_manufacturer
    except IntegrityError:
        existing = _find_pm_by_name(db, name_normalized)
        if existing is not None:
            return existing
        raise


def _normalize_url(url: Optional[str]) -> Optional[str]:
    if not url or not url.strip():
        return None
    return url.strip()


def normalize_part_number(part_number: Optional[str]) -> Optional[str]:
    """
    Normalize part number by stripping common prefixes (SKU:, Part #:, etc.)
    so lookups and storage use the actual code for deduplication.
    """
    if not part_number or not part_number.strip():
        return None
    s = part_number.strip()
    prefixes = [
        r"^SKU\s*:\s*",
        r"^Part\s*#\s*:\s*",
        r"^Part\s*Number\s*:\s*",
        r"^Item\s*#\s*:\s*",
        r"^Product\s*Code\s*:\s*",
        r"^Model\s*#?\s*:\s*",
        r"^Code\s*:\s*",
    ]
    for pattern in prefixes:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    s = s.strip()
    return s if s else None


def find_part_by_product_url(
    db: Session,
    product_url: str,
    *,
    creator_id: Optional[UUID] = None,
) -> Optional[DBPart]:
    """
    Find a part that owns a PartListing with this product URL.

    ``creator_id`` scopes the search to parts owned by that user — used by the
    create dup check to ask "does *this* user already have a part for this
    URL?" without being fooled by another user's part sorting first in
    ``.first()``.

    Returns any matching Part (canonical or duplicate). Callers doing canonical
    dedup should resolve the result to its canonical.
    """
    normalized = _normalize_url(product_url)
    if not normalized:
        return None
    stmt = (
        select(DBPartListing)
        .join(DBPart, DBPart.id == DBPartListing.part_id)
        .where(DBPartListing.product_url == normalized)
    )
    if creator_id is not None:
        stmt = stmt.where(DBPart.user_id == creator_id)
    listing = db.scalars(stmt).first()
    if listing:
        return listing.part
    return None


def find_part_by_part_manufacturer_and_part_number(
    db: Session,
    part_manufacturer_id: UUID,
    part_number: str,
    *,
    creator_id: Optional[UUID] = None,
) -> Optional[DBPart]:
    """
    Find a canonical part by part_manufacturer_id and part_number.

    Uses ``part_number_normalized`` (the canonical alphanumeric-uppercase
    form) for matching so styling drift between ``"AEM-30-2400"`` and
    ``"AEM 30/2400"`` collapses into one dedup key. Only returns canonicals.

    ``creator_id`` optionally scopes to parts owned by that user.
    """
    from app.api.services.page_parser import part_number_canonical

    canonical = part_number_canonical(part_number)
    if not canonical:
        return None
    stmt = select(DBPart).where(
        DBPart.part_manufacturer_id == part_manufacturer_id,
        DBPart.part_number_normalized == canonical,
        DBPart.canonical_part_id.is_(None),
    )
    if creator_id is not None:
        stmt = stmt.where(DBPart.user_id == creator_id)
    return db.scalars(stmt).first()


def normalize_gtin(gtin: Optional[str]) -> Optional[str]:
    """
    Normalize GTIN (UPC/EAN) to digits only for storage and dedup lookup.
    Handles formats like 0-12345-67890-1 or 012345678901.
    """
    if not gtin or not gtin.strip():
        return None
    digits = "".join(c for c in gtin.strip() if c.isdigit())
    return digits if digits else None


def find_part_by_gtin(
    db: Session,
    gtin: str,
    *,
    creator_id: Optional[UUID] = None,
) -> Optional[DBPart]:
    """
    Find a canonical part by GTIN (UPC/EAN).

    Uses normalized digits-only for matching. Only returns canonicals so the
    linker never recommends a duplicate as a merge target.

    ``creator_id`` optionally scopes to parts owned by that user.
    """
    normalized = normalize_gtin(gtin)
    if not normalized:
        return None
    exact_stmt = select(DBPart).where(
        DBPart.gtin == normalized,
        DBPart.canonical_part_id.is_(None),
    )
    if creator_id is not None:
        exact_stmt = exact_stmt.where(DBPart.user_id == creator_id)
    part = db.scalars(exact_stmt).first()
    if part:
        return part
    fuzzy_stmt = select(DBPart).where(
        DBPart.gtin.isnot(None),
        DBPart.canonical_part_id.is_(None),
    )
    if creator_id is not None:
        fuzzy_stmt = fuzzy_stmt.where(DBPart.user_id == creator_id)
    for c in db.scalars(fuzzy_stmt).all():
        if c.gtin and normalize_gtin(c.gtin) == normalized:
            return c
    return None


def find_existing_part_for_create(
    db: Session,
    *,
    creator_id: UUID,
    product_url: Optional[str] = None,
) -> Optional[tuple[DBPart, str]]:
    """
    Decide whether a part-create attempt should be denied in favor of an
    existing part the same user already owns.

    Policy — URL-only, per-user matching: if the creator already has a part
    with a listing for this exact ``product_url``, deny and point them at
    their own prior entry (no accidental self-duplicates). Different users may
    each contribute their own row for the same URL.

    Returns ``(existing_part, "own_part_exists")`` or ``None`` if nothing
    blocks the create.
    """
    if not product_url or not product_url.strip():
        return None

    # Scope by ``creator_id`` in the query (not after ``.first()``) so we
    # don't miss the creator's own row when another user also has one for
    # this URL.
    own = find_part_by_product_url(db, product_url, creator_id=creator_id)
    if own is not None:
        return own, "own_part_exists"

    return None


def create_or_update_listing_and_price(
    db: Session,
    part_id: UUID,
    retailer_id: UUID,
    *,
    product_url: Optional[str] = None,
    price_cents: Optional[int] = None,
    observed_at: Optional[datetime] = None,
) -> DBPartListing:
    """
    Create or update PartListing for (part_id, retailer_id).
    If price_cents is provided, append PartPriceHistory and update listing's last_known_price_cents/last_price_updated_at.
    Returns the PartListing.
    """
    listing = db.scalars(
        select(DBPartListing).where(
            DBPartListing.part_id == part_id,
            DBPartListing.retailer_id == retailer_id,
        )
    ).first()
    if not listing and product_url:
        normalized_url = _normalize_url(product_url)
        if normalized_url:
            listing = db.scalars(
                select(DBPartListing).where(
                    DBPartListing.part_id == part_id,
                    DBPartListing.product_url == normalized_url,
                )
            ).first()
    if not listing:
        listing = DBPartListing(
            part_id=part_id,
            retailer_id=retailer_id,
            product_url=_normalize_url(product_url) if product_url else None,
        )
        db.add(listing)
        db.flush()

    if product_url and _normalize_url(product_url):
        listing.product_url = _normalize_url(product_url)
        db.add(listing)
        db.flush()

    if price_cents is not None and price_cents >= 0:
        ts = observed_at or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        target_date = ts.date()

        # Max one price record per listing per calendar day (UTC); upsert if same day
        existing = db.scalars(
            select(DBPartPriceHistory).where(
                DBPartPriceHistory.part_listing_id == listing.id,
                func.date(DBPartPriceHistory.observed_at) == target_date,
            )
        ).first()
        if existing:
            existing.price_cents = price_cents
            existing.observed_at = ts
            db.add(existing)
        else:
            history = DBPartPriceHistory(
                part_listing_id=listing.id,
                price_cents=price_cents,
                observed_at=ts,
            )
            db.add(history)
        db.flush()
        listing.last_known_price_cents = price_cents
        listing.last_price_updated_at = ts
        db.add(listing)
        db.flush()

        # S07/T03: evaluate per-user price-drop alerts on this part. Same
        # gating condition as the price-history append above (price_cents
        # not None and >= 0). Alert evaluation is exception-safe at the
        # per-alert level — a bad subscription must not poison the
        # price-write transaction. Local import avoids a circular service
        # import at module load.
        from app.api.services.part_price_alert_service import (
            evaluate_alerts_for_listing,
        )

        evaluate_alerts_for_listing(
            db,
            part_id=part_id,
            retailer_id=retailer_id,
            price_cents=price_cents,
            observed_at=ts,
        )

    return listing


def get_best_listing_for_part(db: Session, part_id: UUID) -> Optional[DBPartListing]:
    """Return the PartListing with the lowest current price for this part."""
    return db.scalars(
        select(DBPartListing)
        .where(
            DBPartListing.part_id == part_id,
            DBPartListing.last_known_price_cents.isnot(None),
            DBPartListing.last_known_price_cents >= 0,
        )
        .order_by(DBPartListing.last_known_price_cents.asc())
    ).first()


def domain_from_url(url: str) -> Optional[str]:
    """Extract domain (hostname) from a URL for retailer lookup."""
    if not url or not url.strip():
        return None
    try:
        parsed = urlparse(url.strip())
        if parsed.netloc:
            return parsed.netloc.lower()
        return None
    except Exception:
        return None
