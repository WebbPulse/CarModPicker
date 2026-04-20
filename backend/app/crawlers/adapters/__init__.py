"""
Per-retailer crawler adapters.

Each adapter implements: discover_product_urls() and parse_product_page(html, url).
Register new adapters in ADAPTER_REGISTRY so the runner can run them by name.

``generic`` is always the last-resort fallback and should not be passed to the
crawler runner CLI (it has no discover_product_urls implementation).
"""

from typing import Optional
from urllib.parse import urlparse

from app.crawlers.adapters.base import RetailerCrawlerAdapter

# Last-resort fallback — no discovery; used by URL-host mapping below.
from app.crawlers.adapters.generic import GenericHtmlParser

# Tier 0 — plain HTTP (`HttpFetcher`)
from app.crawlers.adapters.tier0_http.a90shop import A90ShopAdapter
from app.crawlers.adapters.tier0_http.adro import AdroAdapter
from app.crawlers.adapters.tier0_http.amsperformance import AMSPerformanceAdapter
from app.crawlers.adapters.tier0_http.awetuning import AWETuningAdapter
from app.crawlers.adapters.tier0_http.bimmerworld import BimmerworldAdapter
from app.crawlers.adapters.tier0_http.evasivemotorsports import EvasiveMotorsportsAdapter
from app.crawlers.adapters.tier0_http.functionwerk import FunctionwerkAdapter
from app.crawlers.adapters.tier0_http.hondata import HondataAdapter
from app.crawlers.adapters.tier0_http.ie import IEAdapter
from app.crawlers.adapters.tier0_http.ind import INDAdapter
from app.crawlers.adapters.tier0_http.ktuner import KTunerAdapter
from app.crawlers.adapters.tier0_http.maperformance import MAPerformanceAdapter
from app.crawlers.adapters.tier0_http.motorsport034 import Motorsport034Adapter
from app.crawlers.adapters.tier0_http.studiorsr import StudioRSRAdapter
from app.crawlers.adapters.tier0_http.summitracing import SummitRacingAdapter
from app.crawlers.adapters.tier0_http.tickperformance import TickPerformanceAdapter
from app.crawlers.adapters.tier0_http.xph import XPHAdapter

# Tier 1 — TLS impersonation (`TlsFetcher`, `curl_cffi`)
from app.crawlers.adapters.tier1_tls.cobbtuning import CobbTuningAdapter
from app.crawlers.adapters.tier1_tls.enjukuracing import EnjukuRacingAdapter
from app.crawlers.adapters.tier1_tls.mackinindustries import MackinIndustriesAdapter
from app.crawlers.adapters.tier1_tls.texasspeed import TexasSpeedAdapter
from app.crawlers.adapters.tier1_tls.turnermotorsport import TurnerMotorsportAdapter
from app.crawlers.adapters.tier1_tls.vividracing import VividRacingAdapter
from app.crawlers.adapters.tier1_tls.z1motorsports import Z1MotorsportsAdapter

# Tier 2 — FlareSolverr browser (`FlareSolverrFetcher`)
from app.crawlers.adapters.tier2_browser.ecstuning import ECSTuningAdapter
from app.crawlers.adapters.tier2_browser.fcpeuro import FCPEuroAdapter
from app.crawlers.adapters.tier2_browser.jegs import JegsAdapter
from app.crawlers.adapters.tier2_browser.speedindustry import SpeedIndustryAdapter
from app.crawlers.adapters.tier2_browser.tirerack import TireRackAdapter
from app.crawlers.fetchers import Fetcher

ADAPTER_REGISTRY: dict[str, type[RetailerCrawlerAdapter]] = {
    # Tier 0 — plain HTTP
    "034motorsport": Motorsport034Adapter,
    "a90shop": A90ShopAdapter,
    "adro": AdroAdapter,
    "amsperformance": AMSPerformanceAdapter,
    "awetuning": AWETuningAdapter,
    "bimmerworld": BimmerworldAdapter,
    "evasivemotorsports": EvasiveMotorsportsAdapter,
    "functionwerk": FunctionwerkAdapter,
    "hondata": HondataAdapter,
    "ie": IEAdapter,
    "ind": INDAdapter,
    "ktuner": KTunerAdapter,
    "maperformance": MAPerformanceAdapter,
    "studiorsr": StudioRSRAdapter,
    "summitracing": SummitRacingAdapter,
    "tickperformance": TickPerformanceAdapter,
    "xph": XPHAdapter,
    # Tier 1 — TLS impersonation
    "cobbtuning": CobbTuningAdapter,
    "enjukuracing": EnjukuRacingAdapter,
    "mackinindustries": MackinIndustriesAdapter,
    "texasspeed": TexasSpeedAdapter,
    "turnermotorsport": TurnerMotorsportAdapter,
    "vividracing": VividRacingAdapter,
    "z1motorsports": Z1MotorsportsAdapter,
    # Tier 2 — FlareSolverr browser
    "ecstuning": ECSTuningAdapter,
    "fcpeuro": FCPEuroAdapter,
    "jegs": JegsAdapter,
    "speedindustry": SpeedIndustryAdapter,
    "tirerack": TireRackAdapter,
    # Fallback
    "generic": GenericHtmlParser,
}


def adapter_name_for_product_url(url: str) -> str:
    """
    Map a product page URL's host to a registered adapter name.

    Returns a site-specific adapter key when the host is a known retailer,
    otherwise returns ``"generic"`` so any URL can be parsed.

    Used by:
    - POST /crawled-pages/scrape  (live scrape from Chrome extension)
    - archive rescrape pipeline   (admin re-parse of stored HTML)
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "generic"
    if not host:
        return "generic"
    # Tier 0 — plain HTTP
    if host == "034motorsport.com" or host.endswith(".034motorsport.com"):
        return "034motorsport"
    if host.endswith("a90shop.com"):
        return "a90shop"
    if host == "adro.com" or host.endswith(".adro.com"):
        return "adro"
    if host == "amsperformance.com" or host.endswith(".amsperformance.com"):
        return "amsperformance"
    if host == "awe-tuning.com" or host.endswith(".awe-tuning.com"):
        return "awetuning"
    if host == "bimmerworld.com" or host.endswith(".bimmerworld.com"):
        return "bimmerworld"
    if host == "evasivemotorsports.com" or host.endswith(".evasivemotorsports.com"):
        return "evasivemotorsports"
    if host == "functionwerk.com" or host.endswith(".functionwerk.com"):
        return "functionwerk"
    if host == "hondata.com" or host.endswith(".hondata.com"):
        return "hondata"
    if host == "performancebyie.com" or host.endswith(".performancebyie.com"):
        return "ie"
    if host == "ind-distribution.com" or host.endswith(".ind-distribution.com"):
        return "ind"
    if host == "ktuner.com" or host.endswith(".ktuner.com"):
        return "ktuner"
    if host == "maperformance.com" or host.endswith(".maperformance.com"):
        return "maperformance"
    if host == "studiorsr.com" or host.endswith(".studiorsr.com"):
        return "studiorsr"
    if host == "summitracing.com" or host.endswith(".summitracing.com"):
        return "summitracing"
    if host == "tickperformance.com" or host.endswith(".tickperformance.com"):
        return "tickperformance"
    if host == "x-ph.com" or host.endswith(".x-ph.com"):
        return "xph"
    # Tier 1 — TLS impersonation
    if host == "cobbtuning.com" or host.endswith(".cobbtuning.com"):
        return "cobbtuning"
    if host == "enjukuracing.com" or host.endswith(".enjukuracing.com"):
        return "enjukuracing"
    if host == "mackin-ind.com" or host.endswith(".mackin-ind.com"):
        return "mackinindustries"
    if host == "mackinindustries.com" or host.endswith(".mackinindustries.com"):
        return "mackinindustries"
    if host == "texas-speed.com" or host.endswith(".texas-speed.com"):
        return "texasspeed"
    if host == "turnermotorsport.com" or host.endswith(".turnermotorsport.com"):
        return "turnermotorsport"
    if host == "vividracing.com" or host.endswith(".vividracing.com"):
        return "vividracing"
    if host == "z1motorsports.com" or host.endswith(".z1motorsports.com"):
        return "z1motorsports"
    # Tier 2 — FlareSolverr browser
    if host == "ecstuning.com" or host.endswith(".ecstuning.com"):
        return "ecstuning"
    if host == "fcpeuro.com" or host.endswith(".fcpeuro.com"):
        return "fcpeuro"
    if host == "jegs.com" or host.endswith(".jegs.com"):
        return "jegs"
    if host == "speedindustry.com" or host.endswith(".speedindustry.com"):
        return "speedindustry"
    if host == "tirerack.com" or host.endswith(".tirerack.com"):
        return "tirerack"
    return "generic"


def get_adapter(name: str, fetcher: Optional[Fetcher] = None) -> RetailerCrawlerAdapter:
    """
    Return an adapter instance by name. Raises KeyError if unknown.

    When ``fetcher`` is provided (runner path), the adapter uses it directly.
    When omitted (tests, one-off scripts), the adapter constructs a fetcher
    matching its declared ``FETCHER_TIER``.
    """
    if name not in ADAPTER_REGISTRY:
        raise KeyError(f"Unknown adapter: {name}. Available: {list(ADAPTER_REGISTRY.keys())}")
    return ADAPTER_REGISTRY[name](fetcher=fetcher) if fetcher is not None else ADAPTER_REGISTRY[name]()
