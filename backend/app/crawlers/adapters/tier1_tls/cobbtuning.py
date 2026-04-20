"""
Cobb Tuning (cobbtuning.com) crawler adapter — Tier 1 (TLS-impersonating fetcher).

Product URLs: ``https://www.cobbtuning.com/<slug>.html`` (Magento 2 url_key with
``.html`` suffix). Cobb is a Magento 2 storefront behind Cloudflare-style bot
protection: plain ``requests.get`` and ``curl`` with a full current-Chrome header
set both return 403 against every path except ``/robots.txt``, while real-browser
access from the same network loads fine. That profile matches Vivid Racing's
TLS/JA3 fingerprint block (see ``site_problem_notes/vividracing.md`` and
``cobbtuning.md``), so this adapter sets ``FETCHER_TIER = "tls"`` to route
discovery *and* product fetches through curl_cffi's Chrome impersonation.

Notes:

- Product URL pattern is just ``/<slug>.html`` — there is no product-id suffix
  that structurally distinguishes products from CMS / category pages. The
  sitemap is the source of truth for discovery; ``_is_product_url`` is a shape
  guard (reject query strings, reject CMS / account / checkout paths) rather
  than a positive product identifier. ``parse_product_page`` is the final
  filter: a page without JSON-LD Product *and* without a recoverable ``<h1>``
  title returns None.
- ``robots.txt`` bans ``/*?`` — any URL with a query string is off limits.
  ``canonicalize_url()`` strips known tracking params; ``_is_product_url``
  drops anything with a remaining query string on top of that.
- Magento 2's default sitemap lives at ``/sitemap.xml`` and is normally a
  sitemap index pointing at ``/sitemap-N-M.xml`` child urlsets. We walk the
  index via ``self.fetcher`` (not the plain-HTTP ``fetch_page``, which 403s
  on this origin same as product pages).
- Cobb's catalog is overwhelmingly their own hardware — AccessPort, SF
  intakes, Stage packages, NexGen exhausts. When JSON-LD brand is missing and
  no title heuristic fires, the adapter defaults ``part_manufacturer`` to
  ``"COBB Tuning"``; the title-first-word heuristic would otherwise pick up
  product words like "Accessport" or "Stage" and write garbage.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

COBBTUNING_BASE = "https://www.cobbtuning.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Default manufacturer when JSON-LD does not carry a brand. Cobb's catalog is
# overwhelmingly their own hardware (AccessPort, SF intakes, Stage packages,
# NexGen exhausts), so assigning "COBB Tuning" unconditionally on the
# fallback path is strictly better than the shared title-first-word heuristic,
# which would pick up product words like "Accessport" or "Stage" as a
# "manufacturer". Co-branded SKUs that *do* carry a JSON-LD brand (Mishimoto,
# IAG, etc.) go through the JSON-LD path and keep their own manufacturer.
_DEFAULT_MANUFACTURER = "COBB Tuning"

# Magento 2 product URLs end in ``.html`` and are at the site root. This is a
# shape guard only (category / CMS pages also end in .html); the sitemap
# urlset and JSON-LD presence are the real filter.
_PRODUCT_PATH_RE = re.compile(r"^/[a-z0-9][a-z0-9\-/]*\.html$", re.IGNORECASE)

# CMS / account / checkout / informational paths that sometimes show up in
# Magento 2 sitemaps. We drop them up-front so the runner never spends a fetch
# on /about-us.html or /shipping-returns.html.
_NON_PRODUCT_PATH_RE = re.compile(
    r"^/("
    r"customer|checkout|cart|wishlist|onestepcheckout|catalogsearch|review|"
    r"tag|blog|news|press|events|about|about-us|contact|contact-us|support|"
    r"warranty|dealer|dealers|shipping|returns|terms|privacy|cookie|sitemap|"
    r"rss|store|stores|help|faq|careers|media|legal|tuning-support|"
    r"accessport-support"
    r")(/|$|\.html)",
    re.IGNORECASE,
)


# Safe default so a fresh run exercises parsing against a known URL even when
# sitemap discovery comes back empty (e.g. if Cloudflare starts blocking the
# TLS fetcher too). Override via CRAWLER_COBBTUNING_START_URLS. The
# AccessPort V3 page is the flagship SKU and a natural smoke test.
DEFAULT_START_URLS = [
    "https://www.cobbtuning.com/accessport-v3.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a plausible Cobb Tuning product page URL."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.query:
        # robots.txt disallows /*? — any URL with a query string is off limits.
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "cobbtuning.com" or host.endswith(".cobbtuning.com")):
        return False
    path = parsed.path or ""
    if not _PRODUCT_PATH_RE.match(path):
        return False
    if _NON_PRODUCT_PATH_RE.match(path):
        return False
    return True


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_COBBTUNING_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_COBBTUNING_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product image URLs: og:image first, then <img> tags. Normalizes
    protocol-relative and site-root paths to absolute https URLs. Capped at 12.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        if not raw or len(urls) >= 12:
            return
        u = raw.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = COBBTUNING_BASE + u
        if not u.startswith("http"):
            return
        if u in seen:
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


class CobbTuningAdapter(RetailerCrawlerAdapter):
    """
    Cobb Tuning adapter.

    Fetcher tier: ``tls`` — Cobb returns 403 to plain requests and to curl with
    a full current-Chrome header set, while real browsers from the same network
    load fine. curl_cffi's Chrome TLS impersonation is the first thing to try;
    if Cloudflare also starts issuing a JS challenge, the adapter needs to be
    promoted to the ``browser`` (FlareSolverr) tier.

    Discovery: ``CRAWLER_COBBTUNING_START_URLS`` env var wins. Otherwise we
    walk ``/sitemap.xml`` via ``self.fetcher`` (so requests go through the TLS
    fetcher, not plain ``fetch_page`` which Cloudflare 403s here), collect any
    product-shaped URLs, and fall back to ``DEFAULT_START_URLS`` if discovery
    comes back empty.

    Parsing: JSON-LD Product first (Magento 2 emits schema.org by default),
    then DOM/og fallback. Defaults ``part_manufacturer`` to ``COBB Tuning``
    when nothing else surfaces — most of the catalog is COBB-branded, and the
    title-first-word heuristic otherwise picks product words like
    "Accessport" or "Stage" as manufacturers.
    """

    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Env override (``CRAWLER_COBBTUNING_START_URLS``)
        wins; otherwise walks ``/sitemap.xml`` via the TLS fetcher. Falls back
        to ``DEFAULT_START_URLS`` when discovery fails or returns nothing.
        """
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in self._discover_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def _discover_via_sitemap(self) -> List[str]:
        """
        Fetch ``/sitemap.xml`` via the adapter's TLS fetcher and collect every
        product-shaped URL it points at. Walks sitemap indexes one level deep.
        Returns [] on any failure; the caller decides the fallback.

        Gzipped child sitemaps are skipped — the fetcher contract returns
        decoded text, and Magento 2 normally serves plain ``.xml`` urlsets.
        """
        seen: set[str] = set()
        product_urls: List[str] = []

        def parse_urlset_locs(xml_text: str) -> None:
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                return
            for loc in _loc_elements(root):
                if not loc.text:
                    continue
                u = loc.text.strip()
                if not _is_product_url(u):
                    continue
                base = u.split("?", 1)[0]
                if base in seen:
                    continue
                seen.add(base)
                product_urls.append(base)

        try:
            index_url = COBBTUNING_BASE + "/sitemap.xml"
            index_text = self.fetcher.fetch(index_url, timeout=15)
            root = ET.fromstring(index_text)
            tag = root.tag
            if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
                child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
                for i, child_url in enumerate(child_sitemap_urls):
                    if i > 0:
                        time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                    if child_url.endswith(".gz"):
                        continue
                    try:
                        child_text = self.fetcher.fetch(child_url, timeout=15)
                        parse_urlset_locs(child_text)
                    except Exception:
                        continue
            else:
                parse_urlset_locs(index_text)
        except Exception:
            return []

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Cobb Tuning product page. JSON-LD Product first (Magento 2
        emits it by default with name / brand / sku / offers), then a DOM /
        og fallback. Returns None when the URL is not product-shaped or when
        neither JSON-LD nor the DOM yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Magento 2 default SEO output).
        item = extract_json_ld_product(html)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                description = payload.description
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = payload.part_manufacturer or _DEFAULT_MANUFACTURER
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback.
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
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if isinstance(sku_elem, Tag):
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # No JSON-LD brand available. Skip the title-first-word heuristic
        # (which picks "Accessport" / "Stage" / "SF" as manufacturers on this
        # catalog) and use the COBB Tuning default directly.
        part_manufacturer = _DEFAULT_MANUFACTURER

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
