"""
Crawler infrastructure for scraping part information from retailers at scale.

Run from backend directory:
    python -m app.crawlers

Requires env: CRAWLER_USER_ID, CRAWLER_DEFAULT_CATEGORY_ID (or CRAWLER_DEFAULT_CATEGORY_NAME).
"""

from app.crawlers.base import ScrapedPayload, fetch_page, ingest_payload
from app.crawlers.runner import run_crawler, run_crawlers

__all__ = [
    "ScrapedPayload",
    "fetch_page",
    "ingest_payload",
    "run_crawler",
    "run_crawlers",
]
