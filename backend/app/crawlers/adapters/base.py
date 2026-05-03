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
from typing import Any, ClassVar, Dict, Iterator, List, Literal, Optional

from app.crawlers.base import ScrapedPayload
from app.crawlers.fetchers import Fetcher, get_fetcher

FetcherTier = Literal["http", "tls", "browser"]

logger = logging.getLogger(__name__)

#: The six universal field names produced by
#: ``app.crawlers.parsing.extract_universal_fields`` (extended in M004/S06 T03
#: with ``manufacturer_part_number``). Used to validate ``suppress_universal``
#: entries at class-definition time so a typo in an adapter ("weight" vs
#: "weight_grams") fails loudly rather than silently failing to suppress at
#: runtime.
UNIVERSAL_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "weight_grams",
        "material",
        "finish",
        "warranty_days",
        "fitment_notes",
        "manufacturer_part_number",
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

        # Validate MANUFACTURER_SELECTORS shape (S03 T03). A typo'd selector
        # or a wrong-shaped value would silently fail to override at runtime;
        # failing loudly at class-definition time keeps the override honest.
        # Subclasses that don't override the default (an empty dict) skip this
        # validation entirely.
        selectors = getattr(cls, "MANUFACTURER_SELECTORS", {})
        if selectors:
            if not isinstance(selectors, dict):
                raise TypeError(
                    f"{cls.__module__}.{cls.__qualname__} declares MANUFACTURER_SELECTORS "
                    f"that is not a dict: {selectors!r}"
                )
            for sel_key, sel_val in selectors.items():
                if not isinstance(sel_key, str) or not sel_key.strip():
                    raise TypeError(
                        f"{cls.__module__}.{cls.__qualname__} declares MANUFACTURER_SELECTORS "
                        f"key {sel_key!r}; each key must be a non-empty CSS selector string."
                    )
                if isinstance(sel_val, str):
                    if not sel_val.strip():
                        raise TypeError(
                            f"{cls.__module__}.{cls.__qualname__} declares MANUFACTURER_SELECTORS "
                            f"empty-string value for key {sel_key!r}; canonical strings must be non-empty."
                        )
                elif isinstance(sel_val, tuple):
                    if not sel_val:
                        raise TypeError(
                            f"{cls.__module__}.{cls.__qualname__} declares MANUFACTURER_SELECTORS "
                            f"empty tuple for key {sel_key!r}; tuple values must contain at least "
                            f"a canonical string at index 0."
                        )
                    for idx, entry in enumerate(sel_val):
                        if not isinstance(entry, str) or not entry.strip():
                            raise TypeError(
                                f"{cls.__module__}.{cls.__qualname__} declares MANUFACTURER_SELECTORS "
                                f"value tuple[{idx}]={entry!r} for key {sel_key!r}; each tuple entry "
                                f"must be a non-empty string."
                            )
                else:
                    raise TypeError(
                        f"{cls.__module__}.{cls.__qualname__} declares MANUFACTURER_SELECTORS "
                        f"value for key {sel_key!r} of type {type(sel_val).__name__}; "
                        f"must be a non-empty string or a tuple of non-empty strings."
                    )

        # Validate CAR_FITMENT_SELECTORS shape (S04 T04). Mirrors the
        # MANUFACTURER_SELECTORS validator above — same dict-of-CSS-selector
        # shape so an adapter declaring per-retailer fitment selectors fails
        # loudly at import on typos rather than silently dropping car
        # inferences at runtime. Subclasses that don't override the default
        # (an empty dict) skip this validation entirely.
        car_selectors = getattr(cls, "CAR_FITMENT_SELECTORS", {})
        if car_selectors:
            if not isinstance(car_selectors, dict):
                raise TypeError(
                    f"{cls.__module__}.{cls.__qualname__} declares CAR_FITMENT_SELECTORS "
                    f"that is not a dict: {car_selectors!r}"
                )
            for sel_key, sel_val in car_selectors.items():
                if not isinstance(sel_key, str) or not sel_key.strip():
                    raise TypeError(
                        f"{cls.__module__}.{cls.__qualname__} declares CAR_FITMENT_SELECTORS "
                        f"key {sel_key!r}; each key must be a non-empty CSS selector string."
                    )
                if isinstance(sel_val, str):
                    if not sel_val.strip():
                        raise TypeError(
                            f"{cls.__module__}.{cls.__qualname__} declares CAR_FITMENT_SELECTORS "
                            f"empty-string value for key {sel_key!r}; canonical strings must be non-empty."
                        )
                elif isinstance(sel_val, tuple):
                    if not sel_val:
                        raise TypeError(
                            f"{cls.__module__}.{cls.__qualname__} declares CAR_FITMENT_SELECTORS "
                            f"empty tuple for key {sel_key!r}; tuple values must contain at least one entry."
                        )
                    for idx, entry in enumerate(sel_val):
                        if not isinstance(entry, str) or not entry.strip():
                            raise TypeError(
                                f"{cls.__module__}.{cls.__qualname__} declares CAR_FITMENT_SELECTORS "
                                f"value tuple[{idx}]={entry!r} for key {sel_key!r}; each tuple entry "
                                f"must be a non-empty string."
                            )
                else:
                    raise TypeError(
                        f"{cls.__module__}.{cls.__qualname__} declares CAR_FITMENT_SELECTORS "
                        f"value for key {sel_key!r} of type {type(sel_val).__name__}; "
                        f"must be a non-empty string or a tuple of non-empty strings."
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
    #: Per-retailer CSS-selector overrides consulted by
    #: ``app.crawlers.parsing.part_manufacturer_universal`` AHEAD of the
    #: JSON-LD/microdata/OpenGraph layers (S03 T03). Keys are CSS selectors
    #: (e.g. ``'.product-brand'``, ``'meta[name=brand]'``). Values are either:
    #:
    #:   * a canonical-string mapping (e.g. ``'CSF'``) — the resolved selector
    #:     value is checked against the shared
    #:     ``parsing._BRAND_REJECT_TOKENS | parsing._CAR_MAKES`` reject set;
    #:     reject matches coerce to the canonical string, non-rejects pass
    #:     through unchanged.
    #:   * a tuple ``('CSF', 'wheels', 'exhaust')`` — first entry is the
    #:     canonical, remaining entries are *additional* reject tokens
    #:     supplementing the shared set.
    #:
    #: Validated at ``__init_subclass__`` time: must be a dict; each key must
    #: be a non-empty string; each value must be either a non-empty string OR
    #: a tuple of non-empty strings of length ≥ 1. Typos / wrong types raise
    #: ``TypeError`` at class-definition time, mirroring the existing
    #: ``category_targets`` / ``suppress_universal`` validators.
    MANUFACTURER_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {}
    #: Per-retailer CSS-selector overrides for car-fitment markup (S04 T04).
    #: Reserved declarative slot mirroring ``MANUFACTURER_SELECTORS`` — keys are
    #: CSS selectors targeting fitment regions (e.g. JSON-LD ``Product.isCompatibleWith``,
    #: a ``.product-fitment`` block, microdata ``vehicleConfiguration``). Values
    #: follow the same canonical-string-or-tuple shape so future selector-driven
    #: parsers can share the same validation contract. Default empty — concrete
    #: parsing helpers consult ``infer_car_for_part`` today; selectors here are
    #: a forward-compat slot adapters MAY use to drive that hook's implementation.
    #: Validated at ``__init_subclass__`` time identically to
    #: ``MANUFACTURER_SELECTORS``.
    CAR_FITMENT_SELECTORS: ClassVar[dict[str, str | tuple[str, ...]]] = {}

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

    def extract_variants(
        self,
        html: str,
        url: str,
        base_payload: ScrapedPayload,
    ) -> List[ScrapedPayload]:
        """Yield additional ScrapedPayloads when one product page sells distinct SKUs.

        Default returns ``[]`` — most pages are one part. Override on retailers
        whose product pages bundle multiple priced variants (Wix retailers like
        A90 Shop expose ``+$NN`` deltas on dropdown selections; Shopify pages
        like AWE-Tuning expose multi-axis variant arrays). Each returned
        payload becomes its own Part row, so the contract is:

          * ``product_url`` must be UNIQUE per variant (typically
            ``<base_url>?variant=<slug>``). The ingest layer dedupes on
            ``part_listings.product_url``; reusing the base URL would refresh
            the canonical row in place and overwrite earlier variants.
          * ``part_number`` should be derived (``<base_pn>-<variant-slug>``)
            when the page does not expose per-variant SKUs.
          * ``price_cents`` should be the *resolved* variant price, not a delta.
          * Other fields default to the base payload's values; the adapter
            only needs to override what changes per variant.

        The runner ingests each returned payload with the same
        ``ingest_payload`` call used for ``base_payload``, including
        ``apply_universal_extraction`` so universal fields appear on every
        variant. Variant ingest failures are logged but do not abort the
        page — the base part still lands.

        Returning an empty list is the no-variants signal and is the default.
        """
        return []

    def infer_manufacturer_for_part(self, parsed: ScrapedPayload) -> Optional[str]:
        """Adapter-specific manufacturer inference hook (S03 T03).

        Default returns ``None``. Subclasses MAY override to consult
        ``parsed.name`` / ``parsed.description`` / ``parsed.specifications``
        for retailer-specific shape that doesn't fit a CSS selector
        (``MANUFACTURER_SELECTORS``).

        The default lives on the base so callers can invoke it
        unconditionally. Reserved slot — ``part_manufacturer_universal`` does
        NOT call this hook in S03 because no current caller (the harness
        ``_predict_manufacturer`` and any future ingest call site) passes a
        parsed ``ScrapedPayload`` object today. Wiring is deferred to S07's
        backfill, which has parsed payloads in hand.
        """
        return None

    def infer_category_for_part(self, parsed: ScrapedPayload) -> Optional[str]:
        """Adapter-specific category override hook.

        Default returns ``None`` (universal keyword-scoring pipeline runs).
        Subclasses MAY override to return one of the active category slugs
        (e.g. ``"wheels"``, ``"exhaust"``) when retailer-specific signals
        outside the part name/description make the category obvious — for
        example, Wheels Boutique URLs under ``/wheels/`` are wheels regardless
        of whether the product title contains the literal word ``"wheel"``.

        The slug must match an active row in the ``categories`` table; an
        unknown / inactive slug falls through to the universal pipeline so a
        typo can't drop a part into the default category. Returning ``None``
        (or any non-string) hands control back to the keyword scorer.

        Like ``infer_car_for_part``, this hook is load-bearing:
        ``app.crawlers.base.ingest_payload`` calls it ahead of
        ``infer_category`` with adapter-wins semantics.
        """
        return None

    def infer_car_for_part(
        self, parsed: ScrapedPayload
    ) -> Optional[list[tuple[str, str, str]]]:
        """Adapter-specific car-inference hook (S04 T04). Default returns ``None``.

        Subclasses MAY override to return a list of
        ``(car_make_name, car_model_name, generation_name)`` triples extracted
        from retailer-specific fitment markup — JSON-LD
        ``Product.isCompatibleWith``, microdata ``vehicleConfiguration``, the
        ``CAR_FITMENT_SELECTORS`` keys, etc. The triples flow through
        ``app.core.car_inference.resolve_car_triples_to_ids`` at the ingest
        call site, so adapters stay DB-free; only the ingest layer touches the
        session.

        Unlike ``infer_manufacturer_for_part`` (MEM224 — declared but NOT
        called in S03 because no current caller passes a ``ScrapedPayload``),
        this hook IS load-bearing: ``app.crawlers.base.ingest_payload`` calls
        it ahead of the universal ``infer_car_generations`` pipeline with
        adapter-wins semantics. Returning ``None`` (or an empty list) hands
        control back to the universal pipeline.
        """
        return None

    def apply_universal_extraction(self, html: str, payload: Optional[ScrapedPayload]) -> Optional[ScrapedPayload]:
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
        from app.crawlers.runner import classify_fetch_error, http_status_from_exception

        try:
            # D-18: 5s timeout — robots.txt is expected to return fast.
            self.fetcher.fetch(probe_url, timeout=5)
        except FetcherError as e:
            status = http_status_from_exception(e)
            if status is not None and 400 <= status < 500:
                return HealthResult(healthy=False, reason="http_4xx", status_code=status)
            if status is not None and 500 <= status < 600:
                return HealthResult(healthy=False, reason="http_5xx", status_code=status)
            bucket = classify_fetch_error(e, status)
            return HealthResult(healthy=False, reason=bucket or "connection", status_code=status)
        except Exception as e:
            # Non-FetcherError (e.g. requests.exceptions.Timeout raised directly
            # by an HttpFetcher that didn't wrap, or a connection reset).
            status = http_status_from_exception(e)
            if status is not None and 400 <= status < 500:
                return HealthResult(healthy=False, reason="http_4xx", status_code=status)
            if status is not None and 500 <= status < 600:
                return HealthResult(healthy=False, reason="http_5xx", status_code=status)
            bucket = classify_fetch_error(e, status)
            return HealthResult(healthy=False, reason=bucket or "connection", status_code=status)

        # Fetch returned without raising → response was 2xx.
        return HealthResult(healthy=True, reason="ok", status_code=200)
