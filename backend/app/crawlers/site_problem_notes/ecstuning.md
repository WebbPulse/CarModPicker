# ECS Tuning (ecstuning.com)

**Status:** adapter written (parse-only, Tier 2). Live discovery not yet wired up. 2026-04-19.

## Fetch blocker: Cloudflare Bot Management

Per the retailer backlog (`adapters/RETAILER_BACKLOG.md`), ECS Tuning is behind heavy Cloudflare — "Tier-1 TLS minimum, possibly Tier-2 browser." We have not yet run a full probe matrix from AWS egress, but ECS historically serves the managed JS challenge to unprivileged IPs, and ECS is the highest-value Euro retailer to lose to a false-negative fetch.

The adapter declares `FETCHER_TIER = "browser"` as the conservative default. If follow-up probing shows plain TLS impersonation (`curl_cffi`) clears the challenge reliably from our egress, demote to `tier1_tls/`. Cost-of-wrong is asymmetric here: over-fetching with Tier 2 just costs FlareSolverr time; under-fetching with Tier 0/1 silently drops ECS coverage.

## Endpoints to probe (not yet confirmed)

| Path | Expected |
| --- | --- |
| `/b-<brand>-parts/<slug>/<sku>/` (product) | likely 403 challenge from AWS egress |
| `/es<digits>/` (catalog-id redirect) | same |
| `/sitemap.xml` | ECS advertises a sitemap; status unconfirmed |
| `/robots.txt` | assumed 200 |

Re-run the FCP Euro / JEGS probe script against these paths before enabling live crawling.

## Product URL pattern

Two shapes:

1. `/b-<brand-slug>-parts/<product-slug>/<mfr-sku>/`
   Example: `/b-genuine-bmw-parts/thermostat-housing-assembly/11538635689/`
   - `genuine-bmw` — brand slug (often prefixed with `genuine`, `oem`, `oes`, `assembled`, `original` — retailer qualifiers, not part of the manufacturer name).
   - `thermostat-housing-assembly` — human-readable product slug.
   - `11538635689` — manufacturer / OEM SKU. For Genuine BMW parts this is the BMW OEM part number.

2. `/es<digits>/` — ECS internal catalog id. Redirects to the canonical brand-parts URL when resolved. Nothing is derivable from the path alone; adapter falls through to JSON-LD / DOM parsing.

The brand + SKU in pattern 1 are load-bearing for the URL-derived fallback — when the Chrome extension captures a page before late-binding JSON-LD is injected by the theme, the URL is the only reliable signal. Matches the approach in `tier2_browser/jegs.py`.

## Brand-slug normalization

Leading retailer-qualifier tokens are stripped so the stored `part_manufacturer` matches the canonical make:

| URL slug | Stored brand |
| --- | --- |
| `genuine-bmw` | `BMW` |
| `oem-audi` | `Audi` |
| `oes-mercedes` | `Mercedes` |
| `schwaben` | `Schwaben` (ECS house brand — no prefix to strip) |
| `assembled-by-ecs` | `by ECS` (pathological; will almost certainly be overridden by JSON-LD) |

Short make codes (`bmw`, `vw`, `mini`) are uppercased; longer tokens are title-cased. JSON-LD `brand.name` always wins over this fallback when present.

## Discovery plan (when Tier 2 is wired)

- **Do not** walk the vehicle-fitment selector (`/vehicle/<make>/<chassis>/...`). The same product appears under many fitment branches; discovery via fitment pulls huge duplicate sets.
- Walk the category sitemap instead (`/sitemap.xml` → category sitemaps → product URLs). Filter on the `/b-<brand>-parts/` path shape so catalog-id redirects and CMS pages are rejected.
- Respect `robots.txt` Crawl-delay if set — shared `fetch_with_retries` handles it.
- Expect ~6-figure URL count for a full walk; operators should crawl one category at a time (`CRAWLER_ECSTUNING_START_URLS` env var when discovery lands).

## Open questions (need a real page sample)

Without a post-challenge HTML snapshot we can't confirm:

- Does ECS emit JSON-LD `Product` (name, brand, sku, mpn, gtin, offers.price, image)? The synthetic test pages assume a plain `schema.org/Product` shape; tighten against a fixture once captured.
- What are the DOM selectors for title / price / SKU / manufacturer (class names, `data-*` attributes)?
- Is there a CDN pattern we need to allowlist for images (the current adapter accepts any host)?
- Are there bundle/kit landing pages that need to be rejected?

Next step before enabling live crawling: capture a real product page via the Chrome extension and drop it in `backend/tests/crawlers/fixtures/ecstuning/` so parser selectors can be tightened and a probe run can confirm the fetcher tier.
