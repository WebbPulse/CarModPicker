# Enjuku Racing (enjukuracing.com)

**Status:** adapter written 2026-04-19 as Tier-1 TLS (`tier1_tls/enjukuracing.py`).

## Fetch blocker: Cloudflare client-fingerprint challenge

The `RETAILER_BACKLOG.md` entry estimated "Tier-0 should work — pattern matches
`xph.py`." The BigCommerce Stencil shape does match, but the Cloudflare posture
does not: Enjuku serves a client-fingerprint challenge to any non-browser
client at the TLS layer, same pattern as Z1 Motorsports and Vivid Racing.

What we saw on 2026-04-19:

- `curl -I -A "<chrome-ua>" https://www.enjukuracing.com/` → **403**, with the
  classic `cf-mitigated: challenge` header plus `Accept-CH` / `Critical-CH`
  UA-hint requirements. Same for `/xmlsitemap.php` and any product URL.
- `curl_cffi` with `impersonate="chrome"` → **200** on the homepage, sitemap
  index, each `xmlsitemap.php?type=products&page=N` child, and the product
  pages sampled.

Practical implication: the plain-HTTP `fetch_page()` cannot retrieve Enjuku
content. The adapter declares `FETCHER_TIER = "tls"` so the runner hands it a
`TlsFetcher` (curl_cffi Chrome impersonation); `self.fetcher.fetch(...)` is
used for both sitemap and product fetches.

## robots.txt highlights

```
User-agent: *
Disallow: /account.php
Disallow: /cart.php
Disallow: /checkout.php
Disallow: /search.php
Disallow: /admin/
...
```

Only account / checkout / search paths are disallowed. All `/products/...`
URLs are allowed. No `Sitemap:` directive was needed — `/xmlsitemap.php` is
the canonical BigCommerce Stencil sitemap index and is served without
challenge under the TLS fetcher.

## Sitemap shape

`/xmlsitemap.php` is a **sitemap index** with children partitioned by type:

- `xmlsitemap.php?type=pages&page=1`
- `xmlsitemap.php?type=products&page={1..6}` — ~8,287 product URLs per page at
  time of writing (the paging is sparse; total catalog is a few thousand).
- `xmlsitemap.php?type=categories&page=1`
- `xmlsitemap.php?type=brands&page=1`
- `xmlsitemap.php?type=news&page=1`

Discovery walks only the `type=products` children. URLs in those urlsets are
BigCommerce product pages under the `/products/<slug>.html` prefix — unlike
xph, which puts every product slug at the site root. The adapter's positive
filter is the path regex `^/products/<slug>\.html$`.

Override with `CRAWLER_ENJUKURACING_START_URLS` (comma-separated) for ad-hoc
runs.

## Product page shape (JSON-LD Product — unlike xph)

The BigCommerce Stencil theme Enjuku runs **does** emit a full schema.org
`Product` block in JSON-LD — unlike Extreme Power House, which only exposes
BCData + microdata and forced the xph adapter to parse BCData directly.

Fields observed on `isr-performance-inner-tie-rods-nissan-240sx.html`:

| Field        | Source                                              | Notes                                                        |
| ------------ | --------------------------------------------------- | ------------------------------------------------------------ |
| Name         | JSON-LD `name`                                      | Clean; no site-name suffix, no trailing SKU appended to title. |
| Brand        | JSON-LD `brand.name` (Brand object)                 | Authoritative for third-party lines (ISR, Brian Crower, Apexi, …). Enjuku has no "house brand" — they're a pure reseller — so no static-default manufacturer is needed. |
| SKU / MPN    | JSON-LD `sku`, `mpn`                                | Often identical (e.g. `IS-ITR-240` / `IS-ITR-240`). When `mpn` is null (some older Apexi SKUs), `sku` is the retailer-prefixed code (`apx499-A019`) — still the best available part number. `scraped_payload_from_json_ld` picks `sku` first. |
| Description  | JSON-LD `description`                               | Leading product-name duplication is common ("ISR Performance Inner Tie Rods - Nissan 240sx ISR Performance Inner Tie Rods are …"); `normalize_description_text` keeps it readable without heroics. |
| Price        | JSON-LD `offers.price`                              | Dollars; fallback chain drops to BCData `price.without_tax.value` and `og:product:price:amount` when the Offer block is empty. |
| Image        | JSON-LD `image` (single URL)                        | Single high-resolution `cdn11.bigcommerce.com/.../stencil/1280x1280/...` URL. `scraped_payload_from_json_ld` wraps it into a one-element list. |
| GTIN         | — (not emitted)                                     | JSON-LD has no `gtin*` field; BCData `gtin` is null on every page sampled. `gtin` stays unset — cross-retailer dedupe falls back to `(manufacturer, part_number)`. |

The custom Stencil theme uses an `et-`-prefixed class on the `<h1>`
(`et-productView-title`) rather than the stock `productView-title`
with `itemprop="name"` — so the xph-style `<h1 itemprop="name">` selector does
not match here. The DOM fallback uses `og:title` first and then any bare
`<h1>`, which covers this difference.

## Why JSON-LD is trusted over BCData here

On xph, the theme ships no JSON-LD Product at all, so BCData is the only
structured data available. On Enjuku, both are present. JSON-LD is the
preferred source because:

- `brand.name` is rich (Brand object) rather than absent (BCData exposes no
  brand field).
- Name matches the visible `<h1>` cleanly — no trailing SKU to strip.
- Description is ready to normalize without DOM gymnastics around
  `productView-description` heading nodes.

BCData is retained only as a **price fallback** for the rare page where
`offers.price` is empty or malformed. A permissive regex
(`_BCDATA_PRICE_RE`) pulls `product_attributes.price.without_tax.value`
without requiring the full blob to parse as JSON — the test suite covers both
the numeric and string-quoted variants.
