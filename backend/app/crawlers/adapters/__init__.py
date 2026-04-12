"""
Per-retailer crawler adapters.

Each adapter implements: discover_product_urls() and parse_product_page(html, url).
Register new adapters in ADAPTER_REGISTRY so the runner can run them by name.
"""

from typing import Optional
from urllib.parse import urlparse

from app.crawlers.adapters.a90shop import A90ShopAdapter
from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.adapters.studiorsr import StudioRSRAdapter

ADAPTER_REGISTRY: dict[str, type[RetailerCrawlerAdapter]] = {
    "a90shop": A90ShopAdapter,
    "studiorsr": StudioRSRAdapter,
}


def adapter_name_for_product_url(url: str) -> Optional[str]:
    """
    Map a product page URL's host to a registered adapter name.

    Used when archived HTML came from the Chrome extension (source ``chrome_extension``)
    but should be parsed with the same logic as a retailer crawl.
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return None
    if not host:
        return None
    if host == "studiorsr.com" or host.endswith(".studiorsr.com"):
        return "studiorsr"
    if host.endswith("a90shop.com"):
        return "a90shop"
    return None


def get_adapter(name: str) -> RetailerCrawlerAdapter:
    """Return an adapter instance by name. Raises KeyError if unknown."""
    if name not in ADAPTER_REGISTRY:
        raise KeyError(f"Unknown adapter: {name}. Available: {list(ADAPTER_REGISTRY.keys())}")
    return ADAPTER_REGISTRY[name]()
