"""
American Muscle (americanmuscle.com) crawler adapter.

American Muscle is the largest Mustang aftermarket retailer by volume and the
only way to price a full S197/S550/S650 build end-to-end (suspension, exhaust,
cosmetics, drivetrain all live there). Cobb and AWE cover specific Mustang SKUs
but Mustang is a core enthusiast chassis still at effectively half a retailer
of real coverage until AM lands — see ``adapters/RETAILER_BACKLOG.md``.

Product URLs: ``https://www.americanmuscle.com/<product-slug>.html``.
Example: ``/mmd-slotted-hood-07-09.html``. The slug usually leads with a brand
token (``mmd``, ``borla``, ``steeda``, ``roush``, ``ford-performance``) and
often ends with a fitment year range. We do **not** regex brand/part-number
out of the URL — AM slugs are freeform marketing strings and the leading token
is only a brand hint when the brand happens to be one word; multi-word brands
(``ford-performance``, ``bbk-performance``) collide with product descriptors,
and AM's own SKU (``J110088`` style) is not in the URL at all. JSON-LD ``sku``
and ``brand.name`` are the trustworthy signals.

**Fetch blocker:** AM runs heavy anti-bot across the site. The retailer backlog
flags this as almost certainly Tier-2 browser; do not attempt Tier-0 first. We
have not yet run a probe matrix from AWS egress, but AM is high-value enough
that false-negative fetches would silently drop Mustang coverage — conservative
default is ``FETCHER_TIER = "browser"``. If later probing shows plain TLS
impersonation clears AM from our egress, demote to ``tier1_tls/``. See
``site_problem_notes/americanmuscle.md`` for follow-up work.

**Current scope:** parse-only. Pages arrive via the Chrome extension
(``POST /crawled-pages/scrape``) or the archive rescrape pipeline; both route
through ``adapter_name_for_product_url`` so registering ``americanmuscle.com``
there gives captured pages a site-specific parser instead of ``generic``.
``discover_product_urls`` is a stub until Tier 2 is wired up — when it is,
walk category / brand index pages (``/mustang-exhaust.html``,
``/mustang-suspension.html``) rather than the vehicle-year selector. The
year/model selector pushes users through a deep multi-step URL tree that
produces duplicate fitment branches for the same product; brand and category
indexes are flatter and enumerate cleanly.

Parsing strategy mirrors ``tirerack.py`` / ``jegs.py``: JSON-LD ``Product``
first, then OG / meta fallback, then DOM heuristics.
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

AMERICANMUSCLE_BASE = "https://www.americanmuscle.com"


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs. Without a post-challenge fixture we
    don't target AM-specific selectors yet; og:image first, then any
    absolute / protocol-relative / site-root ``<img src>``, capped at 12.
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
            u = AMERICANMUSCLE_BASE + u
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


class AmericanMuscleAdapter(RetailerCrawlerAdapter):
    """
    American Muscle adapter.

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``).
    Until then, this adapter is used only for HTML captured through the
    Chrome extension or replayed from the archive. ``discover_product_urls``
    is a no-op; once Tier 2 is wired up, walk category / brand index pages
    rather than the vehicle-year selector — same reasoning as the ECS fitment
    selector: the year/model tree produces duplicate fitment branches for
    the same product.
    """

    ADAPTER_NAME: ClassVar[str] = "americanmuscle"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "browser"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Stub: live crawling requires FlareSolverr plus category / brand index
        walking (see module docstring). The extension-capture path does not
        go through discovery, so an empty iterator is safe and keeps the
        runner from throwing when an operator kicks this adapter off before
        Tier 2 is deployed.
        """
        return iter(())

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an American Muscle product page. JSON-LD ``Product`` first;
        fall back to OG meta + DOM heuristics. Returns ``None`` when no name
        can be extracted (e.g. a category or search-results page captured by
        mistake).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product — authoritative when present.
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
