"""
Example retailer adapter: stub that yields no URLs by default.

Use this as a template for real adapters. Override discover_product_urls() to yield
actual product URLs (e.g. from a sitemap or category page), and parse_product_page()
to extract name, price, brand, part_number, etc. from the retailer's HTML/JSON.
"""

from typing import Iterator, Optional

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload


class ExampleRetailerAdapter(RetailerCrawlerAdapter):
    """
    Stub adapter. discover_product_urls() yields nothing; parse_product_page() returns None.

    To implement a real retailer:
    1. In discover_product_urls(): fetch category/sitemap/search and yield product URLs.
    2. In parse_product_page(): use BeautifulSoup or regex to extract fields into ScrapedPayload.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield no URLs by default. Replace with sitemap/category logic for a real retailer."""
        yield from ()

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Return None (not a product page / not implemented)."""
        return None
