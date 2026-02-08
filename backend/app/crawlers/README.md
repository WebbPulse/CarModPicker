# Crawler infrastructure

Per-retailer crawlers for scraping part information at scale. Run from the **backend** directory.

**Brands are central:** All crawlers and the chrome extension use the same database. `get_or_create_brand_by_name` ensures a brand is only defined once; you define or edit brands in the app and they apply everywhere.

## Run

```bash
python -m app.crawlers --adapter <name> [--limit N] [--delay SEC]
```

**Required env:**

- **CRAWLER_USER_ID** – User ID that will own crawler-created parts (must have create permission).
- **CRAWLER_DEFAULT_CATEGORY_ID** or **CRAWLER_DEFAULT_CATEGORY_NAME** – Category for new parts (e.g. `exhaust`). If both unset, the first active category in the DB is used.

**Options:**

- `--adapter` – Adapter name (e.g. `example`). Required.
- `--limit` – Max product URLs to process (default: no limit).
- `--delay` – Seconds between requests (default: 2.5). If the site sets a higher **Crawl-delay** in robots.txt, that value is used. Jitter (±20%) is applied so traffic doesn't look robotic.

**Heavy runs:** A run is considered heavy when you're hitting a lot of pages in one go—e.g. no `--limit` (or a high limit), running all adapters, or a full sitemap. For heavy runs, use a higher delay (e.g. `--delay 5` or `delay_sec: 5` in the admin API) to stay well within polite-crawler norms and reduce the chance of rate limits or blocks.

**Robots.txt:** The crawler respects robots.txt per origin: before each product-page request it checks that the configured user agent is allowed to fetch the URL. Disallowed URLs are skipped (and logged). If a site specifies **Crawl-delay**, we use the larger of `--delay` and that value. If robots.txt is unreachable or errors, we allow the request (we do not block the crawl).

**Rate limiting:** Staying unbanned is prioritized over speed. On **429 (Too Many Requests)** or **503 (Service Unavailable)**, the crawler backs off and retries: it honors the **Retry-After** header when present, otherwise uses exponential backoff (2^n seconds, capped), with ±20% jitter to avoid synchronized retries. After 5 retries the request fails. All fetches (product pages and discovery, e.g. sitemaps) use this logic.

**Example (A90 Shop):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=wheels
python -m app.crawlers --adapter a90shop --limit 5
```

Optional: `CRAWLER_A90SHOP_START_URLS` (comma-separated) overrides the default product URLs for the a90shop adapter.

## Adding a retailer adapter

1. Create `adapters/<retailer>.py` (e.g. `summit_racing.py`).
2. Subclass `RetailerCrawlerAdapter` and implement:
   - `discover_product_urls()` – yield product page URLs (sitemap, category, search).
   - `parse_product_page(html, url)` – return a `ScrapedPayload` or `None`.
3. Register in `adapters/__init__.py`: add to `ADAPTER_REGISTRY` and optionally `get_adapter` choices.

See `adapters/example.py` for a stub and `base.py` for the `ScrapedPayload` contract.
