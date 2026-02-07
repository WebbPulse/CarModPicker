"""
Shared crawler base: ScrapedPayload contract, HTTP fetch, and ingest pipeline.

No page parsing lives here; that is entirely in per-retailer adapters.

Respects robots.txt: we check can_fetch_url() before each request and honor
Crawl-delay when present (use the larger of --delay and the directive).

Rate limiting: on 429/503 we retry with exponential backoff, honor Retry-After,
and add jitter. Staying unbanned is prioritized over speed.
"""

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from sqlalchemy.orm import Session

from app.api.endpoints.global_parts import GlobalPartService
from app.api.models.category import Category as DBCategory
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.schemas.global_part import GlobalPartCreate
from app.api.services.part_listing_service import (
    create_or_update_listing_and_price,
    domain_from_url,
    find_part_by_brand_and_part_number,
    find_part_by_gtin,
    find_part_by_product_url,
    get_or_create_brand_by_name,
    get_or_create_retailer,
    normalize_gtin,
)
from app.core.category_inference import infer_category

logger = logging.getLogger(__name__)

# Default delay between requests (seconds) to be polite to retailers
DEFAULT_REQUEST_DELAY_SEC = 1.5
DEFAULT_TIMEOUT_SEC = 30
DEFAULT_USER_AGENT = "CarModPicker-Crawler/1.0 (+https://carmodpicker.webbpulse.com)"

# Rate-limit backoff: we retry on these status codes (staying unbanned over speed)
RATE_LIMIT_STATUS_CODES = (429, 503)
MAX_RATE_LIMIT_RETRIES = 5
BACKOFF_BASE_SEC = 2.0
BACKOFF_MAX_SEC = 300.0
BACKOFF_JITTER_FRACTION = 0.2  # ±20% jitter to avoid thundering herd

# Cache of robots.txt parsers per origin (scheme + netloc)
_robots_cache: Dict[str, RobotFileParser] = {}


@dataclass
class ScrapedPayload:
    """
    Canonical output from any retailer adapter. Maps to GlobalPartCreate + listing/price.
    """

    name: str
    product_url: str
    description: Optional[str] = None
    price_cents: Optional[int] = None
    brand: Optional[str] = None
    part_number: Optional[str] = None
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
    gtin: Optional[str] = None

    def __post_init__(self) -> None:
        if self.image_urls is None and self.image_url:
            self.image_urls = [self.image_url]
        elif self.image_urls and not self.image_url:
            self.image_url = self.image_urls[0]


def _origin_from_url(url: str) -> str:
    """Return scheme + netloc for a URL (e.g. https://www.a90shop.com)."""
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or ""
    return f"{scheme}://{netloc}"


def _get_robots_parser(origin: str, user_agent: str = DEFAULT_USER_AGENT) -> Optional[RobotFileParser]:
    """
    Fetch and parse robots.txt for the given origin; cache and return the parser.
    Returns None on failure (caller should treat as allow to avoid blocking on broken robots.txt).
    """
    if origin in _robots_cache:
        return _robots_cache[origin]
    robots_url = origin.rstrip("/") + "/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
        _robots_cache[origin] = parser
        return parser
    except Exception as e:
        logger.debug("Could not fetch robots.txt for %s: %s; allowing crawl.", origin, e)
        return None


def can_fetch_url(url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    """
    Return True if robots.txt allows the given user agent to fetch the URL.
    If robots.txt is unavailable or errors, we allow (do not block the crawl).
    """
    origin = _origin_from_url(url)
    parser = _get_robots_parser(origin, user_agent)
    if parser is None:
        return True
    return parser.can_fetch(user_agent, url)


def get_crawl_delay_sec(url: str, user_agent: str = DEFAULT_USER_AGENT) -> Optional[float]:
    """
    Return Crawl-delay in seconds for this origin if set in robots.txt, else None.
    Non-standard but used by some sites; we honor it by using max(--delay, crawl_delay).
    """
    origin = _origin_from_url(url)
    parser = _get_robots_parser(origin, user_agent)
    if parser is None:
        return None
    try:
        raw = parser.crawl_delay(user_agent)
        if raw is None:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_retry_after(value: Optional[str], attempt: int) -> float:
    """
    Parse Retry-After header: delay-seconds (int) or HTTP-date.
    Falls back to exponential backoff (BACKOFF_BASE_SEC * 2^attempt) capped at BACKOFF_MAX_SEC.
    """
    if not value or not value.strip():
        return min(BACKOFF_BASE_SEC * (2**attempt), BACKOFF_MAX_SEC)
    value = value.strip()
    try:
        return float(int(value))
    except ValueError:
        pass
    try:
        # HTTP-date: Wed, 21 Oct 2015 07:28:00 GMT
        retry_at = parsedate_to_datetime(value)
        now = datetime.now(timezone.utc)
        delta = (retry_at - now).total_seconds()
        return max(0.0, min(delta, BACKOFF_MAX_SEC))
    except Exception:
        return min(BACKOFF_BASE_SEC * (2**attempt), BACKOFF_MAX_SEC)


def _rate_limit_backoff_sec(retry_after_sec: float, attempt: int) -> float:
    """Apply jitter to backoff time to avoid synchronized retries."""
    jitter = 1.0 + random.uniform(-BACKOFF_JITTER_FRACTION, BACKOFF_JITTER_FRACTION)
    return min(retry_after_sec * jitter, BACKOFF_MAX_SEC)


def _retailer_name_from_domain(domain: str) -> str:
    """Derive a display name from domain (e.g. www.a90shop.com -> A90shop)."""
    if not domain or not domain.strip():
        return "Unknown"
    d = domain.strip().lower()
    # Strip www. prefix
    if d.startswith("www."):
        d = d[4:].lstrip(".")
    if not d:
        return "Unknown"
    # Use the part before the last dot (e.g. a90shop from a90shop.com), title-cased
    if "." in d:
        d = d.rsplit(".", 1)[0]
    return d.title() if d else "Unknown"


def fetch_page(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    user_agent: str = DEFAULT_USER_AGENT,
    session: Optional[requests.Session] = None,
) -> str:
    """
    Fetch a page as HTML. Uses requests (no JS).

    On 429 (Too Many Requests) or 503 (Service Unavailable): retries with exponential
    backoff, honors Retry-After when present, and adds jitter. After MAX_RATE_LIMIT_RETRIES
    retries, re-raises the last response. Other non-2xx responses raise immediately.
    """
    req_session = session or requests.Session()
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            resp = req_session.get(url, headers=headers, timeout=timeout)
            if resp.status_code in RATE_LIMIT_STATUS_CODES:
                if attempt >= MAX_RATE_LIMIT_RETRIES:
                    resp.raise_for_status()
                retry_after_raw = resp.headers.get("Retry-After")
                backoff = _parse_retry_after(retry_after_raw, attempt)
                backoff = _rate_limit_backoff_sec(backoff, attempt)
                logger.warning(
                    "Rate limited (HTTP %s) for %s; Retry-After=%s, backing off %.1fs (attempt %s/%s)",
                    resp.status_code,
                    url,
                    retry_after_raw,
                    backoff,
                    attempt + 1,
                    MAX_RATE_LIMIT_RETRIES + 1,
                )
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except requests.HTTPError:
            # Non–rate-limit 4xx/5xx: raise immediately
            raise

    raise RuntimeError("fetch_page: unexpected exit from retry loop")


def ingest_payload(
    db: Session,
    payload: ScrapedPayload,
    *,
    current_user: DBUser,
    default_category_id: int,
    logger: logging.Logger,
    source: str = "scraped",
) -> DBGlobalPart:
    """
    Resolve retailer and brand, then create or update global part + PartListing/PartPriceHistory
    using the same dedup logic as the API (URL, brand+part_number, GTIN).
    """
    domain = domain_from_url(payload.product_url)
    if not domain:
        raise ValueError(f"Cannot derive domain from product_url: {payload.product_url}")
    friendly_name = _retailer_name_from_domain(domain)
    retailer = get_or_create_retailer(
        db,
        name=friendly_name,
        domain=domain,
        base_url=f"https://{domain}" if domain else None,
    )
    # Fix existing retailers that were created with the old dashed-domain name
    if retailer.name == domain.replace(".", "-"):
        retailer.name = friendly_name
        retailer.base_url = retailer.base_url or (f"https://{domain}" if domain else None)
        db.add(retailer)
    db.flush()

    # Central brand list: all crawlers and the extension use the same DB. get_or_create_brand_by_name
    # ensures a brand is only defined once; manual edits in the app apply everywhere.
    brand_name = (payload.brand or "").strip() or "Unknown"
    brand = get_or_create_brand_by_name(db, brand_name)
    if not brand:
        raise ValueError("Could not resolve or create brand")
    db.flush()

    # Infer category from name/description when possible; else use default
    category_id = default_category_id
    inferred_name = infer_category(payload.name, payload.description)
    if inferred_name:
        cat = db.query(DBCategory).filter(DBCategory.name == inferred_name, DBCategory.is_active).first()
        if cat:
            category_id = cat.id
            logger.debug("Inferred category %s for part %s", inferred_name, (payload.name or "")[:50])

    create_data = GlobalPartCreate(
        name=payload.name,
        description=payload.description,
        image_url=payload.image_url,
        image_urls=payload.image_urls[:12] if payload.image_urls else None,
        product_url=payload.product_url,
        category_id=category_id,
        brand_id=brand.id,
        part_number=payload.part_number,
        gtin=payload.gtin,
        retailer_id=retailer.id,
        price_cents=payload.price_cents,
    )

    # Detect existing part (same dedup order as service: URL, brand+part_number, GTIN)
    # so we can log "update" vs "create" and ensure we always refresh listing/price history
    existing_part = None
    if payload.product_url and payload.product_url.strip():
        existing_part = find_part_by_product_url(db, payload.product_url)
    if existing_part is None and brand.id and payload.part_number and payload.part_number.strip():
        existing_part = find_part_by_brand_and_part_number(db, brand.id, payload.part_number)
    if existing_part is None and payload.gtin and normalize_gtin(payload.gtin):
        existing_part = find_part_by_gtin(db, payload.gtin)

    if existing_part is not None:
        logger.info(
            "Existing part %s matched (by URL/brand+part/GTIN); refreshing listing and price history for retailer %s",
            existing_part.id,
            retailer.id,
        )

    service = GlobalPartService()
    part = service.create(
        db,
        create_data,
        current_user,
        logger,
        additional_data={"source": source},
    )

    # Always create/update PartListing and PartPriceHistory (new or re-scrape):
    # set product_url, append PartPriceHistory when price_cents provided, update last_known_price_cents
    create_or_update_listing_and_price(
        db,
        part.id,
        retailer.id,
        product_url=payload.product_url,
        price_cents=payload.price_cents,
    )
    db.commit()
    return part
