# Variant splitting — implementation plan

Multi-product pages (one URL → N priced SKUs) are the largest catalog-accuracy
gap remaining. AWE Tuning, A90 Shop, ETS, MAPerformance, Burger Motorsports,
X-Ph, Cobbtuning, Vividracing, Roadsportsupply, Sheepeyrace all have
product pages where the user is choosing between 2–8 distinct configurations
(Track vs Touring vs Conversion Kit, Y-pipe option A vs B, oversize bore A
vs B, fan size 12-inch vs 14-inch, etc.) and we currently store one row.

`VARIANTS.md` documents the design space. This plan picks the cheapest
incremental change that produces a measurable accuracy win.

## Status quo

The infrastructure for variant splitting already exists in two places:

* `RetailerCrawlerAdapter.extract_variants(html, url, base_payload)` in
  `adapters/base.py` returns `[]` by default. Adapters override to emit
  per-variant `ScrapedPayload`s with synthetic `?variant=<slug>` URLs.
* `archive_rescrape.py::rescrape_crawled_page_from_archive` and
  `runner.py` already iterate `extract_variants`, calling `ingest_payload`
  per variant. Variant ingest failures don't roll back the base part —
  the contract is fail-soft.

**One adapter overrides today: `a90shop.py`** via `_a90_extract_variant_payloads`.
Its rules (delta-or-categorical filter, ≤6 variants per page, slug-stable
`<base>?variant=<slug>` URLs, derived `<base_pn>-<slug>` SKUs) are the
template.

The reason variant rows haven't shown up in the live DB: existing
crawls happened **before** the a90shop variant code landed, and no bulk
rescrape has been run since. Verified locally — running
`SheepeyAdapter().extract_variants` on archived HTML emits 2 variants per
multi-axis page; the DB has 0 rows with `?variant=` query strings.

## Plan

### Step 1 — Bulk rescrape a90shop archives (no code change)

Easiest first move. Verifies the variant-ingest path end-to-end on a
production data set and produces a measurable improvement immediately.

```bash
# In backend/, with .env loaded:
psql -At -c "select c.url
             from crawled_pages c
             where c.url ilike '%a90shop.com%'
               and (c.html_s3_key is not null or c.html_local_path is not null)" \
  | xargs -n1 -P4 python -m app.crawlers --rescrape-url
```

After: count `part_listings` with `?variant=` query strings. If the count
matches `extract_variants` output for those archives (~20–40% of pages
emit at least 1 variant), the path works.

### Step 2 — Port the a90shop variant pattern to AWE Tuning

AWE is the highest-impact next adapter (252 base rows, ~7 variants each
on average → ~1500 additional Part rows). Pattern:

1. Reuse `_extract_shopify_meta_product` (already in `awetuning.py`) to
   pull the `meta.product.variants` array.
2. For each variant, decide whether it's "different enough":
   * Different `option1` value (e.g. "Track Edition" vs "Touring Edition")
     → always emit.
   * Same `option1` but different `option2`/`option3` (color, finish) →
     suppress when the price delta is ≤2% of base.
   * "Conversion Kit", "Valve sim", "Remote" — categorical, always emit.
3. Per variant: build `<base_url>?variant=<slug>` (slug from
   `public_title`), emit `ScrapedPayload` with `part_number=variant.sku`,
   `price_cents=variant.price`, `name=base.name + " (" + public_title + ")"`.
4. Cap at 12 variants/page (defensive — AWE ships up to 8 in practice).

The `_a90_extract_variant_payloads` shape (`_slugify_variant`,
`_build_variant_payload`) lifts cleanly. Approximate diff: +120 lines in
`awetuning.py`, +1 unit test fixture.

### Step 3 — Generalize: shared `shopify_variant_split` helper

After AWE, the same code wants to run on every Shopify adapter where
JSON-LD `Product` is the parent and the page has a `meta.product` blob
with `variants[]`. Candidates: `corksport`, `delicioustuning`, `englishracing`,
`flyinmiata`, `grimmspeed`, `ie`, `seibon`, `subispeed`, `wheelsboutique`,
... ~30 adapters in `tier0_http/`.

Lift `_a90_extract_variant_payloads`'s logic (minus the Wix-specific
HTML scrape) into `parsing.py` as `extract_shopify_variants(meta_product, base_payload)`.
Each Shopify adapter's `extract_variants` becomes a 5-line shim.

Don't do this until step 2 lands and we have signal on what AWE's
variant rules vs a90shop's actually share.

### Step 4 — Magento-grouped (Texas Speed pistons)

Different platform, different shape — `ProductGroup` JSON-LD with
`hasVariant[]` directly in the parent. Lift the existing per-adapter
helpers (`_extract_product_group_from_json_ld` in `maperformance.py`,
`ets.py`, `burgermotorsports.py`, `texasspeed.py`) into
`parsing.py::extract_product_group_variants`. Same downstream shape —
emit `ScrapedPayload`s, hand to `ingest_payload`.

### Step 5 — Wix-non-a90 + BigCommerce variants

X-Ph (BigCommerce Stencil) embeds variants in `var BCData = {...}` —
similar JSON, different anchor. Wix retailers other than a90shop
(checking the registry: there aren't many) follow a90shop's exact
pattern. Each is a per-adapter port of the relevant extractor.

## What NOT to change

* **Schema.** The `parts` / `part_listings` / `crawled_pages` tables
  are sufficient. Each variant is a separate Part row with a synthetic
  `?variant=...` URL, dedupe-keyed via `parts.canonical_part_id`. No
  migration needed.
* **Runner contract.** The existing `parse_product_page` returns the
  base payload, `extract_variants` adds extras — both already wired in
  `archive_rescrape.py:213-238` and `runner.py`. No change needed there.
* **Chrome extension.** The extension only POSTs single ScrapedPayloads
  from one product page at a time; it doesn't need to know about
  variants — the catalog crawler is the source of truth.

## Validation

After each step:

1. Spot-check by opening one rescraped product URL in the local UI;
   variant rows should show up as separate parts with distinct prices.
2. SQL: `SELECT pl.product_url, COUNT(*) FROM part_listings pl ... WHERE
   pl.product_url ~ '\\?variant='` — should be non-zero for the rescraped
   retailer.
3. Variant rows should land with `source='archive_rescrape'` and a
   non-null `canonical_part_id` linking back to the base part.

## Estimated effort

* Step 1: 1 hour (run + verify).
* Step 2 (AWE): 4 hours.
* Step 3 (shared helper): 6 hours.
* Step 4 (ProductGroup): 4 hours.
* Step 5 (per-adapter ports as needed): 1–2 hours each, ~10 adapters
  realistic before diminishing returns.

Total: 2–3 working days for steps 1–4. Step 5 can be parallelized across
agents (one adapter per task).
