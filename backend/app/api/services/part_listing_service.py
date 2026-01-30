"""
Service for part listing deduplication and retailer/listing/price operations.

Used by global part create, create-and-add-part, and scrapers to:
- Get-or-create retailers and brands
- Find existing parts by URL or brand+part_number
- Create/update PartListing and append PartPriceHistory
"""

from datetime import UTC, datetime
import re
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.models.brand import Brand as DBBrand
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.part_listing import PartListing as DBPartListing
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
        retailer = db.query(DBRetailer).filter(DBRetailer.domain == domain_normalized).first()
        if retailer:
            return retailer
    retailer = db.query(DBRetailer).filter(DBRetailer.name == name.strip()).first()
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


def get_or_create_brand_by_name(db: Session, name: str) -> Optional[DBBrand]:
    """Get existing brand by name (case-insensitive); otherwise create. Returns None if name is empty."""
    if not name or not name.strip():
        return None
    name_normalized = name.strip()
    brand = db.query(DBBrand).filter(DBBrand.name.ilike(name_normalized)).first()
    if brand:
        return brand
    brand = DBBrand(name=name_normalized, is_active=True)
    db.add(brand)
    db.flush()
    return brand


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


def find_part_by_product_url(db: Session, product_url: str) -> Optional[DBGlobalPart]:
    """Find a global part by product URL (via PartListing only)."""
    normalized = _normalize_url(product_url)
    if not normalized:
        return None
    listing = db.query(DBPartListing).filter(DBPartListing.product_url == normalized).first()
    if listing:
        return listing.global_part
    return None


def find_part_by_brand_and_part_number(
    db: Session,
    brand_id: int,
    part_number: str,
) -> Optional[DBGlobalPart]:
    """Find a global part by brand_id and part_number. Uses normalized part_number for matching."""
    normalized = normalize_part_number(part_number)
    if not normalized:
        return None
    # Match by normalized value, or by exact strip (for legacy rows stored before normalization)
    exact = part_number.strip()
    candidates = (
        db.query(DBGlobalPart)
        .filter(
            DBGlobalPart.brand_id == brand_id,
            or_(DBGlobalPart.part_number == normalized, DBGlobalPart.part_number == exact),
        )
        .all()
    )
    for c in candidates:
        if normalize_part_number(c.part_number) == normalized:
            return c
    return None


def create_or_update_listing_and_price(
    db: Session,
    global_part_id: int,
    retailer_id: int,
    *,
    product_url: Optional[str] = None,
    price_cents: Optional[int] = None,
    observed_at: Optional[datetime] = None,
) -> DBPartListing:
    """
    Create or update PartListing for (global_part_id, retailer_id).
    If price_cents is provided, append PartPriceHistory and update listing's last_known_price_cents/last_price_updated_at.
    Returns the PartListing.
    """
    listing = (
        db.query(DBPartListing)
        .filter(
            DBPartListing.global_part_id == global_part_id,
            DBPartListing.retailer_id == retailer_id,
        )
        .first()
    )
    if not listing:
        listing = DBPartListing(
            global_part_id=global_part_id,
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


def get_best_listing_for_part(
    db: Session, global_part_id: int
) -> Optional[DBPartListing]:
    """
    Return the PartListing with the lowest current price for this part.
    Uses last_known_price_cents; only considers listings that have a price.
    Returns None if the part has no listings with a price.
    """
    return (
        db.query(DBPartListing)
        .filter(
            DBPartListing.global_part_id == global_part_id,
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
