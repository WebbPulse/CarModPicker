# Variants and multi-permutation product pages

Design notes for handling product pages that carry more than one SKU —
pistons in multiple bore sizes, brake pads in multiple compounds, wheels
in multiple offsets, etc. This is a known gap; the notes below describe
what each adapter does today, where the seams are, and what to consider
before expanding the model.

> Status: the crawler is designed around **one Part per product URL**.
> The data model doesn't represent variants as first-class rows yet.
> Everything below is about how each adapter copes with that constraint
> and what changes would look like if we lifted it.

---

## 1. Vocabulary

- **Variant** — one purchasable SKU. E.g. "UEM 3540HCA.5MM — .50mm
  oversize".
- **Parent / product group / configurable product** — the listing that
  shows the picker and points at N variants. E.g. "UEM Silv-O-Lite
  Piston" (parent) with four oversizes (variants).
- **Variant axis** — the dimension the variants vary on. Pistons: bore
  oversize. Brake pads: compound. Wheels: offset/bolt pattern/finish.
- **Variant URL** — a URL that deep-links into a specific variant.
  Platforms differ wildly: some give every variant its own canonical
  URL, some use a query string (`?variant=123`), some only expose the
  picker on the parent URL with no deep-link at all.

## 2. How platforms expose variants

| Platform | Variant schema on the PDP | Variant URLs? |
| --- | --- | --- |
| Shopify (plain theme) | `@type: Product` with the **first** variant's fields at top level; full variant list in `/products/<slug>.js` | `?variant=<id>` query string |
| Shopify (SEO apps — MAP, ETS, BMS) | `@type: ProductGroup` with `hasVariant: [Product, ...]` | `?variant=<id>` query string |
| Magento 2 (configurable) | `@type: Product` on the parent URL; children served via JSON embedded in Alpine/Knockout blocks | Usually parent-only; some themes (e.g. Hyva on Texas Speed) also give each variant a distinct slug |
| Magento 2 (grouped) | `@type: ProductGroup` on the parent URL **with full fields of its own** (Texas Speed's piston families — the case that prompted this doc) | Each variant has its own slug |
| WooCommerce (variable product) | `@type: ProductGroup` with `hasVariant`, or a `ProductModel` / raw `variations` array in a data-attr | Usually `?attribute_pa_size=...` query string |
| BigCommerce | `@type: Product`; variants in `var BCData = {...}` | Query string |
| Custom / CS-Cart / Odoo / AbleCommerce | Highly variable; check per-site | Site-specific |

`@type: ProductGroup` is schema.org's canonical "parent with variants"
type. `hasVariant[]` contains the children, `variesBy` names the axis.
The shared `extract_json_ld_product` only accepts `Product`; adapters
that hit `ProductGroup` pages need their own extractor (see §4).

## 3. How adapters currently cope

The honest summary: **every adapter produces exactly one `ScrapedPayload`
per URL**, and each adapter has chosen a rule for which SKU "wins" when
the page actually describes several. The rules:

| Adapter | URL shape on the PDP | Strategy | What's lost |
| --- | --- | --- | --- |
| `maperformance`, `ets`, `burgermotorsports` | Parent URL, `ProductGroup` JSON-LD | Pull `name/brand/description` from the group, `sku/price/image` from `hasVariant[0]`. First variant "wins." | All other variants. Price sits at the floor of the range. |
| `texasspeed` | Parent URL, sometimes `Product`, sometimes `ProductGroup` (piston families) | Prefer JSON-LD `Product`; fall back to ProductGroup parent fields (they're complete on this site, so no descent into variants). | Per-variant SKU/price. Variant URLs themselves crawl separately as `Product` pages. |
| `radium` | Parent URL, `Product` JSON-LD with `sku: "NULL"` and `price: $0` (MAP) | Null out both. Cross-retailer dedupe falls back to `retailer + url`. | Everything — top-level `part_number` is `None` by design. |
| Most Shopify adapters (e.g. `ie`, `corksport`, `grimmspeed`) | Parent URL, `Product` JSON-LD with variant[0] fields already flattened | Take the top-level `sku`/`price`/`image` as-is. | Other variants — silently. |
| `summitracing`, `jegs` (URL-embeds MPN) | Per-variant URL (each variant is its own page with its own JSON-LD) | Parse as a plain `Product`. | Nothing at the page level — but the "parent" concept is gone, so related variants aren't linked. |

Two distinct failure modes fall out of this:

- **Invisible-variant bias.** When the parent URL has every variant
  behind a picker and no per-variant URL, we silently pick one
  (usually the cheapest/first). The DB row looks fine; it just
  represents one of N SKUs.
- **Parallel-row drift.** When each variant has its own URL and we
  scrape all of them, we get N Part rows for what a human would
  consider one family. They share a name prefix and a manufacturer
  but have no explicit relationship.

## 4. Shared code — what exists, what doesn't

- `parsing.py::extract_json_ld_product` — URL-aware `Product` extractor.
  **Does not** accept `ProductGroup`. Adapters that need `ProductGroup`
  currently each ship their own copy of `_extract_product_group_from_json_ld`
  + `_first_variant` (see `maperformance.py`, `ets.py`,
  `burgermotorsports.py`, `texasspeed.py`).
- `parsing.py::scraped_payload_from_json_ld` — works on any dict with
  the standard keys (`name`, `sku`, `mpn`, `brand`, `description`,
  `image`, `offers`). Handles `AggregateOffer` via `lowPrice`. Safe to
  feed a `ProductGroup` top-level dict directly when the group's own
  fields are complete.
- **No `ScrapedVariant` type.** `ScrapedPayload` has no slot for "and
  here are the other N SKUs."

The duplication is tracked in `RETAILER_BACKLOG.md` (Phase 1 caveats
for `ets / burgermotorsports`). The first real cleanup is probably to
lift the ProductGroup extractor into `parsing.py` once a fourth or
fifth adapter needs it. Until then, the per-adapter copy is load-bearing
documentation of the site's exact shape.

## 5. When it actually matters (triage)

Not every variant axis is worth modelling. Three questions to ask
before treating variants as distinct products:

1. **Do the variants have different MPNs?** If yes, they're
   functionally different parts — cross-retailer dedupe and "what
   exact SKU fits my car" both break under a single row. Pistons with
   oversizes, brake pads with compounds, wastegates with spring rates
   — all yes. Wheels in different finishes, shirts in different sizes
   — usually no.
2. **Do the variants have different prices?** Wide price ranges hint
   at functionally distinct products (a 17" wheel is not a 19" wheel).
   A $2 range across sizes is probably cosmetic.
3. **Does fitment differ across variants?** Offset/bolt-pattern
   variants on wheels are effectively different parts because they fit
   different cars. Color variants on the same wheel are not.

If all three are "no", current parent-only behavior is fine. The
problem matters where answers diverge — most acutely for engine
internals and suspension hardware.

## 6. Future directions (options, not plan)

Sketches for expanding the model, roughly from least to most invasive.
None of these are committed work; the intent is that when variants
become a blocker, the next hand picks from this list rather than
re-deriving them.

### Option A — Keep parent-only, document what's lost

Status quo. Every adapter picks one variant. Document the rule per
adapter; when users report "wrong price / missing SKU", point at the
axis.

- **Pro:** zero data-model or schema work; every adapter already does
  this.
- **Con:** users can't shop a specific oversize without leaving the
  app; price drift is invisible.

### Option B — One Part row per variant URL (where variant URLs exist)

For sites like Texas Speed where every variant has its own slug,
crawl each one and emit separate `ScrapedPayload`s. Already happens
accidentally (the sitemap includes them); the current parent-page
handling just means we *also* emit the parent as one more row.

- **Pro:** cross-retailer dedupe on `mpn` starts working per variant.
  No data-model change — these are just more Part rows.
- **Con:** parent/variant relationship still isn't explicit; the
  parent row becomes redundant/confusing. Needs either a "skip
  parents" rule or a way to mark the parent as a listing wrapper.
- **Open question:** how to deduplicate a variant-per-URL against its
  parent's aggregate (same MPN, different URL) without losing either.

### Option C — One Part row per **variant**, via `hasVariant` descent

Generalize B to sites where variants don't have their own URLs. Walk
`hasVariant[]` (or equivalent) from the parent page and emit one
`ScrapedPayload` per variant using synthetic URLs (`<parent>?variant=<id>`
for Shopify, or the site's known deep-link shape).

- **Pro:** captures all variants uniformly across platforms.
- **Con:** `ScrapedPayload` becomes 1:N with the page; the runner's
  "one URL → one payload" contract needs revisiting. Synthetic URLs
  raise questions about how the extension's "re-scrape this page" flow
  should round-trip.

### Option D — First-class Variant model

Add a `Variant` table: `Part 1 → N Variant`, each Variant with its
own `sku`, `price_cents`, `image`, optional axis-value string
(`"4.065 Bore, .50mm oversize"`). `Part.part_number` becomes the
family MPN (nullable). `ScrapedPayload` grows a `variants: list[ScrapedVariant]`
field; adapters that know how to parse variants fill it, others leave
it empty.

- **Pro:** correct long-term model; preserves parent/variant semantics;
  gives price history a place to live per-variant; build lists can
  reference a specific variant.
- **Con:** real schema work (migration, admin UI, extension payload,
  PartListing semantics). The Chrome extension's POST-to-backend
  shape needs a compatible expansion. Probably 1–2 weeks of work
  end-to-end before any adapter code ships.

### Option E — Variant-aware cross-retailer dedupe only

Keep one Part per URL as today, but add a `Part.family_mpn` field that
adapters can populate (e.g. Texas Speed ProductGroup's `productGroupID`,
Shopify parent handle). Use it to link related Part rows for display
without changing the ingestion contract.

- **Pro:** cheapest non-trivial change. No 1:N in the ingest path.
- **Con:** doesn't actually fix "which variant did we price" — only
  makes the family visible in the UI.

---

## 7. Pragmatic next step

When the first user-facing pain shows up (most likely: "the part I
bought says $X but the site says $Y" on a variant axis):

1. Pick a single adapter where the problem is sharpest (likely
   `texasspeed`, `ets`, or `maperformance`).
2. Try **Option B** first — it's a data-only move. Allow per-variant
   URLs through the sitemap filter, treat the parent URL as "wrapper
   only" (skip ingest, but still extract links).
3. If B can't be made to work (parent has no per-variant URLs — pure
   Shopify picker case), escalate to **Option D**. Option C is a trap:
   it expands the ingest contract without giving the UI anywhere to
   put the result.

Whichever direction we go, update this doc and the adapter's docstring
with the new rule so the next author inherits the decision instead of
re-deriving it.
