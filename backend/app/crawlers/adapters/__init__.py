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
from app.crawlers.adapters.tier0_http.afepower import AfePowerAdapter
from app.crawlers.adapters.tier0_http.amsperformance import AMSPerformanceAdapter
from app.crawlers.adapters.tier0_http.aprperformance import APRPerformanceAdapter
from app.crawlers.adapters.tier0_http.atpturbo import ATPTurboAdapter
from app.crawlers.adapters.tier0_http.awetuning import AWETuningAdapter
from app.crawlers.adapters.tier0_http.bcracing import BCRacingAdapter
from app.crawlers.adapters.tier0_http.bimmerworld import BimmerworldAdapter
from app.crawlers.adapters.tier0_http.bloxracing import BloxRacingAdapter
from app.crawlers.adapters.tier0_http.briantooleyracing import BrianTooleyRacingAdapter
from app.crawlers.adapters.tier0_http.burgermotorsports import BurgerMotorsportsAdapter
from app.crawlers.adapters.tier0_http.buschurracing import BuschurRacingAdapter
from app.crawlers.adapters.tier0_http.corksport import CorkSportAdapter
from app.crawlers.adapters.tier0_http.csfrace import CSFRaceAdapter
from app.crawlers.adapters.tier0_http.deatschwerks import DeatschwerksAdapter
from app.crawlers.adapters.tier0_http.delicioustuning import DeliciousTuningAdapter
from app.crawlers.adapters.tier0_http.driveshaftshop import DriveshaftShopAdapter
from app.crawlers.adapters.tier0_http.ecutek import EcuTekAdapter
from app.crawlers.adapters.tier0_http.englishracing import EnglishRacingAdapter
from app.crawlers.adapters.tier0_http.essexparts import EssexPartsAdapter
from app.crawlers.adapters.tier0_http.ets import ETSAdapter
from app.crawlers.adapters.tier0_http.evasivemotorsports import EvasiveMotorsportsAdapter
from app.crawlers.adapters.tier0_http.fifteen52 import Fifteen52Adapter
from app.crawlers.adapters.tier0_http.flyinmiata import FlyinMiataAdapter
from app.crawlers.adapters.tier0_http.ftpmotorsports import FTPMotorsportsAdapter
from app.crawlers.adapters.tier0_http.fullrace import FullRaceAdapter
from app.crawlers.adapters.tier0_http.functionwerk import FunctionwerkAdapter
from app.crawlers.adapters.tier0_http.girodisc import GirodiscAdapter
from app.crawlers.adapters.tier0_http.gmgracing import GMGRacingAdapter
from app.crawlers.adapters.tier0_http.greddy import GReddyAdapter
from app.crawlers.adapters.tier0_http.grimmspeed import GrimmSpeedAdapter
from app.crawlers.adapters.tier0_http.haltech import HaltechAdapter
from app.crawlers.adapters.tier0_http.hasport import HasportAdapter
from app.crawlers.adapters.tier0_http.hennessey import HennesseyAdapter
from app.crawlers.adapters.tier0_http.hksusa import HKSUSAAdapter
from app.crawlers.adapters.tier0_http.hondata import HondataAdapter
from app.crawlers.adapters.tier0_http.hrewheels import HREWheelsAdapter
from app.crawlers.adapters.tier0_http.iagperformance import IAGPerformanceAdapter
from app.crawlers.adapters.tier0_http.ie import IEAdapter
from app.crawlers.adapters.tier0_http.ind import INDAdapter
from app.crawlers.adapters.tier0_http.injectordynamics import InjectorDynamicsAdapter
from app.crawlers.adapters.tier0_http.injentechnology import InjenTechnologyAdapter
from app.crawlers.adapters.tier0_http.ioportracing import IOPortRacingAdapter
from app.crawlers.adapters.tier0_http.jltperformance import JLTPerformanceAdapter
from app.crawlers.adapters.tier0_http.karcepts import KarceptsAdapter
from app.crawlers.adapters.tier0_http.katech import KatechAdapter
from app.crawlers.adapters.tier0_http.ktuner import KTunerAdapter
from app.crawlers.adapters.tier0_http.lingenfelter import LingenfelterAdapter
from app.crawlers.adapters.tier0_http.linkecu import LinkEcuAdapter
from app.crawlers.adapters.tier0_http.maperformance import MAPerformanceAdapter
from app.crawlers.adapters.tier0_http.mishimoto import MishimotoAdapter
from app.crawlers.adapters.tier0_http.modernmusclextreme import ModernMuscleXtremeAdapter
from app.crawlers.adapters.tier0_http.motorsport034 import Motorsport034Adapter
from app.crawlers.adapters.tier0_http.mountainpassperformance import MountainPassPerformanceAdapter
from app.crawlers.adapters.tier0_http.ogracing import OGRacingAdapter
from app.crawlers.adapters.tier0_http.openflashperformance import OpenFlashPerformanceAdapter
from app.crawlers.adapters.tier0_http.perrinperformance import PerrinPerformanceAdapter
from app.crawlers.adapters.tier0_http.prlmotorsports import PRLMotorsportsAdapter
from app.crawlers.adapters.tier0_http.racerwholesale import RacerWholesaleAdapter
from app.crawlers.adapters.tier0_http.radium import RadiumAdapter
from app.crawlers.adapters.tier0_http.rallysportdirect import RallysportDirectAdapter
from app.crawlers.adapters.tier0_http.roadraceengineering import RoadRaceEngineeringAdapter
from app.crawlers.adapters.tier0_http.roadsportsupply import RoadSportSupplyAdapter
from app.crawlers.adapters.tier0_http.rotiform import RotiformAdapter
from app.crawlers.adapters.tier0_http.seiboncarbon import SeibonCarbonAdapter
from app.crawlers.adapters.tier0_http.sheepeybuilt import SheepeyBuiltAdapter
from app.crawlers.adapters.tier0_http.skunk2 import Skunk2Adapter
from app.crawlers.adapters.tier0_http.stanceusa import StanceUsaAdapter
from app.crawlers.adapters.tier0_http.steeda import SteedaAdapter
from app.crawlers.adapters.tier0_http.stoptech import StoptechAdapter
from app.crawlers.adapters.tier0_http.studiorsr import StudioRSRAdapter
from app.crawlers.adapters.tier0_http.subispeed import SubispeedAdapter
from app.crawlers.adapters.tier0_http.tein import TeinAdapter
from app.crawlers.adapters.tier0_http.tickperformance import TickPerformanceAdapter
from app.crawlers.adapters.tier0_http.titan7 import Titan7Adapter
from app.crawlers.adapters.tier0_http.twentysevenwon import TwentySevenWonAdapter
from app.crawlers.adapters.tier0_http.unpluggedperformance import UnpluggedPerformanceAdapter
from app.crawlers.adapters.tier0_http.verusengineering import VerusEngineeringAdapter
from app.crawlers.adapters.tier0_http.voltexusa import VoltexUsaAdapter
from app.crawlers.adapters.tier0_http.wheelsboutique import WheelsBoutiqueAdapter
from app.crawlers.adapters.tier0_http.wilwood import WilwoodAdapter
from app.crawlers.adapters.tier0_http.xph import XPHAdapter

# Tier 1 — TLS impersonation (`TlsFetcher`, `curl_cffi`)
from app.crawlers.adapters.tier1_tls.apr import APRAdapter
from app.crawlers.adapters.tier1_tls.cobbtuning import CobbTuningAdapter
from app.crawlers.adapters.tier1_tls.enjukuracing import EnjukuRacingAdapter
from app.crawlers.adapters.tier1_tls.forgeline import ForgelineAdapter
from app.crawlers.adapters.tier1_tls.fortuneauto import FortuneAutoAdapter
from app.crawlers.adapters.tier1_tls.goodwinracing import GoodWinRacingAdapter
from app.crawlers.adapters.tier1_tls.kwsuspensions import KWSuspensionsAdapter
from app.crawlers.adapters.tier1_tls.mackinindustries import MackinIndustriesAdapter
from app.crawlers.adapters.tier1_tls.racingbeat import RacingBeatAdapter
from app.crawlers.adapters.tier1_tls.suncoastparts import SuncoastPartsAdapter
from app.crawlers.adapters.tier1_tls.texasspeed import TexasSpeedAdapter
from app.crawlers.adapters.tier1_tls.tomeiusa import TomeiUsaAdapter
from app.crawlers.adapters.tier1_tls.turnermotorsport import TurnerMotorsportAdapter
from app.crawlers.adapters.tier1_tls.vividracing import VividRacingAdapter
from app.crawlers.adapters.tier1_tls.z1motorsports import Z1MotorsportsAdapter

# Tier 2 — FlareSolverr browser (`FlareSolverrFetcher`)
from app.crawlers.adapters.tier2_browser.aemelectronics import AEMElectronicsAdapter
from app.crawlers.adapters.tier2_browser.americanmuscle import AmericanMuscleAdapter
from app.crawlers.adapters.tier2_browser.apexwheels import ApexWheelsAdapter
from app.crawlers.adapters.tier2_browser.dinan import DinanAdapter
from app.crawlers.adapters.tier2_browser.ecstuning import ECSTuningAdapter
from app.crawlers.adapters.tier2_browser.fcpeuro import FCPEuroAdapter
from app.crawlers.adapters.tier2_browser.jegs import JegsAdapter
from app.crawlers.adapters.tier2_browser.speedindustry import SpeedIndustryAdapter
from app.crawlers.adapters.tier2_browser.summitracing import SummitRacingAdapter
from app.crawlers.adapters.tier2_browser.tirerack import TireRackAdapter
from app.crawlers.fetchers import Fetcher

ADAPTER_REGISTRY: dict[str, type[RetailerCrawlerAdapter]] = {
    # Tier 0 — plain HTTP
    "034motorsport": Motorsport034Adapter,
    "27won": TwentySevenWonAdapter,
    "a90shop": A90ShopAdapter,
    "adro": AdroAdapter,
    "afepower": AfePowerAdapter,
    "amsperformance": AMSPerformanceAdapter,
    "aprperformance": APRPerformanceAdapter,
    "atpturbo": ATPTurboAdapter,
    "awetuning": AWETuningAdapter,
    "bcracing": BCRacingAdapter,
    "bimmerworld": BimmerworldAdapter,
    "bloxracing": BloxRacingAdapter,
    "briantooleyracing": BrianTooleyRacingAdapter,
    "burgermotorsports": BurgerMotorsportsAdapter,
    "buschurracing": BuschurRacingAdapter,
    "corksport": CorkSportAdapter,
    "csfrace": CSFRaceAdapter,
    "deatschwerks": DeatschwerksAdapter,
    "delicioustuning": DeliciousTuningAdapter,
    "driveshaftshop": DriveshaftShopAdapter,
    "ecutek": EcuTekAdapter,
    "englishracing": EnglishRacingAdapter,
    "essexparts": EssexPartsAdapter,
    "ets": ETSAdapter,
    "evasivemotorsports": EvasiveMotorsportsAdapter,
    "fifteen52": Fifteen52Adapter,
    "flyinmiata": FlyinMiataAdapter,
    "ftpmotorsports": FTPMotorsportsAdapter,
    "fullrace": FullRaceAdapter,
    "functionwerk": FunctionwerkAdapter,
    "girodisc": GirodiscAdapter,
    "gmgracing": GMGRacingAdapter,
    "greddy": GReddyAdapter,
    "grimmspeed": GrimmSpeedAdapter,
    "haltech": HaltechAdapter,
    "hasport": HasportAdapter,
    "hennessey": HennesseyAdapter,
    "hksusa": HKSUSAAdapter,
    "hondata": HondataAdapter,
    "hrewheels": HREWheelsAdapter,
    "iagperformance": IAGPerformanceAdapter,
    "ie": IEAdapter,
    "ind": INDAdapter,
    "injectordynamics": InjectorDynamicsAdapter,
    "injentechnology": InjenTechnologyAdapter,
    "ioportracing": IOPortRacingAdapter,
    "jltperformance": JLTPerformanceAdapter,
    "karcepts": KarceptsAdapter,
    "katech": KatechAdapter,
    "ktuner": KTunerAdapter,
    "lingenfelter": LingenfelterAdapter,
    "linkecu": LinkEcuAdapter,
    "maperformance": MAPerformanceAdapter,
    "mishimoto": MishimotoAdapter,
    "modernmusclextreme": ModernMuscleXtremeAdapter,
    "mountainpassperformance": MountainPassPerformanceAdapter,
    "ogracing": OGRacingAdapter,
    "openflashperformance": OpenFlashPerformanceAdapter,
    "perrinperformance": PerrinPerformanceAdapter,
    "prlmotorsports": PRLMotorsportsAdapter,
    "racerwholesale": RacerWholesaleAdapter,
    "radium": RadiumAdapter,
    "rallysportdirect": RallysportDirectAdapter,
    "roadraceengineering": RoadRaceEngineeringAdapter,
    "roadsportsupply": RoadSportSupplyAdapter,
    "rotiform": RotiformAdapter,
    "seiboncarbon": SeibonCarbonAdapter,
    "sheepeybuilt": SheepeyBuiltAdapter,
    "skunk2": Skunk2Adapter,
    "stanceusa": StanceUsaAdapter,
    "steeda": SteedaAdapter,
    "stoptech": StoptechAdapter,
    "studiorsr": StudioRSRAdapter,
    "subispeed": SubispeedAdapter,
    "tein": TeinAdapter,
    "tickperformance": TickPerformanceAdapter,
    "titan7": Titan7Adapter,
    "unpluggedperformance": UnpluggedPerformanceAdapter,
    "verusengineering": VerusEngineeringAdapter,
    "voltexusa": VoltexUsaAdapter,
    "wheelsboutique": WheelsBoutiqueAdapter,
    "wilwood": WilwoodAdapter,
    "xph": XPHAdapter,
    # Tier 1 — TLS impersonation
    "apr": APRAdapter,
    "cobbtuning": CobbTuningAdapter,
    "enjukuracing": EnjukuRacingAdapter,
    "forgeline": ForgelineAdapter,
    "fortuneauto": FortuneAutoAdapter,
    "goodwinracing": GoodWinRacingAdapter,
    "kwsuspensions": KWSuspensionsAdapter,
    "mackinindustries": MackinIndustriesAdapter,
    "racingbeat": RacingBeatAdapter,
    "suncoastparts": SuncoastPartsAdapter,
    "texasspeed": TexasSpeedAdapter,
    "tomeiusa": TomeiUsaAdapter,
    "turnermotorsport": TurnerMotorsportAdapter,
    "vividracing": VividRacingAdapter,
    "z1motorsports": Z1MotorsportsAdapter,
    # Tier 2 — FlareSolverr browser
    "aemelectronics": AEMElectronicsAdapter,
    "americanmuscle": AmericanMuscleAdapter,
    "apexwheels": ApexWheelsAdapter,
    "dinan": DinanAdapter,
    "ecstuning": ECSTuningAdapter,
    "fcpeuro": FCPEuroAdapter,
    "jegs": JegsAdapter,
    "speedindustry": SpeedIndustryAdapter,
    "summitracing": SummitRacingAdapter,
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
    if host == "afepower.com" or host.endswith(".afepower.com"):
        return "afepower"
    if host == "amsperformance.com" or host.endswith(".amsperformance.com"):
        return "amsperformance"
    # APR Performance (US) — track aero house brand at shop.aprperformance.com
    # (Shopify). **Not** the goapr.com Audi/VW tuning shop, which is the
    # existing ``apr`` adapter. Apex aprperformance.com 301s to shop.*
    if host == "shop.aprperformance.com" or host.endswith(".shop.aprperformance.com"):
        return "aprperformance"
    if host == "aprperformance.com" or host.endswith(".aprperformance.com"):
        return "aprperformance"
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
    if host == "bloxracing.com" or host.endswith(".bloxracing.com"):
        return "bloxracing"
    if host == "briantooleyracing.com" or host.endswith(".briantooleyracing.com"):
        return "briantooleyracing"
    # BMS's live storefront is burgertuning.com; burger-motorsports.com is
    # defunct (NXDOMAIN / ECONNREFUSED) but keep the mapping so any
    # chrome-extension submissions or archived URLs on the legacy host still
    # route to the site-specific parser instead of the generic fallback.
    if host == "burgertuning.com" or host.endswith(".burgertuning.com"):
        return "burgermotorsports"
    if host == "burger-motorsports.com" or host.endswith(".burger-motorsports.com"):
        return "burgermotorsports"
    # Buschur Racing runs a PrestaShop 1.6 storefront at buschursllc.com/br-cart/;
    # buschurracing.com is the marketing apex with a TLS SAN that covers only
    # buschursllc.com, and buschuracing.com is a typo-catcher placeholder. Map
    # all three so archive replay and chrome-extension submissions route to
    # the site-specific parser.
    if host == "buschurracing.com" or host.endswith(".buschurracing.com"):
        return "buschurracing"
    if host == "buschursllc.com" or host.endswith(".buschursllc.com"):
        return "buschurracing"
    if host == "buschuracing.com" or host.endswith(".buschuracing.com"):
        return "buschurracing"
    if host == "corksport.com" or host.endswith(".corksport.com"):
        return "corksport"
    if host == "csfrace.com" or host.endswith(".csfrace.com"):
        return "csfrace"
    if host == "deatschwerks.com" or host.endswith(".deatschwerks.com"):
        return "deatschwerks"
    if host == "delicioustuning.com" or host.endswith(".delicioustuning.com"):
        return "delicioustuning"
    if host == "driveshaftshop.com" or host.endswith(".driveshaftshop.com"):
        return "driveshaftshop"
    if host == "ecutek.com" or host.endswith(".ecutek.com"):
        return "ecutek"
    # English Racing's live catalog is at englishracing.net (Shopify); the
    # englishracing.com apex points at an unresolvable residential IP but is
    # kept here for archive replay.
    if host == "englishracing.net" or host.endswith(".englishracing.net"):
        return "englishracing"
    if host == "englishracing.com" or host.endswith(".englishracing.com"):
        return "englishracing"
    if host == "essexparts.com" or host.endswith(".essexparts.com"):
        return "essexparts"
    # ETS's live storefront is extremeturbosystems.com; ets-racing.com serves
    # an expired cert and is an unrelated business. Map only the live host.
    if host == "extremeturbosystems.com" or host.endswith(".extremeturbosystems.com"):
        return "ets"
    if host == "evasivemotorsports.com" or host.endswith(".evasivemotorsports.com"):
        return "evasivemotorsports"
    if host == "fifteen52.com" or host.endswith(".fifteen52.com"):
        return "fifteen52"
    if host == "flyinmiata.com" or host.endswith(".flyinmiata.com"):
        return "flyinmiata"
    # ``fortuneauto-na.com`` was the old Shopify NA storefront (now NXDOMAIN);
    # the current marketing catalog is ``fortune-auto.com``. Route both so
    # archive replay of the old URLs still lands on the Fortune Auto parser.
    if host == "fortune-auto.com" or host.endswith(".fortune-auto.com"):
        return "fortuneauto"
    if host == "fortuneauto-na.com" or host.endswith(".fortuneauto-na.com"):
        return "fortuneauto"
    # FTP Motorsport's live storefront is ftpmotorsport.com.tw (Taiwan-based,
    # EasyStore platform); the .com variant 302s to the .com.tw host. The
    # .s-plural hosts from the original backlog (ftpmotorsports.com /
    # ftp-motorsports.com) are NXDOMAIN and intentionally not mapped.
    if host == "ftpmotorsport.com.tw" or host.endswith(".ftpmotorsport.com.tw"):
        return "ftpmotorsports"
    if host == "ftpmotorsport.com" or host.endswith(".ftpmotorsport.com"):
        return "ftpmotorsports"
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
    if host == "grimmspeed.com" or host.endswith(".grimmspeed.com"):
        return "grimmspeed"
    if host == "haltech.com" or host.endswith(".haltech.com"):
        return "haltech"
    if host == "hasportperformance.com" or host.endswith(".hasportperformance.com"):
        return "hasport"
    if host == "hasport.com" or host.endswith(".hasport.com"):
        return "hasport"
    # Hennessey Performance lives at hennesseyperformance.com (WordPress).
    # hennessey.com is a separate Venom F5 hypercar storefront — intentionally
    # not routed here; add a sibling adapter if that catalog is ever wanted.
    if host == "hennesseyperformance.com" or host.endswith(".hennesseyperformance.com"):
        return "hennessey"
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
    if host == "injectordynamics.com" or host.endswith(".injectordynamics.com"):
        return "injectordynamics"
    # Injen's live storefront is injen.com (WSM Commerce). Candidate hosts
    # injenonline.com / injentech.com / injenusa.com don't resolve; adding
    # only the live host.
    if host == "injen.com" or host.endswith(".injen.com"):
        return "injentechnology"
    if host == "ioportracing.com" or host.endswith(".ioportracing.com"):
        return "ioportracing"
    # JLT Performance's first-party storefront is gone (apex hosts NXDOMAIN /
    # parked, jltcoldairintake.com is an Amazon-affiliate marketing shell).
    # The adapter is a stub; hosts are mapped only so archive replay /
    # chrome-extension submissions on the legacy URLs get a documented handler
    # rather than the generic fallback.
    if host == "jltperformance.com" or host.endswith(".jltperformance.com"):
        return "jltperformance"
    if host == "jltruemeaning.com" or host.endswith(".jltruemeaning.com"):
        return "jltperformance"
    if host == "jltcoldairintake.com" or host.endswith(".jltcoldairintake.com"):
        return "jltperformance"
    if host == "karcepts.com" or host.endswith(".karcepts.com"):
        return "karcepts"
    # Backlog listed ``katech.com``, but that host belongs to Kinetic Art &
    # Technology (motion-system/electric-motor shop, unrelated). The engine
    # builder lives at ``katechengines.com``; route only that domain here.
    if host == "katechengines.com" or host.endswith(".katechengines.com"):
        return "katech"
    if host == "ktuner.com" or host.endswith(".ktuner.com"):
        return "ktuner"
    if host == "lingenfelter.com" or host.endswith(".lingenfelter.com"):
        return "lingenfelter"
    # Link ECU's live catalog is the dealer storefront (NetSuite SCA); the
    # linkecu.com apex is a marketing-only site. Both mapped so both resolve
    # to the dedicated adapter.
    if host == "dealers.linkecu.com" or host.endswith(".dealers.linkecu.com"):
        return "linkecu"
    if host == "linkecu.com" or host.endswith(".linkecu.com"):
        return "linkecu"
    if host == "maperformance.com" or host.endswith(".maperformance.com"):
        return "maperformance"
    if host == "mishimoto.com" or host.endswith(".mishimoto.com"):
        return "mishimoto"
    # Modern Muscle Xtreme lives at modernmusclextreme.com; the modernmusclepa.com
    # alias doesn't resolve at recon time but keep no mapping for it — add one if
    # it comes back online.
    if host == "modernmusclextreme.com" or host.endswith(".modernmusclextreme.com"):
        return "modernmusclextreme"
    if host == "mountainpassperformance.com" or host.endswith(".mountainpassperformance.com"):
        return "mountainpassperformance"
    if host == "ogracing.com" or host.endswith(".ogracing.com"):
        return "ogracing"
    # OpenFlash apex is openflashtablet.com (WooCommerce storefront);
    # openflashperformance.com 302s to it. Candidate hosts openflashtuning.com
    # and theoftshop.com are NXDOMAIN — not mapped.
    if host == "openflashtablet.com" or host.endswith(".openflashtablet.com"):
        return "openflashperformance"
    if host == "openflashperformance.com" or host.endswith(".openflashperformance.com"):
        return "openflashperformance"
    # Perrin apex is perrin.com; perrinperformance.com 301s to it. Both
    # mapped so archive replay / cached extension submissions on the legacy
    # host route to the site-specific parser.
    if host == "perrin.com" or host.endswith(".perrin.com"):
        return "perrinperformance"
    if host == "perrinperformance.com" or host.endswith(".perrinperformance.com"):
        return "perrinperformance"
    if host == "prlmotorsports.com" or host.endswith(".prlmotorsports.com"):
        return "prlmotorsports"
    # Racer Wholesale — stub adapter (site has been offline ~3 years; .com is
    # Hostinger-parked, .net NXDOMAIN). Mapped for archive replay.
    if host == "racerwholesale.com" or host.endswith(".racerwholesale.com"):
        return "racerwholesale"
    if host == "radiumauto.com" or host.endswith(".radiumauto.com"):
        return "radium"
    if host == "rallysportdirect.com" or host.endswith(".rallysportdirect.com"):
        return "rallysportdirect"
    # Road Race Engineering — stub adapter (catalog-as-long-page with inline
    # PayPal buttons; no per-product URLs). Mapped for archive replay only.
    if host == "roadraceengineering.com" or host.endswith(".roadraceengineering.com"):
        return "roadraceengineering"
    if host == "roadsportsupply.com" or host.endswith(".roadsportsupply.com"):
        return "roadsportsupply"
    if host == "rotiform.com" or host.endswith(".rotiform.com"):
        return "rotiform"
    if host == "seiboncarbon.com" or host.endswith(".seiboncarbon.com"):
        return "seiboncarbon"
    if host == "sheepeyrace.com" or host.endswith(".sheepeyrace.com"):
        return "sheepeybuilt"
    if host == "sheepeybuilt.com" or host.endswith(".sheepeybuilt.com"):
        return "sheepeybuilt"
    if host == "skunk2.com" or host.endswith(".skunk2.com"):
        return "skunk2"
    # Stance Suspension USA's live site is stance-usa.com (hyphenated); the
    # non-hyphenated stanceusa.com is a parked domain and stancesuspension.com
    # doesn't serve the catalog.
    if host == "stance-usa.com" or host.endswith(".stance-usa.com"):
        return "stanceusa"
    if host == "steeda.com" or host.endswith(".steeda.com"):
        return "steeda"
    # StopTech — stub adapter; stoptech.com 301s to centricparts.com marketing
    # landing after Power Stop acquisition. Mapped for archive replay.
    if host == "stoptech.com" or host.endswith(".stoptech.com"):
        return "stoptech"
    if host == "studiorsr.com" or host.endswith(".studiorsr.com"):
        return "studiorsr"
    if host == "subispeed.com" or host.endswith(".subispeed.com"):
        return "subispeed"
    if host == "summitracing.com" or host.endswith(".summitracing.com"):
        return "summitracing"
    # Tein USA — pure-static Apache hand-HTML catalog at www.tein.com. Apex
    # tein.com has no A record; tein.co.jp is the separate Japanese sister
    # site and is intentionally not routed here.
    if host == "tein.com" or host.endswith(".tein.com"):
        return "tein"
    if host == "tickperformance.com" or host.endswith(".tickperformance.com"):
        return "tickperformance"
    if host == "titan7.com" or host.endswith(".titan7.com"):
        return "titan7"
    if host == "titan-7.com" or host.endswith(".titan-7.com"):
        return "titan7"
    if host == "tomeiusa.com" or host.endswith(".tomeiusa.com"):
        return "tomeiusa"
    if host == "unpluggedperformance.com" or host.endswith(".unpluggedperformance.com"):
        return "unpluggedperformance"
    if host == "verus-engineering.com" or host.endswith(".verus-engineering.com"):
        return "verusengineering"
    # Voltex's US storefront is voltexracing.com ("VOLTEX Racing North
    # America" — WooCommerce). Candidate hosts voltexusa.com / voltex-
    # motorsports.com from the original backlog don't resolve.
    if host == "voltexracing.com" or host.endswith(".voltexracing.com"):
        return "voltexusa"
    if host == "wheelsboutique.com" or host.endswith(".wheelsboutique.com"):
        return "wheelsboutique"
    if host == "wilwood.com" or host.endswith(".wilwood.com"):
        return "wilwood"
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
    # Racing Beat's live storefront is on Interchange (classic Perl, same
    # platform as goodwinracing); served behind Cloudflare, needs TLS
    # impersonation to clear the challenge.
    if host == "racingbeat.com" or host.endswith(".racingbeat.com"):
        return "racingbeat"
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
    # AEM Performance Electronics runs a Drupal 7 storefront entirely behind
    # Cloudflare managed JS challenge — parse-only until FlareSolverr is
    # wired in. aem-usa.com is a different company (aerospace passives) and
    # is NOT routed here.
    if host == "aemelectronics.com" or host.endswith(".aemelectronics.com"):
        return "aemelectronics"
    if host == "aempower.com" or host.endswith(".aempower.com"):
        return "aemelectronics"
    if host == "americanmuscle.com" or host.endswith(".americanmuscle.com"):
        return "americanmuscle"
    # Dinan is entirely behind a Cloudflare managed JS challenge — parse-only
    # until FlareSolverr is wired in.
    if host == "dinancars.com" or host.endswith(".dinancars.com"):
        return "dinan"
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
