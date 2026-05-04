"""
ECS Tuning (ecstuning.com) crawler adapter.

Product URLs: ``https://www.ecstuning.com/b-<brand-slug>-parts/<product-slug>/<mfr-sku>/``.
Example: ``/b-genuine-bmw-parts/thermostat-housing-assembly/11538635689/`` —
brand slug ``genuine-bmw``, manufacturer SKU ``11538635689`` (BMW OEM thermostat
housing). ECS also uses an internal ``/es<digits>/`` catalog-id form for some
listings; we treat those as product URLs for parse-time routing but do not try
to derive a part number from the catalog id (it's an ECS internal, not an MPN).

**Fetch blocker:** ECS Tuning sits behind Cloudflare's Bot Management layer —
the backlog note (``adapters/RETAILER_BACKLOG.md``) pegs it at "Tier-1 TLS
minimum, possibly Tier-2 browser," and historically ECS has served the
``Just a moment…`` managed challenge to AWS-egress clients. We pick the
conservative tier here because ECS is the highest-value Euro retailer and we
cannot afford false-negative fetches; if operator testing shows plain TLS
impersonation is enough, demote to ``tier1_tls`` later. See
``site_problem_notes/ecstuning.md`` for the probe log and follow-up work.

**Current scope:** parse-only. Pages arrive via the Chrome extension
(``POST /crawled-pages/scrape``) or the archive rescrape pipeline; both route
through ``adapter_name_for_product_url`` so registering ``ecstuning.com``
there gives captured pages a site-specific parser instead of ``generic``.
``discover_product_urls`` is a stub until Tier 2 is wired up — when it is,
ECS's sitemap index exists but the fitment-selector URLs are deep; discovery
should walk category sitemaps, not the year/make/model tree.

URL-derived fallback: the ``b-<brand>-parts`` segment is the part manufacturer
and the last path segment on a brand-parts URL is the manufacturer SKU, so
even when the HTML lacks JSON-LD we can still produce a usable payload from
the URL alone (matches the JEGS adapter's approach). This is load-bearing
because the extension occasionally captures pages before late-binding JSON-LD
is injected by the theme.

Parsing strategy mirrors ``fcpeuro.py``: JSON-LD ``Product`` first, then OG /
meta fallback, then DOM heuristics. Brand normalization strips the common
``Genuine``/``OEM`` prefix tokens in the URL so the stored manufacturer matches
the canonical make (``genuine-bmw`` → ``BMW``, ``oem-audi`` → ``Audi``) rather
than a retailer-specific tag.
"""

import re
from typing import ClassVar, Iterator, List, Optional
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

ECSTUNING_BASE = "https://www.ecstuning.com"

# Canonical brand-parts product URL:
#   /b-<brand-slug>-parts/<product-slug>/<mfr-sku>/
# brand-slug may itself contain dashes ("genuine-bmw", "oem-audi", "assembled-by-ecs").
# ECS also has an ``/es<digits>/`` catalog-id form; no brand/sku is derivable
# from that path, so the URL fallback just yields ``(None, None)`` for it and we
# fall through to DOM/JSON-LD parsing.
_BRAND_PARTS_URL_RE = re.compile(
    r"^/b-(?P<brand>[a-z0-9][a-z0-9\-]*?)-parts/(?P<slug>[^/]+)/(?P<sku>[^/]+)/?$",
    re.IGNORECASE,
)

# Prefix tokens in the URL brand slug that are retailer-qualifier noise rather
# than the actual manufacturer (``genuine-bmw`` → manufacturer is "BMW", not
# "Genuine BMW"; ``oem-audi`` → "Audi"). Order-sensitive: we strip one match
# from the leading tokens.
_BRAND_PREFIX_STRIP = frozenset({"genuine", "oem", "oes", "assembled", "original"})


def _brand_and_sku_from_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Pull manufacturer brand and manufacturer SKU out of an ECS product URL.
    Returns ``(brand, part_number)`` — each may be ``None`` if the path doesn't
    match the canonical brand-parts shape (e.g. ``/es1234/`` catalog-id URLs).

    Brand is title-cased and has any leading ``genuine``/``oem``/``oes``/
    ``assembled``/``original`` token stripped so ``genuine-bmw`` surfaces as
    ``BMW`` — the actual manufacturer on the shelf — rather than the
    retailer-qualifier form.
    """
    try:
        path = urlparse(url).path
    except Exception:
        return None, None
    m = _BRAND_PARTS_URL_RE.match(path)
    if not m:
        return None, None

    brand_slug = m.group("brand").lower()
    tokens = [t for t in brand_slug.split("-") if t]
    if tokens and tokens[0] in _BRAND_PREFIX_STRIP:
        tokens = tokens[1:]
    if not tokens:
        return None, normalize_part_number(m.group("sku"))
    # Preserve caps for short make codes (BMW, VW, MINI); title-case the rest.
    brand = " ".join(t.upper() if len(t) <= 3 else t.capitalize() for t in tokens)

    sku_raw = m.group("sku").strip()
    part_number = normalize_part_number(sku_raw) if sku_raw else None
    return brand, part_number


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs. Without a confirmed-theme fixture we
    don't target ECS-specific selectors yet; og:image first, then any
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
            u = ECSTUNING_BASE + u
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


class ECSTuningAdapter(RetailerCrawlerAdapter):
    """
    ECS Tuning adapter.

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``).
    Until then, this adapter is used only for HTML captured through the
    Chrome extension or replayed from the archive. ``discover_product_urls``
    is a no-op; once Tier 2 is wired up, walk the category sitemaps (not the
    vehicle-fitment selector — those URLs are deep and the same product shows
    up under many fitment branches).
    """

    ADAPTER_NAME: ClassVar[str] = "ecstuning"
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
        Parse an ECS Tuning product page. JSON-LD ``Product`` first, then OG
        meta + DOM heuristics, then a URL-derived brand/SKU fallback for
        captures that missed the late-bound JSON-LD. Returns ``None`` when no
        name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)
        url_brand, url_part_number = _brand_and_sku_from_url(url)

        # 1. JSON-LD Product — authoritative when present.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images if dom_images else None)
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                if not part_number:
                    part_number = url_part_number

                # URL-derived brand beats the title heuristic because ECS
                # product slugs often lead with a category word ("Thermostat
                # Housing Assembly") that the heuristic picks up as a
                # manufacturer. JSON-LD brand still wins when present.
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
            sku_elem = soup.find(class_=re.compile(r"sku|part[-_ ]?number|mfg[-_ ]?number", re.I)) or soup.find(
                id=re.compile(r"sku|part[-_ ]?number|mfg[-_ ]?number", re.I)
            )
            if isinstance(sku_elem, Tag):
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))
        if not part_number:
            part_number = url_part_number

        # URL-derived brand beats the title heuristic here too — see the
        # JSON-LD path above for rationale.
        part_manufacturer = url_brand
        if not part_manufacturer:
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
