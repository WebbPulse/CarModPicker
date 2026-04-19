# JEGS (jegs.com)

**Status:** adapter not yet written. Investigation 2026-04-19.

## Fetch blocker: Cloudflare managed JS challenge

Product pages (e.g. `https://www.jegs.com/i/JEGS/555/513001/10002/-1`) are gated behind Cloudflare's *managed challenge* — the HTML response is a `Just a moment...` interstitial that requires JS execution and cookie round-trips before the real page is served.

- `requests.get(...)` with any User-Agent (including a current Chrome UA) returns **HTTP 403** + the challenge page (~5 KB of `_cf_chl_opt` bootstrap JS).
- `WebFetch` likewise returns 403.
- This means `fetch_page()` in `app/crawlers/base.py` cannot retrieve JEGS product HTML. The existing crawler runner will not work against JEGS without a JS-capable fetcher.

What still works without a challenge:

- `https://www.jegs.com/robots.txt` → 200
- `https://www.jegs.com/sitemap_index.xml` → 200 (note: not `/sitemap.xml`, which 404s to a regular HTML page)

## Sitemap shape

`sitemap_index.xml` points at 14+ gzipped product sitemaps under `/sitemap/product_sitemapN.xml.gz`. Each lists individual product page URLs. Uses the `http://www.google.com/schemas/sitemap/0.84` namespace (older Google schema), **not** the standard `http://www.sitemaps.org/schemas/sitemap/0.9` that our existing adapters' `SITEMAP_NS` constant assumes — a JEGS adapter's loc extraction must match on either the `.84` schema or use a namespace-agnostic `findall` (`.//{*}loc`).

## Product URL pattern

`/i/<brand>/<mfr-sku>/<internal-id>/<internal-id>/-1`

Example decomposition of the seed URL:

- `/i/` — product-detail path prefix.
- `JEGS` — manufacturer brand segment.
- `555` — manufacturer prefix / line.
- `513001` — manufacturer SKU (together with prefix: part number `555-513001`).
- `10002`, `-1` — JEGS-internal ids (catalog / variant). The trailing `-1` appears on most URLs.

The manufacturer + SKU segments are in the URL itself, which is a useful last-resort fallback if the HTML is unreachable.

## robots.txt

`User-agent: *` is permitted on product pages. The disallows are all filter/query patterns (`?*fq=...`, `?*N=...`, `/webapp/wcs/stores/servlet/*`) and a handful of "research tools" bots that are blocked wholesale. No `Crawl-delay` directive is set for `*`.

## Paths forward

1. **Extension-only adapter** — write `parse_product_page()` tuned to JEGS's DOM/JSON-LD and wire the host into `adapter_name_for_product_url()` in `adapters/__init__.py`. The Chrome extension scrapes pages the user already loaded in their browser (post-challenge), so Cloudflare is not a blocker. `discover_product_urls()` can be a stub (or raise) since the runner can't reach pages anyway. **Lowest-risk first pass.**

2. **Crawler + JS fetcher** — swap the adapter's page fetch for a JS-capable client (`cloudscraper`, Playwright, undetected-chromedriver). Adds a heavy dependency and may still break when Cloudflare rotates challenge logic. Revisit only if bulk ingest proves worth it.
