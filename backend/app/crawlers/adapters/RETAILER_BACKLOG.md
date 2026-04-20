# Retailer Adapter Backlog

Prioritized list of retailers to add to grow enthusiast price-aggregation
coverage. Ordered by impact on platform/segment coverage, not by ease of
implementation. Tier-0/1/2 in this doc refers to **importance**, not the
crawler-fetcher tier (`tier0_http` / `tier1_tls` / `tier2_browser`) used in
the adapter directory layout.

For each entry: domain, what segments it unlocks, why it matters, and any
known scraping notes (platform, anti-bot posture) to inform fetcher-tier
choice when the adapter is built.

---

## Priority 1 — required for credible enthusiast coverage

### ECS Tuning — `ecstuning.com`
- **Segments:** BMW (E-chassis through G-chassis), VAG (Audi, VW, Porsche,
  MINI), Mercedes, Volvo. By volume the most-shopped Euro retailer in the US.
- **Why:** Single biggest gap. Without ECS, any "Euro price compare" feature
  is incomplete. Complements FCP (warranty/maintenance bias) and IND
  (boutique BMW) with broad mid-market pricing.
- **Notes:** Custom platform. Heavy Cloudflare; expect Tier-1 TLS minimum,
  possibly Tier-2 browser. Sitemap exists. Vehicle-fitment URLs are deep —
  discovery should walk category sitemaps, not the fitment selector.

### Turner Motorsport — `turnermotorsport.com`
- **Segments:** BMW street + track, complementary to IND (lifestyle) and
  Bimmerworld (race).
- **Why:** Second-most-shopped BMW retailer after ECS. House-brand parts
  (Turner-branded) only sold here, so prices are reference values, not
  arbitrage candidates — still important for build-list completeness.
- **Notes:** Custom platform. Standard sitemap. Likely Tier-0 or Tier-1.

### AMS Performance — `amsperformance.com`
- **Segments:** R35 GTR, Mk4 Supra + A90 Supra, Evo IX/X, Mk5/6/7 GTI/R,
  Audi RS, Porsche 991/992 Turbo. High-horsepower turbo kits and built
  long-blocks.
- **Why:** High-ticket items ($2k–$30k) where price/availability variance
  matters most for build-list ROI. Currently zero coverage of
  high-horsepower R35/Evo segment.
- **Notes:** Shopify (last check). Tier-0 likely sufficient.

### Z1 Motorsports — `z1motorsports.com`
- **Segments:** 350Z/370Z/G35/G37, R35 GTR, 240SX overlap. The de facto
  hub for the Z/G chassis enthusiast community.
- **Why:** **Zero current Nissan coverage.** Adding Z1 alone unlocks an
  entire chassis platform.
- **Notes:** Custom cart, sitemap available. Tier-0 likely OK.

### Cobb Tuning — `cobbtuning.com`
- **Segments:** Subaru WRX/STI, Ford ST/RS/Mustang Ecoboost,
  Porsche 991/992, Nissan GTR. AccessPort hardware + Stage packages.
- **Why:** AccessPort is the canonical tuning hardware in these platforms;
  Cobb-direct pricing is the reference, and bundle/Stage SKUs are not
  consistently sold elsewhere.
- **Notes:** Custom platform. Some bot protection. Probably Tier-1.

### Tire Rack — `tirerack.com`
- **Segments:** Wheels and tires, all platforms.
- **Why:** Build lists that include wheel/tire packages are incomplete
  without Tire Rack pricing — it's the price-compare benchmark consumers
  already use mentally. Also unlocks staggered fitment / load-rating data
  that retailers above don't surface.
- **Notes:** Heavy anti-bot. Almost certainly Tier-2 browser. Vehicle/size
  selectors drive URL structure — discovery via brand catalogs, not fitment
  selector. Consider whether this lives under a dedicated `wheels_tires/`
  sub-namespace.

---

## Priority 2 — major chassis/segment fill-in

### Enjuku Racing — `enjukuracing.com` — **shipped 2026-04-19** (`tier1_tls/enjukuracing.py`)
- **Segments:** S13/S14/S15 240SX, drift builds, JDM swap parts (SR20,
  RB, KA-T), Nissan platform overflow.
- **Why:** Drift segment is currently uncovered. Also catches older-Nissan
  parts that Z1 doesn't carry.
- **Notes:** BigCommerce (Stencil), per current page source. Tier-0 was the
  initial guess — actually Tier-1: Cloudflare `cf-mitigated: challenge` on
  plain requests, curl_cffi Chrome impersonation passes. Unlike xph, the
  Stencil theme emits a full JSON-LD `Product` block, so parsing reuses the
  shared JSON-LD helpers and keeps BCData only as a price fallback. See
  `site_problem_notes/enjukuracing.md`.

### Texas Speed & Performance — `texas-speed.com`
- **Segments:** LS / LT engine platform — Camaro 5th/6th gen, Corvette
  C5–C8, F-body, GM trucks, swaps. Cams, heads, long-blocks.
- **Why:** LS swap + GM enthusiast segment is the largest performance
  community currently underserved by your catalog (Summit/Jegs carry these
  but at MSRP and without spec data).
- **Notes:** Custom platform. Sitemap exists. Tier-0/1.

### Tick Performance — `tickperformance.com`
- **Segments:** LS/LT drivetrain (clutches, hydraulics, shifters, axles).
  Complement to Texas Speed.
- **Why:** Drivetrain is a separate buy from engine — both retailers
  needed to cover full LS build lists.
- **Notes:** Custom cart. Tier-0 likely.

### ~~Bimmerworld — `bimmerworld.com`~~ — **shipped 2026-04-19**
- **Adapter:** `tier0_http/bimmerworld.py` (Tier-0 plain HTTP — no Cloudflare).
- **Notes file:** `site_problem_notes/bimmerworld.md`.
- NetSuite SuiteCommerce. JSON-LD is built client-side; parser pulls data
  from hidden DOM IDs (`#productName` / `#productDescription` /
  `#priceDisplay`) plus inline-script `var brand=` / `var itemid=` regexes.
  ~34K product URLs in `/sitemap.xml` (single flat urlset).

### Hondata — `hondata.com`
- **Segments:** Honda K-series, L15 turbo (Civic Si/Type R, FK8, FL5),
  ECU tuning hardware (FlashPro, s300).
- **Why:** Direct-only product line. Reference pricing for Honda tuning
  hardware.
- **Notes:** Small catalog, simple site. Tier-0.

### KTuner — `ktuner.com`
- **Segments:** Honda overlap with Hondata (FK8, FL5, Si). Competing
  flash-tuning hardware.
- **Why:** Two-vendor comparison for Honda tuning hardware is the actual
  buyer decision; need both to surface it.
- **Notes:** Tier-0.

### AWE Tuning — `awe-tuning.com`
- **Segments:** Exhaust + intake across VAG, BMW, Porsche, Toyota Supra,
  Honda Civic Type R, Ford Mustang. Direct-to-consumer.
- **Why:** Many AWE SKUs are direct-only or pre-launch direct-only. Their
  catalog overlaps every chassis you cover, so it's force-multiplier
  pricing data.
- **Notes:** Modern Shopify-style. Tier-0/1.

### Mackin Industries — `mackinindustries.com`
- **Segments:** Volk Racing / Rays / Gram Lights wheels. Authorized US
  distributor — reference pricing for high-end JDM wheels.
- **Why:** Wheel pricing on enthusiast forged/cast Volk lineup. Pairs with
  Tire Rack on the wheel-tire dimension.
- **Notes:** Custom catalog, fitment-driven. Tier-1 likely.

### Integrated Engineering (IE) — `performancebyie.com`
- **Segments:** VAG turbo upgrades, internals (rods, cams), fueling.
  Complements 034 and APR in the VAG cluster.
- **Why:** Fills the "built bottom-end + big-turbo" tier of VAG that 034
  and APR don't fully cover.
- **Notes:** Custom platform / Shopify-ish. Tier-0.

---

## Priority 3 — niche but high-signal

### APR LLC — `goapr.com`
- **Segments:** VAG software + hardware (intake, intercooler, downpipe).
  Largest VAG software vendor.
- **Why:** Software pricing is reference-only (no arbitrage), but the
  hardware catalog is widely cross-shopped with IE/034.
- **Notes:** Custom platform. Tier-1.

### GMG Racing — `gmgracing.com`
- **Segments:** Porsche club racing, Audi RS track. Boutique.
- **Why:** Specialty Porsche SKUs (cages, race seats, GT3-spec parts) not
  carried by FCP/ECS.

### RSS Manufacturing — `rss-mfg.com`
- **Segments:** Porsche suspension (monoball kits, end links). Direct.
- **Why:** Reference pricing for Porsche suspension upgrade segment.

### Suncoast Porsche Parts — `suncoastparts.com`
- **Segments:** Porsche OEM + light performance. Complements FCP.
- **Why:** Often beats FCP on Porsche-specific OEM SKUs.

### Driveshaft Shop — `driveshaftshop.com`
- **Segments:** Axles, driveshafts across all high-HP platforms (GTR, Evo,
  STI, R35, F-body, Mk7/Mk8 GTI/R).
- **Why:** Drivetrain upgrade is a chokepoint at >500whp builds — needed
  for any aggressive build list to be priceable.

### Sheepey Built — `sheepeybuilt.com`
- **Segments:** Honda K/L turbo manifolds, custom turbo kits.
- **Why:** Honda high-HP turbo segment.

### Wheels Boutique — `wheelsboutique.com`
- **Segments:** High-end forged wheels (HRE, Vossen, ANRKY, Forgeline).
- **Why:** Premium wheel pricing tier above Mackin.

### HKS USA — `hksusa.com`
- **Segments:** JDM hard parts (Hipermax suspension, Kansai exhausts,
  turbo upgrades) across Toyota/Nissan/Honda/Subaru.
- **Why:** Reference pricing for HKS-branded SKUs across multiple chassis.

### Tomei USA — `tomeiusa.com`
- **Segments:** JDM internals (camshafts, valvetrain, oil pumps) for SR,
  RB, EJ, 4G63, 2JZ.
- **Why:** Engine-build pricing for JDM platforms.

### GReddy / Trust — `greddy.com`
- **Segments:** JDM bolt-ons (intercoolers, intakes, oil coolers) across
  Toyota/Honda/Nissan/Subaru.

---

## Coverage matrix — target state vs. today

Goal: 3+ comparable retailers per major platform.

| Platform                    | Target retailers                              | Today |
| --------------------------- | --------------------------------------------- | ----- |
| BMW M / track               | ECS, Turner, IND, Bimmerworld, FCP            | 3     |
| VAG / Porsche               | ECS, 034, IE, APR, FCP, GMG                   | 3     |
| Honda / Acura               | Evasive, Hondata, KTuner, Sheepey             | 1     |
| Nissan Z / GTR              | Z1, AMS, AWE                                  | **0** |
| Nissan S-chassis (drift)    | Enjuku, Z1                                    | **0** |
| Subaru / Mitsubishi         | MAP, Cobb, Vivid                              | 1.5   |
| GR Supra A90 / Mk4 Supra    | a90shop, AMS, Evasive                         | 2     |
| LS / LT domestic            | Texas Speed, Tick, Summit                     | 1     |
| Ford ST / RS / Mustang      | Cobb, AWE, Summit                             | 0.5   |
| Wheels / Tires              | Tire Rack, Mackin, Wheels Boutique            | **0** |
| Drivetrain (high-HP)        | Driveshaft Shop, Sheepey                      | 0     |

---

## Implementation batches

A reasonable order to attack the backlog, optimized for impact-per-batch:

1. **Batch 1 (Nissan + Euro depth):** ECS, Z1, AMS, Cobb, Tire Rack — fixes
   Nissan from zero and doubles Euro depth in one pass.
2. **Batch 2 (BMW + VAG completion):** Turner, Bimmerworld, IE, APR — fully
   saturates the two strongest existing chassis clusters.
3. **Batch 3 (domestic + Honda):** Texas Speed, Tick, Hondata, KTuner — opens
   LS segment and gives Honda tuning hardware reference pricing.
4. **Batch 4 (drift + JDM hard parts):** Enjuku, HKS, Tomei, GReddy.
5. **Batch 5 (wheels + drivetrain niche):** Mackin, Wheels Boutique,
   Driveshaft Shop, Sheepey.

Realistic end-state: **~30–35 retailers** total, every major chassis platform
with ≥3 comparable sources.
