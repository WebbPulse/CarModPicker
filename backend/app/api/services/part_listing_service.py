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

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.retailer import Retailer as DBRetailer


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
        retailer = (
            db.query(DBRetailer)
            .filter(or_(DBRetailer.domain == domain_normalized, DBRetailer.domain == domain_alt))
            .first()
        )
        if retailer:
            return retailer
    retailer = db.query(DBRetailer).filter(DBRetailer.name.ilike(name.strip())).first()
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


def get_or_create_part_manufacturer_by_name(db: Session, name: str) -> Optional[DBPartManufacturer]:
    """Get existing part manufacturer by name (case-insensitive); otherwise create. Returns None if name is empty."""
    if not name or not name.strip():
        return None
    name_normalized = name.strip()
    part_manufacturer = db.query(DBPartManufacturer).filter(DBPartManufacturer.name.ilike(name_normalized)).first()
    if part_manufacturer:
        return part_manufacturer
    part_manufacturer = DBPartManufacturer(name=name_normalized, is_active=True)
    db.add(part_manufacturer)
    db.flush()
    return part_manufacturer


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


def find_part_by_product_url(db: Session, product_url: str) -> Optional[DBPart]:
    """Find a part by product URL (via PartListing only)."""
    normalized = _normalize_url(product_url)
    if not normalized:
        return None
    listing = db.query(DBPartListing).filter(DBPartListing.product_url == normalized).first()
    if listing:
        return listing.part
    return None


def find_part_by_part_manufacturer_and_part_number(
    db: Session,
    part_manufacturer_id: UUID,
    part_number: str,
) -> Optional[DBPart]:
    """Find a part by part_manufacturer_id and part_number. Uses normalized part_number for matching."""
    normalized = normalize_part_number(part_number)
    if not normalized:
        return None
    exact = part_number.strip()
    candidates = (
        db.query(DBPart)
        .filter(
            DBPart.part_manufacturer_id == part_manufacturer_id,
            or_(DBPart.part_number == normalized, DBPart.part_number == exact),
        )
        .all()
    )
    for c in candidates:
        if normalize_part_number(c.part_number) == normalized:
            return c
    return None


def normalize_gtin(gtin: Optional[str]) -> Optional[str]:
    """
    Normalize GTIN (UPC/EAN) to digits only for storage and dedup lookup.
    Handles formats like 0-12345-67890-1 or 012345678901.
    """
    if not gtin or not gtin.strip():
        return None
    digits = "".join(c for c in gtin.strip() if c.isdigit())
    return digits if digits else None


def find_part_by_gtin(db: Session, gtin: str) -> Optional[DBPart]:
    """Find a part by GTIN (UPC/EAN). Uses normalized digits-only for matching."""
    normalized = normalize_gtin(gtin)
    if not normalized:
        return None
    part = db.query(DBPart).filter(DBPart.gtin == normalized).first()
    if part:
        return part
    candidates = db.query(DBPart).filter(DBPart.gtin.isnot(None)).all()
    for c in candidates:
        if c.gtin and normalize_gtin(c.gtin) == normalized:
            return c
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
    listing = (
        db.query(DBPartListing)
        .filter(
            DBPartListing.part_id == part_id,
            DBPartListing.retailer_id == retailer_id,
        )
        .first()
    )
    if not listing and product_url:
        normalized_url = _normalize_url(product_url)
        if normalized_url:
            listing = (
                db.query(DBPartListing)
                .filter(
                    DBPartListing.part_id == part_id,
                    DBPartListing.product_url == normalized_url,
                )
                .first()
            )
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
        existing = (
            db.query(DBPartPriceHistory)
            .filter(
                DBPartPriceHistory.part_listing_id == listing.id,
                func.date(DBPartPriceHistory.observed_at) == target_date,
            )
            .first()
        )
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

    return listing


def get_best_listing_for_part(db: Session, part_id: UUID) -> Optional[DBPartListing]:
    """Return the PartListing with the lowest current price for this part."""
    return (
        db.query(DBPartListing)
        .filter(
            DBPartListing.part_id == part_id,
            DBPartListing.last_known_price_cents.isnot(None),
            DBPartListing.last_known_price_cents >= 0,
        )
        .order_by(DBPartListing.last_known_price_cents.asc())
        .first()
    )


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
