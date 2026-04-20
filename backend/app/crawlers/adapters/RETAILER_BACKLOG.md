# Retailer Adapter Backlog

Prioritized list of retailers to add to grow enthusiast price-aggregation
coverage. Ordered by impact on platform/segment coverage, not by ease of
implementation. Tier-0/1/2 in this doc refers to **importance**, not the
crawler-fetcher tier (`tier0_http` / `tier1_tls` / `tier2_browser`) used in
the adapter directory layout.

For each entry: domain, what segments it unlocks, why it matters, and any
known scraping notes (platform, anti-bot posture) to inform fetcher-tier
choice when the adapter is built.

The previous backlog (ECS/Turner/Z1/AMS/Cobb/Tire Rack and the Priority 2/3
list) shipped through 2026-04-19. This v2 backlog targets the gaps that
surfaced after the original coverage matrix was satisfied: whole chassis
with zero native coverage (Subaru hubs, Miata, Mustang aftermarket) and
verticals that cross every platform (brakes, coilovers, forged wheels,
forced induction).

---

## Priority 1 — whole-chassis / whole-vertical holes

### RallySport Direct — `rallysportdirect.com`
- **Segments:** Subaru WRX/STI (all generations), FXT, BRZ overflow.
- **Why:** THE Subaru-native retailer. MAP/Cobb/Vivid all carry Subaru, but
  none of them are Subaru-first — without RSD, the Subaru community's
  actual shopping destination isn't in the index. Same-magnitude gap as
  Z1 was for Nissan before batch 1.
- **Notes:** BigCommerce Stencil historically. Expect JSON-LD Product and
  a flat sitemap. Cloudflare posture unknown — start Tier-0, promote to
  Tier-1 if `cf-mitigated: challenge` appears.

### Subispeed — `subispeed.com`
- **Segments:** Subaru WRX/STI + Toyota GR86 / Subaru BRZ. Anchors the
  86/BRZ/GR86 chassis which currently has no dedicated retailer.
- **Why:** Fills Subaru depth alongside RSD and, more importantly, is the
  only way to get real 86/BRZ/GR86 price signal — that chassis is a real
  enthusiast segment (OpenFlash, GrimmSpeed, Perrin SKUs) that the
  current adapter set can't price.
- **Notes:** BigCommerce. Tier-0 likely.

### American Muscle — `americanmuscle.com`
- **Segments:** Mustang S197/S550/S650, plus F-150 performance overlap.
- **Why:** Largest Mustang aftermarket retailer by volume. Cobb and AWE
  cover Mustang for specific SKUs, but without AM, Mustang build lists
  aren't priceable end-to-end (suspension, exhaust, cosmetics, drivetrain
  all live here). Mustang is a core enthusiast chassis still at 0.5
  retailers of real coverage.
- **Notes:** Custom platform with heavy anti-bot. Almost certainly Tier-2
  browser; do not attempt Tier-0 first. Vehicle-year URL structure is
  deep — discovery should walk category/brand pages, not the year/model
  selector.

### Flyin' Miata — `flyinmiata.com`
- **Segments:** NA/NB/NC/ND Mazda MX-5 Miata. The V8 swap side of the
  catalog overlaps LS as well.
- **Why:** Miata is a real enthusiast chassis (autocross, HPDE, V8 swap,
  turbo builds) with **zero current coverage**. Flyin' Miata is
  effectively the only serious catalog for the platform — Good-Win covers
  ND only and doesn't make the problem go away.
- **Notes:** Custom platform / older cart. Probably Tier-0. Small-ish
  catalog (<5k SKUs) so discovery is cheap.

### Essex Parts Services — `essexparts.com`
- **Segments:** AP Racing brake kits (Radi-CAL, Competition), pads,
  rotors, fluids. Cross-platform — BMW, Porsche, Corvette, GR Supra,
  Mustang GT350/GT500, Civic Type R, GR Corolla.
- **Why:** Brakes are an entire vertical currently at zero. The track /
  HPDE community buys AP Racing almost exclusively for serious kits, and
  Essex is the authorized US distributor — reference pricing, not
  arbitrage. Pairs with Girodisc below for the full brake picture.
- **Notes:** Custom platform. Tier-0 or Tier-1. Fitment is by vehicle
  application, not chassis selector, so sitemap-based discovery is fine.

---

## Priority 2 — chassis depth + direct-mfr references

### IAG Performance — `iagperformance.com`
- **Segments:** Subaru built long-blocks, short-blocks, heads, oil system.
- **Why:** $8k–$20k built-engine SKUs — the same "high-ticket reference
  pricing" argument that justified AMS. Subaru built-engine decisions are
  IAG vs. Cosworth vs. 2SX — IAG is the most commonly shopped.
- **Notes:** Custom / Shopify-ish. Tier-0.

### PRL Motorsports — `prlmotorsports.com`
- **Segments:** Honda Civic Si (10th/11th gen), Type R FK8/FL5, Accord
  2.0T. Intakes, intercoolers, charge pipes, downpipes.
- **Why:** Many PRL SKUs are direct-only. FK8/FL5 is the most active
  Honda enthusiast chassis right now and PRL owns the intake/IC tier.
- **Notes:** Shopify. Tier-0.

### 27WON Performance — `27won.com`
- **Segments:** Civic Si / Type R / Accord 2.0T overlap with PRL but
  different SKU mix (engine bay dress-up, intake manifolds, short shifters).
- **Why:** Two-vendor comparison on FK8/FL5 is the actual shopper decision
  (same pattern as Hondata vs. KTuner). PRL alone isn't enough.
- **Notes:** Shopify. Tier-0.

### Brian Tooley Racing (BTR) — `briantooleyracing.com`
- **Segments:** LS / LT / Gen-III HEMI cams, valvetrain, rockers,
  springs. Cross-platform (F-body, Corvette, trucks, swaps).
- **Why:** BTR is the reference price on LS valvetrain — Texas Speed
  competes on the same shelf and both need to be in the index for
  LS build-list prices to be credible.
- **Notes:** BigCommerce. Tier-0 likely.

### Apex Race Parts — `apexraceparts.com`
- **Segments:** BMW M + track-focused wheels across BMW/Porsche/Corvette/
  Civic Type R/GR Corolla. Also their own brake pads and track gear.
- **Why:** Apex is a direct manufacturer — their wheels are not resold
  elsewhere, so neither Tire Rack nor Mackin catches this pricing. Track
  community's default forged/flow-formed wheel.
- **Notes:** Shopify. Tier-0.

### Steeda — `steeda.com`
- **Segments:** Mustang S197/S550/S650, Focus ST/RS, F-150.
- **Why:** Steeda-branded SKUs (chassis braces, suspension, handling
  packages) are direct-only. American Muscle carries some but not the
  full catalog. Needed alongside AM for Mustang build-list completeness.
- **Notes:** Custom platform. Tier-0/1.

---

## Priority 3 — verticals and niche high-signal

### Girodisc — `girodisc.com`
- **Segments:** Two-piece rotors across BMW M, Porsche, Corvette, GT-R,
  Evo, STI, GR Supra, Civic Type R.
- **Why:** Direct manufacturer, reference rotor pricing for the
  semi-pro track segment. Pairs with Essex (AP Racing calipers/pads) to
  price a full track brake package.
- **Notes:** Small catalog, simple site. Tier-0.

### KW Suspensions USA — `kwsuspensions.com`
- **Segments:** Coilovers (V1/V2/V3/Clubsport/Variant 4) across every
  chassis you cover.
- **Why:** Coilover pricing is the largest single suspension line item on
  most build lists and currently has no direct-mfr source. KW is the most
  cross-shopped premium coilover brand.
- **Notes:** Custom platform with bot protection. Likely Tier-1.

### Fortune Auto — `fortuneauto-na.com`
- **Segments:** Coilovers (500/510/Gen8 Dreadnought/Muller) across BMW,
  Subaru, Honda, Nissan, GR Supra, Miata.
- **Why:** Mid-premium coilover tier — the actual buyer comparison for
  KW V2/V3 is Fortune Auto 500/510. Both are needed for the comparison
  to exist in the catalog.
- **Notes:** Custom/Shopify. Tier-0/1.

### BC Racing — `bcracingna.com`
- **Segments:** Budget-to-mid coilovers (BR, DS, ER, ZR). Broadest fitment
  catalog of any coilover brand.
- **Why:** Completes the coilover vertical at the entry tier. Almost
  every platform has a BC option — without it, the lowest price point in
  the suspension category is missing.
- **Notes:** Shopify likely. Tier-0.

### Titan7 — `titan7.com`
- **Segments:** Forged/flow-formed wheels, BMW / Porsche / Corvette /
  Civic Type R / GR Corolla / STI track fitments.
- **Why:** Direct-only manufacturer. Tire Rack does not list Titan7;
  Mackin covers Volks only. This is its own pricing island.
- **Notes:** Shopify. Tier-0.

### Forgeline — `forgeline.com`
- **Segments:** US-forged wheels, high-end track/street (C7/C8 Corvette,
  GT3, Viper, GT500, R35).
- **Why:** Domestic forged reference pricing ($3k–$8k sets). Complement
  to HRE and Mackin's JDM-forged coverage.
- **Notes:** Custom platform. Tier-1 possible.

### HRE Performance Wheels — `hrewheels.com`
- **Segments:** High-end forged wheels (Porsche, BMW, Corvette, McLaren,
  GT-R). $5k–$12k sets.
- **Why:** Reference pricing for top-tier forged — rarely discounted so
  direct is the right source. Catalog-only for most SKUs (quote-driven),
  handle like Wheels Boutique: list without price history.
- **Notes:** Custom platform. Tier-1/2.

### Fifteen52 — `fifteen52.com`
- **Segments:** Rally/ST/RS wheels (Focus RS, Fiesta ST, GR Corolla,
  Subaru, R35 GT-R Project 6GR variants).
- **Why:** Direct. Rally-style fitment and Ford ST/RS specificity don't
  get covered anywhere else.
- **Notes:** Shopify. Tier-0.

### Full-Race Motorsports — `full-race.com`
- **Segments:** Turbo manifolds, kits, and drop-in turbos for Honda K/L,
  Ford Ecoboost/Mustang, GM, and Mopar.
- **Why:** Forced-induction retailers are a vertical currently at zero.
  Full-Race anchors it — their manifold pricing is the reference for
  bottom-mount builds.
- **Notes:** Shopify-ish. Tier-0/1.

### ATP Turbo — `atpturbo.com`
- **Segments:** Garrett / Precision / BorgWarner turbo distribution plus
  full turbo kits for GTI, Mazdaspeed, Evo, STI, G35/370Z.
- **Why:** ATP is the de-facto distributor for Garrett aftermarket —
  matches the Essex-for-AP-Racing role on the turbo side. Pairs with
  Full-Race to cover turbo hardware end-to-end.
- **Notes:** Older custom cart. Tier-0/1.

### Katech — `katech.com`
- **Segments:** LT platform (C7/C8 Corvette, CT4/CT5-V Blackwing), LS
  race engines, GM forced induction.
- **Why:** Reference pricing for LT-specific internals and SC systems —
  Texas Speed's LS catalog does not fully extend into LT/C8.
- **Notes:** Custom. Tier-0.

### Lingenfelter Performance Engineering — `lingenfelter.com`
- **Segments:** LS/LT built engines and SC packages, Camaro/Corvette/
  Cadillac-V, Hellcat overlap.
- **Why:** $15k–$40k built-engine/SC references on the domestic side —
  same role as AMS plays for R35, IAG for Subaru. Needed to complete
  the GM built-engine price tier.
- **Notes:** Custom. Tier-0/1.

### Good-Win Racing — `good-win-racing.com`
- **Segments:** ND Miata primarily, with some NC overlap.
- **Why:** Second-vendor comparison for Miata alongside Flyin' Miata.
  ND-specific catalog differs enough that FM doesn't cover everything.
- **Notes:** Older custom cart. Tier-0.

### Hasport Performance — `hasport.com`
- **Segments:** Honda engine mounts for K-swaps, B-swaps, J-swaps across
  EG/EK/DC/EP chassis and cross-platform swaps.
- **Why:** Swap mounts are Hasport-or-nothing — direct-only, no
  cross-sell. Small catalog but unique SKUs with zero alternative
  pricing anywhere.
- **Notes:** Small simple site. Tier-0.

---

## Coverage matrix — target state vs. today

Goal: 3+ comparable retailers per major platform/vertical.

| Platform / Vertical           | Target retailers                                           | Today |
| ----------------------------- | ---------------------------------------------------------- | ----- |
| BMW M / track                 | ECS, Turner, IND, Bimmerworld, FCP, Apex                   | 5     |
| VAG / Porsche                 | ECS, 034, IE, APR, FCP, GMG, RSS, Suncoast, StudioRSR      | 9     |
| Honda / Acura                 | Evasive, Hondata, KTuner, Sheepey, PRL, 27WON, Hasport     | 4     |
| Nissan Z / GTR                | Z1, AMS, AWE                                               | 3     |
| Nissan S-chassis (drift)      | Enjuku, Z1                                                 | 2     |
| Subaru WRX/STI                | MAP, Cobb, Vivid, RSD, Subispeed, IAG                      | 3     |
| Toyota GR86 / Subaru BRZ      | Subispeed, (MAP/Cobb overlap)                              | **0** |
| GR Supra A90 / Mk4 Supra      | a90shop, AMS, Evasive                                      | 3     |
| Mazda MX-5 Miata (all gens)   | Flyin' Miata, Good-Win                                     | **0** |
| LS / LT domestic              | Texas Speed, Tick, Summit, BTR, Katech, Lingenfelter       | 3     |
| Ford Mustang / ST / RS        | Cobb, AWE, Summit, American Muscle, Steeda                 | 3     |
| Wheels — consumer             | Tire Rack, Mackin, Wheels Boutique                         | 3     |
| Wheels — forged direct        | Apex, Titan7, Forgeline, HRE, Fifteen52                    | **0** |
| Brakes — track                | Essex, Girodisc                                            | **0** |
| Coilovers — direct            | KW, Fortune Auto, BC Racing                                | **0** |
| Forced induction — direct     | Full-Race, ATP Turbo                                       | **0** |
| Drivetrain (high-HP)          | Driveshaft Shop, Sheepey                                   | 2     |

Bold "0" rows are the real holes this backlog is trying to fill.

---

## Implementation batches

Ordered for impact-per-batch, starting with the chassis gaps that can't be
papered over by existing adapters.

1. **Batch 1 (whole-chassis holes):** RallySport Direct, Subispeed,
   American Muscle, Flyin' Miata, Essex Parts — fixes Subaru depth,
   opens Mustang for real, adds Miata + BRZ/GR86 from zero, and opens
   the brakes vertical.
2. **Batch 2 (chassis depth + direct-mfr refs):** IAG, PRL, 27WON, BTR,
   Steeda, Apex Race Parts — adds second-vendor comparisons for the
   platforms batch 1 just opened and closes the FK8/FL5 Honda gap.
3. **Batch 3 (verticals):** Girodisc, KW, Fortune Auto, BC Racing,
   Titan7, Fifteen52 — full coilover tier + brake rotors + direct forged
   wheels. After this batch, "suspension + brakes + wheels" is no longer
   a forced hand-off to Tire Rack.
4. **Batch 4 (forced induction + high-end + niche):** Full-Race, ATP
   Turbo, Forgeline, HRE, Katech, Lingenfelter, Good-Win, Hasport — opens
   the turbo retailer vertical and rounds out built-engine reference
   pricing on GM + Miata + Honda swaps.

Realistic end-state after all batches: **~55 retailers**, every major
chassis platform with ≥3 comparable sources, and every cross-platform
vertical (brakes, coilovers, forged wheels, forced induction) with ≥2.
