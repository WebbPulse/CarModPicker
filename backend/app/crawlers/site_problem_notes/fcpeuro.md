# FCP Euro (fcpeuro.com)

**Status:** adapter not yet written. Investigation 2026-04-19.

## Fetch blocker: Cloudflare managed JS challenge

Product pages (e.g. `https://www.fcpeuro.com/products/bmw-brake-kit-shw-34112284101ktfr33`) are gated behind Cloudflare's *managed challenge* — the HTML response is a `Just a moment...` interstitial (`_cf_chl_opt` bootstrap, ~5 KB) that requires JS execution and cookie round-trips before the real page is served.

- `requests.get(...)` / `curl` with a current Chrome User-Agent → **HTTP 403** + challenge page.
- `curl` with our `CarModPicker-Crawler/1.0` User-Agent → **HTTP 403** + challenge page.
- `WebFetch` → **HTTP 403**.
- The challenge applies to every route tried, including JSON/feed endpoints (see below).
- This means `fetch_page()` in `app/crawlers/base.py` cannot retrieve FCP Euro HTML. The existing crawler runner will not work against FCP Euro without a JS-capable fetcher.

## Endpoints probed

| Path | Result |
| --- | --- |
| `/products/<handle>` | 403 challenge |
| `/products/<handle>.json` | 403 challenge |
| `/products.json` | 403 challenge |
| `/products/<handle>.js` | 500 (empty body) |
| `/sitemap.xml.gz` | 403 challenge (note: response is HTML, not gzip) |
| `/robots.txt` | **200** |

So even the sitemap is gated — we can't cheaply enumerate product URLs from outside a real browser.

## robots.txt

`User-agent: *` is permitted on product pages. Disallows are all account/cart/checkout paths and a long list of filter query params (`?brand=*`, `?year=*`, `?keywords=*`, `?price=*`, `*per_page=*`, etc.). No `Crawl-delay` directive.

The robots file declares one sitemap:

```
Sitemap: https://www.fcpeuro.com/sitemap.xml.gz
```

(which is itself behind the challenge — see above).

## Product URL pattern

`/products/<handle>` — handle is a human-readable slug that frequently embeds make + category + manufacturer SKU, e.g. `bmw-brake-kit-shw-34112284101ktfr33`:

- `bmw` — target vehicle make.
- `brake-kit` — product category hint.
- `shw` — short manufacturer tag (here: Shaw Development / SHW, an OE-supplier brand FCP distributes).
- `34112284101ktfr33` — manufacturer / kit part number (BMW front brake kit, OE-style numbering).

The make + SKU segments are in the URL itself, which is a useful last-resort fallback if HTML is unreachable.

## Paths forward

1. **Extension-only adapter** — write `parse_product_page()` tuned to FCP Euro's DOM/JSON-LD and wire the host into `adapter_name_for_product_url()` in `adapters/__init__.py`. The Chrome extension scrapes pages the user already loaded in their browser (post-challenge), so Cloudflare is not a blocker. `discover_product_urls()` can be a stub (or only yield `CRAWLER_FCPEURO_START_URLS`) since the runner can't reach pages anyway. **Lowest-risk first pass.**

2. **Crawler + JS fetcher** — swap the adapter's page fetch for a JS-capable client (`cloudscraper`, Playwright, undetected-chromedriver). Adds a heavy dependency and may still break when Cloudflare rotates challenge logic. Revisit only if bulk ingest proves worth it.

## Open questions (need a real page sample)

Without a post-challenge HTML snapshot we can't confirm:

- Does FCP Euro emit JSON-LD `Product` (name, brand, sku, mpn, gtin, offers.price, image)?
- What are the DOM selectors for title / price / SKU / manufacturer (class names, `data-*` attributes)?
- Is there an image CDN pattern we need to allowlist (like Shopify's `cdn.shopify.com`)?
- Are there bundle/kit landing pages that need to be rejected (as with ADRO's `-full-kit`)?

Next step before writing the adapter: capture a real product page via the Chrome extension (or manual `View Source` + save) and drop it in a fixture file so parser work can proceed.
