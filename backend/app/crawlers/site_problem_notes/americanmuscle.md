# American Muscle (americanmuscle.com)

**Status:** adapter written (parse-only, Tier 2). Live discovery not yet wired up. 2026-04-19.

## Why this retailer matters

American Muscle is the largest Mustang aftermarket retailer by volume. Cobb and AWE cover Mustang for specific SKUs, but without AM, Mustang build lists (S197 / S550 / S650) are not priceable end-to-end — suspension, exhaust, cosmetics, drivetrain all live here. Also picks up F-150 performance overlap. Mustang is a core enthusiast chassis still at effectively half a retailer of real coverage until AM lands; see `adapters/RETAILER_BACKLOG.md` batch 1.

## Fetch blocker: heavy anti-bot

The retailer backlog flags AM as "custom platform with heavy anti-bot. Almost certainly Tier-2 browser; do not attempt Tier-0 first." We have not yet run a full probe matrix from AWS egress, but AM is high-value enough that false-negative fetches would silently drop Mustang coverage.

Cost-of-wrong is asymmetric — over-fetching via Tier 2 just costs FlareSolverr time; under-fetching via Tier 0/1 silently under-reports Mustang. The adapter declares `FETCHER_TIER = "browser"` as the conservative default. If follow-up probing shows plain TLS impersonation (`curl_cffi`) clears AM from our egress, demote to `tier1_tls/`.

## Endpoints to probe (not yet confirmed)

| Path | Expected |
| --- | --- |
| `/<product-slug>.html` (product) | likely 403 or challenge from AWS egress |
| `/sitemap.xml` | AM advertises a sitemap; status unconfirmed |
| `/robots.txt` | assumed 200 |
| `/mustang-exhaust.html` etc. (category) | likely behind same anti-bot as product pages |

Re-run the FCP Euro / JEGS probe script against these before enabling live crawling.

## Product URL pattern

AM uses a flat, slugified URL shape:

- `/<product-slug>.html`
  Example: `/mmd-slotted-hood-07-09.html`, `/borla-s-type-axleback-exhaust-11-12gt.html`

The slug usually leads with a brand token (`mmd`, `borla`, `steeda`, `roush`, `ford-performance`) and often ends with a fitment year range. **Do not** regex brand / part-number from the URL:

- The leading token is only reliable when the brand is a single word. Multi-word brands (`ford-performance`, `bbk-performance`) collide with product descriptors.
- AM's own SKU (`J110088`-style alphanumeric) is not in the URL at all.
- The year-range suffix is fitment data, not a part identifier.

JSON-LD `sku` + `brand.name` and DOM meta are the trustworthy signals. This matches the posture of the `tirerack.py` adapter — the URL shape churns enough that URL-derived fallback is a net negative.

## Discovery plan (when Tier 2 is wired)

- **Do not** walk the vehicle-year selector (`/2015-2023-mustang-gt/...` etc.). Same problem as the ECS fitment tree: the same product appears under many year-branch URLs, producing large duplicate sets.
- Walk category / brand index pages instead (`/mustang-exhaust.html`, `/mustang-suspension.html`, `/mustang-brakes.html`, and `/brand/<brand-slug>` if AM exposes brand landing pages). These are flatter and enumerate cleanly.
- Respect `robots.txt` Crawl-delay if set — shared `fetch_with_retries` handles it.
- Expect a 6-figure URL count for a full walk. Operators should crawl one category at a time (`CRAWLER_AMERICANMUSCLE_START_URLS` env var when discovery lands).

## Open questions (need a real page sample)

Without a post-challenge HTML snapshot we can't confirm:

- Does AM emit JSON-LD `Product` (name, brand, sku, mpn, gtin, offers.price, image)? The synthetic test pages assume a plain `schema.org/Product` shape; tighten against a fixture once captured.
- What are the DOM selectors for title / price / SKU / brand (class names, `data-*` attributes)? AM historically has an "Item J-number" style SKU visible in a product-info block.
- Is fitment (year / model / trim) exposed as structured data, or only as free text in the DOM? Mustang fitment is the main reason AM exists — structured fitment would be high-value to extract if emitted.
- What's the image CDN pattern (for allowlisting in the frontend image-host whitelist)?
- Bundle / kit landing pages — AM sells "stage" packages (e.g. Stage 1 Power Packs). Decide whether those need to be rejected at parse time or treated as distinct SKUs.

Next step before enabling live crawling: capture a real product page via the Chrome extension and drop it under `backend/tests/crawlers/fixtures/americanmuscle/` so parser selectors can be tightened and a probe run can confirm the fetcher tier.

## Paths forward

1. **Extension-only adapter (this change).** `parse_product_page()` tuned to a generic JSON-LD + DOM shape; hostname wired into `adapter_name_for_product_url()`. The Chrome extension scrapes pages the user already loaded in their browser (post-challenge), so anti-bot is not a blocker for extension-captured HTML. `discover_product_urls()` is a stub.

2. **Crawler + FlareSolverr.** Add category / brand-index walking once Tier 2 is deployed (`FLARESOLVERR_URL` configured). Note that category index pages are themselves behind the anti-bot stack, so discovery also flows through the Tier 2 fetcher.
