# Apex Wheels (apexwheels.com)

**Status:** adapter rewritten 2026-04-19 (parse-only; live crawl requires Tier 2 / FlareSolverr). Replaces the old `apexraceparts.py` Tier 0 Shopify adapter.

## Rebrand + platform migration

Apex rebranded from "Apex Race Parts" → "Apex Wheels" and moved off Shopify onto a Nuxt + Sanity CMS + Vercel stack. Observed state:

- `https://www.apexraceparts.com/sitemap.xml` → Cloudflare HTTP 429 on the old edge. Following redirects lands on `https://apexwheels.com/` (root, not a matching path — they did not preserve the sitemap URL).
- `https://apexwheels.com/*` — every surface (including `/robots.txt` and `/sitemap.xml`) returns HTTP 429 with the Vercel Security Checkpoint interstitial body (`[data-astro-cid-nbv56vs3]`, bootstrapped from `/.well-known/vercel/security/static/challenge.v2.min.js`).

The smoke-test log that triggered this rewrite showed the old adapter burning ~65 s on five 429-with-backoff retries (2.3 s → 4.4 s → 8.9 s → 16 s → 33.8 s) against `apexraceparts.com/sitemap.xml` before we manually cancelled the run.

## Fetch blocker

Probed 2026-04-19 from the workstation with `curl -L -A '<ua>'` across Googlebot, bingbot, and a recent Chrome UA. All three returned HTTP 429 with a ~33 KB Vercel challenge body against both `/sitemap.xml` and `/robots.txt`. Plain `requests`, vanilla TLS impersonation (Tier 1, `curl_cffi`), and `cloudscraper` will not suffice — the challenge requires JS execution and a cookie round-trip before the real page is served.

`fetch_page()` in `app/crawlers/base.py` cannot retrieve Apex product HTML directly. `FETCHER_TIER = "browser"` — the runner will swap in FlareSolverr once `FLARESOLVERR_URL` is configured.

## URL shape (post-rebrand)

Verified against a Wayback Machine snapshot of `https://apexwheels.com/` (20241223024645):

- `/wheels/<tier>/<line>/<model>` — shoppable product page. Examples:
  - `/wheels/flow-formed/classic-line/arc-8`
  - `/wheels/flow-formed/classic-line/ec-7`
  - `/wheels/flow-formed/evolution-line/sm-10`
  - `/wheels/forged/sprint-line/ec-7rs`
  - `/wheels/forged/sprint-line/sm-10rs`
  - `/wheels/forged/sprint-line/vs-5rs`
  - `/wheels/forged/enduro-line/sm-10re`
  - `/wheels/forged/enduro-line/vs-5re`
  - `/wheels/forged/touring-line/arc-8rt`
  - `/wheels/forged/touring-line/ml-10rt`
- `/accessories/<subcat>` — each subcat is itself a shoppable SKU line. Examples:
  - `/accessories/wheel-hardware`
  - `/accessories/hubcentric-wheel-centering-rings`
  - `/accessories/wheel-spacers`
  - `/accessories/wheel-stud-kits`
  - `/accessories/wheel-center-caps`
  - `/accessories/wheel-tpms-sensors-valve-stems`
  - `/accessories/stickers-decals`
  - `/accessories/hats`
  - `/accessories/apparel`
- `/wheels/<tier>` and `/wheels/<tier>/<line>` — category landings, not shoppable. `_is_product_url` rejects these (requires 4 path segments for the wheels tree).
- Legacy `apexraceparts.com/products/<handle>` — no longer resolves live (301 to `apexwheels.com/`), but `_is_product_url` accepts the shape so archive-replay / still-cached Chrome extension submissions route to this adapter.

## JSON-LD shape

Verified via Wayback (20241112152327) capture of `/wheels/flow-formed/classic-line/arc-8`. Nuxt emits JSON-LD as a single-element list:

```json
[{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "ARC-8 Wheels",
  "description": "Our best seller for over 15 years...",
  "sku": "ARC81710ET25-5120-7256-M-AN",
  "image": ["https://cdn.sanity.io/images/c8ihu5xk/production/239076efec-2000x2000.png"],
  "offers": {
    "@type": "Offer",
    "priceCurrency": "USD",
    "price": 334,
    "itemCondition": "https://schema.org/NewCondition",
    "availability": "https://schema.org/InStock"
  }
}]
```

Notes:

- **No `brand` field.** The adapter defaults the manufacturer to the canonical `"Apex"` and collapses all self-spellings (`APEX`, `Apex Wheels`, `Apex Race Parts`, `apexraceparts`) to that one row. Co-branded SKUs (PFC, G-LOC, Motul) that carry a distinct `brand.name` pass through unchanged.
- `sku` encodes the configured variant fitment (width, offset, bolt pattern, center bore, machine, color). Safe as `part_number`; users browsing for ARC-8s at any other fitment will see a different SKU from a different page.
- `image` is a single Sanity CDN URL. `<img>` tags on the rendered page carry the rest of the gallery (profile views, angle shots), but the adapter keeps the JSON-LD hero when present — DOM sweep is capped at 12 and runs only when JSON-LD is absent.
- Prices are bare numbers (no `$` prefix). `extract_dom_price` / `scraped_payload_from_json_ld` both handle this without extra work.

`extract_json_ld_product` already unwraps `[{Product}]` list-form JSON-LD, so the shared helper does the right thing.

## Paths forward

1. **Extension-only adapter (shipped now).** `discover_product_urls()` is a stub that yields nothing; `parse_product_page()` handles HTML captured through the Chrome extension (`POST /crawled-pages/scrape`) or replayed via the archive rescrape pipeline. Both routes go through `adapter_name_for_product_url()` in `adapters/__init__.py`, which now routes both `apexwheels.com` *and* the legacy `apexraceparts.com` host here.

2. **Live crawl via Tier 2 (FlareSolverr).** Adapter already declares `FETCHER_TIER = "browser"`, so the runner will pick up the browser fetcher once `FLARESOLVERR_URL` is set. When wiring up `discover_product_urls()`:

   - Try `/sitemap.xml` first (standard entry point, but Vercel-gated — the FlareSolverr session must be warm or the same JS challenge fires).
   - Fall back to walking `/wheels/<tier>/<line>` category pages, which embed the model-level URLs in the nav DOM.
   - Budget-wise, Apex has roughly ten model pages under `/wheels/` plus ~ten subcategories under `/accessories/` — the full catalog fits in one short discovery run; no need for sitemap pagination.

3. **Capture a real live page when FlareSolverr is up.** Current parser is modeled on the Wayback snapshot, not a live capture — if Apex changes their JSON-LD shape, the synthetic fixture won't catch it. Drop a real capture under `backend/tests/crawlers/fixtures/` and add an end-to-end test.
