"""
Per-retailer crawler adapters.

Each adapter implements: discover_product_urls() and parse_product_page(html, url).
Register new adapters in ADAPTER_REGISTRY so the runner can run them by name.

``generic`` is always the last-resort fallback and should not be passed to the
crawler runner CLI (it has no discover_product_urls implementation).
"""

from urllib.parse import urlparse

from app.crawlers.adapters.a90shop import A90ShopAdapter
from app.crawlers.adapters.adro import AdroAdapter
from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.adapters.generic import GenericHtmlParser
from app.crawlers.adapters.studiorsr import StudioRSRAdapter

ADAPTER_REGISTRY: dict[str, type[RetailerCrawlerAdapter]] = {
    "a90shop": A90ShopAdapter,
    "adro": AdroAdapter,
    "studiorsr": StudioRSRAdapter,
    "generic": GenericHtmlParser,
}


def adapter_name_for_product_url(url: str) -> str:
    """
    Map a product page URL's host to a registered adapter name.

    Returns a site-specific adapter key when the host is a known retailer,
    otherwise returns ``"generic"`` so any URL can be parsed.

    Used by:
    - POST /crawled-pages/scrape  (live scrape from Chrome extension)
    - archive rescrape pipeline   (admin re-parse of stored HTML)
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "generic"
    if not host:
        return "generic"
    if host == "studiorsr.com" or host.endswith(".studiorsr.com"):
        return "studiorsr"
    if host.endswith("a90shop.com"):
        return "a90shop"
    if host == "adro.com" or host.endswith(".adro.com"):
        return "adro"
    return "generic"


def get_adapter(name: str) -> RetailerCrawlerAdapter:
    """Return an adapter instance by name. Raises KeyError if unknown."""
    if name not in ADAPTER_REGISTRY:
        raise KeyError(f"Unknown adapter: {name}. Available: {list(ADAPTER_REGISTRY.keys())}")
    return ADAPTER_REGISTRY[name]()
