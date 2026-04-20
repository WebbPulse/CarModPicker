# Speed Industry (speedindustry.com)

**Status:** adapter scaffolded 2026-04-19 (parse-only first pass; live crawl requires Tier 2 / FlareSolverr). Seed URL under investigation: `https://speedindustry.com/hks-hi-power-catback-exhaust-a90-mkv-supra-gr-2020-titanium-tips-dual-exit`.

## Fetch blocker: Cloudflare managed JS challenge

Every surface we probed returns HTTP 403 + the `Just a moment...` interstitial (`_cf_chl_opt` bootstrap, `cType: 'managed'`) — the same class of challenge as JEGS and FCP Euro, *not* the bare "Sorry, you have been blocked" page Vivid Racing serves.

Probed 2026-04-19 from the workstation (Chrome UA, plain `requests`/`curl`), all 403 with ~5 KB challenge body:

- `/hks-hi-power-catback-exhaust-a90-mkv-supra-gr-2020-titanium-tips-dual-exit` (the seed product)
- `/robots.txt`
- `/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml`
- `/products.json`, `/products`
- `/wp-json/`

That last one is notable: if the store were WooCommerce with a default config, `/wp-json/` would be the REST root, but we can't confirm it's WooCommerce (or anything else) without a real response. The URL slug style `/<slug>` (no `/products/`, `/p/`, or `/parts/` prefix) is consistent with WooCommerce or BigCommerce but doesn't narrow it down by itself.

Practical implication: `fetch_page()` in `app/crawlers/base.py` cannot retrieve Speed Industry product HTML. Plain `requests`, vanilla `cloudscraper`, and most likely `curl_cffi` alone (Tier 1 — solves fingerprint blocks but not JS challenges) will not help either — the challenge requires JS execution and a cookie round-trip before the real page is served.

## Paths forward

1. **Extension-only adapter (first pass, shipped now).** `discover_product_urls()` is a stub that yields nothing; `parse_product_page()` handles HTML captured through the Chrome extension (`POST /crawled-pages/scrape`) or replayed via the archive rescrape pipeline. Both routes go through `adapter_name_for_product_url()` in `adapters/__init__.py`, so registering `speedindustry.com` there gives extension-captured pages a site-specific parser instead of the generic fallback. Lowest-risk pattern — matches how we handled JEGS.

2. **Live crawl via Tier 2 (FlareSolverr).** The adapter already declares `FETCHER_TIER = "browser"`, so the runner will pick up the browser fetcher automatically once `FLARESOLVERR_URL` is set in the HCP Terraform workspace (see `crawlers/README.md` §Tier 2). When that happens, flesh out `discover_product_urls()` — try `sitemap.xml` first (most common), fall back to walking category pages. No TLS-impersonation (Tier 1) intermediate step; the managed-challenge body makes it clear JS execution is required.

3. **Capture a real product page before tuning the parser.** Until we have actual HTML, the adapter leans on generic JSON-LD + OG meta + DOM fallbacks. Grab a sample via the Chrome extension (or Save Page As from a real browser session) and drop it in `backend/tests/crawlers/fixtures/` so the tests can assert against the actual DOM — brand name ("HKS"), price location, SKU/MPN placement, image gallery structure are all unknowns right now.

## Product URL pattern

`/<slug>` — hyphenated product slug directly at the root. Example: `/hks-hi-power-catback-exhaust-a90-mkv-supra-gr-2020-titanium-tips-dual-exit`.

The slug encodes brand + product name + fitment ("hks … a90 mkv supra gr 2020 …") but is marketing copy, not a structured part number. Safe as a last-resort brand fallback (first slug segment is often the manufacturer), unsafe as a `part_number`.
