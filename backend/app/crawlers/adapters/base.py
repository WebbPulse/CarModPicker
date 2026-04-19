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
from typing import ClassVar, Iterator, Literal, Optional

from app.crawlers.base import ScrapedPayload
from app.crawlers.fetchers import Fetcher, get_fetcher

FetcherTier = Literal["http", "tls", "browser"]


class RetailerCrawlerAdapter(ABC):
    """
    Per-retailer adapter: discover product URLs and parse a product page into ScrapedPayload.

    Subclass and implement discover_product_urls() and parse_product_page(html, url).
    Override ``FETCHER_TIER`` on the subclass when plain requests isn't enough
    (Cloudflare TLS-fingerprint block → ``"tls"``; managed JS challenge → ``"browser"``).
    """

    #: Which fetcher tier to use. Default is plain-HTTP; override on subclasses
    #: that need TLS impersonation or a headless browser.
    FETCHER_TIER: ClassVar[FetcherTier] = "http"

    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        # The runner passes in a fetcher matched to FETCHER_TIER so adapters
        # don't have to know which concrete class they got. Constructed lazily
        # here for direct instantiation (tests, REPL, one-off scripts).
        self.fetcher: Fetcher = fetcher if fetcher is not None else get_fetcher(self.FETCHER_TIER)

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
