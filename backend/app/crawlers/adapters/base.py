"""
Base class for retailer crawler adapters.

Adapters implement URL discovery and page parsing; the shared runner handles
fetch and ingest.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Optional

from app.crawlers.base import ScrapedPayload


class RetailerCrawlerAdapter(ABC):
    """
    Per-retailer adapter: discover product URLs and parse a product page into ScrapedPayload.

    Subclass and implement discover_product_urls() and parse_product_page(html, url).
    """

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
