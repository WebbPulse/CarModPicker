# Retailer adapter backlog

## Phase 1 — LANDED (2026-04-20)

10 adapters shipped. Total adapter count: **65 → 75**. All Tier 0 on the
backend; **flagged T4 (unverified) in the admin UI** via
`UNVERIFIED_ADAPTERS` in `frontend/src/pages/admin/CrawlerAdmin.tsx` until
each passes a live smoke test. Delete the adapter's key from that set once
it's validated.

| Retailer              | Adapter key           | Host                          | Tier | Platform         | Default category |
| --------------------- | --------------------- | ----------------------------- | ---- | ---------------- | ---------------- |
| Burger Motorsports    | `burgermotorsports`   | burgertuning.com              | 0    | Shopify (PG)     | engine           |
| CorkSport             | `corksport`           | corksport.com                 | 0    | CS-Cart          | engine           |
| ETS                   | `ets`                 | extremeturbosystems.com       | 0    | Shopify (PG)     | engine           |
| GrimmSpeed            | `grimmspeed`          | grimmspeed.com                | 0    | Shopify          | chassis          |
| Mishimoto             | `mishimoto`           | mishimoto.com                 | 0    | Magento 2 (Hyva) | cooling          |
| Modern Muscle Xtreme  | `modernmusclextreme`  | modernmusclextreme.com        | 0    | AbleCommerce     | engine           |
| Radium Engineering    | `radium`              | radiumauto.com                | 0    | Shopify          | engine           |
| Seibon Carbon         | `seiboncarbon`        | seiboncarbon.com              | 0    | Magento 2        | aero             |
| Skunk2                | `skunk2`              | skunk2.com                    | 0    | Magento 2        | engine           |
| Verus Engineering     | `verusengineering`    | verus-engineering.com         | 0    | Odoo             | aero             |

Platform firsts in Phase 1: **CS-Cart, AbleCommerce, Odoo** (previously:
Shopify, BigCommerce, Magento 2, WooCommerce, custom).

### Phase 1 caveats to remember during smoke-test

- **skunk2** — `robots.txt` is `Disallow: /` for all UAs; the polite runner
  will skip active crawls. Adapter is primarily for Chrome-extension capture
  + archive rescrape. Smoke-test via extension ingest, not a runner crawl.
- **burgermotorsports** — live host is `burgertuning.com`;
  `burger-motorsports.com` is NXDOMAIN. Host map covers both for archive
  replay.
- **ets** — live host is `extremeturbosystems.com`; `ets-racing.com` is an
  unrelated business with an expired cert. Do not add it to the host map.
- **modernmusclextreme** — AbleCommerce / ASP.NET; **Schema.org microdata,
  not JSON-LD**. Discovery walks the HTML sitemap at `/sitemap.aspx`
  (~460 KB, 1,297 products). Related-product microdata blocks are
  guarded against.
- **verusengineering** — Odoo; **microdata + `#product_detail` JSON blob**,
  no JSON-LD `Product` (only `VideoObject`). SKU pulled from
  `data-product-tracking-info`.
- **corksport** — CS-Cart; **JSON-LD has no `brand` field** on any page.
  Brand resolution relies on title heuristic + custom
  `_strip_leading_non_brand_tokens` that peels off `mazda`/`mazdaspeed`/etc.
  before re-running the heuristic.
- **radium** — JSON-LD `sku` is literal `"NULL"` on every PDP; `price` is
  `$0.00` (MAP enforcement). Both are stripped. Real SKUs only exist
  per-variant, so top-level `part_number` is intentionally `None`;
  cross-retailer dedupe falls back to `retailer + url`.
- **mishimoto** — Hyva-theme quirk: category pages emit a full `Product`
  JSON-LD for the first item. Adapter guards via URL-match check +
  depth-1 deny list.
- **ets / burgermotorsports** — Shopify `@type: ProductGroup` with
  `hasVariant[]`; shared `extract_json_ld_product` doesn't match
  `ProductGroup`, so each adapter has its own ProductGroup-aware extractor.
  ETS child sitemap URLs must be fetched verbatim including the
  `?from=&to=` query — stripping it returns HTTP 400.
  See [`VARIANTS.md`](./VARIANTS.md) for cross-adapter notes on
  multi-permutation product pages and the design options we've sketched
  for lifting the "one Part per URL" constraint.

### Smoke-test checklist (per adapter)

For each Phase 1 adapter, before removing from `UNVERIFIED_ADAPTERS`:

1. `python -m app.crawlers --adapter <key> --limit 3` — runs end-to-end
   against the live site.
2. Verify the 3 parts created in the DB have: sensible `name`, non-empty
   `description`, correct `part_manufacturer`, a plausible `part_number`
   (except `radium` — null is expected), a non-zero `price_cents`
   (except `radium` — MAP), and at least one image.
3. For `skunk2` specifically: capture a page via the Chrome extension
   instead of running the crawler — active crawl will be rejected by the
   polite robots.txt check.
4. Spot-check brand canonicalization: pull 1–2 parts from the DB and
   confirm the `part_manufacturer` isn't set to a car make
   ("Honda"/"Subaru"/etc.) or a blank string.

---

## Phase 2 — prioritized todo list

Batches are sized ~10 for parallel-subagent execution. Within each batch,
adapters are ordered by confidence (easiest / most-standard platform
first). A next-session pickup should start at Batch 2A.

### Batch 2A — Tier-0-likely, house-brand (high confidence)

Standard Shopify / Magento / WooCommerce, direct-to-consumer, known
single-brand catalogs. These should slot in cleanly using the Phase 1
patterns as templates.

| # | Retailer | Fills | Likely platform | Closest Phase 1 template |
|---|---|---|---|---|
| 1 | **Perrin Performance** | Subaru/86/BRZ — still open in GR86 row | Shopify | `grimmspeed` |
| 2 | **Delicious Tuning** | Subaru/86 tuning | Shopify | `grimmspeed` |
| 3 | **OpenFlash Performance (OFT)** | Subaru/86/Miata tuning hardware | Shopify | `grimmspeed` |
| 4 | **Deatschwerks** | Fuel injectors/pumps — fuel vertical | Shopify | `radium` |
| 5 | **Injector Dynamics** | Fuel injectors — fuel vertical | Shopify or custom | `radium` |
| 6 | **CSF Radiators** | Track cooling — cooling vertical | Shopify | `mishimoto` |
| 7 | **Injen Technology** | Intakes — cooling/intake vertical | Shopify | `mishimoto` |
| 8 | **Mountain Pass Performance (MPP)** | Tesla performance — Tesla platform | Shopify | `verusengineering` |
| 9 | **Unplugged Performance** | Tesla performance — Tesla platform | Shopify | `grimmspeed` |
| 10 | **Dinan** | BMW — BMW F/G row | Shopify or BigCommerce | `burgermotorsports` |

### Batch 2B — Tier-0-likely, multi-brand resellers

Mix of resell and house brands. Follow `ind` / `corksport` /
`modernmusclextreme` for brand-pass-through handling.

| # | Retailer | Fills | Notes |
|---|---|---|---|
| 11 | **aFe Power** | Intake/exhaust — cooling/intake vertical | House-brand only; large catalog |
| 12 | **FTP Motorsports** | BMW F-chassis charge pipes/intakes | House-brand |
| 13 | **Racing Beat** | RX-7/RX-8 — Mazda beyond Miata | House-brand |
| 14 | **Blox Racing** | Honda/JDM — older Honda vertical | House-brand |
| 15 | **Karcepts** | Honda suspension/geometry | House-brand |
| 16 | **English Racing** | Evo/DSM specialist | Mix |
| 17 | **Road Race Engineering (RRE)** | Evo/DSM | Mix |
| 18 | **Buschur Racing** | Evo/DSM | Mix |
| 19 | **JLT Performance** | Intakes/oil separators cross-platform | House-brand |
| 20 | **Hennessey Performance** | Mustang/Raptor/Mopar high-HP | House-brand |

### Batch 2C — verticals still open

Pickier: some are ECU / track-supply distributors with odd platforms.
Recon each before assigning a template.

| # | Retailer | Fills |
|---|---|---|
| 21 | **Haltech Engine Management** | ECU standalone |
| 22 | **AEM Performance Electronics** | ECU/fuel cross-platform |
| 23 | **EcuTek** | ECU tuning hardware (Subaru/Nissan/Toyota) |
| 24 | **Link Engine Management** | ECU standalone |
| 25 | **APR Performance (US)** | Track aero (not the APR tuning shop) |
| 26 | **Voltex USA** | Track aero |
| 27 | **OG Racing** | Seats/harnesses/helmets — safety vertical |
| 28 | **I/O Port Racing Supplies** | Seats/safety — West Coast |
| 29 | **Racer Wholesale** | Seats/harnesses |
| 30 | **Tein USA** | Coilovers — suspension upper tier |
| 31 | **Stance Suspension USA** | Coilovers |
| 32 | **StopTech** | BBK direct |
| 33 | **Wilwood Disc Brakes** | BBK direct |
| 34 | **Rotiform Wheels** | Wheels consumer |

### Batch 2D — recon first, may not be scrapable

Flagged in the original "Worth checking" section. Some may be
wholesale-only / Cloudflare-heavy / JDM-weird. Do a probe pass before
assigning adapter work.

| # | Retailer | Risk |
|---|---|---|
| 35 | **Nengun Performance** | JDM broker; custom site, likely Tier 2 |
| 36 | **RHDJapan** | JDM broker; custom site, likely Tier 2 |
| 37 | **Rays USA / Volk direct** | Historically wholesale-only (verify direct sales exist) |
| 38 | **Work Wheels USA** | Likely wholesale-only |
| 39 | **SSR Wheels USA** | Likely wholesale-only |
| 40 | **BBS USA** | Likely wholesale-only |
| 41 | **Öhlins USA** | Often wholesale-only |
| 42 | **Brembo** | Wholesale-only; may need reseller instead |
| 43 | **Northridge4x4** | Off-road (audience fit decision) |
| 44 | **American Expedition Vehicles (AEV)** | Off-road/overland (audience fit decision) |

---

## Usage notes for the next agent

- **Brief template that worked well for Phase 1**: point each subagent at
  `adapters/base.py`, `crawlers/parsing.py`, `crawlers/README.md`, 2 closest
  Phase 1 / existing analogs, and *require* live recon
  (robots.txt → sitemap → 2–3 product pages) before writing code.
- **Never let subagents touch `adapters/__init__.py`** — parallel writes
  conflict. The parent stitches imports + `ADAPTER_REGISTRY` + host map
  centrally after all adapters land.
- **Always add new Phase N adapters to `UNVERIFIED_ADAPTERS` in
  `CrawlerAdmin.tsx`** at registration time. The smoke-test workflow
  depends on that flag.
- **Expect `robots.txt: Disallow: /`** on some sites (skunk2 was one).
  Document the active-crawl-skipped status in the adapter docstring and
  keep the parser for extension/rescrape paths.
- **Expect new platform firsts.** Phase 1 added three. If the recon turns
  up something exotic (e.g. Shopify Plus checkout extensions,
  headless commerce with client-rendered product data), note it in the
  adapter docstring so future work on the same platform can reuse the
  pattern.
