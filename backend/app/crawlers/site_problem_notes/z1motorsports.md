# Z1 Motorsports (z1motorsports.com)

**Status:** adapter written 2026-04-19 as Tier-1 TLS (`tier1_tls/z1motorsports.py`).

## Fetch blocker: Cloudflare client-fingerprint challenge

The `RETAILER_BACKLOG.md` entry estimated "Tier-0 likely OK." Investigation
showed that's not quite right — Z1 serves a Cloudflare challenge to any
non-browser client at the TLS layer, same pattern as Vivid Racing.

What we saw on 2026-04-19:

- `curl -A "<chrome-ua>" https://www.z1motorsports.com/sitemap.xml` → **403**,
  `cf-mitigated: challenge` header, ~5 KB interstitial body with `Accept-CH` /
  `Critical-CH` UA-hint requirements. Same for the homepage and any product URL.
- `curl https://www.z1motorsports.com/robots.txt` → **200** (served outside
  the challenge rule, as with most Cloudflare sites).
- `curl_cffi` with `impersonate="chrome"` → **200** on both the sitemap and
  product pages. Same fetcher tier that works for Vivid Racing.

Practical implication: `fetch_page()` in `app/crawlers/base.py` cannot retrieve
Z1 product HTML. The adapter declares `FETCHER_TIER = "tls"` so the runner
hands it a `TlsFetcher` (curl_cffi Chrome impersonation).

## robots.txt highlights

```
User-agent: Goodzer
Disallow: /
User-Agent: *
Disallow:
Disallow: /search*
Disallow: /advanced_search_result*
Allow: /
```

No `Sitemap:` declaration. `/search*` and `/advanced_search_result*` are
disallowed — we don't touch either. All product paths are allowed.

## Sitemap shape

Single flat urlset at `/sitemap.xml` (no sitemap index, no product sub-sitemap):

- ~2,150 URLs total.
- ~1,375 of those are category URLs (`-c-<digits>[_<digits>]*.html`).
- Only ~22 are product URLs (`-p-<digits>.html`). The rest are admin/account
  pages, `cdn-cgi/l/email-protection` links (Cloudflare obfuscated mailto),
  and miscellaneous static pages.
- URLs mix `http://z1motorsports.com/...` (bare host, no TLS) with
  `https://www.z1motorsports.com/...` — the adapter canonicalizes to the
  latter before yielding.

The ~22-product subset is all we can discover from the sitemap alone. Probing
`sitemap_index.xml`, `sitemap-products.xml`, `googlesitemap.xml`,
`sitemap.xml.gz`, and `xmlsitemap.php` all returned 404 or a fallback HTML
200 (`sitemap.xml.gz` serves HTML, not a gzipped sitemap — the file name is
misleading).

## Discovery: why we don't walk categories

Category pages render their product grids **client-side** via JS. Confirmed
2026-04-19: fetching `/performance-parts/brakes-c-6_9.html` and
`/powertrain/rear-differential-c-4_40_151.html` with the TLS fetcher returns
200 with no `-p-<digits>.html` anchors anywhere in the response body —
`hrefs` on the page point only at other categories, the top nav, and the
customer-account pages. Full catalog enumeration would require either:

1. **Tier-2 browser fetcher** — render the category page and wait for the
   AJAX product grid to populate, then harvest `-p-<digits>` anchors.
2. **AJAX endpoint discovery** — intercept the XHR that populates the grid
   and call it directly. Not yet identified; the page lives behind
   Cloudflare so a browser session with its cookies is probably needed.
3. **Extension-captured URLs** — rely on users browsing Z1 naturally and
   POSTing to `/crawled-pages/scrape` from the Chrome extension. The
   site-specific parse logic runs there via `adapter_name_for_product_url`
   regardless of how we obtained the URL.

For now the Tier-1 adapter ships with sitemap-only discovery plus a
`CRAWLER_Z1MOTORSPORTS_START_URLS` env override for ad-hoc runs. Upgrading
discovery to Tier-2 is tracked as a future extension — the parse logic itself
doesn't change.

## Product URL pattern

`/<category-path>/<slug>-p-<digits>.html`

Example:
`https://www.z1motorsports.com/big-brake-upgrades/z1-motorsports/z1-350z-g35-forged-street-big-brake-upgrade-front-and-rear-p-43428.html`

- The `-p-<digits>` tail is Z1's **internal product id** and also the value
  exposed as `<meta itemprop="sku">`. Safe as a per-site dedup key; **never
  written as `part_number`** — same rule as Vivid Racing. Cross-retailer
  dedup keys must come from an MPN, which Z1 does not expose.
- The category path in the middle is unstable: on-sale items redirect from
  the organic category path to `/all-sale-items/.../`. The adapter stores
  whatever URL the fetcher lands on after redirects; archive rescrapes
  against the original URL still parse fine.

## Product page shape (microdata, no JSON-LD Product)

Z1's theme emits only Organization + WebSite JSON-LD blocks — no Product
block. Product data lives in Schema.org microdata on the `<form id="formAddToCart">`
region:

| Field             | Selector                                              | Notes                                                   |
| ----------------- | ----------------------------------------------------- | ------------------------------------------------------- |
| Name              | `<span itemprop="name">` inside `<h1>`                | Authoritative. The `<title itemprop="name">` carries the same prose + site chrome, so the span wins. |
| Brand             | `<a itemprop="brand">`                                | Authoritative — `"Z1 Motorsports"` for house items, real brand names for third-party. |
| SKU (internal id) | `<meta itemprop="sku" content=" 43428">`              | Internal product id; matches `-p-43428`. Not an MPN. Do **not** emit as `part_number`. |
| Price             | `<span itemprop="price" content="1649.99">`           | Sale-aware — the span lives inside `.sp-newPrice`. The `.sp-oldPrice` strike-through has no itemprop, so we won't grab it. |
| Description       | `<div itemprop="description">`                        | Nested HTML (banners, inline images); normalized to plain text via `normalize_description_text`. |
| Image (primary)   | `<meta itemprop="image" content="ss26_43428.jpg">`    | Filename-only — anchor against `https://cdn.z1motorsports.com/images/`. |
| Image (gallery)   | `.product-img-gal-display figure[data-orig-img]` + `.product-img-gal-sel figure[data-{small,display,zoom}-img]` | Multiple resolutions of the same photo (`thumbs/<W>x<H>_<base>.webp`); dedupe by stripping the `<W>x<H>_` prefix and extension. |

No `og:title` / `og:description` is emitted on this theme. `og:image` is
**commented out** in the markup, so fall back to the microdata image meta.
`itemprop="priceCurrency"` is also absent — we assume USD (store is US-based,
prices in the page body are explicitly `$...`).

## Why the SKU isn't usable as `part_number`

`<meta itemprop="sku" content="43428" />` is just Z1's internal integer
product id (the same integer as the URL's `-p-43428` suffix). It's not an
MPN, so writing it to `part_number` would only collide with unrelated SKUs
from other retailers (any other site's `43428` product). The adapter follows
the Vivid Racing pattern: try a title-derived part-number candidate via
`extract_part_number_candidate_from_title`, and leave `part_number=None`
when that comes up empty. Cross-retailer dedup on `(manufacturer,
part_number)` for Z1 items will generally require parts to match on
manufacturer + name — which is the right granularity for Z1's house SKUs,
since most are Z1-branded originals without an MPN-style code anywhere.
