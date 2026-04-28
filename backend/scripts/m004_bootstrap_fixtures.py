"""Inline bootstrap fixtures for the M004 gold-set labeling tool (DB-less path).

When the labeler is invoked under ``--bootstrap`` and no local DB is reachable
(e.g. Postgres docker not up in CI / auto-mode), the labeler walks this list
instead of querying ``CrawledPage``. Each entry is a hand-crafted "synthetic
crawled page" — a realistic HTML excerpt plus the structural metadata
(``part_id``, ``retailer``, ``category``, ``tier``, ``raw_name``,
``raw_description``) that the live labeler would otherwise pull from the DB.

The fixtures cover the three precedence layers that ``m004_ground_truth`` is
designed to drive: JSON-LD Product, microdata ``itemprop="brand"``, and
OpenGraph ``og:brand`` / ``product:brand``. They span at least three retailers
and three SpecRegistry sub-slugs so the strata report produced alongside the
bootstrap row dump shows non-trivial diversity.

Schema parity
-------------
Each fixture is a ``BootstrapFixture`` (TypedDict). The ``part_id`` values are
stable opaque strings prefixed with ``"bootstrap-"`` — they are NOT real DB
UUIDs and must never be inserted into the live DB. Downstream slices treat
bootstrap rows as a directional floor and replace them on ``--resume`` once a
human has labeled the same page (LABELING-RULES.md § Bootstrap Rows vs Human
Rows).
"""

from __future__ import annotations

from typing import TypedDict


class BootstrapFixture(TypedDict):
    """One synthetic CrawledPage row for the DB-less bootstrap path."""

    part_id: str
    retailer: str
    category: str
    tier: str
    raw_name: str
    raw_description: str
    html: str


_FIXTURE_BMW_COILOVER = BootstrapFixture(
    part_id="bootstrap-ind-bmw-coilover-001",
    retailer="ind",
    category="Suspension > Coilovers",
    tier="T0",
    raw_name="KW Variant 3 Coilover Kit — BMW M3 (E46)",
    raw_description=(
        "KW Variant 3 inox-line coilovers for the E46 M3. "
        "Independently adjustable compression and rebound damping. "
        "Spring rate 600 lb/in front, 700 lb/in rear. "
        "Material: stainless steel body. Made in Germany."
    ),
    html="""<!DOCTYPE html>
<html>
<head>
  <title>KW Variant 3 Coilover Kit — BMW M3 (E46) | IND Distribution</title>
  <meta property="og:brand" content="KW Suspensions">
  <meta property="product:brand" content="KW">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "KW Variant 3 Coilover Kit",
    "brand": {"@type": "Brand", "name": "KW Suspensions"},
    "category": "Suspension > Coilovers",
    "manufacturer": {"@type": "Organization", "name": "KW Automotive"}
  }
  </script>
</head>
<body>
  <h1>KW Variant 3 Coilover Kit — BMW M3 (E46)</h1>
  <div itemscope itemtype="http://schema.org/Product">
    <span itemprop="brand">KW Suspensions</span>
    <span itemprop="category">coilover</span>
  </div>
  <table class="spec-table">
    <tr><td>Material</td><td>Stainless Steel</td></tr>
    <tr><td>Spring Rate (front)</td><td>600 lb/in</td></tr>
  </table>
  <p>Independent compression and rebound adjustment. Inox-line construction.</p>
</body>
</html>""",
)


_FIXTURE_HONDA_TURBO = BootstrapFixture(
    part_id="bootstrap-hondata-turbo-002",
    retailer="hondata",
    category="Engine > Turbochargers",
    tier="T0",
    raw_name="Garrett G25-660 Turbocharger — Honda Civic Type R (FK8)",
    raw_description=(
        "Garrett G25-660 ball-bearing turbocharger upgrade for the FK8 "
        "Civic Type R. Internal wastegate. Fits 2017-2021 Civic Type R."
    ),
    html="""<!DOCTYPE html>
<html>
<head>
  <title>Garrett G25-660 Turbo — Honda Civic Type R FK8</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Garrett G25-660 Turbocharger",
    "brand": "Garrett Motion",
    "category": "Engine > Turbochargers"
  }
  </script>
</head>
<body>
  <h1>Garrett G25-660 Turbocharger — Honda Civic Type R (FK8)</h1>
  <div itemprop="brand">Garrett Motion</div>
  <p>Ball-bearing CHRA. Internal wastegate actuator. Fits 2017-2021 Civic Type R.</p>
  <ul>
    <li>Material: cast iron turbine housing</li>
  </ul>
</body>
</html>""",
)


_FIXTURE_SUBARU_BRAKE = BootstrapFixture(
    part_id="bootstrap-rallysportdirect-brake-003",
    retailer="rallysportdirect",
    category="Brakes > Pads",
    tier="T1",
    raw_name="Hawk HP+ Brake Pads — Subaru WRX STi (VA)",
    raw_description=(
        "Hawk HP+ street/track brake pad set for the front of the VA-chassis WRX STi. "
        "Aggressive friction compound, 32-62% friction coefficient over 100-1100F."
    ),
    html="""<!DOCTYPE html>
<html>
<head>
  <title>Hawk HP+ Brake Pads — Subaru WRX STi (VA Chassis)</title>
  <meta property="og:brand" content="Hawk Performance">
</head>
<body>
  <h1>Hawk HP+ Brake Pads — Subaru WRX STi (VA)</h1>
  <div itemscope itemtype="http://schema.org/Product">
    <span itemprop="brand">
      <span itemprop="name">Hawk Performance</span>
    </span>
    <span itemprop="category">brake</span>
  </div>
  <p>Street/track friction compound for the VA WRX STi. 2015-2021 fitment.</p>
</body>
</html>""",
)


_FIXTURE_TOYOTA_OG_ONLY = BootstrapFixture(
    part_id="bootstrap-a90shop-intake-004",
    retailer="a90shop",
    category="Engine > Intakes",
    tier="T2",
    raw_name="HKS Premium Cold Air Intake — Toyota GR Supra (A90)",
    raw_description=(
        "HKS Premium intake kit. Designed for the B58 in the A90 Supra. "
        "Aluminum tubing, dry-flow filter element."
    ),
    html="""<!DOCTYPE html>
<html>
<head>
  <title>HKS Premium Cold Air Intake — Toyota GR Supra (A90)</title>
  <meta property="og:brand" content="HKS USA">
  <meta property="product:brand" content="HKS">
</head>
<body>
  <h1>HKS Premium Cold Air Intake — A90 Supra</h1>
  <p>Premium intake for the B58 A90 Supra. Aluminum tubing.</p>
</body>
</html>""",
)


_FIXTURE_UNIVERSAL_HARDWARE = BootstrapFixture(
    part_id="bootstrap-summitracing-hardware-005",
    retailer="summitracing",
    category="Hardware > Fasteners",
    tier="T2",
    raw_name="ARP Pro Series Stainless Steel Bolt Kit — Universal",
    raw_description=(
        "ARP universal stainless steel bolt kit, 12-piece. M10x1.25 thread pitch. "
        "Stainless steel construction; rated to 170,000 psi tensile."
    ),
    html="""<!DOCTYPE html>
<html>
<head>
  <title>ARP Pro Series Bolt Kit — Universal</title>
</head>
<body>
  <h1>ARP Pro Series Stainless Steel Bolt Kit (Universal)</h1>
  <div itemscope itemtype="http://schema.org/Product">
    <span itemprop="manufacturer">ARP</span>
  </div>
  <ul>
    <li>Material: Stainless Steel</li>
    <li>Universal fitment</li>
  </ul>
</body>
</html>""",
)


BOOTSTRAP_FIXTURES: tuple[BootstrapFixture, ...] = (
    _FIXTURE_BMW_COILOVER,
    _FIXTURE_HONDA_TURBO,
    _FIXTURE_SUBARU_BRAKE,
    _FIXTURE_TOYOTA_OG_ONLY,
    _FIXTURE_UNIVERSAL_HARDWARE,
)
"""Locked-order tuple. The labeling tool consumes them in this order so a
truncated bootstrap (`--bootstrap 3`) always picks the first three deterministically,
which keeps tests stable."""
