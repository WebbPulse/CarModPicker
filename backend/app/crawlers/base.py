"""
Shared crawler base: ScrapedPayload contract, HTTP fetch, and ingest pipeline.

No page parsing lives here; that is entirely in per-retailer adapters.

Respects robots.txt: we check can_fetch_url() before each request and honor
Crawl-delay when present (use the larger of --delay and the directive).

Rate limiting: on 429/503 we retry with exponential backoff, honor Retry-After,
and add jitter. Staying unbanned is prioritized over speed.
"""

import hashlib
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional, Protocol
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
from app.core.car_inference import infer_car_generations, resolve_car_triples_to_ids
from app.core.category_inference import infer_category

logger = logging.getLogger(__name__)

# Optional: save full page HTML for post-processing. Set CRAWL_HTML_SAVE_DIR (or pass via API) to enable.
# When bucket is configured (S3), we upload to the bucket; otherwise we write to local path.
# When set, we save HTML for new URLs only by default; set CRAWL_HTML_SAVE_ON_RECRAWL=1 to overwrite on recrawl too.
CRAWL_HTML_HASH_BYTES = 16  # filename = <sha256(url)>[:16].html so re-crawls overwrite same file


class _S3PutObjectProtocol(Protocol):
    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
    ) -> object: ...

    def get_object(self, *, Bucket: str, Key: str) -> dict: ...


# Lazy S3 client for crawl HTML uploads. Uses CRAWL_BUCKET (separate from user images).
# Falls back to local filesystem if CRAWL_BUCKET is not configured.
_crawl_s3_client: Optional[_S3PutObjectProtocol] = None
_crawl_bucket_name: Optional[str] = None


def _get_crawl_s3_client() -> tuple[Optional[_S3PutObjectProtocol], Optional[str]]:
    """Return (s3_client, bucket_name) for the crawl data bucket; else (None, None)."""
    global _crawl_s3_client, _crawl_bucket_name
    if _crawl_s3_client is not None or _crawl_bucket_name is not None:
        return _crawl_s3_client, _crawl_bucket_name
    try:
        from app.core.config import settings

        bucket = (settings.CRAWL_BUCKET or "").strip()
        if not bucket:
            logger.info(
                "Crawl HTML bucket not configured (CRAWL_BUCKET missing); will use local path as fallback"
            )
            return None, None
        import boto3

        # Pass explicit credentials only when provided; otherwise boto3 uses its default
        # credential chain (IAM role, env vars, ~/.aws/credentials, etc.)
        client_kwargs: dict = {
            "region_name": settings.AWS_REGION or None,
            "endpoint_url": settings.S3_ENDPOINT_URL or None,
        }
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        _crawl_s3_client = boto3.client("s3", **client_kwargs)
        _crawl_bucket_name = bucket
        return _crawl_s3_client, _crawl_bucket_name
    except Exception as e:
        logger.info("Crawl HTML bucket not available (will use local path if save enabled): %s", e)
        return None, None


def url_is_known(db: Session, product_url: str) -> bool:
    """True if we already have a part listing with this product_url (i.e. recrawl, not first visit)."""
    if not product_url or not product_url.strip():
        return False
    return find_part_by_product_url(db, product_url) is not None


def save_crawl_page_html(
    adapter_name: str,
    product_url: str,
    html: str,
    base_dir: str | Path,
    *,
    logger_instance: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Save a full page HTML copy for post-processing. When the app's bucket is configured,
    uploads to S3 under key prefix base_dir (e.g. "crawl_html"). Otherwise writes
    to local path base_dir. Filename is hash of URL so recrawls overwrite. Also writes a .url sidecar
    so we can re-parse later (know which URL the HTML came from).

    Returns the S3 key (e.g. "crawl_html/a90shop/abc123.html") on S3 success,
    the absolute local path string on local success, or None on failure.
    """
    log = logger_instance or logger
    key_prefix = str(base_dir).strip() if base_dir else ""
    url_hash = hashlib.sha256(product_url.encode()).hexdigest()[:CRAWL_HTML_HASH_BYTES]
    html_key = (
        f"{key_prefix}/{adapter_name}/{url_hash}.html" if key_prefix else f"crawl_html/{adapter_name}/{url_hash}.html"
    )
    url_key = (
        f"{key_prefix}/{adapter_name}/{url_hash}.url" if key_prefix else f"crawl_html/{adapter_name}/{url_hash}.url"
    )

    s3_client, bucket_name = _get_crawl_s3_client()
    if s3_client is not None and bucket_name is not None:
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=html_key,
                Body=html.encode("utf-8", errors="replace"),
                ContentType="text/html; charset=utf-8",
            )
            s3_client.put_object(
                Bucket=bucket_name,
                Key=url_key,
                Body=product_url.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
            log.info("Saved page copy to bucket: %s", html_key)
            return html_key
        except Exception as e:
            log.warning("Could not save page copy to bucket %s: %s", html_key, e)
            return None

    # Fallback: local filesystem (bucket not configured or client failed)
    base_path = Path(base_dir) if base_dir else Path("crawl_html")
    if not base_path.is_absolute() and not base_path.exists():
        base_path.mkdir(parents=True, exist_ok=True)
    dir_path = base_path / adapter_name
    dir_path.mkdir(parents=True, exist_ok=True)
    html_path = dir_path / f"{url_hash}.html"
    url_path = dir_path / f"{url_hash}.url"
    try:
        html_path.write_text(html, encoding="utf-8", errors="replace")
        url_path.write_text(product_url, encoding="utf-8")
        log.info("Saved page copy to local (bucket not configured): %s", html_path)
        return str(html_path.resolve())
    except OSError as e:
        log.warning("Could not save page copy to %s: %s", html_path, e)
        return None


# Default delay between requests (seconds) to be polite to retailers.
# Conservative for price monitoring; Scrapy AutoThrottle defaults to 5s; 2.5s is a balance.
DEFAULT_REQUEST_DELAY_SEC = 2.5
DEFAULT_TIMEOUT_SEC = 30
DEFAULT_USER_AGENT = "CarModPicker-Crawler/1.0 (+https://carmodpicker.com)"

# Jitter on normal request delay (±20%) so traffic doesn't look robotic; best practice for polite crawlers.
REQUEST_DELAY_JITTER_FRACTION = 0.2

# Rate-limit backoff: we retry on these status codes (staying unbanned over speed)
RATE_LIMIT_STATUS_CODES = (429, 503)
MAX_RATE_LIMIT_RETRIES = 5
BACKOFF_BASE_SEC = 2.0
BACKOFF_MAX_SEC = 300.0
BACKOFF_JITTER_FRACTION = 0.2  # ±20% jitter to avoid thundering herd

# Transient network errors (timeouts, connection failures): retry a few times with backoff
MAX_TIMEOUT_RETRIES = 2  # 2 retries = 3 total attempts per URL
TIMEOUT_BACKOFF_BASE_SEC = 3.0

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
    """Apply upward-only jitter so we never wait less than Retry-After."""
    jitter = 1.0 + random.uniform(0, BACKOFF_JITTER_FRACTION)  # [1.0, 1.2]
    return min(retry_after_sec * jitter, BACKOFF_MAX_SEC)


def apply_delay_jitter(delay_sec: float, jitter_fraction: float = REQUEST_DELAY_JITTER_FRACTION) -> float:
    """
    Apply ±jitter to a delay so request spacing isn't perfectly regular (polite crawler best practice).
    Returns delay_sec * (1 ± jitter_fraction), clamped to at least 0.5s.
    """
    jitter = 1.0 + random.uniform(-jitter_fraction, jitter_fraction)
    return max(0.5, delay_sec * jitter)


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


def _timeout_backoff_sec(attempt: int) -> float:
    """Exponential backoff with jitter for timeout/connection retries."""
    backoff = min(
        TIMEOUT_BACKOFF_BASE_SEC * (2**attempt),
        BACKOFF_MAX_SEC,
    )
    jitter = backoff * BACKOFF_JITTER_FRACTION * (2 * random.random() - 1)
    return max(1.0, backoff + jitter)


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

    On ReadTimeout, ConnectTimeout, or ConnectionError: retries up to MAX_TIMEOUT_RETRIES
    times with backoff, then re-raises.
    """
    req_session = session or requests.Session()
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    timeout_errors = (requests.ReadTimeout, requests.ConnectTimeout, requests.ConnectionError)

    for timeout_attempt in range(MAX_TIMEOUT_RETRIES + 1):
        try:
            for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
                try:
                    resp = req_session.get(url, headers=headers, timeout=timeout)
                except timeout_errors as e:
                    # Let outer loop handle timeout/connection retries
                    raise
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
            raise RuntimeError("fetch_page: unexpected exit from rate-limit retry loop")
        except requests.HTTPError:
            # Non–rate-limit 4xx/5xx: raise immediately (no retry)
            raise
        except timeout_errors as e:
            if timeout_attempt >= MAX_TIMEOUT_RETRIES:
                raise
            backoff = _timeout_backoff_sec(timeout_attempt)
            logger.warning(
                "Timeout/connection error for %s (attempt %s/%s), retrying in %.1fs: %s",
                url,
                timeout_attempt + 1,
                MAX_TIMEOUT_RETRIES + 1,
                backoff,
                e,
            )
            time.sleep(backoff)

    raise RuntimeError("fetch_page: unexpected exit from timeout retry loop")


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

    # Infer car make/model/generation from name/description/URL when possible
    triples = infer_car_generations(payload.name, payload.description, payload.product_url)
    inferred_car_ids = resolve_car_triples_to_ids(db, triples) if triples else []
    if inferred_car_ids:
        logger.debug(
            "Inferred cars %s for part %s",
            inferred_car_ids,
            (payload.name or "")[:50],
        )

    create_data = GlobalPartCreate(
        name=payload.name,
        description=payload.description,
        image_url=payload.image_url,
        image_urls=payload.image_urls[:12] if payload.image_urls else None,
        product_url=payload.product_url,
        category_id=category_id,
        car_ids=inferred_car_ids if inferred_car_ids else [],
        is_universal=not inferred_car_ids,
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
