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
from app.crawlers.adapters.tier0_http.atpturbo import ATPTurboAdapter
from app.crawlers.adapters.tier0_http.awetuning import AWETuningAdapter
from app.crawlers.adapters.tier0_http.bcracing import BCRacingAdapter
from app.crawlers.adapters.tier0_http.bimmerworld import BimmerworldAdapter
from app.crawlers.adapters.tier0_http.briantooleyracing import BrianTooleyRacingAdapter
from app.crawlers.adapters.tier0_http.driveshaftshop import DriveshaftShopAdapter
from app.crawlers.adapters.tier0_http.essexparts import EssexPartsAdapter
from app.crawlers.adapters.tier0_http.evasivemotorsports import EvasiveMotorsportsAdapter
from app.crawlers.adapters.tier0_http.fifteen52 import Fifteen52Adapter
from app.crawlers.adapters.tier0_http.flyinmiata import FlyinMiataAdapter
from app.crawlers.adapters.tier0_http.fortuneauto import FortuneAutoAdapter
from app.crawlers.adapters.tier0_http.fullrace import FullRaceAdapter
from app.crawlers.adapters.tier0_http.functionwerk import FunctionwerkAdapter
from app.crawlers.adapters.tier0_http.girodisc import GirodiscAdapter
from app.crawlers.adapters.tier0_http.gmgracing import GMGRacingAdapter
from app.crawlers.adapters.tier0_http.greddy import GReddyAdapter
from app.crawlers.adapters.tier0_http.hasport import HasportAdapter
from app.crawlers.adapters.tier0_http.hksusa import HKSUSAAdapter
from app.crawlers.adapters.tier0_http.hondata import HondataAdapter
from app.crawlers.adapters.tier0_http.hrewheels import HREWheelsAdapter
from app.crawlers.adapters.tier0_http.iagperformance import IAGPerformanceAdapter
from app.crawlers.adapters.tier0_http.ie import IEAdapter
from app.crawlers.adapters.tier0_http.ind import INDAdapter
from app.crawlers.adapters.tier0_http.katech import KatechAdapter
from app.crawlers.adapters.tier0_http.ktuner import KTunerAdapter
from app.crawlers.adapters.tier0_http.lingenfelter import LingenfelterAdapter
from app.crawlers.adapters.tier0_http.maperformance import MAPerformanceAdapter
from app.crawlers.adapters.tier0_http.motorsport034 import Motorsport034Adapter
from app.crawlers.adapters.tier0_http.prlmotorsports import PRLMotorsportsAdapter
from app.crawlers.adapters.tier0_http.rallysportdirect import RallysportDirectAdapter
from app.crawlers.adapters.tier0_http.roadsportsupply import RoadSportSupplyAdapter
from app.crawlers.adapters.tier0_http.sheepeybuilt import SheepeyBuiltAdapter
from app.crawlers.adapters.tier0_http.steeda import SteedaAdapter
from app.crawlers.adapters.tier0_http.studiorsr import StudioRSRAdapter
from app.crawlers.adapters.tier0_http.subispeed import SubispeedAdapter
from app.crawlers.adapters.tier0_http.summitracing import SummitRacingAdapter
from app.crawlers.adapters.tier0_http.tickperformance import TickPerformanceAdapter
from app.crawlers.adapters.tier0_http.titan7 import Titan7Adapter
from app.crawlers.adapters.tier0_http.twentysevenwon import TwentySevenWonAdapter
from app.crawlers.adapters.tier0_http.wheelsboutique import WheelsBoutiqueAdapter
from app.crawlers.adapters.tier0_http.xph import XPHAdapter

# Tier 1 — TLS impersonation (`TlsFetcher`, `curl_cffi`)
from app.crawlers.adapters.tier1_tls.apr import APRAdapter
from app.crawlers.adapters.tier1_tls.cobbtuning import CobbTuningAdapter
from app.crawlers.adapters.tier1_tls.enjukuracing import EnjukuRacingAdapter
from app.crawlers.adapters.tier1_tls.forgeline import ForgelineAdapter
from app.crawlers.adapters.tier1_tls.goodwinracing import GoodWinRacingAdapter
from app.crawlers.adapters.tier1_tls.kwsuspensions import KWSuspensionsAdapter
from app.crawlers.adapters.tier1_tls.mackinindustries import MackinIndustriesAdapter
from app.crawlers.adapters.tier1_tls.suncoastparts import SuncoastPartsAdapter
from app.crawlers.adapters.tier1_tls.texasspeed import TexasSpeedAdapter
from app.crawlers.adapters.tier1_tls.tomeiusa import TomeiUsaAdapter
from app.crawlers.adapters.tier1_tls.turnermotorsport import TurnerMotorsportAdapter
from app.crawlers.adapters.tier1_tls.vividracing import VividRacingAdapter
from app.crawlers.adapters.tier1_tls.z1motorsports import Z1MotorsportsAdapter

# Tier 2 — FlareSolverr browser (`FlareSolverrFetcher`)
from app.crawlers.adapters.tier2_browser.americanmuscle import AmericanMuscleAdapter
from app.crawlers.adapters.tier2_browser.apexwheels import ApexWheelsAdapter
from app.crawlers.adapters.tier2_browser.ecstuning import ECSTuningAdapter
from app.crawlers.adapters.tier2_browser.fcpeuro import FCPEuroAdapter
from app.crawlers.adapters.tier2_browser.jegs import JegsAdapter
from app.crawlers.adapters.tier2_browser.speedindustry import SpeedIndustryAdapter
from app.crawlers.adapters.tier2_browser.tirerack import TireRackAdapter
from app.crawlers.fetchers import Fetcher

ADAPTER_REGISTRY: dict[str, type[RetailerCrawlerAdapter]] = {
    # Tier 0 — plain HTTP
    "034motorsport": Motorsport034Adapter,
    "27won": TwentySevenWonAdapter,
    "a90shop": A90ShopAdapter,
    "adro": AdroAdapter,
    "amsperformance": AMSPerformanceAdapter,
    "atpturbo": ATPTurboAdapter,
    "awetuning": AWETuningAdapter,
    "bcracing": BCRacingAdapter,
    "bimmerworld": BimmerworldAdapter,
    "briantooleyracing": BrianTooleyRacingAdapter,
    "driveshaftshop": DriveshaftShopAdapter,
    "essexparts": EssexPartsAdapter,
    "evasivemotorsports": EvasiveMotorsportsAdapter,
    "fifteen52": Fifteen52Adapter,
    "flyinmiata": FlyinMiataAdapter,
    "fortuneauto": FortuneAutoAdapter,
    "fullrace": FullRaceAdapter,
    "functionwerk": FunctionwerkAdapter,
    "girodisc": GirodiscAdapter,
    "gmgracing": GMGRacingAdapter,
    "greddy": GReddyAdapter,
    "hasport": HasportAdapter,
    "hksusa": HKSUSAAdapter,
    "hondata": HondataAdapter,
    "hrewheels": HREWheelsAdapter,
    "iagperformance": IAGPerformanceAdapter,
    "ie": IEAdapter,
    "ind": INDAdapter,
    "katech": KatechAdapter,
    "ktuner": KTunerAdapter,
    "lingenfelter": LingenfelterAdapter,
    "maperformance": MAPerformanceAdapter,
    "prlmotorsports": PRLMotorsportsAdapter,
    "rallysportdirect": RallysportDirectAdapter,
    "roadsportsupply": RoadSportSupplyAdapter,
    "sheepeybuilt": SheepeyBuiltAdapter,
    "steeda": SteedaAdapter,
    "studiorsr": StudioRSRAdapter,
    "subispeed": SubispeedAdapter,
    "summitracing": SummitRacingAdapter,
    "tickperformance": TickPerformanceAdapter,
    "titan7": Titan7Adapter,
    "wheelsboutique": WheelsBoutiqueAdapter,
    "xph": XPHAdapter,
    # Tier 1 — TLS impersonation
    "apr": APRAdapter,
    "cobbtuning": CobbTuningAdapter,
    "enjukuracing": EnjukuRacingAdapter,
    "forgeline": ForgelineAdapter,
    "goodwinracing": GoodWinRacingAdapter,
    "kwsuspensions": KWSuspensionsAdapter,
    "mackinindustries": MackinIndustriesAdapter,
    "suncoastparts": SuncoastPartsAdapter,
    "texasspeed": TexasSpeedAdapter,
    "tomeiusa": TomeiUsaAdapter,
    "turnermotorsport": TurnerMotorsportAdapter,
    "vividracing": VividRacingAdapter,
    "z1motorsports": Z1MotorsportsAdapter,
    # Tier 2 — FlareSolverr browser
    "americanmuscle": AmericanMuscleAdapter,
    "apexwheels": ApexWheelsAdapter,
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
    if host == "27won.com" or host.endswith(".27won.com"):
        return "27won"
    if host.endswith("a90shop.com"):
        return "a90shop"
    if host == "adro.com" or host.endswith(".adro.com"):
        return "adro"
    if host == "amsperformance.com" or host.endswith(".amsperformance.com"):
        return "amsperformance"
    # Apex rebranded from Apex Race Parts → Apex Wheels and migrated off
    # Shopify onto Nuxt + Sanity + Vercel. Route both the new host and the
    # legacy one to the same adapter so archive-replay and any still-cached
    # Chrome-extension submissions on the old URLs still get a site-specific
    # parser. The old Shopify ``/products/<handle>`` URLs no longer resolve
    # (301 → apexwheels.com root), but ``_is_product_url`` accepts them for
    # archive routing.
    if host == "apexwheels.com" or host.endswith(".apexwheels.com"):
        return "apexwheels"
    if host == "apexraceparts.com" or host.endswith(".apexraceparts.com"):
        return "apexwheels"
    if host == "atpturbo.com" or host.endswith(".atpturbo.com"):
        return "atpturbo"
    if host == "awe-tuning.com" or host.endswith(".awe-tuning.com"):
        return "awetuning"
    if host == "bcracing-na.com" or host.endswith(".bcracing-na.com"):
        return "bcracing"
    if host == "bimmerworld.com" or host.endswith(".bimmerworld.com"):
        return "bimmerworld"
    if host == "briantooleyracing.com" or host.endswith(".briantooleyracing.com"):
        return "briantooleyracing"
    if host == "driveshaftshop.com" or host.endswith(".driveshaftshop.com"):
        return "driveshaftshop"
    if host == "essexparts.com" or host.endswith(".essexparts.com"):
        return "essexparts"
    if host == "evasivemotorsports.com" or host.endswith(".evasivemotorsports.com"):
        return "evasivemotorsports"
    if host == "fifteen52.com" or host.endswith(".fifteen52.com"):
        return "fifteen52"
    if host == "flyinmiata.com" or host.endswith(".flyinmiata.com"):
        return "flyinmiata"
    if host == "fortuneauto-na.com" or host.endswith(".fortuneauto-na.com"):
        return "fortuneauto"
    if host == "full-race.com" or host.endswith(".full-race.com"):
        return "fullrace"
    if host == "functionwerk.com" or host.endswith(".functionwerk.com"):
        return "functionwerk"
    if host == "girodisc.com" or host.endswith(".girodisc.com"):
        return "girodisc"
    if host == "gmgracing.com" or host.endswith(".gmgracing.com") or host == "gmgracing.myshopify.com":
        return "gmgracing"
    if host == "greddy.com" or host.endswith(".greddy.com"):
        return "greddy"
    if host == "hasportperformance.com" or host.endswith(".hasportperformance.com"):
        return "hasport"
    if host == "hasport.com" or host.endswith(".hasport.com"):
        return "hasport"
    if host == "hksusa.com" or host.endswith(".hksusa.com"):
        return "hksusa"
    if host == "hondata.com" or host.endswith(".hondata.com"):
        return "hondata"
    if host == "hrewheels.com" or host.endswith(".hrewheels.com"):
        return "hrewheels"
    if host == "iagperformance.com" or host.endswith(".iagperformance.com"):
        return "iagperformance"
    if host == "performancebyie.com" or host.endswith(".performancebyie.com"):
        return "ie"
    if host == "ind-distribution.com" or host.endswith(".ind-distribution.com"):
        return "ind"
    # Backlog listed ``katech.com``, but that host belongs to Kinetic Art &
    # Technology (motion-system/electric-motor shop, unrelated). The engine
    # builder lives at ``katechengines.com``; route only that domain here.
    if host == "katechengines.com" or host.endswith(".katechengines.com"):
        return "katech"
    if host == "ktuner.com" or host.endswith(".ktuner.com"):
        return "ktuner"
    if host == "lingenfelter.com" or host.endswith(".lingenfelter.com"):
        return "lingenfelter"
    if host == "maperformance.com" or host.endswith(".maperformance.com"):
        return "maperformance"
    if host == "prlmotorsports.com" or host.endswith(".prlmotorsports.com"):
        return "prlmotorsports"
    if host == "rallysportdirect.com" or host.endswith(".rallysportdirect.com"):
        return "rallysportdirect"
    if host == "roadsportsupply.com" or host.endswith(".roadsportsupply.com"):
        return "roadsportsupply"
    if host == "sheepeyrace.com" or host.endswith(".sheepeyrace.com"):
        return "sheepeybuilt"
    if host == "sheepeybuilt.com" or host.endswith(".sheepeybuilt.com"):
        return "sheepeybuilt"
    if host == "steeda.com" or host.endswith(".steeda.com"):
        return "steeda"
    if host == "studiorsr.com" or host.endswith(".studiorsr.com"):
        return "studiorsr"
    if host == "subispeed.com" or host.endswith(".subispeed.com"):
        return "subispeed"
    if host == "summitracing.com" or host.endswith(".summitracing.com"):
        return "summitracing"
    if host == "tickperformance.com" or host.endswith(".tickperformance.com"):
        return "tickperformance"
    if host == "titan7.com" or host.endswith(".titan7.com"):
        return "titan7"
    if host == "tomeiusa.com" or host.endswith(".tomeiusa.com"):
        return "tomeiusa"
    if host == "wheelsboutique.com" or host.endswith(".wheelsboutique.com"):
        return "wheelsboutique"
    if host == "x-ph.com" or host.endswith(".x-ph.com"):
        return "xph"
    # Tier 1 — TLS impersonation
    if host == "goapr.com" or host.endswith(".goapr.com"):
        return "apr"
    if host == "cobbtuning.com" or host.endswith(".cobbtuning.com"):
        return "cobbtuning"
    if host == "enjukuracing.com" or host.endswith(".enjukuracing.com"):
        return "enjukuracing"
    if host == "forgeline.com" or host.endswith(".forgeline.com"):
        return "forgeline"
    if host == "good-win-racing.com" or host.endswith(".good-win-racing.com"):
        return "goodwinracing"
    if host == "kwsuspensions.com" or host.endswith(".kwsuspensions.com"):
        return "kwsuspensions"
    if host == "mackin-ind.com" or host.endswith(".mackin-ind.com"):
        return "mackinindustries"
    if host == "mackinindustries.com" or host.endswith(".mackinindustries.com"):
        return "mackinindustries"
    if host == "suncoastparts.com" or host.endswith(".suncoastparts.com"):
        return "suncoastparts"
    if host == "texas-speed.com" or host.endswith(".texas-speed.com"):
        return "texasspeed"
    if host == "turnermotorsport.com" or host.endswith(".turnermotorsport.com"):
        return "turnermotorsport"
    if host == "vividracing.com" or host.endswith(".vividracing.com"):
        return "vividracing"
    if host == "z1motorsports.com" or host.endswith(".z1motorsports.com"):
        return "z1motorsports"
    # Tier 2 — FlareSolverr browser
    if host == "americanmuscle.com" or host.endswith(".americanmuscle.com"):
        return "americanmuscle"
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
