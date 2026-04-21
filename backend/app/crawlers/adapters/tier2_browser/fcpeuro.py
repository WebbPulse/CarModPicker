"""
FCP Euro (fcpeuro.com) crawler adapter.

Product URLs: ``https://www.fcpeuro.com/products/<handle>``. Handles are
human-readable slugs that frequently encode make + category + manufacturer
SKU (e.g. ``bmw-brake-kit-shw-34112284101ktfr33``). FCP Euro is a Shopify
storefront, so JSON-LD ``Product`` is the parse path of choice when we can
reach the real HTML.

**Fetch blocker:** every surface (product pages, ``.json`` variants,
``/sitemap.xml.gz``) is behind a Cloudflare *managed JS challenge* — the
``Just a moment...`` interstitial that requires JS execution and cookie
round-trips. See ``site_problem_notes/fcpeuro.md`` for the probe log. ``robots.txt``
is the only route that returns 200. Plain ``requests`` cannot reach product
HTML; TLS impersonation (Tier 1) also won't help because the challenge
requires JS execution.

Hence ``FETCHER_TIER = "browser"`` — the runner swaps in FlareSolverr
(Tier 2) once ``FLARESOLVERR_URL`` is configured.

**Current scope:** parse-only. Pages arrive via the Chrome extension
(``POST /crawled-pages/scrape``) or the archive rescrape pipeline; both
route through ``adapter_name_for_product_url`` so registering ``fcpeuro.com``
there gives captured pages a site-specific parser instead of ``generic``.
``discover_product_urls`` is a stub until Tier 2 is wired up.

Parsing strategy mirrors ``studiorsr.py`` (same underlying platform):
JSON-LD ``Product`` first, then OG / meta fallback, then DOM heuristics.
"""

from typing import Iterator, List, Optional

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

FCPEURO_BASE = "https://www.fcpeuro.com"


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs from the DOM. Shopify emits og:image
    plus an ``<img>``-dense gallery; we take og:image first, then any
    absolute/relative ``<img src>``, capped at 12.
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
            u = FCPEURO_BASE + u
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


class FCPEuroAdapter(RetailerCrawlerAdapter):
    """
    FCP Euro adapter.

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``).
    Until then, this adapter is used only for HTML captured through the
    Chrome extension or replayed from the archive. ``discover_product_urls``
    is a no-op; once Tier 2 is wired up, switch it to walk a published
    sitemap (FCP advertises ``sitemap.xml.gz`` — needs gzip handling that
    our existing adapters don't do, so expect some plumbing work there).
    """

    FETCHER_TIER = "browser"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Stub: live crawling requires FlareSolverr. The extension-capture path
        does not go through discovery, so returning an empty iterator is safe
        and keeps the runner from throwing when an operator accidentally kicks
        this adapter off before Tier 2 is deployed.
        """
        return iter(())

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an FCP Euro product page. JSON-LD ``Product`` first (Shopify
        exposes this reliably), then OG meta + DOM heuristics. Returns
        ``None`` when no name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Shopify's default schema).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images if dom_images else None)
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None

                part_manufacturer = payload.part_manufacturer
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

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
