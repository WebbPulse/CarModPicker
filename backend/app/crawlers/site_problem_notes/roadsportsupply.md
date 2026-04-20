# Road Sport Supply / RSS Manufacturing (roadsportsupply.com)

**Status:** adapter shipped 2026-04-19 as Tier-0 HTTP (`tier0_http/roadsportsupply.py`).

## Domain correction

The `RETAILER_BACKLOG.md` entry listed `rss-mfg.com` as the manufacturer's
domain. That hostname does not resolve (`Could not resolve host: rss-mfg.com`
on DNS; confirmed in April 2026).

RSS ("Road Sport Supply") is the manufacturer — Porsche suspension / chassis
components, Costa Mesa CA — and their actual live storefront is
`roadsportsupply.com`. The adapter and host router are keyed on that domain.

## Fetcher posture

No challenge on this origin. A plain Chrome-UA `curl` returned HTTP 200 on:

- `https://roadsportsupply.com/` (homepage)
- `https://roadsportsupply.com/xmlsitemap.php` (sitemap index)
- `https://roadsportsupply.com/xmlsitemap.php?type=products&page=1` (child urlset)
- `https://roadsportsupply.com/323-thrust-arm-bushing-puck-non-castor-adjustable-front-axle/` (product)

Cloudflare is present (`server: cloudflare`, `cf-ray:` headers) but passive at
this TLS layer — no `cf-mitigated: challenge` observed. Tier-0 `HttpFetcher`
is sufficient; unlike Enjuku Racing, we do not need `curl_cffi`.

## Sitemap shape

`/xmlsitemap.php` is a **sitemap index** partitioned by content type, the
standard BigCommerce Stencil layout:

- `xmlsitemap.php?type=pages&page=1`
- `xmlsitemap.php?type=products&page=1` (and paginations)
- `xmlsitemap.php?type=categories&page=1`
- `xmlsitemap.php?type=brands&page=1`
- `xmlsitemap.php?type=news&page=1`

Discovery walks only the `type=products` children — same filter as xph /
enjukuracing / enjukuracing. Within those child urlsets the product URLs live
at the site root (`/<slug>/` with trailing slash, no `/products/` prefix),
mirroring the xph.com shape.

Override with `CRAWLER_ROADSPORTSUPPLY_START_URLS` (comma-separated) for
ad-hoc runs.

## Product page shape (BigCommerce Stencil with JSON-LD Product)

Fields observed on `323-thrust-arm-bushing-puck-non-castor-adjustable-front-axle`:

| Field       | Source                                              | Notes                                                        |
| ----------- | --------------------------------------------------- | ------------------------------------------------------------ |
| Name        | JSON-LD `name`                                      | Clean — no site-name suffix, no trailing SKU appended.       |
| Brand       | JSON-LD `brand.name` (Brand object)                 | Authoritative. "RSS" on in-house SKUs; third-party brand names on reseller SKUs (Sharkwerks, Cargraphic, Racetech, Girodisc, …). No static default is forced — the storefront spans both house and third-party lines. |
| SKU / MPN   | JSON-LD `sku`, `mpn`                                | `sku` is the canonical part number on every page sampled. `mpn` is sometimes the same string, sometimes null. `scraped_payload_from_json_ld` picks `sku` first. |
| Description | JSON-LD `description`                               | HTML-entity escaped (e.g. `&amp;ndash;`, `&amp;reg;`); `normalize_description_text` unescapes and trims without additional work. |
| Price       | JSON-LD `offers.price`                              | Dollars. Fallback chain drops to BCData `price.without_tax.value` then `og:product:price:amount` when the Offer block is empty (rare). |
| Image       | JSON-LD `image` (single URL)                        | High-resolution `cdn11.bigcommerce.com/s-kmq200x97v/images/stencil/1280x1280/...` URL. |
| GTIN        | — (not emitted)                                     | JSON-LD has no `gtin*` field; BCData `gtin` is null on every page sampled. Left unset — cross-retailer dedupe falls back to `(manufacturer, part_number)`. |

The stock Stencil `<h1 itemprop="name">` is **not** emitted on this theme —
only a bare `<h1>`. The DOM fallback therefore uses `og:title` first, then any
bare `<h1>`, matching the enjukuracing approach.

## Why this adapter mirrors enjukuracing instead of xph

Same BigCommerce Stencil platform family as both. The choice of base:

- **Not xph**: xph emits *no* JSON-LD Product block at all, forcing that
  adapter to parse BCData directly and strip trailing SKU tokens from titles.
  Road Sport Supply ships full JSON-LD — we'd be wasting work.
- **Matches enjukuracing**: both have JSON-LD Product + BCData as price
  fallback + no GTIN. The only divergence is the URL shape: enjukuracing is
  `/products/<slug>.html`, RSS is `/<slug>/` at the root.

## BCData fallback

BCData is retained only as a **price fallback** for the rare page where
`offers.price` is empty or malformed. The same permissive regex as
enjukuracing (`_BCDATA_PRICE_RE`) pulls `product_attributes.price.without_tax.value`
without requiring the full blob to parse as JSON; tests cover both numeric and
string-quoted variants.
