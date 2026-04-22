"""
Speed Industry (speedindustry.com) crawler adapter.

Product URLs: ``https://speedindustry.com/<slug>`` (slug at the root — no
``/products/`` / ``/parts/`` prefix). Platform is not publicly identifiable
(WooCommerce / BigCommerce / Shopify-with-alt-routing all fit the shape) and
we have not yet captured a real page body to confirm.

**Fetch blocker:** every surface (product pages, ``/robots.txt``, ``/sitemap.xml``,
``/wp-json/``) is behind a Cloudflare managed JS challenge. See
``site_problem_notes/speedindustry.md`` for the probe log. Plain ``requests`` cannot
reach product HTML; TLS impersonation (Tier 1) also won't suffice because the
challenge requires JS execution. Hence ``FETCHER_TIER = "browser"`` — the
runner swaps in FlareSolverr (Tier 2) once ``FLARESOLVERR_URL`` is configured.

**Current scope:** parse-only. ``parse_product_page`` handles HTML that
arrives via the Chrome extension (``POST /crawled-pages/scrape``) or the
archive rescrape pipeline — both route through ``adapter_name_for_product_url``
so registering ``speedindustry.com`` there already gives captured pages a
site-specific parser. ``discover_product_urls`` is a stub until FlareSolverr
is in place and we can verify a working sitemap endpoint.

Parsing strategy mirrors ``generic.py`` (the extension's captured-HTML
pipeline): JSON-LD ``Product`` first, then OG / meta fallback, then DOM
heuristics. We have not seen a real page yet, so the adapter intentionally
avoids retailer-specific selectors until a fixture confirms them.
"""

from typing import ClassVar, Iterator, List, Optional

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

SPEEDINDUSTRY_BASE = "https://speedindustry.com"


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs from the DOM (og:image first, then any
    same-origin / absolute ``<img src>``). Platform-agnostic: until we confirm
    the theme, we don't target specific selectors — we take og:image + <img>
    tags and let the ingest pipeline cap at 12.
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
            u = SPEEDINDUSTRY_BASE + u
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


class SpeedIndustryAdapter(RetailerCrawlerAdapter):
    """
    Speed Industry adapter.

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``).
    Until then, this adapter is used only for HTML captured through the
    Chrome extension or replayed from the archive. ``discover_product_urls``
    is a no-op; flesh it out once Tier 2 is wired up (try sitemap.xml first).
    """

    ADAPTER_NAME: ClassVar[str] = "speedindustry"
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
        Parse a Speed Industry product page. JSON-LD ``Product`` first (covers
        Shopify / WooCommerce / BigCommerce out of the box); fall back to OG
        meta + DOM heuristics when missing. Returns ``None`` when no name can
        be extracted — the ingest pipeline treats that as a parse failure.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (the path most modern e-com platforms expose).
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
