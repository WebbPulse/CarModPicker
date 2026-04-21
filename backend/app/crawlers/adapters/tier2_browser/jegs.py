"""
JEGS (jegs.com) crawler adapter.

Product URLs: ``https://www.jegs.com/i/<brand>/<mfr-prefix>/<mfr-sku>/<internal-id>/-1``.
Example: ``/i/JEGS/555/513001/10002/-1`` — brand "JEGS", manufacturer prefix
"555", manufacturer SKU "513001" (joined: part number ``555-513001``).

**Fetch blocker:** product pages are behind a Cloudflare *managed JS
challenge*; only ``/robots.txt`` and ``/sitemap_index.xml`` return 200. See
``site_problem_notes/jegs.md`` for the probe log. Plain ``requests`` cannot reach
product HTML; TLS impersonation won't help because the challenge requires
JS execution. Hence ``FETCHER_TIER = "browser"`` — the runner swaps in
FlareSolverr once ``FLARESOLVERR_URL`` is configured.

**Current scope:** parse-only. Pages arrive via the Chrome extension
(``POST /crawled-pages/scrape``) or the archive rescrape pipeline; both
route through ``adapter_name_for_product_url`` so registering ``jegs.com``
there gives captured pages a site-specific parser instead of ``generic``.
``discover_product_urls`` is a stub until Tier 2 is wired up; once it is,
JEGS's sitemap index (``/sitemap_index.xml``) points at gzipped child
sitemaps and uses the older ``schemas/sitemap/0.84`` namespace, so the
discovery code has to decompress gzip and do namespace-agnostic ``loc``
extraction (``.//{*}loc``).

URL-derived fallback: the manufacturer brand and manufacturer SKU are both
embedded in the product URL itself, so when the HTML lacks JSON-LD we can
still produce a usable payload from ``url`` alone. That matters here because
the Chrome extension sometimes captures a page before late-binding JSON is
injected by the theme.
"""

import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

JEGS_BASE = "https://www.jegs.com"

# /i/<brand>/<mfr-prefix>/<mfr-sku>/<internal>/-1 — brand + prefix + sku are
# the useful pieces. Groups 2 and 3 together form the manufacturer part number
# (e.g. prefix 555 + sku 513001 → "555-513001").
_JEGS_PRODUCT_URL_RE = re.compile(
    r"^/i/([^/]+)/([^/]+)/([^/]+)/[^/]+/-1/?$",
    re.IGNORECASE,
)


def _brand_and_sku_from_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Pull brand and manufacturer SKU out of the JEGS URL path. Returns
    ``(brand, part_number)`` — each may be ``None`` if the path doesn't match
    the canonical JEGS product shape.
    """
    try:
        path = urlparse(url).path
    except Exception:
        return None, None
    m = _JEGS_PRODUCT_URL_RE.match(path)
    if not m:
        return None, None
    raw_brand = m.group(1).strip()
    prefix = m.group(2).strip()
    sku = m.group(3).strip()
    brand = raw_brand if raw_brand else None
    part_number = f"{prefix}-{sku}" if prefix and sku else None
    return brand, normalize_part_number(part_number) if part_number else None


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs. Without a real-page fixture we don't
    know JEGS's theme selectors, so fall back to og:image + ``<img src>``.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u or u in seen:
            return
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = JEGS_BASE + u
        if not u.startswith("http"):
            return
        seen.add(u)
        urls.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img", src=True):
        if not isinstance(img, Tag) or len(urls) >= 12:
            break
        src = img.get("src")
        if isinstance(src, str) and src.strip():
            add(src.strip())

    return urls[:12]


class JegsAdapter(RetailerCrawlerAdapter):
    """
    JEGS adapter.

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``).
    Until then, this adapter is used only for HTML captured through the
    Chrome extension or replayed from the archive. ``discover_product_urls``
    is a no-op until Tier 2 is wired up and the gzipped / 0.84-namespaced
    sitemap is handled.
    """

    FETCHER_TIER = "browser"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Stub: live crawling requires FlareSolverr and gzip-aware sitemap
        reading for the ``/sitemap_index.xml`` tree. Safe empty iterator for
        now.
        """
        return iter(())

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a JEGS product page. JSON-LD ``Product`` first; fall back to OG
        meta + DOM heuristics; as a last resort, derive the manufacturer brand
        and part number from the URL path itself (which encodes both).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)
        url_brand, url_part_number = _brand_and_sku_from_url(url)

        # 1. JSON-LD Product.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images if dom_images else None)
                part_number = normalize_part_number(payload.part_number) if payload.part_number else url_part_number

                part_manufacturer = payload.part_manufacturer or url_brand
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_from_title(payload.name)
                if not part_manufacturer and payload.description:
                    part_manufacturer = part_manufacturer_from_description(
                        payload.description, product_name=payload.name
                    )
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_fallback_from_title(payload.name)

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls[:12] if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. DOM fallback: og:title → h1.
        name: Optional[str] = None
        og_title = soup.find("meta", property="og:title")
        content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
        if content_title and content_title.strip():
            name = content_title.strip()
        if not name:
            h1 = soup.find("h1")
            if isinstance(h1, Tag):
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    name = h1_text
        if not name or len(name) < 3:
            return None

        description: Optional[str] = None
        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag):
            d = meta_content(og_desc)
            if d and d.strip():
                description = normalize_description_text(d, max_len=2000)
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000)

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))
        if not part_number:
            part_number = url_part_number

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))
        if not part_manufacturer:
            part_manufacturer = url_brand

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
