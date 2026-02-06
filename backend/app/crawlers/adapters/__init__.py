"""
Per-retailer crawler adapters.

Each adapter implements: discover_product_urls() and parse_product_page(html, url).
Register new adapters in ADAPTER_REGISTRY so the runner can run them by name.
"""

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.adapters.example import ExampleRetailerAdapter
from app.crawlers.adapters.a90shop import A90ShopAdapter

ADAPTER_REGISTRY: dict[str, type[RetailerCrawlerAdapter]] = {
    "example": ExampleRetailerAdapter,
    "a90shop": A90ShopAdapter,
}


def get_adapter(name: str) -> RetailerCrawlerAdapter:
    """Return an adapter instance by name. Raises KeyError if unknown."""
    if name not in ADAPTER_REGISTRY:
        raise KeyError(f"Unknown adapter: {name}. Available: {list(ADAPTER_REGISTRY.keys())}")
    return ADAPTER_REGISTRY[name]()
