"""
Crawler runner: discover URLs from an adapter, fetch, parse, and ingest.

Run from backend directory:
    python -m app.crawlers --adapter example
    python -m app.crawlers --adapter example --limit 5

Requires env:
    CRAWLER_USER_ID: user ID to attribute created parts to (must have create permission).
    CRAWLER_DEFAULT_CATEGORY_ID: category ID for new parts (optional if CRAWLER_DEFAULT_CATEGORY_NAME set).
    CRAWLER_DEFAULT_CATEGORY_NAME: category name (e.g. exhaust) for new parts (used if category_id not set).

Optional (full-page archive for post-processing):
    CRAWL_HTML_SAVE_DIR: directory path to save full page HTML (always saved for every URL crawled).
"""

import argparse
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import pybreaker
import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.core.cloudwatch_emf import emit_crawler_run_metrics
from app.crawlers.adapters import ADAPTER_REGISTRY, get_adapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    DEFAULT_USER_AGENT,
    apply_delay_jitter,
    can_fetch_url,
    canonicalize_url,
    crawl_html_fingerprint,
    get_crawl_delay_sec,
    ingest_payload,
    save_crawl_page_html,
)
from app.crawlers.fetchers import FetcherError, get_fetcher
from app.db.session import API_CONNECTION_RESERVE, DB_MAX_OVERFLOW, DB_POOL_SIZE, SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class CrawlerConfigError(ValueError):
    """Raised when crawler env/config is invalid (CRAWLER_USER_ID, category, etc)."""

    pass


# Per-adapter-name pybreaker registry (CRAWL-04 / D-08).
# Replaces the old RATE_LIMIT_CIRCUIT_BREAKER_* counter block with a
# thread-safe pybreaker CircuitBreaker keyed by ADAPTER_NAME. Breakers
# are shared across ThreadPoolExecutor workers for the same adapter, so
# a trip in one worker affects every subsequent fetch for that adapter.
# Pitfall BR-01: module-level Lock + double-checked locking prevents
# two workers constructing breakers for the same adapter in parallel.
_BREAKERS: dict[str, pybreaker.CircuitBreaker] = {}
_BREAKERS_LOCK = threading.Lock()


def get_breaker(adapter_name: str) -> pybreaker.CircuitBreaker:
    """Return the process-global breaker for ``adapter_name``, creating it on first access.

    Config per D-09:
      - ``fail_max=3``: three consecutive exceptions through ``breaker.call()``
        trip it (the 4th call raises CircuitBreakerError).
      - ``reset_timeout=120``: OPEN state lasts 120s before auto-transitioning
        to HALF-OPEN for a single trial call.
    """
    breaker = _BREAKERS.get(adapter_name)
    if breaker is not None:
        return breaker
    with _BREAKERS_LOCK:
        breaker = _BREAKERS.get(adapter_name)
        if breaker is not None:
            return breaker
        breaker = pybreaker.CircuitBreaker(
            fail_max=3,
            reset_timeout=120,
            name=adapter_name,
        )
        _BREAKERS[adapter_name] = breaker
        return breaker


def _get_crawler_user(db: Session) -> DBUser:
    """
    Return the crawler service account (is_service_account=True).
    Falls back to CRAWLER_USER_ID env var for backwards compatibility with local/CLI usage.
    Raises CrawlerConfigError when neither resolves (API-safe; does not sys.exit).
    """
    user = db.scalars(select(DBUser).where(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False))).first()
    if user:
        return user

    # Fallback: legacy env-var path (CLI / local dev before service account is seeded).
    # WR-03: ``User.id`` is UUID-based (see ``is_service_account`` filter above and
    # ``resolve_crawler_user`` below which uses the ``UUID`` type). The previous
    # ``int(raw)`` cast was vestigial from the pre-UUID schema and produced a
    # misleading "must be an integer" error for valid UUID strings. Parse as UUID
    # to match the model.
    raw = os.environ.get("CRAWLER_USER_ID")
    if raw:
        try:
            user_id = UUID(raw)
        except ValueError as exc:
            raise CrawlerConfigError("CRAWLER_USER_ID must be a valid UUID.") from exc
        user = db.scalars(select(DBUser).where(DBUser.id == user_id)).first()
        if not user:
            raise CrawlerConfigError(f"CRAWLER_USER_ID={user_id}: no user found.")
        if user.disabled:
            raise CrawlerConfigError(f"CRAWLER_USER_ID={user_id}: user is disabled.")
        return user

    raise CrawlerConfigError(
        "No crawler service account found and CRAWLER_USER_ID is not set. "
        "Ensure the app has run its startup initialisation (which creates the service account)."
    )


def resolve_crawler_user(db: Session, user_id_override: Optional[UUID] = None) -> DBUser:
    """
    Resolve crawler user. Uses user_id_override if provided, else CRAWLER_USER_ID env.
    """
    if user_id_override is not None:
        user = db.scalars(select(DBUser).where(DBUser.id == user_id_override)).first()
        if not user:
            raise CrawlerConfigError(f"Crawler user_id={user_id_override}: no user found.")
        if user.disabled:
            raise CrawlerConfigError(f"Crawler user_id={user_id_override}: user is disabled.")
        return user
    return _get_crawler_user(db)


def resolve_default_category_id(db: Session, category_id_override: Optional[UUID] = None) -> UUID:
    """
    Resolve default category. Uses category_id_override if provided, else env vars.
    """
    if category_id_override is not None:
        cat = db.scalars(select(DBCategory).where(DBCategory.id == category_id_override)).first()
        if not cat or not cat.is_active:
            raise CrawlerConfigError(f"Default category_id={category_id_override}: not found or inactive.")
        return cat.id
    return _get_default_category_id(db)


def _get_default_category_id(db: Session) -> UUID:
    """
    Resolve default category from CRAWLER_DEFAULT_CATEGORY_ID or CRAWLER_DEFAULT_CATEGORY_NAME.
    Raises CrawlerConfigError if no category can be resolved (API-safe; does not sys.exit).
    """
    raw_id = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
    if raw_id:
        try:
            cat_id = UUID(raw_id)
        except ValueError:
            pass
        else:
            cat = db.scalars(select(DBCategory).where(DBCategory.id == cat_id)).first()
            if cat and cat.is_active:
                return cat.id
            logger.warning("CRAWLER_DEFAULT_CATEGORY_ID=%s: category not found or inactive.", raw_id)

    name = os.environ.get("CRAWLER_DEFAULT_CATEGORY_NAME", "").strip()
    if name:
        cat = db.scalars(select(DBCategory).where(DBCategory.name == name, DBCategory.is_active)).first()
        if cat:
            return cat.id
        logger.warning("CRAWLER_DEFAULT_CATEGORY_NAME=%r: category not found or inactive.", name)

    # Fallback: first active category
    first = db.scalars(select(DBCategory).where(DBCategory.is_active).order_by(DBCategory.sort_order)).first()
    if first:
        logger.info("Using first active category: id=%s name=%s", first.id, first.name)
        return first.id

    raise CrawlerConfigError(
        "No default category. Set CRAWLER_DEFAULT_CATEGORY_ID or CRAWLER_DEFAULT_CATEGORY_NAME, "
        "or ensure categories are seeded."
    )


def _upsert_crawled_page(
    db: Session,
    *,
    url: str,
    source: str,
    storage_key: Optional[str],
    part_id: Optional[UUID],
    html_sha256: Optional[str] = None,
) -> None:
    """
    Create or update a CrawledPage record for the given URL.
    storage_key is an S3 key (no leading "/") or an absolute local path (starts with "/").
    part_id, when provided, marks the parse as successful.
    Calls db.flush() — caller is responsible for the surrounding commit.
    """
    now = datetime.now(timezone.utc)

    html_s3_key: Optional[str] = None
    html_local_path: Optional[str] = None
    if storage_key:
        if storage_key.startswith("/"):
            html_local_path = storage_key
        else:
            html_s3_key = storage_key

    insert_values: dict = {
        "url": url,
        "source": source,
        "crawled_at": now,
        "parse_status": "pending",
        "html_s3_key": html_s3_key,
        "html_local_path": html_local_path,
        "part_id": part_id,
    }
    if part_id is not None:
        insert_values["parse_status"] = "parsed"
        insert_values["last_parsed_at"] = now
    if html_sha256 is not None:
        insert_values["html_sha256"] = html_sha256

    update_values: dict = {"crawled_at": now}
    if html_s3_key is not None:
        update_values["html_s3_key"] = html_s3_key
    if html_local_path is not None:
        update_values["html_local_path"] = html_local_path
    if part_id is not None:
        update_values["part_id"] = part_id
        update_values["parse_status"] = "parsed"
        update_values["last_parsed_at"] = now
    if html_sha256 is not None:
        update_values["html_sha256"] = html_sha256

    stmt = (
        pg_insert(DBCrawledPage)
        .values(**insert_values)
        .on_conflict_do_update(index_elements=["url"], set_=update_values)
    )
    db.execute(stmt)
    db.flush()


def _http_status_from_exception(e: BaseException) -> Optional[int]:
    """
    Extract an HTTP status code from any exception the fetcher tiers can raise.

    - ``requests.HTTPError`` carries the status on ``.response.status_code``.
    - ``FetcherError`` (TlsFetcher / FlareSolverrFetcher) carries it on
      ``.status_code`` when the failure was driven by a 4xx/5xx upstream.

    Returns ``None`` for timeouts, DNS failures, and other non-HTTP errors.
    """
    if isinstance(e, requests.exceptions.HTTPError):
        resp = getattr(e, "response", None)
        return getattr(resp, "status_code", None)
    if isinstance(e, FetcherError):
        return e.status_code
    return None


def _classify_fetch_error(e: BaseException, status: Optional[int]) -> str:
    """
    Bucket a fetch/parse failure into a short label for the per-adapter
    http_errors breakdown. HTTP statuses are stringified ("404", "503"); other
    failure modes get a descriptive key so the report separates timeouts,
    connection issues, and unexpected exceptions.
    """
    if status is not None:
        return str(status)
    if isinstance(e, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "connection"
    if isinstance(e, requests.exceptions.TooManyRedirects):
        return "redirects"
    if isinstance(e, requests.exceptions.SSLError):
        return "ssl"
    if isinstance(e, FetcherError):
        return "fetcher"
    return "other"


def _mark_url_gone(db: Session, *, url: str, source: str) -> None:
    """
    Upsert a CrawledPage row with parse_status='gone' so later runs skip the dead URL.
    Retailers advertise removed products in sitemaps indefinitely; without this marker
    we re-fetch and 404 on the same URLs every run.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(DBCrawledPage)
        .values(url=url, source=source, crawled_at=now, parse_status="gone")
        .on_conflict_do_update(
            index_elements=["url"],
            set_={"crawled_at": now, "parse_status": "gone"},
        )
    )
    db.execute(stmt)
    db.flush()


def _bulk_insert_pending_urls(
    db: Session,
    *,
    canonical_urls: list[str],
    source: str,
    chunk_size: int = 1000,
) -> int:
    """
    Insert rows for discovered URLs with parse_status='pending'.
    ON CONFLICT (url) DO NOTHING preserves any existing row — we never downgrade
    a parsed/gone/failed URL or reassign its source. Caller commits.

    Returns the count of rows actually inserted (i.e. URLs new to crawled_pages).
    """
    if not canonical_urls:
        return 0
    now = datetime.now(timezone.utc)
    # Dedupe: sitemaps sometimes list variants that canonicalize to the same URL.
    unique_urls = list({u for u in canonical_urls if u})
    inserted_total = 0
    for start in range(0, len(unique_urls), chunk_size):
        chunk = unique_urls[start : start + chunk_size]
        values = [{"url": u, "source": source, "crawled_at": now, "parse_status": "pending"} for u in chunk]
        stmt = (
            pg_insert(DBCrawledPage)
            .values(values)
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(DBCrawledPage.id)
        )
        result = db.execute(stmt)
        inserted_total += len(result.all())
    db.flush()
    return inserted_total


def run_crawler(
    adapter_name: str,
    *,
    limit: Optional[int] = None,
    delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
    user_id: Optional[UUID] = None,
    default_category_id: Optional[UUID] = None,
    crawl_html_save_dir: Optional[str] = None,
    stop_event: Optional[threading.Event] = None,
    skip_known_urls: bool = False,
) -> dict:
    """
    Run one adapter: discover URLs, fetch, parse, ingest. Optionally cap at `limit` URLs.
    If user_id or default_category_id are provided, use them; otherwise fall back to env vars.
    Saves full page HTML to the archive for every URL crawled (new and previously-seen).
    If stop_event is provided and set, the loop exits early (cooperative cancellation).
    If skip_known_urls is True, URLs already in crawled_pages with parse_status='parsed' are
    filtered out before the limit is applied — useful for successive test runs against the same site.
    Returns a dict: {"adapter": name, "ingested": int, "skipped": int, "errors": int, "total": int}.
    Raises CrawlerConfigError or KeyError (unknown adapter) on setup failure.
    """
    db: Session = SessionLocal()
    # Fetcher is constructed inside the try block (after we know the adapter
    # exists); bound here at None so the finally block's cleanup pass is safe
    # even when we fail before construction.
    fetcher = None
    try:
        # Bail before we spend time on discovery (which itself does network
        # I/O for sitemaps and can sit in retry-backoff loops).
        if stop_event is not None and stop_event.is_set():
            logger.info("Adapter %s: cancelled before discovery.", adapter_name)
            return {"adapter": adapter_name, "ingested": 0, "skipped": 0, "errors": 0, "total": 0, "cancelled": True}
        user = resolve_crawler_user(db, user_id)
        cat_id = resolve_default_category_id(db, default_category_id)
        # Construct the fetcher matching this adapter's declared tier before the
        # adapter itself, so the adapter's discover_product_urls() (which may
        # need the upgraded fetcher for sitemap calls on Tier 1/2 sites) can
        # use self.fetcher. Existing Tier 0 adapters that call module-level
        # fetch_page() directly are unaffected — they get an HttpFetcher they
        # simply don't touch.
        adapter_cls = ADAPTER_REGISTRY[adapter_name] if adapter_name in ADAPTER_REGISTRY else None
        tier = adapter_cls.FETCHER_TIER if adapter_cls is not None else "http"
        fetcher = get_fetcher(tier)
        logger.info("Adapter %s: using fetcher tier %r (%s)", adapter_name, tier, fetcher.__class__.__name__)
        adapter = get_adapter(adapter_name, fetcher=fetcher)

        # Pre-crawl health gate (CRAWL-06 / D-19). If the adapter's configured
        # HEALTH_PROBE_URL comes back unhealthy, skip the URL loop entirely
        # and return a result row tagged with health_skipped=True — the job
        # report surfaces it so operators see "adapter X was down, not broken."
        # Adapters that leave HEALTH_PROBE_URL=None (DISC-04 Option A default)
        # short-circuit inside check_health and return healthy=True.
        health = adapter.check_health()
        if not health.healthy:
            logger.warning(
                "skipping %s: health=%s status=%s",
                adapter_name,
                health.reason,
                health.status_code,
            )
            return {
                "adapter": adapter_name,
                "ingested": 0,
                "skipped": 0,
                "skipped_robots": 0,
                "skipped_not_product": 0,
                "skipped_gone": 0,
                "errors": 0,
                "total": 0,
                "http_errors": {},
                "error_urls": [],
                "error_urls_truncated": False,
                "parse_miss_urls": [],
                "parse_miss_urls_truncated": False,
                "rate_limit_bailout": False,
                "rate_limit_bailout_after": 0,
                "health_skipped": True,
                "health_reason": f"health_{health.reason}",
                "health_status_code": health.status_code,
                # CRAWL-07: health check ran BEFORE the URL loop (and before
                # `t0`), so elapsed_seconds is 0.0 on this path. parse_failures
                # is trivially 0 — no URLs processed.
                "parse_failures": 0,
                "sample_failure_urls": [],
                "elapsed_seconds": 0.0,
            }

        urls = list(adapter.discover_product_urls())
        if urls:
            canonical_urls = [canonicalize_url(u) for u in urls]
            # Persist every discovered URL as pending before any filter/limit,
            # so catalog size stays visible across interrupted runs. A pending
            # row is an IOU, not a signal the URL is done — the skip filter
            # below never skips pending, so scraping behavior is unchanged.
            try:
                inserted = _bulk_insert_pending_urls(db, canonical_urls=canonical_urls, source=adapter_name)
                db.commit()
                logger.info(
                    "Adapter %s: discovered %s URL(s); %s newly persisted as pending.",
                    adapter_name,
                    len(canonical_urls),
                    inserted,
                )
            except Exception as e:
                db.rollback()
                logger.warning(
                    "Adapter %s: failed to bulk-persist discovered URLs (%s); continuing.",
                    adapter_name,
                    e,
                )
            statuses_to_skip = ["gone"]
            if skip_known_urls:
                statuses_to_skip.append("parsed")
            skip_set = set(
                db.scalars(
                    select(DBCrawledPage.url).where(
                        DBCrawledPage.url.in_(canonical_urls),
                        DBCrawledPage.parse_status.in_(statuses_to_skip),
                    )
                ).all()
            )
            if skip_set:
                before = len(urls)
                urls = [u for u in urls if canonicalize_url(u) not in skip_set]
                logger.info(
                    "Adapter %s: skipped %s known-%s URL(s), %s remaining.",
                    adapter_name,
                    before - len(urls),
                    "/".join(statuses_to_skip),
                    len(urls),
                )
        if limit is not None:
            urls = urls[:limit]
        total = len(urls)
        if total == 0:
            # Discovery returning zero is almost always a broken sitemap or a
            # silently-swallowed exception inside the adapter's discover path,
            # not a genuinely empty catalog. WARNING so it stands out in logs.
            logger.warning(
                "Adapter %s: discovered 0 URLs — likely broken sitemap or discovery path.",
                adapter_name,
            )
        else:
            logger.info("Adapter %s: %s URL(s) to process.", adapter_name, total)

        ingested = 0
        skipped_robots = 0
        skipped_not_product = 0
        skipped_gone = 0
        errors = 0
        # Per-adapter breakdown of non-2xx fetch outcomes. Keys are stringified
        # HTTP statuses ("404", "503") plus named buckets ("timeout",
        # "connection", etc.) — surfaced in the end-of-job report email so
        # operators can see *which* upstream failures dominated a run rather
        # than just a single aggregate error count.
        http_errors: dict[str, int] = {}
        # Bounded per-URL failure samples for the job report. Errors carry
        # the exception and HTTP status; parse-miss samples help an operator
        # spot adapter drift (e.g., the HTML layout changed). Capped so a
        # broken sitewide scrape can't balloon the job row's JSON blob.
        error_urls: list[dict[str, Any]] = []
        parse_miss_urls: list[dict[str, Any]] = []
        _MAX_SAMPLES = 50
        # Circuit-breaker state (CRAWL-04). `rate_limit_bailout` flips to
        # True when the pybreaker trips and is surfaced in the returned
        # result. The breaker is process-global per ADAPTER_NAME, hoisted
        # ONCE outside the URL loop so all iterations share state.
        rate_limit_bailout = False
        rate_limit_bailout_after = 0
        breaker = get_breaker(adapter_name)

        # CRAWL-07 / Plan 03-03: wall-clock start for `elapsed_seconds` in the
        # result dict. Captured AFTER check_health (which has its own timeout)
        # so elapsed_seconds measures the URL-loop cost exclusively. Used by
        # both the success-path return and the breaker-bail return below.
        # OBS-02 / D-17: `start_ts` aliases `t0` so the EMF emission at the
        # end of run_crawler uses the same wall-clock window as the return
        # dict's `elapsed_seconds` field.
        start_ts = time.monotonic()
        t0 = start_ts

        for i, url in enumerate(urls, 1):
            if stop_event is not None and stop_event.is_set():
                logger.info("Adapter %s: stop requested, exiting after %s/%s URLs.", adapter_name, i - 1, total)
                break
            try:
                if i > 1:
                    # Honor robots.txt Crawl-delay if set; use the larger of --delay and directive
                    crawl_delay = get_crawl_delay_sec(url, DEFAULT_USER_AGENT)
                    base_delay = max(delay_sec, crawl_delay or 0)
                    actual_delay = apply_delay_jitter(base_delay)
                    time.sleep(actual_delay)
                if not can_fetch_url(url, DEFAULT_USER_AGENT):
                    skipped_robots += 1
                    logger.info(
                        "[%s/%s] Skipped (robots.txt disallows): %s",
                        i,
                        total,
                        url,
                    )
                    continue
                try:
                    html = breaker.call(adapter.fetcher.fetch, url)
                except pybreaker.CircuitBreakerError:
                    # Pitfall BR-03: this handler MUST precede the generic
                    # `except Exception` below. Breaker is OPEN — skip the
                    # rest of the URL list and record the bailout.
                    logger.error(
                        "Adapter %s: breaker OPEN after %s URLs; bailing.",
                        adapter_name,
                        i,
                    )
                    rate_limit_bailout = True
                    rate_limit_bailout_after = i
                    break
                payload = adapter.parse_product_page(html, url)
                if payload is None:
                    skipped_not_product += 1
                    # Per-URL log stays at INFO: a single miss is usually a
                    # non-product URL in the sitemap (category/blog/etc).
                    # The end-of-run summary escalates if the rate is high.
                    logger.info(
                        "[%s/%s] Skipped (not a product page or parse failed): %s",
                        i,
                        total,
                        url,
                    )
                    if len(parse_miss_urls) < _MAX_SAMPLES:
                        parse_miss_urls.append({"url": url})
                    continue
                arch_url = canonicalize_url(url)
                html_utf8, _, html_sha = crawl_html_fingerprint(html)
                existing = db.scalars(select(DBCrawledPage).where(DBCrawledPage.url == arch_url)).first()
                storage_key: Optional[str]
                if existing and existing.html_sha256 == html_sha and (existing.html_s3_key or existing.html_local_path):
                    storage_key = existing.html_s3_key or existing.html_local_path
                else:
                    storage_key = save_crawl_page_html(
                        adapter_name,
                        arch_url,
                        html,
                        "",
                        html_utf8=html_utf8,
                        logger_instance=logger,
                    )
                part = ingest_payload(
                    db,
                    payload,
                    current_user=user,
                    default_category_id=cat_id,
                    logger=logger,
                    source="scraped",
                )
                _upsert_crawled_page(
                    db,
                    url=arch_url,
                    source=adapter_name,
                    storage_key=storage_key,
                    part_id=part.id,
                    html_sha256=html_sha,
                )
                ingested += 1
                logger.info("[%s/%s] Ingested: %s", i, total, url)
            except Exception as e:
                # 404 / 410 are routine on retailer sitemaps — the product has
                # been removed but the sitemap still lists the URL. Count as a
                # skip so one stale entry doesn't show up as a scary traceback
                # alongside 49 healthy pages. HttpFetcher raises
                # requests.HTTPError (status on .response); TlsFetcher and
                # FlareSolverrFetcher raise FetcherError with .status_code.
                status = _http_status_from_exception(e)
                bucket = _classify_fetch_error(e, status)
                http_errors[bucket] = http_errors.get(bucket, 0) + 1
                # Pre-trip the breaker on any terminal 429/503 per D-11: a
                # single such response is upstream explicitly telling us to
                # back off. Manually opening here means the NEXT URL's
                # breaker.call() raises CircuitBreakerError and bails out,
                # without waiting for fail_max=3 to accumulate.
                #
                # WR-04: ``breaker.call`` already recorded this fetch as a
                # failure for pybreaker's internal accounting before re-raising
                # into this except block. Only force the state machine to OPEN
                # when it's still CLOSED/HALF_OPEN — pybreaker treats open->open
                # as a no-op, but this avoids re-issuing the warning in the
                # already-open case (e.g. concurrent worker tripped it first)
                # and keeps the manual override visibly tied to a state change.
                if status in (429, 503):
                    if breaker.current_state != "open":
                        logger.warning(
                            "Adapter %s: terminal %s on URL %s — forcing breaker OPEN for 120s (D-11)",
                            adapter_name,
                            status,
                            url,
                        )
                        breaker.open()
                if status in (404, 410):
                    skipped_gone += 1
                    logger.warning("[%s/%s] Skipped (HTTP %s gone): %s", i, total, status, url)
                    db.rollback()
                    try:
                        _mark_url_gone(db, url=canonicalize_url(url), source=adapter_name)
                        db.commit()
                    except Exception as mark_err:
                        db.rollback()
                        logger.warning("Failed to mark %s as gone: %s", url, mark_err)
                else:
                    errors += 1
                    logger.exception("Error processing %s: %s", url, e)
                    if len(error_urls) < _MAX_SAMPLES:
                        error_urls.append(
                            {
                                "url": url,
                                "status": status,
                                "bucket": bucket,
                                "error": str(e),
                            }
                        )
                    db.rollback()

        skipped = skipped_robots + skipped_not_product + skipped_gone
        # Pick the summary log level based on how healthy the run looks. A
        # retailer that discovered pages but ingested zero is almost always a
        # broken parser (or sitewide 4xx) — surface it at ERROR so it isn't
        # buried in the INFO stream alongside healthy adapters. High but
        # non-total miss rates (>50% parse-None on at least 10 URLs) are a
        # softer signal of drift and go to WARNING.
        summary_level = logging.INFO
        summary_reason = ""
        if rate_limit_bailout:
            summary_level = logging.ERROR
            summary_reason = (
                " — rate-limit circuit breaker tripped after %s/%s URLs; upstream appears to be shedding load"
                % (rate_limit_bailout_after, total)
            )
        elif total > 0 and ingested == 0:
            summary_level = logging.ERROR
            summary_reason = " — 0 ingested from %s URLs, adapter likely broken" % total
        elif total >= 10 and skipped_not_product > total * 0.5:
            summary_level = logging.WARNING
            summary_reason = " — >50%% of pages failed to parse as products, adapter may be drifting"
        elif errors > 0 and errors >= max(1, total // 4):
            summary_level = logging.WARNING
            summary_reason = " — %s error(s) on %s URLs" % (errors, total)
        # OBS-02 / D-17 — emit EMF BEFORE the summary log (RESEARCH Landmine 3:
        # aws-embedded-metrics issue #109 drops the final EMF line if no non-EMF
        # line follows; the summary log below acts as the flush trigger).
        # NEVER reorder these two blocks.
        emit_crawler_run_metrics(
            adapter_name=adapter_name,
            run_type="live",  # runner.py handles live path; rescrape path emits separately in ecs_rescrape_runner.py (D-21)
            ingested=ingested,
            parse_failures=skipped_not_product,  # D-22: parse_failures == skipped_not_product
            elapsed_seconds=time.monotonic() - start_ts,
        )
        logger.log(
            summary_level,
            "Adapter %s done. Ingested=%s skipped=%s (robots=%s not_product=%s gone=%s) errors=%s total=%s%s",
            adapter_name,
            ingested,
            skipped,
            skipped_robots,
            skipped_not_product,
            skipped_gone,
            errors,
            total,
            summary_reason,
        )
        return {
            "adapter": adapter_name,
            "ingested": ingested,
            "skipped": skipped,
            "skipped_robots": skipped_robots,
            "skipped_not_product": skipped_not_product,
            "skipped_gone": skipped_gone,
            "errors": errors,
            "total": total,
            "http_errors": http_errors,
            # Bounded samples for the job report. Consumers show these in
            # the email + admin UI so an operator can jump straight to a
            # problem URL instead of inferring it from counts.
            "error_urls": error_urls,
            "error_urls_truncated": errors > len(error_urls),
            "parse_miss_urls": parse_miss_urls,
            "parse_miss_urls_truncated": skipped_not_product > len(parse_miss_urls),
            # Circuit-breaker trip. Present on every result (False when the
            # adapter ran to completion) so report renderers can key off it
            # without worrying about missing fields. `_after` is 0 unless
            # tripped; it records the URL index at which we bailed.
            "rate_limit_bailout": rate_limit_bailout,
            "rate_limit_bailout_after": rate_limit_bailout_after,
            # Pre-crawl health-probe outcome (CRAWL-06). False on successful
            # runs (this path); the early-return above sets True and fills
            # `health_reason` / `health_status_code`. Present on every result
            # for consistent schema across healthy + skipped paths.
            "health_skipped": False,
            "health_reason": None,
            "health_status_code": None,
            # CRAWL-07 (Plan 03-03): parse-failure count + first-5 URL samples
            # (encounter order, URL-only per D-23) + wall-clock elapsed.
            # `parse_failures` is an alias for `skipped_not_product` expressing
            # intent distinctly from transport/HTTP "errors" — Phase 2 OBS-02
            # CloudWatch reads these keys without any further schema change.
            "parse_failures": skipped_not_product,
            "sample_failure_urls": [p["url"] for p in parse_miss_urls[:5]],
            "elapsed_seconds": round(time.monotonic() - t0, 3),
        }
    finally:
        # Close the fetcher if we got far enough to create one. FlareSolverr
        # in particular holds a server-side browser session we want to destroy
        # cleanly so we don't pile up orphaned Chromium instances in its pool.
        if fetcher is not None:
            try:
                fetcher.close()
            except Exception as e:
                logger.warning("Fetcher cleanup failed: %s", e)
        db.close()


def _compute_adapter_workers(num_adapters: int) -> int:
    """
    Decide how many adapter threads may run in parallel.

    Scales up to ``num_adapters`` by default but never beyond what the DB pool
    can sustain while still reserving ``API_CONNECTION_RESERVE`` connections
    for live API traffic. Each running adapter holds exactly one SessionLocal
    for its full run, so the ceiling is
    ``DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE``.

    ``CRAWLER_MAX_ADAPTER_WORKERS`` (int env var) is an operator override that
    caps worker count regardless of pool size — useful for throttling against
    external constraints (RDS max_connections, FlareSolverr pool, upstream
    retailer rate limits) without bouncing the process.
    """
    worker_budget = max(1, DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE)
    max_workers = min(num_adapters, worker_budget)

    override_raw = os.environ.get("CRAWLER_MAX_ADAPTER_WORKERS")
    if override_raw:
        try:
            override = int(override_raw)
            if override > 0:
                max_workers = min(max_workers, override)
        except ValueError:
            logger.warning("Ignoring non-integer CRAWLER_MAX_ADAPTER_WORKERS=%r", override_raw)

    return max(1, max_workers)


def run_crawlers(
    adapter_names: list[str],
    *,
    limits: Optional[dict[str, int]] = None,
    global_limit: Optional[int] = None,
    delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
    delays: Optional[dict[str, float]] = None,
    parallel: bool = True,
    user_id: Optional[UUID] = None,
    default_category_id: Optional[UUID] = None,
    default_category_ids: Optional[dict[str, UUID]] = None,
    crawl_html_save_dir: Optional[str] = None,
    stop_event: Optional[threading.Event] = None,
    skip_known_urls: bool = False,
    skip_known_urls_by_adapter: Optional[dict[str, bool]] = None,
) -> dict:
    """
    Run one or more adapters. If multiple adapters, runs them in parallel threads by default.

    Args:
        adapter_names: List of adapter names (e.g. ["a90shop", "example"]).
        limits: Per-adapter limits: {"a90shop": 10, "example": 5}. Overrides global_limit when set.
        global_limit: Limit applied to all adapters when no per-adapter limit is set.
        delay_sec: Default delay between requests per crawler when no per-adapter override is set.
        delays: Per-adapter delay override: {"a90shop": 7.5}. Falls back to ``delay_sec``.
        parallel: If True and len(adapter_names) > 1, run in parallel threads.
        default_category_id: Default category used when no per-adapter override is set.
        default_category_ids: Per-adapter category override: {"a90shop": <uuid>}.
            Falls back to ``default_category_id``.
        crawl_html_save_dir: Kept for backward compatibility; HTML is always archived for every URL.
        stop_event: Optional threading.Event for cooperative cancellation across all adapters.
        skip_known_urls: Default skip flag when no per-adapter override is set.
        skip_known_urls_by_adapter: Per-adapter override: {"a90shop": True}.

    Returns:
        {
            "results": [{"adapter": str, "ingested": int, "skipped": int, "errors": int, "total": int}, ...],
            "summary": {"total_ingested": int, "total_skipped": int, "total_errors": int},
            "failed": [{"adapter": str, "error": str}, ...],
        }
    """
    limits = limits or {}
    delays = delays or {}
    default_category_ids = default_category_ids or {}
    skip_known_urls_by_adapter = skip_known_urls_by_adapter or {}
    results: list[dict] = []
    failed: list[dict] = []

    def run_one(name: str) -> dict | None:
        # Skip work entirely if cancellation was requested before this future
        # was pulled off the queue. Otherwise queued adapters still spin up a
        # DB session, build a fetcher, and run sitemap discovery (with its own
        # retries) before they get to the per-URL stop-event check — which is
        # exactly what makes a 50-adapter cancel feel like it "isn't working."
        if stop_event is not None and stop_event.is_set():
            logger.info("Adapter %s: cancelled before start.", name)
            return {"adapter": name, "ingested": 0, "skipped": 0, "errors": 0, "total": 0, "cancelled": True}
        limit = limits.get(name)
        if limit is None and global_limit is not None:
            limit = global_limit
        adapter_delay = delays.get(name, delay_sec)
        adapter_skip = skip_known_urls_by_adapter.get(name, skip_known_urls)
        adapter_category = default_category_ids.get(name, default_category_id)
        try:
            return run_crawler(
                name,
                limit=limit,
                delay_sec=adapter_delay,
                user_id=user_id,
                default_category_id=adapter_category,
                crawl_html_save_dir=crawl_html_save_dir,
                stop_event=stop_event,
                skip_known_urls=adapter_skip,
            )
        except (CrawlerConfigError, KeyError) as e:
            return {"_error": str(e), "_adapter": name}
        except Exception as e:
            logger.exception("Crawler %s failed: %s", name, e)
            return {"_error": str(e), "_adapter": name}

    if len(adapter_names) > 1 and parallel:
        max_workers = _compute_adapter_workers(len(adapter_names))
        if max_workers < len(adapter_names):
            logger.info(
                "Capping adapter parallelism at %s (requested %s). Set CRAWLER_MAX_ADAPTER_WORKERS to override.",
                max_workers,
                len(adapter_names),
            )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_one, name): name for name in adapter_names}
            for future in as_completed(futures):
                r = future.result()
                if r is None:
                    continue
                if "_error" in r:
                    failed.append({"adapter": r["_adapter"], "error": r["_error"]})
                else:
                    results.append(r)
    else:
        for name in adapter_names:
            r = run_one(name)
            if r is None:
                continue
            if "_error" in r:
                failed.append({"adapter": r["_adapter"], "error": r["_error"]})
            else:
                results.append(r)

    total_ingested = sum(r.get("ingested", 0) for r in results)
    total_skipped = sum(r.get("skipped", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    total_http_errors: dict[str, int] = {}
    for r in results:
        for bucket, count in (r.get("http_errors") or {}).items():
            total_http_errors[bucket] = total_http_errors.get(bucket, 0) + count

    return {
        "results": results,
        "summary": {
            "total_ingested": total_ingested,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
            "total_http_errors": total_http_errors,
        },
        "failed": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a retailer crawler adapter (discover URLs, fetch, parse, ingest).",
    )
    parser.add_argument(
        "--adapter",
        required=True,
        choices=list(ADAPTER_REGISTRY.keys()),
        help="Adapter name to run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of product URLs to process (default: no limit).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SEC,
        help=f"Seconds to wait between requests (default: {DEFAULT_REQUEST_DELAY_SEC}).",
    )
    parser.add_argument(
        "--skip-known",
        action="store_true",
        default=False,
        help="Skip URLs already in crawled_pages with parse_status='parsed'.",
    )
    args = parser.parse_args()

    try:
        run_crawler(args.adapter, limit=args.limit, delay_sec=args.delay, skip_known_urls=args.skip_known)
    except CrawlerConfigError as e:
        logger.error("%s", e)
        sys.exit(1)
    except KeyError as e:
        logger.error("Unknown adapter: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
