"""
Base class for retailer crawler adapters.

Adapters implement URL discovery and page parsing; the shared runner handles
fetch and ingest.

Each adapter declares a ``FETCHER_TIER`` — ``"http"``, ``"tls"``, or
``"browser"`` — that controls which fetcher the runner uses for product page
fetches. Adapters that need the upgraded fetcher for sitemap/discovery calls
too should call ``self.fetcher.fetch(...)`` from ``discover_product_urls()``
rather than the module-level ``fetch_page``. See ``crawlers/fetchers.py`` and
``crawlers/README.md`` for the tier model.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Iterator, Literal, Optional

from app.crawlers.base import ScrapedPayload
from app.crawlers.fetchers import Fetcher, get_fetcher

FetcherTier = Literal["http", "tls", "browser"]


@dataclass(frozen=True)
class HealthResult:
    """Result of a pre-crawl adapter health probe (CRAWL-06, D-18/D-19)."""

    healthy: bool
    reason: str  # "ok" | "http_4xx" | "http_5xx" | "timeout" | "connection" | "skipped_by_config"
    status_code: int | None


class RetailerCrawlerAdapter(ABC):
    """
    Per-retailer adapter: discover product URLs and parse a product page into ScrapedPayload.

    Subclass and implement discover_product_urls() and parse_product_page(html, url).
    Override ``FETCHER_TIER`` on the subclass when plain requests isn't enough
    (Cloudflare TLS-fingerprint block → ``"tls"``; managed JS challenge → ``"browser"``).
    """

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # IS_FALLBACK=True marks GenericHtmlParser (excluded from ADAPTER_REGISTRY per D-03).
        if getattr(cls, "IS_FALLBACK", False):
            return
        # Still-abstract intermediate bases (e.g., Shopify/WooCommerce mixins) have no slug.
        if getattr(cls, "__abstractmethods__", None):
            return
        name = getattr(cls, "ADAPTER_NAME", "")
        if not isinstance(name, str) or not name.strip():
            raise TypeError(
                f"{cls.__module__}.{cls.__qualname__} must declare "
                f"ADAPTER_NAME: ClassVar[str] = '<slug>' (non-empty). See D-02."
            )

    #: Globally-unique slug for this adapter. Enforced non-empty by __init_subclass__.
    #: Must equal the existing ADAPTER_REGISTRY key verbatim (no derivation from class name per D-02).
    ADAPTER_NAME: ClassVar[str] = ""
    #: When True, this adapter is the URL-host fallback and is excluded from ADAPTER_REGISTRY (per D-03).
    IS_FALLBACK: ClassVar[bool] = False
    #: URL to probe in check_health(). `None` = opt out (per DISC-04 Option A — default opt-in).
    HEALTH_PROBE_URL: ClassVar[str | None] = None
    #: Which fetcher tier to use. Default is plain-HTTP; override on subclasses
    #: that need TLS impersonation or a headless browser.
    FETCHER_TIER: ClassVar[FetcherTier] = "http"

    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        # Defer default-fetcher construction until first access. Archive rescrape
        # instantiates adapters only to call parse_product_page() — it never
        # touches self.fetcher — so it shouldn't have to satisfy discovery-time
        # config (e.g. FLARESOLVERR_URL) for browser-tier adapters.
        self._fetcher: Optional[Fetcher] = fetcher

    @property
    def fetcher(self) -> Fetcher:
        if self._fetcher is None:
            self._fetcher = get_fetcher(self.FETCHER_TIER)
        return self._fetcher

    @abstractmethod
    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product page URLs for this retailer (sitemap, category, search, or fixed list).
        """
        ...

    @abstractmethod
    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a product page HTML (and optional url for context) into ScrapedPayload.
        Return None if the page is not a product page or parsing fails.
        """
        ...

    def check_health(self) -> HealthResult:
        """Opt-in pre-crawl health probe. Default implementation honors HEALTH_PROBE_URL=None.

        Plan 02 (CRAWL-06) will wire the probe I/O path; Plan 01 lands the
        opt-out default only so subclasses can already opt in declaratively.
        """
        probe_url = type(self).HEALTH_PROBE_URL
        if probe_url is None:
            return HealthResult(healthy=True, reason="skipped_by_config", status_code=None)
        # Probe I/O wired in Plan 02 (CRAWL-06). For Plan 01, fall through to the opt-out default.
        return HealthResult(healthy=True, reason="skipped_by_config", status_code=None)
