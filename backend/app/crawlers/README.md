# Crawler infrastructure

Per-retailer crawlers for scraping part information at scale. Run from the **backend** directory.

**PartManufacturers are central:** All crawlers and the chrome extension use the same database. `get_or_create_part_manufacturer_by_name` ensures a part_manufacturer is only defined once; you define or edit part_manufacturers in the app and they apply everywhere.

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

**Example (Studio RSR):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=roll-cage
python -m app.crawlers --adapter studiorsr --limit 5
```

Optional: `CRAWLER_STUDIORSR_START_URLS` (comma-separated) overrides product URLs for the studiorsr adapter. By default, product URLs are discovered via sitemap.xml (all URLs containing `/products/`).

**Example (ADRO):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=aero
python -m app.crawlers --adapter adro --limit 5
```

Optional: `CRAWLER_ADRO_START_URLS` (comma-separated) overrides product URLs for the adro adapter. By default, product URLs are discovered via sitemap.xml (all URLs containing `/products/`). Brand is always normalized to `ADRO` (titles lead with the target vehicle, so the generic title heuristic would otherwise pick the car make).

**Full-page archive (optional):** To keep a copy of each product page for post-processing or re-parsing:

- **CRAWL_HTML_SAVE_DIR** – Directory to save HTML (e.g. `./crawl_cache`). When set, we save a full page copy for **new URLs only** (first time we see that product URL). Recrawls (known URLs) still fetch and update price but do not write HTML by default.
- **CRAWL_HTML_SAVE_ON_RECRAWL** – Set to `1`, `true`, or `yes` to also overwrite the saved HTML when recrawling known URLs (so you always have the latest page copy; overwriting is one write per URL).

Files are stored as `CRAWL_HTML_SAVE_DIR/<adapter>/<url_hash>.html` with a sidecar `<url_hash>.url` containing the product URL so you can re-parse later without re-fetching.

## Adding a retailer adapter

1. Create `adapters/<retailer>.py` (e.g. `summit_racing.py`).
2. Subclass `RetailerCrawlerAdapter` and implement:
   - `discover_product_urls()` – yield product page URLs (sitemap, category, search).
   - `parse_product_page(html, url)` – return a `ScrapedPayload` or `None`.
3. Register in `adapters/__init__.py`: add to `ADAPTER_REGISTRY` and optionally `get_adapter` choices.

See `adapters/a90shop.py` and `adapters/studiorsr.py` for examples; `parsing.py` for shared helpers (JSON-LD, meta_content, extract_dom_price, part_manufacturer_from_title); and `base.py` for the `ScrapedPayload` contract.
