# Bimmerworld (bimmerworld.com)

**Status:** adapter shipped 2026-04-19 as Tier-0 plain-HTTP
(`tier0_http/bimmerworld.py`).

The `RETAILER_BACKLOG.md` entry estimated "Tier-0/1." Investigation showed
plain HTTP is sufficient — no Cloudflare block, no TLS-fingerprint check, no
JS challenge. The interesting wrinkle is on the **parser** side, not the
fetcher: NetSuite SuiteCommerce builds the JSON-LD `Product` block in
JavaScript at runtime, so a fetched page has an empty
`<script id="dynamicJSONLD">`. Parser pulls data from the same DOM hooks
the JS reads from.

## Platform

NetSuite SuiteCommerce. Telltales in the page source:

- `compid=3750282` baked into image URLs and tracker pixels.
- Product images served from `/core/media/media.nl?id=<int>&c=3750282&h=<hash>`.
- Backend templates served from `/s.nl`, `/app/site/...`, `/app/center/...`.
- Footer comment: `<!-- Host [ sh.sp.3.prod.phx.na5 ] App Version
  [ 2026.1.13.30009 ] -->` — the standard NetSuite SuiteCommerce
  build-version comment.

## Probe results, 2026-04-19, AWS egress, browser UA

| Path                                                                                   | HTTP | Notes                                  |
| -------------------------------------------------------------------------------------- | ---- | -------------------------------------- |
| `/robots.txt`                                                                          |  200 | Allows all; `Crawl-Delay: 10`.         |
| `/`                                                                                    |  200 | Plain-HTTP is fine.                    |
| `/sitemap.xml`                                                                         |  301 | Redirects to `/Sitemap-https.xml`.     |
| `/Sitemap-https.xml`                                                                   |  200 | Single flat urlset, ~5.5 MB, ~34K URLs.|
| `/Brakes/StopTech-ST60-380-Big-Brake-Kit-E9X-335i.html`                                |  200 | Product page, plain HTML.              |

`requests.Session().get()` follows the 301 transparently, so the adapter
calls `fetch_page("/sitemap.xml")` and lets the redirect resolve itself.

## robots.txt highlights

```
User-agent: Googlebot
Disallow:

User-agent: Googlebot-image
Disallow:

User-agent: *

Crawl-Delay: 10
```

- `User-Agent: *` has no `Disallow` directives — every path is crawlable.
- `Crawl-Delay: 10` is honored automatically by the runner via
  `get_crawl_delay_sec()`; no adapter-side change needed.
- No `Sitemap:` directive. `/sitemap.xml` is the conventional path and
  NetSuite redirects it to the canonical `/Sitemap-https.xml`.

## Sitemap shape

Single flat urlset (no sitemap index):

- Total `<url>` entries: ~34,386.
- Of those, ~34,063 end in `.html` — these are product URLs.
- The remaining ~320 end with `/` — these are top-level category pages
  (`/Brakes/`, `/Engine/`, `/Suspension-Steering/`, …) and CMS pages
  (`/About-Us/`, `/About-Us/BMW-Tech-Info/`, etc.).
- The product-vs-category split is purely on the trailing `.html`. The
  adapter's `_is_product_url` matches `^/[A-Za-z0-9][A-Za-z0-9_\-/]*\.html$`
  and additionally rejects a small list of CMS pages that happen to use the
  `.html` suffix (`/Gift-Certificate.html`, `/Wishlist.html`).

## Product URL pattern

`/<Category>/[<Sub>/]<Slug>.html`

Examples:

- `https://www.bimmerworld.com/Brakes/StopTech-ST60-380-Big-Brake-Kit-E9X-335i.html`
- `https://www.bimmerworld.com/BMW-Interior/BMW-Interior-Floor-Mats/Rear-All-Weather-Floor-Mats-Black-Red-F48-X1.html`
- `https://www.bimmerworld.com/Brakes/BMW-OEM-Front-Brake-Pads-F25-X3-2012-2016-F26-X4-34106856191.html`

OEM parts often have the BMW part number (e.g. `34106856191`) baked into
the slug. House and third-party items don't.

## Product page shape (no usable JSON-LD)

The static HTML emits `<script id="dynamicJSONLD" type="application/ld+json"></script>`
— **empty**. A jQuery `$(document).ready(...)` handler later in the page
populates it from page state by reading these elements / variables:

| Field         | Source                                                  | Notes                                                   |
| ------------- | ------------------------------------------------------- | ------------------------------------------------------- |
| Name          | `<span id="productName" style="display: none;">`        | Hidden span the JS reads via `$("#productName").text()`. |
| Description   | `#tabs-1 .tab-content1`                                 | Full description tab — feature bullets + BMW fitments. The hidden `<span id="productDescription">` carries only a one-line blurb (also used for og:description). Adapter prefers the tab. |
| Price         | `<span id="priceDisplay" style="display: none;">`       | Plain text like `$3,959.46`. |
| Brand         | inline `<script>` — `var brand = "...";`                | Hard-coded into the page by the SuiteCommerce template. Reliable. |
| Part number   | inline `<script>` — `var itemid = "...";`               | Bimmerworld's internal SKU (e.g. `83.154.6800`). The same script computes `var mpn = "" || itemid;` and emits *both* as `sku` and `mpn` in the JSON-LD it builds — Bimmerworld treats `itemid` as the canonical part number. Fallback source: `<meta name="description" content="This is BMW parts item <ID> described as ...">`. |
| Image         | og:image + `.product-image-slider .slide [data-zoom]`   | NetSuite `/core/media/media.nl?id=<int>` URLs. Multiple slides may reference the same media `id` at different `h` hashes / sizes — dedup on the `id` query param so the gallery collapses to unique photos. |

## Why we extract from inline `<script>` source

Brand and `itemid` are only available as JS-variable initializers in an
inline `<script>` block — they are *not* surfaced anywhere in the rendered
DOM. Two options:

1. Run the JS (Tier-2 browser fetcher) and read the populated
   `#dynamicJSONLD` body.
2. Regex the JS-variable initializers out of the static HTML.

Option 2 is materially cheaper (no FlareSolverr round-trip, no Chrome boot)
and the source markup is stable: NetSuite's product detail template ships
the same `var name = ...; var image = ...; var itemid = ...; var brand = ...;`
preamble on every product page in the storefront. The adapter falls back to
the static `<meta name="description">` lead (`"This is BMW parts item <ID>
described as ..."`) when the script regex misses, so a future template tweak
that minifies / renames the JS vars still produces a usable part number.

## On the `itemid` → `part_number` choice

Bimmerworld's `itemid` (e.g. `83.154.6800`) is their internal NetSuite item
number. For BimmerWorld house-brand SKUs it *is* the canonical part number —
there is no separate MPN. For third-party SKUs (StopTech, Brembo, Girodisc,
Alcon), the page does **not** surface the manufacturer's MPN; only the
internal `itemid` is shown.

Storing `itemid` as `part_number` follows Bimmerworld's own JSON-LD shape
(`{"sku": itemid, "mpn": itemid, "brand": brand}`), which means cross-
retailer dedup via `(manufacturer, part_number)` will work for items where
two retailers happen to both render Bimmerworld's `itemid` (uncommon — most
sites use the manufacturer's MPN), and *won't* match another retailer's
listing of the same StopTech SKU. Acceptable trade-off: the `itemid` is
deterministic per Bimmerworld product, makes the part addressable in our
system, and avoids `part_number=None` for the entire catalog. If we later
add a second retailer for any of these third-party brands and want to
dedup, the right move is title + manufacturer + price-band heuristic, not a
`part_number` change here.
