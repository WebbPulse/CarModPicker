"""
Base class for retailer crawler adapters.

Adapters implement URL discovery and page parsing; the shared runner handles
fetch and ingest.

Each adapter declares a ``FETCHER_TIER`` — ``"http"``, ``"tls"``, or
``"browser"`` — that controls which fetcher the runner uses for product page
fetches. Adapters that need the upgraded fetcher for sitemap/discovery calls
too should call ``self.fetcher.fetch(...)`` from ``discover_product_urls()``
rather than the module-level ``fetch_page``. See ``crawlers/fetchers.py`` and
``crawlers/README.md`` for the tier model.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Iterator, Literal, Optional

from app.crawlers.base import ScrapedPayload
from app.crawlers.fetchers import Fetcher, get_fetcher

FetcherTier = Literal["http", "tls", "browser"]

logger = logging.getLogger(__name__)

#: The five universal field names produced by
#: ``app.crawlers.parsing.extract_universal_fields``. Used to validate
#: ``suppress_universal`` entries at class-definition time so a typo in an
#: adapter ("weight" vs "weight_grams") fails loudly rather than silently
#: failing to suppress at runtime.
UNIVERSAL_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "weight_grams",
        "material",
        "finish",
        "warranty_days",
        "fitment_notes",
    }
)


@dataclass(frozen=True)
class HealthResult:
    """Result of a pre-crawl adapter health probe (CRAWL-06, D-18/D-19)."""

    healthy: bool
    reason: str  # "ok" | "http_4xx" | "http_5xx" | "timeout" | "connection" | "skipped_by_config"
    status_code: int | None


class RetailerCrawlerAdapter(ABC):
    """
    Per-retailer adapter: discover product URLs and parse a product page into ScrapedPayload.

    Subclass and implement discover_product_urls() and parse_product_page(html, url).
    Override ``FETCHER_TIER`` on the subclass when plain requests isn't enough
    (Cloudflare TLS-fingerprint block → ``"tls"``; managed JS challenge → ``"browser"``).
    """

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # IS_FALLBACK=True marks GenericHtmlParser (excluded from ADAPTER_REGISTRY per D-03).
        if getattr(cls, "IS_FALLBACK", False):
            return
        # Still-abstract intermediate bases (e.g., Shopify/WooCommerce mixins) have no slug.
        if getattr(cls, "__abstractmethods__", None):
            return
        name = getattr(cls, "ADAPTER_NAME", "")
        if not isinstance(name, str) or not name.strip():
            raise TypeError(
                f"{cls.__module__}.{cls.__qualname__} must declare "
                f"ADAPTER_NAME: ClassVar[str] = '<slug>' (non-empty). See D-02."
            )
        targets = getattr(cls, "category_targets", [])
        if targets:
            # Lazy import: app.crawlers.specs imports CategorySpec subclasses,
            # not adapter machinery, so the dependency direction stays one-way.
            from app.crawlers.specs import default_registry

            for entry in targets:
                if not isinstance(entry, str) or not entry.strip():
                    raise TypeError(
                        f"{cls.__module__}.{cls.__qualname__} declares invalid "
                        f"category_targets entry {entry!r}; each entry must be a non-empty string."
                    )
                if default_registry.resolve(entry) is None:
                    raise TypeError(
                        f"{cls.__module__}.{cls.__qualname__} declares unknown "
                        f"category_targets entry {entry!r}; not registered in default_registry"
                    )

        # Validate suppress_universal entries against the known universal
        # field names. Typos here (e.g. 'weight' instead of 'weight_grams')
        # would silently fail to suppress at runtime; failing loudly at
        # class-definition time keeps the per-adapter override honest.
        suppress = getattr(cls, "suppress_universal", [])
        if suppress:
            if not isinstance(suppress, (list, tuple)):
                raise TypeError(
                    f"{cls.__module__}.{cls.__qualname__} declares suppress_universal "
                    f"that is not a list/tuple: {suppress!r}"
                )
            for entry in suppress:
                if not isinstance(entry, str) or entry not in UNIVERSAL_FIELD_NAMES:
                    raise TypeError(
                        f"{cls.__module__}.{cls.__qualname__} declares unknown "
                        f"suppress_universal entry {entry!r}; must be one of "
                        f"{sorted(UNIVERSAL_FIELD_NAMES)!r}."
                    )

    #: Globally-unique slug for this adapter. Enforced non-empty by __init_subclass__.
    #: Must equal the existing ADAPTER_REGISTRY key verbatim (no derivation from class name per D-02).
    ADAPTER_NAME: ClassVar[str] = ""
    #: When True, this adapter is the URL-host fallback and is excluded from ADAPTER_REGISTRY (per D-03).
    IS_FALLBACK: ClassVar[bool] = False
    #: URL to probe in check_health(). `None` = opt out (per DISC-04 Option A — default opt-in).
    HEALTH_PROBE_URL: ClassVar[str | None] = None
    #: Which fetcher tier to use. Default is plain-HTTP; override on subclasses
    #: that need TLS impersonation or a headless browser.
    FETCHER_TIER: ClassVar[FetcherTier] = "http"
    #: Category-spec slugs (per app.crawlers.specs.default_registry) this adapter targets.
    #: Default empty — adapters opt in by overriding. Validated at class-definition time
    #: by __init_subclass__: each entry must resolve via default_registry.resolve(), so
    #: typos in the S03 retrofit fail loudly at import rather than silently dropping specs.
    category_targets: ClassVar[list[str]] = []
    #: Universal-extraction field names this adapter wants to opt out of. Default
    #: empty — every adapter gets all five universal fields auto-extracted by
    #: ``apply_universal_extraction``. Override on subclasses that hand-roll a
    #: more accurate value for one or more universal fields, e.g.
    #: ``suppress_universal: ClassVar[list[str]] = ['weight_grams']``. Each
    #: entry must be one of the five names in ``UNIVERSAL_FIELD_NAMES``;
    #: __init_subclass__ raises TypeError on unknown names so typos are caught
    #: at import.
    suppress_universal: ClassVar[list[str]] = []

    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        # Defer default-fetcher construction until first access. Archive rescrape
        # instantiates adapters only to call parse_product_page() — it never
        # touches self.fetcher — so it shouldn't have to satisfy discovery-time
        # config (e.g. FLARESOLVERR_URL) for browser-tier adapters.
        self._fetcher: Optional[Fetcher] = fetcher

    @property
    def fetcher(self) -> Fetcher:
        if self._fetcher is None:
            self._fetcher = get_fetcher(self.FETCHER_TIER)
        return self._fetcher

    @abstractmethod
    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product page URLs for this retailer (sitemap, category, search, or fixed list).
        """
        ...

    @abstractmethod
    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a product page HTML (and optional url for context) into ScrapedPayload.
        Return None if the page is not a product page or parsing fails.
        """
        ...

    def apply_universal_extraction(
        self, html: str, payload: Optional[ScrapedPayload]
    ) -> Optional[ScrapedPayload]:
        """
        Run the five universal extractors over ``html`` and merge the results
        into ``payload.specifications``.

        Adapter values win on conflict — for any field key the adapter already
        set in ``payload.specifications``, this hook leaves the existing entry
        alone. Fields listed in ``self.suppress_universal`` are skipped
        entirely. The hook is intended to be invoked by call sites that
        already received a non-None payload from ``parse_product_page``;
        ``payload is None`` short-circuits to a no-op so callers can drop the
        None-check on the failure branch.

        Returns the (possibly mutated) payload. Always returns the same
        payload instance — never replaces it — so call-site assignment
        ``payload = adapter.apply_universal_extraction(html, payload)`` is
        safe to write reflexively.
        """
        if payload is None:
            return payload

        # Lazy import: parsing.py imports ScrapedPayload from crawlers.base, so
        # importing extract_universal_fields here keeps the import direction
        # one-way (adapters/base imports parsing only at call time).
        from app.crawlers.parsing import extract_universal_fields

        extracted = extract_universal_fields(html)
        if not extracted:
            return payload

        suppressed = set(type(self).suppress_universal or [])
        adapter_name = getattr(type(self), "ADAPTER_NAME", "") or "unknown"

        existing: Dict[str, Any] = dict(payload.specifications or {})
        merged_added = False
        for field, (value, confidence) in extracted.items():
            if field in suppressed:
                continue
            confidence_field = f"{field}_confidence"
            # Adapter wins: only fill keys the adapter didn't already set.
            wrote_value = False
            if field not in existing:
                existing[field] = value
                wrote_value = True
            if confidence_field not in existing:
                existing[confidence_field] = confidence
            if wrote_value:
                merged_added = True
                logger.debug(
                    "universal_extraction: adapter=%s field=%s confidence=%s",
                    adapter_name,
                    field,
                    confidence,
                )

        if merged_added or (existing and payload.specifications is None):
            payload.specifications = existing or None
        return payload

    def check_health(self) -> HealthResult:
        """Pre-crawl health probe (CRAWL-06 / D-19).

        When ``HEALTH_PROBE_URL`` is set, fetch it through this adapter's own
        fetcher (tier-specific transport — http/tls/browser) with a 5-second
        timeout (D-18). Classify the outcome into a ``HealthResult``:

          - 2xx (fetch returned, no exception) → healthy=True, reason="ok"
          - 4xx → healthy=False, reason="http_4xx"
          - 5xx → healthy=False, reason="http_5xx"
          - Timeout → healthy=False, reason="timeout"
          - Other (connection/fetcher/etc) → healthy=False, reason=<bucket>

        When ``HEALTH_PROBE_URL=None`` (the default per DISC-04 Option A),
        returns healthy=True with reason="skipped_by_config" — the adapter
        opts out of probing and the runner proceeds directly to the URL loop.
        """
        probe_url = type(self).HEALTH_PROBE_URL
        if probe_url is None:
            return HealthResult(healthy=True, reason="skipped_by_config", status_code=None)

        # Helpers live in runner.py (transport-layer classification). Imported
        # lazily to avoid a circular import (runner imports ADAPTER_REGISTRY
        # from this package).
        from app.crawlers.fetchers import FetcherError
        from app.crawlers.runner import _classify_fetch_error, _http_status_from_exception

        try:
            # D-18: 5s timeout — robots.txt is expected to return fast.
            self.fetcher.fetch(probe_url, timeout=5)
        except FetcherError as e:
            status = _http_status_from_exception(e)
            if status is not None and 400 <= status < 500:
                return HealthResult(healthy=False, reason="http_4xx", status_code=status)
            if status is not None and 500 <= status < 600:
                return HealthResult(healthy=False, reason="http_5xx", status_code=status)
            bucket = _classify_fetch_error(e, status)
            return HealthResult(healthy=False, reason=bucket or "connection", status_code=status)
        except Exception as e:
            # Non-FetcherError (e.g. requests.exceptions.Timeout raised directly
            # by an HttpFetcher that didn't wrap, or a connection reset).
            status = _http_status_from_exception(e)
            if status is not None and 400 <= status < 500:
                return HealthResult(healthy=False, reason="http_4xx", status_code=status)
            if status is not None and 500 <= status < 600:
                return HealthResult(healthy=False, reason="http_5xx", status_code=status)
            bucket = _classify_fetch_error(e, status)
            return HealthResult(healthy=False, reason=bucket or "connection", status_code=status)

        # Fetch returned without raising → response was 2xx.
        return HealthResult(healthy=True, reason="ok", status_code=200)
