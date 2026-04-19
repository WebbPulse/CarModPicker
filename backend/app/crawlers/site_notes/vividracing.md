# Vivid Racing (vividracing.com)

**Status:** adapter not yet written. Investigation 2026-04-19.

## Fetch blocker: Cloudflare block (not a JS challenge)

Product pages (e.g. `https://www.vividracing.com/agency-power-oval-taper-air-filter-wrap-enclosed-top-tapers-bottom-tall-p-152475800.html`) come back as a Cloudflare **"Sorry, you have been blocked"** page — not a managed JS interstitial like JEGS, but an outright block with a Ray ID and the "triggered the security solution" copy.

- `requests.get(...)` with the default crawler UA → blocked.
- `curl` with a full current-Chrome header set (UA, `Sec-Ch-Ua*`, `Sec-Fetch-*`, `Accept-Language`, `Accept-Encoding: gzip, deflate, br, zstd`, `Upgrade-Insecure-Requests`, `--compressed`) → still blocked, ~5 KB Cloudflare error page, no challenge script to solve.
- **The same URL loads fine in a real browser from the same network** (user confirmed 2026-04-19 on the seed URL). That rules out an IP / ASN block against our egress — Cloudflare is fingerprinting the *client*, not the source address. Likely signals: TLS ClientHello / JA3 fingerprint (Python `requests` and curl both look nothing like real Chrome here), missing Cloudflare cookies from a prior passive challenge, or Bot Management scoring on header order / HTTP/2 frame behavior.
- Practical implication: a TLS-impersonating client (`curl_cffi` with `impersonate="chrome"`) or a real headless browser (Playwright / undetected-chromedriver) has a reasonable chance of getting through, because we are not IP-banned. Plain `requests` / stock `cloudscraper` likely will not — they fail the TLS fingerprint check before any JS challenge is even served.

This means `fetch_page()` in `app/crawlers/base.py` cannot retrieve Vivid Racing product HTML from our AWS egress.

What still works unauthenticated:

- `https://www.vividracing.com/robots.txt` → 200 (served outside the Cloudflare block rule).
- `https://www.vividracing.com/sitemap.xml` → **403** with the same block page. `robots.txt` advertises `https://www.vividracing.com/sitemap_index.xml.gz`, which is likely also blocked (same origin, same rule).

## robots.txt highlights

- `User-Agent: *` is allowed for product paths.
- `Disallow: /*?*` — **any URL with query params is disallowed.** Canonical product URLs have no query string so we're fine, but any tracking-param or filtered-catalog URL we might pick up from referrers must be stripped before being fed to the adapter. `canonicalize_url()` in `crawlers/base.py` already strips known tracking params, which covers the common cases.
- Large list of `/account*`, `/checkout*`, `/address_book*` disallows — standard e-commerce account pages, irrelevant for product discovery.
- Sitemap declared: `https://www.vividracing.com/sitemap_index.xml.gz` (gzipped index — our existing sitemap discovery code in the other adapters reads plain XML via `fetch_page()` and would need `.gz` handling even if the URL were reachable).

## Product URL pattern

`/<slug>-p-<product-id>.html`

Example: `agency-power-oval-taper-air-filter-wrap-enclosed-top-tapers-bottom-tall-p-152475800.html`

- Slug encodes manufacturer + product name (here "Agency Power" → first two slug segments). This is a useful manufacturer fallback when the HTML is unreachable, but noisy — the slug is marketing copy, not a structured field.
- `p-<digits>.html` — Vivid internal product id, **not** a manufacturer SKU. Safe as a dedup key within Vivid but should never be written as `part_number`.

## Paths forward

1. **Extension-only adapter** — write `parse_product_page()` tuned to Vivid's DOM/JSON-LD and register the host in `adapter_name_for_product_url()` in `adapters/__init__.py`. The Chrome extension scrapes pages the user already loaded in their own browser (past the Cloudflare block), and `POST /crawled-pages/scrape` + the archive rescrape pipeline both route through `adapter_name_for_product_url()`, so a parse-only adapter gives us better quality than `generic` for every extension-captured Vivid page. `discover_product_urls()` should be a stub (or raise) since the runner cannot reach pages anyway. **Lowest-risk first pass — same shape as the JEGS plan.**

2. **Crawler + TLS-impersonating fetcher** — since the block is methodology-based, not IP-based (real-browser access from the same network works), swapping `fetch_page()` for `curl_cffi` with `impersonate="chrome"` is the first thing to try. That alone may be enough; if Cloudflare also issues a JS challenge on top, a headless browser (Playwright / undetected-chromedriver) becomes the fallback. Plain `cloudscraper` and vanilla `requests` will not help — they fail the TLS fingerprint check before any challenge is served. No residential-proxy spend required at first. Worth considering if we want scheduled server-side ingest from Vivid.

3. **Capture a real-browser sample for adapter development** — before writing the adapter, capture one representative product page via the Chrome extension (or save-as from a logged-in browser session) and drop the HTML in the repo / S3 so the adapter can be built and tested against the actual DOM. Our machine can't fetch it on demand.
